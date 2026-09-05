"""Calendar helpers: building the list of shifts for a given month."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Shift:
    day_index: int  # 1-based day of month
    the_date: date
    is_day_shift: bool  # True = gunduz (08:00-18:00), False = gece (18:00-08:00)

    @property
    def weekday(self) -> int:
        """Monday=0 .. Sunday=6, per the shift's calendar date."""
        return self.the_date.weekday()


def build_month_shifts(year: int, month: int, days: int) -> list[Shift]:
    """Build the ordered list of day/night shifts for every day of the month."""
    shifts = []
    for day_index in range(1, days + 1):
        the_date = date(year, month, day_index)
        shifts.append(Shift(day_index, the_date, True))
        shifts.append(Shift(day_index, the_date, False))
    return shifts
