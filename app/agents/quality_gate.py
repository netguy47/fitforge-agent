"""Quality Gate Agent: Enforces evidence grounding, contradiction checks, section completeness, and retry bounds.

Milestone 1 QA rules:
- Every non-missing resume_evidence MUST be a verbatim substring of the
  normalised résumé.
- Direct evidence must also satisfy requirement-specific grounding (at least
  one domain keyword from the requirement appears in the evidence line).
- On correction pass: downgrade or clear unsupported evidence, recalculate
  fit, regenerate action plan, revalidate.  Fail if still unsupported.
"""

import re
from typing import List
from app.agents.base import BaseAgent
from app.models import (
    ActionPlan,
    EvidenceClassification,
    EvidenceItem,
    FitAssessment,
    NormalizedInput,
    QualityGateResult,
    RecommendationType,
)


class QualityGateAgent(BaseAgent):
    """Specialist agent acting as safety and accuracy gatekeeper before final delivery."""

    @property
    def name(self) -> str:
        return "Quality Gate"

    @staticmethod
    def _is_verbatim_substring(evidence: str, resume_text: str) -> bool:
        """Check if evidence text is a verbatim substring of the resume."""
        return evidence in resume_text

    @staticmethod
    def _has_requirement_keyword_overlap(requirement: str, evidence: str) -> bool:
        """Check that the evidence line contains at least one domain-specific
        keyword from the requirement (excluding common stop-words)."""
        stop = {
            "with", "from", "that", "this", "have", "must", "across", "proven",
            "demonstrated", "track", "record", "years", "least", "experience",
            "required", "ability", "ensure", "full", "strict", "over", "under",
            "their", "there", "other", "about", "will", "shall", "should", "into",
        }
        req_words = {
            w.lower() for w in re.findall(r"[a-zA-Z0-9]{3,}", requirement)
        } - stop
        ev_words = {
            w.lower() for w in re.findall(r"[a-zA-Z0-9]{3,}", evidence)
        } - stop

        if req_words & ev_words:
            return True

        # Prefix/stem matching (e.g. unit/units, manage/management/managing, operate/operations)
        for rw in req_words:
            rw_stem = rw[:4] if len(rw) >= 4 else rw
            for ew in ev_words:
                ew_stem = ew[:4] if len(ew) >= 4 else ew
                if rw_stem == ew_stem or (len(rw) >= 4 and rw in ew) or (len(ew) >= 4 and ew in rw):
                    return True

        return False

    def validate(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
        action_plan: ActionPlan,
        current_corrections: int = 0,
    ) -> QualityGateResult:
        """Run rigorous integrity rules against generated workflow assets."""
        issues: List[str] = []
        resume_text = normalized_inputs.normalized_resume

        # 1. Check Section Completeness
        if not matrix:
            issues.append("Evidence matrix is empty; no requirements evaluated.")
        if not action_plan.prioritized_next_actions:
            issues.append("Action plan lacks prioritized next actions.")
        if not action_plan.application_brief:
            issues.append("Action plan lacks application brief.")
        if not fit_assessment.score_explanation:
            issues.append("Fit assessment missing score explanation.")

        # 2. Check Contradictions
        if fit_assessment.fit_score < 50 and fit_assessment.recommendation == RecommendationType.PURSUE:
            issues.append(
                f"Contradiction: Fit score is {fit_assessment.fit_score} but recommendation is 'Pursue'."
            )
        has_missing = any(i.classification == EvidenceClassification.MISSING for i in matrix)
        if fit_assessment.fit_score == 100 and has_missing:
            issues.append(
                "Contradiction: Fit score is 100% despite missing requirement items in evidence matrix."
            )

        # 3. Verbatim grounding check for ALL non-missing evidence
        for idx, item in enumerate(matrix):
            if item.classification == EvidenceClassification.MISSING:
                continue
            if item.resume_evidence == "None found in résumé.":
                continue
            if not self._is_verbatim_substring(item.resume_evidence, resume_text):
                issues.append(
                    f"Unsupported Claim in requirement #{idx+1} ('{item.requirement[:50]}'): "
                    f"Evidence text is not a verbatim résumé substring."
                )
            elif item.classification == EvidenceClassification.DIRECT:
                # Direct evidence must also satisfy requirement-keyword overlap
                if not self._has_requirement_keyword_overlap(item.requirement, item.resume_evidence):
                    issues.append(
                        f"Weak Direct in requirement #{idx+1} ('{item.requirement[:50]}'): "
                        f"Evidence line does not contain requirement-specific keywords."
                    )

        is_valid = len(issues) == 0
        notes = "All quality gate checks passed successfully." if is_valid else f"Found {len(issues)} quality issues."

        return QualityGateResult(
            is_valid=is_valid,
            passed=is_valid,
            issues=issues,
            correction_count=current_corrections,
            notes=notes,
        )

    def apply_corrections(
        self,
        normalized_inputs: NormalizedInput,
        matrix: List[EvidenceItem],
        quality_report: QualityGateResult,
    ) -> List[EvidenceItem]:
        """Deterministic correction pass: downgrade or clear unsupported evidence."""
        resume_text = normalized_inputs.normalized_resume
        corrected: List[EvidenceItem] = []

        for item in matrix:
            if item.classification == EvidenceClassification.MISSING:
                corrected.append(item)
                continue

            evidence_ok = (
                item.resume_evidence == "None found in résumé."
                or self._is_verbatim_substring(item.resume_evidence, resume_text)
            )

            if not evidence_ok:
                # Evidence is fabricated – downgrade to missing
                corrected.append(EvidenceItem(
                    requirement=item.requirement,
                    category=item.category,
                    classification=EvidenceClassification.MISSING,
                    resume_evidence="None found in résumé.",
                    reasoning=f"Correction: Original evidence was not a verbatim résumé substring. Downgraded from {item.classification.value}.",
                ))
            elif item.classification == EvidenceClassification.DIRECT:
                if not self._has_requirement_keyword_overlap(item.requirement, item.resume_evidence):
                    corrected.append(EvidenceItem(
                        requirement=item.requirement,
                        category=item.category,
                        classification=EvidenceClassification.TRANSFERABLE,
                        resume_evidence=item.resume_evidence,
                        reasoning=f"Correction: Downgraded from direct – evidence lacks requirement-specific keyword overlap.",
                    ))
                else:
                    corrected.append(item)
            else:
                corrected.append(item)

        return corrected

    def run(
        self,
        normalized_inputs: NormalizedInput,
        evidence_matrix: List[EvidenceItem],
        fit_assessment: FitAssessment,
        action_plan: ActionPlan,
        current_corrections: int = 0,
    ) -> QualityGateResult:
        return self.validate(
            normalized_inputs,
            evidence_matrix,
            fit_assessment,
            action_plan,
            current_corrections,
        )
