"""Excel doctor-roster parser: "Doktorlar" sheet -> list[Doctor].

Expected columns (by header name, any order): İsim, Kıdem, Nöbet Hedefi,
İzin Günleri. İzin Günleri is free text: comma-separated day numbers, single
("25") or range ("1-10") mixed, tolerant of stray whitespace/commas, e.g.
"1-10, 25". Month/year are supplied by the caller (the GUI), not read from
the sheet, and used to turn day numbers into real dates.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import load_workbook

from .doctor import Doctor

SHEET_NAME = "Doktorlar"
COLUMN_NAME = "İsim"
COLUMN_SENIORITY = "Kıdem"
COLUMN_TARGET = "Nöbet Hedefi"
COLUMN_LEAVE_DAYS = "İzin Günleri"
REQUIRED_COLUMNS = [COLUMN_NAME, COLUMN_SENIORITY, COLUMN_TARGET, COLUMN_LEAVE_DAYS]


class ExcelInputError(Exception):
    """Raised when the Excel doctor roster is missing, malformed, or a cell
    (most commonly İzin Günleri) can't be parsed — always names the row."""


def _parse_leave_days_cell(cell_value: object, year: int, month: int, row_number: int) -> set[date]:
    if cell_value is None:
        return set()
    text = str(cell_value).strip()
    if not text:
        return set()

    day_numbers: set[int] = set()
    for raw_token in text.split(","):
        token = raw_token.strip()
        if not token:
            continue  # tolerate stray/doubled commas

        if "-" in token:
            parts = [p.strip() for p in token.split("-")]
            if len(parts) != 2 or not all(parts):
                raise ExcelInputError(
                    f"Satır {row_number}: İzin Günleri hücresindeki '{token}' aralığı anlaşılamadı "
                    "(beklenen format: 'başlangıç-bitiş', örn. '1-10')."
                )
            start_str, end_str = parts
            if not (start_str.isdigit() and end_str.isdigit()):
                raise ExcelInputError(
                    f"Satır {row_number}: İzin Günleri hücresindeki '{token}' aralığı sayısal değil."
                )
            start, end = int(start_str), int(end_str)
            if start > end:
                raise ExcelInputError(
                    f"Satır {row_number}: İzin Günleri hücresindeki '{token}' aralığında başlangıç "
                    "bitişten büyük."
                )
            day_numbers.update(range(start, end + 1))
        else:
            if not token.isdigit():
                raise ExcelInputError(
                    f"Satır {row_number}: İzin Günleri hücresindeki '{token}' geçerli bir gün "
                    "numarası değil."
                )
            day_numbers.add(int(token))

    leave_dates: set[date] = set()
    for day_number in day_numbers:
        try:
            leave_dates.add(date(year, month, day_number))
        except ValueError as exc:
            raise ExcelInputError(
                f"Satır {row_number}: '{day_number}' {year}-{month:02d} ayı için geçerli bir gün "
                f"değil ({exc})."
            ) from exc
    return leave_dates


def load_doctors_from_excel(path: str | Path, year: int, month: int) -> list[Doctor]:
    path = Path(path)
    wb = load_workbook(path, data_only=True)

    if SHEET_NAME not in wb.sheetnames:
        raise ExcelInputError(
            f"'{SHEET_NAME}' adlı bir sayfa bulunamadı. Bulunan sayfalar: {wb.sheetnames}"
        )
    ws = wb[SHEET_NAME]

    header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if header_row is None:
        raise ExcelInputError(f"'{SHEET_NAME}' sayfası boş.")

    col_index: dict[str, int] = {}
    for idx, value in enumerate(header_row):
        if value is not None and str(value).strip():
            col_index[str(value).strip()] = idx

    missing = [c for c in REQUIRED_COLUMNS if c not in col_index]
    if missing:
        raise ExcelInputError(
            f"'{SHEET_NAME}' sayfasında şu kolonlar eksik: {', '.join(missing)}. "
            f"Bulunan kolonlar: {list(col_index.keys())}"
        )

    doctors: list[Doctor] = []
    for row_number, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        name_cell = row[col_index[COLUMN_NAME]] if col_index[COLUMN_NAME] < len(row) else None
        if name_cell is None or not str(name_cell).strip():
            continue  # skip blank trailing rows

        name = str(name_cell).strip()
        seniority_raw = row[col_index[COLUMN_SENIORITY]]
        target_raw = row[col_index[COLUMN_TARGET]]
        leave_raw = row[col_index[COLUMN_LEAVE_DAYS]] if col_index[COLUMN_LEAVE_DAYS] < len(row) else None

        try:
            seniority = int(seniority_raw)
        except (TypeError, ValueError):
            raise ExcelInputError(
                f"Satır {row_number}: Kıdem değeri '{seniority_raw}' geçerli bir tam sayı değil."
            )

        try:
            shift_count_target = int(target_raw)
        except (TypeError, ValueError):
            raise ExcelInputError(
                f"Satır {row_number}: Nöbet Hedefi değeri '{target_raw}' geçerli bir tam sayı değil."
            )

        leave_dates = _parse_leave_days_cell(leave_raw, year, month, row_number)

        try:
            doctors.append(
                Doctor(
                    name=name,
                    seniority=seniority,
                    shift_count_target=shift_count_target,
                    leave_dates=leave_dates,
                )
            )
        except ValueError as exc:
            raise ExcelInputError(f"Satır {row_number}: {exc}") from exc

    if not doctors:
        raise ExcelInputError(f"'{SHEET_NAME}' sayfasında hiç doktor satırı bulunamadı.")

    return doctors
