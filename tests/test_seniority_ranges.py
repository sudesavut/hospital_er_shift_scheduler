"""Sanity checks that the model works with arbitrary seniority ranges,
not just the original 0-4 example scale — seniority is now an unbounded
non-negative integer, and role-priority weighting must use each doctor's
RELATIVE rank among the seniority levels actually present, not the raw value.
"""

from nobet_scheduler.doctor import Doctor
from nobet_scheduler.model import (
    ROLE_COMEZ_BASI,
    ROLE_KAPICI,
    ROLE_NOBET_BASI,
    build_and_solve_schedule,
)


def _assert_feasible_and_exact(doctors, year, month):
    result = build_and_solve_schedule(doctors, year=year, month=month, seed=7, max_time_seconds=60)

    for d in doctors:
        assert result.doctor_totals[d.name] == d.shift_count_target

    for s in result.shifts:
        assert len(result.assignments[(s, ROLE_NOBET_BASI)]) == 1
        if s.is_day_shift:
            assert len(result.assignments[(s, ROLE_KAPICI)]) == 1
        assert len(result.assignments.get((s, ROLE_COMEZ_BASI), [])) >= 1

        # only senior (seniority >= 1) doctors may hold senior-only roles,
        # regardless of what the actual seniority values in this pool are
        for role in (ROLE_NOBET_BASI, ROLE_KAPICI, ROLE_COMEZ_BASI):
            for name in result.assignments.get((s, role), []):
                doctor = next(d for d in doctors if d.name == name)
                assert doctor.is_senior

    return result


def test_narrow_seniority_range_0_to_2_is_feasible():
    doctors = (
        [Doctor(f"Junior{i}", seniority=0, shift_count_target=8) for i in range(8)]
        + [Doctor(f"Mid{i}", seniority=1, shift_count_target=16) for i in range(6)]
        + [Doctor(f"Senior{i}", seniority=2, shift_count_target=15) for i in range(4)]
    )
    # November 2026 has 30 days.
    _assert_feasible_and_exact(doctors, year=2026, month=11)


def test_wide_and_non_contiguous_seniority_range_is_feasible():
    # Seniority values 0, 3, 5, 7: sparse and non-contiguous on purpose, to
    # prove the priority objective ranks by relative position among the
    # levels present, not by any assumed fixed max (e.g. "seniority == 4").
    doctors = (
        [Doctor(f"Junior{i}", seniority=0, shift_count_target=8) for i in range(8)]
        + [Doctor(f"Level3_{i}", seniority=3, shift_count_target=15) for i in range(4)]
        + [Doctor(f"Level5_{i}", seniority=5, shift_count_target=17) for i in range(3)]
        + [Doctor(f"Level7_{i}", seniority=7, shift_count_target=17) for i in range(3)]
    )
    # October 2026 has 31 days.
    _assert_feasible_and_exact(doctors, year=2026, month=10)
