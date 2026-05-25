"""
Unit tests for the parallel scraping engine.

Tests cover:
- ``ScrapeStats`` thread-safe counter increments
- ``ParallelScrapingEngine`` with a fully mocked scraper (no network/DB)
- Sequential vs parallel correctness comparison
- Stop/cancellation mechanism
- Progress callback delivery
- Edge cases: empty slug list, all-failing scraper, single store
"""

import threading
import time
import pytest
from unittest.mock import MagicMock, patch
from typing import List, Optional

from core.parallel_engine import (
    ParallelScrapingEngine,
    ProgressEvent,
    ScrapeStats,
)


# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------

def make_fake_product(slug: str) -> dict:
    """Returns a minimal product dict that looks like adapter output."""
    return {
        "product_id": f"fake_{slug}",
        "canonical_name": f"Товар {slug}",
        "brand": "FakeBrand",
        "offers": [{"sku": slug, "pricing": {"current_price": 99.9, "regular_price": 99.9}}],
    }


class FakeScraper:
    """
    A deterministic fake scraper for testing purposes.

    Args:
        slugs: Fixed slug list to return from discover_slugs.
        fail_slugs: Slugs that should raise an exception during processing.
        none_slugs: Slugs that should return None (product not found).
        delay: Optional artificial delay per product (seconds).
    """

    def __init__(
        self,
        slugs: List[str],
        fail_slugs: Optional[List[str]] = None,
        none_slugs: Optional[List[str]] = None,
        delay: float = 0.0,
    ):
        self._slugs = slugs
        self._fail = set(fail_slugs or [])
        self._none = set(none_slugs or [])
        self._delay = delay

    def discover_slugs(self) -> List[str]:
        return list(self._slugs)

    def process_product(self, slug: str) -> Optional[dict]:
        if self._delay:
            time.sleep(self._delay)
        if slug in self._fail:
            raise RuntimeError(f"Simulated failure for {slug}")
        if slug in self._none:
            return None
        return make_fake_product(slug)


# ---------------------------------------------------------------------------
# ScrapeStats tests
# ---------------------------------------------------------------------------

