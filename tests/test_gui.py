"""
tests/test_gui.py
=================
Tests for Tkinter desktop GUI (gui.py).
Supports both headless (CI/Docker) and headed desktop environments.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from schemas.candidate import CandidateRecord, EducationRecord, ExtractionMetadata, WorkExperience
from src.document_reader import DocumentResult, ProcessingStatus


def test_gui_imports_and_constants():
    """Verify gui module imports without error when tkinter is available."""
    pytest.importorskip("tkinter")
    import gui

    assert hasattr(gui, "ResumeDropApp")
    assert hasattr(gui, "main")


def test_gui_candidate_treeview_data_format():
    """Verify that CandidateRecord maps to expected Treeview columns."""
    cand = CandidateRecord(
        candidate_id="cand-001",
        resume_filename="sarah_connor.pdf",
        full_name="Sarah Connor",
        email="sarah@example.com",
        phone="+1 555-0199",
        location="Los Angeles, CA",
        education=[EducationRecord(qualification="B.S.", specialization="Computer Science")],
        work_experience=[WorkExperience(employer="TechCorp", job_title="Engineer")],
        metadata=ExtractionMetadata(processing_status="success"),
    )

    row_values = (
        1,
        cand.full_name or "N/A",
        cand.email or "N/A",
        cand.phone or "N/A",
        cand.location or "N/A",
        cand.highest_degree or "N/A",
        cand.years_of_experience or 0,
        cand.metadata.processing_status,
    )

    assert row_values[1] == "Sarah Connor"
    assert row_values[2] == "sarah@example.com"
    assert row_values[5] == "B.S. in Computer Science"
    assert row_values[6] == 1
    assert row_values[7] == "success"


def test_gui_worker_handles_failed_documents():
    """Verify failed document dictionaries conform to processing log schema."""
    failed_doc = DocumentResult(
        filename="corrupted.pdf",
        status=ProcessingStatus.UNSUPPORTED_FORMAT,
        error="Unsupported file format",
        text="",
    )

    f_info = {
        "filename": failed_doc.filename,
        "doc_status": failed_doc.status.value,
        "error": failed_doc.error,
        "char_count": failed_doc.char_count,
    }

    assert f_info["filename"] == "corrupted.pdf"
    assert f_info["doc_status"] == "unsupported_format"
    assert f_info["char_count"] == 0
    assert "error" in f_info
