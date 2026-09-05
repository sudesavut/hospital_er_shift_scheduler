"""Command-line entry point: monthly emergency-department shift scheduler."""

from __future__ import annotations

import argparse
import sys

from .doctor import load_doctors
from .export import export_schedule
from .formulas import InfeasibleDoctorTargetError, InfeasibleTotalShiftsError
from .model import build_and_solve_schedule


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hospital emergency department monthly shift scheduler")
    parser.add_argument("--doctors", required=True, help="Path to doctor roster (.csv or .json)")
    parser.add_argument("--month", type=int, default=None, help="Month number (1-12); prompted if omitted")
    parser.add_argument("--year", type=int, default=None, help="Year; prompted if omitted")
    parser.add_argument("--output", default="nobet_listesi.xlsx", help="Output .xlsx path")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for tie-breaking (reproducibility)")
    parser.add_argument("--time-limit", type=float, default=60.0, help="CP-SAT solver time limit in seconds")
    return parser.parse_args(argv)


def prompt_int(label: str) -> int:
    while True:
        raw = input(f"{label}: ").strip()
        try:
            return int(raw)
        except ValueError:
            print("Please enter a valid integer.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    month = args.month if args.month is not None else prompt_int("Month (1-12)")
    year = args.year if args.year is not None else prompt_int("Year")

    doctors = load_doctors(args.doctors)

    try:
        result = build_and_solve_schedule(
            doctors, year, month, seed=args.seed, max_time_seconds=args.time_limit
        )
    except (InfeasibleTotalShiftsError, InfeasibleDoctorTargetError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    export_schedule(result, doctors, args.output)
    print(f"Schedule written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
