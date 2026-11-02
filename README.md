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

### Record a watering

```bash
$ gardenlog water Basil
Watered Basil on 2026-11-02. Next due 2026-11-05.
```

Backfill a watering you forgot to log with `--date`:

```bash
$ gardenlog water Basil --date 2026-10-31
```

### Remove a plant and see the summary

```bash
$ gardenlog remove Basil
Removed Basil from tracking.

$ gardenlog stats
Plants tracked: 2
Waterings logged: 1
Most overdue: Monstera (2 day(s) past due)
```

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
      "waterings": ["2026-10-31"]
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
