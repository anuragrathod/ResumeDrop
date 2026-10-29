"""
pages/e.py
==========
Extracted Text Viewer · ResumeDrop
Accessible in Streamlit sidebar or at: http://localhost:8501/e

A dedicated, minimalist page to upload a resume and inspect the exact text
extracted by DocumentReader (PyMuPDF / python-docx / MarkItDown).
"""

from __future__ import annotations

import html
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="Extracted text · ResumeDrop",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.document_reader import DocumentReader, DocumentResult, ProcessingStatus

# Design system matching app.py
st.markdown("""
<style>
:root {
    --bg: #fbfbfd;
    --surface: #ffffff;
    --text: #1d1d1f;
    --muted: #6e6e73;
    --line: rgba(0, 0, 0, 0.10);
    --accent: #0071e3;
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
.rd-meta { margin: 1rem 0; font-size: 0.95rem; color: var(--text); }
.rd-meta span { color: var(--muted); font-size: 0.85rem; margin-left: 8px; }
[data-testid="stCodeBlock"] {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius);
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="rd-nav">
    <a href="/" target="_self" class="rd-nav-brand">ResumeDrop</a>
    <div class="rd-nav-links">
        <a href="/" target="_self" class="rd-nav-link">Extractor</a>
        <a href="/logs" target="_self" class="rd-nav-link">API Logs</a>
        <a href="/e" target="_self" class="rd-nav-link active">Raw Text</a>
    </div>
</div>
<h1 class="rd-title">Extracted text</h1>
<p class="rd-lede">Upload a resume to inspect the exact text extracted from it by DocumentReader.</p>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Upload a resume (PDF, DOCX, TXT)",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=False,
    key="raw_text_uploader",
    label_visibility="collapsed",
)

if uploaded_file:
    reader = DocumentReader()
    raw_bytes = uploaded_file.getvalue()
    doc_result: DocumentResult = reader.process_bytes(raw_bytes, uploaded_file.name)

    if doc_result.status == ProcessingStatus.SUCCESS:
        text = doc_result.text
        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.splitlines())

        col_info, col_dl = st.columns([3, 1], vertical_alignment="center")
        with col_info:
            st.markdown(
                f'<div class="rd-meta"><strong>{html.escape(uploaded_file.name)}</strong>'
                f"<span>{char_count:,} characters · {word_count:,} words · {line_count:,} lines</span></div>",
                unsafe_allow_html=True,
            )

        with col_dl:
            base_name = Path(uploaded_file.name).stem
            st.download_button(
                label="Download .txt",
                data=text,
                file_name=f"{base_name}_extracted.txt",
                mime="text/plain",
                type="primary",
                use_container_width=True,
                key="download_raw_txt",
            )

        st.code(text, language="text", wrap_lines=True)
    else:
        st.error(f"Failed to extract text from {uploaded_file.name}: {doc_result.error}")
else:
    st.info("Upload a resume above to see its extracted text.")
