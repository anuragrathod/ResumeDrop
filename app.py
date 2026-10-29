"""
app.py
======
ResumeDrop — Modernized Streamlit Web Interface.
Resume-to-Excel automation system with Multi-Key NVIDIA NIM Pool (40 RPM), parallel batch processing,
Apple-inspired typography & zero-pill design, and formatted 5-sheet workbook export.
"""

from __future__ import annotations

import html
import io
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

st.set_page_config(
    page_title="ResumeDrop",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load environment variables
try:
    import dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        dotenv.load_dotenv(dotenv_path=_env_path, override=True)
    else:
        dotenv.load_dotenv(override=True)
except ImportError:
    pass

from schemas.candidate import (
    CandidateRecord,
    EducationRecord,
    ExtractionMetadata,
    Project,
    WorkExperience,
)
from src.ai_extractor import (
    DEFAULT_NVIDIA_MODEL,
    FALLBACK_NVIDIA_MODELS,
    AIConfig,
    AIExtractor,
    NvidiaKeyPool,
    check_nvidia_available,
    list_nvidia_models,
)
from src.document_reader import DocumentReader, DocumentResult, ProcessingStatus
from src.excel_exporter import export_to_bytes
from src.resume_parser import ResumeParser
from src.validator import validate_candidate

logging.basicConfig(level=logging.INFO)

MAX_FILE_SIZE_MB = 10
_AVAILABLE_MODELS = [
    "meta/llama-3.3-70b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "deepseek-ai/deepseek-r1",
    "mistralai/mistral-large-2-instruct",
]

_STATUS_CONFIG = {
    "success": {"label": "Verified", "color": "#248a3d", "bg": "rgba(36, 138, 61, 0.12)"},
    "partial": {"label": "Partial", "color": "#b25000", "bg": "rgba(178, 80, 0, 0.12)"},
    "review_required": {"label": "Needs Review", "color": "#b25000", "bg": "rgba(178, 80, 0, 0.12)"},
    "failed": {"label": "Failed", "color": "#d70015", "bg": "rgba(215, 0, 21, 0.12)"},
    "pending": {"label": "Pending", "color": "#6e6e73", "bg": "rgba(0, 0, 0, 0.06)"},
}

# ---------------------------------------------------------------------------
# Design System: Apple / SF Pro Typography, Zero-Pill Discipline
# ---------------------------------------------------------------------------
st.markdown("""
<style>
:root {
    --bg: #fbfbfd;
    --surface: #ffffff;
    --sidebar: #f5f5f7;
    --text: #1d1d1f;
    --muted: #6e6e73;
    --line: rgba(0, 0, 0, 0.10);
    --line-strong: rgba(0, 0, 0, 0.22);
    --accent: #0071e3;
    --accent-hover: #0077ed;
    --ok: #248a3d;
    --warn: #b25000;
    --bad: #d70015;
    --radius: 12px;
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
            "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}

.stApp, .stApp :where(p, li, label, input, textarea, button, summary, h1, h2, h3, h4, td, th) {
    font-family: var(--font);
    -webkit-font-smoothing: antialiased;
}

.stApp { background: var(--bg); color: var(--text); }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container {
    max-width: 1080px;
    padding: 2.25rem clamp(1rem, 4vw, 2.5rem) 4rem !important;
}

h1, h2, h3 { color: var(--text) !important; letter-spacing: -0.025em !important; }
h3 { font-size: 1.25rem !important; font-weight: 600 !important; padding-top: 1.75rem !important; }

.rd-title {
    font-size: clamp(2rem, 4.5vw, 2.75rem);
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin: 0 0 0.5rem 0;
    color: var(--text);
}
.rd-lede {
    font-size: 1.05rem;
    line-height: 1.5;
    color: var(--muted);
    margin: 0 0 1.75rem 0;
    max-width: 42rem;
}

/* Top Navigation Bar */
.rd-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 1.25rem;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid var(--line);
}
.rd-nav-brand {
    font-size: 1.15rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: var(--text);
    text-decoration: none;
}
.rd-nav-links {
    display: flex;
    gap: 1.25rem;
}
.rd-nav-link {
    font-size: 0.92rem;
    font-weight: 500;
    color: var(--muted);
    text-decoration: none;
    transition: color 0.15s ease;
}
.rd-nav-link:hover { color: var(--accent); }
.rd-nav-link.active {
    color: var(--accent);
    font-weight: 600;
}

.rd-brand {
    font-size: 1.2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0 0 1.25rem 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.rd-status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    color: var(--text);
    margin: 0.25rem 0;
    font-weight: 500;
}
.rd-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    flex: none;
}
.rd-dot.ok { background: var(--ok); }
.rd-dot.warn { background: var(--warn); }
.rd-dot.bad { background: var(--bad); }

.rd-note { font-size: 0.8rem; color: var(--muted); line-height: 1.5; margin: 0 0 1rem 0; }
.rd-progress-line { font-size: 0.85rem; margin: 4px 0; font-family: monospace; }
.rd-progress-line.ok { color: var(--ok); }
.rd-progress-line.bad { color: var(--bad); }

/* Sidebar completely removed */
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
section[data-testid="stSidebar"] {
    display: none !important;
}

/* Metrics */
[data-testid="stMetric"] {
    background: transparent;
    border: none;
    border-top: 1px solid var(--line);
    border-radius: 0;
    padding: 0.85rem 0 0 0;
    box-shadow: none;
}
[data-testid="stMetricLabel"] p { font-size: 0.85rem; font-weight: 500; color: var(--muted); }
[data-testid="stMetricValue"] div {
    font-size: clamp(1.6rem, 3vw, 2.2rem);
    font-weight: 600;
    letter-spacing: -0.03em;
    color: var(--text);
    font-variant-numeric: tabular-nums;
}

/* Buttons */
.stButton > button,
.stFormSubmitButton > button,
.stDownloadButton > button {
    min-height: 2.6rem;
    border-radius: 980px;
    font-weight: 500;
    font-size: 0.92rem;
    padding: 0.4rem 1.4rem;
    border: 1px solid var(--line-strong) !important;
    background: var(--surface) !important;
    color: var(--text) !important;
    box-shadow: none !important;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}
.stButton > button:hover,
.stFormSubmitButton > button:hover,
.stDownloadButton > button:hover {
    background: #f0f0f2 !important;
}
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #ffffff !important;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {
    background: var(--accent-hover) !important;
}
.stButton > button[kind="primary"] p,
.stDownloadButton > button[kind="primary"] p { color: #ffffff !important; }

/* File list */
.rd-files { display: flex; flex-wrap: wrap; gap: 8px; margin: 0.75rem 0 1rem 0; }
.rd-file {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 980px;
    padding: 4px 12px;
    font-size: 0.82rem;
    color: var(--text);
}
.rd-file span { color: var(--muted); margin-left: 6px; font-size: 0.75rem; }
.rd-file.dup { border-color: rgba(178, 80, 0, 0.45); color: var(--warn); }

/* Expanders */
[data-testid="stExpander"] details {
    background: var(--surface);
    border: 1px solid var(--line) !important;
    border-radius: var(--radius) !important;
}
[data-testid="stExpander"] summary { padding: 0.85rem 1rem; font-weight: 500; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------


def _init_state() -> None:
    defaults = {
        "candidates": [],
        "failed_docs": [],
        "processed": False,
        "upload_key": 0,
        "edited": {},
        "selected_model": DEFAULT_NVIDIA_MODEL,
        "custom_keys_text": "",
        "max_workers": 3,
        "rules_only": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init_state()


def _reset_workspace() -> None:
    st.session_state.candidates = []
    st.session_state.failed_docs = []
    st.session_state.processed = False
    st.session_state.edited = {}
    st.session_state.upload_key += 1
    st.rerun()


# ---------------------------------------------------------------------------
# Key Pool Manager
# ---------------------------------------------------------------------------


def _save_keys_to_env(keys_str: str) -> None:
    """Save provided NVIDIA keys to .env file for persistence."""
    env_file = Path(__file__).resolve().parent / ".env"
    cleaned_keys = [k.strip() for k in re.split(r"[,;\s\n]+", keys_str) if k.strip().startswith("nvapi-")]
    if not cleaned_keys:
        return

    joined = ", ".join(cleaned_keys)
    lines = []
    found_keys = False
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("NVIDIA_API_KEYS="):
                lines.append(f"NVIDIA_API_KEYS={joined}")
                found_keys = True
            elif line.startswith("NVIDIA_API_KEY_1=") and len(cleaned_keys) >= 1:
                lines.append(f"NVIDIA_API_KEY_1={cleaned_keys[0]}")
            elif line.startswith("NVIDIA_API_KEY_2=") and len(cleaned_keys) >= 2:
                lines.append(f"NVIDIA_API_KEY_2={cleaned_keys[1]}")
            elif line.startswith("NVIDIA_API_KEY_3=") and len(cleaned_keys) >= 3:
                lines.append(f"NVIDIA_API_KEY_3={cleaned_keys[2]}")
            else:
                lines.append(line)
    if not found_keys:
        lines.append(f"NVIDIA_API_KEYS={joined}")
        for idx, k in enumerate(cleaned_keys[:3], start=1):
            lines.append(f"NVIDIA_API_KEY_{idx}={k}")

    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["NVIDIA_API_KEYS"] = joined
    for idx, k in enumerate(cleaned_keys[:3], start=1):
        os.environ[f"NVIDIA_API_KEY_{idx}"] = k


@st.cache_resource(show_spinner=False)
def _get_key_pool(keys_tuple: tuple[str, ...]) -> NvidiaKeyPool:
    """Return a shared NvidiaKeyPool instance."""
    pool = NvidiaKeyPool()
    if keys_tuple:
        pool.set_keys(list(keys_tuple))
    else:
        pool.reload_from_env()
    return pool


# ---------------------------------------------------------------------------
# API Key Discovery & Connection Verification on Load
# ---------------------------------------------------------------------------
def _discover_all_env_keys() -> list[str]:
    """Discover all NVIDIA API keys from environment variables."""
    keys: list[str] = []
    # 1. Numbered keys NVIDIA_API_KEY_1, NVIDIA_API_KEY_2, NVIDIA_API_KEY_3
    for i in range(1, 11):
        k = os.getenv(f"NVIDIA_API_KEY_{i}", "").strip()
        if k and k not in keys:
            keys.append(k)
    # 2. Comma/whitespace separated keys in NVIDIA_API_KEYS
    val_multi = os.getenv("NVIDIA_API_KEYS", "").strip()
    if val_multi:
        for item in re.split(r"[,;\s\n]+", val_multi):
            k = item.strip()
            if k and k not in keys:
                keys.append(k)
    # 3. Single key fallback
    single = os.getenv("NVIDIA_API_KEY", "").strip()
    if single and single not in keys:
        keys.append(single)
    return keys


if st.session_state.custom_keys_text.strip():
    custom_keys = [
        k.strip()
        for k in re.split(r"[,;\s\n]+", st.session_state.custom_keys_text)
        if k.strip().startswith("nvapi-")
    ]
    effective_keys = tuple(custom_keys) if custom_keys else tuple(_discover_all_env_keys())
else:
    effective_keys = tuple(_discover_all_env_keys())

pool = _get_key_pool(effective_keys)

# Model selector list
available_nvidia_models = list(_AVAILABLE_MODELS)

# Check or retrieve cached connection status without blocking page render
if "conn_status" not in st.session_state:
    if pool.total_count > 0:
        st.session_state["conn_status"] = (
            True,
            f"NVIDIA NIM configured ({pool.active_count}/{pool.total_count} keys active · max {pool.rate_limiter.max_requests} RPM)",
        )
    else:
        st.session_state["conn_status"] = (
            False,
            "No keys configured. Set NVIDIA_API_KEY_1, NVIDIA_API_KEY_2, NVIDIA_API_KEY_3 in .env.",
        )

is_api_connected, api_status_message = st.session_state["conn_status"]

if st.session_state.selected_model not in available_nvidia_models:
    st.session_state.selected_model = available_nvidia_models[0]

# ---------------------------------------------------------------------------
# Navigation Bar
# ---------------------------------------------------------------------------
st.markdown("""
<div class="rd-nav">
    <a href="/" target="_self" class="rd-nav-brand">ResumeDrop</a>
    <div class="rd-nav-links">
        <a href="/" target="_self" class="rd-nav-link active">Extractor</a>
        <a href="/logs" target="_self" class="rd-nav-link">API Logs</a>
        <a href="/e" target="_self" class="rd-nav-link">Raw Text</a>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header Section & Top Action Controls
# ---------------------------------------------------------------------------
hdr_col, action_col = st.columns([4, 1], vertical_alignment="center")
with hdr_col:
    st.markdown("""
    <h1 class="rd-title">Resume to Excel</h1>
    <p class="rd-lede">Drop PDF, DOCX, or TXT resumes below. Candidate details are extracted via NVIDIA NIM into a formatted 5-worksheet Excel workbook you can review and edit first.</p>
    """, unsafe_allow_html=True)

with action_col:
    if st.button("Reset workspace", key="main_reset_btn", use_container_width=True):
        _reset_workspace()

    if st.button("Retest connection", key="retest_conn_btn", use_container_width=True):
        with st.spinner("Testing NVIDIA NIM connection..."):
            is_conn, msg = check_nvidia_available(pool)
            st.session_state["conn_status"] = (is_conn, msg)
            st.session_state["last_connection_test"] = (is_conn, msg)

if "last_connection_test" in st.session_state:
    is_conn, msg = st.session_state["last_connection_test"]
    if is_conn:
        st.success(f"NVIDIA NIM Connected: {pool.active_count}/{pool.total_count} keys active · max 40 RPM · {msg}", icon="🟢")
    else:
        st.error(f"NVIDIA NIM Connection Failed: {msg}", icon="🔴")

# ---------------------------------------------------------------------------
# Key Pool Manager & NIM Settings Expander
# ---------------------------------------------------------------------------
with st.expander(f"⚙ NVIDIA NIM Key Pool & Settings ({pool.active_count}/{pool.total_count} keys active · max {pool.rate_limiter.max_requests} RPM)", expanded=False):
    st.markdown("**Active Keys in Pool:**")
    if pool.keys:
        cols_disp = st.columns(len(pool.keys))
        for idx, k_stat in enumerate(pool.keys):
            with cols_disp[idx]:
                st.markdown(
                    f"**Key #{k_stat.index + 1}**  \n"
                    f"`{k_stat.masked_key}`  \n"
                    f"{'🟢 Ready' if k_stat.is_available else '🔴 Cooldown'} · {k_stat.total_calls} calls"
                )
    else:
        st.warning("No API keys loaded. Provide your keys below.")

    st.write("")
    st.markdown("**Update NVIDIA API Keys:**")
    col_k1, col_k2, col_k3 = st.columns(3)
    k1_val = pool.keys[0].key if len(pool.keys) >= 1 else ""
    k2_val = pool.keys[1].key if len(pool.keys) >= 2 else ""
    k3_val = pool.keys[2].key if len(pool.keys) >= 3 else ""

    with col_k1:
        new_k1 = st.text_input("NVIDIA Key 1", value=k1_val, type="password", key="inp_key_1")
    with col_k2:
        new_k2 = st.text_input("NVIDIA Key 2", value=k2_val, type="password", key="inp_key_2")
    with col_k3:
        new_k3 = st.text_input("NVIDIA Key 3", value=k3_val, type="password", key="inp_key_3")

    col_btn_save, col_model_sel = st.columns([1, 2])
    with col_btn_save:
        if st.button("Save & Update Keys", key="save_keys_btn", use_container_width=True):
            updated_keys = [
                k.strip()
                for k in [new_k1, new_k2, new_k3]
                if k.strip().startswith("nvapi-")
            ]
            if updated_keys:
                _save_keys_to_env(", ".join(updated_keys))
                st.session_state.custom_keys_text = ", ".join(updated_keys)
                _get_key_pool.clear()
                st.success(f"Saved {len(updated_keys)} keys to pool!")
                st.rerun()
            else:
                st.error("Please enter valid keys starting with nvapi-")

    with col_model_sel:
        chosen_model = st.selectbox(
            "Active NIM Model",
            options=available_nvidia_models,
            index=available_nvidia_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_nvidia_models else 0,
            key="model_selector_dropdown",
        )
        if chosen_model != st.session_state.selected_model:
            st.session_state.selected_model = chosen_model
            st.rerun()


# ---------------------------------------------------------------------------
# Upload Section
# ---------------------------------------------------------------------------
uploaded_files = st.file_uploader(
    "Upload resumes",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.upload_key}",
    help=f"PDF, DOCX, or TXT up to {MAX_FILE_SIZE_MB} MB per file.",
    label_visibility="collapsed",
)

if uploaded_files:
    filenames = [f.name for f in uploaded_files]

    # Detect duplicate filenames in current batch
    seen_names: set[str] = set()
    duplicate_names: set[str] = set()
    for name in filenames:
        if name in seen_names:
            duplicate_names.add(name)
        seen_names.add(name)

    chips_html = '<div class="rd-files">'
    for uf in uploaded_files:
        try:
            size_kb = len(uf.getvalue()) / 1024
        except Exception:
            size_kb = (uf.size / 1024) if hasattr(uf, "size") and uf.size else 0.0
        is_dup = uf.name in duplicate_names
        chips_html += (
            f'<div class="rd-file{" dup" if is_dup else ""}">'
            f"{html.escape(uf.name)}<span>{size_kb:.1f} KB{' · duplicate' if is_dup else ''}</span>"
            "</div>"
        )
    chips_html += "</div>"
    st.markdown(chips_html, unsafe_allow_html=True)

    if duplicate_names:
        st.warning(f"Duplicate files detected: {', '.join(duplicate_names)}. Content hash deduplication will process duplicates once.")

    # Reset results if batch has changed
    if st.session_state.processed:
        prev = set(st.session_state.get("_last_filenames", []))
        curr = set(filenames)
        if prev != curr:
            st.session_state.candidates = []
            st.session_state.failed_docs = []
            st.session_state.processed = False
            st.session_state.edited = {}
    st.session_state["_last_filenames"] = filenames


# ---------------------------------------------------------------------------
# Action Bar
# ---------------------------------------------------------------------------
col_btn1, col_btn2, _ = st.columns([1.5, 1, 3])
with col_btn1:
    process_clicked = st.button(
        "Process resumes",
        disabled=not uploaded_files,
        key="process_btn",
        type="primary",
        use_container_width=True,
    )
with col_btn2:
    if st.button("Clear all", key="clear_btn", use_container_width=True):
        _reset_workspace()


# ---------------------------------------------------------------------------
# Processing Workflow (Parallel Multi-Key Engine)
# ---------------------------------------------------------------------------
if process_clicked and uploaded_files and not st.session_state.processed:
    ai_extractor = None
    if not st.session_state.rules_only and pool.total_count > 0:
        config = AIConfig(
            model=st.session_state.selected_model,
            key_pool=pool,
        )
        ai_extractor = AIExtractor(config=config)

    parser = ResumeParser(ai_extractor=ai_extractor)
    reader = DocumentReader()

    # Step 1: Read files and detect duplicates via SHA-256
    doc_results: list[DocumentResult] = []
    seen_hashes: set[str] = set()

    # Deduplicate upload list by filename
    seen_names = set()
    unique_uploads = []
    for uf in uploaded_files:
        if uf.name not in seen_names:
            seen_names.add(uf.name)
            unique_uploads.append(uf)

    progress_bar = st.progress(0, text="Reading documents...")
    status_area = st.empty()

    for uf in unique_uploads:
        raw_bytes = uf.getvalue()
        doc = reader.process_bytes(raw_bytes, uf.name, seen_hashes)
        if doc.file_hash:
            seen_hashes.add(doc.file_hash)
        doc_results.append(doc)

    # Step 2: Parallel Batch Extraction across NVIDIA NIM Multi-Key Pool
    progress_bar.progress(20, text=f"Extracting with {st.session_state.max_workers} parallel workers...")
    logs_holder: list[str] = []

    def _on_progress(completed: int, total: int, item: CandidateRecord | dict):
        pct = 20 + int((completed / total) * 75)
        fn = item.resume_filename if isinstance(item, CandidateRecord) else item.get("filename", "")
        status_label = item.metadata.processing_status if isinstance(item, CandidateRecord) else item.get("doc_status", "error")
        progress_bar.progress(pct, text=f"Processed {fn} ({completed}/{total})...")
        is_ok = isinstance(item, CandidateRecord) and item.metadata.processing_status in ("success", "review_required", "partial")
        line = f'<div class="rd-progress-line {"ok" if is_ok else "bad"}">{"✓" if is_ok else "✗"} {html.escape(fn)} → {html.escape(str(status_label))}</div>'
        logs_holder.append(line)
        status_area.markdown("\n".join(logs_holder[-4:]), unsafe_allow_html=True)

    candidates, failed_docs = parser.parse_batch_parallel(
        doc_results,
        max_workers=st.session_state.max_workers if ai_extractor else 1,
        callback=_on_progress,
    )

    progress_bar.progress(100, text="Extraction complete")
    st.session_state.candidates = candidates
    st.session_state.failed_docs = failed_docs
    st.session_state.processed = True
    st.session_state.edited = {}
    status_area.empty()
    st.rerun()


# ---------------------------------------------------------------------------
# Results Section
# ---------------------------------------------------------------------------
if st.session_state.processed:
    candidates = st.session_state.candidates
    failed_docs = st.session_state.failed_docs

    st.subheader("Results")

    total = len(candidates) + len(failed_docs)
    succeeded = sum(1 for c in candidates if c.metadata.processing_status == "success")
    review = sum(1 for c in candidates if c.metadata.processing_status in ("review_required", "partial"))
    failed = len(failed_docs)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total resumes", total)
    c2.metric("Verified", succeeded)
    c3.metric("Needs review", review)
    c4.metric("Failed", failed)

    # Candidate Overview Table
    if candidates:
        st.write("")
        table_rows = []
        for rec in candidates:
            effective = st.session_state.edited.get(rec.resume_filename, rec)
            edu_str = "; ".join(
                " · ".join(filter(None, [e.qualification, e.institution, e.graduation_year]))
                for e in effective.education
            )
            status = effective.metadata.processing_status
            cfg = _STATUS_CONFIG.get(status, {"label": status})
            table_rows.append({
                "Filename": effective.resume_filename,
                "Candidate Name": effective.full_name or "—",
                "Email": effective.email or "—",
                "Phone": effective.phone or "—",
                "Education": edu_str or "—",
                "Top Skills": ", ".join(effective.technical_skills[:5]) or "—",
                "Status": cfg["label"],
            })
        st.dataframe(table_rows, use_container_width=True, hide_index=True)

    # Failed documents list
    if failed_docs:
        with st.expander(f"Failed documents ({len(failed_docs)})", expanded=False):
            for fd in failed_docs:
                st.markdown(f"- **{fd['filename']}** — `{fd.get('doc_status', 'error')}`: {fd.get('error', 'Unspecified error')}")

    # Inline Editor for Review
    if candidates:
        st.subheader("Review and edit")
        st.caption("Changes you save here are automatically re-validated and included in the exported workbook.")

        for orig_rec in candidates:
            filename = orig_rec.resume_filename
            rec = st.session_state.edited.get(filename, orig_rec)
            status = rec.metadata.processing_status
            cfg = _STATUS_CONFIG.get(status, {"label": status})

            with st.expander(f"{rec.full_name or filename}  ·  {cfg['label']}", expanded=(status == "review_required")):
                if rec.metadata.validation_issues:
                    st.warning("**Validation Notes:**\n" + "\n".join(f"- {i}" for i in rec.metadata.validation_issues))
                if rec.metadata.missing_fields:
                    st.info("**Missing Recommended Fields:** " + ", ".join(rec.metadata.missing_fields))

                with st.form(key=f"edit_form_{filename}"):
                    col1, col2 = st.columns(2)
                    new_name = col1.text_input("Full Name", value=rec.full_name or "", key=f"fn_{filename}")
                    new_email = col2.text_input("Email", value=rec.email or "", key=f"em_{filename}")

                    col3, col4 = st.columns(2)
                    new_phone = col3.text_input("Phone Number", value=rec.phone or "", key=f"ph_{filename}")
                    new_loc = col4.text_input("Location", value=rec.location or "", key=f"lc_{filename}")

                    edu_text = st.text_area(
                        "Education (Qualification | Specialization | Institution | Graduation Year)",
                        value="\n".join(
                            " | ".join(filter(None, [e.qualification, e.specialization, e.institution, e.graduation_year]))
                            for e in rec.education
                        ),
                        height=80,
                        key=f"edu_{filename}",
                    )

                    col5, col6, col7 = st.columns(3)
                    new_skills = col5.text_area("Technical Skills", value=", ".join(rec.technical_skills), height=70, key=f"sk_{filename}")
                    new_langs = col6.text_area("Languages", value=", ".join(rec.programming_languages), height=70, key=f"lg_{filename}")
                    new_tools = col7.text_area("Tools & Libraries", value=", ".join(rec.tools), height=70, key=f"tl_{filename}")

                    exp_text = st.text_area(
                        "Work Experience (Employer | Job Title | Start Date | End Date)",
                        value="\n".join(
                            " | ".join(filter(None, [e.employer, e.job_title, e.start_date, e.end_date]))
                            for e in rec.work_experience
                        ),
                        height=90,
                        key=f"exp_{filename}",
                    )

                    proj_text = st.text_area(
                        "Projects (Project Name | Description | Technologies)",
                        value="\n".join(
                            " | ".join(filter(None, [p.name, p.description, ", ".join(p.technologies)]))
                            for p in rec.projects
                        ),
                        height=80,
                        key=f"prj_{filename}",
                    )

                    col8, col9, col10 = st.columns(3)
                    new_li = col8.text_input("LinkedIn", value=rec.linkedin_url or "", key=f"li_{filename}")
                    new_gh = col9.text_input("GitHub", value=rec.github_url or "", key=f"gh_{filename}")
                    new_pf = col10.text_input("Portfolio", value=rec.portfolio_url or "", key=f"pf_{filename}")

                    new_certs = st.text_input("Certifications (comma-separated)", value=", ".join(rec.certifications), key=f"crt_{filename}")

                    save_submitted = st.form_submit_button("Save changes", use_container_width=True)

                if save_submitted:
                    new_edu: list[EducationRecord] = []
                    for line in edu_text.strip().splitlines():
                        parts = [p.strip() for p in line.split("|")]
                        if any(parts):
                            new_edu.append(EducationRecord(
                                qualification=parts[0] if len(parts) > 0 and parts[0] else None,
                                specialization=parts[1] if len(parts) > 1 and parts[1] else None,
                                institution=parts[2] if len(parts) > 2 and parts[2] else None,
                                graduation_year=parts[3] if len(parts) > 3 and parts[3] else None,
                            ))

                    new_exp: list[WorkExperience] = []
                    for line in exp_text.strip().splitlines():
                        parts = [p.strip() for p in line.split("|")]
                        if any(parts):
                            new_exp.append(WorkExperience(
                                employer=parts[0] if len(parts) > 0 and parts[0] else None,
                                job_title=parts[1] if len(parts) > 1 and parts[1] else None,
                                start_date=parts[2] if len(parts) > 2 and parts[2] else None,
                                end_date=parts[3] if len(parts) > 3 and parts[3] else None,
                            ))

                    new_proj: list[Project] = []
                    for line in proj_text.strip().splitlines():
                        parts = [p.strip() for p in line.split("|")]
                        if any(parts):
                            techs = [t.strip() for t in parts[2].split(",") if t.strip()] if len(parts) > 2 else []
                            new_proj.append(Project(
                                name=parts[0] if len(parts) > 0 and parts[0] else None,
                                description=parts[1] if len(parts) > 1 and parts[1] else None,
                                technologies=techs,
                            ))

                    def _split_csv(s: str) -> list[str]:
                        return [x.strip() for x in s.split(",") if x.strip()]

                    updated_record = CandidateRecord(
                        candidate_id=rec.candidate_id,
                        resume_filename=rec.resume_filename,
                        full_name=new_name.strip() or None,
                        email=new_email.strip() or None,
                        phone=new_phone.strip() or None,
                        location=new_loc.strip() or None,
                        education=new_edu,
                        technical_skills=_split_csv(new_skills),
                        programming_languages=_split_csv(new_langs),
                        tools=_split_csv(new_tools),
                        work_experience=new_exp,
                        projects=new_proj,
                        certifications=_split_csv(new_certs),
                        linkedin_url=new_li.strip() or None,
                        github_url=new_gh.strip() or None,
                        portfolio_url=new_pf.strip() or None,
                        metadata=ExtractionMetadata(
                            processing_status=rec.metadata.processing_status,
                            extraction_method=rec.metadata.extraction_method,
                            model_used=rec.metadata.model_used,
                            key_index_used=rec.metadata.key_index_used,
                            extracted_at=rec.metadata.extracted_at,
                        ),
                        raw_text_snippet=rec.raw_text_snippet,
                    )
                    updated_record = validate_candidate(updated_record)
                    st.session_state.edited[filename] = updated_record
                    st.success(f"Updated record for {filename}")
                    st.rerun()

    # -----------------------------------------------------------------------
    # Export Section
    # -----------------------------------------------------------------------
    final_records = [
        st.session_state.edited.get(rec.resume_filename, rec)
        for rec in st.session_state.candidates
    ]

    if final_records or st.session_state.failed_docs:
        st.subheader("Export")
        try:
            excel_bytes = export_to_bytes(final_records, failed_docs=st.session_state.failed_docs)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dl_filename = f"candidates_{timestamp}.xlsx"

            col_dl1, col_dl2, _ = st.columns([2, 1, 3])
            with col_dl1:
                st.download_button(
                    label=f"⬇ Download Excel workbook ({len(final_records)} candidates)",
                    data=excel_bytes,
                    file_name=dl_filename,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_btn",
                    type="primary",
                    use_container_width=True,
                )
            with col_dl2:
                json_bytes = json.dumps([r.model_dump() for r in final_records], indent=2).encode("utf-8")
                st.download_button(
                    label="⬇ Download JSON",
                    data=json_bytes,
                    file_name=f"candidates_{timestamp}.json",
                    mime="application/json",
                    key="download_json_btn",
                    use_container_width=True,
                )
        except Exception as exc:
            st.error(f"Error creating Excel workbook: {exc}")
