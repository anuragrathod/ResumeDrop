"""
src/excel_exporter.py
=====================
Phase 3: Formatted 5-worksheet Excel workbook generation using openpyxl.

Worksheets:
  1. Candidates      — one row per candidate (summary)
  2. Education       — one row per qualification
  3. Work Experience — one row per job
  4. Projects        — one row per project
  5. Processing Log  — audit trail of all processed documents & failures
"""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Optional, Sequence

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from schemas.candidate import CandidateRecord, EducationRecord
from src.validator import sanitise_formula_injection

logger = logging.getLogger(__name__)

_HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
_HEADER_FILL = PatternFill(fill_type="solid", fgColor="1F497D")  # dark blue
_WRAP_ALIGN = Alignment(wrap_text=True, vertical="top")
_TOP_ALIGN = Alignment(vertical="top")

_STATUS_COLOURS: dict[str, str] = {
    "success": "C6EFCE",  # light green
    "partial": "FFEB9C",  # light amber
    "review_required": "FFEB9C",  # light amber
    "failed": "FFC7CE",  # light red
    "pending": "DDDDDD",  # grey
}


def _safe(value: Optional[str]) -> str:
    if value is None:
        return ""
    sanitised = sanitise_formula_injection(str(value))
    return sanitised or ""


def _safe_phone(phone: Optional[str]) -> str:
    return _safe(phone)


def _join(items: list[str], sep: str = "; ") -> str:
    return sep.join(i for i in items if i)


def _style_header_row(ws, col_count: int) -> None:
    for col in range(1, col_count + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = _TOP_ALIGN


def _freeze_and_filter(ws, col_count: int) -> None:
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(col_count)}1"


def _set_column_widths(ws, widths: list[int]) -> None:
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _colour_status_cell(cell, status: str) -> None:
    colour = _STATUS_COLOURS.get(str(status).lower(), "FFFFFF")
    cell.fill = PatternFill(fill_type="solid", fgColor=colour)


def get_highest_education(records: list[EducationRecord]) -> Optional[EducationRecord]:
    """Rank credentials: Ph.D. > Master's > Bachelor's > Diploma > High School."""
    if not records:
        return None

    def _rank(edu: EducationRecord) -> tuple[int, int]:
        q = (edu.qualification or "").lower()
        level = 0
        if any(w in q for w in ("ph.d", "phd", "doctorate", "doctoral")):
            level = 5
        elif any(w in q for w in ("m.tech", "m.e.", "m.s.", "m.sc", "mca", "mba", "master")):
            level = 4
        elif any(w in q for w in ("b.tech", "b.e.", "b.s.", "b.sc", "bca", "bba", "bachelor", "degree")):
            level = 3
        elif any(w in q for w in ("diploma", "polytechnic")):
            level = 2
        elif any(w in q for w in ("hsc", "ssc", "12th", "10th", "high school", "secondary")):
            level = 1

        yr = 0
        if edu.graduation_year:
            m = re.search(r"\b(19\d\d|20\d\d)\b", str(edu.graduation_year))
            if m:
                yr = int(m.group(1))
        return (level, yr)

    return max(records, key=_rank)


def _build_candidates_sheet(wb: openpyxl.Workbook, records: list[CandidateRecord]) -> None:
    ws = wb.active
    ws.title = "Candidates"

    headers = [
        "Candidate ID", "Resume Filename", "Full Name", "Email", "Phone",
        "Location", "Highest Qualification", "Specialization", "Institution",
        "Graduation Year", "All Education",
        "Technical Skills", "Programming Languages", "Tools",
        "Total Experience (jobs)", "Certifications",
        "LinkedIn URL", "GitHub URL", "Portfolio URL",
        "Processing Status", "Extraction Method",
        "Missing Fields", "Validation Issues", "Review Notes",
    ]

    ws.append(headers)
    _style_header_row(ws, len(headers))

    for rec in records:
        highest_edu = get_highest_education(rec.education)
        all_edu = _join([
            " | ".join(filter(None, [
                e.qualification, e.specialization, e.institution, e.graduation_year
            ]))
            for e in rec.education
        ])
        status = rec.metadata.processing_status

        row = [
            _safe(rec.candidate_id),
            _safe(rec.resume_filename),
            _safe(rec.full_name),
            _safe(rec.email),
            _safe_phone(rec.phone),
            _safe(rec.location),
            _safe(highest_edu.qualification if highest_edu else None),
            _safe(highest_edu.specialization if highest_edu else None),
            _safe(highest_edu.institution if highest_edu else None),
            _safe(highest_edu.graduation_year if highest_edu else None),
            _safe(all_edu),
            _join(rec.technical_skills),
            _join(rec.programming_languages),
            _join(rec.tools),
            str(len(rec.work_experience)),
            _join(rec.certifications),
            _safe(rec.linkedin_url),
            _safe(rec.github_url),
            _safe(rec.portfolio_url),
            _safe(status),
            _safe(rec.metadata.extraction_method),
            _join(rec.metadata.missing_fields, ", "),
            _join(rec.metadata.validation_issues),
            _join(rec.metadata.review_notes),
        ]
        ws.append(row)

        status_cell = ws.cell(row=ws.max_row, column=20)
        _colour_status_cell(status_cell, status)

        for col in (11, 12, 13, 14, 16, 22, 23, 24):
            ws.cell(row=ws.max_row, column=col).alignment = _WRAP_ALIGN

    _freeze_and_filter(ws, len(headers))
    _set_column_widths(ws, [
        14, 24, 22, 28, 16, 20,
        22, 20, 26, 14, 40,
        30, 26, 26,
        10, 30,
        30, 30, 30,
        18, 14,
        24, 40, 32,
    ])


