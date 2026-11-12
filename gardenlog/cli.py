"""Command-line interface for GardenLog (argparse-based)."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from datetime import date
from pathlib import Path

from . import store


def _err(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _parse_day(value: str | None, today: date) -> date:
    return store.parse_date(value) if value else today


def cmd_add(args: argparse.Namespace, today: date) -> int:
    profile = None
    profile_name = ""
    if args.profile:
        profile_name = args.profile.lower()
        profile = store.PROFILES.get(profile_name)
        if profile is None:
            available = ", ".join(sorted(store.PROFILES))
            return _err(
                f"unknown care profile '{args.profile}' — available: {available}"
            )
    interval = args.interval
    if interval is None:
        interval = profile["interval_days"] if profile else 7
    feed_interval = args.feed_interval
    if feed_interval is None and profile:
        feed_interval = profile["feed_interval_days"]
    if interval < 1:
        return _err("watering interval must be at least 1 day")
    if feed_interval is not None and feed_interval < 1:
        return _err("fertiliser interval must be at least 1 day")
    data = store.load_data()
    if store.find_plant(data, args.name):
        return _err(f"a plant named '{args.name}' is already tracked")
    planted = _parse_day(args.planted, today)
    plant = store.make_plant(
        args.name,
        args.species,
        planted,
        interval,
        feed_interval,
        args.zone.strip(),
        profile_name,
    )
    data["plants"].append(plant)
    store.save_data(data)
    species = f" ({plant['species']})" if plant["species"] else ""
    message = (
        f"Added {plant['name']}{species}: planted {plant['planted']}, "
        f"water every {plant['interval_days']} day(s), "
        f"first due {store.next_due(plant).isoformat()}."
    )
    if store.feed_interval(plant) is not None:
        message += (
            f" Feed every {store.feed_interval(plant)} day(s), "
            f"first feed due {store.next_feed_due(plant).isoformat()}."
        )
    if store.plant_zone(plant):
        message += f" Zone: {store.plant_zone(plant)}."
    if store.profile_of(plant):
        message += f" Care profile: {store.profile_of(plant)}."
    print(message)
    return 0


def cmd_profiles(args: argparse.Namespace, today: date) -> int:
    print("Available care profiles (starting defaults, all overridable):")
    for name in sorted(store.PROFILES):
        profile = store.PROFILES[name]
        print(
            f"- {name}: water every {profile['interval_days']} day(s), "
            f"feed every {profile['feed_interval_days']} day(s)"
        )
    return 0


def _filter_zone(plants: list, zone: str | None) -> list:
    if zone is None:
        return plants
    return [p for p in plants if store.plant_zone(p).lower() == zone.lower()]


def cmd_list(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    if not data["plants"]:
        print("No plants tracked yet. Add one with: gardenlog add <name>")
        return 0
    plants = _filter_zone(data["plants"], args.zone)
    if not plants:
        print(f"No plants in zone '{args.zone}'.")
        return 0
    print(f"{'Name':<20} {'Species':<24} {'Last watered':<13} {'Next due':<11} Status")
    print("-" * 78)
    for plant in sorted(plants, key=lambda p: p["name"].lower()):
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
        zone = store.plant_zone(plant)
        if zone:
            print(f"    zone: {zone}")
        note = store.plant_note(plant)
        if note:
            print(f"    note: {note}")
    return 0


def cmd_due(args: argparse.Namespace, today: date) -> int:
    forecast = None
    if args.forecast:
        try:
            forecast = store.load_forecast(Path(args.forecast).expanduser())
        except (OSError, ValueError) as exc:
            return _err(f"could not read forecast file '{args.forecast}': {exc}")
    data = store.load_data()
    plants = _filter_zone(data["plants"], args.zone)
    due_plants = [p for p in plants if store.is_due(p, today)]
    feed_plants = [p for p in plants if store.is_feed_due(p, today)]
    if not due_plants and not feed_plants:
        if args.zone is not None:
            print(f"Nothing due as of {today.isoformat()} in zone '{args.zone}'.")
        else:
            print(f"Nothing due as of {today.isoformat()}. All plants are on schedule.")
        return 0
    if due_plants:
        due_plants.sort(key=lambda p: store.days_overdue(p, today), reverse=True)
        print(f"Plants needing water as of {today.isoformat()}:")
        for plant in due_plants:
            overdue = store.days_overdue(plant, today)
            when = "due today" if overdue == 0 else f"{overdue} day(s) overdue"
            line = (
                f"- {plant['name']}: last watered {store.last_watered(plant).isoformat()}, "
                f"was due {store.next_due(plant).isoformat()} ({when})"
            )
            if forecast is not None and store.rain_expected(forecast, today):
                dry = store.next_dry_day(forecast, today)
                if dry is not None:
                    line += (
                        f" (rain expected today — consider delaying "
                        f"to {dry.isoformat()} if outdoors)"
                    )
                else:
                    line += " (rain expected today — no dry day in the next 7 days)"
            print(line)
    if feed_plants:
        feed_plants.sort(
            key=lambda p: store.feed_days_overdue(p, today), reverse=True
        )
        print(f"Plants needing fertiliser as of {today.isoformat()}:")
        for plant in feed_plants:
            overdue = store.feed_days_overdue(plant, today)
            when = "due today" if overdue == 0 else f"{overdue} day(s) overdue"
            print(
                f"- {plant['name']}: last fed {store.last_fed(plant).isoformat()}, "
                f"was due {store.next_feed_due(plant).isoformat()} ({when})"
            )
    return 0


def cmd_feed(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    plant = store.find_plant(data, args.name)
    if plant is None:
        return _err(f"no plant named '{args.name}' is tracked")
    if store.feed_interval(plant) is None:
        return _err(
            f"no fertiliser schedule for '{plant['name']}' — set one with: "
            f"gardenlog schedule-feed {plant['name']} --every 30"
        )
    day = _parse_day(args.date, today)
    feedings = store.feedings_of(plant)
    if day.isoformat() not in feedings:
        feedings.append(day.isoformat())
        feedings.sort()
    plant["feedings"] = feedings
    store.save_data(data)
    print(
        f"Fed {plant['name']} on {day.isoformat()}. "
        f"Next feed due {store.next_feed_due(plant).isoformat()}."
    )
    return 0


def cmd_schedule_feed(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    plant = store.find_plant(data, args.name)
    if plant is None:
        return _err(f"no plant named '{args.name}' is tracked")
    if args.off:
        plant["feed_interval_days"] = None
        store.save_data(data)
        print(f"Fertiliser schedule for {plant['name']} turned off.")
        return 0
    if args.every is None:
        interval = store.feed_interval(plant)
        if interval is None:
            print(f"No fertiliser schedule for {plant['name']}.")
        else:
            print(
                f"{plant['name']}: feed every {interval} day(s), "
                f"next feed due {store.next_feed_due(plant).isoformat()}."
            )
        return 0
    if args.every < 1:
        return _err("fertiliser interval must be at least 1 day")
    plant["feed_interval_days"] = args.every
    plant.setdefault("feedings", [])
    store.save_data(data)
    print(
        f"Fertiliser schedule for {plant['name']}: every {args.every} day(s), "
        f"next feed due {store.next_feed_due(plant).isoformat()}."
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


def cmd_note(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    plant = store.find_plant(data, args.name)
    if plant is None:
        return _err(f"no plant named '{args.name}' is tracked")
    if args.clear:
        plant["note"] = ""
        store.save_data(data)
        print(f"Cleared the note for {plant['name']}.")
        return 0
    if args.text is None:
        note = store.plant_note(plant)
        if note:
            print(f"{plant['name']} note: {note}")
        else:
            print(
                f"{plant['name']} has no note. "
                f'Add one with: gardenlog note {plant["name"]} "..."'
            )
        return 0
    text = args.text.strip()
    if not text:
        return _err("note text is empty — use --clear to remove a note")
    plant["note"] = text
    store.save_data(data)
    print(f"Note saved for {plant['name']}: {text}")
    return 0


EXPORT_FIELDS = [
    "name",
    "species",
    "zone",
    "profile",
    "planted",
    "interval_days",
    "note",
    "waterings_count",
    "last_watered",
    "next_due",
    "waterings",
    "feed_interval_days",
    "feedings_count",
    "last_fed",
    "next_feed_due",
    "feedings",
]


def _export_rows(data: dict) -> list[dict]:
    rows = []
    for plant in sorted(data["plants"], key=lambda p: p["name"].lower()):
        feedings = sorted(store.feedings_of(plant))
        interval = store.feed_interval(plant)
        next_feed = store.next_feed_due(plant)
        rows.append(
            {
                "name": plant["name"],
                "species": plant["species"],
                "zone": store.plant_zone(plant),
                "profile": store.profile_of(plant),
                "planted": plant["planted"],
                "interval_days": plant["interval_days"],
                "note": store.plant_note(plant),
                "waterings_count": len(plant["waterings"]),
                "last_watered": store.last_watered(plant).isoformat(),
                "next_due": store.next_due(plant).isoformat(),
                "waterings": ";".join(sorted(plant["waterings"])),
                "feed_interval_days": interval if interval is not None else "",
                "feedings_count": len(feedings),
                "last_fed": (
                    store.last_fed(plant).isoformat()
                    if (feedings or interval is not None)
                    else ""
                ),
                "next_feed_due": next_feed.isoformat() if next_feed else "",
                "feedings": ";".join(feedings),
            }
        )
    return rows


def cmd_export(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    rows = _export_rows(data)
    if args.output:
        path = Path(args.output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=EXPORT_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Exported {len(rows)} plant(s) to {path}.")
        return 0
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    sys.stdout.write(buffer.getvalue())
    return 0


def cmd_zone(args: argparse.Namespace, today: date) -> int:
    data = store.load_data()
    plant = store.find_plant(data, args.name)
    if plant is None:
        return _err(f"no plant named '{args.name}' is tracked")
    if args.clear:
        plant["zone"] = ""
        store.save_data(data)
        print(f"Cleared the zone for {plant['name']}.")
        return 0
    if args.text is None:
        zone = store.plant_zone(plant)
        if zone:
            print(f"{plant['name']} zone: {zone}")
        else:
            print(
                f"{plant['name']} has no zone. "
                f'Set one with: gardenlog zone {plant["name"]} "balcony"'
            )
        return 0
    text = args.text.strip()
    if not text:
        return _err("zone name is empty — use --clear to remove a zone")
    plant["zone"] = text
    store.save_data(data)
    print(f"Zone for {plant['name']} set to: {text}")
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
    total_feedings = sum(len(store.feedings_of(p)) for p in plants)
    print(f"Plants tracked: {len(plants)}")
    print(f"Waterings logged: {total_waterings}")
    print(f"Feedings logged: {total_feedings}")
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
        default=None,
        metavar="DAYS",
        help="watering interval in days (default: 7, or the care profile's)",
    )
    p_add.add_argument(
        "--profile",
        default="",
        metavar="NAME",
        help="care profile to start from (see: gardenlog profiles)",
    )
    p_add.add_argument(
        "--feed-interval",
        type=int,
        default=None,
        metavar="DAYS",
        help="fertiliser interval in days (default: feeding not tracked)",
    )
    p_add.add_argument(
        "--zone",
        default="",
        metavar="ZONE",
        help="location group, e.g. balcony or kitchen (optional)",
    )
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="list all tracked plants")
    p_list.add_argument(
        "--zone",
        default=None,
        metavar="ZONE",
        help="only show plants in this zone",
    )
    p_list.set_defaults(func=cmd_list)

    p_due = sub.add_parser("due", help="show plants due or overdue for watering")
    p_due.add_argument(
        "--zone",
        default=None,
        metavar="ZONE",
        help="only show plants in this zone",
    )
    p_due.add_argument(
        "--forecast",
        default=None,
        metavar="PATH",
        help="JSON rain-forecast file; due waterings expecting rain are flagged",
    )
    p_due.set_defaults(func=cmd_due)

    p_feed = sub.add_parser("feed", help="record a feeding for a plant")
    p_feed.add_argument("name", help="name of the plant you fed")
    p_feed.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="feeding date (default: today)",
    )
    p_feed.set_defaults(func=cmd_feed)

    p_schedule_feed = sub.add_parser(
        "schedule-feed", help="view, set or disable a plant's fertiliser schedule"
    )
    p_schedule_feed.add_argument("name", help="name of the plant")
    p_schedule_feed.add_argument(
        "--every",
        type=int,
        default=None,
        metavar="DAYS",
        help="feed every DAYS days",
    )
    p_schedule_feed.add_argument(
        "--off",
        action="store_true",
        help="stop tracking feeding for this plant",
    )
    p_schedule_feed.set_defaults(func=cmd_schedule_feed)

    p_water = sub.add_parser("water", help="record a watering for a plant")
    p_water.add_argument("name", help="name of the plant you watered")
    p_water.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="watering date (default: today)",
    )
    p_water.set_defaults(func=cmd_water)

    p_note = sub.add_parser("note", help="view or set a free-text note on a plant")
    p_note.add_argument("name", help="name of the plant")
    p_note.add_argument(
        "text",
        nargs="?",
        default=None,
        help="the note text (omit to view the current note)",
    )
    p_note.add_argument(
        "--clear",
        action="store_true",
        help="remove the plant's note",
    )
    p_note.set_defaults(func=cmd_note)

    p_export = sub.add_parser(
        "export", help="export plants and watering history as CSV"
    )
    p_export.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default=None,
        help="write the CSV to this file (default: standard output)",
    )
    p_export.set_defaults(func=cmd_export)

    p_zone = sub.add_parser("zone", help="view or set a plant's zone")
    p_zone.add_argument("name", help="name of the plant")
    p_zone.add_argument(
        "text",
        nargs="?",
        default=None,
        help="the zone name (omit to view the current zone)",
    )
    p_zone.add_argument(
        "--clear",
        action="store_true",
        help="remove the plant's zone",
    )
    p_zone.set_defaults(func=cmd_zone)

    p_remove = sub.add_parser("remove", help="stop tracking a plant")
    p_remove.add_argument("name", help="name of the plant to remove")
    p_remove.set_defaults(func=cmd_remove)

    p_stats = sub.add_parser("stats", help="summary counts and the most overdue plant")
    p_stats.set_defaults(func=cmd_stats)

    p_profiles = sub.add_parser("profiles", help="list the available care profiles")
    p_profiles.set_defaults(func=cmd_profiles)

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
