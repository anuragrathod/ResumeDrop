"""
src/validator.py
================
Phase 2: Post-extraction validation, normalisation, and formula sanitisation.

Checks:
- Email syntax validation.
- Phone number plausibility (7 to 15 digits).
- Graduation-year plausibility (1950 to 2035).
- Duplicate education and work experience detection.
- Spreadsheet formula injection protection (prefixing with ' for Excel safety).
"""

from __future__ import annotations

import re
from typing import Optional

from schemas.candidate import CandidateRecord

_MIN_GRAD_YEAR = 1950
_MAX_GRAD_YEAR = 2035

# Characters that trigger spreadsheet formula execution in Excel / Calc
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

_VALID_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def validate_email(email: Optional[str]) -> Optional[str]:
    """Return an issue string if email is malformed, else None."""
    if email is None:
        return None
    if not _VALID_EMAIL_RE.match(email.strip()):
        return f"Email '{email}' does not appear to be valid."
    return None


def validate_phone(phone: Optional[str]) -> Optional[str]:
    """Return an issue string if phone has an implausible digit count."""
    if phone is None:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 7:
        return f"Phone '{phone}' has fewer than 7 digits — likely not a phone number."
    if len(digits) > 15:
        return f"Phone '{phone}' has more than 15 digits — likely not a phone number."
    return None


def validate_graduation_years(record: CandidateRecord) -> list[str]:
    """Return issue strings for implausible graduation or start years."""
    issues = []
    for edu in record.education:
        for attr in ("graduation_year", "start_year"):
            raw = getattr(edu, attr, None)
            if raw is None:
                continue
            year_match = re.search(r"\b(19|20)\d{2}\b", str(raw))
            if year_match:
                year = int(year_match.group())
                if not (_MIN_GRAD_YEAR <= year <= _MAX_GRAD_YEAR):
                    issues.append(
                        f"Education {attr} '{raw}' is outside the plausible range "
                        f"({_MIN_GRAD_YEAR}–{_MAX_GRAD_YEAR})."
                    )
    return issues


def sanitise_formula_injection(value: Optional[str]) -> Optional[str]:
    """Prefix a string with a single quote if it starts with a formula character."""
    if value is None:
        return None
    str_val = str(value)
    if any(str_val.startswith(prefix) for prefix in _FORMULA_PREFIXES):
        return "'" + str_val
    return str_val


def _find_duplicates(items: list, key_fn) -> list[str]:
    """Return a list of duplicate keys found in items."""
    seen: set = set()
    dupes: list[str] = []
    for item in items:
        k = key_fn(item)
        if k and k.lower() in seen:
            dupes.append(str(k))
        elif k:
            seen.add(k.lower())
    return dupes


def validate_candidate(record: CandidateRecord) -> CandidateRecord:
    """Run all post-extraction validation passes on record in place."""
    record.metadata.validation_issues = []
    record.metadata.review_notes = []

    # Email
    email_issue = validate_email(record.email)
    if email_issue:
        record.add_issue(email_issue)

    # Phone
    phone_issue = validate_phone(record.phone)
    if phone_issue:
        record.add_issue(phone_issue)

    # Graduation years
    for issue in validate_graduation_years(record):
        record.add_issue(issue)

    # Duplicate education
    edu_dupes = _find_duplicates(
        record.education,
        lambda e: (e.institution or "") + "_" + (e.qualification or ""),
    )
    for dupe in edu_dupes:
        record.add_review_note(f"Duplicate education entry detected: '{dupe}'")

    # Duplicate work experience
    exp_dupes = _find_duplicates(
        record.work_experience,
        lambda e: (e.employer or "") + "_" + (e.job_title or ""),
    )
    for dupe in exp_dupes:
        record.add_review_note(f"Duplicate work experience entry detected: '{dupe}'")

    # Missing recommended fields
    record.metadata.missing_fields = []
    if not record.full_name:
        record.mark_missing("full_name")
    if not record.email:
        record.mark_missing("email")
    if not record.phone:
        record.mark_missing("phone")
    if not record.education:
        record.mark_missing("education")
    if not (record.technical_skills or record.programming_languages or record.tools):
        record.mark_missing("technical_skills")

    # Status update
    if record.metadata.validation_issues:
        record.metadata.processing_status = "review_required"

    return record
