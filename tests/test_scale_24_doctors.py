from pathlib import Path

from nobet_scheduler.doctor import load_doctors
from nobet_scheduler.model import (
    ROLE_COMEZ_BASI,
    ROLE_KAPICI,
    ROLE_NOBET_BASI,
    build_and_solve_schedule,
)

FIXTURE = Path(__file__).parent.parent / "data" / "doctors_test_scale.csv"


def test_24_doctor_scale_is_feasible_for_september_2026():
    doctors = load_doctors(FIXTURE)
    result = build_and_solve_schedule(doctors, year=2026, month=9, seed=42, max_time_seconds=120)

    for d in doctors:
        assert result.doctor_totals[d.name] == d.shift_count_target

    for s in result.shifts:
        assert len(result.assignments[(s, ROLE_NOBET_BASI)]) == 1
        if s.is_day_shift:
            assert len(result.assignments[(s, ROLE_KAPICI)]) == 1
        assert len(result.assignments.get((s, ROLE_COMEZ_BASI), [])) >= 1
