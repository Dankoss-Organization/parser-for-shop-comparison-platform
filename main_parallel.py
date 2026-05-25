"""
main_parallel.py — Entry point for the multithreaded scraping run.

Supports two modes:
    1. **GUI mode** (default): Opens the Tkinter dashboard. All controls
       are available interactively.
    2. **CLI mode** (``--no-gui``): Runs the engine headlessly and prints
       progress to stdout. Suitable for CI/CD or server environments.

Usage:
    # GUI (interactive)
    python main_parallel.py

    # CLI headless
    python main_parallel.py --no-gui --stores atb silpo --workers 6
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)-20s] %(levelname)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def run_gui():
    """Launches the Tkinter dashboard."""
    from gui.scraping_dashboard import ScrapingDashboard
    ScrapingDashboard().run()


def run_cli(stores, workers):
    """
    Runs the parallel engine in headless CLI mode.

    Args:
        stores (List[str]): Stores to scrape.
        workers (int): Thread count per store.
    """
    from core.parallel_engine import ParallelScrapingEngine, ProgressEvent

    def on_event(event: ProgressEvent):
        print(event.message)

    engine = ParallelScrapingEngine(
        stores=stores,
        workers_per_store=workers,
        progress_callback=on_event,
    )

    try:
        stats = engine.run()
    except KeyboardInterrupt:
        print("\n🛑 Перервано користувачем (Ctrl+C).")
        engine.stop()
        return

    print("\n" + "=" * 60)
    print("  ПІДСУМОК")
    print("=" * 60)
    for store, s in stats.items():
        print(
            f"  {store:<14} ✅{s.processed}  ⚠{s.skipped}  ❌{s.failed}  "
            f"⏱{s.elapsed:.1f}s"
        )
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Parallel scraping engine")
    parser.add_argument(
        "--no-gui", action="store_true",
        help="Run in headless CLI mode (no Tkinter window)."
    )
    parser.add_argument(
        "--stores", nargs="+",
        default=["atb", "silpo", "fora", "varus"],
        help="Stores to scrape (space-separated). Default: atb silpo fora varus"
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="Number of worker threads per store. Default: 4"
    )
    args = parser.parse_args()

    if args.no_gui:
        run_cli(args.stores, args.workers)
    else:
        run_gui()


if __name__ == "__main__":
    main()
