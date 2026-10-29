# System Architecture & Technical Diagrams Dossier
## Project: ResumeDrop (AI Resume Extraction & Excel Automation)

This document contains verified, implementation-grounded Mermaid architecture and technical diagrams for **ResumeDrop**. Every connection, module boundary, data structure, and interaction depicted in these diagrams is directly backed by source code evidence in the repository.

---

## 1. System Context & High-Level Architecture (C4 Level 1/2)

### Source Evidence:
- UI entry points: `gui.py` (Desktop GUI), `app.py` (Streamlit Web), `cli_demo.py` (Command Line Interface).
- Processing pipeline: `src/document_reader.py`, `src/resume_parser.py`, `src/ai_extractor.py`, `src/validator.py`, `src/excel_exporter.py`.
- External service: NVIDIA NIM API (`https://integrate.api.nvidia.com/v1`).
- Storage & Output: Local filesystem (`.xlsx` workbooks, `.json` dumps).

```mermaid
graph TD
    subgraph Users ["Users & Operators"]
        HR["Recruiter / Hiring Manager / HR Analyst"]
        CLI_User["DevOps / Automation Engineer"]
    end

    subgraph UserInterfaces ["User Interface Layer"]
        GUI["Tkinter Desktop GUI (gui.py)<br/>• Thread-safe UI Queue<br/>• Interactive Candidate Treeview<br/>• Modal Candidate Review & Editor"]
        WEB["Streamlit Web UI (app.py & pages/e.py)<br/>• Zero-Pill Typography<br/>• Real-time Batch Progress<br/>• Inline Form Review & Re-validation"]
        CLI["CLI Tool (cli_demo.py)<br/>• Headless Batch Ingestion<br/>• Direct Pipeline Execution"]
    end

    subgraph CoreEngine ["ResumeDrop Core Automation Engine"]
        DR["Document Ingestion Subsystem<br/>(src/document_reader.py & src/utils.py)<br/>• Magic Bytes & SHA-256 Deduplication<br/>• PyMuPDF (PDF) & python-docx (DOCX)<br/>• MarkItDown Fallback & Normalization"]
        
        RP["Orchestration Subsystem<br/>(src/resume_parser.py)<br/>• ThreadPoolExecutor Parallel Workers<br/>• Rule-Based Regex Extractors<br/>• Hybrid Result Merging & Conflict Logging"]
        
        GKP["NVIDIA NIM Key Pool & Rate Limiter<br/>(src/ai_extractor.py)<br/>• 3-Key Concurrency Management<br/>• Shared 40 RPM Rate Limiter<br/>• HTTP 429 Cooldown & Failover"]
        
        VAL["Validation & Sanitization Engine<br/>(src/validator.py)<br/>• Syntax & Plausibility Rules<br/>• Degree / Experience Duplication Check<br/>• CSV / Formula Injection Neutralization"]
        
        EXP["Excel Generation Subsystem<br/>(src/excel_exporter.py)<br/>• openpyxl Formatted 5-Worksheet Engine<br/>• Conditional Status Color Coding<br/>• Degree Hierarchy Ranking Algorithm"]
    end

    subgraph DataStructures ["Data Representation Layer"]
        SCHEMA["Canonical Pydantic v2 Models<br/>(schemas/candidate.py)<br/>• CandidateRecord<br/>• EducationRecord<br/>• WorkExperience<br/>• Project<br/>• ExtractionMetadata"]
    end

    subgraph ExternalServices ["External Infrastructure"]
        NVIDIA_NIM["NVIDIA NIM Inference Engine<br/>• meta/llama-3.3-70b-instruct<br/>• 128k Context Length<br/>• JSON Object Mode"]
    end

    subgraph FileOutputs ["Generated Artifacts"]
        XLSX["5-Worksheet Excel Workbook (.xlsx)<br/>1. Candidates (Summary)<br/>2. Education (Academic)<br/>3. Work Experience (Jobs)<br/>4. Projects (Tech & Portfolios)<br/>5. Processing Log (Audit Trail)"]
        JSON_OUT["Candidate JSON Exports"]
    end

    HR -->|Uploads Resumes| GUI
    HR -->|Uploads Resumes| WEB
    CLI_User -->|Batch Directory Ingestion| CLI

    GUI --> DR
    WEB --> DR
    CLI --> DR

    DR -->|DocumentResult| RP
    RP --> SCHEMA
    RP <-->|JSON Structured Schema| GKP
    GKP <-->|HTTPS REST API / JSON| NVIDIA_NIM
    RP --> VAL
    VAL -->|Validated CandidateRecord| SCHEMA
    SCHEMA --> GUI
    SCHEMA --> WEB
    SCHEMA --> EXP
    EXP --> XLSX
    WEB --> JSON_OUT
```

