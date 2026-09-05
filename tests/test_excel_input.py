"""End-to-end test: Excel parser + CP-SAT engine, no GUI involved.

Verifies the Excel roster (data/doctors_september2026.xlsx, converted from
the existing doctors_september2026.json test data) parses to the same
doctors and solves to a schedule that fulfills every target exactly — the
same guarantee the JSON-based test already checks.
"""

import json
from pathlib import Path

import pytest

from nobet_scheduler.doctor import Doctor
from nobet_scheduler.excel_input import ExcelInputError, load_doctors_from_excel
from nobet_scheduler.model import (
    ROLE_COMEZ_BASI,
    ROLE_KAPICI,
    ROLE_NOBET_BASI,
    build_and_solve_schedule,
)

EXCEL_FIXTURE = Path(__file__).parent.parent / "data" / "doctors_september2026.xlsx"
JSON_FIXTURE = Path(__file__).parent.parent / "doctors_september2026.json"


def _load_json_doctors() -> list[Doctor]:
    with JSON_FIXTURE.open(encoding="utf-8") as f:
        raw = json.load(f)
    from datetime import date

    return [
        Doctor(
            name=entry["name"],
            seniority=int(entry["seniority"]),
            shift_count_target=int(entry["shift_count_target"]),
            leave_dates={date.fromisoformat(d) for d in entry["leave_dates"]},
        )
        for entry in raw
    ]


def test_excel_parser_matches_json_source_data():
    excel_doctors = load_doctors_from_excel(EXCEL_FIXTURE, year=2026, month=9)
    json_doctors = _load_json_doctors()

    excel_by_name = {d.name: d for d in excel_doctors}
    json_by_name = {d.name: d for d in json_doctors}

    assert set(excel_by_name) == set(json_by_name)
    for name in json_by_name:
        assert excel_by_name[name] == json_by_name[name], f"Mismatch for {name}"


def test_excel_roster_solves_to_a_feasible_schedule_matching_targets():
    doctors = load_doctors_from_excel(EXCEL_FIXTURE, year=2026, month=9)
    result = build_and_solve_schedule(doctors, year=2026, month=9, seed=42, max_time_seconds=120)

    for d in doctors:
        assert result.doctor_totals[d.name] == d.shift_count_target

    for s in result.shifts:
        assert len(result.assignments[(s, ROLE_NOBET_BASI)]) == 1
        if s.is_day_shift:
            assert len(result.assignments[(s, ROLE_KAPICI)]) == 1
        assert len(result.assignments.get((s, ROLE_COMEZ_BASI), [])) >= 1


def test_leave_days_range_and_single_mixed_format():
    excel_doctors = load_doctors_from_excel(EXCEL_FIXTURE, year=2026, month=9)
    ozan = next(d for d in excel_doctors if d.name == "Dr. Ozan Sarıkaya")
    # source JSON: 2026-09-01..10 plus 2026-09-25 -> Excel cell "1-10, 25"
    from datetime import date

    expected = {date(2026, 9, day) for day in range(1, 11)} | {date(2026, 9, 25)}
    assert ozan.leave_dates == expected


def test_invalid_leave_cell_reports_row_number(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Doktorlar"
    ws.append(["İsim", "Kıdem", "Nöbet Hedefi", "İzin Günleri"])
    ws.append(["Dr. Test", 1, 5, "abc"])
    bad_file = tmp_path / "bad.xlsx"
    wb.save(bad_file)

    with pytest.raises(ExcelInputError, match="Satır 2"):
        load_doctors_from_excel(bad_file, year=2026, month=9)


def test_missing_sheet_reports_clear_error(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.title = "YanlışSayfa"
    bad_file = tmp_path / "no_sheet.xlsx"
    wb.save(bad_file)

    with pytest.raises(ExcelInputError, match="Doktorlar"):
        load_doctors_from_excel(bad_file, year=2026, month=9)
