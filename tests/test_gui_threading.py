"""Regression test for the GUI's cross-thread result handoff.

Bug this guards against: the background worker used to call
`root.after(0, self._show_success, ...)` directly from a non-main thread,
which is not reliably safe on every platform/Tk build (flaky on macOS in
particular) — the success popup could simply never appear, leaving the
"Hesaplanıyor..." status stuck forever.

The fix routes results through a thread-safe queue.Queue, drained only by a
main-thread poll loop scheduled with root.after. This test runs the REAL
background thread (real Excel parse + real CP-SAT solve + real export, no
mocking of the pipeline) several times in a row against the same running app,
pumping the Tk event loop by hand (no mainloop() in a test), and asserts the
(mocked, to avoid a blocking OS dialog) success popup fires and the status
text clears every single time.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from tkinter import Tk
from unittest.mock import patch

from nobet_scheduler.gui import SchedulerApp

EXCEL_FIXTURE = Path(__file__).parent.parent / "data" / "doctors_september2026.xlsx"


def _pump_until(root: Tk, predicate, timeout: float = 180.0, interval: float = 0.05) -> None:
    """Drive the Tk event loop by hand (no mainloop) until predicate() is
    true — this is what lets root.after callbacks actually fire in a test."""
    start = time.monotonic()
    while not predicate():
        root.update()
        if time.monotonic() - start > timeout:
            raise TimeoutError("Condition not met within timeout while pumping the Tk event loop")
        time.sleep(interval)


def test_success_popup_and_status_clear_across_repeated_runs(tmp_path):
    root = Tk()
    try:
        app = SchedulerApp(root)

        success_messages: list[str] = []
        with (
            patch("nobet_scheduler.gui.messagebox.showinfo", side_effect=lambda *a: success_messages.append(a[1])),
            patch("nobet_scheduler.gui.messagebox.showerror") as mock_error,
        ):
            for i in range(3):
                output_path = tmp_path / f"nobet_listesi_run_{i}.xlsx"

                app._set_busy(True)
                assert app.status_var.get() != ""

                thread = threading.Thread(
                    target=app._run_calculation,
                    args=(str(EXCEL_FIXTURE), 2026, 9, str(output_path)),
                    daemon=True,
                )
                thread.start()

                # Only the main-thread poll loop (root.after -> _poll_result_queue)
                # should be able to move this forward — proves the handoff works.
                _pump_until(root, lambda: len(success_messages) == i + 1)
                thread.join(timeout=5)

                assert output_path.exists(), f"run {i}: output file was never written"
                assert app.status_var.get() == "", f"run {i}: status text stuck instead of clearing"
                assert str(output_path) in success_messages[i]

            mock_error.assert_not_called()
    finally:
        root.destroy()
