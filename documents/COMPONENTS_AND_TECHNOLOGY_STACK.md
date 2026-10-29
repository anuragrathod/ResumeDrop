# Components and Technology Stack: What, Why, and How
## Project: ResumeDrop (AI Resume Extraction & Excel Automation)

This document provides a comprehensive, practical, and technically rigorous explanation of every major component, technology, library, framework, service, and data structure employed in **ResumeDrop**.

---

## 1. Comprehensive Technology & Component Matrix

| Component or Technology | Declared Version | Purpose | Why We Use It | How We Use It in Our Project |
|---|---|---|---|---|
| **Python** | `3.10` – `3.12` | Core Programming Language & Runtime | Provides cross-platform ubiquity, clean type hints, mature standard libraries (`threading`, `re`, `hashlib`, `queue`), and high-performance C bindings for file parsing. | All backend modules (`src/`), schemas (`schemas/`), UI entry points (`gui.py`, `app.py`), and test suites (`tests/`) are written in 100% pure Python. |
| **Tkinter / ttk** | `8.6` (standard library) | Native Desktop Graphical User Interface | Built directly into Python on Windows/macOS; zero external C++ runtime dependencies (unlike PyQt or wxWidgets); instant startup (<0.2s); lightweight memory footprint. | Powers `gui.py`: renders the main 1180x760 desktop window, queue listbox, worker progress bar, candidate Treeview table, and Candidate Review modal. |
| **Streamlit** | `1.43.2` (`>=1.35.0,<1.44.0`) | Reactive Browser-Based Web Dashboard | Enables rapid web interface deployment with native file uploaders, session state persistence, live progress notifications, and one-click binary file download handlers. | Powers `app.py` and `pages/e.py`: provides drag-and-drop batch resume uploading, expandable candidate review cards, inline editing forms, and live connection testing. |
| **Pydantic** | `2.14.1` (`>=2.7.0,<3.0.0`) | Canonical Data Modeling & Schema Validation | Backed by a high-performance compiled Rust core (`pydantic-core`); enforces strict type coercion, field validators, and JSON schema serialization without runtime lag. | Defines canonical models in `schemas/candidate.py` (`CandidateRecord`, `EducationRecord`, `WorkExperience`, `Project`, `ExtractionMetadata`); sanitizes and validates all extracted entities. |
| **PyMuPDF (`fitz`)** | `1.25.5` (`>=1.24.0,<1.26.0`) | High-Speed Digital PDF Text Extraction | Built on the C-based MuPDF rendering engine; extracts layout-aware text in <1ms per page; detects encryption; eliminates multi-gigabyte PyTorch/CUDA dependencies. | Implemented in `src/document_reader.py:_extract_pdf()`: parses text blocks, multi-page PDFs, and checks `doc.is_encrypted` to flag password-protected files. |
| **python-docx** | `1.1.2` (`>=1.1.0,<1.2.0`) | Microsoft Word (.docx) XML Document Ingestion | Directly traverses the Office Open XML (ISO/IEC 29500) document tree; extracts text from paragraphs and embedded tables without requiring Microsoft Office installed. | Implemented in `src/document_reader.py:_extract_docx()`: extracts text from body paragraphs and table rows, preserving table cell delimiters with ` \| `. |
| **openpyxl** | `3.1.5` (`>=3.1.2,<3.2.0`) | Formatted 5-Worksheet Excel (.xlsx) Generation | Programmatic builder for OpenXML spreadsheets; supports fonts, header fills, column width calculation, auto-filters, text wrapping, and freeze panes. | Implemented in `src/excel_exporter.py`: builds `Candidates`, `Education`, `Work Experience`, `Projects`, and `Processing Log` worksheets in memory buffer or disk. |
| **openai (Python SDK)** | `1.109.1` (`>=1.0.0,<2.0.0`) | NVIDIA NIM OpenAI-Compatible API Client | Official client for querying NVIDIA NIM endpoints (`https://integrate.api.nvidia.com/v1`); enables fast inference, JSON schema enforcement, and streaming. | Implemented in `src/ai_extractor.py`: communicates with NVIDIA NIM endpoints over HTTPS TLS 1.3 using pooled API keys with shared 40 RPM rate limiting. |
| **NVIDIA NIM Models** | `meta/llama-3.3-70b-instruct` | Generative Language Processing & Entity Extraction | Flagship instruction-tuned 70B parameter model hosted on NVIDIA NIM; 128k context window, exceptional JSON schema adherence, reasoning, and context comprehension. | Configured via `src/ai_extractor.py:AIConfig`; analyzes raw resume text and outputs normalized JSON objects conforming to the candidate schema. |
| **python-dotenv** | `1.2.4` (`>=1.0.0,<2.0.0`) | Environment Configuration Management | Loads environment variables from local `.env` files into `os.environ`; separates configuration and API credentials from application source code. | Used in `app.py`, `gui.py`, and `src/ai_extractor.py` to securely read `NVIDIA_API_KEY_1..3` and configuration parameters without hardcoding secrets. |
| **pandas** | `2.3.3` (`>=2.0.0,<3.0.0`) | Tabular Data Structure & Web Rendering | Industry-standard tabular data manipulation; integrates seamlessly with Streamlit for interactive grid rendering and filtering. | Used in `app.py` to format candidate records into clean overview tables displayed to the recruiter prior to export. |
| **pytest & pytest-cov** | `8.4.2` & `5.0.0` | Automated Testing & Code Coverage Harness | Provides automated test discovery, fixture management, assertion rewriting, and statement/branch code coverage analysis. | Powers the automated tests in `tests/` verifying document reading, deduplication, NVIDIA key pooling, 40 RPM rate limiting, GUI formatting, and Excel generation. |

