# ResumeDrop — AI Resume Extraction & Excel Automation

ResumeDrop is a 100% Python-native desktop automation suite that ingests batches of PDF, DOCX, and TXT resumes, extracts structured candidate records using a high-throughput multi-key NVIDIA NIM pool (`meta/llama-3.3-70b-instruct`) with automatic HTTP 429 failover, shared 40 RPM rate limiting, and rule-based regex fallback, validates the extracted data, and exports a professionally formatted 5-worksheet Excel workbook.

---

## ⚡ Key Highlights

- **Pure Python Architecture**: Built exclusively with Python (no TypeScript/Node.js). Zero npm dependencies.
- **Modern Tkinter Desktop GUI (`gui.py`)**: Native cross-platform desktop application featuring multi-file queueing, real-time progress tracking, candidate review and inline editing, API pool health monitoring, and 1-click Excel export.
- **Multi-Key NVIDIA NIM Pool**: Thread-safe key manager (`NvidiaKeyPool`) supporting 3 NVIDIA API keys belonging to the same account with automatic load distribution and failover.
- **Shared Concurrency-Safe Rate Limiter**: Strictly enforces a global budget of up to 40 requests per rolling minute across all 3 keys combined, preventing account-wide throttling and retry storms.
- **OpenAI-Compatible NVIDIA NIM Endpoint**: Powered by `https://integrate.api.nvidia.com/v1` using official Free Endpoint models like `meta/llama-3.3-70b-instruct` (128k context length, high-accuracy structured JSON output).
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

Copy `.env.example` to `.env` and configure your 3 NVIDIA API keys:

```bash
cp .env.example .env
```

```env
# 3 NVIDIA API keys from the same account (https://build.nvidia.com/)
NVIDIA_API_KEY_1=nvapi-your_first_key_here
NVIDIA_API_KEY_2=nvapi-your_second_key_here
NVIDIA_API_KEY_3=nvapi-your_third_key_here

# Selected model and rate limit
DEFAULT_NVIDIA_MODEL=meta/llama-3.3-70b-instruct
NVIDIA_RATE_LIMIT_RPM=40
MAX_WORKERS=3
```

### 3. Launch Desktop GUI or Web App

```bash
# Launch Tkinter Desktop GUI:
python gui.py

# Or launch Streamlit web application:
bash run_dev.sh
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
- **Worker Concurrency**: Select background worker thread count (1–8) and target NVIDIA model.
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
# Run unit and integration tests
pytest

# Run tests with code coverage
pytest --cov=src tests/

# Run extraction throughput benchmark (>800 resumes/sec)
python scripts/benchmark.py

# Run accuracy evaluation against synthetic resumes
python scripts/evaluate_extraction.py
```

---

## 📁 Repository Structure

```
ResumeDrop/
├── gui.py                      # Pure Python Tkinter modern desktop GUI application
├── cli_demo.py                 # Standalone CLI batch extraction & export tool
├── app.py                      # Streamlit web application
├── requirements.txt            # Pinned, tested Python dependencies (openai, pydantic, pymupdf, etc.)
├── SETUP.md                    # Windows (PowerShell) and Linux setup manual
├── PROJECT_AUDIT.md            # Comprehensive architecture & engineering audit
├── .env.example                # 3-key NVIDIA NIM environment template
├── .gitignore                  # Pure Python ignore rules
├── eval_data/
│   └── dataset.py              # Synthetic resumes with ground-truth labels
├── sample_resumes/             # Sample PDF and DOCX test resumes
├── schemas/
│   └── candidate.py            # Canonical Pydantic v2 data models
├── scripts/
│   ├── benchmark.py            # Extraction throughput benchmarking script
│   └── evaluate_extraction.py  # Precision/recall accuracy evaluation script
├── src/
│   ├── ai_extractor.py         # Multi-key NvidiaKeyPool with shared 40 RPM rate limiter & NIM parser
│   ├── document_reader.py      # PyMuPDF, python-docx, and MarkItDown text reader
│   ├── excel_exporter.py       # 5-worksheet openpyxl styled Excel builder
│   ├── resume_parser.py        # Rule-based regex parser & parallel batch orchestrator
│   ├── utils.py                # Text normalization, hashing, and signature validation
│   └── validator.py            # Post-extraction validation & formula sanitization
└── tests/                      # Pytest suite (reader, parser, nvidia pool, excel, app)
```

---

## 🔒 Security

- **Formula Injection Prevention**: Cell contents starting with `=`, `@`, `+`, `-`, `\t`, or `\r` are safely escaped with a leading single quote `'`.
- **Zero Credential Leakage**: API keys reside solely in environment variables, are masked as `nvapi-***` in logs, and are never exported to workbooks.
- **Safe Document Ingestion**: Native Python readers prevent macro execution, shell spawning, and external entity resolution.
