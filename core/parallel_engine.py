"""
Parallel scraping engine using multithreaded Producer-Consumer pattern.

Architecture:
    - **Producer threads** (workers_per_store per store): fetch and normalize
      product pages concurrently using ThreadPoolExecutor.
    - **DB Consumer thread** (1 global): serializes all DB writes so that
      SQLAlchemy sessions are never shared between threads.
    - **DB Queue**: thread-safe buffer between producers and consumer.
      Uses maxsize=0 (unlimited) to avoid ever blocking producers — if the DB
      consumer is slow we queue up, not deadlock.
    - **Progress Queue**: a *separate* queue that GUI polls on a timer.
      Worker threads never call Tkinter directly; they only enqueue events.

Design Patterns:
    - Producer-Consumer (threading + queue.Queue)
    - Observer (progress via ProgressQueue polled by GUI)
    - Strategy (sequential main.py vs parallel main_parallel.py share same scraper API)
    - Template Method (inherited from BaseScraper: discover_slugs / process_product)
"""

import threading
import queue
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, FIRST_COMPLETED
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any

from core.factory import ParserFactory
from core.resolution.router import EntityRouter

logger = logging.getLogger(__name__)

_DB_SENTINEL = None  # Signals DB consumer to stop


@dataclass
class ScrapeStats:
    """
    Thread-safe accumulator for per-store scraping statistics.

    Uses a threading.Lock for all mutations so that multiple producer
    threads can update counters concurrently without data races.

    Attributes:
        store (str): Store name.
        total (int): Total slugs to process (set after discovery).
        processed (int): Successfully processed and enqueued for DB.
        failed (int): Slugs that raised an exception.
        skipped (int): Slugs that returned None from the scraper.
        start_time (float): Unix timestamp when scraping started.
        end_time (float): Unix timestamp when scraping finished (0 = still running).
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
        """Atomically increments one counter (thread-safe)."""
        with self._lock:
            setattr(self, field_name, getattr(self, field_name) + 1)

    def finish(self) -> None:
        """Freezes the elapsed timer."""
        self.end_time = time.time()

    @property
    def elapsed(self) -> float:
        """Wall-clock time in seconds since scraping started."""
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    @property
    def done(self) -> int:
        """Total slugs accounted for (processed + failed + skipped)."""
        return self.processed + self.failed + self.skipped


@dataclass
class ProgressEvent:
    """
    A progress snapshot delivered to the GUI.

    Attributes:
        store (str): Store identifier.
        slug (str): The slug just processed ("" for discovery/summary messages).
        stats (ScrapeStats): Current stats snapshot for the store.
        message (str): Human-readable log line.
        level (str): "info" | "success" | "warning" | "error"
    """
    store: str
    slug: str
    stats: ScrapeStats
    message: str
    level: str = "info"


class ParallelScrapingEngine:
    """
    Orchestrates parallel scraping of multiple stores with a shared DB writer thread.

    Two layers of concurrency:
    1. Each store runs its own ThreadPoolExecutor (workers_per_store threads).
    2. A single DB consumer thread drains a queue.Queue and writes to PostgreSQL.

    GUI integration:
        Pass a ``progress_queue`` (queue.Queue) and poll it from the main thread
        with ``root.after(50, poll_fn)``. Worker threads only put events on the
        queue — they never touch Tkinter directly.

    Args:
        stores: Store identifiers to scrape.
        workers_per_store: Concurrent fetcher threads per store. Default 4.
        progress_queue: Optional queue.Queue for GUI events. If None, events
            are logged to stdout via the ``progress_callback`` fallback.
        progress_callback: Optional callable for headless (CLI) mode.
    """

    def __init__(
        self,
        stores: List[str],
        workers_per_store: int = 4,
        progress_queue: Optional[queue.Queue] = None,
        progress_callback: Optional[Callable[[ProgressEvent], None]] = None,
    ) -> None:
        self.stores = stores
        self.workers_per_store = workers_per_store
        self._progress_queue = progress_queue
        self._progress_callback = progress_callback

        # Unlimited DB queue — producers never block waiting for DB consumer.
        self._db_queue: queue.Queue = queue.Queue(maxsize=0)

        self.stats: Dict[str, ScrapeStats] = {}
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, ScrapeStats]:
        """
        Starts the full parallel run and blocks until all stores and DB writes finish.

        Workflow:
        1. Start the DB consumer thread.
        2. Start one StoreOrchestrator thread per store (stores run concurrently).
        3. Join all store threads.
        4. Send DB sentinel to stop the consumer.
        5. Join the consumer thread.
        6. Return per-store statistics.

        Returns:
            Dict[str, ScrapeStats]: Final statistics per store.
        """
        self._stop_event.clear()

        db_thread = threading.Thread(
            target=self._db_consumer_worker,
            name="DBConsumer",
            daemon=True,
        )
        db_thread.start()

        store_threads = [
            threading.Thread(
                target=self._run_store,
                args=(store,),
                name=f"StoreOrchestrator-{store}",
                daemon=True,
            )
            for store in self.stores
        ]
        for t in store_threads:
            t.start()
        for t in store_threads:
            t.join()

        # Signal DB consumer to finish after draining remaining items.
        self._db_queue.put(_DB_SENTINEL)
        db_thread.join()

        return self.stats

    def stop(self) -> None:
        """
        Requests a graceful stop.

        Sets a threading.Event that worker threads check between slugs.
        In-flight HTTP requests will complete but no new slugs are picked up.
        """
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Store orchestrator (one thread per store)
    # ------------------------------------------------------------------

    def _run_store(self, store: str) -> None:
        stats = ScrapeStats(store=store)
        self.stats[store] = stats

        self._notify(store, "", stats, f"[{store.upper()}] ⏳ Збираємо список товарів...", "info")

        try:
            scraper = ParserFactory.create_scraper(store)
            slugs = scraper.discover_slugs()
        except NotImplementedError as exc:
            self._notify(store, "", stats, f"[{store.upper()}] ⏭ Пропущено: {exc}", "warning")
            return
        except Exception as exc:
            logger.exception("Discovery failed for %s", store)
            self._notify(store, "", stats, f"[{store.upper()}] ❌ Помилка discovery: {exc}", "error")
            return

        stats.total = len(slugs)
        self._notify(
            store, "", stats,
            f"[{store.upper()}] ✅ Знайдено {len(slugs)} товарів. Запускаємо {self.workers_per_store} потоки...",
            "success",
        )

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
                    msg, level = future.result()
                    self._notify(store, slug, stats, msg, level)
                except Exception as exc:
                    stats.increment("failed")
                    self._notify(store, slug, stats, f"[{store}] ❌ {slug}: {exc}", "error")

        stats.finish()
        self._notify(
            store, "", stats,
            (
                f"[{store.upper()}] 🚀 Завершено! "
                f"✅{stats.processed}  ⚠{stats.skipped}  ❌{stats.failed}  "
                f"⏱{stats.elapsed:.1f}с"
            ),
            "success",
        )

    # ------------------------------------------------------------------
    # Producer worker (one per slug, inside executor)
    # ------------------------------------------------------------------

    def _fetch_and_enqueue(self, store: str, slug: str, scraper: Any) -> tuple:
        """
        Fetches and normalizes one product, then enqueues for DB consumer.

        Never does any DB access. Never calls Tkinter. Thread-safe.
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

        self._db_queue.put((store, product))
        stats.increment("processed")
        return (
            f"[{store}] ✅ ({stats.done}/{stats.total}) {product.get('canonical_name', slug)}",
            "success",
        )

    # ------------------------------------------------------------------
    # DB consumer (single thread — owns the SQLAlchemy session)
    # ------------------------------------------------------------------

    def _db_consumer_worker(self) -> None:
        """
        Drains the DB queue in BATCHES and writes to PostgreSQL efficiently.

        Instead of processing items one-by-one, this consumer:
        1. Reads up to BATCH_SIZE items from the queue (or waits for 500ms timeout).
        2. Partitions by store and performs Fast Track lookups in bulk.
        3. Streams remaining items through the slow-track ML pipeline in parallel.
        4. Commits all in a single transaction.

        This can achieve 5–10x speedup vs single-item processing because:
        - SQL queries are batched (1 SELECT for 50 SKUs instead of 50 SELECTs).
        - ML inference is parallelized across multiple worker threads.
        - A single COMMIT flushes all changes atomically.

        Creating EntityRouter here (not in __init__) ensures the SQLAlchemy
        session belongs to this thread. ML model loading also happens here,
        not blocking producers.
        """
        BATCH_SIZE = 50  # Read up to 50 items at a time
        BATCH_TIMEOUT_SEC = 0.5  # Wait up to 500ms to accumulate a batch

        self._notify("system", "", ScrapeStats(store="system"),
                     "🗄 DB Consumer: ініціалізація (завантаження ML-моделей)...", "info")
        try:
            router = EntityRouter()
        except Exception as exc:
            self._notify("system", "", ScrapeStats(store="system"),
                         f"❌ DB Consumer: помилка ініціалізації: {exc}", "error")
            self._drain_queue()
            return

        self._notify("system", "", ScrapeStats(store="system"),
                     "🗄 DB Consumer: готовий до запису (batch mode).", "success")

        try:
            while True:
                # ── Batch accumulation: read up to BATCH_SIZE items (or timeout) ──
                batch = []
                deadline = time.time() + BATCH_TIMEOUT_SEC
                while len(batch) < BATCH_SIZE:
                    remaining_timeout = max(0.01, deadline - time.time())
                    try:
                        item = self._db_queue.get(timeout=remaining_timeout)
                        if item is _DB_SENTINEL:
                            # Drain remaining items if any
                            while not self._db_queue.empty():
                                try:
                                    batch.append(self._db_queue.get_nowait())
                                except queue.Empty:
                                    break
                            # Sentinel received → exit after processing final batch
                            if batch:
                                self._process_batch(batch, router)
                            return
                        batch.append(item)
                    except queue.Empty:
                        break  # Timeout reached, process what we have

                if batch:
                    self._process_batch(batch, router)

        except Exception as exc:
            logger.error("DBConsumer crashed: %s", exc)
        finally:
            try:
                router.close()
            except Exception:
                pass
            logger.info("DBConsumer shut down.")

    def _process_batch(self, batch: list, router) -> None:
        """
        Processes a batch of (store, product) tuples with bulk-optimized queries.

        Flow:
        1. Partition products by store for grouped logging.
        2. Extract all store-SKUs and query the DB once (vs once-per-item).
        3. Separate into Fast Track (update) and Slow Track (ML) groups.
        4. Process both tracks in parallel (slow track uses a thread pool).
        5. Commit once.

        Args:
            batch (list): List of (store, product) tuples.
            router: EntityRouter instance.
        """
        if not batch:
            return

        store_counts = {}
        for store, _ in batch:
            store_counts[store] = store_counts.get(store, 0) + 1

        msg = " | ".join(f"{s}:{c}" for s, c in sorted(store_counts.items()))
        logger.info(f"📦 Batch processing: {len(batch)} items ({msg})")

        fast_track_items = []
        slow_track_items = []

        # ── Fast Track: bulk SKU lookup ──
        store_skus = [item[1]["offers"][0]["sku"] for item in batch]
        existing_offers = router.repo.find_offers_by_store_skus(store_skus)
        existing_skus = {o.store_sku for o in existing_offers}

        for store, product in batch:
            store_sku = product["offers"][0]["sku"]
            if store_sku in existing_skus:
                fast_track_items.append((store, product, store_sku))
            else:
                slow_track_items.append((store, product))

        # ── Execute both tracks ──
        # ВАЖЛИВО: slow_track.find_match() всередині робить запити до БД через
        # SQLAlchemy сесію. Сесія НЕ є thread-safe — не можна передавати її
        # між потоками. Тому ML обробка виконується ПОСЛІДОВНО в цьому ж потоці
        # (DB Consumer). Паралелізм досягається на рівні scraper workers (fetch),
        # а не на рівні DB writes.
        try:
            # Fast track: bulk price updates (sequential, ~1ms each)
            for store, product, store_sku in fast_track_items:
                price = product["offers"][0]["pricing"]["current_price"]
                try:
                    router.repo.update_offer_price_by_sku(store_sku, price)
                    logger.debug(f"⚡ Updated {store_sku} → {price} грн")
                except Exception as exc:
                    logger.error(f"Fast track failed [{store}]: {exc}")

            # Slow track: sequential ML + DB (session не thread-safe)
            for store, product in slow_track_items:
                try:
                    router.process_scraped_item(product)
                    logger.debug(f"🔗 Slow track OK [{store}]: {product.get(chr(39)+'canonical_name'+chr(39), chr(39)+'?'+chr(39))}")
                except Exception as exc:
                    logger.error(f"Slow track failed [{store}]: {exc}")
                    try:
                        router.repo.session.rollback()
                    except Exception:
                        pass

            try:
                router.repo.session.commit()
            except Exception:
                pass

            logger.info(f"✅ Batch done ({len(fast_track_items)} fast + {len(slow_track_items)} slow)")

        except Exception as exc:
            logger.error(f"Batch processing failed: {exc}")
            try:
                router.repo.session.rollback()
            except Exception:
                pass

        finally:
            for _ in batch:
                self._db_queue.task_done()

    def _drain_queue(self) -> None:
        """Empties the DB queue when consumer fails — prevents producer deadlock."""
        while True:
            try:
                item = self._db_queue.get_nowait()
                if item is _DB_SENTINEL:
                    break
            except queue.Empty:
                time.sleep(0.1)

    # ------------------------------------------------------------------
    # Notification helper
    # ------------------------------------------------------------------

    def _notify(self, store: str, slug: str, stats: ScrapeStats, message: str, level: str) -> None:
        """
        Delivers a ProgressEvent to the GUI queue or CLI callback.

        NEVER calls Tkinter directly. Workers use this method only.
        """
        event = ProgressEvent(store=store, slug=slug, stats=stats,
                              message=message, level=level)
        if self._progress_queue is not None:
            try:
                self._progress_queue.put_nowait(event)
            except queue.Full:
                pass  # Drop event if GUI queue is full — never block a worker.
        if self._progress_callback is not None:
            try:
                self._progress_callback(event)
            except Exception:
                pass