---

## 2. Component & Subsystem Dependency Diagram

### Source Evidence:
- `gui.py` imports `src.document_reader`, `src.resume_parser`, `src.ai_extractor`, `src.excel_exporter`, `schemas.candidate`.
- `app.py` imports identical core modules plus `src.validator`.
- `src/resume_parser.py` imports `src.ai_extractor.AIExtractor`, `src.document_reader.DocumentResult`, `src.validator.validate_candidate`, `schemas.candidate.*`.
- `src/document_reader.py` imports `src.utils.*`, `fitz` (PyMuPDF), `docx`, optional `markitdown`.
- `src/excel_exporter.py` imports `openpyxl`, `schemas.candidate.*`, `src.validator.sanitise_formula_injection`.

```mermaid
graph LR
    subgraph Entrypoints ["Application Entrypoints"]
        GUI["gui.py"]
        WEB["app.py"]
        PAGES["pages/e.py"]
        CLI["cli_demo.py"]
        BENCH["scripts/benchmark.py"]
        EVAL["scripts/evaluate_extraction.py"]
    end

    subgraph Schemas ["Schemas Module"]
        CAND["schemas/candidate.py<br/>CandidateRecord<br/>EducationRecord<br/>WorkExperience<br/>Project<br/>ExtractionMetadata"]
    end

    subgraph EngineModules ["Core Source Modules (src/)"]
        UTILS["src/utils.py<br/>clean_text()<br/>compute_sha256()<br/>detect_file_type()"]
        DR["src/document_reader.py<br/>DocumentReader<br/>DocumentResult<br/>ProcessingStatus"]
        AI["src/ai_extractor.py<br/>AIExtractor<br/>NvidiaKeyPool<br/>NvidiaRateLimiter"]
        PARSER["src/resume_parser.py<br/>ResumeParser<br/>run_rule_based_extraction()<br/>_merge_results()"]
        VAL["src/validator.py<br/>validate_candidate()<br/>sanitise_formula_injection()<br/>validate_email()<br/>validate_phone()"]
        EXP["src/excel_exporter.py<br/>export_to_bytes()<br/>export_to_file()<br/>get_highest_education()"]
    end

    subgraph ThirdParty ["Third-Party Libraries"]
        FITZ["PyMuPDF (fitz)"]
        DOCX["python-docx"]
        OPENPYXL["openpyxl"]
        OPENAI_SDK["openai Python SDK"]
        PYDANTIC["pydantic v2"]
        STREAMLIT["streamlit"]
        TK["tkinter / ttk"]
    end

    GUI --> DR & PARSER & AI & EXP & CAND & TK
    WEB --> DR & PARSER & AI & EXP & VAL & CAND & STREAMLIT
    PAGES --> DR & STREAMLIT
    CLI --> DR & PARSER & EXP & AI
    BENCH --> DR & PARSER
    EVAL --> DR & PARSER & AI & CAND

    DR --> UTILS & FITZ & DOCX
    AI --> OPENAI_SDK
    PARSER --> AI & DR & VAL & CAND
    VAL --> CAND
    EXP --> OPENPYXL & VAL & CAND
    CAND --> PYDANTIC
```

---

## 3. End-to-End Data Flow Diagram

