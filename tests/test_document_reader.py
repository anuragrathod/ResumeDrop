"""Unit tests for src/document_reader.py and src/utils.py."""
import tempfile
from pathlib import Path
import pytest

from src.document_reader import DocumentReader, ProcessingStatus
from src.utils import clean_text, compute_sha256, is_supported_file, is_text_empty


def test_clean_text_normalization():
    raw = "John Doe\r\n\r\nSoftware  Engineer\t\tResume\n\n\n\nSan Francisco\u00A0CA"
    cleaned = clean_text(raw)
    assert "John Doe" in cleaned
    assert "Software Engineer" in cleaned
    assert "San Francisco CA" in cleaned
    assert "\r" not in cleaned
    assert "\n\n\n" not in cleaned


def test_is_text_empty():
    assert is_text_empty("", min_chars=50) is True
    assert is_text_empty("   \n\t   ", min_chars=50) is True
    assert is_text_empty("Short text", min_chars=50) is True
    assert is_text_empty("A" * 60, min_chars=50) is False


def test_sha256_computation():
    data = b"Hello world resume content"
    h1 = compute_sha256(data)
    h2 = compute_sha256(data)
    assert h1 == h2
    assert len(h1) == 64


def test_process_text_file():
    reader = DocumentReader(min_text_chars=10)
    content = "Jane Doe\njane@example.com | 555-0199 | Austin, TX\nSenior Python Engineer with 8 years experience."
    res = reader.process_bytes(content.encode("utf-8"), "jane_resume.txt")
    assert res.status == ProcessingStatus.SUCCESS
    assert "Jane Doe" in res.text
    assert res.char_count > 20


def test_duplicate_file_detection():
    reader = DocumentReader(min_text_chars=10)
    content = b"Same identical candidate resume content for duplicate testing."
    seen = set()

    res1 = reader.process_bytes(content, "res1.txt", seen)
    seen.add(res1.file_hash)
    assert res1.status == ProcessingStatus.SUCCESS

    res2 = reader.process_bytes(content, "res2.txt", seen)
    assert res2.status == ProcessingStatus.DUPLICATE


def test_unsupported_format():
    reader = DocumentReader()
    res = reader.process_bytes(b"image data", "photo.png")
    assert res.status == ProcessingStatus.UNSUPPORTED_FORMAT


def test_empty_file():
    reader = DocumentReader()
    res = reader.process_bytes(b"", "empty.txt")
    assert res.status == ProcessingStatus.EMPTY_FILE
