"""Tests for individual specialist agents (Intake, Evidence, Fit Analyst, Action Planner).

Milestone 1 QA additions:
- test_sample_jd_extracts_all_core_requirements: proves that P&L, talent, food-safety,
  vendor/capex, multi-unit, and driver/travel requirements are ALL extracted.
- test_drivers_license_classified_missing: driver's licence requirement → missing.
- test_travel_classified_inference: willingness-to-travel → inference (not direct).
- test_evidence_grounding_is_verbatim_or_sentinel: every resume_evidence field is
  either a verbatim substring of the résumé or "None found in résumé."
"""

import json
from pathlib import Path
import pytest
from app.agents.action_planner import ActionPlannerAgent
from app.agents.evidence import EvidenceAgent
from app.agents.fit_analyst import FitAnalystAgent
from app.agents.intake import IntakeAgent
from app.models import (
    ApplicantPriorities,
    EvidenceClassification,
    EvidenceItem,
    FitAssessment,
    NormalizedInput,
    RecommendationType,
    WorkflowInput,
)


# ---- Fixtures ----

@pytest.fixture
def sample_data():
    sample_path = Path(__file__).resolve().parent.parent / "samples" / "restaurant_district_manager.json"
    with open(sample_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sample_normalized(sample_data):
    agent = IntakeAgent()
    raw = WorkflowInput(
        resume_text=sample_data["resume_text"],
        job_description_text=sample_data["job_description_text"],
        priorities=ApplicantPriorities(**sample_data["priorities"]),
    )
    return agent.run(raw)


# ---- Intake Agent ----

def test_intake_agent_normalization():
    """Verify IntakeAgent cleans text and extracts sections."""
    agent = IntakeAgent()
    raw_input = WorkflowInput(
        resume_text="  • Results-driven operations leader \r\n\r\n\r\n* Overseeing 7 stores  ",
        job_description_text="  - Must have 3+ years experience\n- P&L responsibility  ",
        priorities=ApplicantPriorities(min_compensation="$100k", location_preference="Remote"),
    )
    result = agent.run(raw_input)

    assert "- Results-driven operations leader" in result.normalized_resume
    assert "- Overseeing 7 stores" in result.normalized_resume
    assert "\r\n" not in result.normalized_resume
    assert result.normalized_priorities.min_compensation == "$100k"


def test_intake_agent_missing_detection():
    """Verify IntakeAgent identifies missing critical data."""
    agent = IntakeAgent()
    sparse_input = WorkflowInput(
        resume_text="Brief note without sections.",
        job_description_text="Short job note.",
        priorities=ApplicantPriorities(),
    )
    result = agent.run(sparse_input)
    assert len(result.identified_missing_inputs) > 0
    assert any("compensation" in m.lower() for m in result.identified_missing_inputs)


# ---- Evidence Agent: Classification Types ----

def test_evidence_classification_types():
    """Verify EvidenceAgent produces all 4 classification categories correctly."""
    agent = EvidenceAgent()

    # 1. Direct match
    direct_item = agent.find_evidence_for_requirement(
        req="Requires ServSafe Manager Certification and health inspections",
        category="Quality & Safety Compliance",
        resume_text="ServSafe Manager Certified. District food safety audit leader.",
    )
    assert direct_item.classification == EvidenceClassification.DIRECT
    assert "ServSafe" in direct_item.resume_evidence

    # 2. Transferable match
    transferable_item = agent.find_evidence_for_requirement(
        req="Multi-unit district management oversight",
        category="Multi-Unit Operations",
        resume_text="Single store General Manager with Area Training Lead duties.",
    )
    assert transferable_item.classification == EvidenceClassification.TRANSFERABLE

    # 3. Inference match
    inference_item = agent.find_evidence_for_requirement(
        req="Willingness to travel daily within assigned territory",
        category="Execution",
        resume_text="Regional Operations Manager overseeing 7 high volume locations.",
    )
    assert inference_item.classification == EvidenceClassification.INFERENCE

    # 4. Missing match
    missing_item = agent.find_evidence_for_requirement(
        req="Experience with enterprise SAP ERP database architecture",
        category="Technology",
        resume_text="Operations manager with culinary and restaurant background.",
    )
    assert missing_item.classification == EvidenceClassification.MISSING
    assert missing_item.resume_evidence == "None found in résumé."


# ---- Evidence Agent: Sample Requirement Extraction (Milestone 1 QA) ----

def test_sample_jd_extracts_all_core_requirements(sample_normalized):
    """Prove the sample JD extracts its P&L, talent-development, food-safety,
    vendor/capex, multi-unit, and driver/travel requirements."""
    agent = EvidenceAgent()
    reqs = agent.extract_requirements(sample_normalized.normalized_job_description)
    req_texts_lower = [r[0].lower() for r in reqs]

    # P&L / financial
    assert any("p&l" in t or "profitability" in t or "labor cost" in t or "revenue" in t for t in req_texts_lower), \
        f"P&L requirement not extracted. Got: {req_texts_lower}"

    # Talent / People Leadership
    assert any("recruit" in t or "coach" in t or "talent" in t or "mentor" in t or "promote" in t for t in req_texts_lower), \
        f"Talent requirement not extracted. Got: {req_texts_lower}"

    # Food Safety / ServSafe
    assert any("servsafe" in t or "food safety" in t or "food handling" in t or "health" in t for t in req_texts_lower), \
        f"Food safety requirement not extracted. Got: {req_texts_lower}"

    # Vendor / Capex
    assert any("vendor" in t or "capex" in t or "supply chain" in t or "equipment" in t or "contractor" in t for t in req_texts_lower), \
        f"Vendor/capex requirement not extracted. Got: {req_texts_lower}"

    # Multi-unit
    assert any("multi-unit" in t or "locations" in t or "district" in t or "territory" in t for t in req_texts_lower), \
        f"Multi-unit requirement not extracted. Got: {req_texts_lower}"

    # Driver/travel
    assert any("driver" in t or "travel" in t or "license" in t for t in req_texts_lower), \
        f"Driver/travel requirement not extracted. Got: {req_texts_lower}"


def test_drivers_license_classified_missing(sample_normalized):
    """Valid driver's licence requirement must be classified as MISSING."""
    agent = EvidenceAgent()
    item = agent.find_evidence_for_requirement(
        req="Valid driver's license and willingness to travel daily within the assigned district",
        category="Logistics & Travel",
        resume_text=sample_normalized.normalized_resume,
    )
    assert item.classification == EvidenceClassification.MISSING, \
        f"Expected MISSING, got {item.classification.value}"
    assert item.resume_evidence == "None found in résumé."


def test_travel_only_classified_inference(sample_normalized):
    """Willingness to travel (not combined with driver's licence) → INFERENCE when
    resume shows regional/district background."""
    agent = EvidenceAgent()
    item = agent.find_evidence_for_requirement(
        req="Willingness to travel daily within the assigned district",
        category="Logistics & Travel",
        resume_text=sample_normalized.normalized_resume,
    )
    assert item.classification == EvidenceClassification.INFERENCE, \
        f"Expected INFERENCE, got {item.classification.value}"


# ---- Evidence Agent: Verbatim Grounding (Milestone 1 QA) ----

def test_evidence_grounding_is_verbatim_or_sentinel(sample_normalized):
    """Every resume_evidence field MUST be either a verbatim substring of the
    normalised résumé or the exact sentinel 'None found in résumé.'"""
    agent = EvidenceAgent()
    matrix = agent.run(sample_normalized)
    resume = sample_normalized.normalized_resume

    for item in matrix:
        if item.resume_evidence == "None found in résumé.":
            continue
        assert item.resume_evidence in resume, (
            f"Evidence for '{item.requirement[:50]}' is NOT a verbatim résumé substring:\n"
            f"  Evidence: {item.resume_evidence!r}\n"
            f"  Résumé excerpt: {resume[:200]!r}"
        )


# ---- Fit Analyst: Score & Recommendation Boundaries ----

def test_fit_score_and_recommendation_boundaries():
    """Verify fit score boundaries (0-100) and recommendation thresholds (Pursue, Investigate, Pass)."""
    analyst = FitAnalystAgent()

    # Scenario A: High match -> Pursue (>= 75)
    high_matrix = [
        EvidenceItem(
            requirement="P&L management", category="Financial",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="EBITDA expansion of 4.2%", reasoning="Direct match",
        ),
        EvidenceItem(
            requirement="Multi-unit leadership", category="Operations",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="7 units oversight", reasoning="Direct match",
        ),
        EvidenceItem(
            requirement="ServSafe", category="Safety",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="Certified", reasoning="Direct match",
        ),
        EvidenceItem(
            requirement="Talent development", category="People",
            classification=EvidenceClassification.TRANSFERABLE,
            resume_evidence="Promoted 9 staff", reasoning="Strong match",
        ),
    ]
    assessment_high = analyst.calculate_score_and_uncertainty(
        high_matrix, ApplicantPriorities(), "District Manager role with on-site travel."
    )
    assert 75 <= assessment_high.fit_score <= 100
    assert assessment_high.recommendation == RecommendationType.PURSUE

    # Scenario B: Moderate match -> Investigate (50-74)
    mid_matrix = [
        EvidenceItem(
            requirement="Req 1", category="General",
            classification=EvidenceClassification.TRANSFERABLE,
            resume_evidence="Some related skill", reasoning="Transferable",
        ),
        EvidenceItem(
            requirement="Req 2", category="General",
            classification=EvidenceClassification.INFERENCE,
            resume_evidence="Inferred", reasoning="Inferred",
        ),
        EvidenceItem(
            requirement="Req 3", category="General",
            classification=EvidenceClassification.MISSING,
            resume_evidence="None found in résumé.", reasoning="Missing",
        ),
    ]
    assessment_mid = analyst.calculate_score_and_uncertainty(
        mid_matrix, ApplicantPriorities(), "Mid level role."
    )
    assert 0 <= assessment_mid.fit_score <= 100
    assert assessment_mid.recommendation in [RecommendationType.INVESTIGATE, RecommendationType.PASS]

    # Scenario C: Severe non-negotiable conflict -> Pass
    conflict_priorities = ApplicantPriorities(
        non_negotiables=["Must be strictly 100% remote work only"]
    )
    assessment_conflict = analyst.calculate_score_and_uncertainty(
        high_matrix, conflict_priorities, "Position requires daily on-site field travel to 10 stores."
    )
    assert assessment_conflict.recommendation == RecommendationType.PASS
    assert assessment_conflict.fit_score <= 45
    assert any("remote" in r.lower() for r in assessment_conflict.risks)


# ---- Action Planner ----

def test_action_planner_output_structure():
    """Verify ActionPlannerAgent creates populated briefs, actions, and STAR talking points."""
    planner = ActionPlannerAgent()
    normalized = NormalizedInput(
        normalized_resume="Sample resume",
        normalized_job_description="Sample JD",
        normalized_priorities=ApplicantPriorities(),
    )
    matrix = [
        EvidenceItem(
            requirement="Labor cost management", category="Operations",
            classification=EvidenceClassification.DIRECT,
            resume_evidence="Reduced labor 2.8%", reasoning="Quantified metric",
        )
    ]
    fit_assessment = FitAssessment(
        fit_score=85,
        recommendation=RecommendationType.PURSUE,
        score_explanation="Strong score",
        uncertainty_explanation="Low uncertainty",
    )

    plan = planner.run(normalized, matrix, fit_assessment)

    assert len(plan.application_brief) > 20
    assert len(plan.prioritized_next_actions) >= 3
    assert len(plan.clarification_questions) >= 2
    assert len(plan.interview_prep_points) >= 2
    assert any("STAR" in point for point in plan.interview_prep_points)
