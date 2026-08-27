"""Abstract base class for workflow execution adapters."""

from abc import ABC, abstractmethod
from typing import List

from app.models import (
    ActionPlan,
    EvidenceItem,
    FitAssessment,
    NormalizedInput,
    QualityGateResult,
    WorkflowInput,
)


class WorkflowExecutionAdapter(ABC):
    """Abstract execution adapter defining specialist stage interfaces."""

    @property
    @abstractmethod
    def mode_name(self) -> str:
        """Name of the execution mode ('deterministic' or 'gemini')."""
        pass

    @abstractmethod
    def run_intake(self, inputs: WorkflowInput) -> NormalizedInput:
        """Execute Stage 1: Intake Agent."""
        pass

    @abstractmethod
    def run_evidence(self, normalized_inputs: NormalizedInput) -> List[EvidenceItem]:
        """Execute Stage 2: Evidence Agent."""
        pass

    @abstractmethod
    def run_fit_analyst(
        self, normalized_inputs: NormalizedInput, matrix: List[EvidenceItem]
    ) -> FitAssessment:
        """Execute Stage 3: Fit Analyst Agent."""
        pass

    @abstractmethod
    def run_action_planner(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
    ) -> ActionPlan:
        """Execute Stage 4: Action Planner Agent."""
        pass

    @abstractmethod
    def run_quality_gate(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
        action_plan: ActionPlan,
        current_corrections: int = 0,
    ) -> QualityGateResult:
        """Execute Stage 5: Quality Gate Agent."""
        pass

    @abstractmethod
    def apply_quality_corrections(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        quality_report: QualityGateResult,
    ) -> List[EvidenceItem]:
        """Apply deterministic quality gate corrections."""
        pass