### Source Evidence:
Traces the lifecycle of a resume file from ingestion to final spreadsheet rows:
1. `DocumentReader.process_bytes` or `process_files` (`src/document_reader.py:85-124`).
2. Deduplication check via `compute_sha256` (`src/utils.py:26-36`).
3. Extraction via `PyMuPDF`/`python-docx` (`src/document_reader.py:240-311`).
4. Parsing via `ResumeParser.parse` (`src/resume_parser.py:377-440`).
5. Dual-track extraction (regex in `src/resume_parser.py:92-202` + LLM prompt in `src/ai_extractor.py:353-457`).
6. Priority merge in `_merge_results` (`src/resume_parser.py:336-360`).
7. Quality validation and formula escaping in `src/validator.py:72-148`.
8. 5-worksheet dispatch in `src/excel_exporter.py:330-347`.

```mermaid
flowchart TD
    A[Input Resume: PDF, DOCX, or TXT] --> B[File Size & Extension Validation]
    B -->|Size > 10MB or Unsupported Format| B_FAIL[Flag Status: FILE_TOO_LARGE / UNSUPPORTED_FORMAT]
    B -->|Valid File Format & Size| C[Compute SHA-256 Hash]
    
    C --> D{Hash in Seen Hashes?}
    D -->|Yes| D_DUP[Flag Status: DUPLICATE<br/>Bypass Extraction]
    D -->|No| E[Text Ingestion Engine]
    
    E --> E1{Format Dispatch}
    E1 -->|PDF| E_PDF[PyMuPDF fitz.open]
    E_PDF -->|is_encrypted == True| E_PASS[Flag Status: PASSWORD_PROTECTED]
    E_PDF -->|Extract Text Blocks| E_TEXT[Raw Extracted Text]
    
    E1 -->|DOCX| E_DOCX[python-docx Document]
    E_DOCX -->|Paragraphs & Table Cells| E_TEXT
    
    E1 -->|TXT| E_TXT[UTF-8 / Latin-1 Stream]
    E_TXT --> E_TEXT
    
    E_TEXT --> F[Text Cleaning & Normalization src/utils.py]
    F -->|Collapses Whitespace & Cleans Control Chars| F_CLEAN[Cleaned Text String]
    
    F_CLEAN --> G{Length < 50 chars?}
    G -->|Yes| G_EMPTY[Flag Status: EMPTY / Scanned Image]
    G -->|No| H[Parallel ResumeParser Orchestrator]
    
    subgraph DualTrackExtraction ["Dual-Track Hybrid Extraction"]
        H --> I1[Track A: Deterministic Regex Extractors<br/>• Strict Email Regex<br/>• Multi-National Phone Regex<br/>• LinkedIn, GitHub, Portfolio Regex<br/>• Header Name & Location Heuristics]
        H --> I2[Track B: NVIDIA NIM Multi-Key Engine<br/>• Acquire Permit from Shared 40 RPM Rate Limiter<br/>• Lease Key from 3-Key Pool<br/>• Execute NIM Inference with System Prompt<br/>• Parse & Clean JSON Response Object]
    end
    
    I1 --> J[Priority Result Merger src/resume_parser.py]
    I2 --> J
    
    J -->|Rules override contact details; AI populates complex history| K[Populate Canonical CandidateRecord]
    
    K --> L[Validator Engine src/validator.py]
    L -->|Validate Email Syntax| L1[Email Check]
    L -->|Validate Phone Digits 7-15| L2[Phone Plausibility]
    L -->|Validate Grad Years 1950-2035| L3[Year Range Check]
    L -->|Identify Duplicate Degrees/Jobs| L4[Duplicate Suppression]
    L -->|Escape =, +, -, @, tab, newline with '| L5[Formula Injection Shield]
    
    L --> M{Validation Issues Exist?}
    M -->|Yes| M1[Set Status: review_required<br/>Log Issues to Metadata]
    M -->|No| M2[Set Status: success]
    
    M1 --> N[Interactive Review Layer: Tkinter Treeview or Streamlit Form]
    M2 --> N
    
    N -->|User Inline Corrections| N1[Re-validate CandidateRecord]
    N1 --> O[openpyxl 5-Worksheet Excel Exporter]
    N -->|Direct Export| O
    
    O --> P1[Sheet 1: Candidates Summary with Auto-Filter]
    O --> P2[Sheet 2: Education Academic History]
    O --> P3[Sheet 3: Work Experience with Responsibilities]
    O --> P4[Sheet 4: Projects with Technologies]
    O --> P5[Sheet 5: Processing Log Audit Trail]
    
    B_FAIL --> P5
    D_DUP --> P5
    E_PASS --> P5
    G_EMPTY --> P5
```

