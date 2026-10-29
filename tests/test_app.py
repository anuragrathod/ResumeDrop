"""
tests/test_app.py
=================
Tests for ResumeDrop FastAPI application endpoints.
"""

from __future__ import annotations

import io
from fastapi.testclient import TestClient
import pytest

from app import app

client = TestClient(app)


def test_home_page_serves_html():
    """Verify GET / returns 200 OK with HTML content."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "ResumeDrop" in response.text
    assert "Resume-to-Excel Automation" in response.text


def test_logs_page_serves_html():
    """Verify GET /logs returns 200 OK with HTML content."""
    response = client.get("/logs")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "API Call Logs" in response.text


def test_get_api_logs_structure():
    """Verify GET /api/logs returns json with logs list having 5 required fields."""
    response = client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data
    assert isinstance(data["logs"], list)


def test_check_connection_endpoint():
    """Verify POST /api/check-connection returns clean boolean success and message."""
    response = client.post("/api/check-connection")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "message" in data
    # Ensure no API keys are exposed
    assert "nvapi-" not in data["message"]


def test_clear_logs_endpoint():
    """Verify POST /api/clear-logs resets in-memory logs."""
    response = client.post("/api/clear-logs")
    assert response.status_code == 200
    assert response.json().get("status") == "cleared"


def test_export_endpoint():
    """Verify POST /api/export produces downloadable Excel .xlsx file."""
    mock_candidates = [
        {
            "full_name": "Alice Chen",
            "email": "alice@example.com",
            "phone": "+1 555-0100",
            "location": "San Francisco, CA",
            "technical_skills": ["Python", "FastAPI"],
            "education": [{"qualification": "B.S. Computer Science"}],
            "work_experience": [{"employer": "Tech Corp", "job_title": "Software Engineer"}],
        }
    ]
    response = client.post("/api/export", json={"candidates": mock_candidates})
    assert response.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers["content-type"]
    assert len(response.content) > 1000
