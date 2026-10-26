"""
src/document_reader.py
======================
Phase 1 document reader for the ResumeDrop automation system.

Responsibilities:
- Accept one or more PDF, DOCX, or TXT file paths or bytes.
- Validate each file (size, signature, emptiness, batch duplicates).
- Extract text via PyMuPDF (fitz) for PDF, python-docx for DOCX, with MarkItDown fallback.
- Detect scanned PDFs and password-protected files with clear status codes.
- Normalize extracted text and return a structured DocumentResult.
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable

from src.utils import (
    MAX_FILE_SIZE_BYTES,
    SUPPORTED_EXTENSIONS,
    clean_text,
    compute_sha256,
    is_supported_file,
    is_text_empty,
)

logger = logging.getLogger(__name__)


class ProcessingStatus(str, Enum):
    """Possible outcomes for a single file."""

    SUCCESS = "success"
    EMPTY = "empty"  # File existed but contained no usable text (scanned PDF / graphics)
    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    EMPTY_FILE = "empty_file"  # Zero-byte file
    DUPLICATE = "duplicate"  # Content hash already seen in this batch
    CORRUPT = "corrupt"  # File could not be parsed
    PASSWORD_PROTECTED = "password_protected"
    ERROR = "error"  # Unexpected runtime error


@dataclass
class DocumentResult:
    """The result of processing a single document."""

    filename: str
    status: ProcessingStatus
    text: str = ""
    error: str = ""
    file_hash: str = ""
    char_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)

    @property
    def succeeded(self) -> bool:
        return self.status == ProcessingStatus.SUCCESS

    @property
    def extracted_text(self) -> str:
        return self.text


class DocumentReader:
    """Extracts text from PDF, DOCX, and TXT files using Python-native libraries."""

    def __init__(
        self,
        max_file_size: int = MAX_FILE_SIZE_BYTES,
        min_text_chars: int = 50,
    ) -> None:
        self._max_file_size = max_file_size
        self._min_text_chars = min_text_chars

    def process_files(self, file_paths: Iterable[str | Path]) -> list[DocumentResult]:
        """Process multiple files sequentially with batch duplicate detection."""
        results: list[DocumentResult] = []
        seen_hashes: set[str] = set()

        for raw_path in file_paths:
            path = Path(raw_path)
            result = self._process_single(path, seen_hashes)
            if result.file_hash:
                seen_hashes.add(result.file_hash)
            results.append(result)

        return results

    def process_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        seen_hashes: set[str] | None = None,
    ) -> DocumentResult:
        """Process raw uploaded bytes from web UI without retaining temp files."""
        if seen_hashes is None:
            seen_hashes = set()

        suffix = Path(filename).suffix.lower()
        tmp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            return self._process_single(Path(tmp_path), seen_hashes, display_name=filename)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def _process_single(
        self,
        path: Path,
        seen_hashes: set[str],
        display_name: str | None = None,
    ) -> DocumentResult:
        filename = display_name or path.name

        if not path.exists():
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.ERROR,
                error=f"File not found: {path}",
            )

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.UNSUPPORTED_FORMAT,
                error=f"Unsupported file type '{suffix}'. Accepted formats: PDF, DOCX, TXT.",
            )

        try:
            file_size = path.stat().st_size
        except OSError as exc:
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.ERROR,
                error=f"Cannot read file metadata: {exc}",
            )

        if file_size == 0:
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.EMPTY_FILE,
                error="File is empty (0 bytes).",
            )

        if file_size > self._max_file_size:
            limit_mb = self._max_file_size / (1024 * 1024)
            size_mb = file_size / (1024 * 1024)
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.FILE_TOO_LARGE,
                error=f"File is {size_mb:.1f} MB; the limit is {limit_mb:.0f} MB.",
            )

        try:
            file_hash = compute_sha256(path)
        except OSError:
            file_hash = ""

        if file_hash and file_hash in seen_hashes:
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.DUPLICATE,
                error="A file with identical content has already been processed in this batch.",
                file_hash=file_hash,
            )

        # Extract text
        raw_text, extraction_error = self._extract_text(path)

        if extraction_error:
            if "password" in extraction_error.lower() or "encrypt" in extraction_error.lower():
                return DocumentResult(
                    filename=filename,
                    status=ProcessingStatus.PASSWORD_PROTECTED,
                    error=extraction_error,
                    file_hash=file_hash,
                )
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.CORRUPT,
                error=extraction_error,
                file_hash=file_hash,
            )

        cleaned = clean_text(raw_text)

        if is_text_empty(cleaned, self._min_text_chars):
            return DocumentResult(
                filename=filename,
                status=ProcessingStatus.EMPTY,
                error="No readable text could be extracted. The file may be a scanned image or contain only graphics.",
                file_hash=file_hash,
                text=cleaned,
            )

        return DocumentResult(
            filename=filename,
            status=ProcessingStatus.SUCCESS,
            text=cleaned,
            file_hash=file_hash,
        )

    def _extract_text(self, path: Path) -> tuple[str, str]:
        """Extract text with Python-native engines (PyMuPDF, python-docx, markitdown)."""
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return self._extract_pdf(path)
        elif suffix == ".docx":
            return self._extract_docx(path)
        elif suffix == ".txt":
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
                return text, ""
            except Exception as exc:
                return "", f"Failed to read text file: {exc}"

        return "", f"Unsupported file extension: {suffix}"

    @staticmethod
    def _extract_pdf(path: Path) -> tuple[str, str]:
        """Extract PDF text using PyMuPDF (fitz) with layout preservation and password check."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(path))
            if getattr(doc, "needs_pass", False) or getattr(doc, "is_encrypted", False):
                doc.close()
                return "", "PDF is password-protected or encrypted."

            pages: list[str] = []
            for page in doc:
                text = page.get_text()
                if text:
                    pages.append(text)
            doc.close()

            full_text = "\n\n".join(pages)
            return full_text, ""
        except Exception as exc:
            err_str = str(exc).lower()
            if "password" in err_str or "encrypt" in err_str:
                return "", f"PDF is password-protected: {exc}"
            # Fallback to markitdown if available
            try:
                from markitdown import MarkItDown

                md = MarkItDown()
                result = md.convert(str(path))
                return result.text_content or "", ""
            except Exception:
                return "", f"PDF extraction failed: {exc}"

    @staticmethod
    def _extract_docx(path: Path) -> tuple[str, str]:
        """Extract DOCX text using python-docx (paragraphs and tables)."""
        try:
            import docx

            doc = docx.Document(str(path))
            lines: list[str] = []

            for p in doc.paragraphs:
                if p.text.strip():
                    lines.append(p.text.strip())

            for table in doc.tables:
                for row in table.rows:
                    row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    if row_cells:
                        lines.append(" | ".join(row_cells))

            full_text = "\n".join(lines)
            if full_text.strip():
                return full_text, ""

            # Fallback to markitdown
            from markitdown import MarkItDown

            md = MarkItDown()
            result = md.convert(str(path))
            return result.text_content or "", ""
        except Exception as exc:
            try:
                from markitdown import MarkItDown

                md = MarkItDown()
                result = md.convert(str(path))
                return result.text_content or "", ""
            except Exception:
                return "", f"DOCX extraction failed: {exc}"
