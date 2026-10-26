# ResumeDrop — High-Speed AI Resume Extraction & Excel Automation

ResumeDrop is a high-throughput, Python-native automation engine and modern web application that ingests batches of PDF, DOCX, and TXT resumes, extracts structured candidate records using a parallel multi-key Groq LPU pool with rule-based regex fallback, validates the extracted data, and exports a professionally styled 5-worksheet Excel workbook.

---

## ⚡ Key Highlights

- **Multi-Key Groq LPU Engine**: Pools 1 to 3+ Groq API keys with round-robin leasing, concurrent thread workers, and automatic HTTP 429 rate-limit failover with cooldown tracking.
- **Python-Only Document Parsing**: Lightweight, ultra-fast layout-aware extraction via `PyMuPDF` (`fitz`) and `python-docx` without heavy 4 GB+ PyTorch or Docling bloat.
- **Rule-Based Hybrid Parser**: Regex extraction for emails, international phones (+1, +44, +91, Indian 10-digit mobile, UK formats), LinkedIn, GitHub, and portfolios. Works completely offline even without API keys.
- **Data Validation & Sanitization**: Validates graduation years (1950–2035), cleans duplicate degrees, formats names, and neutralizes Excel formula injections (`=`, `+`, `-`, `@`, `\t`, `\r` prefixed with `'`).
- **Apple/Google-Inspired Streamlit UI**: Clean SF Pro typography, zero-pill metric cards, interactive multi-key pool health status, parallel concurrency slider, inline candidate editor, and instant Excel export.
- **Professional 5-Worksheet Excel Output**:
  1. `Candidates` — High-level summary with auto-filter, frozen panes, and status-colored cells.
  2. `Education` — Academic history normalized by degree level and graduation year.
  3. `Work Experience` — Career history with roles, companies, dates, and responsibilities.
  4. `Projects` — Technical and personal projects with technologies.
  5. `Processing Log` — Complete audit log detailing execution status, model used, and character counts.

---

## 🚀 Quick Start

For detailed step-by-step setup on Windows (PowerShell) and Linux (Bash), see the [Complete Setup Guide (SETUP.md)](SETUP.md).

### 1. Installation

```bash
# Clone and enter directory
cd ResumeDrop

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .\.venv\Scripts\Activate.ps1

# Install lightweight dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and insert your Groq API key(s):

```bash
cp .env.example .env
```

```env
# Multi-key pool (1, 2, or 3 keys for high throughput and rate-limit redundancy)
GROQ_API_KEY_1=gsk_your_key_1
GROQ_API_KEY_2=gsk_your_key_2
GROQ_API_KEY_3=gsk_your_key_3

DEFAULT_GROQ_MODEL=llama-3.3-70b-versatile
MAX_WORKERS=4
```

### 3. Launch Web App

```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 💻 CLI Usage

ResumeDrop includes a standalone command-line tool `cli_demo.py` for automated pipelines and DevOps workflows:

```bash
# Preview text extraction from a single resume
python cli_demo.py sample_resumes/alice_chen_resume.pdf --verbose

# Batch process a folder and export directly to a 5-sheet Excel workbook
python cli_demo.py --dir sample_resumes --extract --export output/candidates.xlsx --verbose

# Run with AI extraction enabled
python cli_demo.py --dir sample_resumes --extract --use-ai --export output/candidates.xlsx
```

---

## 🧪 Testing & Quality Assurance

Run the test suite:

```bash
# Run 20 unit and integration tests
pytest

# Run tests with test coverage reporting
pytest --cov=src tests/

# Run speed benchmark
python scripts/benchmark.py

# Run extraction accuracy against 25 ground-truth synthetic resumes
python scripts/evaluate_extraction.py
```

---

## 📁 Repository Structure

```
ResumeDrop/
├── app.py                      # Modern Streamlit UI application
├── cli_demo.py                 # Standalone CLI batch extraction & export tool
├── requirements.txt            # Pinned, tested Python dependencies
├── SETUP.md                    # Windows (PowerShell) and Linux setup manual
├── PROJECT_AUDIT.md            # Comprehensive architecture & engineering audit
├── .env.example                # Multi-key Groq environment template
├── eval_data/
│   └── dataset.py              # 25 synthetic resumes with ground-truth labels
├── pages/
│   └── e.py                    # Extracted text viewer page
├── sample_resumes/             # Sample PDF and DOCX resumes
├── schemas/
│   └── candidate.py            # Canonical Pydantic v2 data models
├── scripts/
│   ├── benchmark.py            # Extraction throughput benchmarking script
│   └── evaluate_extraction.py  # Precision/recall accuracy evaluation script
├── src/
│   ├── ai_extractor.py         # Multi-key GroqKeyPool with failover & LLM parser
│   ├── document_reader.py      # PyMuPDF, python-docx, and MarkItDown text reader
│   ├── excel_exporter.py       # 5-worksheet openpyxl styled Excel builder
│   ├── resume_parser.py        # Rule-based regex parser & parallel batch orchestrator
│   ├── utils.py                # Text normalization, hashing, and signature validation
│   └── validator.py            # Post-extraction validation & formula sanitization
└── tests/                      # Pytest suite (reader, parser, groq pool, excel, app)
```

---

## 🔒 Security

- **Formula Injection Prevention**: Input beginning with `=`, `@`, `+`, `-`, `\t`, or `\r` is escaped with a leading single quote `'` before writing to Excel worksheets.
- **Credential Protection**: API keys are isolated in local environment variables and memory; never hardcoded or logged in outputs.
- **Safe Parsing**: Native Python document readers protect against PDF/DOCX macro execution and external entity expansion.
