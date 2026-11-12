# Changelog

All notable changes to GardenLog are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and GardenLog
uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `gardenlog note` — a free-text note per plant: set with
  `gardenlog note <name> "..."`, view with `gardenlog note <name>`, remove
  with `--clear`. Notes are shown indented under the plant in `gardenlog
  list`. Data files written before this feature (plants without a `note`
  field) keep working unchanged.

## [0.1.0] - 2026-11-02

### Added

- `gardenlog add` — register a plant with an optional species, planted
  date, and watering interval in days (defaults: today, every 7 days).
  Duplicate names are rejected with a friendly error.
- `gardenlog list` — all tracked plants with last-watered date, next due
  date, and a plain-language status (overdue / due today / in N days).
- `gardenlog due` — plants due or overdue for watering, worst first.
- `gardenlog water` — record a watering today, or backfill with `--date`.
- `gardenlog remove` — stop tracking a plant.
- `gardenlog stats` — plants tracked, waterings logged, most overdue plant.
- Single-file JSON storage at `~/.gardenlog.json`, overridable with the
  `GARDENLOG_DATA` environment variable.
- Unit tests for the schedule logic and every command (14 tests).
