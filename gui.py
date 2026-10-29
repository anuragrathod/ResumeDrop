"""
gui.py
======
ResumeDrop — Modern Desktop GUI for Resume Extraction & Excel Automation.
Built exclusively in Python using Tkinter & ttk.

Features:
- Pure Python desktop interface (Windows & Linux compatible)
- Multi-file & folder batch queue (PDF, DOCX, TXT)
- Multi-threaded non-blocking extraction worker with progress bar
- Multi-key NVIDIA NIM pool (3 keys, 40 RPM limit) with automatic failover
- Structured candidate Treeview table with status indicators
- Candidate Detail & Inline Review modal
- 5-Worksheet styled Excel (.xlsx) export
"""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
from pathlib import Path
from typing import Any, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from schemas.candidate import CandidateRecord
from src.ai_extractor import AIExtractor, NvidiaKeyPool
from src.document_reader import DocumentReader, DocumentResult, ProcessingStatus
from src.excel_exporter import export_to_file
from src.resume_parser import ResumeParser

logger = logging.getLogger(__name__)


class ResumeDropApp:
    """Main desktop application class for ResumeDrop."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ResumeDrop — AI Resume Extraction & Excel Automation")
        self.root.geometry("1180x760")
        self.root.minsize(980, 640)

        # Application state
        self.queued_files: list[Path] = []
        self.extracted_candidates: list[CandidateRecord] = []
        self.failed_documents: list[dict[str, Any]] = []
        self.is_processing = False
        self.stop_requested = False
        self.ui_queue: queue.Queue = queue.Queue()

        # Engine instances
        self.doc_reader = DocumentReader()
        self.key_pool = NvidiaKeyPool.from_env()
        self.ai_extractor: Optional[AIExtractor] = None

        # Build styles and UI
        self._setup_styles()
        self._build_ui()
        self._verify_keys_on_load()

        # Start periodic queue polling for thread-safe UI updates
        self.root.after(100, self._process_ui_queue)

    def _setup_styles(self) -> None:
        """Configure modern ttk styles."""
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        # Primary palette
        self.bg_color = "#F8FAFC"
        self.surface_color = "#FFFFFF"
        self.primary_color = "#1E40AF"      # Deep Blue
        self.primary_active = "#1D4ED8"
        self.text_primary = "#0F172A"       # Slate 900
        self.text_secondary = "#475569"     # Slate 600
        self.border_color = "#E2E8F0"
        self.success_color = "#16A34A"
        self.warning_color = "#D97706"
        self.danger_color = "#DC2626"

        self.root.configure(bg=self.bg_color)

        self.style.configure(".", background=self.bg_color, foreground=self.text_primary, font=("Segoe UI", 10))
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("Surface.TFrame", background=self.surface_color, relief="solid", borderwidth=1)
        self.style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground=self.primary_color, background=self.bg_color)
        self.style.configure("Subheader.TLabel", font=("Segoe UI", 10), foreground=self.text_secondary, background=self.bg_color)
        self.style.configure("Status.TLabel", font=("Segoe UI", 10, "italic"), foreground=self.text_secondary, background=self.bg_color)

        # Buttons
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=self.primary_color, foreground="#FFFFFF")
        self.style.map("Primary.TButton", background=[("active", self.primary_active)])

        self.style.configure("Secondary.TButton", font=("Segoe UI", 10), background="#F1F5F9", foreground=self.text_primary)
        self.style.map("Secondary.TButton", background=[("active", "#E2E8F0")])

        # Treeview styling
        self.style.configure(
            "Treeview",
            background=self.surface_color,
            fieldbackground=self.surface_color,
            foreground=self.text_primary,
            rowheight=28,
            font=("Segoe UI", 9),
        )
        self.style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background="#F1F5F9",
            foreground=self.text_primary,
            relief="flat",
        )
        self.style.map("Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", "#1E3A8A")])

    def _build_ui(self) -> None:
        """Construct the visual desktop layout."""
        # Top Header Bar
        header_frame = ttk.Frame(self.root, padding="16 12 16 12")
        header_frame.pack(fill=tk.X)

        title_container = ttk.Frame(header_frame)
        title_container.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(title_container, text="ResumeDrop", style="Header.TLabel").pack(anchor=tk.W)
        ttk.Label(
            title_container,
            text="High-Speed AI Resume Extraction & 5-Worksheet Excel Automation",
            style="Subheader.TLabel",
        ).pack(anchor=tk.W)

        # Engine Config in Header
        config_frame = ttk.Frame(header_frame)
        config_frame.pack(side=tk.RIGHT, fill=tk.Y)

        key_count = len(self.key_pool.keys)
        pool_status_text = f"API Keys: {key_count} in pool" if key_count > 0 else "API Keys: Rules Only (Offline)"
        self.lbl_pool_status = ttk.Label(
            config_frame,
            text=pool_status_text,
            font=("Segoe UI", 9, "bold"),
            foreground=self.success_color if key_count > 0 else self.warning_color,
        )
        self.lbl_pool_status.pack(side=tk.LEFT, padx=12)

        ttk.Label(config_frame, text="Model:").pack(side=tk.LEFT, padx=4)
        self.model_var = tk.StringVar(value=os.getenv("DEFAULT_NVIDIA_MODEL", "meta/llama-3.3-70b-instruct"))
        self.model_combo = ttk.Combobox(
            config_frame,
            textvariable=self.model_var,
            values=[
                "meta/llama-3.3-70b-instruct",
                "nvidia/llama-3.1-nemotron-70b-instruct",
                "deepseek-ai/deepseek-r1",
                "mistralai/mistral-large-2-instruct",
            ],
            state="readonly",
            width=28,
        )
        self.model_combo.pack(side=tk.LEFT, padx=4)

        ttk.Label(config_frame, text="Workers:").pack(side=tk.LEFT, padx=(12, 4))
        self.workers_var = tk.IntVar(value=int(os.getenv("MAX_WORKERS", "3")))
        self.spin_workers = ttk.Spinbox(config_frame, from_=1, to=8, width=3, textvariable=self.workers_var)
        self.spin_workers.pack(side=tk.LEFT)

        # Separator line
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=4)

        # Main Content Split (PanedWindow: Left Queue / Right Grid & Details)
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)

        # Left Queue Panel
        queue_frame = ttk.LabelFrame(self.paned, text=" Resume Queue ", padding="10")
        self.paned.add(queue_frame, weight=1)

        btn_box = ttk.Frame(queue_frame)
        btn_box.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(btn_box, text="+ Add Files", style="Primary.TButton", command=self._add_files).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_box, text="+ Add Folder", style="Secondary.TButton", command=self._add_folder).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_box, text="Clear", style="Secondary.TButton", command=self._clear_queue).pack(side=tk.RIGHT)

        # Queue Listbox with scrollbar
        list_container = ttk.Frame(queue_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        self.queue_list = tk.Listbox(
            list_container,
            bg=self.surface_color,
            fg=self.text_primary,
            selectbackground="#DBEAFE",
            selectforeground="#1E3A8A",
            relief="solid",
            borderwidth=1,
            highlightthickness=0,
            font=("Segoe UI", 9),
        )
        queue_scroll = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self.queue_list.yview)
        self.queue_list.configure(yscrollcommand=queue_scroll.set)
        self.queue_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        queue_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.lbl_queue_count = ttk.Label(queue_frame, text="0 documents in queue", style="Status.TLabel")
        self.lbl_queue_count.pack(anchor=tk.W, pady=(6, 0))

        # Right Panel (Results Treeview & Inspection)
        results_frame = ttk.LabelFrame(self.paned, text=" Extracted Candidates ", padding="10")
        self.paned.add(results_frame, weight=3)

        # Treeview for candidate records
        tree_container = ttk.Frame(results_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        cols = ("idx", "name", "email", "phone", "location", "degree", "exp", "status")
        self.tree = ttk.Treeview(tree_container, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("idx", text="#")
        self.tree.heading("name", text="Full Name")
        self.tree.heading("email", text="Email")
        self.tree.heading("phone", text="Phone")
        self.tree.heading("location", text="Location")
        self.tree.heading("degree", text="Highest Degree")
        self.tree.heading("exp", text="Exp (Yrs)")
        self.tree.heading("status", text="Status")

        self.tree.column("idx", width=36, anchor=tk.CENTER)
        self.tree.column("name", width=140, anchor=tk.W)
        self.tree.column("email", width=170, anchor=tk.W)
        self.tree.column("phone", width=120, anchor=tk.W)
        self.tree.column("location", width=110, anchor=tk.W)
        self.tree.column("degree", width=110, anchor=tk.W)
        self.tree.column("exp", width=70, anchor=tk.CENTER)
        self.tree.column("status", width=90, anchor=tk.CENTER)

        tree_y_scroll = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        tree_x_scroll = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_y_scroll.set, xscrollcommand=tree_x_scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        tree_x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # Quick action row under treeview
        tree_action_frame = ttk.Frame(results_frame)
        tree_action_frame.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(
            tree_action_frame,
            text="Tip: Double-click any candidate to review, inspect, or edit details.",
            style="Status.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Button(tree_action_frame, text="Edit Selected Candidate", style="Secondary.TButton", command=self._edit_selected_candidate).pack(side=tk.RIGHT)

        # Bottom Progress & Action Bar
        bottom_frame = ttk.Frame(self.root, padding="16 10 16 16")
        bottom_frame.pack(fill=tk.X)

        progress_container = ttk.Frame(bottom_frame)
        progress_container.pack(fill=tk.X, pady=(0, 8))

        self.progress_bar = ttk.Progressbar(progress_container, orient=tk.HORIZONTAL, mode="determinate")
        self.progress_bar.pack(fill=tk.X)

        status_box = ttk.Frame(progress_container)
        status_box.pack(fill=tk.X, pady=(4, 0))
        self.lbl_progress_status = ttk.Label(status_box, text="Ready. Add resumes to start.", style="Status.TLabel")
        self.lbl_progress_status.pack(side=tk.LEFT)

        self.lbl_stats = ttk.Label(status_box, text="", font=("Segoe UI", 9, "bold"), foreground=self.primary_color)
        self.lbl_stats.pack(side=tk.RIGHT)

        # Primary Action Buttons
        actions_box = ttk.Frame(bottom_frame)
        actions_box.pack(fill=tk.X)

        self.btn_start = ttk.Button(actions_box, text="▶  Start Extraction", style="Primary.TButton", command=self._start_processing)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = ttk.Button(actions_box, text="⏹  Stop", style="Secondary.TButton", command=self._stop_processing, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_export = ttk.Button(
            actions_box,
            text="📥  Export to Excel (.xlsx)",
            style="Primary.TButton",
            command=self._export_excel,
            state=tk.DISABLED,
        )
        self.btn_export.pack(side=tk.RIGHT)

    def _verify_keys_on_load(self) -> None:
        """Check whether configured API keys are connected whenever app is loaded."""
        if not self.key_pool.keys:
            self.lbl_pool_status.config(
                text="API Keys: None (Rules-Only Offline)",
                foreground=self.warning_color,
            )
            return

        def _check_bg() -> None:
            try:
                from src.ai_extractor import check_nvidia_available
                is_connected, msg = check_nvidia_available(self.key_pool)
                if is_connected:
                    self.ui_queue.put(("pool_status", f"NVIDIA NIM: Connected ({self.key_pool.active_count}/{self.key_pool.total_count} active)", self.success_color))
                else:
                    self.ui_queue.put(("pool_status", "NVIDIA NIM: Offline / Fallback", self.warning_color))
            except Exception:
                self.ui_queue.put(("pool_status", "NVIDIA NIM: Offline (Rule-Based)", self.warning_color))

        threading.Thread(target=_check_bg, daemon=True).start()

    # -----------------------------------------------------------------------
    # Queue Management
    # -----------------------------------------------------------------------

    def _add_files(self) -> None:
        """Add individual files to queue."""
        files = filedialog.askopenfilenames(
            title="Select Resumes",
            filetypes=[("Resume Files", "*.pdf *.docx *.txt"), ("PDF Documents", "*.pdf"), ("Word Documents", "*.docx"), ("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not files:
            return

        added = 0
        for f in files:
            p = Path(f)
            if p not in self.queued_files and p.is_file():
                self.queued_files.append(p)
                self.queue_list.insert(tk.END, f"📄 {p.name}")
                added += 1

        self._update_queue_label()

    def _add_folder(self) -> None:
        """Add all supported files in a chosen directory."""
        folder = filedialog.askdirectory(title="Select Folder Containing Resumes")
        if not folder:
            return

        path = Path(folder)
        added = 0
        for item in sorted(path.iterdir()):
            if item.is_file() and item.suffix.lower() in (".pdf", ".docx", ".txt"):
                if item not in self.queued_files:
                    self.queued_files.append(item)
                    self.queue_list.insert(tk.END, f"📄 {item.name}")
                    added += 1

        self._update_queue_label()

    def _clear_queue(self) -> None:
        """Clear queued documents."""
        if self.is_processing:
            messagebox.showwarning("Busy", "Cannot clear queue while extraction is in progress.")
            return

        self.queued_files.clear()
        self.queue_list.delete(0, tk.END)
        self._update_queue_label()

    def _update_queue_label(self) -> None:
        count = len(self.queued_files)
        self.lbl_queue_count.config(text=f"{count} document(s) in queue")

    # -----------------------------------------------------------------------
    # Background Processing & Thread-Safe UI Updates
    # -----------------------------------------------------------------------

    def _start_processing(self) -> None:
        """Initiate background thread for extraction."""
        if not self.queued_files:
            messagebox.showinfo("Queue Empty", "Please add at least one resume file (.pdf, .docx, or .txt).")
            return

        # Initialize AI extractor if keys are present
        try:
            self.key_pool = NvidiaKeyPool.from_env()
            self.ai_extractor = AIExtractor(
                pool=self.key_pool,
                default_model=self.model_var.get(),
            )
        except Exception as e:
            logger.warning(f"Could not initialize AIExtractor: {e}. Falling back to rule-based.")
            self.ai_extractor = None

        self.is_processing = True
        self.stop_requested = False
        self.extracted_candidates.clear()
        self.failed_documents.clear()
        self.tree.delete(*self.tree.get_children())

        # Update button states
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_export.config(state=tk.DISABLED)
        self.progress_bar.config(value=0, maximum=len(self.queued_files))
        self.lbl_progress_status.config(text=f"Reading {len(self.queued_files)} documents...")

        # Spawn worker thread
        t = threading.Thread(target=self._worker_thread_run, daemon=True)
        t.start()

    def _stop_processing(self) -> None:
        """Request graceful cancellation."""
        self.stop_requested = True
        self.lbl_progress_status.config(text="Stopping batch...")

    def _worker_thread_run(self) -> None:
        """Background extraction worker."""
        total_files = len(self.queued_files)
        workers = max(1, min(self.workers_var.get(), total_files))

        try:
            # Step 1: Read all documents
            self.ui_queue.put(("status", "Parsing document text (PyMuPDF & python-docx)..."))
            doc_results: list[DocumentResult] = self.doc_reader.process_files(self.queued_files)

            # Step 2: Parse resumes via ResumeParser
            parser = ResumeParser(
                ai_extractor=self.ai_extractor,
            )

            completed = 0
            for doc in doc_results:
                if self.stop_requested:
                    self.ui_queue.put(("status", "Batch cancelled by user."))
                    break

                if doc.status != ProcessingStatus.SUCCESS:
                    f_info = {
                        "filename": doc.filename,
                        "doc_status": doc.status.value,
                        "error": doc.error,
                        "char_count": doc.char_count,
                    }
                    self.failed_documents.append(f_info)
                    completed += 1
                    self.ui_queue.put(("doc_failed", f_info, completed, total_files))
                    continue

                # Parse single document
                self.ui_queue.put(("status", f"Extracting [{completed+1}/{total_files}]: {doc.filename}..."))
                cand = parser.parse(doc)
                self.extracted_candidates.append(cand)
                completed += 1
                self.ui_queue.put(("candidate_done", cand, completed, total_files))

            self.ui_queue.put(("finished", None))

        except Exception as exc:
            logger.exception("Worker thread failure")
            self.ui_queue.put(("error", str(exc)))

    def _process_ui_queue(self) -> None:
        """Read UI updates posted from background worker."""
        try:
            while True:
                msg_type, payload, *extra = self.ui_queue.get_nowait()

                if msg_type == "status":
                    self.lbl_progress_status.config(text=payload)

                elif msg_type == "pool_status":
                    status_text = payload
                    status_color = extra[0] if extra else self.success_color
                    self.lbl_pool_status.config(text=status_text, foreground=status_color)

                elif msg_type == "candidate_done":
                    cand: CandidateRecord = payload
                    completed, total = extra[0], extra[1]
                    self.progress_bar.config(value=completed)

                    # Insert row in Treeview
                    idx = len(self.extracted_candidates)
                    status_text = cand.metadata.processing_status
                    row_id = self.tree.insert(
                        "",
                        tk.END,
                        values=(
                            idx,
                            cand.full_name or "N/A",
                            cand.email or "N/A",
                            cand.phone or "N/A",
                            cand.location or "N/A",
                            cand.highest_degree or "N/A",
                            cand.years_of_experience or 0,
                            status_text,
                        ),
                    )
                    # Color status
                    if status_text == "success":
                        self.tree.item(row_id, tags=("success",))
                    elif status_text == "failed":
                        self.tree.item(row_id, tags=("danger",))
                    else:
                        self.tree.item(row_id, tags=("warning",))

                elif msg_type == "doc_failed":
                    f_info = payload
                    completed, total = extra[0], extra[1]
                    self.progress_bar.config(value=completed)
                    idx = len(self.extracted_candidates) + len(self.failed_documents)
                    self.tree.insert(
                        "",
                        tk.END,
                        values=(
                            idx,
                            f_info["filename"],
                            "—",
                            "—",
                            "—",
                            "—",
                            0,
                            f"failed ({f_info.get('doc_status')})",
                        ),
                    )

                elif msg_type == "finished":
                    self.is_processing = False
                    self.btn_start.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                    if self.extracted_candidates:
                        self.btn_export.config(state=tk.NORMAL)

                    success_cnt = len(self.extracted_candidates)
                    fail_cnt = len(self.failed_documents)
                    self.lbl_progress_status.config(text=f"Completed. {success_cnt} candidates extracted, {fail_cnt} failed.")
                    self.lbl_stats.config(text=f"Total: {success_cnt + fail_cnt} | Success: {success_cnt} | Issues: {fail_cnt}")

                elif msg_type == "error":
                    self.is_processing = False
                    self.btn_start.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                    messagebox.showerror("Error", f"Processing error: {payload}")
                    self.lbl_progress_status.config(text="An error occurred.")

        except queue.Empty:
            pass

        # Reschedule check
        self.root.after(100, self._process_ui_queue)

    # -----------------------------------------------------------------------
    # Candidate Detail Inspector Modal
    # -----------------------------------------------------------------------

    def _on_tree_double_click(self, event: Any) -> None:
        self._edit_selected_candidate()

    def _edit_selected_candidate(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Selection Required", "Please select a candidate in the table to review.")
            return

        item = self.tree.item(selected[0])
        idx_val = item["values"][0]

        try:
            cand_idx = int(idx_val) - 1
            if 0 <= cand_idx < len(self.extracted_candidates):
                cand = self.extracted_candidates[cand_idx]
                self._open_candidate_modal(cand, selected[0])
            else:
                messagebox.showinfo("Document Failed", "This document failed reading and has no candidate record to inspect.")
        except (ValueError, IndexError):
            pass

    def _open_candidate_modal(self, cand: CandidateRecord, tree_item_id: str) -> None:
        """Open editable modal for candidate review."""
        modal = tk.Toplevel(self.root)
        modal.title(f"Candidate Review — {cand.full_name or 'Unnamed'}")
        modal.geometry("640x560")
        modal.transient(self.root)
        modal.grab_set()

        form_frame = ttk.Frame(modal, padding="16")
        form_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(form_frame, text=f"Review: {cand.resume_filename}", font=("Segoe UI", 12, "bold"), foreground=self.primary_color).pack(anchor=tk.W, pady=(0, 12))

        # Fields
        def make_field(label: str, initial_val: str) -> tk.StringVar:
            row = ttk.Frame(form_frame)
            row.pack(fill=tk.X, pady=4)
            ttk.Label(row, text=label, width=16, anchor=tk.W, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
            var = tk.StringVar(value=initial_val)
            entry = ttk.Entry(row, textvariable=var)
            entry.pack(side=tk.RIGHT, fill=tk.X, expand=True)
            return var

        name_var = make_field("Full Name:", cand.full_name or "")
        email_var = make_field("Email:", cand.email or "")
        phone_var = make_field("Phone:", cand.phone or "")
        loc_var = make_field("Location:", cand.location or "")
        degree_var = make_field("Highest Degree:", cand.highest_degree or "")

        all_skills = cand.technical_skills + cand.programming_languages
        skills_var = make_field("Skills (comma):", ", ".join(all_skills))

        # Issues box
        if cand.metadata.validation_issues:
            issues_box = ttk.LabelFrame(form_frame, text=" Validation Warnings ", padding="8")
            issues_box.pack(fill=tk.X, pady=10)
            for iss in cand.metadata.validation_issues:
                ttk.Label(issues_box, text=f"• {iss}", foreground=self.danger_color, font=("Segoe UI", 8)).pack(anchor=tk.W)

        # Raw snippet preview
        if cand.raw_text_snippet:
            snip_frame = ttk.LabelFrame(form_frame, text=" Document Text Snippet ", padding="8")
            snip_frame.pack(fill=tk.BOTH, expand=True, pady=6)
            txt = tk.Text(snip_frame, height=6, bg="#F8FAFC", wrap=tk.WORD, font=("Consolas", 8))
            txt.insert("1.0", cand.raw_text_snippet)
            txt.config(state=tk.DISABLED)
            txt.pack(fill=tk.BOTH, expand=True)

        # Save & Close Buttons
        btn_row = ttk.Frame(form_frame)
        btn_row.pack(fill=tk.X, pady=(12, 0))

        def save_changes() -> None:
            cand.full_name = name_var.get().strip() or None
            cand.email = email_var.get().strip() or None
            cand.phone = phone_var.get().strip() or None
            cand.location = loc_var.get().strip() or None
            cand.highest_degree = degree_var.get().strip() or None
            cand.technical_skills = [s.strip() for s in skills_var.get().split(",") if s.strip()]

            # Update Treeview row
            idx_val = self.tree.item(tree_item_id)["values"][0]
            self.tree.item(
                tree_item_id,
                values=(
                    idx_val,
                    cand.full_name or "N/A",
                    cand.email or "N/A",
                    cand.phone or "N/A",
                    cand.location or "N/A",
                    cand.highest_degree or "N/A",
                    cand.years_of_experience or 0,
                    cand.metadata.processing_status,
                ),
            )
            modal.destroy()
            messagebox.showinfo("Updated", "Candidate details updated successfully.")

        ttk.Button(btn_row, text="Save Changes", style="Primary.TButton", command=save_changes).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_row, text="Cancel", style="Secondary.TButton", command=modal.destroy).pack(side=tk.RIGHT)

    # -----------------------------------------------------------------------
    # Excel Export
    # -----------------------------------------------------------------------

    def _export_excel(self) -> None:
        """Export candidates to 5-worksheet Excel workbook."""
        if not self.extracted_candidates:
            messagebox.showinfo("No Data", "No candidate records available to export.")
            return

        dest = filedialog.asksaveasfilename(
            title="Export Candidate Workbook",
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")],
            initialfile="candidates_export.xlsx",
        )
        if not dest:
            return

        try:
            out_path = export_to_file(
                records=self.extracted_candidates,
                output_path=dest,
                failed_docs=self.failed_documents,
            )
            messagebox.showinfo(
                "Export Complete",
                f"Successfully exported {len(self.extracted_candidates)} candidate(s) to:\n{out_path}\n\nWorksheets:\n1. Candidates\n2. Education\n3. Work Experience\n4. Projects\n5. Processing Log",
            )
        except Exception as e:
            logger.exception("Excel export error")
            messagebox.showerror("Export Failed", f"Could not write Excel workbook: {e}")


def main() -> None:
    root = tk.Tk()
    app = ResumeDropApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
