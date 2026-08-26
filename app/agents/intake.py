"""Intake Agent: Normalizes raw inputs, preserves originals, and identifies missing data."""

import re
from typing import Dict, List, Tuple
from app.agents.base import BaseAgent
from app.models import ApplicantPriorities, NormalizedInput, WorkflowInput


class IntakeAgent(BaseAgent):
    """Specialist agent responsible for text normalization and missing data detection."""

    @property
    def name(self) -> str:
        return "Intake Agent"

    def normalize_text(self, text: str) -> str:
        """Clean and normalize whitespace, bullet points, and character artifacts."""
        if not text:
            return ""
        # Standardize line breaks
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
        # Standardize common bullet point characters
        cleaned = re.sub(r"[•*·▪–—]\s*", "- ", cleaned)
        # Normalize multiple consecutive spaces (keeping line breaks)
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        # Trim leading/trailing blank lines
        cleaned = "\n".join([line.strip() for line in cleaned.split("\n")])
        # Collapse 3+ newlines to 2
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    def extract_resume_sections(self, text: str) -> Dict[str, str]:
        """Heuristically identify common resume sections."""
        sections: Dict[str, str] = {
            "summary": "",
            "experience": "",
            "skills": "",
            "education": "",
            "other": "",
        }

        current_sec = "summary"
        lines = text.split("\n")

        for line in lines:
            lower_line = line.lower().strip()
            if any(k in lower_line for k in ["experience", "employment", "work history", "career"]):
                current_sec = "experience"
                continue
            elif any(k in lower_line for k in ["skills", "competencies", "tools", "technologies"]):
                current_sec = "skills"
                continue
            elif any(k in lower_line for k in ["education", "certifications", "degrees", "academic"]):
                current_sec = "education"
                continue
            elif any(k in lower_line for k in ["summary", "profile", "overview", "objective"]):
                current_sec = "summary"
                continue

            sections[current_sec] = (sections[current_sec] + "\n" + line).strip()

        return sections

    def check_missing_information(
        self,
        resume: str,
        job_desc: str,
        priorities: ApplicantPriorities,
        sections: Dict[str, str],
    ) -> List[str]:
        """Detect critical missing pieces across applicant inputs and role requirements."""
        missing: List[str] = []

        if len(resume.strip()) < 50:
            missing.append("Résumé text is very brief or incomplete.")
        if not sections.get("experience"):
            missing.append("No explicit work experience section detected in résumé.")
        if not sections.get("education"):
            missing.append("No explicit education or certifications section detected in résumé.")

        if len(job_desc.strip()) < 50:
            missing.append("Job description is very brief or incomplete.")

        # Check job description attributes
        jd_lower = job_desc.lower()
        if not any(w in jd_lower for w in ["$", "salary", "compensation", "per year", "/yr", "hourly"]):
            missing.append("Job description lacks stated compensation range.")
        if not any(w in jd_lower for w in ["remote", "hybrid", "on-site", "location", "travel", "relocation"]):
            missing.append("Job description lacks explicit location or remote policy details.")

        # Check applicant priorities
        if not priorities.min_compensation:
            missing.append("Applicant minimum compensation preference is unspecified.")
        if not priorities.location_preference:
            missing.append("Applicant location or commute preference is unspecified.")
        if not priorities.desired_role_type:
            missing.append("Applicant desired role type is unspecified.")

        return missing

    def run(self, inputs: WorkflowInput) -> NormalizedInput:
        """Execute intake processing, returning normalized representation."""
        norm_resume = self.normalize_text(inputs.resume_text)
        norm_jd = self.normalize_text(inputs.job_description_text)

        # Normalize priorities
        cleaned_non_negotiables = [
            self.normalize_text(item) for item in inputs.priorities.non_negotiables if item.strip()
        ]
        norm_priorities = ApplicantPriorities(
            min_compensation=self.normalize_text(inputs.priorities.min_compensation or "") or None,
            location_preference=self.normalize_text(inputs.priorities.location_preference or "") or None,
            desired_role_type=self.normalize_text(inputs.priorities.desired_role_type or "") or None,
            non_negotiables=cleaned_non_negotiables,
        )

        sections = self.extract_resume_sections(norm_resume)
        missing = self.check_missing_information(norm_resume, norm_jd, norm_priorities, sections)

        return NormalizedInput(
            normalized_resume=norm_resume,
            normalized_job_description=norm_jd,
            normalized_priorities=norm_priorities,
            identified_missing_inputs=missing,
            resume_sections=sections,
            job_key_attributes={},
        )
