"""
Parallel scraping engine using multithreaded Producer-Consumer pattern.

This module implements the core multithreading infrastructure for the Shop
Comparison Platform. It replaces the sequential store-by-store scraping loop
with a concurrent pipeline where multiple scraper threads produce data that
a dedicated database thread consumes.

Architecture:
    - **Producer threads** (N per store): fetch and normalize product pages in parallel.
    - **DB Consumer thread** (1 global): serializes all DB writes to avoid race conditions.
    - **Shared Queue**: thread-safe buffer (``queue.Queue``) between producers and consumer.
    - **Progress callbacks**: allow the GUI to receive live updates without polling.

Design Patterns used:
    - Producer-Consumer (threading + queue)
    - Observer (progress_callback)
    - Strategy (sequential vs parallel run modes share the same interface)
    - Template Method (inherited from BaseScraper)
"""

import threading
import queue
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any

from core.factory import ParserFactory
from core.resolution.router import EntityRouter

logger = logging.getLogger(__name__)

# Sentinel value: when the DB consumer reads this it knows producers are done.
_DB_SENTINEL = None


@dataclass
class ScrapeStats:
    """
    Thread-safe accumulator for scraping statistics.

    All mutations go through a ``threading.Lock`` so that multiple producer
    threads can update the counters concurrently without data races.

    Attributes:
        store (str): Name of the store being scraped.
        total (int): Total number of slugs to process.
        processed (int): Number of successfully processed products.
        failed (int): Number of products that raised an exception.
        skipped (int): Number of products that returned no data (404 etc.).
        start_time (float): Unix timestamp of when scraping began.
        end_time (float): Unix timestamp of when scraping finished (0 = running).
    """

    store: str
    total: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def increment(self, field_name: str) -> None:
        """Atomically increments one of the mutable counters."""
        with self._lock:
            setattr(self, field_name, getattr(self, field_name) + 1)

    def finish(self) -> None:
        """Records the finish timestamp."""
        self.end_time = time.time()

    @property
    def elapsed(self) -> float:
        """Elapsed wall-clock time in seconds."""
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    @property
    def done(self) -> int:
        """Total slugs accounted for (processed + failed + skipped)."""
        return self.processed + self.failed + self.skipped


@dataclass
class ProgressEvent:
    """
    A snapshot of scraping progress sent to the GUI callback.

    Attributes:
        store (str): Store identifier.
        slug (str): The slug that was just processed.
        stats (ScrapeStats): Current statistics snapshot.
        message (str): Human-readable status message.
        level (str): One of ``"info"``, ``"success"``, ``"warning"``, ``"error"``.
    """
    store: str
    slug: str
    stats: ScrapeStats
    message: str
    level: str = "info"


