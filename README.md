# Nöbet Scheduler

A CP-SAT-based monthly shift scheduler for a hospital emergency department. Given a
roster of doctors (seniority, target shift count, leave days) and a target month, it
builds an exact-assignment optimization model with [Google OR-Tools](https://developers.google.com/optimization)
CP-SAT and produces a day/night shift schedule that satisfies every hard constraint
(role eligibility, exact per-doctor shift totals, leave days, consecutive-shift rules,
etc.) while optimizing soft preferences (seniority-based role priority, day/night
balance, spread across the month).

Output is an Excel workbook (`nobet_listesi.xlsx`) with the full shift-by-shift
schedule plus a per-doctor summary.

## Requirements

- Python 3.10+
- macOS or Windows (the packaged desktop app targets both; see [Packaging](#packaging))

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

### Desktop GUI

```bash
python -m nobet_scheduler.gui
```

This opens a small Tkinter window where you:

1. Pick a doctor roster Excel file
2. Pick the output folder (defaults to the Desktop)
3. Enter the month and year
4. Click "Hesapla" — the solve runs in the background; a popup reports success
   (with the output file's path) or a clear error message if the roster is
   infeasible or malformed

### Excel input format

The roster file must contain a sheet named **"Doktorlar"** with these columns
(any column order is fine, matched by header name):

| Column           | Meaning                                                         |
|-------------------|------------------------------------------------------------------|
| İsim              | Doctor's name                                                     |
| Kıdem             | Seniority: `0` = junior, `1` and up = senior (no fixed upper bound) |
| Nöbet Hedefi      | Exact number of shifts this doctor must be assigned this month     |
| İzin Günleri      | Leave days this month, as day numbers (see below)                  |

**İzin Günleri** is free text: comma-separated day numbers, single (`25`) or
range (`1-10`) — mixing both is fine, e.g. `1-10, 25`. Extra whitespace and
stray commas are tolerated. Leave the cell empty for no leave days.

A ready-to-use example is at `data/doctors_september2026.xlsx`.

### Command line (alternative to the GUI)

```bash
python -m nobet_scheduler --doctors path/to/roster.csv --month 9 --year 2026 --output nobet_listesi.xlsx
```

The CLI also accepts a doctor roster as CSV or JSON (see `data/doctors_sample.csv` /
`data/doctors_sample.json` for the expected shape); Excel input is GUI/`excel_input`
module territory as described above.

## Running tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Packaging

The desktop GUI can be packaged into a standalone app with
[PyInstaller](https://pyinstaller.org/) using the included spec file:

```bash
pip install pyinstaller   # already in requirements.txt
pyinstaller --noconfirm NobetListesi.spec
```

This builds in `--onedir --windowed` mode (native architecture only — no
universal2/cross-arch build). The result:

- **macOS**: `dist/NobetListesi.app` — double-clickable app bundle
- **Windows**: run the same command on a Windows machine to produce
  `dist/NobetListesi/NobetListesi.exe` (PyInstaller doesn't cross-compile, so a
  Windows build must be produced on Windows)

`collect_all()` is used in the spec for `ortools` and `openpyxl` to make sure
their native extensions and data files are bundled correctly — the most common
cause of a packaged build failing when the same code works fine via
`python -m ...`.
