"""Tests for Quality Gate Agent: Unsupported claim detection, verbatim grounding, contradiction prevention, correction pass.

Milestone 1 QA additions:
- test_verbatim_grounding_check: verifies that non-missing evidence must be a verbatim
  résumé substring or the gate fails.
- test_apply_corrections_downgrades_unsupported: validates the correction pass method.
"""

import pytest
from app.agents.quality_gate import QualityGateAgent
from app.coordinator import WorkflowCoordinator
from app.models import (
    ActionPlan,
    ApplicantPriorities,
    EvidenceClassification,
    EvidenceItem,
    FitAssessment,
    NormalizedInput,
    RecommendationType,
    WorkflowInput,
    WorkflowState,
)


def test_quality_gate_passes_clean_inputs():
    """Verify Quality Gate passes valid and grounded data."""
    gate = QualityGateAgent()
    norm = NormalizedInput(
        normalized_resume="Experience at Apex Hospitality managing 7 restaurant units with $16.5M revenue.",
        normalized_job_description="District Manager wanted for restaurant units.",
        normalized_priorities=ApplicantPriorities(),
    )
    matrix = [
        EvidenceItem(
            requirement="District multi-unit management",
            category="Operations",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="Experience at Apex Hospitality managing 7 restaurant units with $16.5M revenue.",
            reasoning="Direct match",
        )
    ]
    assessment = FitAssessment(
        fit_score=85,
        recommendation=RecommendationType.PURSUE,
        score_explanation="Detailed score rationale.",
        uncertainty_explanation="Low uncertainty.",
    )
    plan = ActionPlan(
        application_brief="Candidate is well aligned.",
        prioritized_next_actions=["Submit resume"],
        clarification_questions=["Clarify bonus"],
        interview_prep_points=["STAR Story"],
    )

    result = gate.run(norm, matrix, assessment, plan, current_corrections=0)
    assert result.is_valid is True
    assert result.passed is True
    assert len(result.issues) == 0


def test_unsupported_claim_rejection():
    """Verify Quality Gate flags fabricated claims where evidence does not exist in résumé."""
    gate = QualityGateAgent()
    norm = NormalizedInput(
        normalized_resume="Marketing coordinator with social media and digital campaign experience.",
        normalized_job_description="Executive Chef requiring master pastry certification.",
        normalized_priorities=ApplicantPriorities(),
    )
    matrix = [
        EvidenceItem(
            requirement="Master Pastry Chef certification and chocolate tempering mastery",
            category="Culinary",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="Master Chocolatier Certified with 15 years artisanal bakery leadership.",
            reasoning="Invented qualification",
        )
    ]
    assessment = FitAssessment(
        fit_score=95,
        recommendation=RecommendationType.PURSUE,
        score_explanation="Score",
        uncertainty_explanation="Uncertainty",
    )
    plan = ActionPlan(
        application_brief="Brief",
        prioritized_next_actions=["Apply"],
        clarification_questions=["Question"],
        interview_prep_points=["STAR"],
    )

    result = gate.run(norm, matrix, assessment, plan, current_corrections=0)
    assert result.is_valid is False
    assert result.passed is False
    assert any("Unsupported Claim" in issue for issue in result.issues)


def test_contradiction_rejection():
    """Verify Quality Gate detects logical contradictions (e.g. low score with Pursue recommendation)."""
    gate = QualityGateAgent()
    norm = NormalizedInput(
        normalized_resume="General worker.",
        normalized_job_description="VP Operations.",
        normalized_priorities=ApplicantPriorities(),
    )
    matrix = [
        EvidenceItem(
            requirement="10+ years VP leadership",
            category="Leadership",
            classification=EvidenceClassification.MISSING,
            resume_evidence="None found in résumé.",
            reasoning="Missing",
        )
    ]
    assessment = FitAssessment(
        fit_score=30,
        recommendation=RecommendationType.PURSUE,
        score_explanation="Score",
        uncertainty_explanation="Uncertainty",
    )
    plan = ActionPlan(
        application_brief="Brief",
        prioritized_next_actions=["Apply"],
        clarification_questions=["Question"],
        interview_prep_points=["STAR"],
    )

    result = gate.run(norm, matrix, assessment, plan, current_corrections=0)
    assert result.is_valid is False
    assert any("Contradiction" in issue for issue in result.issues)


