"""
benchmarks/run_benchmarks.py — Standalone benchmark runner.

Measures wall-clock time for sequential vs parallel scraping across several
thread counts and writes human-readable results to ``benchmarks/results.md``.

Run:
    python -m benchmarks.run_benchmarks --stores atb silpo --slugs 20
"""

import argparse
import os
import sys
import logging
from datetime import datetime

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.benchmark import Benchmark

logging.basicConfig(level=logging.WARNING)  # Suppress info noise during benchmarks


RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.md")


def save_markdown(report_text: str):
    """Writes the benchmark report to a Markdown file."""
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write(f"# Benchmark Results\n\n")
        f.write(f"_Generated: {datetime.now():%Y-%m-%d %H:%M:%S}_\n\n")
        f.write("## What was measured\n\n")
        f.write(
            "Each store's slug list was discovered once (not counted in timing). "
            "Then the first `N` slugs were processed (fetched + normalized, **without DB writes**) "
            "in two modes:\n\n"
            "- **Sequential**: single thread, slugs processed one-by-one.\n"
            "- **Parallel**: `ThreadPoolExecutor` with varying thread counts.\n\n"
            "Wall-clock time was recorded with `time.perf_counter()` for accuracy.\n\n"
            "**Throughput** = slugs processed / elapsed seconds.\n\n"
            "**Speedup** = sequential_time / best_parallel_time.\n\n"
        )
        f.write("## Results\n\n")
        f.write("```\n")
        f.write(report_text)
        f.write("\n```\n")
    print(f"\n💾 Results saved to: {RESULTS_PATH}")


def main():
    parser = argparse.ArgumentParser(description="Run scraping benchmarks")
    parser.add_argument(
        "--stores", nargs="+", default=["atb"],
        help="Stores to benchmark"
    )
    parser.add_argument(
        "--slugs", type=int, default=20,
        help="Max slugs per store per run (keep small for quick results)"
    )
    parser.add_argument(
        "--workers", nargs="+", type=int, default=[1, 2, 4, 8],
        help="Thread counts to test in parallel mode"
    )
    args = parser.parse_args()

    print(f"🏁 Starting benchmark: stores={args.stores}, slugs={args.slugs}, workers={args.workers}")
    print("   (This may take a few minutes depending on network speed)\n")

    benchmark = Benchmark(
        stores=args.stores,
        max_slugs=args.slugs,
        worker_configs=args.workers,
    )

    report = benchmark.run()
    summary = report.summary()

    print(summary)
    save_markdown(summary)


if __name__ == "__main__":
    main()
