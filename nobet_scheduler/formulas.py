"""Feasibility pre-check and apprentice-count (comez) formulas from the spec.

Generalized to a single day-count-agnostic formula (equivalent to the spec's
original separate 30-day/31-day cases, algebraically simplified):
- Feasibility: toplam_nöbet_sayısı >= 5 * gün_sayısı
- Average apprentice count per shift:
    ortalama_çömez = (toplam_nöbet_sayısı - 5*gün_sayısı) / (2*gün_sayısı)
- Apprentice-count floor/ceil distribution across shifts, with night shifts
  prioritized for the ceiling value.
"""

from __future__ import annotations

import calendar
import math
import random

from .calendar_utils import Shift
from .doctor import Doctor

# Per calendar day, the mandatory senior-only roles: 2x nobet_basi + 1x kapici
# + 2x comez_basi (one of each pair per day shift, one per night shift minus kapici).
FIXED_ROLES_PER_DAY = 5


class InfeasibleTotalShiftsError(Exception):
    """Raised when the sum of doctor shift-count targets cannot cover the month."""


class InfeasibleDoctorTargetError(Exception):
    """Raised when a doctor's shift_count_target exceeds their available
    (non-leave) days this month, since a doctor can work at most one shift
    (day OR night) per calendar day."""


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def check_feasibility(total_shift_count_target: int, days: int) -> None:
    """Raise InfeasibleTotalShiftsError unless Toplam(nöbet_sayısı) >= days*5."""
    minimum_required = days * FIXED_ROLES_PER_DAY
    if total_shift_count_target < minimum_required:
        raise InfeasibleTotalShiftsError(
            f"Total shift-count target ({total_shift_count_target}) is below the minimum "
            f"required to cover the mandatory senior-only roles for {days} days "
            f"({minimum_required} = {days} x {FIXED_ROLES_PER_DAY}). "
            "Increase doctors' shift_count_target values or add more doctors."
        )


def check_doctor_feasibility(doctors: list[Doctor], year: int, month: int, days: int) -> None:
    """Raise InfeasibleDoctorTargetError if any doctor's target exceeds their
    available (non-leave) days — a doctor works at most one shift per day."""
    problems = []
    for d in doctors:
        leave_in_month = sum(1 for dt in d.leave_dates if dt.year == year and dt.month == month)
        available_days = days - leave_in_month
        if d.shift_count_target > available_days:
            problems.append((d.name, d.shift_count_target, available_days))

    if problems:
        details = "; ".join(
            f"{name} (target={target}, available_days={available})"
            for name, target, available in problems
        )
        raise InfeasibleDoctorTargetError(
            "The following doctors have a shift_count_target that exceeds their "
            "available (non-leave) days this month — a doctor can work at most "
            f"one shift per calendar day: {details}. "
            "Lower their target or reduce their leave days."
        )


def average_apprentice_count(total_shift_count_target: int, days: int) -> float:
    """toplam_çömez_sayısı_ortalaması: (toplam_nöbet_sayısı - 5*gün) / (2*gün)."""
    return (total_shift_count_target - FIXED_ROLES_PER_DAY * days) / (2 * days)


def total_apprentice_slots(total_shift_count_target: int, days: int) -> int:
    """Toplam_çömez_sayısı: total integer count of apprentice seats across the month."""
    return total_shift_count_target - days * FIXED_ROLES_PER_DAY


def distribute_apprentice_counts(
    total_apprentice_slots_count: int,
    average: float,
    shifts: list[Shift],
    rng: random.Random,
) -> dict[Shift, int]:
    """Assign an integer apprentice (comez) headcount to each shift.

    When the average is fractional, most shifts get floor(average) and the
    remainder get ceil(average); night shifts are prioritized to receive the
    ceiling value, with random tie-breaking among same-type shifts.
    """
    n_shifts = len(shifts)
    floor_val = math.floor(average)
    ceil_val = math.ceil(average)

    counts = {s: floor_val for s in shifts}
    if floor_val == ceil_val:
        return counts  # integer average: every shift gets exactly that count

    n_ceil = total_apprentice_slots_count - floor_val * n_shifts
    if n_ceil <= 0:
        return counts

    day_shifts = [s for s in shifts if s.is_day_shift]
    night_shifts = [s for s in shifts if not s.is_day_shift]
    rng.shuffle(day_shifts)
    rng.shuffle(night_shifts)

    chosen = night_shifts[:n_ceil]
    if n_ceil > len(night_shifts):
        chosen = night_shifts + day_shifts[: n_ceil - len(night_shifts)]

    for s in chosen:
        counts[s] = ceil_val
    return counts