def test_verbatim_grounding_check():
    """Verify that non-missing evidence must be a verbatim résumé substring."""
    gate = QualityGateAgent()
    norm = NormalizedInput(
        normalized_resume="Managed 3 retail stores in downtown area with $2M annual revenue.",
        normalized_job_description="Store manager role.",
        normalized_priorities=ApplicantPriorities(),
    )
    # Evidence is paraphrased, not verbatim
    matrix = [
        EvidenceItem(
            requirement="Retail management experience",
            category="Operations",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="Oversaw 3 retail outlets generating $2M per year in revenue.",
            reasoning="Paraphrased claim",
        )
    ]
    assessment = FitAssessment(
        fit_score=80,
        recommendation=RecommendationType.PURSUE,
        score_explanation="Good score.",
        uncertainty_explanation="Low.",
    )
    plan = ActionPlan(
        application_brief="Candidate fits.",
        prioritized_next_actions=["Apply"],
        clarification_questions=["Clarify"],
        interview_prep_points=["STAR"],
    )

    result = gate.run(norm, matrix, assessment, plan, current_corrections=0)
    assert result.is_valid is False
    assert any("Unsupported Claim" in issue or "verbatim" in issue.lower() for issue in result.issues)


def test_apply_corrections_downgrades_unsupported():
    """Verify apply_corrections downgrades fabricated evidence to MISSING."""
    gate = QualityGateAgent()
    norm = NormalizedInput(
        normalized_resume="Software engineer with Python and cloud experience.",
        normalized_job_description="Backend developer.",
        normalized_priorities=ApplicantPriorities(),
    )
    matrix = [
        EvidenceItem(
            requirement="Python backend development",
            category="Engineering",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="Software engineer with Python and cloud experience.",
            reasoning="Direct match",
        ),
        EvidenceItem(
            requirement="Kubernetes orchestration expertise",
            category="DevOps",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="10 years running Kubernetes clusters across 50 nodes.",
            reasoning="Fabricated",
        ),
    ]
    quality_report = gate.run(
        norm, matrix,
        FitAssessment(fit_score=90, recommendation=RecommendationType.PURSUE,
                      score_explanation="S", uncertainty_explanation="U"),
        ActionPlan(application_brief="B", prioritized_next_actions=["A"],
                   clarification_questions=["Q"], interview_prep_points=["P"]),
    )
    assert not quality_report.passed

    corrected = gate.apply_corrections(norm, matrix, quality_report)
    # First item should survive, second should be downgraded
    assert corrected[0].classification == EvidenceClassification.DIRECT
    assert corrected[1].classification == EvidenceClassification.MISSING
    assert corrected[1].resume_evidence == "None found in résumé."


def test_coordinator_one_permitted_correction_pass():
    """Verify the coordinator initiates exactly 1 correction pass when contradictions occur and resolves them."""
    coordinator = WorkflowCoordinator()

    conflict_input = WorkflowInput(
        resume_text="Operations manager overseeing 7 units with ServSafe certification and labor reduction.",
        job_description_text="District Manager position requiring daily field travel to 10 stores.",
        priorities=ApplicantPriorities(
            non_negotiables=["Must be 100% remote work only from home"]
        ),
    )

    workflow = coordinator.execute_workflow(conflict_input)
    assert workflow.state == WorkflowState.COMPLETED

    assert workflow.fit_assessment.recommendation == RecommendationType.PASS
    assert workflow.fit_assessment.fit_score <= 50


def test_prevention_of_infinite_retries():
    """Verify Quality Gate enforces single correction count and coordinator caps retries."""
    coordinator = WorkflowCoordinator()

    workflow = coordinator.execute_workflow(
        WorkflowInput(
            resume_text="Sample candidate resume content for test purposes with enough length to pass validation.",
            job_description_text="Sample job description with requirements for a position that needs many skills.",
            priorities=ApplicantPriorities(),
        )
    )

    assert workflow.state in [WorkflowState.COMPLETED, WorkflowState.FAILED]
    assert workflow.quality_report is not None
    assert workflow.quality_report.correction_count <= 1