---

## 4. Sequence Diagram: 3-Key NVIDIA NIM Extraction, Rate Limiting & Failover

### Source Evidence:
- `src/ai_extractor.py`: `NvidiaKeyPool.get_key_for_request()`, `NvidiaRateLimiter.acquire()`, `record_rate_limit()`, `record_success()`.
- `src/ai_extractor.py`: `AIExtractor.extract()`.
- `src/resume_parser.py`: `ResumeParser.parse()`.

```mermaid
sequenceDiagram
    autonumber
    actor User as Recruiter / Operator
    participant UI as Desktop GUI / Streamlit UI
    participant Parser as ResumeParser (src/resume_parser.py)
    participant AI as AIExtractor (src/ai_extractor.py)
    participant Limiter as NvidiaRateLimiter (<=40 RPM)
    participant Pool as NvidiaKeyPool (3 Keys)
    participant NimAPI as NVIDIA NIM (integrate.api.nvidia.com)
    participant Val as Validator (src/validator.py)

    User->>UI: Selects batch of resumes & clicks "Start Extraction"
    UI->>Parser: parse_batch_parallel(docs, max_workers=3)
    
    loop For each DocumentResult
        Parser->>Parser: run_rule_based_extraction(text)
        Note over Parser: Extracts email, phone, URLs via regex
        
        Parser->>AI: extract(truncated_text, filename)
        AI->>Limiter: acquire(timeout=60.0)
        Limiter-->>AI: Permit granted (within 40 RPM window)
        AI->>Pool: get_key_for_request()
        Pool-->>AI: Return KeyStatus(index=0, key="nvapi-key1")
        
        AI->>NimAPI: chat.completions.create(model="meta/llama-3.3-70b-instruct", key="nvapi-key1")
        
        alt NVIDIA returns HTTP 429 (Rate Limit Exceeded)
            NimAPI-->>AI: Error 429: Rate limit reached (Retry-After)
            AI->>Pool: record_rate_limit(key0, backoff_seconds=30.0, account_wide=True)
            Note over Pool: Key 0 and account cooldown enforced
            
            AI->>Limiter: acquire(timeout=60.0)
            Limiter-->>AI: Permit granted after cooldown
            AI->>Pool: get_key_for_request() (Attempt 2)
            Pool-->>AI: Return KeyStatus(index=1, key="nvapi-key2")
            
            AI->>NimAPI: chat.completions.create(model="meta/llama-3.3-70b-instruct", key="nvapi-key2")
            NimAPI-->>AI: HTTP 200 OK with Candidate JSON
            AI->>Pool: record_success(key1)
        else NVIDIA returns HTTP 200 OK directly
            NimAPI-->>AI: HTTP 200 OK with Candidate JSON
            AI->>Pool: record_success(key0)
        end
        
        AI->>AI: extract_json_from_response(raw)
        AI-->>Parser: AIExtractionResult(success=True, data=dict)
        
        Parser->>Parser: _merge_results(rule_data, ai_data)
        Parser->>Val: validate_candidate(record)
        Val->>Val: validate_email(), validate_phone(), validate_graduation_years()
        Val-->>Parser: Validated CandidateRecord
        Parser-->>UI: Progress update callback & CandidateRecord
        UI->>UI: Update Treeview row & Progress bar
    end
    
    UI->>User: Batch Complete Notification (Success / Review required)
```

---

## 5. Sequence Diagram: Desktop GUI Threading Architecture

