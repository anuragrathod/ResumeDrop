# ResumeDrop — Setup & Installation Guide

This document provides verified, step-by-step installation, configuration, execution, and troubleshooting instructions for both **Windows (PowerShell)** and **Linux (Bash)** environments.

---

## System Requirements & Prerequisites

| Requirement | Specification |
|---|---|
| **Python Version** | Python 3.10, 3.11, or 3.12 (64-bit recommended) |
| **Operating System** | Windows 10/11 (PowerShell 5.1+ / PowerShell 7+) or Linux (Ubuntu 20.04+, Debian 11+, RHEL/Fedora) |
| **Disk Space** | ~250 MB for dependencies (lightweight; no PyTorch/Docling bloat) |
| **API Keys** | 1 to 3 Groq API keys (free tier available at [console.groq.com](https://console.groq.com/keys)) |

---

## 🪟 Windows Setup (PowerShell)

### Step 1: Verify Python Installation
Open **Windows PowerShell** (or Windows Terminal) and verify that Python 3.10+ and pip are installed and added to your `PATH`:

```powershell
python --version
pip --version
```

> **Note**: If `python` is not recognized, download the latest 64-bit installer from [python.org](https://www.python.org/downloads/) and ensure **"Add Python to PATH"** is checked during installation.

### Step 2: Clone or Enter Repository
```powershell
cd path\to\ResumeDrop
```

### Step 3: Create & Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> **Execution Policy Troubleshooting**: If you see `Execution_Policies` script restriction error, run:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> .\.venv\Scripts\Activate.ps1
> ```

### Step 4: Upgrade Pip & Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables
Copy the `.env.example` file to `.env`:
```powershell
Copy-Item .env.example .env
```

Open `.env` in Notepad or your preferred editor:
```powershell
notepad .env
```

Add your Groq API keys (you can provide 1, 2, or 3 keys to enable high-speed round-robin rotation and automatic HTTP 429 rate-limit failover):
```env
# Single key:
GROQ_API_KEY=gsk_your_key_here

# OR multi-key pool for parallel rotation:
GROQ_API_KEY_1=gsk_key1_here
GROQ_API_KEY_2=gsk_key2_here
GROQ_API_KEY_3=gsk_key3_here

# Default model (recommended: llama-3.3-70b-versatile or llama-3.1-8b-instant):
DEFAULT_GROQ_MODEL=llama-3.3-70b-versatile
MAX_WORKERS=4
```

### Step 6: Run the Application

#### Option A: Streamlit Modern Web Application
```powershell
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

#### Option B: Fast CLI Batch Extraction & Excel Export
```powershell
# Extract sample resumes and export to 5-worksheet Excel workbook:
python cli_demo.py --dir sample_resumes --extract --export output/candidates.xlsx --verbose

# Process custom folder of resumes:
python cli_demo.py --dir C:\path\to\resumes --extract --export output\results.xlsx
```

### Step 7: Run Automated Tests
```powershell
pytest
```
To run tests with code coverage:
```powershell
pytest --cov=src tests/
```

### Step 8: Deactivate Virtual Environment
When finished, deactivate the environment:
```powershell
deactivate
```

---

## 🐧 Linux Setup (Bash)

### Step 1: Install System Prerequisites
On Debian/Ubuntu-based distributions:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv build-essential
```

Verify Python:
```bash
python3 --version
pip3 --version
```

### Step 2: Clone or Enter Repository
```bash
cd /path/to/ResumeDrop
```

### Step 3: Create & Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Step 4: Upgrade Pip & Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Configure Environment Variables
```bash
cp .env.example .env
nano .env   # or vim .env
```

Configure your Groq key pool:
```env
GROQ_API_KEY_1=gsk_key1_here
GROQ_API_KEY_2=gsk_key2_here
GROQ_API_KEY_3=gsk_key3_here
DEFAULT_GROQ_MODEL=llama-3.3-70b-versatile
MAX_WORKERS=4
```

### Step 6: Run the Application

#### Option A: Streamlit Modern Web Application
```bash
streamlit run app.py --server.port 8501
```
Open `http://localhost:8501` in your browser.

#### Option B: CLI Batch Tool
```bash
# Process sample resumes and generate 5-sheet Excel workbook:
python3 cli_demo.py --dir sample_resumes --extract --export output/candidates.xlsx --verbose
```

### Step 7: Run Unit Tests & Benchmarks
```bash
# Run all unit tests
pytest

# Run throughput benchmark
python3 scripts/benchmark.py

# Run accuracy evaluation against synthetic ground truth
python3 scripts/evaluate_extraction.py
```

### Step 8: Deactivation
```bash
deactivate
```

---

## 🛠️ Common Troubleshooting

### 1. "Invalid API Key" or 401 Unauthorized Error
- **Symptom**: Console outputs `Error code: 401 - Invalid API Key`.
- **Solution**: Obtain valid API keys from [console.groq.com/keys](https://console.groq.com/keys). Paste them into `.env` as `GROQ_API_KEY_1`, `GROQ_API_KEY_2`, etc. Even without an API key, ResumeDrop continues operating using rule-based regex extraction (extracting name, email, phone, location, links).

### 2. Rate Limit (HTTP 429) Handling
- **Built-in Resilience**: ResumeDrop automatically detects HTTP 429 rate limit responses, puts the exhausted key on a 60-second cooldown, logs the failover event, and automatically re-routes pending requests to the next active key in the pool.
- **Recommendation**: Adding 2 or 3 distinct Groq keys provides 2x to 3x higher throughput with uninterrupted processing during large resume batches.

### 3. File Formats Supported
- **PDF**: Handled natively by `PyMuPDF` (`fitz`), preserving layout columns, tables, and multi-page text.
- **DOCX**: Handled natively by `python-docx` for paragraphs and embedded tables.
- **TXT**: Handled via UTF-8 / latin-1 decoding with MarkItDown fallback.
- **Encrypted / Password-Protected PDFs**: Detected gracefully; the system flags them as `password_protected` in the audit log without crashing.

### 4. Excel Formula Injection Protection
All text fields exported to `.xlsx` are automatically sanitized. If any string starts with `=`, `+`, `-`, `@`, `\t`, or `\r`, an apostrophe prefix (`'`) is prepended to ensure formulas do not execute when opened in Microsoft Excel or LibreOffice Calc.
