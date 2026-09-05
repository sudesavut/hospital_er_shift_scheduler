import pytest

from nobet_scheduler.formulas import (
    InfeasibleTotalShiftsError,
    average_apprentice_count,
    check_feasibility,
    days_in_month,
    total_apprentice_slots,
)


def test_days_in_month_30_and_31():
    assert days_in_month(2026, 9) == 30
    assert days_in_month(2026, 10) == 31


def test_days_in_month_february_non_leap_year():
    assert days_in_month(2026, 2) == 28


def test_days_in_month_february_leap_year():
    assert days_in_month(2028, 2) == 29


def test_february_runs_through_the_same_general_formula():
    # Sanity check: February is no longer a special case — the general
    # formula must behave consistently for 28- and 29-day months too.
    days = days_in_month(2026, 2)
    total = 5 * days + 20  # comfortably above the feasibility minimum
    check_feasibility(total, days)  # should not raise
    assert average_apprentice_count(total, days) == pytest.approx(20 / (2 * days))
    assert total_apprentice_slots(total, days) == 20

    days_leap = days_in_month(2028, 2)
    total_leap = 5 * days_leap + 20
    check_feasibility(total_leap, days_leap)
    assert average_apprentice_count(total_leap, days_leap) == pytest.approx(20 / (2 * days_leap))
    assert total_apprentice_slots(total_leap, days_leap) == 20


def test_check_feasibility_raises_when_below_minimum():
    with pytest.raises(InfeasibleTotalShiftsError):
        check_feasibility(100, 30)


def test_check_feasibility_ok_at_minimum():
    check_feasibility(150, 30)
    check_feasibility(155, 31)


def test_average_apprentice_count_matches_scale_example():
    assert average_apprentice_count(294, 30) == pytest.approx(2.4)


def test_total_apprentice_slots_matches_scale_example():
    assert total_apprentice_slots(294, 30) == 144
