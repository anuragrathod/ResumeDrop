# ResumeDrop — Setup & Installation Guide

This document provides verified, step-by-step installation, configuration, execution, and troubleshooting instructions for **Windows (PowerShell)** and **Linux (Bash)** environments for the pure Python ResumeDrop application powered by **NVIDIA NIM APIs**.

---

## System Requirements & Prerequisites

| Requirement | Specification |
|---|---|
| **Python Version** | Python 3.10, 3.11, or 3.12 (64-bit recommended) |
| **Operating System** | Windows 10/11 (PowerShell 5.1+ / PowerShell 7+) or Linux (Ubuntu 20.04+, Debian 11+, RHEL/Fedora) |
| **GUI Framework** | Python `tkinter` (included on Windows/macOS; `python3-tk` on Debian/Ubuntu) |
| **Disk Space** | ~250 MB for dependencies (lightweight; no PyTorch or Docling bloat) |
| **API Keys** | 3 NVIDIA API keys belonging to the same account (free tier available at [build.nvidia.com](https://build.nvidia.com/)) |
| **Target Rate Limit** | Up to 40 requests/minute shared across all 3 keys combined |

---

## 🔑 Obtaining Your 3 NVIDIA API Keys

1. Visit **[https://build.nvidia.com/](https://build.nvidia.com/)** and sign in or create a free NVIDIA Developer account (no credit card required).
2. Go to **[https://build.nvidia.com/models](https://build.nvidia.com/models)** and select a model with the **Free Endpoint** tag, such as **Meta Llama 3.3 70B Instruct** (`meta/llama-3.3-70b-instruct`).
3. Click **Get API Key** to generate an API key starting with `nvapi-`.
4. Generate three distinct API keys under your account.
5. Copy all three keys into your `.env` configuration file as `NVIDIA_API_KEY_1`, `NVIDIA_API_KEY_2`, and `NVIDIA_API_KEY_3`.

---

## 🪟 Windows Setup (PowerShell)

### Step 1: Verify Python Installation
Open **Windows PowerShell** (or Windows Terminal) and verify that Python 3.10+ and pip are installed and added to your `PATH`:

```powershell
python --version
pip --version
```

> **Note**: Tkinter is bundled by default with official Python for Windows installers from [python.org](https://www.python.org/downloads/). Ensure **"tcl/tk and IDLE"** was not deselected during installation.

### Step 2: Clone or Enter Repository
```powershell
git clone https://github.com/anuragrathod/ResumeDrop.git
cd ResumeDrop
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
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Open `.env` in Notepad:
```powershell
notepad .env
```

Add your 3 NVIDIA API keys:
```env
NVIDIA_API_KEY_1=nvapi-your_first_key_here
NVIDIA_API_KEY_2=nvapi-your_second_key_here
NVIDIA_API_KEY_3=nvapi-your_third_key_here

DEFAULT_NVIDIA_MODEL=meta/llama-3.3-70b-instruct
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_RATE_LIMIT_RPM=40
MAX_WORKERS=3
```

### Step 6: Start the Application

#### Option A: Modern Tkinter Desktop GUI
```powershell
python gui.py
```

#### Option B: Fast CLI Batch Extraction & Excel Export
```powershell
# Extract sample resumes and export to 5-worksheet Excel workbook:
python cli_demo.py --dir sample_resumes --extract --export output/candidates.xlsx --verbose

# Process custom folder of resumes:
python cli_demo.py --dir C:\path\to\resumes --extract --export output\results.xlsx
```

#### Option C: Streamlit Web UI (Alternative)
```powershell
streamlit run app.py
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
```powershell
deactivate
```

---

## 🐧 Linux Setup (Bash)

### Step 1: Install System Prerequisites
On Debian/Ubuntu-based distributions:
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk build-essential
```

Verify Python & Tkinter:
```bash
python3 --version
python3 -c "import tkinter; print('Tkinter available')"
```

### Step 2: Clone or Enter Repository
```bash
git clone https://github.com/anuragrathod/ResumeDrop.git
cd ResumeDrop
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

Configure your NVIDIA key pool:
```env
NVIDIA_API_KEY_1=nvapi-your_first_key_here
NVIDIA_API_KEY_2=nvapi-your_second_key_here
NVIDIA_API_KEY_3=nvapi-your_third_key_here

DEFAULT_NVIDIA_MODEL=meta/llama-3.3-70b-instruct
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_RATE_LIMIT_RPM=40
MAX_WORKERS=3
```

### Step 6: Start the Application

#### Option A: Modern Tkinter Desktop GUI
```bash
python3 gui.py
```
> **Headless / Remote Linux Note**: If running over SSH without X11 forwarding or on a headless server, use the CLI tool (Option B) or launch Tkinter using X11 forwarding (`ssh -X`) or a virtual display (`xvfb-run python3 gui.py`).

#### Option B: CLI Batch Tool
```bash
python3 cli_demo.py --dir sample_resumes --extract --export output/candidates.xlsx --verbose
```

#### Option C: Streamlit Web UI
```bash
bash run_dev.sh
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

## 🛠️ Architecture & Rate-Limit Mechanics

### 1. Three API Keys & Shared 40 RPM Limit
- Because all 3 API keys belong to the same NVIDIA account, they share account-level and model-level quotas.
- `NvidiaRateLimiter` implements a concurrency-safe sliding-window rate limiter that limits total outbound requests across all 3 keys to at most 40 requests per rolling 60 seconds.
- Requests run in parallel whenever the shared limiter has available capacity, avoiding unnecessary serial waiting while strictly protecting against quota exhaustion.

### 2. Rate Limit (HTTP 429) & Cooldown Handling
- If an HTTP 429 status code is received, ResumeDrop parses the `Retry-After` header or message, applies exponential backoff, pauses the exhausted key, and temporarily enforces a shared account cooldown to avoid retry storms.

### 3. File Formats Supported
- **PDF**: Handled natively by `PyMuPDF` (`fitz`), preserving layout columns, tables, and multi-page text.
- **DOCX**: Handled natively by `python-docx` for paragraphs and embedded tables.
- **TXT**: Handled via UTF-8 / latin-1 decoding.
- **Encrypted / Password-Protected PDFs**: Detected gracefully and flagged as `password_protected` in the audit log without crashing.

### 4. Excel Formula Injection Protection
All text fields exported to `.xlsx` are automatically sanitized. If any string starts with `=`, `+`, `-`, `@`, `\t`, or `\r`, an apostrophe prefix (`'`) is prepended to ensure formulas do not execute when opened in Microsoft Excel or LibreOffice Calc.
