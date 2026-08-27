"""Deterministic local execution adapter for FitForge Agent (Milestone 1 baseline)."""

from typing import List

from app.agents.action_planner import ActionPlannerAgent
from app.agents.evidence import EvidenceAgent
from app.agents.fit_analyst import FitAnalystAgent
from app.agents.intake import IntakeAgent
from app.agents.quality_gate import QualityGateAgent
from app.execution.base import WorkflowExecutionAdapter
from app.models import (
    ActionPlan,
    EvidenceItem,
    FitAssessment,
    NormalizedInput,
    QualityGateResult,
    WorkflowInput,
)


class DeterministicExecutionAdapter(WorkflowExecutionAdapter):
    """Adapter executing the verified deterministic rule-based specialist agents."""

    def __init__(self) -> None:
        self.intake_agent = IntakeAgent()
        self.evidence_agent = EvidenceAgent()
        self.fit_analyst = FitAnalystAgent()
        self.action_planner = ActionPlannerAgent()
        self.quality_gate = QualityGateAgent()

    @property
    def mode_name(self) -> str:
        return "deterministic"

    def run_intake(self, inputs: WorkflowInput) -> NormalizedInput:
        return self.intake_agent.run(inputs)

    def run_evidence(self, normalized_inputs: NormalizedInput) -> List[EvidenceItem]:
        return self.evidence_agent.run(normalized_inputs)

    def run_fit_analyst(
        self, normalized_inputs: NormalizedInput, matrix: List[EvidenceItem]
    ) -> FitAssessment:
        return self.fit_analyst.run(normalized_inputs, matrix)

    def run_action_planner(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
    ) -> ActionPlan:
        return self.action_planner.run(normalized_inputs, matrix, fit_assessment)

    def run_quality_gate(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
        action_plan: ActionPlan,
        current_corrections: int = 0,
    ) -> QualityGateResult:
        return self.quality_gate.run(
            normalized_inputs=normalized_inputs,
            evidence_matrix=matrix,
            fit_assessment=fit_assessment,
            action_plan=action_plan,
            current_corrections=current_corrections,
        )

    def apply_quality_corrections(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        quality_report: QualityGateResult,
    ) -> List[EvidenceItem]:
        return self.quality_gate.apply_corrections(
            normalized_inputs=normalized_inputs,
            matrix=matrix,
            quality_report=quality_report,
        )