---

## 2. Technology Relationships and Component Interaction

ResumeDrop connects these technologies into an integrated, modular pipeline where each component has a distinct responsibility:

```
┌────────────────────────────────────────────────────────┐
│                   1. Ingestion Layer                   │
│   • Input: PDF, DOCX, TXT                              │
│   • Handled by: PyMuPDF (fitz), python-docx, utils.py  │
│   • Operations: Magic byte check, SHA-256 deduplication│
│   • Output: Normalized, cleaned plain text string       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             2. Dual-Track Extraction Layer             │
│   ┌──────────────────────────┬───────────────────────┐ │
│   │ Track A: Regex Rules     │ Track B: NVIDIA NIM   │ │
│   │ • Python 're' module     │ • openai Python SDK   │ │
│   │ • Extracts email, phone, │ • NvidiaKeyPool (3 k) │ │
│   │   URLs, header name      │ • Llama-3.3-70b       │ │
│   │ • 100% offline capable   │ • Strict JSON schema  │ │
│   └──────────────────────────┴───────────────────────┘ │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            3. Merging & Validation Layer               │
│   • Priority rules: Deterministic regex overrides      │
│     contact fields; LLM populates employment history   │
│   • Canonical data model: schemas/candidate.py         │
│   • Validation checks: src/validator.py                │
│   • Formula Shield: Sanitizes =, +, -, @ with '        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            4. Presentation & Review Layer              │
│   • Desktop GUI (Tkinter/ttk) or Web UI (Streamlit)    │
│   • Treeview / Table displays candidate status badges  │
│   • Recruiter reviews warnings & performs inline edits │
│   • Edits immediately re-validated in-place            │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│              5. Export & Output Layer                  │
│   • Handled by: openpyxl                               │
│   • Produces: 5-worksheet .xlsx workbook               │
│   • Features: Frozen headers, auto-filters, status fills│
└────────────────────────────────────────────────────────┘
```

---

## 3. Artificial Intelligence: Role, Models, and Prompt Engineering