### Source Evidence:
- `gui.py:47-73`: Tkinter initialization, `ui_queue`, and `root.after(100, self._process_ui_queue)`.
- `gui.py:378-411`: Background thread spawn `threading.Thread(target=self._worker_thread_run, daemon=True)`.
- `gui.py:463-551`: Thread-safe UI polling via `Queue.get_nowait()`.

```mermaid
sequenceDiagram
    autonumber
    actor User as Operator
    participant MainThread as Tkinter Main Thread (gui.py)
    participant UIQueue as queue.Queue (Thread-Safe UI Queue)
    participant WorkerThread as Background Worker Thread
    participant Reader as DocumentReader
    participant Parser as ResumeParser

    User->>MainThread: Clicks "Start Extraction"
    MainThread->>MainThread: btn_start.config(state=DISABLED), btn_stop.config(state=NORMAL)
    MainThread->>WorkerThread: Spawn threading.Thread(target=_worker_thread_run)
    
    Note over MainThread: Main Thread continues running Tkinter mainloop() smoothly (No UI Freezing)
    
    WorkerThread->>Reader: process_files(queued_files)
    Reader-->>WorkerThread: List of DocumentResult objects
    
    loop For each DocumentResult
        WorkerThread->>UIQueue: put(("status", "Extracting [1/10]: resume.pdf..."))
        WorkerThread->>Parser: parse(doc)
        Parser-->>WorkerThread: CandidateRecord
        WorkerThread->>UIQueue: put(("candidate_done", cand, completed=1, total=10))
    end
    
    WorkerThread->>UIQueue: put(("finished", None))
    
    loop Polled every 100ms via root.after()
        MainThread->>UIQueue: get_nowait()
        UIQueue-->>MainThread: ("candidate_done", cand, 1, 10)
        MainThread->>MainThread: tree.insert(row), progress_bar.step()
        
        MainThread->>UIQueue: get_nowait()
        UIQueue-->>MainThread: ("finished", None)
        MainThread->>MainThread: btn_start.config(state=NORMAL), btn_export.config(state=NORMAL)
    end
```

---

## 6. Entity-Relationship & Relational Data Model (Workbook Structure)

### Source Evidence:
- Schemas: `schemas/candidate.py:25-146`.
- Spreadsheet generator: `src/excel_exporter.py:112-328`.
- Foreign key relationship: `CandidateRecord.candidate_id` (UUID4 string) acts as the primary key in `Candidates` and the foreign key in `Education`, `Work Experience`, and `Projects`.

```mermaid
erDiagram
    CANDIDATES ||--o{ EDUCATION : "has academic records"
    CANDIDATES ||--o{ WORK_EXPERIENCE : "has employment history"
    CANDIDATES ||--o{ PROJECTS : "has portfolio projects"
    CANDIDATES ||--|| PROCESSING_LOG : "generates audit entry"

    CANDIDATES {
        string candidate_id PK "UUID4 unique candidate identifier"
        string resume_filename "Source filename (e.g. alice_chen.pdf)"
        string full_name "Candidate's normalized personal name"
        string email "Lowercased email address"
        string phone "Phone number preserving country code"
        string location "Explicit candidate city / region"
        string highest_qualification "Derived highest degree (e.g. Ph.D., M.Sc.)"
        string specialization "Branch / field of study"
        string institution "College / university name"
        string graduation_year "4-digit year or expected year"
        string all_education "Semicolon-separated education summary"
        string technical_skills "Semicolon-separated competencies"
        string programming_languages "Semicolon-separated languages"
        string tools "Semicolon-separated frameworks & tools"
        string total_experience_jobs "Count of distinct job entries"
        string certifications "Semicolon-separated certificates"
        string linkedin_url "Normalized HTTPS LinkedIn profile"
        string github_url "Normalized HTTPS GitHub profile"
        string portfolio_url "Personal website / portfolio"
        string processing_status "success | review_required | partial | failed"
        string extraction_method "rules_only | ai | rules+ai"
        string missing_fields "Fields missing from resume"
        string validation_issues "Validation failure warnings"
        string review_notes "Duplicate entries or merge conflicts"
    }

    EDUCATION {
        string candidate_id FK "References CANDIDATES.candidate_id"
        string resume_filename "Source resume file"
        string full_name "Candidate name"
        string qualification "Degree level (B.Tech, M.S., Ph.D.)"
        string specialization "Major / branch of engineering"
        string institution "Awarding university / college"
        string start_year "4-digit start year"
        string graduation_year "4-digit completion year"
    }

    WORK_EXPERIENCE {
        string candidate_id FK "References CANDIDATES.candidate_id"
        string resume_filename "Source resume file"
        string full_name "Candidate name"
        string employer "Company / organization"
        string job_title "Official designation"
        string start_date "Start period"
        string end_date "End period or Present"
        string responsibilities "Bullet-pointed responsibilities (• formatted)"
        string description "Narrative role description"
    }

    PROJECTS {
        string candidate_id FK "References CANDIDATES.candidate_id"
        string resume_filename "Source resume file"
        string full_name "Candidate name"
        string project_name "Title of project"
        string description "Technical summary of architecture / functionality"
        string technologies "Comma-separated tech stack"
    }

    PROCESSING_LOG {
        string resume_filename "Source filename"
        string document_status "success | corrupt | empty | unsupported | duplicate"
        string extraction_status "success | partial | failed | review_required"
        string extraction_method "rules_only | ai | rules+ai | none"
        int characters_extracted "Total character count extracted from doc"
        string missing_fields "Missing recommended fields"
        string validation_issues "Detailed validation messages"
        string failure_reason "Exception string or error explanation"
        string extracted_at "ISO-8601 UTC timestamp"
    }
```

