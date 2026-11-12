# GardenLog CLI

A tiny command-line garden care tracker. GardenLog keeps a list of your
plants, remembers when each one was last watered, and tells you which ones
are due (or overdue) for their next drink.

Pure Python 3, standard library only — no dependencies to install.

## Install

```bash
pip install .
```

This provides the `gardenlog` command. You can also run it without
installing, straight from the source tree:

```bash
python -m gardenlog --help
```

Requires Python 3.9 or newer.

## Usage

### Add a plant

```bash
$ gardenlog add Monstera --species "Monstera deliciosa" --planted 2026-10-24 --interval 7
Added Monstera (Monstera deliciosa): planted 2026-10-24, water every 7 day(s), first due 2026-10-31.

$ gardenlog add Basil --species "Sweet basil" --planted 2026-10-30 --interval 3
Added Basil (Sweet basil): planted 2026-10-30, water every 3 day(s), first due 2026-11-02.
```

`--species` is optional, `--planted` defaults to today, and `--interval`
(the watering interval in days) defaults to 7. Plant names are unique —
adding the same name twice is rejected with a friendly error.

### See everything at a glance

```bash
$ gardenlog list
Name                 Species                  Last watered  Next due    Status
------------------------------------------------------------------------------
Basil                Sweet basil              2026-10-30    2026-11-02  due today
Monstera             Monstera deliciosa       2026-10-24    2026-10-31  OVERDUE by 2d
```

A plant that has never been watered counts as last watered on the day it
was planted, so its first due date is `planted + interval`.

### What needs water right now?

```bash
$ gardenlog due
Plants needing water as of 2026-11-02:
- Monstera: last watered 2026-10-24, was due 2026-10-31 (2 day(s) overdue)
- Basil: last watered 2026-10-30, was due 2026-11-02 (due today)
```

### Rain-aware due list (opt-in, still offline)

GardenLog never fetches weather itself. If you keep a small JSON forecast
file — written by hand or by your own script — `due` can flag waterings
that rain would cover anyway:

```
$ cat forecast.json
{"2026-11-12": {"rain": true}, "2026-11-13": {"rain_chance": 10}}

$ gardenlog due --forecast forecast.json
Plants needing water as of 2026-11-12:
- Fern: last watered 2026-11-05, was due 2026-11-12 (due today) (rain expected today — consider delaying to 2026-11-13 if outdoors)
```

A day counts as rainy with `"rain": true` or `"rain_chance"` of 50 or
more. The schedule itself never changes — the flag is advisory only.

### Record a watering

```bash
$ gardenlog water Basil
Watered Basil on 2026-11-02. Next due 2026-11-05.
```

Backfill a watering you forgot to log with `--date`:

```bash
$ gardenlog water Basil --date 2026-10-31
```

### Feed on its own schedule

Feeding is tracked separately from watering, with its own interval:

```
$ gardenlog add Fern --planted 2026-10-20 --feed-interval 30
Added Fern: planted 2026-10-20, water every 7 day(s), first due 2026-10-27. Feed every 30 day(s), first feed due 2026-11-19.

$ gardenlog feed Fern
Fed Fern on 2026-11-12. Next feed due 2026-12-12.
```

Plants that already exist get a schedule with
`gardenlog schedule-feed <name> --every 30` (and `--off` removes it).
Due feedings show up in `gardenlog due` next to due waterings.

### Start from a care profile

```
$ gardenlog profiles
Available care profiles (starting defaults, all overridable):
- fern: water every 3 day(s), feed every 30 day(s)
- herb: water every 2 day(s), feed every 14 day(s)
- succulent: water every 14 day(s), feed every 60 day(s)

$ gardenlog add Basil --profile herb
```

Profiles are only starting points: `--interval` and `--feed-interval`
override the profile's values, and schedules can be changed at any time.

### Group plants into zones

```
$ gardenlog add Fern --zone balcony
$ gardenlog list --zone balcony
$ gardenlog due --zone balcony
```

A zone is just a location label (balcony, kitchen, greenhouse…). Set it
when adding a plant, or later with `gardenlog zone <name> "balcony"`
(`--clear` removes it). `list` and `due` filter by zone
case-insensitively.

### Keep a note on a plant

```
$ gardenlog note Monstera "moved to the balcony"
Note saved for Monstera: moved to the balcony

$ gardenlog note Monstera
Monstera note: moved to the balcony
```

Notes appear under the plant in `gardenlog list`; remove one with
`gardenlog note <name> --clear`.

### Remove a plant and see the summary

```bash
$ gardenlog remove Basil
Removed Basil from tracking.

$ gardenlog stats
Plants tracked: 2
Waterings logged: 1
Most overdue: Monstera (2 day(s) past due)
```

### Export to CSV

```
$ gardenlog export --output plants.csv
Exported 2 plant(s) to plants.csv.
```

One row per plant — name, species, planted date, interval, note, watering
count, last-watered and next-due dates, plus the full watering history
joined by `;` — ready for spreadsheets and backups. Without `--output`,
the CSV goes to standard output.

## Data format

Everything lives in one JSON file — `~/.gardenlog.json` by default, or the
path in the `GARDENLOG_DATA` environment variable. It is plain,
human-readable JSON, so you can inspect or back it up with any tool:

```json
{
  "plants": [
    {
      "name": "Monstera",
      "species": "Monstera deliciosa",
      "planted": "2026-10-24",
      "interval_days": 7,
      "waterings": ["2026-10-31"],
      "note": "",
      "feed_interval_days": null,
      "feedings": [],
      "zone": "",
      "profile": ""
    }
  ]
}
```

## Development

Run the test suite (standard-library `unittest`, no extra packages):

```bash
python -m unittest discover -s tests -v
```

See [ROADMAP.md](ROADMAP.md) for where GardenLog is heading and
[CHANGELOG.md](CHANGELOG.md) for what has shipped.

## License

MIT — see [LICENSE](LICENSE).