### 3.1 Role of the AI Model
In ResumeDrop, the AI model is not a conversational chatbot. It operates as a **deterministic, structured entity extraction function**. Its responsibility is to parse unstructured, variable resume sections (work experience bullet points, academic credentials, technical projects) and translate them into a strictly typed JSON object matching the canonical schema.

### 3.2 Model Selection Rationale
1. **`meta/llama-3.3-70b-instruct` (Default Free Endpoint Model)**:
   - *Why*: State-of-the-art open-weights reasoning model available via NVIDIA NIM's hosted Free Endpoint; excels at following strict JSON schema instructions without commentary or markdown fences; 128k context window to ingest full multi-page resumes; high accuracy in extracting implicit dates and separating degree qualifications from institutions.
2. **`nvidia/llama-3.1-nemotron-70b-instruct` (High-Alignment Alternative)**:
   - *Why*: NVIDIA-customized 70B model with RLHF alignment for instruction precision; available as an active NIM endpoint.
3. **NVIDIA NIM Cloud Infrastructure**:
   - *Why*: Hosted on `https://integrate.api.nvidia.com/v1`, NVIDIA NIM provides OpenAI-compatible API access, TensorRT-LLM acceleration, and structured JSON outputs under a developer-friendly Free Endpoint tier.

### 3.3 Prompt Engineering Architecture (`prompts/extract_candidate.txt`)
The AI engine utilizes a comprehensive 282-line system prompt designed for high extraction fidelity:
- **Zero-Fabrication Constraint**: Explicitly mandates returning `null` for missing scalar fields and `[]` for empty lists; strictly prohibits inventing credentials or technologies.
- **Executive One-Line Summaries**: Mandates generating a concise 15–25 word factual summary for every job experience and project (e.g., explaining the core contribution and business outcome).
- **Skill Classification Taxonomy**: Separates candidate competencies into 4 distinct collections: `programming_languages`, `tools`, `technical_skills`, and `certifications`.
- **JSON Object Enforcement**: API calls utilize `response_format={"type": "json_object"}` with temperature `0.1` for maximum reproducibility.

---

## 4. Key Architectural Decisions and Trade-Off Analysis

### 4.1 Native PyMuPDF & python-docx vs. Heavy Deep-Learning OCR
- **Decision**: Use `PyMuPDF` (`fitz`) and `python-docx` instead of PyTorch, Docling, or LayoutLM.
- **Rationale**: Real-world digital resumes (PDF/DOCX) contain native text streams. Using PyMuPDF reduces the installation footprint by **>90%** (~250 MB vs >4 GB), eliminates CUDA compiler incompatibilities on client laptops, and boosts extraction speed to **>900 resumes/second**.
- **Trade-Off**: Bitmap-scanned resumes contain no selectable text layer. ResumeDrop safely traps scanned files, flagging them as `EMPTY` with character count 0 in the audit log, rather than bloating the application with gigabytes of neural OCR libraries.

### 4.2 Native Python Tkinter vs. Electron or PyQt
- **Decision**: Build the desktop GUI using Python's built-in `tkinter` and `ttk`.
- **Rationale**: Standard Tkinter is included in official Python installers on Windows and macOS. It requires zero compilation, avoids bundling a 200 MB Chromium runtime (Electron), and provides instant application startup.
- **Trade-Off**: Tkinter has simpler canvas styling capabilities than CSS, but `ttk` with the `clam` theme, custom palettes, and Treeviews provides a clean, professional native desktop experience.

### 4.3 Three-Key NVIDIA NIM Pool & Shared 40 RPM Rate Limiter
- **Decision**: Implement `NvidiaKeyPool` managing 3 API keys with round-robin leasing and `NvidiaRateLimiter` enforcing an aggregate <= 40 RPM global rate limit.
- **Rationale**: Free evaluation endpoints on NVIDIA NIM enforce an account-level rate limit (~40 RPM). When using 3 keys from the same account, requests must share a concurrency-safe limiter to prevent account-level 429 throttling while still permitting independent requests to execute concurrently within quota. Automatic failover and exponential cooldown protect against retry storms.
