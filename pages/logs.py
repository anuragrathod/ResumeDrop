"""
pages/logs.py
=============
API Call Logs · ResumeDrop
Accessible at: http://localhost:8501/logs or via top navigation.

A simple and neat dashboard displaying every NVIDIA NIM API call made,
including timestamp, model, key used, latency, HTTP status, and error details.
"""

from __future__ import annotations

import html
import os
import re
import streamlit as st

st.set_page_config(
    page_title="API Logs · ResumeDrop",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.ai_extractor import (
    DEFAULT_NVIDIA_MODEL,
    DEFAULT_RATE_LIMIT_RPM,
    NvidiaKeyPool,
    clear_api_call_logs,
    get_api_call_logs,
    make_test_api_call,
)

# ---------------------------------------------------------------------------
# Design System (Minimalist, Apple-inspired Typography & Zero-Pill Discipline)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
:root {
    --bg: #fbfbfd;
    --surface: #ffffff;
    --text: #1d1d1f;
    --muted: #6e6e73;
    --line: rgba(0, 0, 0, 0.10);
    --line-strong: rgba(0, 0, 0, 0.20);
    --accent: #0071e3;
    --accent-hover: #0077ed;
    --ok: #248a3d;
    --ok-bg: rgba(36, 138, 61, 0.08);
    --warn: #b25000;
    --warn-bg: rgba(178, 80, 0, 0.08);
    --bad: #d70015;
    --bad-bg: rgba(215, 0, 21, 0.08);
    --radius: 12px;
    --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
            "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
.stApp, .stApp :where(p, li, label, input, textarea, button, summary, h1, h2, h3, h4, td, th) {
    font-family: var(--font);
    -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--bg); color: var(--text); }
[data-testid="stSidebar"], [data-testid="collapsedControl"], section[data-testid="stSidebar"] { display: none !important; }
.block-container { max-width: 1080px; padding: 2rem 2rem 4rem !important; }

/* Navigation */
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

.rd-title {
    font-size: clamp(2rem, 4vw, 2.5rem);
    font-weight: 700;
    letter-spacing: -0.03em;
    margin: 0.25rem 0 0.25rem 0;
    color: var(--text);
}
.rd-lede { font-size: 1rem; color: var(--muted); margin: 0 0 1.5rem 0; }

/* Metrics */
[data-testid="stMetric"] {
    background: transparent;
    border: none;
    border-top: 1px solid var(--line);
    padding: 0.85rem 0 0 0;
}
[data-testid="stMetricLabel"] p { font-size: 0.82rem; font-weight: 500; color: var(--muted); }
[data-testid="stMetricValue"] div {
    font-size: clamp(1.6rem, 3vw, 2.2rem);
    font-weight: 600;
    letter-spacing: -0.03em;
    color: var(--text);
    font-variant-numeric: tabular-nums;
}

/* Custom neat log table */
.rd-log-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    overflow: hidden;
    margin-top: 1rem;
    font-size: 0.88rem;
}
.rd-log-table th {
    background: #f5f5f7;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    font-size: 0.8rem;
    color: var(--muted);
    border-bottom: 1px solid var(--line);
    letter-spacing: 0.02em;
    text-transform: uppercase;
}
.rd-log-table td {
    padding: 12px 14px;
    border-bottom: 1px solid var(--line);
    color: var(--text);
    vertical-align: middle;
}
.rd-log-table tr:last-child td { border-bottom: none; }
.rd-log-table tr:hover td { background: #fafafa; }

.status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}
.status-badge.success {
    background: var(--ok-bg);
    color: var(--ok);
    border: 1px solid rgba(36, 138, 61, 0.2);
}
.status-badge.rate-limited {
    background: var(--warn-bg);
    color: var(--warn);
    border: 1px solid rgba(178, 80, 0, 0.2);
}
.status-badge.error {
    background: var(--bad-bg);
    color: var(--bad);
    border: 1px solid rgba(215, 0, 21, 0.2);
}

.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 0.82rem; }
.subtext { font-size: 0.76rem; color: var(--muted); margin-top: 2px; }

.rd-empty-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    padding: 3rem 1.5rem;
    text-align: center;
    color: var(--muted);
    margin-top: 1rem;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Navigation Bar
