"""
Tkinter-based scraping dashboard with real-time progress display.

This module provides a fully functional GUI that:
- Lets the user select which stores to scrape and configure thread counts.
- Displays live log output from worker threads.
- Shows per-store progress bars that update as products are processed.
- Allows starting, stopping, and re-running the scraping engine.

Thread-safety note:
    Tkinter widgets must only be mutated from the main thread. Worker threads
    deliver updates via ``root.after(0, callback)`` which schedules execution
    on the main event loop — the standard Tkinter threading pattern.

Design Patterns:
    - Observer: ``ParallelScrapingEngine`` calls ``progress_callback`` which
      dispatches events to the GUI via ``root.after``.
    - MVC-lite: ``ScrapingDashboard`` (View + Controller) owns the engine
      (Model) and reacts to its events.

Usage:
    >>> python gui/scraping_dashboard.py
    or
    >>> from gui.scraping_dashboard import ScrapingDashboard
    >>> ScrapingDashboard().run()
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
from typing import Dict, Optional
from datetime import datetime

from core.parallel_engine import ParallelScrapingEngine, ProgressEvent, ScrapeStats

# All stores the platform knows about
ALL_STORES = ["atb", "silpo", "fora", "varus", "novus", "megamarket",
              "ekomarket", "torba", "ultramarket", "metro", "auchan"]

# Colour scheme
BG_DARK = "#1e1e2e"
BG_PANEL = "#2a2a3e"
BG_CARD = "#313149"
ACCENT = "#a78bfa"
SUCCESS = "#4ade80"
WARNING = "#fbbf24"
ERROR = "#f87171"
TEXT_MAIN = "#e2e8f0"
TEXT_DIM = "#94a3b8"
FONT_MONO = ("Consolas", 10)
FONT_UI = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 13, "bold")


class StoreProgressCard(ttk.Frame):
    """
    A single card widget that shows live progress for one store.

    Attributes:
        store (str): Store identifier displayed in the card header.
    """

    def __init__(self, parent, store: str, **kwargs):
        super().__init__(parent, style="Card.TFrame")
        self.store = store
        self._build()

    def _build(self):
        self.configure(padding=8)

        header = tk.Frame(self, bg=BG_CARD)
        header.pack(fill="x")

        self._store_label = tk.Label(
            header, text=self.store.upper(),
            font=("Segoe UI", 10, "bold"),
            fg=ACCENT, bg=BG_CARD
        )
        self._store_label.pack(side="left")

        self._pct_label = tk.Label(
            header, text="0%",
            font=FONT_MONO, fg=TEXT_DIM, bg=BG_CARD
        )
        self._pct_label.pack(side="right")

        self._bar = ttk.Progressbar(self, mode="determinate", length=220)
        self._bar.pack(fill="x", pady=(4, 2))

        self._status_label = tk.Label(
            self, text="Очікування...",
            font=("Segoe UI", 8), fg=TEXT_DIM, bg=BG_CARD,
            anchor="w", wraplength=220
        )
        self._status_label.pack(fill="x")

        self._detail_label = tk.Label(
            self, text="",
            font=("Segoe UI", 8), fg=TEXT_DIM, bg=BG_CARD,
            anchor="w"
        )
        self._detail_label.pack(fill="x")

        self.configure(style="Card.TFrame")
        self.pack_propagate(False)
        self.configure(width=240, height=110)

    def update_stats(self, stats: ScrapeStats, message: str, level: str):
        """
        Refreshes the card from a ``ScrapeStats`` snapshot.

        Must be called from the main Tkinter thread.

        Args:
            stats: Current scraping statistics.
            message: Last log message for this store.
            level: Log level string (``"success"``, ``"error"``, etc.).
        """
        colour_map = {
            "success": SUCCESS, "error": ERROR,
            "warning": WARNING, "info": TEXT_MAIN,
        }
        colour = colour_map.get(level, TEXT_MAIN)

        if stats.total > 0:
            pct = int((stats.done / stats.total) * 100)
            self._bar["value"] = pct
            self._pct_label.config(text=f"{pct}%")
        else:
            self._bar["value"] = 0
            self._pct_label.config(text="—")

        # Truncate long messages for the card
        short_msg = message[message.find("]") + 1:].strip() if "]" in message else message
        if len(short_msg) > 38:
            short_msg = short_msg[:35] + "..."
        self._status_label.config(text=short_msg, fg=colour)

        if stats.total > 0:
            self._detail_label.config(
                text=(
                    f"✅{stats.processed}  ⚠{stats.skipped}  "
                    f"❌{stats.failed}  ⏱{stats.elapsed:.0f}s"
                ),
                fg=TEXT_DIM,
            )


class ScrapingDashboard:
    """
    Main GUI class for the parallel scraping dashboard.

    Assembles all Tkinter widgets, manages the ``ParallelScrapingEngine``
    lifecycle, and routes ``ProgressEvent`` objects to the correct widgets.

    Args:
        title (str): Window title string.
    """

    def __init__(self, title: str = "🛒 Parser Dashboard — Parallel Mode"):
        self.root = tk.Tk()
        self.root.title(title)
        self.root.configure(bg=BG_DARK)
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)

        self._engine: Optional[ParallelScrapingEngine] = None
        self._engine_thread: Optional[threading.Thread] = None
        self._store_vars: Dict[str, tk.BooleanVar] = {}
        self._store_cards: Dict[str, StoreProgressCard] = {}

        self._setup_styles()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG_DARK)
        style.configure("Card.TFrame", background=BG_CARD, relief="flat")
        style.configure("TLabel", background=BG_DARK, foreground=TEXT_MAIN, font=FONT_UI)
        style.configure("TCheckbutton", background=BG_PANEL, foreground=TEXT_MAIN, font=FONT_UI)
        style.configure("TProgressbar", troughcolor=BG_PANEL, background=ACCENT, thickness=10)
        style.configure("Start.TButton", font=("Segoe UI", 11, "bold"),
                        background=ACCENT, foreground="#1e1e2e")
        style.configure("Stop.TButton", font=("Segoe UI", 11, "bold"),
                        background=ERROR, foreground="#1e1e2e")
        style.configure("TScale", background=BG_PANEL, troughcolor=BG_DARK)
        style.map("TCheckbutton", background=[("active", BG_PANEL)])

    def _build_ui(self):
        # ── Top bar ──────────────────────────────────────────────────
        top = tk.Frame(self.root, bg=BG_DARK, pady=10)
        top.pack(fill="x", padx=16)

        tk.Label(top, text="🛒 Parallel Scraping Dashboard",
                 font=FONT_TITLE, fg=ACCENT, bg=BG_DARK).pack(side="left")

        self._status_var = tk.StringVar(value="⏸ Готово")
        tk.Label(top, textvariable=self._status_var,
                 font=FONT_MONO, fg=TEXT_DIM, bg=BG_DARK).pack(side="right")

        # ── Main layout: left panel + right log ──────────────────────
        main = tk.Frame(self.root, bg=BG_DARK)
        main.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        # Left: settings + store cards
        left = tk.Frame(main, bg=BG_DARK, width=280)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        self._build_settings_panel(left)
        self._build_store_selector(left)
        self._build_cards_panel(left)

        # Right: log
        right = tk.Frame(main, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)
        self._build_log_panel(right)

        # ── Bottom controls ──────────────────────────────────────────
        self._build_controls()

    def _build_settings_panel(self, parent):
        panel = tk.LabelFrame(parent, text="⚙ Налаштування",
                              bg=BG_PANEL, fg=ACCENT, font=FONT_UI,
                              bd=1, relief="flat", padx=8, pady=6)
        panel.pack(fill="x", pady=(0, 8))

        tk.Label(panel, text="Потоків на магазин:", bg=BG_PANEL, fg=TEXT_MAIN,
                 font=FONT_UI).pack(anchor="w")

        self._workers_var = tk.IntVar(value=4)
        workers_frame = tk.Frame(panel, bg=BG_PANEL)
        workers_frame.pack(fill="x")

        self._workers_scale = ttk.Scale(
            workers_frame, from_=1, to=16,
            variable=self._workers_var, orient="horizontal",
            command=lambda _: self._workers_label.config(
                text=str(self._workers_var.get()))
        )
        self._workers_scale.pack(side="left", fill="x", expand=True)
        self._workers_label = tk.Label(
            workers_frame, text="4", width=3,
            bg=BG_PANEL, fg=ACCENT, font=FONT_MONO
        )
        self._workers_label.pack(side="left")

    def _build_store_selector(self, parent):
        panel = tk.LabelFrame(parent, text="🏪 Магазини",
                              bg=BG_PANEL, fg=ACCENT, font=FONT_UI,
                              bd=1, relief="flat", padx=8, pady=6)
        panel.pack(fill="x", pady=(0, 8))

        btn_frame = tk.Frame(panel, bg=BG_PANEL)
        btn_frame.pack(fill="x", pady=(0, 4))
        tk.Button(btn_frame, text="Всі", command=self._select_all,
                  bg=BG_CARD, fg=TEXT_MAIN, font=("Segoe UI", 8),
                  relief="flat", cursor="hand2").pack(side="left", padx=(0, 4))
        tk.Button(btn_frame, text="Жодного", command=self._select_none,
                  bg=BG_CARD, fg=TEXT_MAIN, font=("Segoe UI", 8),
                  relief="flat", cursor="hand2").pack(side="left")

        grid = tk.Frame(panel, bg=BG_PANEL)
        grid.pack(fill="x")
        for i, store in enumerate(ALL_STORES):
            var = tk.BooleanVar(value=store in ("atb", "silpo"))
            self._store_vars[store] = var
            cb = ttk.Checkbutton(grid, text=store, variable=var,
                                 style="TCheckbutton")
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=2)

    def _build_cards_panel(self, parent):
        self._cards_outer = tk.LabelFrame(
            parent, text="📊 Прогрес",
            bg=BG_PANEL, fg=ACCENT, font=FONT_UI,
            bd=1, relief="flat", padx=4, pady=4
        )
        self._cards_outer.pack(fill="both", expand=True)

    def _build_log_panel(self, parent):
        header = tk.Frame(parent, bg=BG_DARK)
        header.pack(fill="x", pady=(0, 4))
        tk.Label(header, text="📋 Лог", font=FONT_TITLE,
                 fg=ACCENT, bg=BG_DARK).pack(side="left")
        tk.Button(header, text="Очистити", command=self._clear_log,
                  bg=BG_CARD, fg=TEXT_DIM, font=("Segoe UI", 8),
                  relief="flat", cursor="hand2").pack(side="right")

        self._log = scrolledtext.ScrolledText(
            parent, bg="#0f0f1a", fg=TEXT_MAIN,
            font=FONT_MONO, wrap="word",
            insertbackground=TEXT_MAIN,
            selectbackground=BG_CARD,
            relief="flat", state="disabled"
        )
        self._log.pack(fill="both", expand=True)

        # Tag colours for different log levels
        self._log.tag_config("success", foreground=SUCCESS)
        self._log.tag_config("error", foreground=ERROR)
        self._log.tag_config("warning", foreground=WARNING)
        self._log.tag_config("info", foreground=TEXT_MAIN)
        self._log.tag_config("dim", foreground=TEXT_DIM)

    def _build_controls(self):
        bar = tk.Frame(self.root, bg=BG_PANEL, pady=8)
        bar.pack(fill="x", padx=16, pady=(0, 12))

        self._start_btn = ttk.Button(
            bar, text="▶  Запустити", style="Start.TButton",
            command=self._on_start, cursor="hand2"
        )
        self._start_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = ttk.Button(
            bar, text="⏹  Зупинити", style="Stop.TButton",
            command=self._on_stop, state="disabled", cursor="hand2"
        )
        self._stop_btn.pack(side="left")

        # Overall progress bar
        self._overall_var = tk.DoubleVar(value=0)
        self._overall_bar = ttk.Progressbar(
            bar, variable=self._overall_var, mode="determinate", length=300
        )
        self._overall_bar.pack(side="right", padx=(8, 0))
        tk.Label(bar, text="Загальний прогрес:",
                 bg=BG_PANEL, fg=TEXT_DIM, font=FONT_UI).pack(side="right")

    # ------------------------------------------------------------------
    # Engine lifecycle
    # ------------------------------------------------------------------

    def _on_start(self):
        selected = [s for s, v in self._store_vars.items() if v.get()]
        if not selected:
            messagebox.showwarning("Увага", "Оберіть хоча б один магазин!")
            return

        self._start_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._status_var.set("🔄 Парсинг...")
        self._overall_var.set(0)

        # Rebuild store cards
        for widget in self._cards_outer.winfo_children():
            widget.destroy()
        self._store_cards.clear()

        card_grid = tk.Frame(self._cards_outer, bg=BG_PANEL)
        card_grid.pack(fill="both", expand=True)
        for i, store in enumerate(selected):
            card = StoreProgressCard(card_grid, store)
            card.grid(row=i // 1, column=i % 1, padx=4, pady=4, sticky="ew")
            card_grid.grid_columnconfigure(0, weight=1)
            self._store_cards[store] = card

        self._log_line(
            f"{'─'*60}\n▶ Старт парсингу | {datetime.now():%H:%M:%S} | "
            f"Магазини: {', '.join(selected)} | Потоків: {self._workers_var.get()}\n{'─'*60}",
            "dim"
        )

        workers = self._workers_var.get()
        prog_queue = queue.Queue()
        self._engine = ParallelScrapingEngine(
            stores=selected,
            workers_per_store=workers,
            progress_queue=prog_queue,
        )
        self._poll_progress(prog_queue)

        self._engine_thread = threading.Thread(
            target=self._engine_run_wrapper,
            daemon=True,
            name="EngineThread",
        )
        self._engine_thread.start()

    def _engine_run_wrapper(self):
        """Runs the engine and schedules UI update on completion."""
        try:
            self._engine.run()
        except Exception as exc:
            self.root.after(0, lambda: self._log_line(f"❌ Критична помилка: {exc}", "error"))
        finally:
            self.root.after(0, self._on_engine_done)

    def _on_stop(self):
        if self._engine:
            self._engine.stop()
            self._log_line("⏹ Зупинку запитано — чекаємо завершення поточних запитів...", "warning")
            self._stop_btn.config(state="disabled")

    def _on_engine_done(self):
        self._start_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        self._status_var.set("✅ Завершено")
        self._overall_var.set(100)
        self._log_line(
            f"{'─'*60}\n✅ Парсинг завершено | {datetime.now():%H:%M:%S}\n{'─'*60}",
            "success"
        )

    # ------------------------------------------------------------------
    # Progress event handling (called from worker threads via root.after)
    # ------------------------------------------------------------------

    def _poll_progress(self, prog_queue: queue.Queue):
        """
        Polls the progress queue every 50ms and applies events to the GUI.

        This is the correct Tkinter threading pattern:
        - Worker threads put events on a queue.Queue (thread-safe).
        - The main thread polls via root.after() — never calls Tkinter from workers.

        Args:
            prog_queue: The shared progress queue owned by the engine.
        """
        try:
            while True:
                event = prog_queue.get_nowait()
                self._apply_event(event)
        except queue.Empty:
            pass

        # If engine is still running, keep polling
        if self._engine_thread and self._engine_thread.is_alive():
            self.root.after(50, lambda: self._poll_progress(prog_queue))
        else:
            # Drain any remaining events after engine finishes
            try:
                while True:
                    self._apply_event(prog_queue.get_nowait())
            except queue.Empty:
                pass

    def _on_progress_event(self, event):
        """Fallback callback for CLI mode (not used in GUI)."""
        pass

    def _apply_event(self, event: ProgressEvent):
        """Applies a progress event to the GUI (runs on main thread)."""
        self._log_line(event.message, event.level)

        card = self._store_cards.get(event.store)
        if card:
            card.update_stats(event.stats, event.message, event.level)

        self._update_overall_progress()

    def _update_overall_progress(self):
        """Recalculates and sets the overall progress bar value."""
        if not self._engine:
            return
        total_done = total_all = 0
        for stats in self._engine.stats.values():
            total_done += stats.done
            total_all += stats.total
        if total_all > 0:
            self._overall_var.set((total_done / total_all) * 100)

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _log_line(self, message: str, level: str = "info"):
        """
        Appends a coloured line to the log widget.

        Args:
            message (str): Text to append.
            level (str): Tag name for colour (``"success"``, ``"error"``, etc.).
        """
        self._log.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] ", "dim")
        self._log.insert("end", message + "\n", level)
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    # ------------------------------------------------------------------
    # Store selector helpers
    # ------------------------------------------------------------------

    def _select_all(self):
        for var in self._store_vars.values():
            var.set(True)

    def _select_none(self):
        for var in self._store_vars.values():
            var.set(False)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        """Starts the Tkinter main event loop (blocking)."""
        self.root.mainloop()


if __name__ == "__main__":
    ScrapingDashboard().run()