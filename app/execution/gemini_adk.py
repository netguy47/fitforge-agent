"""Google Agent Development Kit (ADK) & Gemini execution adapter for FitForge Agent."""

import asyncio
import concurrent.futures
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
import uuid
from pydantic import BaseModel, Field, ValidationError

import google.adk as adk
from google.adk.runners import InMemoryRunner, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.execution.base import WorkflowExecutionAdapter
from app.models import (
    ActionPlan,
    ApplicantPriorities,
    EvidenceClassification,
    EvidenceItem,
    FitAssessment,
    NormalizedInput,
    QualityGateResult,
    RecommendationType,
    WorkflowInput,
)
from app.prompts.action_planner import ACTION_PLANNER_SYSTEM_INSTRUCTION
from app.prompts.evidence import EVIDENCE_SYSTEM_INSTRUCTION
from app.prompts.fit_analyst import FIT_ANALYST_SYSTEM_INSTRUCTION
from app.prompts.intake import INTAKE_SYSTEM_INSTRUCTION
from app.prompts.quality_gate import QUALITY_GATE_SYSTEM_INSTRUCTION
from app.settings import Settings, get_settings

logger = logging.getLogger("fitforge.adk")

T = TypeVar("T", bound=BaseModel)


# Structured response schemas for ADK / Gemini API communication
class IntakeResponse(BaseModel):
    """API-facing Intake response schema (strictly excludes open dictionaries / additionalProperties)."""
    normalized_resume: str
    normalized_job_description: str
    normalized_priorities: ApplicantPriorities
    identified_missing_inputs: List[str] = Field(default_factory=list)


class EvidenceMatrixResponse(BaseModel):
    """API-facing Evidence Matrix response schema."""
    items: List[EvidenceItem]


def categorize_gemini_error(exc: Exception) -> str:
    """Classify provider or runtime exceptions into sanitized error categories."""
    err_str = str(exc).lower()
    err_type = type(exc).__name__.lower()

    if any(k in err_str or k in err_type for k in ["additionalproperties", "unsupported_mldev_properties", "schema_unsupported", "unsupported property"]):
        return "gemini_schema_unsupported"
    if any(k in err_str or k in err_type for k in ["auth", "401", "unauthenticated", "invalid api key", "credential"]):
        return "gemini_authentication_failed"
    if any(k in err_str or k in err_type for k in ["permission", "403", "forbidden"]):
        return "gemini_permission_denied"
    if any(k in err_str or k in err_type for k in ["rate", "429", "resourceexhausted", "quota", "ratelimit"]):
        return "gemini_rate_limited"
    if any(k in err_str or k in err_type for k in ["timeout", "deadlineexceeded"]):
        return "gemini_timeout"
    if any(k in err_str or k in err_type for k in ["500", "503", "unavailable", "connect", "network", "socket"]):
        return "gemini_unavailable"
    return "gemini_output_invalid"


