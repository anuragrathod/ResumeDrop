"""
src/resume_parser.py
====================
Rule-based extraction, orchestrator, and concurrent batch processing.

Coordinates:
1. Rule-based extraction on cleaned text (email, phone, URLs).
2. AI-based extraction via multi-key NVIDIA NIM extractor.
3. Merging results with priority rules.
4. Validation and candidate normalization.
5. Parallel batch processing across multiple worker threads.
"""

from __future__ import annotations

import concurrent.futures
import logging
import re
from typing import Callable, Optional

from schemas.candidate import (
    CandidateRecord,
    EducationRecord,
    ExtractionMetadata,
    Project,
    WorkExperience,
)
from src.ai_extractor import AIExtractor
from src.document_reader import DocumentResult, ProcessingStatus
from src.validator import validate_candidate

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regular Expressions
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(
    r"(?<![^\s])([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    re.IGNORECASE,
)

_PHONE_RE = re.compile(
    r"""
    (?<!\d)
    (?:
        \+\d{1,3}[\s\-\.]?
        (?:\(?\d{1,4}\)?[\s\-\.]?)?
        \d{3,5}[\s\-\.]?\d{3,5}
        |
        0\d{10}
        |
        [6-9]\d{9}
    )
    (?!\d)
    """,
    re.VERBOSE,
)

_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-%.]+/?",
    re.IGNORECASE,
)

_GITHUB_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+/?",
    re.IGNORECASE,
)

_PORTFOLIO_RE = re.compile(
    r"https?://(?:www\.)?(?!linkedin\.com|github\.com|mail\.google|gmail)"
    r"[\w\-]+\.(?:io|dev|me|site|tech|app|co|com|net|org)/[\w\-./]*",
    re.IGNORECASE,
)

_LOCATION_RE = re.compile(
    r"(?:(?:map[-_ ]*marker(?:[-_ ]*alt)?|location|address|residence|city)\s*[:\-]?\s*)?"
    r"([A-Z][a-zA-Z\s]{1,30},\s*[A-Z][a-zA-Z\s]{1,30}(?:\s*,\s*[A-Z][a-zA-Z\s]{1,30})?)",
    re.VERBOSE,
)

_MIN_PHONE_DIGITS = 8
_MAX_PHONE_CANDIDATES = 3
_RULE_PRIORITY_FIELDS = {"email", "phone", "linkedin_url", "github_url", "portfolio_url"}


# ---------------------------------------------------------------------------
# Rule-based extractors
# ---------------------------------------------------------------------------


def extract_email(text: str) -> Optional[str]:
    match = _EMAIL_RE.search(text)
    return match.group(1).lower() if match else None


def extract_phone(text: str) -> Optional[str]:
    candidates: list[str] = []
    for match in _PHONE_RE.finditer(text):
        raw = match.group(0).strip()
        digit_count = sum(c.isdigit() for c in raw)
        if _MIN_PHONE_DIGITS <= digit_count <= 15:
            candidates.append(raw)
        if len(candidates) >= _MAX_PHONE_CANDIDATES:
            break

    if not candidates:
        return None

    chosen = max(candidates, key=lambda s: sum(c.isdigit() for c in s))
    cleaned = re.sub(
        r"^(?:phone[-_ ]*(?:alt)?|tel|mobile|cell)\s*[:\-]?\s*",
        "",
        chosen,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned or chosen


def extract_linkedin_url(text: str) -> Optional[str]:
    match = _LINKEDIN_RE.search(text)
    if not match:
        return None
    url = match.group(0).strip().rstrip("/")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def extract_github_url(text: str) -> Optional[str]:
    match = _GITHUB_RE.search(text)
    if not match:
        return None
    url = match.group(0).strip().rstrip("/")
    if not url.lower().startswith(("http://", "https://")):
        url = "https://" + url
    return url


def extract_portfolio_url(text: str) -> Optional[str]:
    match = _PORTFOLIO_RE.search(text)
    return match.group(0) if match else None


def extract_name(text: str) -> Optional[str]:
    """Heuristic fallback for candidate name in the first few lines."""
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:8]:
        if any(w in line for w in ("@", "http", "www.", ".com", ".org", ".in")):
            continue
        if sum(c.isdigit() for c in line) >= 3:
            continue
        if line.startswith(("-", "*", "•", "#", ">", "|")):
            continue
        lower = line.lower()
        if any(h in lower for h in (
            "curriculum vitae", "resume", "cv", "profile", "contact",
            "experience", "education", "skills", "projects", "summary",
            "objective", "phone", "email", "address"
        )):
            continue
        candidate = re.sub(r"^(?:name|candidate|user)\s*[:\-]\s*", "", line, flags=re.IGNORECASE).strip()
        if " | " in candidate:
            candidate = candidate.split(" | ")[0].strip()
        elif " - " in candidate:
            candidate = candidate.split(" - ")[0].strip()

        words = candidate.split()
        if 2 <= len(words) <= 4 and all(re.match(r"^[A-Za-z.\-']+$", w) for w in words):
            if candidate.isupper():
                candidate = candidate.title()
            return candidate
    return None


