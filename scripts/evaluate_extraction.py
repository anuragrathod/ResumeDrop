"""
scripts/evaluate_extraction.py
==============================
Evaluate candidate extraction accuracy against the synthetic dataset.

Usage:
    python scripts/evaluate_extraction.py --rules-only
    python scripts/evaluate_extraction.py --limit 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_data.dataset import DATASET
from schemas.candidate import CandidateRecord
from src.ai_extractor import AIExtractor, NvidiaKeyPool
from src.document_reader import DocumentResult, ProcessingStatus
from src.resume_parser import ResumeParser


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate extraction accuracy")
    parser.add_argument("--rules-only", action="store_true", help="Evaluate using regex rules only")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of evaluated resumes")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed per-field reporting")
    args = parser.parse_args()

    items = DATASET[:args.limit] if args.limit > 0 else DATASET

    ai_extractor = None
    if not args.rules_only:
        pool = NvidiaKeyPool()
        if pool.total_count > 0:
            ai_extractor = AIExtractor()
        else:
            print("No NVIDIA API keys found — defaulting to rules-only evaluation.")

    resume_parser = ResumeParser(ai_extractor=ai_extractor)

    print(f"Evaluating {len(items)} synthetic resume(s) (Engine: {'Rules-only' if not ai_extractor else 'NVIDIA NIM'})...\n")

    results = []
    field_scores = {
        "email": 0,
        "phone": 0,
        "name": 0,
        "location": 0,
        "education": 0,
        "work_experience": 0,
        "projects": 0,
    }

    for item in items:
        doc = DocumentResult(
            filename=f"{item['id']}.txt",
            status=ProcessingStatus.SUCCESS,
            text=item["text"],
        )
        cand = resume_parser.parse(doc)
        exp = item["expected"]

        # Check matches
        email_match = (cand.email or "").lower() == (exp.get("email") or "").lower()
        if email_match:
            field_scores["email"] += 1

        phone_cand_digits = (cand.phone or "").replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        phone_exp_digits = (exp.get("phone") or "").replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
        phone_match = phone_cand_digits == phone_exp_digits
        if phone_match:
            field_scores["phone"] += 1

        name_match = (cand.full_name or "").lower() == (exp.get("full_name") or "").lower()
        if name_match:
            field_scores["name"] += 1

        loc_match = bool(cand.location) if exp.get("location") else True
        if loc_match:
            field_scores["location"] += 1

        edu_match = len(cand.education) == exp.get("education_count", 0)
        if edu_match:
            field_scores["education"] += 1

        exp_match = len(cand.work_experience) == exp.get("work_experience_count", 0)
        if exp_match:
            field_scores["work_experience"] += 1

        proj_match = len(cand.projects) == exp.get("project_count", 0)
        if proj_match:
            field_scores["projects"] += 1

        status_icon = "✓" if cand.metadata.processing_status in ("success", "review_required") else "✗"
        print(f"{status_icon} {item['id']:25s} | Name: {'✓' if name_match else '✗'} | Email: {'✓' if email_match else '✗'} | Phone: {'✓' if phone_match else '✗'} | Edu: {len(cand.education)}/{exp.get('education_count', 0)}")

    total = len(items)
    print("\n" + "=" * 50)
    print("ACCURACY SUMMARY")
    print("=" * 50)
    for field, count in field_scores.items():
        pct = (count / total) * 100
        print(f"  {field.replace('_', ' ').title():18s}: {count}/{total} ({pct:.1f}%)")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())
