"""JSON storage layer and plant schedule logic for GardenLog.

Data lives in a single JSON document:

    {
      "plants": [
        {
          "name": "Monstera",
          "species": "Monstera deliciosa",
          "planted": "2026-10-01",
          "interval_days": 7,
          "waterings": ["2026-10-03", "2026-10-10"]
        }
      ]
    }

All dates are ISO calendar dates (YYYY-MM-DD). A plant that has never been
watered is treated as last watered on the day it was planted, so its first
due date is ``planted + interval_days``.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from pathlib import Path

DEFAULT_DATA_FILE = "~/.gardenlog.json"
ENV_DATA_FILE = "GARDENLOG_DATA"


def data_path() -> Path:
    """Resolve the data file: $GARDENLOG_DATA, else ~/.gardenlog.json."""
    override = os.environ.get(ENV_DATA_FILE)
    if override:
        return Path(override).expanduser()
    return Path(DEFAULT_DATA_FILE).expanduser()


def empty_data() -> dict:
    return {"plants": []}


def load_data(path: Path | None = None) -> dict:
    """Load the data document, returning an empty one if it doesn't exist."""
    path = path or data_path()
    if not path.exists():
        return empty_data()
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    data.setdefault("plants", [])
    return data


def save_data(data: dict, path: Path | None = None) -> None:
    path = path or data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def find_plant(data: dict, name: str) -> dict | None:
    """Case-insensitive lookup by plant name."""
    for plant in data["plants"]:
        if plant["name"].lower() == name.lower():
            return plant
    return None


def make_plant(name: str, species: str | None, planted: date, interval_days: int) -> dict:
    return {
        "name": name,
        "species": species or "",
        "planted": planted.isoformat(),
        "interval_days": interval_days,
        "waterings": [],
    }


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def last_watered(plant: dict) -> date:
    """Most recent watering date, falling back to the planted date."""
    if plant["waterings"]:
        return max(parse_date(day) for day in plant["waterings"])
    return parse_date(plant["planted"])


def next_due(plant: dict) -> date:
    """The date the plant next needs water."""
    return last_watered(plant) + timedelta(days=int(plant["interval_days"]))


def days_overdue(plant: dict, today: date) -> int:
    """Days past the due date as of `today` (negative if not yet due)."""
    return (today - next_due(plant)).days


def is_due(plant: dict, today: date) -> bool:
    return days_overdue(plant, today) >= 0