def extract_location(text: str) -> Optional[str]:
    """Heuristic fallback for location in top lines."""
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()][:15]
    for line in lines:
        match = _LOCATION_RE.search(line)
        if match:
            loc = match.group(1).strip().strip("|,;:-•")
            if not any(w in loc.lower() for w in ("university", "college", "school", "technologies", "institute", "developer", "engineer")):
                return loc
    return None


def run_rule_based_extraction(text: str) -> dict:
    return {
        "email": extract_email(text),
        "phone": extract_phone(text),
        "linkedin_url": extract_linkedin_url(text),
        "github_url": extract_github_url(text),
        "portfolio_url": extract_portfolio_url(text),
        "full_name": extract_name(text),
        "location": extract_location(text),
    }


# ---------------------------------------------------------------------------
# Normalization & Cleaning Helpers
# ---------------------------------------------------------------------------


def clean_name(name: Optional[str]) -> Optional[str]:
    if not name or not name.strip():
        return None
    cleaned = re.sub(
        r"^(?:name\s*[:\-]|candidate\s*[:\-]|resume\s*[:\-]|cv\s*[:\-])\s*",
        "",
        name.strip(),
        flags=re.IGNORECASE,
    ).strip()
    if " | " in cleaned:
        cleaned = cleaned.split(" | ")[0].strip()
    elif " - " in cleaned and len(cleaned.split(" - ")) == 2:
        parts = cleaned.split(" - ")
        if any(w in parts[1].lower() for w in ("developer", "engineer", "designer", "intern", "manager", "tester", "student")):
            cleaned = parts[0].strip()
    if cleaned.isupper() and len(cleaned) > 2:
        cleaned = cleaned.title()
    return cleaned or None


def clean_phone(phone: Optional[str]) -> Optional[str]:
    if not phone or not phone.strip():
        return None
    cleaned = re.sub(r"^(?:phone[-_ ]*(?:alt)?|tel|mobile|cell)\s*[:\-]?\s*", "", phone.strip(), flags=re.IGNORECASE).strip()
    return cleaned or None


def clean_location(loc: Optional[str]) -> Optional[str]:
    if not loc or not str(loc).strip():
        return None
    cleaned = re.sub(
        r"^(?:map[-_ ]*marker(?:[-_ ]*alt)?|location|address|city|residence|pin)\s*[:\-]?\s*",
        "",
        str(loc).strip(),
        flags=re.IGNORECASE,
    ).strip().strip("|,;:-•")
    return cleaned or None


def clean_url(url: Optional[str]) -> Optional[str]:
    if not url or not url.strip():
        return None
    cleaned = url.strip().rstrip("/")
    if not cleaned.lower().startswith(("http://", "https://")):
        cleaned = "https://" + cleaned
    return cleaned


