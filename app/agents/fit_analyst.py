"""Fit Analyst Agent: Calculates fit score (0-100), determines recommendation, and analyzes strengths/risks."""

from typing import List
from app.agents.base import BaseAgent
from app.models import (
    ApplicantPriorities,
    EvidenceClassification,
    EvidenceItem,
    FitAssessment,
    NormalizedInput,
    RecommendationType,
)


class FitAnalystAgent(BaseAgent):
    """Specialist agent that computes quantitative fit, uncertainty levels, and strategic recommendations."""

    @property
    def name(self) -> str:
        return "Fit Analyst"

    def calculate_score_and_uncertainty(
        self, matrix: List[EvidenceItem], priorities: ApplicantPriorities, jd_text: str
    ) -> FitAssessment:
        """Calculate weighted score, evaluate priority alignment, and formulate recommendations."""
        if not matrix:
            return FitAssessment(
                fit_score=0,
                recommendation=RecommendationType.PASS,
                score_explanation="No job requirements were available for evaluation.",
                uncertainty_explanation="100% uncertainty due to empty evidence matrix.",
                strengths=[],
                gaps=["No evaluable requirements identified in job description."],
                risks=["Unable to map candidate background against target position."],
            )

        # Classification weights
        weight_map = {
            EvidenceClassification.DIRECT: 100.0,
            EvidenceClassification.TRANSFERABLE: 75.0,
            EvidenceClassification.INFERENCE: 40.0,
            EvidenceClassification.MISSING: 0.0,
        }

        total_points = sum(weight_map[item.classification] for item in matrix)
        raw_score = total_points / len(matrix)

        direct_count = sum(1 for i in matrix if i.classification == EvidenceClassification.DIRECT)
        transferable_count = sum(1 for i in matrix if i.classification == EvidenceClassification.TRANSFERABLE)
        inference_count = sum(1 for i in matrix if i.classification == EvidenceClassification.INFERENCE)
        missing_count = sum(1 for i in matrix if i.classification == EvidenceClassification.MISSING)

        # Check priorities alignment
        risks: List[str] = []
        gaps: List[str] = []
        strengths: List[str] = []

        # Evaluate strengths from direct/transferable evidence
        for item in matrix:
            if item.classification == EvidenceClassification.DIRECT:
                strengths.append(f"Strong match in {item.category}: {item.requirement[:70]}...")
            elif item.classification == EvidenceClassification.MISSING:
                gaps.append(f"Unverified or missing experience in {item.category}: {item.requirement[:70]}...")
            elif item.classification == EvidenceClassification.INFERENCE:
                gaps.append(f"Inferred capability requiring verification in {item.category}: {item.requirement[:70]}...")

        # Evaluate non-negotiables and priority constraints
        non_negotiable_conflict = False
        if priorities.non_negotiables:
            jd_lower = jd_text.lower()
            for nn in priorities.non_negotiables:
                nn_lower = nn.lower()
                if "remote" in nn_lower and "on-site" in jd_lower and "travel" in jd_lower:
                    risks.append(f"Non-negotiable conflict: Candidate requires remote work, but role requires on-site district travel.")
                    non_negotiable_conflict = True
                elif "under 12 units" in nn_lower and "20+ units" in jd_lower:
                    risks.append("Non-negotiable conflict: Role territory exceeds desired unit threshold.")
                    non_negotiable_conflict = True

        # Clamp and adjust score
        adjusted_score = raw_score
        if non_negotiable_conflict:
            adjusted_score = min(adjusted_score, 45.0)

        final_score = int(round(max(0.0, min(100.0, adjusted_score))))

        # Recommendation boundaries
        if non_negotiable_conflict or final_score < 50:
            rec = RecommendationType.PASS
        elif final_score >= 75 and missing_count <= 1:
            rec = RecommendationType.PURSUE
        else:
            rec = RecommendationType.INVESTIGATE

        # Uncertainty calculation
        uncertain_items = inference_count + missing_count
        uncertainty_pct = int(round((uncertain_items / len(matrix)) * 100))

        if uncertainty_pct >= 40:
            uncertainty_level = "High"
        elif uncertainty_pct >= 20:
            uncertainty_level = "Moderate"
        else:
            uncertainty_level = "Low"

        score_expl = (
            f"Score calculated as {final_score}/100 based on {len(matrix)} requirements: "
            f"{direct_count} Direct (100%), {transferable_count} Transferable (75%), "
            f"{inference_count} Inferred (40%), and {missing_count} Missing (0%)."
        )
        if non_negotiable_conflict:
            score_expl += " A downward adjustment was applied due to applicant non-negotiable condition conflicts."

        uncert_expl = (
            f"{uncertainty_level} uncertainty ({uncertainty_pct}% of requirements). "
            f"{inference_count} requirement(s) rely on inference and {missing_count} have no direct résumé proof."
        )

        if not risks:
            risks.append("Ensure verification of territory mileage compensation and bonus target feasibility during initial screen.")

        return FitAssessment(
            fit_score=final_score,
            recommendation=rec,
            score_explanation=score_expl,
            uncertainty_explanation=uncert_expl,
            strengths=strengths[:5],
            gaps=gaps[:5],
            risks=risks,
        )

    def run(
        self, normalized_inputs: NormalizedInput, evidence_matrix: List[EvidenceItem]
    ) -> FitAssessment:
        """Execute fit analysis on mapped evidence and applicant preferences."""
        return self.calculate_score_and_uncertainty(
            matrix=evidence_matrix,
            priorities=normalized_inputs.normalized_priorities,
            jd_text=normalized_inputs.normalized_job_description,
        )
