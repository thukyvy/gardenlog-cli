"""Command-line interface for GardenLog (argparse-based)."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from . import store


def _err(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _parse_day(value: str | None, today: date) -> date:
    return store.parse_date(value) if value else today


def cmd_add(args: argparse.Namespace, today: date) -> int:
    if args.interval < 1:
        return _err("watering interval must be at least 1 day")
    data = store.load_data()
    if store.find_plant(data, args.name):
        return _err(f"a plant named '{args.name}' is already tracked")
    planted = _parse_day(args.planted, today)
    plant = store.make_plant(args.name, args.species, planted, args.interval)
    data["plants"].append(plant)
    store.save_data(data)
    species = f" ({plant['species']})" if plant["species"] else ""
    print(
        f"Added {plant['name']}{species}: planted {plant['planted']}, "
        f"water every {plant['interval_days']} day(s), "
        f"first due {store.next_due(plant).isoformat()}."
    )
    return 0


def cmd_list(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    if not data["plants"]:
        print("No plants tracked yet. Add one with: gardenlog add <name>")
        return 0
    print(f"{'Name':<20} {'Species':<24} {'Last watered':<13} {'Next due':<11} Status")
    print("-" * 78)
    for plant in sorted(data["plants"], key=lambda p: p["name"].lower()):
        overdue = store.days_overdue(plant, today)
        if overdue > 0:
            status = f"OVERDUE by {overdue}d"
        elif overdue == 0:
            status = "due today"
        else:
            status = f"in {-overdue}d"
        print(
            f"{plant['name']:<20} {plant['species'] or '-':<24} "
            f"{store.last_watered(plant).isoformat():<13} "
            f"{store.next_due(plant).isoformat():<11} {status}"
        )
    return 0


def cmd_due(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    due_plants = [p for p in data["plants"] if store.is_due(p, today)]
    if not due_plants:
        print(f"Nothing due as of {today.isoformat()}. All plants are watered.")
        return 0
    due_plants.sort(key=lambda p: store.days_overdue(p, today), reverse=True)
    print(f"Plants needing water as of {today.isoformat()}:")
    for plant in due_plants:
        overdue = store.days_overdue(plant, today)
        when = "due today" if overdue == 0 else f"{overdue} day(s) overdue"
        print(
            f"- {plant['name']}: last watered {store.last_watered(plant).isoformat()}, "
            f"was due {store.next_due(plant).isoformat()} ({when})"
        )
    return 0


def cmd_water(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    plant = store.find_plant(data, args.name)
    if plant is None:
        return _err(f"no plant named '{args.name}' is tracked")
    day = _parse_day(args.date, today)
    if day.isoformat() not in plant["waterings"]:
        plant["waterings"].append(day.isoformat())
        plant["waterings"].sort()
    store.save_data(data)
    print(
        f"Watered {plant['name']} on {day.isoformat()}. "
        f"Next due {store.next_due(plant).isoformat()}."
    )
    return 0


def cmd_remove(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    plant = store.find_plant(data, args.name)
    if plant is None:
        return _err(f"no plant named '{args.name}' is tracked")
    data["plants"].remove(plant)
    store.save_data(data)
    print(f"Removed {plant['name']} from tracking.")
    return 0


def cmd_stats(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    plants = data["plants"]
    total_waterings = sum(len(p["waterings"]) for p in plants)
    print(f"Plants tracked: {len(plants)}")
    print(f"Waterings logged: {total_waterings}")
    overdue = [(store.days_overdue(p, today), p) for p in plants]
    overdue = [(days, p) for days, p in overdue if days > 0]
    if overdue:
        days, plant = max(overdue, key=lambda item: item[0])
        print(f"Most overdue: {plant['name']} ({days} day(s) past due)")
    else:
        print("Most overdue: none — everything is on schedule")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gardenlog",
        description="Track your plants and know when each one needs water.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p_add = sub.add_parser("add", help="register a new plant")
    p_add.add_argument("name", help="unique name for the plant")
    p_add.add_argument("--species", default="", help="species / variety (optional)")
    p_add.add_argument(
        "--planted",
        metavar="YYYY-MM-DD",
        help="planting date (default: today)",
    )
    p_add.add_argument(
        "--interval",
        type=int,
        default=7,
        metavar="DAYS",
        help="watering interval in days (default: 7)",
    )
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="list all tracked plants")
    p_list.set_defaults(func=cmd_list)

    p_due = sub.add_parser("due", help="show plants due or overdue for watering")
    p_due.set_defaults(func=cmd_due)

    p_water = sub.add_parser("water", help="record a watering for a plant")
    p_water.add_argument("name", help="name of the plant you watered")
    p_water.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="watering date (default: today)",
    )
    p_water.set_defaults(func=cmd_water)

    p_remove = sub.add_parser("remove", help="stop tracking a plant")
    p_remove.add_argument("name", help="name of the plant to remove")
    p_remove.set_defaults(func=cmd_remove)

    p_stats = sub.add_parser("stats", help="summary counts and the most overdue plant")
    p_stats.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None, today: date | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        return args.func(args, today or date.today())
    except ValueError as exc:  # e.g. malformed date input
        return _err(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