def _build_education_sheet(wb: openpyxl.Workbook, records: list[CandidateRecord]) -> None:
    ws = wb.create_sheet("Education")
    headers = [
        "Candidate ID", "Resume Filename", "Full Name",
        "Qualification", "Specialization", "Institution",
        "Start Year", "Graduation Year",
    ]
    ws.append(headers)
    _style_header_row(ws, len(headers))

    for rec in records:
        for edu in rec.education:
            ws.append([
                _safe(rec.candidate_id),
                _safe(rec.resume_filename),
                _safe(rec.full_name),
                _safe(edu.qualification),
                _safe(edu.specialization),
                _safe(edu.institution),
                _safe(edu.start_year),
                _safe(edu.graduation_year),
            ])

    _freeze_and_filter(ws, len(headers))
    _set_column_widths(ws, [14, 24, 22, 26, 22, 30, 12, 14])


def _build_experience_sheet(wb: openpyxl.Workbook, records: list[CandidateRecord]) -> None:
    ws = wb.create_sheet("Work Experience")
    headers = [
        "Candidate ID", "Resume Filename", "Full Name",
        "Employer", "Job Title", "Start Date", "End Date",
        "Responsibilities", "Description",
    ]
    ws.append(headers)
    _style_header_row(ws, len(headers))

    for rec in records:
        for exp in rec.work_experience:
            resp_str = _join(exp.responsibilities, "\n• ")
            if resp_str:
                resp_str = "• " + resp_str
            ws.append([
                _safe(rec.candidate_id),
                _safe(rec.resume_filename),
                _safe(rec.full_name),
                _safe(exp.employer),
                _safe(exp.job_title),
                _safe(exp.start_date),
                _safe(exp.end_date),
                _safe(resp_str),
                _safe(exp.description),
            ])
            for col in (8, 9):
                ws.cell(row=ws.max_row, column=col).alignment = _WRAP_ALIGN

    _freeze_and_filter(ws, len(headers))
    _set_column_widths(ws, [14, 24, 22, 26, 22, 14, 14, 50, 40])


def _build_projects_sheet(wb: openpyxl.Workbook, records: list[CandidateRecord]) -> None:
    ws = wb.create_sheet("Projects")
    headers = [
        "Candidate ID", "Resume Filename", "Full Name",
        "Project Name", "Description", "Technologies",
    ]
    ws.append(headers)
    _style_header_row(ws, len(headers))

    for rec in records:
        for proj in rec.projects:
            ws.append([
                _safe(rec.candidate_id),
                _safe(rec.resume_filename),
                _safe(rec.full_name),
                _safe(proj.name),
                _safe(proj.description),
                _join(proj.technologies),
            ])
            ws.cell(row=ws.max_row, column=5).alignment = _WRAP_ALIGN

    _freeze_and_filter(ws, len(headers))
    _set_column_widths(ws, [14, 24, 22, 28, 50, 30])


def _build_log_sheet(
    wb: openpyxl.Workbook,
    records: list[CandidateRecord],
    failed_docs: Optional[list[dict]] = None,
) -> None:
    ws = wb.create_sheet("Processing Log")
    headers = [
        "Resume Filename", "Document Status", "Extraction Status",
        "Extraction Method", "Characters Extracted",
        "Missing Fields", "Validation Issues", "Failure Reason",
        "Extracted At",
    ]
    ws.append(headers)
    _style_header_row(ws, len(headers))

    for rec in records:
        status = rec.metadata.processing_status
        row = [
            _safe(rec.resume_filename),
            "success",
            _safe(status),
            _safe(rec.metadata.extraction_method),
            len(rec.raw_text_snippet or "") * 10 if rec.raw_text_snippet else 0,
            _join(rec.metadata.missing_fields, ", "),
            _join(rec.metadata.validation_issues),
            "",
            _safe(rec.metadata.extracted_at),
        ]
        ws.append(row)
        status_cell = ws.cell(row=ws.max_row, column=3)
        _colour_status_cell(status_cell, status)

    for failed in (failed_docs or []):
        row = [
            _safe(failed.get("filename")),
            _safe(failed.get("doc_status", "failed")),
            "failed",
            "none",
            failed.get("char_count", 0),
            "",
            "",
            _safe(failed.get("error", "")),
            "",
        ]
        ws.append(row)
        ws.cell(row=ws.max_row, column=3).fill = PatternFill(
            fill_type="solid", fgColor=_STATUS_COLOURS["failed"]
        )

    _freeze_and_filter(ws, len(headers))
    _set_column_widths(ws, [28, 18, 18, 16, 18, 24, 40, 40, 26])

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.column in (6, 7, 8):
                cell.alignment = _WRAP_ALIGN


def export_to_bytes(
    records: Sequence[CandidateRecord],
    failed_docs: Optional[list[dict]] = None,
) -> bytes:
    """Generate in-memory .xlsx workbook bytes."""
    record_list = list(records)
    wb = openpyxl.Workbook()

    _build_candidates_sheet(wb, record_list)
    _build_education_sheet(wb, record_list)
    _build_experience_sheet(wb, record_list)
    _build_projects_sheet(wb, record_list)
    _build_log_sheet(wb, record_list, failed_docs=failed_docs)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def export_to_file(
    records: Sequence[CandidateRecord],
    output_path: str | Path,
    failed_docs: Optional[list[dict]] = None,
) -> Path:
    """Write an Excel workbook to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = export_to_bytes(records, failed_docs=failed_docs)
    path.write_bytes(data)
    return path
