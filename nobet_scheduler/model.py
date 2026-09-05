"""CP-SAT model: build the monthly shift roster and solve it.

Modeling approach: Google OR-Tools CP-SAT, because each doctor's
shift_count_target is an exact hard constraint (an exact-target assignment
problem), not a preference to approximate.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .calendar_utils import Shift, build_month_shifts
from .doctor import Doctor
from .formulas import (
    average_apprentice_count,
    check_doctor_feasibility,
    check_feasibility,
    days_in_month,
    distribute_apprentice_counts,
    total_apprentice_slots,
)

ROLE_NOBET_BASI = "nobet_basi"
ROLE_KAPICI = "kapici"
ROLE_COMEZ_BASI = "comez_basi"
ROLE_COMEZ = "comez"

# Soft priority rule: higher seniority should preferentially fill the more
# important role (nobet_basi > kapici > comez_basi > comez). This is NOT a
# hard constraint, only an objective-function preference.
ROLE_PRIORITY_WEIGHT = {
    ROLE_NOBET_BASI: 4,
    ROLE_KAPICI: 3,
    ROLE_COMEZ_BASI: 2,
}

# comez_basi has a hard lower bound of 1 per shift but no upper bound in the
# spec ("en az 1"); this penalty keeps the solver at the practical minimum
# (exactly 1) unless something else forces more.
COMEZ_BASI_SURPLUS_PENALTY = 50

# comez is normally junior; seniors may fill it only "rarely" per the spec,
# so senior-in-comez assignments are discouraged (not forbidden).
SENIOR_IN_COMEZ_PENALTY = 10

# General spread preference: avoid scheduling the same doctor on back-to-back
# calendar days (any shift combination), so assignments spread out across the
# month instead of clustering. Soft only — the hard 2-consecutive-nights
# allowance and the forbidden weekday combos above still take precedence.
# Secondary (small) term: nudges the total consecutive-day count down as a
# tie-break once the worst-case count below is already minimized.
CONSECUTIVE_DAY_PENALTY = 5

# Primary spread term: minimizes the WORST per-doctor consecutive-day count (a
# minimax), not just the total, so the unavoidable clustering doesn't pile up
# on a couple of doctors while others stay fully spread out. Weighted above
# any single-assignment role-priority reward so it dominates.
MAX_CONSECUTIVE_DAYS_PENALTY = 30

# General balance preference: for every doctor, keep their own night-shift and
# day-shift counts close to each other (roughly 50/50), rather than skewing
# one doctor toward mostly nights and another toward mostly days. Soft only.
# Secondary (small) term: nudges the total imbalance down as a tie-break once
# the worst-case imbalance below is already minimized.
DAY_NIGHT_BALANCE_PENALTY = 2

# Primary balance term: minimizes the WORST per-doctor imbalance (a minimax),
# not just the total. Minimizing only the sum would let the solver dump the
# whole month's unavoidable day/night skew onto a couple of doctors as long as
# the total stayed low; this instead spreads it across everyone. Weighted well
# above any single-assignment role-priority reward (bounded by
# ROLE_PRIORITY_WEIGHT[nobet_basi] * max relative seniority rank — see
# _seniority_ranks) so it dominates.
MAX_IMBALANCE_PENALTY = 100

# Every senior doctor (seniority >= 1) should be nobet_basi proportionally to
# their workload: one guaranteed chief turn per every NOBET_BASI_PER_SHIFTS
# shifts in their target (hard requirement = shift_count_target // N). Below
# one full group of NOBET_BASI_PER_SHIFTS shifts, only a soft, best-effort
# reward applies (never breaks feasibility for doctors with very few shifts
# or heavy leave).
NOBET_BASI_PER_SHIFTS = 5
AT_LEAST_ONE_NOBET_BASI_BONUS = 25


def roles_for_shift(is_day_shift: bool) -> list[str]:
    if is_day_shift:
        return [ROLE_NOBET_BASI, ROLE_KAPICI, ROLE_COMEZ_BASI, ROLE_COMEZ]
    return [ROLE_NOBET_BASI, ROLE_COMEZ_BASI, ROLE_COMEZ]


def _seniority_ranks(doctors: list[Doctor]) -> dict[str, int]:
    """Map each senior doctor's name to its RELATIVE seniority rank (1..K)
    among the distinct seniority levels present in this doctor pool.

    Seniority has no fixed upper bound, so the role-priority objective must
    scale with the doctor pool's actual seniority spread, not the raw
    seniority value — a rank of 1..K keeps objective weights consistent
    whether the input uses a 0-4 scale, 0-2, 0-7, or anything else.
    """
    distinct_levels = sorted({d.seniority for d in doctors if d.is_senior})
    rank_by_level = {level: rank for rank, level in enumerate(distinct_levels, start=1)}
    return {d.name: rank_by_level[d.seniority] for d in doctors if d.is_senior}


@dataclass
class ScheduleResult:
    shifts: list[Shift]
    assignments: dict[tuple[Shift, str], list[str]]  # (shift, role) -> doctor names
    doctor_totals: dict[str, int]


def build_and_solve_schedule(
    doctors: list[Doctor],
    year: int,
    month: int,
    seed: int | None = None,
    max_time_seconds: float = 60.0,
) -> ScheduleResult:
    days = days_in_month(year, month)
    total_target = sum(d.shift_count_target for d in doctors)
    check_feasibility(total_target, days)
    check_doctor_feasibility(doctors, year, month, days)

    average = average_apprentice_count(total_target, days)
    total_comez = total_apprentice_slots(total_target, days)

    shifts = build_month_shifts(year, month, days)
    rng = random.Random(seed)
    comez_counts = distribute_apprentice_counts(total_comez, average, shifts, rng)
    seniority_rank = _seniority_ranks(doctors)

    model = cp_model.CpModel()

    role_vars: dict[tuple[Shift, str, str], cp_model.IntVar] = {}
    assigned_vars: dict[tuple[Shift, str], cp_model.IntVar] = {}

    for s in shifts:
        roles = roles_for_shift(s.is_day_shift)
        tag = f"{s.the_date.isoformat()}_{'D' if s.is_day_shift else 'N'}"

        for d in doctors:
            for r in roles:
                role_vars[(s, d.name, r)] = model.NewBoolVar(f"role_{tag}_{d.name}_{r}")

            assigned = model.NewBoolVar(f"assigned_{tag}_{d.name}")
            assigned_vars[(s, d.name)] = assigned
            model.Add(assigned == sum(role_vars[(s, d.name, r)] for r in roles))

            if s.the_date in d.leave_dates:
                model.Add(assigned == 0)

            if not d.is_senior:
                for r in (ROLE_NOBET_BASI, ROLE_KAPICI, ROLE_COMEZ_BASI):
                    if r in roles:
                        model.Add(role_vars[(s, d.name, r)] == 0)

        model.Add(sum(role_vars[(s, d.name, ROLE_NOBET_BASI)] for d in doctors) == 1)
        if s.is_day_shift:
            model.Add(sum(role_vars[(s, d.name, ROLE_KAPICI)] for d in doctors) == 1)
        model.Add(sum(role_vars[(s, d.name, ROLE_COMEZ_BASI)] for d in doctors) >= 1)
        model.Add(sum(role_vars[(s, d.name, ROLE_COMEZ)] for d in doctors) == comez_counts[s])

    for d in doctors:
        model.Add(sum(assigned_vars[(s, d.name)] for s in shifts) == d.shift_count_target)

    day_shift_by_day = {s.day_index: s for s in shifts if s.is_day_shift}
    night_shift_by_day = {s.day_index: s for s in shifts if not s.is_day_shift}

    def night_var(day_index: int, name: str):
        return assigned_vars[(night_shift_by_day[day_index], name)]

    def day_var(day_index: int, name: str):
        return assigned_vars[(day_shift_by_day[day_index], name)]

    # A doctor works at most one shift per calendar day: day OR night, never both.
    for d in doctors:
        for day_index in day_shift_by_day:
            model.Add(day_var(day_index, d.name) + night_var(day_index, d.name) <= 1)

    # No 3 consecutive nights (2 in a row is fine).
    for d in doctors:
        for day_index in range(1, days - 1):
            model.Add(
                night_var(day_index, d.name)
                + night_var(day_index + 1, d.name)
                + night_var(day_index + 2, d.name)
                <= 2
            )

    # A doctor who works a night shift can never take the next day's day shift
    # (no immediate rest-then-day-shift after a night). Hard, no exceptions.
    for d in doctors:
        for day_index in range(1, days):
            model.Add(night_var(day_index, d.name) + day_var(day_index + 1, d.name) <= 1)

    # Forbidden combos: Mon-night + Tue-day + Tue-night, and Wed-night + Thu-day + Thu-night.
    # (Already fully unreachable given the night-then-next-day-day rule above —
    # Mon-night+Tue-day alone is now forbidden — kept only as an explicit,
    # readable statement of the original spec rule.)
    for d in doctors:
        for s in shifts:
            if s.is_day_shift or s.weekday not in (0, 2):  # Monday=0, Wednesday=2
                continue
            nxt = s.day_index + 1
            if nxt in day_shift_by_day:
                model.Add(
                    night_var(s.day_index, d.name) + day_var(nxt, d.name) + night_var(nxt, d.name) <= 2
                )

    # Hard requirement: a senior doctor must be nobet_basi at least
    # (shift_count_target // NOBET_BASI_PER_SHIFTS) times during the month.
    for d in doctors:
        if not d.is_senior:
            continue
        required_min = d.shift_count_target // NOBET_BASI_PER_SHIFTS
        if required_min >= 1:
            model.Add(sum(role_vars[(s, d.name, ROLE_NOBET_BASI)] for s in shifts) >= required_min)

    objective_terms = []
    for s in shifts:
        roles = roles_for_shift(s.is_day_shift)
        for d in doctors:
            for r in roles:
                if r in ROLE_PRIORITY_WEIGHT:
                    weight = ROLE_PRIORITY_WEIGHT[r] * seniority_rank.get(d.name, 0)
                    if weight:
                        objective_terms.append(weight * role_vars[(s, d.name, r)])
                elif r == ROLE_COMEZ and d.is_senior:
                    rank = seniority_rank.get(d.name, 0)
                    objective_terms.append(-SENIOR_IN_COMEZ_PENALTY * rank * role_vars[(s, d.name, r)])
            objective_terms.append(-COMEZ_BASI_SURPLUS_PENALTY * role_vars[(s, d.name, ROLE_COMEZ_BASI)])

    # Reward each low-target senior doctor (target < NOBET_BASI_PER_SHIFTS, so
    # the hard rule above requires 0) getting at least one nobet_basi
    # assignment during the month, if achievable (soft — never forces
    # infeasibility).
    for d in doctors:
        if not d.is_senior or d.shift_count_target // NOBET_BASI_PER_SHIFTS >= 1:
            continue
        nobet_basi_total = sum(role_vars[(s, d.name, ROLE_NOBET_BASI)] for s in shifts)
        got_nobet_basi = model.NewBoolVar(f"got_nobet_basi_{d.name}")
        model.Add(got_nobet_basi <= nobet_basi_total)
        objective_terms.append(AT_LEAST_ONE_NOBET_BASI_BONUS * got_nobet_basi)

    # Penalize the same doctor working on two consecutive calendar days
    # (day and/or night shift either day), to spread assignments out. The
    # shared max_consecutive variable makes the solver minimize the worst
    # offender, not just the total across all doctors.
    max_possible_consec_pairs = max(days - 1, 0)
    max_consecutive = model.NewIntVar(0, max_possible_consec_pairs, "max_consecutive_days")
    for d in doctors:
        worked_day_vars = {}
        for day_index in range(1, days + 1):
            worked = model.NewBoolVar(f"worked_day_{day_index}_{d.name}")
            model.Add(worked >= day_var(day_index, d.name))
            model.Add(worked >= night_var(day_index, d.name))
            model.Add(worked <= day_var(day_index, d.name) + night_var(day_index, d.name))
            worked_day_vars[day_index] = worked

        consecutive_vars = []
        for day_index in range(1, days):
            consecutive = model.NewBoolVar(f"consec_days_{day_index}_{d.name}")
            model.Add(consecutive >= worked_day_vars[day_index] + worked_day_vars[day_index + 1] - 1)
            objective_terms.append(-CONSECUTIVE_DAY_PENALTY * consecutive)
            consecutive_vars.append(consecutive)
        model.Add(max_consecutive >= sum(consecutive_vars))
    objective_terms.append(-MAX_CONSECUTIVE_DAYS_PENALTY * max_consecutive)

    # Penalize each doctor's night-count/day-count imbalance, so day and night
    # assignments come out roughly even per doctor instead of some doctors
    # getting mostly nights and others mostly days. The shared max_imbalance
    # variable makes the solver minimize the worst offender, not just the sum.
    max_possible_target = max((d.shift_count_target for d in doctors), default=0)
    max_imbalance = model.NewIntVar(0, max_possible_target, "max_day_night_imbalance")
    for d in doctors:
        day_total = sum(day_var(day_index, d.name) for day_index in day_shift_by_day)
        night_total = sum(night_var(day_index, d.name) for day_index in night_shift_by_day)
        imbalance = model.NewIntVar(0, d.shift_count_target, f"day_night_imbalance_{d.name}")
        model.Add(imbalance >= day_total - night_total)
        model.Add(imbalance >= night_total - day_total)
        model.Add(max_imbalance >= imbalance)
        objective_terms.append(-DAY_NIGHT_BALANCE_PENALTY * imbalance)
    objective_terms.append(-MAX_IMBALANCE_PENALTY * max_imbalance)

    model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max_time_seconds
    solver.parameters.num_search_workers = 8
    if seed is not None:
        solver.parameters.random_seed = seed
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(
            "No feasible schedule found. Check doctor pool size, seniority mix, "
            "leave dates and shift-count targets against the constraints."
        )

    assignments: dict[tuple[Shift, str], list[str]] = {}
    doctor_totals: dict[str, int] = {d.name: 0 for d in doctors}

    for s in shifts:
        for r in roles_for_shift(s.is_day_shift):
            names = sorted(d.name for d in doctors if solver.Value(role_vars[(s, d.name, r)]))
            assignments[(s, r)] = names
        for d in doctors:
            if solver.Value(assigned_vars[(s, d.name)]):
                doctor_totals[d.name] += 1

    return ScheduleResult(shifts=shifts, assignments=assignments, doctor_totals=doctor_totals)
