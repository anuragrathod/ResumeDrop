"""
scripts/benchmark.py
====================
Measures extraction and parsing throughput across DocumentReader and ResumeParser.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval_data.dataset import DATASET
from src.document_reader import DocumentResult, ProcessingStatus
from src.resume_parser import ResumeParser


def main() -> int:
    parser = argparse.ArgumentParser(description="Performance benchmark")
    parser.add_argument("--runs", type=int, default=1, help="Number of repetitions")
    args = parser.parse_args()

    resume_parser = ResumeParser()
    docs = [
        DocumentResult(
            filename=f"{item['id']}.txt",
            status=ProcessingStatus.SUCCESS,
            text=item["text"],
        )
        for item in DATASET
    ]

    print(f"Benchmarking {len(docs)} resumes across {args.runs} run(s)...")

    durations = []
    for r in range(args.runs):
        start = time.perf_counter()
        candidates, _ = resume_parser.parse_batch_parallel(docs, max_workers=3)
        elapsed = time.perf_counter() - start
        durations.append(elapsed)
        print(f"  Run {r+1}: {elapsed:.3f}s ({len(candidates)} processed, {len(candidates)/elapsed:.1f} resumes/s)")

    avg = sum(durations) / len(durations)
    print(f"\nAverage duration: {avg:.3f}s | Average throughput: {len(docs)/avg:.1f} resumes/second")
    return 0


if __name__ == "__main__":
    sys.exit(main())
