"""Tkinter desktop GUI for the CP-SAT emergency-department shift scheduler.

Run with: python -m nobet_scheduler.gui
"""

from __future__ import annotations

import queue
import sys
import threading
import traceback
from pathlib import Path
from tkinter import StringVar, Tk, filedialog, messagebox, ttk

from .excel_input import ExcelInputError, load_doctors_from_excel
from .export import export_schedule
from .formulas import InfeasibleDoctorTargetError, InfeasibleTotalShiftsError
from .model import build_and_solve_schedule

OUTPUT_FILE_NAME = "nobet_listesi.xlsx"
QUEUE_POLL_INTERVAL_MS = 100


def _default_output_dir() -> str:
    desktop = Path.home() / "Desktop"
    return str(desktop if desktop.is_dir() else Path.home())


class SchedulerApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title("Nöbet Listesi Oluşturucu")
        root.resizable(False, False)

        self.excel_path_var = StringVar()
        self.output_dir_var = StringVar(value=_default_output_dir())
        self.month_var = StringVar()
        self.year_var = StringVar()
        self.status_var = StringVar(value="")

        # Cross-thread handoff: the background worker never touches Tk directly
        # (calling root.after from a worker thread is not reliably safe on
        # every platform/Tk build — notably flaky on macOS). It only puts a
        # ("success"|"error", payload) tuple on this thread-safe queue; the
        # main thread drains it via a self-rescheduling root.after poll.
        self._result_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        frame = ttk.Frame(root, padding=16)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Doktor Excel Dosyası:").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Entry(frame, textvariable=self.excel_path_var, width=48).grid(
            row=1, column=0, columnspan=2, sticky="we"
        )
        ttk.Button(frame, text="Seç...", command=self._pick_excel_file).grid(row=1, column=2, padx=(8, 0))

        ttk.Label(frame, text="Kayıt Klasörü (çıktı):").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(12, 0)
        )
        ttk.Entry(frame, textvariable=self.output_dir_var, width=48).grid(
            row=3, column=0, columnspan=2, sticky="we"
        )
        ttk.Button(frame, text="Seç...", command=self._pick_output_dir).grid(row=3, column=2, padx=(8, 0))

        ttk.Label(frame, text="Ay (1-12):").grid(row=4, column=0, sticky="w", pady=(12, 0))
        ttk.Label(frame, text="Yıl:").grid(row=4, column=1, sticky="w", pady=(12, 0))
        ttk.Entry(frame, textvariable=self.month_var, width=10).grid(row=5, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.year_var, width=10).grid(row=5, column=1, sticky="w")

        self.calculate_button = ttk.Button(frame, text="Hesapla", command=self._on_calculate_clicked)
        self.calculate_button.grid(row=6, column=0, columnspan=3, pady=(16, 4), sticky="we")

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=7, column=0, columnspan=3, sticky="we")

        ttk.Label(frame, textvariable=self.status_var, foreground="gray").grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        self.root.after(QUEUE_POLL_INTERVAL_MS, self._poll_result_queue)

    def _pick_excel_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Doktor Excel dosyasını seç",
            filetypes=[("Excel dosyaları", "*.xlsx")],
        )
        if path:
            self.excel_path_var.set(path)

    def _pick_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Çıktının kaydedileceği klasörü seç")
        if path:
            self.output_dir_var.set(path)

    def _on_calculate_clicked(self) -> None:
        excel_path = self.excel_path_var.get().strip()
        output_dir = self.output_dir_var.get().strip() or _default_output_dir()
        month_text = self.month_var.get().strip()
        year_text = self.year_var.get().strip()

        if not excel_path:
            messagebox.showerror("Hata", "Lütfen bir Excel dosyası seçin.")
            return
        if not Path(excel_path).exists():
            messagebox.showerror("Hata", f"Dosya bulunamadı:\n{excel_path}")
            return
        if not Path(output_dir).is_dir():
            messagebox.showerror("Hata", f"Kayıt klasörü bulunamadı:\n{output_dir}")
            return

        try:
            month = int(month_text)
            year = int(year_text)
        except ValueError:
            messagebox.showerror("Hata", "Ay ve yıl geçerli tam sayılar olmalı.")
            return
        if not (1 <= month <= 12):
            messagebox.showerror("Hata", "Ay 1 ile 12 arasında olmalı.")
            return

        output_path = str(Path(output_dir) / OUTPUT_FILE_NAME)

        self._set_busy(True)
        thread = threading.Thread(
            target=self._run_calculation, args=(excel_path, year, month, output_path), daemon=True
        )
        thread.start()

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.calculate_button.config(state="disabled")
            self.progress.start(12)
            self.status_var.set("Hesaplanıyor, lütfen bekleyin (birkaç saniye sürebilir)...")
        else:
            self.calculate_button.config(state="normal")
            self.progress.stop()
            self.status_var.set("")

    def _run_calculation(self, excel_path: str, year: int, month: int, output_path: str) -> None:
        """Runs on a background thread. Never touches Tk — only ever puts a
        result on the thread-safe queue; the main-thread poll loop does the
        rest (see _poll_result_queue)."""
        try:
            doctors = load_doctors_from_excel(excel_path, year=year, month=month)
            result = build_and_solve_schedule(doctors, year=year, month=month)
            export_schedule(result, doctors, output_path)
        except (
            ExcelInputError,
            InfeasibleTotalShiftsError,
            InfeasibleDoctorTargetError,
            RuntimeError,
        ) as exc:
            self._result_queue.put(("error", str(exc)))
            return
        except Exception as exc:  # noqa: BLE001 - surface every failure to the user, never just the console
            self._result_queue.put(
                ("error", f"Beklenmeyen bir hata oluştu:\n{exc}\n\n{traceback.format_exc()}")
            )
            return
        self._result_queue.put(("success", output_path))

    def _poll_result_queue(self) -> None:
        """Runs on the main thread only, rescheduled via root.after every
        QUEUE_POLL_INTERVAL_MS for as long as the app is alive. Draining the
        queue here (instead of the worker thread calling into Tk directly)
        is what makes the success/error popup show up reliably."""
        try:
            while True:
                kind, payload = self._result_queue.get_nowait()
                if kind == "success":
                    self._show_success(payload)
                else:
                    self._show_error(payload)
        except queue.Empty:
            pass
        finally:
            self.root.after(QUEUE_POLL_INTERVAL_MS, self._poll_result_queue)

    def _show_error(self, message: str) -> None:
        self._set_busy(False)
        messagebox.showerror("Hata", message)

    def _show_success(self, output_path: str) -> None:
        self._set_busy(False)
        messagebox.showinfo("Tamamlandı", f"Nöbet listesi oluşturuldu:\n{output_path}")


def _run_selftest(excel_path: str, year: int, month: int, output_path: str) -> None:
    """Headless pipeline check for verifying a *packaged* (frozen) build
    without driving real UI automation: exercises the exact same Excel-parse
    -> CP-SAT solve -> export code path the GUI's background thread runs,
    proving every bundled dependency/resource is actually importable and
    working inside the frozen executable. Not part of normal app usage.

    Invoked as: <packaged executable> --selftest <excel> <year> <month> <output>
    """
    try:
        doctors = load_doctors_from_excel(excel_path, year=year, month=month)
        result = build_and_solve_schedule(doctors, year=year, month=month)
        export_schedule(result, doctors, output_path)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    print(f"SELFTEST_OK:{output_path}")
    sys.exit(0)


def main() -> None:
    if len(sys.argv) >= 6 and sys.argv[1] == "--selftest":
        _run_selftest(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
        return
    root = Tk()
    SchedulerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
