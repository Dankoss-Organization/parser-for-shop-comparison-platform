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

_DB_SENTINEL = None

@dataclass
class ScrapeStats:
    store: str
    total: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def increment(self, field_name: str) -> None:
        with self._lock:
            setattr(self, field_name, getattr(self, field_name) + 1)

    def finish(self) -> None:
        self.end_time = time.time()

    @property
    def elapsed(self) -> float:
        end = self.end_time if self.end_time else time.time()
        return end - self.start_time

    @property
    def done(self) -> int:
        return self.processed + self.failed + self.skipped

@dataclass
class ProgressEvent:
    store: str
    slug: str
    stats: ScrapeStats
    message: str
    level: str = "info"

class ParallelScrapingEngine:
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
        self._db_queue: queue.Queue = queue.Queue(maxsize=db_queue_maxsize)
        self.stats: Dict[str, ScrapeStats] = {}
        self._stop_event = threading.Event()
        self._active_producers = 0
        self._producers_lock = threading.Lock()

    def run(self) -> Dict[str, ScrapeStats]:
        self._stop_event.clear()
        with self._producers_lock:
            self._active_producers = len(self.stores)

        db_thread = threading.Thread(target=self._db_consumer_worker, name="DBConsumer", daemon=True)
        db_thread.start()

        store_threads = []
        for store in self.stores:
            t = threading.Thread(target=self._run_store, args=(store,), name=f"StoreOrchestrator-{store}", daemon=True)
            t.start()
            store_threads.append(t)

        for t in store_threads:
            t.join()

        self._db_queue.put(_DB_SENTINEL)
        db_thread.join()
        return self.stats

    def stop(self) -> None:
        self._stop_event.set()
        logger.info("Stop requested — draining remaining work...")

    def _run_store(self, store: str) -> None:
        stats = ScrapeStats(store=store)
        self.stats[store] = stats

        self._notify(ProgressEvent(store=store, slug="", stats=stats, message=f"[{store.upper()}] Починаємо сканування каталогу...", level="info"))

        try:
            scraper = ParserFactory.create_scraper(store)
            slugs = scraper.discover_slugs()
        except Exception as exc:
            logger.exception("Discovery failed for %s", store)
            self._notify(ProgressEvent(store=store, slug="", stats=stats, message=f"[{store.upper()}] ❌ Помилка discovery: {exc}", level="error"))
            self._mark_producer_done()
            return

        stats.total = len(slugs)
        self._notify(ProgressEvent(store=store, slug="", stats=stats, message=f"[{store.upper()}] ✅ Знайдено {len(slugs)} товарів. Запуск потоків...", level="success"))

        with ThreadPoolExecutor(max_workers=self.workers_per_store, thread_name_prefix=f"Worker-{store}") as executor:
            futures = {executor.submit(self._fetch_and_enqueue, store, slug, scraper): slug for slug in slugs}
            for future in as_completed(futures):
                if self._stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                slug = futures[future]
                try:
                    result_msg, level = future.result()
                    self._notify(ProgressEvent(store=store, slug=slug, stats=stats, message=result_msg, level=level))
                except Exception as exc:
                    stats.increment("failed")
                    self._notify(ProgressEvent(store=store, slug=slug, stats=stats, message=f"[{store}] ❌ {slug}: {exc}", level="error"))

        stats.finish()
        self._notify(ProgressEvent(store=store, slug="", stats=stats, message=f"[{store.upper()}] 🚀 Завершено! Оброблено: {stats.processed} | Час: {stats.elapsed:.1f}с", level="success"))
        self._mark_producer_done()

    def _fetch_and_enqueue(self, store: str, slug: str, scraper: Any) -> tuple:
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
        return f"[{store}] ✅ ({stats.done}/{stats.total}) {product.get('canonical_name', slug)}", "success"

    def _db_consumer_worker(self) -> None:
        try:
            router = EntityRouter()
            logger.info("DBConsumer started.")
        except Exception as exc:
            logger.error("DBConsumer init failed: %s", exc)
            self._notify(ProgressEvent(store="system", slug="", stats=ScrapeStats("system"), message=f"❌ Помилка БД: {exc}", level="error"))
            while True:
                try:
                    item = self._db_queue.get_nowait()
                    self._db_queue.task_done()
                    if item is _DB_SENTINEL: break
                except queue.Empty:
                    break
            return

        try:
            while True:
                try:
                    item = self._db_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if item is _DB_SENTINEL:
                    self._db_queue.task_done()
                    break

                store, product = item
                try:
                    router.process_scraped_item(product)
                except Exception as exc:
                    logger.error("DB write failed for %s: %s", store, exc)
                    try: router.repo.session.rollback()
                    except Exception: pass
                finally:
                    self._db_queue.task_done()
        finally:
            try: router.close()
            except Exception: pass

    def _mark_producer_done(self) -> None:
        with self._producers_lock:
            self._active_producers -= 1

    def _notify(self, event: ProgressEvent) -> None:
        if self.progress_callback:
            try: self.progress_callback(event)
            except Exception: pass