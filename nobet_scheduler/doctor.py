"""Doctor roster data model and loaders (CSV / JSON)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

MIN_SENIORITY = 0


@dataclass
class Doctor:
    name: str
    seniority: int  # 0 = junior (kidemsiz), >=1 = senior (kidemli); no fixed upper bound
    shift_count_target: int
    leave_dates: set[date] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.seniority < MIN_SENIORITY:
            raise ValueError(
                f"Doctor '{self.name}' has invalid seniority {self.seniority}; "
                f"must be a non-negative integer (>= {MIN_SENIORITY})."
            )
        if self.shift_count_target < 0:
            raise ValueError(f"Doctor '{self.name}' has negative shift_count_target.")

    @property
    def is_senior(self) -> bool:
        return self.seniority >= 1


def load_doctors(path: str | Path) -> list[Doctor]:
    """Load the doctor roster from a .csv or .json file, chosen by extension."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        return _load_doctors_json(path)
    if path.suffix.lower() == ".csv":
        return _load_doctors_csv(path)
    raise ValueError(f"Unsupported doctor roster file format: {path.suffix}")


def _parse_date(value: str) -> date:
    return date.fromisoformat(value.strip())


def _load_doctors_json(path: Path) -> list[Doctor]:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    doctors = []
    for entry in raw:
        leave_dates = {_parse_date(d) for d in entry.get("leave_dates", [])}
        doctors.append(
            Doctor(
                name=entry["name"],
                seniority=int(entry["seniority"]),
                shift_count_target=int(entry["shift_count_target"]),
                leave_dates=leave_dates,
            )
        )
    return doctors


def _load_doctors_csv(path: Path) -> list[Doctor]:
    doctors = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leave_raw = (row.get("leave_dates") or "").strip()
            leave_dates = (
                {_parse_date(d) for d in leave_raw.split(";") if d.strip()} if leave_raw else set()
            )
            doctors.append(
                Doctor(
                    name=row["name"],
                    seniority=int(row["seniority"]),
                    shift_count_target=int(row["shift_count_target"]),
                    leave_dates=leave_dates,
                )
            )
    return doctors
