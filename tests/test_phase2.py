"""Unit tests for Phase 2: rule extractors, normalizers, and validator."""
from schemas.candidate import CandidateRecord, EducationRecord, WorkExperience
from src.resume_parser import (
    clean_education,
    clean_name,
    clean_phone,
    clean_skills_list,
    extract_email,
    extract_github_url,
    extract_linkedin_url,
    extract_phone,
    run_rule_based_extraction,
)
from src.validator import (
    sanitise_formula_injection,
    validate_candidate,
    validate_email,
    validate_phone,
)


def test_extract_email():
    text = "Candidate: Alice Smith | Email: Alice.Smith@Example.COM | Phone: 555-1234"
    assert extract_email(text) == "alice.smith@example.com"
    assert extract_email("No email here") is None


def test_extract_phone_formats():
    assert extract_phone("Call me at +1 (650) 555-0101 today") is not None
    assert extract_phone("India mobile: +91-98765-43210") is not None
    assert extract_phone("Bare: 9876543210") is not None


def test_extract_profile_urls():
    text = "Profiles: linkedin.com/in/alice-smith and github.com/alicesmith"
    li = extract_linkedin_url(text)
    gh = extract_github_url(text)
    assert li == "https://linkedin.com/in/alice-smith"
    assert gh == "https://github.com/alicesmith"


def test_clean_name():
    assert clean_name("Name: SARTHAK PADWAL") == "Sarthak Padwal"
    assert clean_name("Anurag Rathod | Python Developer") == "Anurag Rathod"
    assert clean_name("Jane Doe - Software Engineer") == "Jane Doe"


def test_clean_skills_list():
    raw = ["Python, Docker, AWS", "python", "Docker", "FastAPI"]
    cleaned = clean_skills_list(raw)
    assert cleaned == ["Python", "Docker", "AWS", "FastAPI"]


def test_formula_injection_sanitization():
    assert sanitise_formula_injection("=SUM(A1:A10)") == "'=SUM(A1:A10)"
    assert sanitise_formula_injection("+12345") == "'+12345"
    assert sanitise_formula_injection("-50") == "'-50"
    assert sanitise_formula_injection("@special") == "'@special"
    assert sanitise_formula_injection("Normal Text") == "Normal Text"


def test_candidate_validator():
    cand = CandidateRecord(
        resume_filename="test.pdf",
        full_name="Bob Smith",
        email="invalid-email-address",
        phone="123",  # fewer than 7 digits
        education=[EducationRecord(qualification="B.S.", graduation_year="1850")],
    )
    validated = validate_candidate(cand)
    assert validated.metadata.processing_status == "review_required"
    assert len(validated.metadata.validation_issues) >= 2
