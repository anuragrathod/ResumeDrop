# ResumeDrop — Python Project Audit, Setup Repair, UI Modernization & Parallel AI Architecture

A comprehensive plan to restore the native Python architecture of **ResumeDrop**, resolve environment and dependency conflicts, implement high-speed multi-key Groq extraction with rate-limit failover and parallel batch processing, modernize the Streamlit user experience, and deliver enterprise-grade setup guides and audit reports.

---

## User Review & Critical Decisions

> [!IMPORTANT]
> The following architectural decisions were confirmed based on user direction:
> - **Repository Scope**: Restore and focus exclusively on the Python application (`app.py`, `cli_demo.py`, `src/`, `schemas/`, `tests/`, `scripts/`).
> - **Document Parsing Strategy**: Best-in-class Python-native parsing using `PyMuPDF` (and `pymupdf4llm`), `python-docx`, `markitdown`, and `openpyxl`. Eliminates heavyweight Torch/CUDA dependencies while providing sub-second text extraction, table layout preservation, and scanned PDF detection.
> - **AI Extraction Engine**: Groq Cloud LPU engine enhanced with a **Multi-Key Client Pool** supporting multiple API keys (`GROQ_API_KEYS` or numbered `GROQ_API_KEY_1`, `_2`, `_3`), automatic round-robin load distribution, parallel worker execution (`ThreadPoolExecutor`), and instant failover on HTTP 429 rate limits.

---

## 1. Overview & Core Concept

