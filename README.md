# ResumeDrop — AI Resume Extraction & Excel Automation

ResumeDrop is a 100% Python-native desktop automation suite that ingests batches of PDF, DOCX, and TXT resumes, extracts structured candidate records using a high-throughput multi-key Groq LPU pool (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`) with automatic HTTP 429 failover and rule-based regex fallback, validates the extracted data, and exports a professionally formatted 5-worksheet Excel workbook.

---

## ⚡ Key Highlights

- **Pure Python Architecture**: Built exclusively with Python (no TypeScript/Node.js). Zero npm dependencies.
- **Modern Tkinter Desktop GUI (`gui.py`)**: Native cross-platform desktop application featuring multi-file queueing, real-time progress tracking, candidate review and inline editing, API pool health monitoring, and 1-click Excel export.
- **Multi-Key Groq LPU Pool**: Thread-safe round-robin key manager (`GroqKeyPool`) supporting 1 to 3+ Groq API keys with automatic HTTP 429 rate-limit failover and cooldown tracking.
- **Python-Only Document Parsing**: Layout-aware text extraction via `PyMuPDF` (`fitz`) and `python-docx` without heavy 4 GB+ PyTorch or Docling bloat (~250 MB total environment).
- **Rule-Based Hybrid Fallback**: Regex extraction for emails, international phones (+1, +44, +91, Indian 10-digit mobile, UK formats), LinkedIn, GitHub, and portfolios. Fully functional offline.
- **Data Validation & Sanitization**: Validates graduation years (1950–2035), suppresses duplicate degrees, and neutralizes Excel formula injections (`=`, `+`, `-`, `@`, `\t`, `\r` prefixed with `'`).
- **Professional 5-Worksheet Excel Output**:
  1. `Candidates` — Summary row per candidate with formatted headers, auto-filter, and color-coded status cells.
  2. `Education` — Academic history normalized by degree level and graduation year.
  3. `Work Experience` — Career history with roles, companies, dates, and responsibilities.
  4. `Projects` — Technical and personal projects with technologies.
  5. `Processing Log` — Complete audit trail detailing execution status, model used, and character counts.

---

## 🚀 Quick Start

For detailed step-by-step setup on Windows (PowerShell) and Linux (Bash), see the [Complete Setup Guide (SETUP.md)](SETUP.md).

### 1. Installation

```bash
# Clone repository
git clone https://github.com/anuragrathod/ResumeDrop.git
cd ResumeDrop

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .\.venv\Scripts\Activate.ps1

# Install lightweight dependencies
pip install -r requirements.txt
```

> **Linux Tkinter Note**: On Debian/Ubuntu systems, if Tkinter is not already installed, run `sudo apt install python3-tk`. On Windows and macOS, Tkinter is included automatically with Python.

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

### 3. Launch Desktop GUI

```bash
python gui.py
```

### 4. Or Run CLI Batch Tool

```bash
# Extract sample resumes and export directly to 5-sheet Excel workbook:
python cli_demo.py --dir sample_resumes --extract --export output/candidates.xlsx --verbose
```

---

## 💻 Desktop GUI & CLI Features

### Desktop GUI (`gui.py`)
- **Batch Queue**: Drag or add multiple resume files or entire directories.
- **Worker Concurrency**: Select background worker thread count (1–8) and target Groq model.
- **Interactive Review**: Double-click any candidate in the Treeview table to inspect validation issues, review raw document snippets, and edit fields prior to export.
- **Excel Export**: Save structured workbooks anywhere on your filesystem.

### CLI Batch Tool (`cli_demo.py`)
- Automated command-line extraction for headless environments and CI/CD pipelines:
  ```bash
  python cli_demo.py [files...] [--dir DIR] [--extract] [--export FILE.xlsx] [--use-ai] [--verbose]
  ```

---

## 🧪 Testing & Quality Assurance

Run the automated test suite:

```bash
# Run 20 unit and integration tests
pytest

# Run tests with code coverage
pytest --cov=src tests/

# Run extraction throughput benchmark (>900 resumes/sec)
python scripts/benchmark.py

# Run accuracy evaluation against 25 ground-truth synthetic resumes
python scripts/evaluate_extraction.py
```

---

## 📁 Repository Structure

```
ResumeDrop/
├── gui.py                      # Pure Python Tkinter modern desktop GUI application
├── cli_demo.py                 # Standalone CLI batch extraction & export tool
├── app.py                      # Streamlit web application
├── requirements.txt            # Pinned, tested Python dependencies
├── SETUP.md                    # Windows (PowerShell) and Linux setup manual
├── PROJECT_AUDIT.md            # Comprehensive architecture & engineering audit
├── .env.example                # Multi-key Groq environment template
├── .gitignore                  # Pure Python ignore rules
├── eval_data/
│   └── dataset.py              # 25 synthetic resumes with ground-truth labels
├── sample_resumes/             # Sample PDF and DOCX test resumes
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

- **Formula Injection Prevention**: Cell contents starting with `=`, `@`, `+`, `-`, `\t`, or `\r` are safely escaped with a leading single quote `'`.
- **Zero Credential Leakage**: API keys reside solely in environment variables and are never exported to workbooks or logs.
- **Safe Document Ingestion**: Native Python readers prevent macro execution, shell spawning, and external entity resolution.
