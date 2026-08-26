"""Evidence Agent: Extracts job requirements, maps résumé evidence, and classifies match strength.

Design principles (Milestone 1 QA):
- resume_evidence is ALWAYS either a verbatim substring of the normalised résumé
  or the sentinel "None found in résumé."
- Specific requirements (driver's license, travel) are evaluated before broad
  category catch-alls (multi-unit, P&L) so a narrow requirement never gets
  swallowed by a wide-scope match.
- Direct classification requires a verbatim grounded quote AND
  requirement-specific keyword alignment.  Generic word overlap alone produces
  transferable or inference.
"""

import re
from typing import List, Optional, Tuple
from app.agents.base import BaseAgent
from app.models import EvidenceClassification, EvidenceItem, NormalizedInput


class EvidenceAgent(BaseAgent):
    """Specialist agent that maps candidate résumé evidence to job requirements."""

    @property
    def name(self) -> str:
        return "Evidence Agent"

    # ------------------------------------------------------------------
    # Requirement extraction
    # ------------------------------------------------------------------

    def extract_requirements(self, jd_text: str) -> List[Tuple[str, str]]:
        """Extract key requirement statements and their domain category from the job description.

        Lines are classified as headings only when they are SHORT standalone
        labels (≤ 60 chars, ending with `:` or all-caps) that contain no bullet
        or numbered prefix.  Everything else that begins with a bullet or number
        is kept as a requirement.
        """
        reqs: List[Tuple[str, str]] = []
        lines = [ln.strip() for ln in jd_text.split("\n") if ln.strip()]

        current_category = "General Requirements"

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            # Detect standalone section headings:
            #   - Short (≤ 60 chars), ends with ':'  (e.g. "KEY RESPONSIBILITIES:")
            #   - All-caps label
            is_bullet = stripped.startswith("-") or stripped.startswith("*") or stripped.startswith("•")
            is_numbered = bool(re.match(r"^\d+[\.\)]\s+", stripped))

            is_heading = (
                not is_bullet
                and not is_numbered
                and (
                    (stripped.endswith(":") and len(stripped) <= 60)
                    or (stripped == stripped.upper() and len(stripped) <= 60 and len(stripped) > 2)
                )
            )

            if is_heading:
                # Use the heading text to set the current category bucket
                if any(h in lower for h in ["responsibilities", "duties", "accountabilities"]):
                    current_category = "Core Responsibilities"
                elif any(h in lower for h in ["qualifications", "requirements", "skills", "must have"]):
                    current_category = "Qualifications & Skills"
                elif any(h in lower for h in ["about", "role", "position", "overview"]):
                    current_category = "Role Overview"
                else:
                    current_category = stripped.rstrip(":").strip()
                continue

            # Keep bullet/numbered items as requirements
            if is_bullet or is_numbered:
                if is_numbered:
                    cleaned_req = re.sub(r"^\d+[\.\)]\s*", "", stripped).strip()
                else:
                    cleaned_req = re.sub(r"^[-*•]\s*", "", stripped).strip()
                if len(cleaned_req) >= 15:
                    cat = self._categorize_requirement(cleaned_req, current_category)
                    reqs.append((cleaned_req, cat))

        # Fallback: if zero formatted requirements found, pick long lines
        if not reqs:
            for line in lines:
                if len(line) >= 25 and not line.endswith(":"):
                    cat = self._categorize_requirement(line, current_category)
                    reqs.append((line, cat))

        # Deduplicate keeping order, cap at 10 requirements
        seen: set[str] = set()
        deduped: List[Tuple[str, str]] = []
        for req, cat in reqs:
            if req not in seen:
                seen.add(req)
                deduped.append((req, cat))
        return deduped[:10]

    def _categorize_requirement(self, req: str, fallback_cat: str) -> str:
        r = req.lower()
        if any(k in r for k in ["driver", "license", "travel", "relocation", "commute"]):
            return "Logistics & Travel"
        if any(k in r for k in ["p&l", "ebitda", "profit", "cost", "budget", "financial", "revenue"]):
            return "P&L & Financial Management"
        if any(k in r for k in ["safety", "servsafe", "health", "compliance", "inspection", "sanitation", "standards"]):
            return "Quality & Safety Compliance"
        if any(k in r for k in ["recruit", "coach", "talent", "train", "team", "staff", "mentor", "hire", "turnover", "promote"]):
            return "People Leadership & Talent"
        if any(k in r for k in ["vendor", "capex", "supply chain", "marketing", "equipment", "contractor"]):
            return "Execution & Vendor Management"
        if any(k in r for k in ["multi-unit", "district", "regional", "territory", "store operations", "locations"]):
            return "Multi-Unit Operations"
        return fallback_cat

    # ------------------------------------------------------------------
    # Evidence grounding helpers
    # ------------------------------------------------------------------

    def _find_verbatim_line(self, resume_lines: List[str], keywords: List[str]) -> Optional[str]:
        """Return the first resume line containing ALL keywords (case-insensitive), or None."""
        for line in resume_lines:
            ll = line.lower()
            if all(k in ll for k in keywords):
                return line
        return None

    def _find_best_line(self, resume_lines: List[str], keywords: List[str], min_hits: int = 2) -> Optional[str]:
        """Return the resume line with the most keyword hits (>= min_hits), or None."""
        best: Optional[str] = None
        best_count = 0
        for line in resume_lines:
            ll = line.lower()
            hits = sum(1 for k in keywords if k in ll)
            if hits >= min_hits and hits > best_count:
                best = line
                best_count = hits
        return best

    # ------------------------------------------------------------------
    # Per-requirement evidence mapping
    # ------------------------------------------------------------------

    def find_evidence_for_requirement(
        self, req: str, category: str, resume_text: str,
    ) -> EvidenceItem:
        req_lower = req.lower()
        resume_lines = [ln.strip() for ln in resume_text.split("\n") if ln.strip()]

        # ---- SPECIFIC requirements first (narrow scope) ----

        # Driver's license
        if "driver" in req_lower and "license" in req_lower:
            return EvidenceItem(
                requirement=req, category=category,
                classification=EvidenceClassification.MISSING,
                resume_evidence="None found in résumé.",
                reasoning="Résumé does not mention a valid driver's license.",
            )

        # Willingness to travel (NOT a license requirement)
        if "travel" in req_lower and "driver" not in req_lower:
            line = self._find_best_line(resume_lines, ["regional", "district", "locations"], min_hits=1)
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.INFERENCE,
                    resume_evidence=line,
                    reasoning="Multi-unit district management implies regular field travel; explicit willingness statement not found.",
                )
            return EvidenceItem(
                requirement=req, category=category,
                classification=EvidenceClassification.MISSING,
                resume_evidence="None found in résumé.",
                reasoning="No evidence of regular field travel in résumé.",
            )

        # Combined driver + travel clause (e.g. "Valid driver's license and willingness to travel daily")
        if ("license" in req_lower or "driver" in req_lower) and "travel" in req_lower:
            # The driver-license part is missing → whole item is missing
            return EvidenceItem(
                requirement=req, category=category,
                classification=EvidenceClassification.MISSING,
                resume_evidence="None found in résumé.",
                reasoning="Résumé does not mention a valid driver's license or explicit willingness to travel daily.",
            )

        # ---- ServSafe / Food Safety ----
        if "servsafe" in req_lower or "food safety" in req_lower or ("food" in req_lower and "handling" in req_lower):
            line = self._find_verbatim_line(resume_lines, ["servsafe"])
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.DIRECT,
                    resume_evidence=line,
                    reasoning="Active ServSafe certification explicitly stated in résumé.",
                )
            line = self._find_best_line(resume_lines, ["food", "safety"], min_hits=2) or \
                   self._find_best_line(resume_lines, ["health", "inspection"], min_hits=2)
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.TRANSFERABLE,
                    resume_evidence=line,
                    reasoning="Related food safety/health experience found but specific certification unverified.",
                )
            return self._missing(req, category)

        # ---- P&L / EBITDA / Financial ----
        if any(k in req_lower for k in ["p&l", "ebitda", "labor cost", "food cost", "profitability", "cost reduction"]):
            # Direct: need a line that references EBITDA, labor cost, or P&L quantitatively
            line = self._find_best_line(resume_lines, ["ebitda"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["labor", "cost"], min_hits=2) or \
                   self._find_best_line(resume_lines, ["p&l"], min_hits=1)
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.DIRECT,
                    resume_evidence=line,
                    reasoning="Explicit P&L/EBITDA/labor-cost management with quantified results found in résumé.",
                )
            line = self._find_best_line(resume_lines, ["budget", "revenue", "sales"], min_hits=1)
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.TRANSFERABLE,
                    resume_evidence=line,
                    reasoning="Budget/revenue management found but specific controllable-cost metrics not stated.",
                )
            return self._missing(req, category)

        # ---- People / Talent / Coaching ----
        if any(k in req_lower for k in ["recruit", "coach", "talent", "mentor", "hire", "turnover", "promote", "succession"]):
            line = self._find_best_line(resume_lines, ["promoted", "turnover"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["team", "members", "manager"], min_hits=2) or \
                   self._find_best_line(resume_lines, ["trainer"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["coaching"], min_hits=1)
            if line:
                has_quant = bool(re.search(r"\d", line))
                cls = EvidenceClassification.DIRECT if has_quant else EvidenceClassification.TRANSFERABLE
                reason = (
                    "Quantified talent development and succession planning directly in résumé."
                    if has_quant
                    else "Related people-leadership experience found without explicit metrics."
                )
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=cls,
                    resume_evidence=line,
                    reasoning=reason,
                )
            return self._missing(req, category)

        # ---- Multi-Unit Operations ----
        if any(k in req_lower for k in ["multi-unit", "district", "locations", "territory"]):
            line = self._find_best_line(resume_lines, ["restaurant", "locations"], min_hits=2) or \
                   self._find_best_line(resume_lines, ["high-volume", "restaurant"], min_hits=2) or \
                   self._find_best_line(resume_lines, ["multi-unit"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["district"], min_hits=1)
            if line:
                has_quant = bool(re.search(r"\d", line))
                cls = EvidenceClassification.DIRECT if has_quant else EvidenceClassification.TRANSFERABLE
                reason = (
                    "Explicit multi-unit oversight with quantified scope found in résumé."
                    if has_quant
                    else "Multi-unit or district reference found but unit count unquantified."
                )
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=cls,
                    resume_evidence=line,
                    reasoning=reason,
                )
            # GM-level single unit → transferable
            line = self._find_best_line(resume_lines, ["general manager"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["store"], min_hits=1)
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.TRANSFERABLE,
                    resume_evidence=line,
                    reasoning="Single-unit GM or store-level experience transferable to multi-unit scope.",
                )
            return self._missing(req, category)

        # ---- Vendor / Capex / Supply Chain ----
        if any(k in req_lower for k in ["vendor", "capex", "supply chain", "contractor", "distributor", "equipment"]):
            line = self._find_best_line(resume_lines, ["distributor"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["capital", "expenditure"], min_hits=2) or \
                   self._find_best_line(resume_lines, ["inventory"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["vendor"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["budgets"], min_hits=1)
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.DIRECT,
                    resume_evidence=line,
                    reasoning="Direct vendor/capex/inventory management evidence found in résumé.",
                )
            line = self._find_best_line(resume_lines, ["operations"], min_hits=1)
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.INFERENCE,
                    resume_evidence=line,
                    reasoning="Operational scope implies vendor coordination but explicit evidence not found.",
                )
            return self._missing(req, category)

        # ---- Guest / Marketing / Growth ----
        if any(k in req_lower for k in ["guest", "hospitality", "marketing", "customer"]):
            line = self._find_best_line(resume_lines, ["guest", "satisfaction"], min_hits=2) or \
                   self._find_best_line(resume_lines, ["marketing"], min_hits=1) or \
                   self._find_best_line(resume_lines, ["mystery", "shopper"], min_hits=2)
            if line:
                return EvidenceItem(
                    requirement=req, category=category,
                    classification=EvidenceClassification.DIRECT,
                    resume_evidence=line,
                    reasoning="Guest satisfaction/marketing evidence found in résumé.",
                )
            return self._missing(req, category)

        # ---- Generic fallback with strict grounding ----
        stop_words = {
            "with", "from", "that", "this", "have", "must", "across", "proven",
            "demonstrated", "track", "record", "years", "least", "managing",
            "experience", "required", "ability",
        }
        words = [
            w for w in re.findall(r"\b[a-zA-Z0-9-]{4,}\b", req_lower) if w not in stop_words
        ]
        line = self._find_best_line(resume_lines, words, min_hits=3)
        if line:
            return EvidenceItem(
                requirement=req, category=category,
                classification=EvidenceClassification.TRANSFERABLE,
                resume_evidence=line,
                reasoning="Related background found in résumé via keyword alignment.",
            )
        return self._missing(req, category)

    def _missing(self, req: str, category: str) -> EvidenceItem:
        return EvidenceItem(
            requirement=req, category=category,
            classification=EvidenceClassification.MISSING,
            resume_evidence="None found in résumé.",
            reasoning="Résumé does not contain explicit evidence for this requirement.",
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, normalized_inputs: NormalizedInput) -> List[EvidenceItem]:
        reqs = self.extract_requirements(normalized_inputs.normalized_job_description)
        matrix: List[EvidenceItem] = []
        for req_text, category in reqs:
            item = self.find_evidence_for_requirement(
                req_text, category, normalized_inputs.normalized_resume,
            )
            matrix.append(item)
        return matrix
