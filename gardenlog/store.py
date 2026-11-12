"""JSON storage layer and plant schedule logic for GardenLog.

Data lives in a single JSON document:

    {
      "plants": [
        {
          "name": "Monstera",
          "species": "Monstera deliciosa",
          "planted": "2026-10-01",
          "interval_days": 7,
          "waterings": ["2026-10-03", "2026-10-10"],
          "note": "moved to the balcony",
          "feed_interval_days": 30,
          "feedings": [],
          "zone": "balcony",
          "profile": ""
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


def make_plant(
    name: str,
    species: str | None,
    planted: date,
    interval_days: int,
    feed_interval_days: int | None = None,
    zone: str = "",
    profile: str = "",
) -> dict:
    return {
        "name": name,
        "species": species or "",
        "planted": planted.isoformat(),
        "interval_days": interval_days,
        "waterings": [],
        "note": "",
        "feed_interval_days": feed_interval_days,
        "feedings": [],
        "zone": zone or "",
        "profile": profile or "",
    }


def plant_zone(plant: dict) -> str:
    """The plant's zone ('' when unset or from an older data file)."""
    return plant.get("zone", "") or ""


# Care profiles: reusable starting intervals for common plant kinds.
# These are defaults only — every value can be overridden per plant.
PROFILES: dict[str, dict[str, int]] = {
    "succulent": {"interval_days": 14, "feed_interval_days": 60},
    "fern": {"interval_days": 3, "feed_interval_days": 30},
    "herb": {"interval_days": 2, "feed_interval_days": 14},
}


def profile_of(plant: dict) -> str:
    """The care profile the plant was started from ('' when none)."""
    return plant.get("profile", "") or ""


def plant_note(plant: dict) -> str:
    """The plant's free-text note ('' when unset or from an older data file)."""
    return plant.get("note", "") or ""


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


def feed_interval(plant: dict) -> int | None:
    """Fertiliser interval in days, or None when feeding is not tracked."""
    value = plant.get("feed_interval_days")
    return int(value) if value else None


def feedings_of(plant: dict) -> list:
    """Feeding dates recorded for the plant ([] for older data files)."""
    return plant.get("feedings", [])


def last_fed(plant: dict) -> date:
    """Most recent feeding date, falling back to the planted date."""
    feedings = feedings_of(plant)
    if feedings:
        return max(parse_date(day) for day in feedings)
    return parse_date(plant["planted"])


def next_feed_due(plant: dict) -> date | None:
    """The date the plant next needs fertiliser (None when not tracked)."""
    interval = feed_interval(plant)
    if interval is None:
        return None
    return last_fed(plant) + timedelta(days=interval)


def feed_days_overdue(plant: dict, today: date) -> int | None:
    """Days past the feed due date (None when feeding is not tracked)."""
    due = next_feed_due(plant)
    if due is None:
        return None
    return (today - due).days


def is_feed_due(plant: dict, today: date) -> bool:
    overdue = feed_days_overdue(plant, today)
    return overdue is not None and overdue >= 0


def load_forecast(path: Path) -> dict:
    """Load a rain forecast JSON file keyed by ISO date:

        {"2026-11-13": {"rain": true}, "2026-11-14": {"rain_chance": 80}}

    GardenLog never fetches weather itself — the file is supplied by the
    user (or their own script), keeping the tool offline by default.
    """
    with path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        raise ValueError("forecast file must be a JSON object keyed by date")
    return raw


def rain_expected(forecast: dict, day: date) -> bool:
    """True when the forecast marks `day` rainy ("rain" or >= 50% chance)."""
    entry = forecast.get(day.isoformat())
    if not isinstance(entry, dict):
        return False
    if entry.get("rain"):
        return True
    chance = entry.get("rain_chance")
    return chance is not None and int(chance) >= 50


def next_dry_day(forecast: dict, start: date, max_days: int = 7) -> date | None:
    """First day after `start` with no rain expected (None if all rainy)."""
    for offset in range(1, max_days + 1):
        candidate = start + timedelta(days=offset)
        if not rain_expected(forecast, candidate):
            return candidate
    return None
