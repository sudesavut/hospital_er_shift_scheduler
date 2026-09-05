import random

from nobet_scheduler.calendar_utils import build_month_shifts
from nobet_scheduler.formulas import distribute_apprentice_counts


def test_distribution_respects_total_and_prioritizes_night_shifts():
    shifts = build_month_shifts(2026, 9, 30)
    rng = random.Random(42)
    counts = distribute_apprentice_counts(144, 2.4, shifts, rng)

    assert sum(counts.values()) == 144
    day_ceil = sum(1 for s in shifts if s.is_day_shift and counts[s] == 3)
    night_ceil = sum(1 for s in shifts if not s.is_day_shift and counts[s] == 3)
    assert night_ceil == 24
    assert day_ceil == 0


def test_distribution_with_integer_average_is_uniform():
    shifts = build_month_shifts(2026, 9, 30)
    rng = random.Random(1)
    counts = distribute_apprentice_counts(120, 2.0, shifts, rng)
    assert all(v == 2 for v in counts.values())
