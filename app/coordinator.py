"""Workflow Coordinator: Orchestrates multi-agent pipeline and enforces state transitions & audit logs.

Correction-pass behaviour (Milestone 1 QA):
- On first QG failure, coordinator uses QualityGateAgent.apply_corrections
  to downgrade/remove unsupported evidence, then recalculates fit, regenerates
  the action plan, and revalidates.
- If the second QG still fails, the workflow enters the `failed` state.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.agents.action_planner import ActionPlannerAgent
from app.agents.evidence import EvidenceAgent
from app.agents.fit_analyst import FitAnalystAgent
from app.agents.intake import IntakeAgent
from app.agents.quality_gate import QualityGateAgent
from app.models import (
    AuditEvent,
    RecommendationType,
    WorkflowInput,
    WorkflowResult,
    WorkflowState,
)
from app.repositories.in_memory import WorkflowRepository, workflow_repo


class WorkflowCoordinator:
    """Coordinator that orchestrates specialist agents through defined state transitions."""

    def __init__(self, repo: Optional[WorkflowRepository] = None) -> None:
        self.repo = repo or workflow_repo
        self.intake_agent = IntakeAgent()
        self.evidence_agent = EvidenceAgent()
        self.fit_analyst = FitAnalystAgent()
        self.action_planner = ActionPlannerAgent()
        self.quality_gate = QualityGateAgent()

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

    def execute_workflow(self, inputs: WorkflowInput, workflow_id: Optional[str] = None) -> WorkflowResult:
        wid = workflow_id or str(uuid4())
        workflow = WorkflowResult(
            workflow_id=wid,
            state=WorkflowState.CREATED,
            inputs=inputs,
        )
        initial_event = AuditEvent(
            from_state=None,
            to_state=WorkflowState.CREATED,
            agent_name="Coordinator",
            message="Workflow initialized for job assessment.",
        )
        workflow.audit_trail.append(initial_event)
        self.repo.save(workflow)

        try:
            if not inputs.resume_text.strip() or not inputs.job_description_text.strip():
                self._transition_state(
                    workflow, WorkflowState.FAILED, "Coordinator",
                    "Workflow failed: Missing required résumé or job description text.",
                )
                workflow.error = "Missing required input: résumé and job description must not be empty."
                self.repo.save(workflow)
                return workflow

            # Stage 1: Intake
            self._transition_state(
                workflow, WorkflowState.NORMALIZING, self.intake_agent.name,
                "Normalizing input text, parsing sections, and checking for missing criteria.",
            )
            normalized_inputs = self.intake_agent.run(inputs)
            workflow.normalized_inputs = normalized_inputs

            # Stage 2: Evidence
            self._transition_state(
                workflow, WorkflowState.MAPPING_EVIDENCE, self.evidence_agent.name,
                "Extracting job requirements and mapping candidate résumé evidence.",
            )
            evidence_matrix = self.evidence_agent.run(normalized_inputs)
            workflow.evidence_matrix = evidence_matrix

            # Stage 3: Fit Analyst
            self._transition_state(
                workflow, WorkflowState.SCORING_FIT, self.fit_analyst.name,
                "Calculating fit score, evaluating non-negotiables, and formulating recommendation.",
            )
            fit_assessment = self.fit_analyst.run(normalized_inputs, evidence_matrix)
            workflow.fit_assessment = fit_assessment

            # Stage 4: Action Planner
            self._transition_state(
                workflow, WorkflowState.PLANNING_ACTIONS, self.action_planner.name,
                "Generating prioritized next steps, employer clarification questions, and interview preparation.",
            )
            action_plan = self.action_planner.run(normalized_inputs, evidence_matrix, fit_assessment)
            workflow.action_plan = action_plan

            # Stage 5: Quality Gate
            self._transition_state(
                workflow, WorkflowState.VALIDATING, self.quality_gate.name,
                "Auditing outputs for unsupported claims, contradictions, and completeness.",
            )
            quality_report = self.quality_gate.run(
                normalized_inputs=normalized_inputs,
                evidence_matrix=evidence_matrix,
                fit_assessment=fit_assessment,
                action_plan=action_plan,
                current_corrections=0,
            )
            workflow.quality_report = quality_report

            # Correction pass (max ONE)
            if not quality_report.passed:
                self._transition_state(
                    workflow, WorkflowState.VALIDATING, "Coordinator",
                    f"Initiating correction pass #1 to resolve {len(quality_report.issues)} validation issue(s).",
                )

                # 1. Downgrade / remove unsupported evidence
                evidence_matrix = self.quality_gate.apply_corrections(
                    normalized_inputs, evidence_matrix, quality_report,
                )
                workflow.evidence_matrix = evidence_matrix

                # 2. Recalculate fit with corrected matrix
                fit_assessment = self.fit_analyst.run(normalized_inputs, evidence_matrix)
                workflow.fit_assessment = fit_assessment

                # 3. Regenerate action plan
                action_plan = self.action_planner.run(normalized_inputs, evidence_matrix, fit_assessment)
                workflow.action_plan = action_plan

                # 4. Revalidate
                quality_report = self.quality_gate.run(
                    normalized_inputs=normalized_inputs,
                    evidence_matrix=evidence_matrix,
                    fit_assessment=fit_assessment,
                    action_plan=action_plan,
                    current_corrections=1,
                )
                workflow.quality_report = quality_report

            # Final verdict
            if quality_report.passed:
                self._transition_state(
                    workflow, WorkflowState.COMPLETED, "Coordinator",
                    "All workflow stages and quality gates completed successfully.",
                )
            else:
                self._transition_state(
                    workflow, WorkflowState.FAILED, "Coordinator",
                    f"Workflow failed quality gate after 1 correction pass: {'; '.join(quality_report.issues)}",
                )
                workflow.error = f"Quality gate validation failed: {'; '.join(quality_report.issues)}"

            self.repo.save(workflow)
            return workflow

        except Exception as e:
            self._transition_state(
                workflow, WorkflowState.FAILED, "Coordinator",
                f"Workflow execution encountered fatal exception: {str(e)}",
            )
            workflow.error = str(e)
            self.repo.save(workflow)
            return workflow
