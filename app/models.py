"""Data models for FitForge Agent workflow orchestration."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class WorkflowState(str, Enum):
    """Workflow state lifecycle states."""
    CREATED = "created"
    NORMALIZING = "normalizing"
    MAPPING_EVIDENCE = "mapping_evidence"
    SCORING_FIT = "scoring_fit"
    PLANNING_ACTIONS = "planning_actions"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class EvidenceClassification(str, Enum):
    """Evidence strength classifications."""
    DIRECT = "direct"
    TRANSFERABLE = "transferable"
    INFERENCE = "inference"
    MISSING = "missing"


class RecommendationType(str, Enum):
    """Final assessment recommendation categories."""
    PURSUE = "Pursue"
    INVESTIGATE = "Investigate"
    PASS = "Pass"


class AuditEvent(BaseModel):
    """Timestamped audit trail record for state transitions and agent actions."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    from_state: Optional[WorkflowState] = None
    to_state: WorkflowState
    agent_name: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ApplicantPriorities(BaseModel):
    """Applicant preferences and non-negotiables."""
    min_compensation: Optional[str] = Field(
        default=None, description="Desired minimum compensation"
    )
    location_preference: Optional[str] = Field(
        default=None, description="Location, commute, or travel boundaries"
    )
    desired_role_type: Optional[str] = Field(
        default=None, description="Role title, level, or domain preference"
    )
    non_negotiables: List[str] = Field(
        default_factory=list, description="List of non-negotiable requirements"
    )


class WorkflowInput(BaseModel):
    """Raw inputs provided to start a workflow."""
    resume_text: str = Field(..., min_length=1, description="Raw text of the résumé")
    job_description_text: str = Field(
        ..., min_length=1, description="Raw text of the job description"
    )
    priorities: ApplicantPriorities = Field(
        default_factory=ApplicantPriorities,
        description="Applicant priorities and constraints"
    )


class NormalizedInput(BaseModel):
    """Cleaned and normalized representations of input texts."""
    normalized_resume: str
    normalized_job_description: str
    normalized_priorities: ApplicantPriorities
    identified_missing_inputs: List[str] = Field(default_factory=list)
    resume_sections: Dict[str, str] = Field(default_factory=dict)
    job_key_attributes: Dict[str, Any] = Field(default_factory=dict)


class EvidenceItem(BaseModel):
    """Individual job requirement mapped to résumé evidence."""
    requirement: str
    category: str
    classification: EvidenceClassification
    resume_evidence: str
    reasoning: str
    parent_requirement: Optional[str] = Field(
        default=None,
        description="Original compound requirement from which this atomic claim was decomposed",
    )
    atomic_claim: Optional[str] = Field(
        default=None,
        description="Decomposed atomic requirement statement",
    )


class FitAssessment(BaseModel):
    """Fit scoring and recommendation analysis."""
    fit_score: int = Field(..., ge=0, le=100, description="Overall fit score from 0 to 100")
    recommendation: RecommendationType
    score_explanation: str
    uncertainty_explanation: str
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class ActionPlan(BaseModel):
    """Actionable steps, application brief, and interview preparation."""
    application_brief: str
    prioritized_next_actions: List[str] = Field(default_factory=list)
    clarification_questions: List[str] = Field(default_factory=list)
    interview_prep_points: List[str] = Field(default_factory=list)


class QualityGateResult(BaseModel):
    """Quality gate validation findings and integrity checks."""
    is_valid: bool
    passed: bool
    issues: List[str] = Field(default_factory=list)
    correction_count: int = 0
    notes: str = ""


class WorkflowResult(BaseModel):
    """Complete workflow entity including inputs, outputs, state, and audit trail."""
    workflow_id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    state: WorkflowState = WorkflowState.CREATED
    execution_mode: str = Field(
        default="deterministic",
        description="Execution adapter used for this workflow run: 'deterministic' or 'gemini'",
    )
    inputs: WorkflowInput
    normalized_inputs: Optional[NormalizedInput] = None
    evidence_matrix: Optional[List[EvidenceItem]] = None
    fit_assessment: Optional[FitAssessment] = None
    action_plan: Optional[ActionPlan] = None
    quality_report: Optional[QualityGateResult] = None
    audit_trail: List[AuditEvent] = Field(default_factory=list)
    error: Optional[str] = None


class WorkflowCreateResponse(BaseModel):
    """API response when a workflow is submitted."""
    workflow_id: str
    state: WorkflowState
    message: str
