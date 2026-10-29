"""
app.py
======
ResumeDrop — Modern Pure Python Web Application (FastAPI).
High-throughput resume extraction & 5-sheet Excel workbook automation
powered by Multi-Key NVIDIA NIM Pool (40 RPM) and Server-Sent Events (SSE).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load environment variables
try:
    import dotenv
    _env_path = BASE_DIR / ".env"
    if _env_path.exists():
        dotenv.load_dotenv(dotenv_path=_env_path, override=True)
    else:
        dotenv.load_dotenv(override=True)
except ImportError:
    pass

from schemas.candidate import CandidateRecord
from src.ai_extractor import (
    DEFAULT_NVIDIA_MODEL,
    AIExtractor,
    NvidiaKeyPool,
    check_nvidia_available,
    clear_api_call_logs,
    get_api_call_logs,
    make_test_api_call,
)
from src.document_reader import DocumentReader, DocumentResult, ProcessingStatus
from src.excel_exporter import export_to_bytes
from src.resume_parser import ResumeParser

logger = logging.getLogger("resumedrop")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Initialize FastAPI application
app = FastAPI(
    title="ResumeDrop",
    description="Resume-to-Excel automation system extracting candidate profiles into formatted 5-sheet workbooks.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory SSE queues mapped by session_id
_SSE_QUEUES: dict[str, asyncio.Queue] = {}
_SSE_LOCK = asyncio.Lock()


# ---------------------------------------------------------------------------
# Frontend Shell Routes (Single Page Application)
# ---------------------------------------------------------------------------
@app.get("/", response_class=FileResponse)
async def serve_home():
    """Serve the single-page application shell."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="static/index.html not found")
    return FileResponse(str(index_path))


@app.get("/logs", response_class=FileResponse)
async def serve_logs():
    """Serve the application shell with logs view active."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="static/index.html not found")
    return FileResponse(str(index_path))


# ---------------------------------------------------------------------------
# API Logs Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/logs")
async def get_logs():
    """
    Return recent outbound API calls formatted strictly for the 5-column display:
    Time, Used for (Type), Model, Latency, Status.
    """
    records = get_api_call_logs()
    formatted = []
    for r in records:
        formatted.append({
            "id": r.id,
            "timestamp": r.timestamp,
            "used_for": r.document_name or "Resume Extraction",
            "model": r.model,
            "latency_ms": r.latency_ms,
            "status": r.status,
            "http_status": r.http_status,
        })
    return {"logs": formatted}


@app.post("/api/clear-logs")
async def clear_logs():
    """Clear in-memory API call logs."""
    clear_api_call_logs()
    return {"status": "cleared"}


@app.post("/api/check-connection")
async def check_connection():
    """
    Probe the NVIDIA NIM endpoints and report whether all APIs are operational.
    Crucial requirement: NO API keys or credentials are exposed in the output,
    and messages are clean and safe for the auto-dismissing banner.
    """
    loop = asyncio.get_running_loop()
    # Run test completion call across pool in thread
    success, detail = await loop.run_in_executor(None, make_test_api_call)

    if success:
        return {
            "success": True,
            "message": "All APIs are operational and working.",
        }
    else:
        # Sanitize error detail to never leak raw key or tokens
        safe_msg = "API connection check failed. Please verify network access or rate limit cooldown."
        if "rate limit" in detail.lower():
            safe_msg = "API rate limit reached (40 RPM limit). Please wait for cooldown."
        elif "invalid" in detail.lower() or "401" in detail:
            safe_msg = "Authentication failure on API key. Please check configured credentials."
        elif "timeout" in detail.lower():
            safe_msg = "Connection timed out reaching NVIDIA NIM endpoint."
        return {
            "success": False,
            "message": safe_msg,
        }


# ---------------------------------------------------------------------------
# Server-Sent Events (SSE) for Real-Time Load Bar
# ---------------------------------------------------------------------------
@app.get("/api/events")
async def sse_events(session_id: str):
    """
    Stream real-time resume parsing progress to the browser client.
    Powers the real load bar with actual processed resume counts.
    """
    async with _SSE_LOCK:
        if session_id not in _SSE_QUEUES:
            _SSE_QUEUES[session_id] = asyncio.Queue()
        queue = _SSE_QUEUES[session_id]

    async def event_generator():
        try:
            while True:
                try:
                    # Wait for next event with a 30s keep-alive timeout
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(data)}\n\n"
                    if data.get("type") in ("complete", "fatal_error"):
                        break
                except asyncio.TimeoutError:
                    # Send comment to keep connection alive
                    yield ": ping\n\n"
        finally:
            async with _SSE_LOCK:
                _SSE_QUEUES.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Resume Processing Pipeline
# ---------------------------------------------------------------------------
async def _push_sse_event(session_id: str, data: dict[str, Any]) -> None:
    async with _SSE_LOCK:
        queue = _SSE_QUEUES.get(session_id)
    if queue:
        await queue.put(data)


@app.post("/api/process")
async def process_resumes(
    files: list[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
):
    """
    Upload and parse one or more resumes concurrently, streaming real-time
    progress updates to the frontend SSE listener.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    # Read all uploaded file contents into memory
    file_payloads: list[tuple[str, bytes]] = []
    for file in files:
        content = await file.read()
        file_payloads.append((file.filename or "resume.pdf", content))

    total = len(file_payloads)
    sid = session_id or f"session_{int(time.time() * 1000)}"

    # Ensure queue exists
    async with _SSE_LOCK:
        if sid not in _SSE_QUEUES:
            _SSE_QUEUES[sid] = asyncio.Queue()

    # Launch processing in background task to stream progress
    asyncio.create_task(_run_batch_extraction(file_payloads, sid, total))

    return {"status": "started", "session_id": sid, "total_files": total}