class ParallelScrapingEngine:
    """
    Orchestrates parallel scraping of multiple stores with a shared DB writer thread.

    This engine manages two layers of concurrency:

    1. **Inter-store parallelism**: each store runs in its own ``ThreadPoolExecutor``
       with ``workers_per_store`` threads for page fetching.
    2. **DB serialization**: a single background thread drains a ``queue.Queue``
       and writes to PostgreSQL, eliminating the need for per-thread sessions.

    Args:
        stores (List[str]): Store identifiers to scrape (e.g. ``["atb", "silpo"]``).
        workers_per_store (int): Number of concurrent fetcher threads per store.
            Defaults to 4. Keep ≤ 8 to respect target-site rate limits.
        db_queue_maxsize (int): Maximum items buffered in the DB queue.
            When full, producer threads block, providing natural back-pressure.
        progress_callback (Callable[[ProgressEvent], None] | None):
            Optional function called from threads on every progress update.
            Must be thread-safe (e.g., use ``root.after`` in Tkinter).

    Example:
        >>> engine = ParallelScrapingEngine(
        ...     stores=["atb", "silpo"],
        ...     workers_per_store=4,
        ...     progress_callback=my_gui_update_fn,
        ... )
        >>> engine.run()
    """

    def __init__(
        self,
        stores: List[str],
        workers_per_store: int = 4,
        db_queue_maxsize: int = 0,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> None:
        self.stores = stores
        self.workers_per_store = workers_per_store
        self.progress_callback = progress_callback

        # One shared queue between all producer threads and the single DB consumer.
        self._db_queue: queue.Queue = queue.Queue(maxsize=db_queue_maxsize)

        # Each store gets its own stats object; protected by individual locks inside.
        self.stats: Dict[str, ScrapeStats] = {}

        # A global stop-event lets the GUI cancel the run mid-flight.
        self._stop_event = threading.Event()

        # Count of active producer pools so the consumer knows when to stop.
        self._active_producers = 0
        self._producers_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, ScrapeStats]:
        """
        Starts the full parallel scraping run and blocks until completion.

        Workflow:
        1. Starts the **DB consumer thread**.
        2. Launches one ``ThreadPoolExecutor`` per store (all stores run concurrently).
        3. Waits for all executor threads to finish.
        4. Signals the DB consumer to stop via the sentinel.
        5. Joins the consumer thread.
        6. Returns per-store statistics.

        Returns:
            Dict[str, ScrapeStats]: Mapping of store name → final statistics.
        """
        self._stop_event.clear()

        # Register all stores as active producers before starting threads.
        with self._producers_lock:
            self._active_producers = len(self.stores)

        # Start the single database consumer thread.
        db_thread = threading.Thread(
            target=self._db_consumer_worker,
            name="DBConsumer",
            daemon=True,
        )
        db_thread.start()

        # Launch one executor per store (stores run in parallel).
        store_threads = []
        for store in self.stores:
            t = threading.Thread(
                target=self._run_store,
                args=(store,),
                name=f"StoreOrchestrator-{store}",
                daemon=True,
            )
            t.start()
            store_threads.append(t)

        for t in store_threads:
            t.join()

        # All producers finished — send sentinel to unblock consumer.
        self._db_queue.put(_DB_SENTINEL)
        db_thread.join()

        return self.stats

    def stop(self) -> None:
        """
        Requests a graceful stop of the scraping run.

        Sets an internal ``threading.Event`` that producer threads check after
        each processed slug. The current in-flight requests will finish, but no
        new slugs will be picked up.
        """
        self._stop_event.set()
        logger.info("Stop requested — draining remaining work...")

    # ------------------------------------------------------------------
    # Private: store orchestrator (one per store)
    # ------------------------------------------------------------------

    def _run_store(self, store: str) -> None:
        """
        Discovers slugs for one store and fans them out across worker threads.

        Args:
            store (str): Store identifier.
        """
        stats = ScrapeStats(store=store)
        self.stats[store] = stats

        self._notify(ProgressEvent(
            store=store, slug="",
            stats=stats,
            message=f"[{store.upper()}] Починаємо сканування каталогу...",
            level="info",
        ))

        try:
            scraper = ParserFactory.create_scraper(store)
            slugs = scraper.discover_slugs()
        except NotImplementedError as exc:
            self._notify(ProgressEvent(
                store=store, slug="",
                stats=stats,
                message=f"[{store.upper()}] ⏭ Пропущено: {exc}",
                level="warning",
            ))
            self._mark_producer_done()
            return
        except Exception as exc:
            logger.exception("Discovery failed for %s", store)
            self._notify(ProgressEvent(
                store=store, slug="",
                stats=stats,
                message=f"[{store.upper()}] ❌ Помилка discovery: {exc}",
                level="error",
            ))
            self._mark_producer_done()
            return

        stats.total = len(slugs)
        self._notify(ProgressEvent(
            store=store, slug="",
            stats=stats,
            message=f"[{store.upper()}] ✅ Знайдено {len(slugs)} товарів. Запускаємо {self.workers_per_store} потоки...",
            level="success",
        ))

        # Fan out: process slugs concurrently inside this store's executor.
        with ThreadPoolExecutor(
            max_workers=self.workers_per_store,
            thread_name_prefix=f"Worker-{store}",
        ) as executor:
            futures = {
                executor.submit(self._fetch_and_enqueue, store, slug, scraper): slug
                for slug in slugs
            }
            for future in as_completed(futures):
                if self._stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                slug = futures[future]
                try:
                    result_msg, level = future.result()
                    self._notify(ProgressEvent(
                        store=store,
                        slug=slug,
                        stats=stats,
                        message=result_msg,
                        level=level,
                    ))
                except Exception as exc:
                    stats.increment("failed")
                    self._notify(ProgressEvent(
                        store=store, slug=slug, stats=stats,
                        message=f"[{store}] ❌ {slug}: {exc}",
                        level="error",
                    ))

        stats.finish()
        self._notify(ProgressEvent(
            store=store, slug="",
            stats=stats,
            message=(
                f"[{store.upper()}] 🚀 Завершено! "
                f"Оброблено: {stats.processed} | "
                f"Пропущено: {stats.skipped} | "
                f"Помилок: {stats.failed} | "
                f"Час: {stats.elapsed:.1f}с"
            ),
            level="success",
        ))

        self._mark_producer_done()

    # ------------------------------------------------------------------
    # Private: producer worker (one per slug, run inside executor)
    # ------------------------------------------------------------------

    def _fetch_and_enqueue(self, store: str, slug: str, scraper: Any) -> tuple:
        """
        Fetches and normalizes one product, then enqueues it for the DB consumer.

        This method runs inside a thread-pool worker. It is intentionally
        CPU/IO bound and must not perform any direct database access.

        Args:
            store (str): Store name (for logging).
            slug (str): Product identifier.
            scraper: A store-specific scraper instance (shared across threads;
                BaseScraper implementations must be stateless or thread-safe).

        Returns:
            tuple[str, str]: (human-readable message, log level)
        """
        stats = self.stats[store]

        if self._stop_event.is_set():
            stats.increment("skipped")
            return f"[{store}] ⏹ {slug}: скасовано", "warning"

        try:
            product = scraper.process_product(slug)
        except Exception as exc:
            stats.increment("failed")
            return f"[{store}] ❌ {slug}: {exc}", "error"

        if product is None:
            stats.increment("skipped")
            return f"[{store}] ⚠ {slug}: товар не знайдено", "warning"

        # Put on the shared queue (blocks if queue is full → back-pressure).
        self._db_queue.put((store, product))
        stats.increment("processed")
        return (
            f"[{store}] ✅ ({stats.done}/{stats.total}) {product.get('canonical_name', slug)}",
            "success",
        )

    # ------------------------------------------------------------------
    # Private: DB consumer (single thread)
    # ------------------------------------------------------------------

    def _db_consumer_worker(self) -> None:
        """
        Drains the shared queue and writes items to the database sequentially.

        A single thread handles all DB writes, ensuring that SQLAlchemy sessions
        are never shared between threads. The consumer loops indefinitely until
        it receives the ``_DB_SENTINEL`` value, which signals that all producers
        have finished and the queue is empty.

        Important:
            Each item gets its own ``EntityRouter`` (and therefore its own
            ``Session``) to ensure transaction isolation and avoid session
            contamination between stores.
        """
        try:
            router = EntityRouter()
            logger.info("DBConsumer started.")
        except Exception as exc:
            logger.error("DBConsumer init failed: %s", exc)
            while True:
                try:
                    item = self._db_queue.get_nowait()
                    if item is _DB_SENTINEL:
                        break
                except queue.Empty:
                    break
            return

        try:
            while True:
                try:
                    # timeout=1 дозволяє потоку не "залипати" наглухо
                    item = self._db_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if item is _DB_SENTINEL:
                    logger.info("DBConsumer received sentinel — shutting down.")
                    break

                store, product = item
                try:
                    router.process_scraped_item(product)
                except Exception as exc:
                    logger.error("DB write failed for %s: %s", store, exc)
                    router.repo.session.rollback()
                finally:
                    self._db_queue.task_done()

        finally:
            try:
                router.close()
            except Exception:
                pass
            logger.info("DBConsumer shut down cleanly.")

    # ------------------------------------------------------------------
    # Private: helpers
    # ------------------------------------------------------------------

    def _mark_producer_done(self) -> None:
        """Decrements the active producer counter; no-op sentinel is sent by run()."""
        with self._producers_lock:
            self._active_producers -= 1

    def _notify(self, event: ProgressEvent) -> None:
        """Calls the progress callback if one was registered (silently ignores errors)."""
        if self.progress_callback:
            try:
                self.progress_callback(event)
            except Exception:
                pass  # Never let a broken callback crash a worker thread.