def clean_skills_list(skills: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for s in skills:
        if not s or not isinstance(s, str):
            continue
        for sub in s.split(","):
            item = sub.strip("'\"`.,;:-•*[]() ").strip()
            if item and item.lower() not in seen:
                seen.add(item.lower())
                cleaned.append(item)
    return cleaned


def clean_education(edu: EducationRecord) -> EducationRecord:
    if edu.qualification and " in " in edu.qualification and not edu.specialization:
        parts = edu.qualification.split(" in ", 1)
        edu.qualification = parts[0].strip()
        edu.specialization = parts[1].strip()
    elif edu.qualification and " - " in edu.qualification and not edu.specialization:
        parts = edu.qualification.split(" - ", 1)
        edu.qualification = parts[0].strip()
        edu.specialization = parts[1].strip()

    if edu.graduation_year and (" - " in edu.graduation_year or "–" in edu.graduation_year or " to " in edu.graduation_year):
        sep = " - " if " - " in edu.graduation_year else ("–" if "–" in edu.graduation_year else " to ")
        parts = [p.strip() for p in edu.graduation_year.split(sep, 1)]
        if len(parts) == 2:
            m_start = re.search(r"\b(19\d\d|20\d\d)\b", parts[0])
            if m_start and not edu.start_year:
                edu.start_year = m_start.group(1)
            m_end = re.search(r"\b(19\d\d|20\d\d)\b", parts[1])
            edu.graduation_year = m_end.group(1) if m_end else parts[1]
    return edu


def clean_work_experience(exp: WorkExperience) -> WorkExperience:
    if exp.start_date and not exp.end_date:
        s = exp.start_date.strip()
        if " - " in s or "–" in s or " to " in s:
            sep = " - " if " - " in s else ("–" if "–" in s else " to ")
            parts = [p.strip() for p in s.split(sep, 1)]
            if len(parts) == 2:
                exp.start_date = parts[0]
                exp.end_date = parts[1]

    cleaned_resp: list[str] = []
    for r in exp.responsibilities:
        if r and isinstance(r, str):
            b = re.sub(r"^[\s•*–\-\u2022\u25cf\u25cb\u25aa\d.]+\s*", "", r).strip()
            if b:
                cleaned_resp.append(b)
    exp.responsibilities = cleaned_resp

    if not exp.responsibilities and exp.description:
        lines = [l.strip() for l in exp.description.splitlines() if l.strip()]
        if len(lines) > 1 or (lines and re.match(r"^[\s•*–\-\u2022\u25cf]", lines[0])):
            exp.responsibilities = [re.sub(r"^[\s•*–\-\u2022\u25cf\u25cb\u25aa\d.]+\s*", "", l).strip() for l in lines]
            exp.description = None
    return exp


def clean_project(proj: Project) -> Project:
    if proj.name:
        name = proj.name.strip()
        if "|" in name:
            parts = [p.strip() for p in name.split("|", 1)]
            proj.name = parts[0].strip()
            if len(parts) > 1 and not proj.technologies:
                proj.technologies = [t.strip() for t in parts[1].split(",") if t.strip()]
        elif "(" in name and name.endswith(")"):
            m = re.match(r"^(.*?)\s*\((.*?)\)$", name)
            if m:
                proj.name = m.group(1).strip()
                if not proj.technologies:
                    proj.technologies = [t.strip() for t in m.group(2).split(",") if t.strip()]
    return proj


def _merge_results(rule_data: dict, ai_data: dict) -> dict:
    merged = dict(ai_data)
    conflicts: list[str] = []

    for field in _RULE_PRIORITY_FIELDS:
        rule_val = rule_data.get(field)
        ai_val = ai_data.get(field)

        if rule_val is not None:
            if field == "phone" and ai_val is not None:
                rule_digits = "".join(c for c in str(rule_val) if c.isdigit())
                ai_digits = "".join(c for c in str(ai_val) if c.isdigit())
                if str(ai_val).strip().startswith("+") and ai_digits.endswith(rule_digits):
                    merged[field] = ai_val
                    continue
            if ai_val is not None and ai_val != rule_val:
                conflicts.append(f"{field}: rule='{rule_val}' vs ai='{ai_val}' — kept rule value")
            merged[field] = rule_val
        elif ai_val is not None:
            merged[field] = ai_val

    merged["_conflicts"] = conflicts
    return merged


# ---------------------------------------------------------------------------
# Orchestrator & Parallel Parser
# ---------------------------------------------------------------------------


class ResumeParser:
    """Coordinates rule-based and multi-key NVIDIA NIM extraction for single or batch resumes."""

    def __init__(
        self,
        ai_extractor: Optional[AIExtractor] = None,
        max_chars: int = 25000,
    ) -> None:
        self.ai = ai_extractor
        self.max_chars = max_chars

    def parse(self, doc: DocumentResult) -> CandidateRecord:
        """Parse a single document into a validated CandidateRecord."""
        record = CandidateRecord(
            resume_filename=doc.filename,
            metadata=ExtractionMetadata(
                processing_status="pending",
                extraction_method="none",
            ),
        )

        if doc.status != ProcessingStatus.SUCCESS:
            record.metadata.processing_status = "failed"
            record.metadata.validation_issues.append(
                f"Document reading failed: {doc.status.value} — {doc.error}"
            )
            return record

        text = doc.text
        record.raw_text_snippet = text[:500] if text else None

        # 1. Rule extraction
        rule_data = run_rule_based_extraction(text)

        # 2. AI extraction
        ai_data: dict = {}
        ai_method = "rules_only"
        model_used: Optional[str] = None
        key_index_used: Optional[int] = None

        if self.ai is not None:
            truncated = text[: self.max_chars]
            ai_res = self.ai.extract(truncated, doc.filename)
            if ai_res.success:
                ai_data = ai_res.data
                ai_method = "rules+ai"
                model_used = ai_res.model_used
                key_index_used = ai_res.key_index
            else:
                record.add_issue(f"AI extraction failed: {ai_res.error}")
                record.metadata.processing_status = "partial"

        # 3. Merge
        merged = _merge_results(rule_data, ai_data)
        for conflict in merged.pop("_conflicts", []):
            record.add_review_note(conflict)

        # 4. Fallbacks for missing name / location
        if not merged.get("full_name") and rule_data.get("full_name"):
            merged["full_name"] = rule_data["full_name"]
        if not merged.get("location") and rule_data.get("location"):
            merged["location"] = rule_data["location"]

        # 5. Populate
        self._populate_record(record, merged)

        # 6. Metadata stamp
        if record.metadata.processing_status == "pending":
            record.metadata.processing_status = "success"
        record.metadata.extraction_method = ai_method
        record.metadata.model_used = model_used
        record.metadata.key_index_used = key_index_used

        # 7. Post-validation
        return validate_candidate(record)

    def parse_batch_parallel(
        self,
        docs: list[DocumentResult],
        max_workers: int = 3,
        callback: Optional[Callable[[int, int, CandidateRecord | dict], None]] = None,
    ) -> tuple[list[CandidateRecord], list[dict]]:
        """Process a list of documents in parallel using ThreadPoolExecutor."""
        candidates: list[CandidateRecord] = []
        failed_docs: list[dict] = []
        total = len(docs)

        # Separate failed documents from success documents
        valid_docs = [d for d in docs if d.status == ProcessingStatus.SUCCESS]
        failed_in_reader = [d for d in docs if d.status != ProcessingStatus.SUCCESS]

        for fd in failed_in_reader:
            f_info = {
                "filename": fd.filename,
                "doc_status": fd.status.value,
                "error": fd.error,
                "char_count": fd.char_count,
            }
            failed_docs.append(f_info)

        if not valid_docs:
            return candidates, failed_docs

        workers = max(1, min(max_workers, len(valid_docs)))
        completed = len(failed_docs)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_doc = {executor.submit(self.parse, doc): doc for doc in valid_docs}

            for future in concurrent.futures.as_completed(future_to_doc):
                doc = future_to_doc[future]
                completed += 1
                try:
                    cand = future.result()
                    candidates.append(cand)
                    if callback:
                        callback(completed, total, cand)
                except Exception as exc:
                    err_info = {
                        "filename": doc.filename,
                        "doc_status": "error",
                        "error": str(exc),
                        "char_count": doc.char_count,
                    }
                    failed_docs.append(err_info)
                    if callback:
                        callback(completed, total, err_info)

        return candidates, failed_docs

    def _populate_record(self, record: CandidateRecord, data: dict) -> None:
        if data.get("full_name"):
            record.full_name = clean_name(data["full_name"])
        if data.get("email"):
            record.email = str(data["email"]).strip().lower()
        if data.get("phone"):
            record.phone = clean_phone(data["phone"])
        if data.get("location"):
            record.location = clean_location(data["location"])
        if data.get("linkedin_url"):
            record.linkedin_url = clean_url(data["linkedin_url"])
        if data.get("github_url"):
            record.github_url = clean_url(data["github_url"])
        if data.get("portfolio_url"):
            record.portfolio_url = clean_url(data["portfolio_url"])

        record.technical_skills = clean_skills_list(data.get("technical_skills") or [])
        record.programming_languages = clean_skills_list(data.get("programming_languages") or [])
        record.tools = clean_skills_list(data.get("tools") or [])
        record.certifications = clean_skills_list(data.get("certifications") or [])

        # Education
        edu_items = []
        for item in data.get("education") or []:
            if isinstance(item, dict):
                edu_items.append(clean_education(EducationRecord(**item)))
            elif isinstance(item, EducationRecord):
                edu_items.append(clean_education(item))
        record.education = edu_items

        # Experience
        exp_items = []
        for item in data.get("work_experience") or []:
            if isinstance(item, dict):
                exp_items.append(clean_work_experience(WorkExperience(**item)))
            elif isinstance(item, WorkExperience):
                exp_items.append(clean_work_experience(item))
        record.work_experience = exp_items

        # Projects
        proj_items = []
        for item in data.get("projects") or []:
            if isinstance(item, dict):
                proj_items.append(clean_project(Project(**item)))
            elif isinstance(item, Project):
                proj_items.append(clean_project(item))
        record.projects = proj_items
