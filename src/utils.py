"""
src/utils.py
============
Utility functions for hashing, file validation, and text normalization.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

# Maximum file size accepted by the application (10 MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Set of lowercased file extensions that the application supports
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

# Magic byte signatures for supported file types
_MAGIC_BYTES: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".docx": [b"PK\x03\x04"],  # ZIP archive header used by DOCX
}


def compute_sha256(data_or_path: bytes | str | Path) -> str:
    """Compute the SHA-256 hexadecimal hash of bytes or a file on disk."""
    hasher = hashlib.sha256()
    if isinstance(data_or_path, (str, Path)):
        p = Path(data_or_path)
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
    else:
        hasher.update(data_or_path)
    return hasher.hexdigest()


def detect_file_type(data_or_path: bytes | str | Path) -> str | None:
    """Detect file type from leading magic bytes."""
    header: bytes
    if isinstance(data_or_path, (str, Path)):
        p = Path(data_or_path)
        with open(p, "rb") as f:
            header = f.read(16)
    else:
        header = data_or_path[:16]

    for ext, signatures in _MAGIC_BYTES.items():
        for sig in signatures:
            if header.startswith(sig):
                return ext
    return None


def is_supported_file(data_or_path: bytes | str | Path, declared_ext: str | None = None) -> bool:
    """Return True if the file extension or signature matches supported types."""
    if isinstance(data_or_path, (str, Path)):
        ext = Path(data_or_path).suffix.lower()
        if ext == ".txt":
            return True
        detected = detect_file_type(data_or_path)
        return detected == ext if detected else ext in SUPPORTED_EXTENSIONS
    if declared_ext:
        if declared_ext.lower() == ".txt":
            return True
        detected = detect_file_type(data_or_path)
        return detected == declared_ext.lower()
    return detect_file_type(data_or_path) in SUPPORTED_EXTENSIONS


def clean_text(raw_text: str) -> str:
    """Normalize extracted text: replace control characters, normalize linebreaks and spaces."""
    if not raw_text:
        return ""
    # Normalize Windows and Mac line endings
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace non-breaking and unusual spaces with standard space
    text = re.sub(r"[\u00A0\u1680\u2000-\u200B\u202F\u205F\u3000]", " ", text)
    # Remove control characters except tab, newline
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    # Collapse multiple consecutive horizontal spaces
    text = re.sub(r"[ \t]+", " ", text)
    # Collapse 3 or more newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_text_empty(text: str, min_chars: int = 50) -> bool:
    """Return True if text has fewer than min_chars non-whitespace characters."""
    stripped = "".join(text.split())
    return len(stripped) < min_chars