**ResumeDrop** is a resume-to-Excel automation system that converts batches of PDF, DOCX, and TXT resumes into a validated, 5-worksheet `.xlsx` workbook.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ResumeDrop Pipeline                             │
└────────────────────────────────────────────────────────────────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   Multi-File Upload                         Duplicate Hash Filter
  (PDF / DOCX / TXT)                        (SHA-256 byte hashing)
            │                                         │
            └────────────────────┬────────────────────┘
                                 ▼
                     Document Reader (Python)
          ┌──────────────────────────────────────────────┐
          │ PyMuPDF (fitz) + python-docx + markitdown    │
          │ Fallback: Scanned PDF / Password Detection   │
          └──────────────────────────────────────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   Rule-Based Extractors                     Multi-Key Groq Pool
   - RFC-5321 Email Regex                    - 2 to 3+ API Keys
   - Global Phone Patterns                   - Round-Robin / Concurrency
   - LinkedIn, GitHub, Portfolio             - Instant 429 Rate-Limit Fallback
   - Name & Location Heuristics              - Models: gpt-oss-120b, 20b
            │                                         │
            └────────────────────┬────────────────────┘
                                 ▼
                    Orchestrator & Merge Engine
          ┌──────────────────────────────────────────────┐
          │ Strict field precedence & normalizations    │
          │ Pydantic v2 validation (CandidateRecord)     │
          │ Formula-injection sanitization (' prefix)    │
          └──────────────────────────────────────────────┘
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   Modern Streamlit UI                       5-Worksheet Excel Export
   - Apple SF Pro / Dark/Light               - 1. Candidates (Summary)
   - Real-time Multi-key Status              - 2. Education (All degrees)
   - Inline Candidate Editor                 - 3. Work Experience (Jobs)
   - Live Progress & Metrics                 - 4. Projects (Tech stack)
   - Extracted Text View (/e)                - 5. Audit Processing Log
```

---

## 2. User Experience & Visual Design

Following the **Universal Frontend Design Constitution** and **SaaS & Dashboard Guidelines**:

- **Visual Theme & Typography**:
  - Restrained Apple-inspired aesthetic with system font typography (`-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto`).
  - Strict **zero-pill discipline**: metadata (timestamps, file sizes, counts, categories) is displayed as clean unboxed text with subtle typographic separators (`·`, `/`).
  - Single-elevation card depth with delicate 1px borders (`rgba(0, 0, 0, 0.08)` / dark mode equivalent).
  - High-density metrics with tabular figures (`font-variant-numeric: tabular-nums`).
- **Interactive Controls**:
  - Drag-and-drop zone with clear hover states and duplicate warnings.
  - Sidebar multi-key manager: displays loaded Groq API keys, active key rotation status, and real-time rate limit health.
  - Batch progress bar with per-file status messages (`✓ candidate.pdf → Verified` or `✗ resume.pdf → Corrupt`).
  - Inline candidate review accordions with direct field inputs for name, email, phone, location, education, skills, experience, projects, and links.
  - Dedicated **Extracted Text Viewer** (`pages/e.py`) to inspect raw text extracted from any resume.
  - Built-in **Accuracy Benchmark** tab/page running evaluation against synthetic test resumes.

---

## 3. Key Technical Decisions & Architecture

### A. Multi-Key Groq Rotation & Parallel Concurrency
- **Problem**: Individual Groq free-tier keys have per-minute request (RPM) and token (TPM) limits that can trigger HTTP 429 when processing large batches of resumes.
- **Solution**: Implement `GroqKeyPool` in `src/ai_extractor.py`:
  - Parses multiple keys from environment (`GROQ_API_KEY`, `GROQ_API_KEYS`, `GROQ_API_KEY_1`, `_2`, `_3`) or the UI sidebar.
  - Uses a round-robin rotation for concurrent requests.
  - Thread-safe key leasing with exponential backoff on 429: if Key 1 hits a rate limit, the request automatically retries immediately on Key 2 without user intervention.
  - Concurrent batch processing using `concurrent.futures.ThreadPoolExecutor` (e.g. 2–4 workers) while preserving progress bar updates in Streamlit.

### B. Python-Native Document Reader Stack
- **Problem**: Heavyweight dependencies like Docling/PyTorch create massive downloads (>2 GB), installation failures on Windows/macOS, and Python 3.12 wheel conflicts.
- **Solution**:
  - Primary PDF engine: `PyMuPDF` (`fitz`) and `markitdown` for fast, structured text extraction.
  - DOCX engine: `python-docx` for structured paragraph and table text extraction.
  - Scanned PDF detection: flags documents with low character counts as image-only.
  - Encrypted / password-protected document detection: gracefully isolates locked documents without crashing the batch.

### C. Enterprise Excel Export (`openpyxl`)
- Five dedicated worksheets:
  1. `Candidates`: One row per resume with highest education, all skills, contact links, and color-coded status cells (`#C6EFCE` green for verified, `#FFEB9C` amber for review_required, `#FFC7CE` red for failed).
  2. `Education`: One row per degree record.
  3. `Work Experience`: One row per job with AI one-line summary and bulleted responsibilities.
  4. `Projects`: One row per project with technology tags.
  5. `Processing Log`: Audit sheet logging all files, character counts, status, and error details.
- Frozen header panes (`A2`), auto-filter across all columns, formula-injection sanitization (`'` prefix on `=`, `+`, `-`, `@`).

---

## 4. Prioritized Execution Phases

```
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Repository Baseline & Architecture Restore                   │
├────────────────────────────────────────────────────────────────────────┤
│ • Restore Python directory layout (schemas, src, pages, scripts, tests)│
│ • Establish clean requirements.txt with tested version pins            │
│ • Create .env.example with multi-key Groq template                     │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 2: Document Reader & Multi-Key Groq AI Engine                    │
├────────────────────────────────────────────────────────────────────────┤
│ • Implement PyMuPDF + python-docx reader in src/document_reader.py     │
│ • Implement GroqKeyPool with round-robin & 429 failover                │
│ • Implement parallel batch extractor in src/resume_parser.py           │
│ • Implement Pydantic v2 schemas in schemas/candidate.py                │
│ • Implement validator & formula sanitizer in src/validator.py          │
│ • Implement openpyxl 5-sheet workbook exporter in src/excel_exporter.py│
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 3: Modernized Streamlit UI & Pages                               │
├────────────────────────────────────────────────────────────────────────┤
│ • Modernize app.py with Apple-inspired theme, zero-pill discipline     │
│ • Implement live progress, metrics, candidate editor & download buttons│
│ • Re-create pages/e.py for raw text inspection                         │
│ • Update cli_demo.py for CLI batch processing                          │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 4: Test Suite & Benchmark Evaluation                             │
├────────────────────────────────────────────────────────────────────────┤
│ • Run pytest across all test suites (document_reader, phase2, excel)   │
│ • Implement synthetic evaluation script in scripts/evaluate_extraction │
│ • Verify accuracy gates and performance benchmarks                     │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 5: Documentation & Audit Deliverables                            │
├────────────────────────────────────────────────────────────────────────┤
│ • Create SETUP.md with verified Windows (PowerShell) and Linux guides  │
│ • Update README.md with quick-start and architecture documentation     │
│ • Create PROJECT_AUDIT.md detailing findings, fixes, and performance   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Verification Plan

1. **Dependency Installation**: Verify `pip install -r requirements.txt` succeeds cleanly in a standard Python virtual environment without conflicts.
2. **Automated Testing**: Run `pytest tests/ -v` to ensure 100% of unit tests pass (document reader, schemas, rule extractors, validator, and Excel exporter).
3. **Multi-Key Groq Verification**: Test API key rotation with rate-limit simulation and parallel batch execution.
4. **Excel Integrity**: Verify exported `.xlsx` workbook opens cleanly with all 5 sheets, formatting, filters, and formula sanitization.
5. **Streamlit App Launch**: Verify `streamlit run app.py` starts without warnings and renders the modernized UI on port 3000.
6. **Extracted Text Viewer**: Test `pages/e.py` with sample resumes.
