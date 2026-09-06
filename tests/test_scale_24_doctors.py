from collections import defaultdict
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

    # Every senior doctor with at least 1 shift this month must have done
    # kapici at least once (hard constraint) — the seniority-based role
    # priority (nobet_basi > comez_basi > kapici) must not let the most
    # senior doctors skip kapici duty entirely.
    kapici_counts: dict[str, int] = {d.name: 0 for d in doctors}
    for s in result.shifts:
        for name in result.assignments.get((s, ROLE_KAPICI), []):
            kapici_counts[name] += 1

    for d in doctors:
        if d.is_senior and d.shift_count_target >= 1:
            assert kapici_counts[d.name] >= 1, f"{d.name}: hiç kapıcı olmamış"


def test_nobet_basi_scales_gradually_with_seniority():
    """nobet_basi distribution must GRADE UP with seniority (higher seniority
    -> more turns on average), not concentrate onto whichever single doctor
    ranks highest. Verifies the fair-share deviation objective replaced the
    old flat per-assignment reward correctly."""
    doctors = load_doctors(FIXTURE)
    result = build_and_solve_schedule(doctors, year=2026, month=9, seed=42, max_time_seconds=120)

    nobet_basi_counts: dict[str, int] = {d.name: 0 for d in doctors}
    for s in result.shifts:
        for name in result.assignments.get((s, ROLE_NOBET_BASI), []):
            nobet_basi_counts[name] += 1

    # No full exclusion: every eligible senior doctor got at least 1 turn.
    for d in doctors:
        if d.is_senior and d.shift_count_target >= 1:
            assert nobet_basi_counts[d.name] >= 1, f"{d.name}: hiç nöbet_başı olmamış"

    # Gradual, not concentrated: average nobet_basi count per doctor must be
    # non-decreasing as seniority increases, level by level.
    counts_by_seniority = defaultdict(list)
    for d in doctors:
        if d.is_senior and d.shift_count_target >= 1:
            counts_by_seniority[d.seniority].append(nobet_basi_counts[d.name])

    levels = sorted(counts_by_seniority)
    averages = [sum(counts_by_seniority[level]) / len(counts_by_seniority[level]) for level in levels]
    for lower, higher in zip(averages, averages[1:]):
        assert higher >= lower, (
            f"nöbet_başı ortalaması kıdemle birlikte artmıyor: {list(zip(levels, averages))}"
        )

    # Not piled onto a single doctor: nobody should hold an outsized share of
    # the month's total nobet_basi slots (empirically ~17% for this fixture;
    # 30% leaves headroom without allowing real concentration back in).
    total_slots = len(result.shifts)
    max_single_doctor_count = max(nobet_basi_counts.values())
    assert max_single_doctor_count <= 0.30 * total_slots, (
        f"Tek doktor nöbet_başı slotlarının %{100 * max_single_doctor_count / total_slots:.0f}'ini almış"
    )