async def _run_batch_extraction(
    file_payloads: list[tuple[str, bytes]],
    session_id: str,
    total: int,
):
    """Background task processing documents and pushing progress to SSE."""
    reader = DocumentReader()
    parser = ResumeParser()
    loop = asyncio.get_running_loop()

    completed = 0

    for idx, (filename, raw_bytes) in enumerate(file_payloads):
        # 1. Document text extraction
        doc_result: DocumentResult = await loop.run_in_executor(
            None, reader.process_bytes, raw_bytes, filename
        )

        cand_data = None
        if doc_result.status == ProcessingStatus.SUCCESS:
            try:
                # 2. AI & Rule-based extraction via multi-key NVIDIA NIM pool
                cand_record = await loop.run_in_executor(
                    None, parser.parse, doc_result
                )
                cand_data = cand_record.model_dump()
                # Format highest degree for display
                cand_data["highest_degree"] = cand_record.highest_degree
                cand_data["status"] = cand_record.metadata.processing_status
            except Exception as exc:
                logger.error("Failed to parse resume %s: %s", filename, exc)
                cand_data = {
                    "full_name": Path(filename).stem,
                    "email": "—",
                    "phone": "—",
                    "location": "—",
                    "highest_degree": "—",
                    "years_of_experience": 0,
                    "status": "failed",
                    "education": [],
                    "work_experience": [],
                    "technical_skills": [],
                }
        else:
            logger.warning("DocumentReader failed on %s: %s", filename, doc_result.error)
            cand_data = {
                "full_name": Path(filename).stem,
                "email": "—",
                "phone": "—",
                "location": "—",
                "highest_degree": "—",
                "years_of_experience": 0,
                "status": "failed",
                "education": [],
                "work_experience": [],
                "technical_skills": [],
            }

        completed += 1
        await _push_sse_event(session_id, {
            "type": "progress",
            "completed": completed,
            "total": total,
            "filename": filename,
            "candidate": cand_data,
        })

    # All files completed
    await _push_sse_event(session_id, {
        "type": "complete",
        "completed": completed,
        "total": total,
    })


# ---------------------------------------------------------------------------
# Excel Workbook Export Endpoint
# ---------------------------------------------------------------------------
class ExportRequest(BaseModel):
    candidates: list[dict[str, Any]]


@app.post("/api/export")
async def export_candidates_excel(req: ExportRequest):
    """
    Generate and stream formatted 5-sheet Excel workbook from extracted candidates.
    """
    if not req.candidates:
        raise HTTPException(status_code=400, detail="No candidates provided for export.")

    candidate_records: list[CandidateRecord] = []
    for c_dict in req.candidates:
        fn = c_dict.get("resume_filename") or f"{(c_dict.get('full_name') or 'candidate').lower().replace(' ', '_')}.pdf"
        try:
            dict_copy = dict(c_dict)
            dict_copy.setdefault("resume_filename", fn)
            cand = CandidateRecord(**dict_copy)
            candidate_records.append(cand)
        except Exception:
            # Fallback construct
            cand = CandidateRecord(
                resume_filename=fn,
                full_name=c_dict.get("full_name") or "Candidate",
                email=c_dict.get("email") or "",
                phone=c_dict.get("phone") or "",
                location=c_dict.get("location") or "",
                technical_skills=c_dict.get("technical_skills") or [],
            )
            candidate_records.append(cand)

    loop = asyncio.get_running_loop()
    excel_bytes = await loop.run_in_executor(
        None, export_to_bytes, candidate_records, []
    )

    filename = f"resumedrop_export_{int(time.time())}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


# ---------------------------------------------------------------------------
# Direct Launch Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 3000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")