---

## 7. Deployment & Operational Environment Architecture

### Source Evidence:
- Deployment manual: `SETUP.md` (Windows PowerShell & Linux Bash).
- Development container: `.devcontainer/devcontainer.json`.
- Startup script: `run_dev.sh` (Streamlit web server on port 3000).
- Configuration: `package.json`, `.env.example`, `pytest.ini`.

```mermaid
graph TB
    subgraph HostSystem ["Host Operating System (Windows 10/11 or Ubuntu / Debian Linux)"]
        subgraph PythonRuntime ["Python Runtime Environment (Python 3.10 - 3.12)"]
            subgraph VirtualEnv [".venv Virtual Environment (~250 MB footprint)"]
                CORE_LIBS["PyMuPDF (fitz) | python-docx | openpyxl | pydantic v2 | openai"]
                TEST_LIBS["pytest | pytest-cov"]
            end
            
            subgraph AppExecutionModes ["Execution Profiles"]
                DESKTOP_MODE["Desktop Mode: python gui.py<br/>• Native OS Window (Tkinter / ttk)<br/>• Direct Local File System Access<br/>• Zero Browser Latency"]
                CLI_MODE["CLI Mode: python cli_demo.py<br/>• Headless Terminal Execution<br/>• Automated CI/CD Scripting"]
                WEB_MODE["Web Mode: streamlit run app.py<br/>• Port 3000 Web UI<br/>• Localhost / Container Access"]
            end
        end

        subgraph LocalFileSystem ["Local Storage Layer"]
            SAMPLE_DIR["sample_resumes/ (PDF, DOCX, TXT)"]
            ENV_FILE[".env (3-Key NVIDIA Storage)"]
            OUT_DIR["output/ (Formatted .xlsx workbooks)"]
        end
    end

    subgraph ExternalCloud ["External Cloud Infrastructure"]
        NVIDIA_CLOUD["NVIDIA NIM Inference Network<br/>• OpenAI-Compatible API (integrate.api.nvidia.com)<br/>• Model: meta/llama-3.3-70b-instruct<br/>• Shared 40 RPM Rate Limiter"]
    end

    ENV_FILE -.->|Reads NVIDIA_API_KEY_1..3| VirtualEnv
    SAMPLE_DIR -->|Read Files| AppExecutionModes
    AppExecutionModes -->|Write Workbook| OUT_DIR
    VirtualEnv <==>|Encrypted REST Calls| NVIDIA_CLOUD
```