def _run_coroutine_sync(coro):
    """Execute an asynchronous coroutine synchronously, safe across event loop states."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class GeminiAdkExecutionAdapter(WorkflowExecutionAdapter):
    """Execution adapter orchestrating specialist agents through genuine Google ADK Runners."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        runner_factory: Optional[Callable[[adk.Agent], Runner]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.model_name = self.settings.gemini_model
        self._runner_factory = runner_factory

        # Validate credentials when live mode is configured without a test runner factory
        if self._runner_factory is None:
            self.settings.validate_credentials()

        # Instantiate genuine Google ADK Agents for each stage with clean API-compatible schemas
        self.intake_adk_agent = adk.Agent(
            name="intake_agent",
            description="Normalizes candidate résumé and job description texts with security filtering.",
            model=self.model_name,
            instruction=INTAKE_SYSTEM_INSTRUCTION,
            output_schema=IntakeResponse,
        )

        self.evidence_adk_agent = adk.Agent(
            name="evidence_agent",
            description="Decomposes requirements into atomic claims and maps verbatim résumé evidence.",
            model=self.model_name,
            instruction=EVIDENCE_SYSTEM_INSTRUCTION,
            output_schema=EvidenceMatrixResponse,
        )

        self.fit_analyst_adk_agent = adk.Agent(
            name="fit_analyst_agent",
            description="Calculates quantitative fit score and strategic recommendation.",
            model=self.model_name,
            instruction=FIT_ANALYST_SYSTEM_INSTRUCTION,
            output_schema=FitAssessment,
        )

        self.action_planner_adk_agent = adk.Agent(
            name="action_planner_agent",
            description="Synthesizes application brief, next actions, and STAR talking points.",
            model=self.model_name,
            instruction=ACTION_PLANNER_SYSTEM_INSTRUCTION,
            output_schema=ActionPlan,
        )

        self.quality_gate_adk_agent = adk.Agent(
            name="quality_gate_agent",
            description="Audits assertions, verbatim quotes, contradictions, and completeness.",
            model=self.model_name,
            instruction=QUALITY_GATE_SYSTEM_INSTRUCTION,
            output_schema=QualityGateResult,
        )

    @property
    def mode_name(self) -> str:
        return "gemini"

    def _create_runner_for_agent(self, agent: adk.Agent) -> Any:
        """Create or supply an ADK Runner instance for the given agent."""
        if self._runner_factory is not None:
            return self._runner_factory(agent)
        return InMemoryRunner(agent=agent, app_name="fitforge")

    async def _run_adk_stage_async(
        self,
        agent: adk.Agent,
        prompt_content: str,
        response_model: Type[T],
        stage_name: str,
    ) -> T:
        """Execute agent via ADK Runner, consuming events and enforcing output schemas."""
        start_time = time.monotonic()
        runner = self._create_runner_for_agent(agent)

        user_id = f"fitforge_user_{uuid.uuid4().hex[:8]}"
        session_id = f"fitforge_{agent.name}_{uuid.uuid4().hex[:8]}"

        # Initialize session if session service is accessible
        if hasattr(runner, "session_service") and runner.session_service is not None:
            try:
                await runner.session_service.create_session(
                    app_name="fitforge", user_id=user_id, session_id=session_id
                )
            except Exception:
                pass

        new_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt_content)],
        )

        final_text: Optional[str] = None
        event_output: Any = None
        max_transient_retries = 2 if self._runner_factory is None else 0

        # Execute through ADK runner.run_async with transient retry
        for attempt in range(max_transient_retries + 1):
            final_text = None
            event_output = None
            try:
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=new_message,
                ):
                    if event.error_code or event.error_message:
                        raise RuntimeError(f"ADK Event Error: {event.error_message or event.error_code}")
                    if event.output is not None:
                        event_output = event.output
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                final_text = part.text
                break
            except Exception as prov_err:
                category = categorize_gemini_error(prov_err)
                if category in {"gemini_unavailable", "gemini_rate_limited", "gemini_timeout"} and attempt < max_transient_retries:
                    wait_time = (attempt + 1) * 2
                    logger.warning(
                        "ADK stage '%s' transient error (%s). Retrying in %ds (attempt %d/%d)...",
                        stage_name,
                        category,
                        wait_time,
                        attempt + 1,
                        max_transient_retries,
                    )
                    await asyncio.sleep(wait_time)
                    continue

                if category != "gemini_output_invalid":
                    # Provider-level error: do NOT attempt schema repair
                    duration = time.monotonic() - start_time
                    logger.error(
                        "ADK stage '%s' failed in %.2fs with category: %s",
                        stage_name,
                        duration,
                        category,
                    )
                    raise RuntimeError(f"Gemini execution failed: {category}") from prov_err
                final_text = ""
                break

        # Validate structured output from event
        if event_output is not None:
            if isinstance(event_output, response_model):
                return event_output
            if isinstance(event_output, dict):
                try:
                    return response_model.model_validate(event_output)
                except ValidationError:
                    pass

        # Parse text into target Pydantic model
        if final_text:
            try:
                result = response_model.model_validate_json(final_text)
                duration = time.monotonic() - start_time
                logger.info(
                    "ADK stage '%s' completed successfully in %.2fs via ADK Runner.",
                    stage_name,
                    duration,
                )
                return result
            except (ValidationError, json.JSONDecodeError):
                pass

        # Exactly ONE schema-repair attempt via ADK Runner
        logger.warning(
            "ADK stage '%s' output did not match schema %s. Initiating 1 schema-repair attempt.",
            stage_name,
            response_model.__name__,
        )

        repair_prompt = (
            f"Your previous output did not conform to the required JSON schema for {response_model.__name__}.\n"
            f"Please re-evaluate the original task input below and produce strictly valid JSON matching the schema:\n\n"
            f"{prompt_content}"
        )
        repair_message = types.Content(
            role="user",
            parts=[types.Part.from_text(text=repair_prompt)],
        )

        repair_session_id = f"fitforge_{agent.name}_repair_{uuid.uuid4().hex[:8]}"
        if hasattr(runner, "session_service") and runner.session_service is not None:
            try:
                await runner.session_service.create_session(
                    app_name="fitforge", user_id=user_id, session_id=repair_session_id
                )
            except Exception:
                pass

        repair_text: Optional[str] = None
        repair_output: Any = None

        try:
            async for event in runner.run_async(
                user_id=user_id,
                session_id=repair_session_id,
                new_message=repair_message,
            ):
                if event.error_code or event.error_message:
                    raise RuntimeError(f"ADK Event Error: {event.error_message or event.error_code}")
                if event.output is not None:
                    repair_output = event.output
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            repair_text = part.text
        except Exception as rep_err:
            category = categorize_gemini_error(rep_err)
            raise RuntimeError(f"Gemini execution failed: {category}") from rep_err

        if repair_output is not None:
            if isinstance(repair_output, response_model):
                return repair_output
            if isinstance(repair_output, dict):
                try:
                    return response_model.model_validate(repair_output)
                except ValidationError:
                    pass

        if repair_text:
            try:
                result = response_model.model_validate_json(repair_text)
                duration = time.monotonic() - start_time
                logger.info(
                    "ADK stage '%s' schema-repair succeeded in %.2fs via ADK Runner.",
                    stage_name,
                    duration,
                )
                return result
            except (ValidationError, json.JSONDecodeError) as final_err:
                duration = time.monotonic() - start_time
                logger.error(
                    "ADK stage '%s' failed schema validation after repair in %.2fs.",
                    stage_name,
                    duration,
                )
                raise RuntimeError("Gemini execution failed: gemini_output_invalid") from final_err

        raise RuntimeError("Gemini execution failed: gemini_output_invalid")

    def _execute_stage_sync(
        self,
        agent: adk.Agent,
        prompt_content: str,
        response_model: Type[T],
        stage_name: str,
    ) -> T:
        """Helper to invoke asynchronous ADK runner synchronously."""
        return _run_coroutine_sync(
            self._run_adk_stage_async(
                agent=agent,
                prompt_content=prompt_content,
                response_model=response_model,
                stage_name=stage_name,
            )
        )

    # -------------------------------------------------------------------------
    # Specialist Stage Execution Implementations
    # -------------------------------------------------------------------------

    def run_intake(self, inputs: WorkflowInput) -> NormalizedInput:
        """Execute Stage 1: Intake Agent via ADK Runner and convert to domain NormalizedInput."""
        user_prompt = (
            f"Candidate Résumé:\n```\n{inputs.resume_text}\n```\n\n"
            f"Job Description:\n```\n{inputs.job_description_text}\n```\n\n"
            f"Applicant Priorities:\n```\n{inputs.priorities.model_dump_json(indent=2)}\n```"
        )
        resp = self._execute_stage_sync(
            agent=self.intake_adk_agent,
            prompt_content=user_prompt,
            response_model=IntakeResponse,
            stage_name="Intake Agent",
        )
        return NormalizedInput(
            normalized_resume=resp.normalized_resume,
            normalized_job_description=resp.normalized_job_description,
            normalized_priorities=resp.normalized_priorities,
            identified_missing_inputs=resp.identified_missing_inputs,
            resume_sections={},
            job_key_attributes={},
        )

    def run_evidence(self, normalized_inputs: NormalizedInput) -> List[EvidenceItem]:
        """Execute Stage 2: Evidence Agent via ADK Runner with atomic decomposition."""
        user_prompt = (
            f"Normalized Candidate Résumé:\n```\n{normalized_inputs.normalized_resume}\n```\n\n"
            f"Normalized Job Description:\n```\n{normalized_inputs.normalized_job_description}\n```"
        )
        matrix_resp = self._execute_stage_sync(
            agent=self.evidence_adk_agent,
            prompt_content=user_prompt,
            response_model=EvidenceMatrixResponse,
            stage_name="Evidence Agent",
        )

        # Post-validation safety verification on evidence grounding
        resume_text = normalized_inputs.normalized_resume
        matrix = matrix_resp.items
        for item in matrix:
            req_lower = (item.requirement or "").lower()
            if "driver" in req_lower and "license" in req_lower:
                if item.resume_evidence != "None found in résumé." and item.resume_evidence not in resume_text:
                    item.classification = EvidenceClassification.MISSING
                    item.resume_evidence = "None found in résumé."
                    item.reasoning = "Driver's license unverified in candidate résumé."
            elif item.classification != EvidenceClassification.MISSING:
                if item.resume_evidence != "None found in résumé." and item.resume_evidence not in resume_text:
                    item.classification = EvidenceClassification.MISSING
                    item.resume_evidence = "None found in résumé."
                    item.reasoning = "Unverified claim: cited text was not found verbatim in résumé."

        return matrix

    def run_fit_analyst(
        self, normalized_inputs: NormalizedInput, matrix: List[EvidenceItem]
    ) -> FitAssessment:
        """Execute Stage 3: Fit Analyst Agent via ADK Runner."""
        user_prompt = (
            f"Evidence Matrix:\n```\n{json.dumps([i.model_dump() for i in matrix], indent=2)}\n```\n\n"
            f"Applicant Priorities & Non-Negotiables:\n```\n{normalized_inputs.normalized_priorities.model_dump_json(indent=2)}\n```\n\n"
            f"Job Description:\n```\n{normalized_inputs.normalized_job_description}\n```"
        )
        assessment = self._execute_stage_sync(
            agent=self.fit_analyst_adk_agent,
            prompt_content=user_prompt,
            response_model=FitAssessment,
            stage_name="Fit Analyst Agent",
        )

        has_missing = any(i.classification == EvidenceClassification.MISSING for i in matrix)
        if has_missing and assessment.recommendation == RecommendationType.PURSUE:
            assessment.recommendation = RecommendationType.INVESTIGATE
            assessment.score_explanation += " (Recommendation adjusted to 'Investigate' pending verification of missing qualification items)."

        return assessment

    def run_action_planner(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
    ) -> ActionPlan:
        """Execute Stage 4: Action Planner Agent via ADK Runner."""
        user_prompt = (
            f"Candidate Résumé:\n```\n{normalized_inputs.normalized_resume}\n```\n\n"
            f"Job Description:\n```\n{normalized_inputs.normalized_job_description}\n```\n\n"
            f"Evidence Matrix:\n```\n{json.dumps([i.model_dump() for i in matrix], indent=2)}\n```\n\n"
            f"Fit Assessment:\n```\n{fit_assessment.model_dump_json(indent=2)}\n```"
        )
        return self._execute_stage_sync(
            agent=self.action_planner_adk_agent,
            prompt_content=user_prompt,
            response_model=ActionPlan,
            stage_name="Action Planner Agent",
        )

    def run_quality_gate(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
        action_plan: ActionPlan,
        current_corrections: int = 0,
    ) -> QualityGateResult:
        """Execute Stage 5: Quality Gate Agent via ADK Runner."""
        user_prompt = (
            f"Normalized Candidate Résumé:\n```\n{normalized_inputs.normalized_resume}\n```\n\n"
            f"Evidence Matrix:\n```\n{json.dumps([i.model_dump() for i in matrix], indent=2)}\n```\n\n"
            f"Fit Assessment:\n```\n{fit_assessment.model_dump_json(indent=2)}\n```\n\n"
            f"Action Plan:\n```\n{action_plan.model_dump_json(indent=2)}\n```"
        )
        report = self._execute_stage_sync(
            agent=self.quality_gate_adk_agent,
            prompt_content=user_prompt,
            response_model=QualityGateResult,
            stage_name="Quality Gate Agent",
        )
        report.correction_count = current_corrections

        # Deterministic secondary assertion on verbatim quotes
        resume_text = normalized_inputs.normalized_resume
        deterministic_issues: List[str] = list(report.issues)
        for idx, item in enumerate(matrix):
            if item.classification != EvidenceClassification.MISSING:
                if item.resume_evidence != "None found in résumé." and item.resume_evidence not in resume_text:
                    deterministic_issues.append(
                        f"Unsupported Claim in requirement #{idx+1}: Evidence is not a verbatim résumé substring."
                    )

        if deterministic_issues and report.passed:
            report.passed = False
            report.is_valid = False
            report.issues = deterministic_issues
            report.notes = f"Quality gate flagged {len(deterministic_issues)} issue(s)."

        return report

    def apply_quality_corrections(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        quality_report: QualityGateResult,
    ) -> List[EvidenceItem]:
        """Apply deterministic quality gate corrections."""
        resume_text = normalized_inputs.normalized_resume
        corrected: List[EvidenceItem] = []

        for item in matrix:
            if item.classification == EvidenceClassification.MISSING:
                corrected.append(item)
            elif item.resume_evidence == "None found in résumé." or item.resume_evidence in resume_text:
                corrected.append(item)
            else:
                corrected.append(
                    EvidenceItem(
                        requirement=item.requirement,
                        category=item.category,
                        classification=EvidenceClassification.MISSING,
                        resume_evidence="None found in résumé.",
                        reasoning="Correction: Original claim was unsupported by verbatim résumé text.",
                        parent_requirement=item.parent_requirement,
                        atomic_claim=item.atomic_claim,
                    )
                )

        return corrected