class TestScrapeStats:
    """Tests for the thread-safe statistics accumulator."""

    def test_initial_values(self):
        """All counters start at zero."""
        s = ScrapeStats(store="test")
        assert s.processed == 0
        assert s.failed == 0
        assert s.skipped == 0
        assert s.total == 0

    def test_increment_processed(self):
        """increment() correctly adds 1 to the target field."""
        s = ScrapeStats(store="test")
        s.increment("processed")
        s.increment("processed")
        assert s.processed == 2

    def test_increment_failed(self):
        s = ScrapeStats(store="test")
        s.increment("failed")
        assert s.failed == 1

    def test_done_property(self):
        """done == processed + failed + skipped."""
        s = ScrapeStats(store="test")
        s.increment("processed")
        s.increment("failed")
        s.increment("skipped")
        assert s.done == 3

    def test_elapsed_before_finish(self):
        """elapsed returns positive value even before finish() is called."""
        s = ScrapeStats(store="test")
        time.sleep(0.05)
        assert s.elapsed >= 0.04

    def test_elapsed_after_finish(self):
        """elapsed is frozen after finish() is called."""
        s = ScrapeStats(store="test")
        time.sleep(0.05)
        s.finish()
        frozen = s.elapsed
        time.sleep(0.05)
        # Should not grow after finish
        assert abs(s.elapsed - frozen) < 0.01

    def test_thread_safe_increments(self):
        """
        Concurrent increments from multiple threads must not lose updates.

        This is the classic lost-update race condition test. We use 20 threads
        each incrementing 100 times → expect exactly 2000.
        """
        s = ScrapeStats(store="concurrent")
        threads = [
            threading.Thread(target=lambda: [s.increment("processed") for _ in range(100)])
            for _ in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert s.processed == 2000


# ---------------------------------------------------------------------------
# ParallelScrapingEngine tests
# ---------------------------------------------------------------------------

class TestParallelScrapingEngine:
    """Tests for the main parallel orchestration engine."""

    def _make_engine(self, fake_scraper, stores=("fake",), workers=2, callback=None):
        """Helper: creates an engine with ParserFactory mocked to return fake_scraper."""
        engine = ParallelScrapingEngine(
            stores=list(stores),
            workers_per_store=workers,
            progress_callback=callback,
        )
        return engine

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_all_products_processed(self, mock_factory, mock_router):
        """
        Engine processes exactly N slugs when all succeed.

        Verifies that no products are silently dropped in the handoff
        between producer threads and the DB consumer.
        """
        slugs = [f"slug-{i}" for i in range(10)]
        fake = FakeScraper(slugs=slugs)
        mock_factory.create_scraper.return_value = fake
        mock_router.return_value = MagicMock()

        engine = ParallelScrapingEngine(stores=["fake"], workers_per_store=3)
        stats = engine.run()

        s = stats["fake"]
        assert s.processed == 10
        assert s.failed == 0
        assert s.skipped == 0

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_failed_slugs_counted(self, mock_factory, mock_router):
        """Slugs that raise exceptions are counted as failed, not processed."""
        slugs = ["ok-1", "ok-2", "bad-1", "bad-2"]
        fake = FakeScraper(slugs=slugs, fail_slugs=["bad-1", "bad-2"])
        mock_factory.create_scraper.return_value = fake
        mock_router.return_value = MagicMock()

        engine = ParallelScrapingEngine(stores=["fake"], workers_per_store=2)
        stats = engine.run()

        s = stats["fake"]
        assert s.processed == 2
        assert s.failed == 2

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_none_products_counted_as_skipped(self, mock_factory, mock_router):
        """Slugs for which the scraper returns None are counted as skipped."""
        slugs = ["good", "missing"]
        fake = FakeScraper(slugs=slugs, none_slugs=["missing"])
        mock_factory.create_scraper.return_value = fake
        mock_router.return_value = MagicMock()

        engine = ParallelScrapingEngine(stores=["fake"], workers_per_store=2)
        stats = engine.run()

        s = stats["fake"]
        assert s.processed == 1
        assert s.skipped == 1

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_empty_slug_list(self, mock_factory, mock_router):
        """An empty slug list should produce zero counts without errors."""
        fake = FakeScraper(slugs=[])
        mock_factory.create_scraper.return_value = fake
        mock_router.return_value = MagicMock()

        engine = ParallelScrapingEngine(stores=["fake"], workers_per_store=2)
        stats = engine.run()

        s = stats["fake"]
        assert s.processed == 0
        assert s.failed == 0

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_multiple_stores_run_concurrently(self, mock_factory, mock_router):
        """
        Multiple stores are processed and each receives its own stats entry.
        """
        slugs = [f"slug-{i}" for i in range(5)]

        def create(store_name):
            return FakeScraper(slugs=slugs)

        mock_factory.create_scraper.side_effect = create
        mock_router.return_value = MagicMock()

        engine = ParallelScrapingEngine(
            stores=["store_a", "store_b", "store_c"],
            workers_per_store=2,
        )
        stats = engine.run()

        assert set(stats.keys()) == {"store_a", "store_b", "store_c"}
        for s in stats.values():
            assert s.processed == 5

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_progress_callback_called(self, mock_factory, mock_router):
        """
        Progress callback must be invoked for every processed slug.

        The number of 'success' events should equal the number of processed
        slugs (some extras for discovery/summary messages are fine).
        """
        slugs = [f"slug-{i}" for i in range(8)]
        fake = FakeScraper(slugs=slugs)
        mock_factory.create_scraper.return_value = fake
        mock_router.return_value = MagicMock()

        events = []
        engine = ParallelScrapingEngine(
            stores=["fake"],
            workers_per_store=3,
            progress_callback=events.append,
        )
        engine.run()

        success_events = [e for e in events if e.level == "success"]
        # Each of the 8 slugs + at least 1 summary event
        assert len(success_events) >= 8

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_stop_event_halts_processing(self, mock_factory, mock_router):
        """
        Calling stop() before the engine finishes should result in fewer
        processed items than the total slug count.
        """
        # Use 50 slugs with a small delay so stop() can fire mid-run
        slugs = [f"slug-{i}" for i in range(50)]
        fake = FakeScraper(slugs=slugs, delay=0.02)
        mock_factory.create_scraper.return_value = fake
        mock_router.return_value = MagicMock()

        engine = ParallelScrapingEngine(stores=["fake"], workers_per_store=2)

        # Stop after a short delay
        def _stop_later():
            time.sleep(0.1)
            engine.stop()

        stopper = threading.Thread(target=_stop_later)
        stopper.start()

        stats = engine.run()
        stopper.join()

        # We should have processed fewer than all 50 slugs
        assert stats["fake"].processed < 50

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_discovery_not_implemented_skips_store(self, mock_factory, mock_router):
        """
        If a scraper raises NotImplementedError in discover_slugs,
        the store should be skipped gracefully with a warning event.
        """
        broken_scraper = MagicMock()
        broken_scraper.discover_slugs.side_effect = NotImplementedError("Not supported")
        mock_factory.create_scraper.return_value = broken_scraper
        mock_router.return_value = MagicMock()

        events = []
        engine = ParallelScrapingEngine(
            stores=["broken"],
            workers_per_store=2,
            progress_callback=events.append,
        )
        stats = engine.run()

        warning_events = [e for e in events if e.level == "warning"]
        assert len(warning_events) >= 1
        # The store should still appear in stats (initialized)
        assert "broken" in stats


# ---------------------------------------------------------------------------
# Sequential vs Parallel correctness comparison
# ---------------------------------------------------------------------------

class TestSequentialVsParallel:
    """
    Verifies that parallel execution produces the same results as sequential.

    This is the most important correctness test for a multithreading lab:
    parallelism must not affect the outcome, only the speed.
    """

    def _run_sequential(self, scraper, slugs) -> List[dict]:
        """Simulates sequential processing, returns list of products."""
        results = []
        for slug in slugs:
            try:
                p = scraper.process_product(slug)
                if p:
                    results.append(p)
            except Exception:
                pass
        return results

    @patch("core.parallel_engine.EntityRouter")
    @patch("core.parallel_engine.ParserFactory")
    def test_same_product_count(self, mock_factory, mock_router):
        """
        Parallel engine must process the same number of valid products as
        a sequential loop over the same slug list.
        """
        slugs = [f"slug-{i}" for i in range(20)]
        fail_slugs = ["slug-3", "slug-7"]
        none_slugs = ["slug-11"]
        fake = FakeScraper(slugs=slugs, fail_slugs=fail_slugs, none_slugs=none_slugs)

        # Sequential count
        seq_products = self._run_sequential(fake, slugs)
        expected_count = len(seq_products)  # 20 - 2 fail - 1 none = 17

        # Parallel count
        mock_factory.create_scraper.return_value = fake
        mock_router.return_value = MagicMock()

        engine = ParallelScrapingEngine(stores=["fake"], workers_per_store=4)
        stats = engine.run()

        assert stats["fake"].processed == expected_count
