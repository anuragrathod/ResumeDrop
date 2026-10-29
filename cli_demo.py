"""
cli_demo.py
===========
Command-line text extraction and resume parsing tool for ResumeDrop.

Features:
- Fast document text extraction (PyMuPDF for PDF, python-docx for DOCX, MarkItDown/utf-8 for TXT)
- Candidate structured extraction (Rule-based or AI-assisted via NVIDIA NIM pool)
- 5-sheet styled Excel workbook export (Candidates, Education, Work Experience, Projects, Log)

Usage:
    # Text extraction preview
    python cli_demo.py sample_resumes/alice_chen_resume.pdf --verbose

    # Process all resumes in sample_resumes/
    python cli_demo.py --dir sample_resumes/

    # Full structured extraction and export to Excel:
    python cli_demo.py --dir sample_resumes/ --extract --export output/candidates.xlsx --verbose
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.document_reader import DocumentReader, ProcessingStatus
from src.resume_parser import ResumeParser
from src.excel_exporter import export_to_file


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ResumeDrop CLI: High-Speed Resume Extraction & Excel Export",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="*", help="Paths to PDF, DOCX, or TXT files")
    parser.add_argument("--dir", type=str, default="sample_resumes", help="Directory containing resumes (default: sample_resumes)")
    parser.add_argument("--extract", "-e", action="store_true", help="Perform structured entity extraction into CandidateRecord")
    parser.add_argument("--export", type=str, default=None, help="Export candidates to multi-sheet Excel file (.xlsx)")
    parser.add_argument("--use-ai", action="store_true", help="Enable NVIDIA NIM AI extractor (uses NVIDIA_API_KEY_1..3 pool)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed extracted fields / text preview")
    args = parser.parse_args()

    target_files: list[Path] = []
    if args.files:
        target_files = [Path(f) for f in args.files]
    else:
        d = Path(args.dir)
        if d.exists() and d.is_dir():
            target_files = sorted([
                p for p in d.iterdir()
                if p.is_file() and p.suffix.lower() in (".pdf", ".docx", ".txt")
            ])

    if not target_files:
        print(f"[!] No resume files found in '{args.dir}'. Pass files directly or add files to the directory.")
        return 1

    print(f"[*] Reading {len(target_files)} document(s)...")
    reader = DocumentReader()
    results = reader.process_files(target_files)

    candidates = []
    success_count = 0
    ai_ext = None
    if args.use_ai:
        from src.ai_extractor import AIExtractor
        ai_ext = AIExtractor()
    resume_parser = ResumeParser(ai_extractor=ai_ext) if (args.extract or args.export) else None

    for res in results:
        status_icon = "✓" if res.status == ProcessingStatus.SUCCESS else "✗"
        print(f"  {status_icon} {res.filename:<32} [{res.status.value:<14}] ({res.char_count:>6,} chars)")

        if res.status == ProcessingStatus.SUCCESS:
            success_count += 1
            if resume_parser:
                cand = resume_parser.parse(res)
                candidates.append(cand)
                if args.verbose:
                    print(f"      Candidate : {cand.full_name or 'N/A'}")
                    print(f"      Email     : {cand.email or 'N/A'} | Phone: {cand.phone or 'N/A'}")
                    print(f"      Location  : {cand.location or 'N/A'}")
                    all_skills = cand.technical_skills + cand.programming_languages
                    print(f"      Top Skills: {', '.join(all_skills[:6]) if all_skills else 'None'}")
                    print(f"      Status    : {cand.metadata.processing_status}")
                    if cand.metadata.validation_issues:
                        print(f"      Issues    : {'; '.join(cand.metadata.validation_issues[:2])}")
            elif args.verbose:
                preview = res.text[:220].replace("\n", " ").strip()
                print(f"      Preview   : {preview}...\n")
        else:
            print(f"      Error     : {res.error}\n")

    print(f"\n[=] Extraction Summary: {success_count}/{len(results)} documents processed successfully.")

    if args.export and candidates:
        export_path = export_to_file(candidates, args.export)
        print(f"[+] Successfully exported {len(candidates)} candidate(s) to 5-sheet workbook: {export_path}")

    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