# ---------------------------------------------------------------------------
st.markdown("""
<div class="rd-nav">
    <a href="/" target="_self" class="rd-nav-brand">ResumeDrop</a>
    <div class="rd-nav-links">
        <a href="/" target="_self" class="rd-nav-link">Extractor</a>
        <a href="/logs" target="_self" class="rd-nav-link active">API Logs</a>
        <a href="/e" target="_self" class="rd-nav-link">Raw Text</a>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<h1 class="rd-title">API Call Logs</h1>
<p class="rd-lede">Live outgoing requests to NVIDIA NIM APIs. Displays model, key rotation, latency, and status in real time.</p>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load shared Key Pool and API Logs
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _get_shared_pool() -> NvidiaKeyPool:
    pool = NvidiaKeyPool()
    pool.reload_from_env()
    return pool

pool = _get_shared_pool()
logs = get_api_call_logs()

# Summary Metrics
total_calls = len(logs)
success_calls = sum(1 for e in logs if e.status == "SUCCESS")
rate_limit_calls = sum(1 for e in logs if e.status == "RATE_LIMITED")
failed_calls = sum(1 for e in logs if e.status in ("FAILED", "AUTH_ERROR", "PARSE_ERROR"))

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
col_m1.metric("Total Calls", total_calls)
col_m2.metric("Success (200)", success_calls)
col_m3.metric("Throttled (429)", rate_limit_calls)
col_m4.metric("Errors", failed_calls)
col_m5.metric("Active Keys", f"{pool.active_count}/{pool.total_count}")

st.write("")

# ---------------------------------------------------------------------------
# Action Controls
# ---------------------------------------------------------------------------
act_col1, act_col2, act_col3, _ = st.columns([1.2, 1.6, 1.2, 2.5])

with act_col1:
    if st.button("Refresh logs", key="refresh_logs_btn", use_container_width=True):
        st.rerun()

with act_col2:
    if st.button("⚡ Make Test Call", key="test_api_call_btn", use_container_width=True):
        with st.spinner("Calling NVIDIA NIM..."):
            ok, msg = make_test_api_call(pool=pool)
            if ok:
                st.success(f"Test Call: {msg}")
            else:
                st.error(f"Test Call Failed: {msg}")
        st.rerun()

with act_col3:
    if st.button("Clear logs", key="clear_logs_btn", use_container_width=True):
        clear_api_call_logs()
        st.rerun()

# ---------------------------------------------------------------------------
# Simple & Neat Table Showing Calls and Status
# ---------------------------------------------------------------------------
if not logs:
    st.markdown("""
    <div class="rd-empty-card">
        <p style="font-size: 1.1rem; font-weight: 600; color: var(--text); margin-bottom: 6px;">No API Calls Logged Yet</p>
        <p style="margin: 0;">Upload resumes in the Extractor or click <strong>Make Test Call</strong> above to generate real-time log records.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    table_html = """
    <table class="rd-log-table">
        <thead>
            <tr>
                <th style="width: 10%;">Time</th>
                <th style="width: 25%;">Request / Document</th>
                <th style="width: 23%;">Model</th>
                <th style="width: 18%;">Key Used</th>
                <th style="width: 10%;">Latency</th>
                <th style="width: 14%;">Status</th>
            </tr>
        </thead>
        <tbody>
    """
    for entry in logs:
        # Determine badge style
        if entry.status == "SUCCESS":
            badge_class = "success"
            badge_text = f"200 OK"
        elif entry.status == "RATE_LIMITED":
            badge_class = "rate-limited"
            badge_text = f"429 Throttled"
        elif entry.status == "AUTH_ERROR":
            badge_class = "error"
            badge_text = f"401 Auth Error"
        else:
            badge_class = "error"
            badge_text = f"{entry.http_status} {entry.status}"

        detail_html = ""
        if entry.error_detail:
            detail_html = f'<div class="subtext">{html.escape(entry.error_detail)}</div>'

        latency_display = f"{entry.latency_ms / 1000:.2f}s" if entry.latency_ms >= 1000 else f"{entry.latency_ms:.0f}ms"

        table_html += f"""
        <tr>
            <td class="mono">{html.escape(entry.timestamp)}</td>
            <td>
                <strong>{html.escape(entry.document_name)}</strong>
                {detail_html}
            </td>
            <td class="mono" style="font-size: 0.8rem;">{html.escape(entry.model)}</td>
            <td class="mono" style="font-size: 0.8rem;">{html.escape(entry.key_masked)}</td>
            <td class="mono">{html.escape(latency_display)}</td>
            <td><span class="status-badge {badge_class}">{html.escape(badge_text)}</span></td>
        </tr>
        """

    table_html += """
        </tbody>
    </table>
    """
    st.markdown(table_html, unsafe_allow_html=True)
