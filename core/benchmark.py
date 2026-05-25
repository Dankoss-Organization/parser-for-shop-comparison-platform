"""
Benchmarking utilities for comparing sequential vs parallel scraping performance.

This module provides the ``Benchmark`` class which runs the scraping pipeline
in both modes, measures wall-clock time, and produces a structured report
suitable for inclusion in a lab report or repository README.

Usage (standalone):
    >>> python -m benchmarks.run_benchmarks

Usage (programmatic):
    >>> from core.benchmark import Benchmark
    >>> report = Benchmark(stores=["silpo"], max_slugs=50).run()
    >>> print(report.summary())
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """
    Holds the outcome of a single benchmark run.

    Attributes:
        mode (str): ``"sequential"`` or ``"parallel"``.
        store (str): Store identifier.
        slugs_processed (int): How many slugs were actually processed.
        elapsed_sec (float): Total wall-clock time in seconds.
        workers (int): Thread count used (1 for sequential).
        errors (int): Number of failed slugs.
    """
    mode: str
    store: str
    slugs_processed: int
    elapsed_sec: float
    workers: int
    errors: int = 0

    @property
    def throughput(self) -> float:
        """Products processed per second."""
        if self.elapsed_sec == 0:
            return 0.0
        return self.slugs_processed / self.elapsed_sec

    def __str__(self) -> str:
        return (
            f"[{self.mode.upper():>12}] store={self.store:<12} "
            f"slugs={self.slugs_processed:<6} "
            f"time={self.elapsed_sec:>7.2f}s  "
            f"throughput={self.throughput:>6.2f} items/s  "
            f"workers={self.workers}  errors={self.errors}"
        )


@dataclass
class BenchmarkReport:
    """
    Aggregated results for one benchmark session (sequential + parallel runs).

    Attributes:
        results (List[BenchmarkResult]): All individual run results.
        worker_configs (List[int]): Thread counts that were tested in parallel mode.
    """
    results: List[BenchmarkResult] = field(default_factory=list)
    worker_configs: List[int] = field(default_factory=list)

    def speedup(self, store: str) -> Optional[float]:
        """
        Computes the speedup ratio: sequential_time / best_parallel_time.

        Args:
            store (str): Store to compute speedup for.

        Returns:
            float | None: Speedup ratio, or None if data is incomplete.
        """
        seq = next((r for r in self.results if r.mode == "sequential" and r.store == store), None)
        parallel_runs = [r for r in self.results if r.mode == "parallel" and r.store == store]
        if not seq or not parallel_runs:
            return None
        best_parallel = min(parallel_runs, key=lambda r: r.elapsed_sec)
        if best_parallel.elapsed_sec == 0:
            return None
        return seq.elapsed_sec / best_parallel.elapsed_sec

    def summary(self) -> str:
        """Returns a formatted human-readable report string."""
        lines = [
            "=" * 80,
            "  BENCHMARK REPORT — Sequential vs Parallel Scraping",
            "=" * 80,
            "",
        ]
        for r in self.results:
            lines.append(str(r))

        lines.append("")
        lines.append("--- Speedup Summary ---")
        stores = {r.store for r in self.results}
        for store in sorted(stores):
            sp = self.speedup(store)
            if sp is not None:
                lines.append(f"  {store}: {sp:.2f}x speedup over sequential")
        lines.append("=" * 80)
        return "\n".join(lines)


class Benchmark:
    """
    Runs sequential and parallel scraping of a limited slug sample and reports timing.

    The benchmark is intentionally **read-only with respect to the database** — it
    calls ``scraper.fetch_data()`` and ``adapter.normalize()`` only, without
    routing results to the DB. This makes it safe to run repeatedly without
    polluting production data.

    Args:
        stores (List[str]): Stores to benchmark.
        max_slugs (int): Maximum number of slugs to process per store per run.
            Keep small (20–100) for fast benchmark cycles.
        worker_configs (List[int]): List of thread counts to test in parallel mode.
            E.g. ``[1, 2, 4, 8]``.

    Example:
        >>> report = Benchmark(stores=["atb"], max_slugs=30, worker_configs=[2, 4]).run()
        >>> print(report.summary())
    """

    def __init__(
        self,
        stores: List[str],
        max_slugs: int = 50,
        worker_configs: Optional[List[int]] = None,
    ) -> None:
        self.stores = stores
        self.max_slugs = max_slugs
        self.worker_configs = worker_configs or [1, 2, 4, 8]

    def run(self) -> BenchmarkReport:
        """
        Executes all benchmark runs and returns the aggregated report.

        For each store it runs:
        1. One **sequential** run (single thread, no executor).
        2. One **parallel** run for each worker count in ``worker_configs``.

        Returns:
            BenchmarkReport: Structured results with timing and throughput.
        """
        report = BenchmarkReport(worker_configs=self.worker_configs)

        for store in self.stores:
            logger.info("Benchmarking store: %s", store)

            # --- Discover slugs once (not counted in benchmark time) ---
            try:
                from core.factory import ParserFactory
                scraper = ParserFactory.create_scraper(store)
                all_slugs = scraper.discover_slugs()
                slugs = all_slugs[: self.max_slugs]
            except Exception as exc:
                logger.warning("Skipping %s — discovery failed: %s", store, exc)
                continue

            if not slugs:
                logger.warning("No slugs found for %s, skipping.", store)
                continue

            # --- Sequential run ---
            seq_result = self._run_sequential(store, slugs, scraper)
            report.results.append(seq_result)
            logger.info("Sequential: %s", seq_result)

            # --- Parallel runs ---
            for workers in self.worker_configs:
                par_result = self._run_parallel(store, slugs, scraper, workers)
                report.results.append(par_result)
                logger.info("Parallel(%d): %s", workers, par_result)

        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _run_sequential(self, store: str, slugs: List[str], scraper) -> BenchmarkResult:
        """
        Processes slugs one-by-one in the calling thread.

        Args:
            store (str): Store name.
            slugs (List[str]): Slug list to process.
            scraper: Configured scraper instance.

        Returns:
            BenchmarkResult: Timing result for the sequential run.
        """
        processed = errors = 0
        start = time.perf_counter()

        for slug in slugs:
            try:
                product = scraper.process_product(slug)
                if product:
                    processed += 1
                # Note: we intentionally skip DB write in benchmarks.
            except Exception:
                errors += 1

        elapsed = time.perf_counter() - start
        return BenchmarkResult(
            mode="sequential",
            store=store,
            slugs_processed=processed,
            elapsed_sec=elapsed,
            workers=1,
            errors=errors,
        )

    def _run_parallel(
        self, store: str, slugs: List[str], scraper, workers: int
    ) -> BenchmarkResult:
        """
        Processes slugs concurrently using a ``ThreadPoolExecutor``.

        Args:
            store (str): Store name.
            slugs (List[str]): Slug list to process.
            scraper: Configured scraper instance.
            workers (int): Number of concurrent threads.

        Returns:
            BenchmarkResult: Timing result for this parallel configuration.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        processed = errors = 0
        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"bench-{store}") as ex:
            futures = {ex.submit(scraper.process_product, slug): slug for slug in slugs}
            for future in as_completed(futures):
                try:
                    product = future.result()
                    if product:
                        processed += 1
                except Exception:
                    errors += 1

        elapsed = time.perf_counter() - start
        return BenchmarkResult(
            mode="parallel",
            store=store,
            slugs_processed=processed,
            elapsed_sec=elapsed,
            workers=workers,
            errors=errors,
        )
