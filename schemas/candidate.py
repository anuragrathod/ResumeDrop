"""
schemas/candidate.py
====================
Canonical Pydantic v2 data models for candidate records.

Every successfully processed resume produces exactly one CandidateRecord.
Missing scalar values remain None; missing collections remain [].
Nothing is ever fabricated to fill required fields.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class EducationRecord(BaseModel):
    """A single qualification / degree."""

    qualification: Optional[str] = None
    """E.g. 'B.Tech', 'M.Sc.', 'Ph.D.'"""

    specialization: Optional[str] = None
    """E.g. 'Computer Science', 'Data Analytics'"""

    institution: Optional[str] = None
    """College or university name."""

    graduation_year: Optional[str] = None
    """4-digit year string, or original text when ambiguous (e.g. 'Expected 2025')."""

    start_year: Optional[str] = None
    """Start year if available."""

    @field_validator("graduation_year", "start_year", mode="before")
    @classmethod
    def coerce_year_to_str(cls, v: object) -> Optional[str]:
        """Accept int years from model output and convert to string."""
        if v is None:
            return None
        return str(v).strip() or None


class WorkExperience(BaseModel):
    """A single work experience entry."""

    employer: Optional[str] = None
    job_title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    summary: Optional[str] = None
    """AI-written one-line summary of role and impact."""
    responsibilities: list[str] = Field(default_factory=list)
    """Bullet-point responsibilities as a list of strings."""
    description: Optional[str] = None
    """Free-form description when a bullet list is not available."""


class Project(BaseModel):
    """A single project entry."""

    name: Optional[str] = None
    summary: Optional[str] = None
    """AI-written one-line summary of project purpose and outcome."""
    description: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)


class ExtractionMetadata(BaseModel):
    """Records what happened during extraction — never modifies candidate data."""

    processing_status: str = "pending"
    """One of: pending | success | partial | failed | review_required"""

    missing_fields: list[str] = Field(default_factory=list)
    """Names of fields that could not be extracted."""

    validation_issues: list[str] = Field(default_factory=list)
    """Human-readable descriptions of validation problems."""

    review_notes: list[str] = Field(default_factory=list)
    """Flags raised for manual review (conflicting data, low confidence, etc.)."""

    extraction_method: str = "none"
    """How the record was built: 'rules_only' | 'ai' | 'rules+ai' | 'none'"""

    model_used: Optional[str] = None
    """The NVIDIA NIM model tag that was used, e.g. 'meta/llama-3.3-70b-instruct'."""

    key_index_used: Optional[int] = None
    """Index of the NVIDIA API key from the multi-key pool that handled this record."""

    extracted_at: Optional[str] = None
    """ISO-8601 timestamp of extraction."""


# ---------------------------------------------------------------------------
# Top-level candidate record
# ---------------------------------------------------------------------------


class CandidateRecord(BaseModel):
    """The canonical output record for a single resume."""

    # ---- Identification --------------------------------------------------
    candidate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resume_filename: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None

    # ---- Education -------------------------------------------------------
    education: list[EducationRecord] = Field(default_factory=list)

    # ---- Skills ----------------------------------------------------------
    technical_skills: list[str] = Field(default_factory=list)
    programming_languages: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)

    # ---- Work experience -------------------------------------------------
    work_experience: list[WorkExperience] = Field(default_factory=list)

    # ---- Projects --------------------------------------------------------
    projects: list[Project] = Field(default_factory=list)

    # ---- Additional ------------------------------------------------------
    certifications: list[str] = Field(default_factory=list)
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    # ---- Metadata --------------------------------------------------------
    metadata: ExtractionMetadata = Field(default_factory=ExtractionMetadata)

    # ---- Source text (for inspection, not exported to candidate cells) ---
    raw_text_snippet: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: object) -> Optional[str]:
        if v is None or v == "":
            return None
        return str(v).strip().lower()

    @field_validator("phone", mode="before")
    @classmethod
    def coerce_phone(cls, v: object) -> Optional[str]:
        if v is None or v == "":
            return None
        return str(v).strip()

    @field_validator(
        "technical_skills", "programming_languages", "tools", "certifications",
        mode="before",
    )
    @classmethod
    def ensure_list(cls, v: object) -> list:
        if v is None:
            return []
        if isinstance(v, str):
            return [v] if v.strip() else []
        return list(v)

    @model_validator(mode="after")
    def stamp_extraction_time(self) -> "CandidateRecord":
        if self.metadata.extracted_at is None:
            self.metadata.extracted_at = datetime.now(timezone.utc).isoformat()
        return self

    def mark_missing(self, field_name: str) -> None:
        if field_name not in self.metadata.missing_fields:
            self.metadata.missing_fields.append(field_name)

    def add_issue(self, issue: str) -> None:
        self.metadata.validation_issues.append(issue)

    def add_review_note(self, note: str) -> None:
        self.metadata.review_notes.append(note)

    @property
    def is_complete(self) -> bool:
        return (
            not self.metadata.missing_fields
            and not self.metadata.validation_issues
        )

    @property
    def highest_degree(self) -> Optional[str]:
        if not self.education:
            return None
        for edu in self.education:
            if edu.qualification:
                if edu.specialization:
                    return f"{edu.qualification} in {edu.specialization}"
                return edu.qualification
        return None

    @property
    def years_of_experience(self) -> int:
        return len(self.work_experience)
