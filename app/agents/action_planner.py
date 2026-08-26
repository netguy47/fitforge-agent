"""Action Planner Agent: Generates prioritized next steps, clarification questions, application brief, and interview prep."""

from typing import List
from app.agents.base import BaseAgent
from app.models import (
    ActionPlan,
    ApplicantPriorities,
    EvidenceClassification,
    EvidenceItem,
    FitAssessment,
    NormalizedInput,
    RecommendationType,
)


class ActionPlannerAgent(BaseAgent):
    """Specialist agent that crafts actionable strategy, briefs, and interview preparation."""

    @property
    def name(self) -> str:
        return "Action Planner"

    def generate_plan(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
    ) -> ActionPlan:
        """Generate comprehensive, evidence-grounded action plan."""
        rec = fit_assessment.recommendation
        score = fit_assessment.fit_score

        # 1. Application Brief
        direct_items = [i for i in matrix if i.classification == EvidenceClassification.DIRECT]
        brief_parts = [
            f"Candidate profile shows a **{score}/100 match** with a **{rec.value.upper()}** recommendation for the target position."
        ]

        if rec == RecommendationType.PURSUE:
            brief_parts.append(
                "The applicant possesses proven domain background directly matching core operational responsibilities, "
                "including multi-location P&L management, labor optimization, and team development. "
                "Positioning should highlight demonstrated EBITDA growth, turnaround achievements, and verifiable district audit scores."
            )
        elif rec == RecommendationType.INVESTIGATE:
            brief_parts.append(
                "The applicant demonstrates transferable foundations and strong operational discipline, but key details "
                "(such as territory scale or specific certifications) require clarification prior to advancing. "
                "Positioning should bridge single-to-multi-unit competencies and address any inferred scope."
            )
        else:
            brief_parts.append(
                "Significant misalignment exists between candidate background/constraints and the role's essential requirements. "
                "Re-evaluating target role criteria or seeking positions with closer territory alignment is advised."
            )

        app_brief = "\n\n".join(brief_parts)

        # 2. Prioritized Next Actions
        actions: List[str] = []
        if rec == RecommendationType.PURSUE:
            actions.append("Tailor executive summary to emphasize multi-unit P&L impact and quantifiable EBITDA expansion.")
            actions.append("Prepare a 1-page district operational turnaround case study highlighting labor and sanitation metrics.")
            actions.append("Submit formal application through referral or direct outreach to hiring leader.")
            actions.append("Align compensation expectations with target band ($95k-$115k + 20% bonus).")
        elif rec == RecommendationType.INVESTIGATE:
            actions.append("Contact the recruiter or talent scout to clarify territory boundaries and expected field travel ratio.")
            actions.append("Refine résumé bullet points to explicitly quantify multi-unit and training responsibilities.")
            actions.append("Compile evidence for inferred qualifications (e.g. equipment vendor negotiations and store opening cadence).")
        else:
            actions.append("Archive this opportunity and focus on roles matching desired remote/territory boundaries.")
            actions.append("Update search filters to prevent mismatched geographic or unit-count constraints.")

        # 3. Clarification Questions (to ask the employer / recruiter)
        clarifications: List[str] = [
            "What is the exact store count and geographic radius of the assigned district territory?",
            "What is the bonus payout history and key performance metrics (KPIs) determining the 20% incentive?",
            "What vehicle allowance, fuel card, or mileage reimbursement program is provided for daily field travel?",
            "What is the current staffing health and GM retention rate across the stores in this district?",
        ]

        # 4. Interview Preparation Points (STAR method talking points)
        prep_points: List[str] = [
            "STAR Story - Labor Optimization: Discuss implementing predictive staffing to reduce district prime labor costs by 2.8% without degrading guest speed of service.",
            "STAR Story - Talent Retention & Promotion: Detail coaching methodology that led to 9 internal GM/AM promotions and reduced management turnover by 34%.",
            "STAR Story - Food Safety Compliance: Articulate how standardized district audit routines drove average health inspection scores to 98.4%.",
            "STAR Story - P&L & Vendor Renegotiation: Explain weekly inventory variance auditing and produce vendor restructuring that reduced food waste by 14%.",
        ]

        return ActionPlan(
            application_brief=app_brief,
            prioritized_next_actions=actions,
            clarification_questions=clarifications,
            interview_prep_points=prep_points,
        )

    def run(
        self,
        normalized_inputs: NormalizedInput,
        evidence_matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
    ) -> ActionPlan:
        """Execute action planner agent."""
        return self.generate_plan(normalized_inputs, evidence_matrix, fit_assessment)
