"""Workflow Coordinator: Orchestrates multi-agent pipeline and enforces state transitions & audit logs.

Milestone 2 Architecture:
- Uses pluggable WorkflowExecutionAdapter (Deterministic or Gemini ADK).
- Strict state transitions with timestamped audit events.
- Never silently falls back from Gemini to deterministic on failure.
"""

from datetime import datetime, timezone
import logging
from typing import Optional
from uuid import uuid4

from app.execution.base import WorkflowExecutionAdapter
from app.execution.deterministic import DeterministicExecutionAdapter
from app.execution.gemini_adk import GeminiAdkExecutionAdapter
from app.models import (
    AuditEvent,
    RecommendationType,
    WorkflowInput,
    WorkflowResult,
    WorkflowState,
)
from app.repositories import BaseWorkflowRepository, get_repository
from app.settings import Settings, get_settings

logger = logging.getLogger("fitforge.coordinator")


class WorkflowCoordinator:
    """Coordinator that orchestrates specialist agents through defined state transitions."""

    def __init__(
        self,
        repo: Optional[BaseWorkflowRepository] = None,
        adapter: Optional[WorkflowExecutionAdapter] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.repo = repo or get_repository(settings=self.settings)

        if adapter is not None:
            self.adapter = adapter
        elif self.settings.is_gemini_mode:
            self.adapter = GeminiAdkExecutionAdapter(settings=self.settings)
        else:
            self.adapter = DeterministicExecutionAdapter()

    def _transition_state(
        self,
        workflow: WorkflowResult,
        to_state: WorkflowState,
        agent_name: str,
        message: str,
        details: Optional[dict] = None,
    ) -> None:
        from_state = workflow.state
        workflow.state = to_state
        workflow.updated_at = datetime.now(timezone.utc).isoformat()
        event = AuditEvent(
            from_state=from_state,
            to_state=to_state,
            agent_name=agent_name,
            message=message,
            details=details,
        )
        workflow.audit_trail.append(event)
        self.repo.save(workflow)

    def execute_workflow(
        self, inputs: WorkflowInput, workflow_id: Optional[str] = None
    ) -> WorkflowResult:
        """Run the full 5-stage agent workflow via the configured execution adapter."""
        wid = workflow_id or str(uuid4())
        workflow = WorkflowResult(
            workflow_id=wid,
            state=WorkflowState.CREATED,
            execution_mode=self.adapter.mode_name,
            inputs=inputs,
        )
        initial_event = AuditEvent(
            from_state=None,
            to_state=WorkflowState.CREATED,
            agent_name="Coordinator",
            message=f"Workflow initialized for job assessment [{self.adapter.mode_name} mode].",
            details={"mode": self.adapter.mode_name},
        )
        workflow.audit_trail.append(initial_event)
        self.repo.save(workflow)

        try:
            if not inputs.resume_text.strip() or not inputs.job_description_text.strip():
                self._transition_state(
                    workflow,
                    WorkflowState.FAILED,
                    "Coordinator",
                    "Workflow failed: Missing required résumé or job description text.",
                )
                workflow.error = "Missing required input: résumé and job description must not be empty."
                self.repo.save(workflow)
                return workflow

            # Stage 1: Intake
            self._transition_state(
                workflow,
                WorkflowState.NORMALIZING,
                "Intake Agent",
                f"Normalizing input text, parsing sections, and checking for missing criteria [{self.adapter.mode_name}].",
            )
            normalized_inputs = self.adapter.run_intake(inputs)
            workflow.normalized_inputs = normalized_inputs

            # Stage 2: Evidence
            self._transition_state(
                workflow,
                WorkflowState.MAPPING_EVIDENCE,
                "Evidence Agent",
                f"Extracting job requirements and mapping candidate résumé evidence [{self.adapter.mode_name}].",
            )
            evidence_matrix = self.adapter.run_evidence(normalized_inputs)
            workflow.evidence_matrix = evidence_matrix

            # Stage 3: Fit Analyst
            self._transition_state(
                workflow,
                WorkflowState.SCORING_FIT,
                "Fit Analyst",
                f"Calculating fit score, evaluating non-negotiables, and formulating recommendation [{self.adapter.mode_name}].",
            )
            fit_assessment = self.adapter.run_fit_analyst(normalized_inputs, evidence_matrix)
            workflow.fit_assessment = fit_assessment

            # Stage 4: Action Planner
            self._transition_state(
                workflow,
                WorkflowState.PLANNING_ACTIONS,
                "Action Planner",
                f"Generating prioritized next steps, employer clarification questions, and interview preparation [{self.adapter.mode_name}].",
            )
            action_plan = self.adapter.run_action_planner(
                normalized_inputs, evidence_matrix, fit_assessment
            )
            workflow.action_plan = action_plan

            # Stage 5: Quality Gate
            self._transition_state(
                workflow,
                WorkflowState.VALIDATING,
                "Quality Gate",
                f"Auditing outputs for unsupported claims, contradictions, and completeness [{self.adapter.mode_name}].",
            )
            quality_report = self.adapter.run_quality_gate(
                normalized_inputs=normalized_inputs,
                matrix=evidence_matrix,
                fit_assessment=fit_assessment,
                action_plan=action_plan,
                current_corrections=0,
            )
            workflow.quality_report = quality_report

            # Correction pass (max ONE)
            if not quality_report.passed:
                self._transition_state(
                    workflow,
                    WorkflowState.VALIDATING,
                    "Coordinator",
                    f"Initiating correction pass #1 to resolve {len(quality_report.issues)} validation issue(s).",
                )

                # 1. Downgrade / remove unsupported evidence
                evidence_matrix = self.adapter.apply_quality_corrections(
                    normalized_inputs, evidence_matrix, quality_report
                )
                workflow.evidence_matrix = evidence_matrix

                # 2. Recalculate fit with corrected matrix
                fit_assessment = self.adapter.run_fit_analyst(normalized_inputs, evidence_matrix)
                workflow.fit_assessment = fit_assessment

                # 3. Regenerate action plan
                action_plan = self.adapter.run_action_planner(
                    normalized_inputs, evidence_matrix, fit_assessment
                )
                workflow.action_plan = action_plan

                # 4. Revalidate
                quality_report = self.adapter.run_quality_gate(
                    normalized_inputs=normalized_inputs,
                    matrix=evidence_matrix,
                    fit_assessment=fit_assessment,
                    action_plan=action_plan,
                    current_corrections=1,
                )
                workflow.quality_report = quality_report

            # Final verdict
            if quality_report.passed:
                self._transition_state(
                    workflow,
                    WorkflowState.COMPLETED,
                    "Coordinator",
                    "All workflow stages and quality gates completed successfully.",
                )
            else:
                self._transition_state(
                    workflow,
                    WorkflowState.FAILED,
                    "Coordinator",
                    f"Workflow failed quality gate after 1 correction pass: {'; '.join(quality_report.issues)}",
                )
                workflow.error = f"Quality gate validation failed: {'; '.join(quality_report.issues)}"

            self.repo.save(workflow)
            return workflow

        except Exception as e:
            logger.error("Workflow failed with error in mode '%s': %s", self.adapter.mode_name, str(e))
            self._transition_state(
                workflow,
                WorkflowState.FAILED,
                "Coordinator",
                f"Workflow execution encountered exception: {str(e)}",
            )
            workflow.error = str(e)
            self.repo.save(workflow)
            return workflow
