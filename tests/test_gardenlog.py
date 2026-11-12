"""Unit tests for GardenLog's schedule logic and CLI commands.

Deterministic: every test injects a fixed `today` and points
$GARDENLOG_DATA at a fresh temporary file.
"""

import csv
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from pathlib import Path

from gardenlog import cli, store

TODAY = date(2026, 11, 2)  # a fixed Monday


class GardenLogTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data_file = Path(self._tmp.name) / "data.json"
        self._old_env = os.environ.get(store.ENV_DATA_FILE)
        os.environ[store.ENV_DATA_FILE] = str(self.data_file)

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop(store.ENV_DATA_FILE, None)
        else:
            os.environ[store.ENV_DATA_FILE] = self._old_env
        self._tmp.cleanup()

    def run_cli(self, argv, today=TODAY):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv, today=today)
        return code, out.getvalue(), err.getvalue()

    def add_fern(self):
        code, out, _ = self.run_cli(
            ["add", "Fern", "--planted", "2026-10-20", "--interval", "7"]
        )
        self.assertEqual(code, 0, out)


class TestScheduleLogic(GardenLogTestCase):
    def test_never_watered_counts_planted_date_as_last_watered(self):
        plant = store.make_plant("Fern", "", date(2026, 10, 20), 7)
        self.assertEqual(store.last_watered(plant), date(2026, 10, 20))
        self.assertEqual(store.next_due(plant), date(2026, 10, 27))

    def test_due_on_exact_due_date(self):
        plant = store.make_plant("Fern", "", date(2026, 10, 20), 7)
        self.assertTrue(store.is_due(plant, date(2026, 10, 27)))
        self.assertFalse(store.is_due(plant, date(2026, 10, 26)))

    def test_days_overdue_counts_past_due_date(self):
        plant = store.make_plant("Fern", "", date(2026, 10, 20), 7)
        self.assertEqual(store.days_overdue(plant, TODAY), 6)

    def test_new_plant_has_empty_note_and_old_data_without_note_is_fine(self):
        plant = store.make_plant("Fern", "", date(2026, 10, 20), 7)
        self.assertEqual(store.plant_note(plant), "")
        legacy = {
            "name": "Old",
            "species": "",
            "planted": "2026-10-01",
            "interval_days": 7,
            "waterings": [],
        }
        self.assertEqual(store.plant_note(legacy), "")

    def test_feed_schedule_counts_from_planted_until_first_feeding(self):
        plant = store.make_plant("Fern", "", date(2026, 10, 20), 7, 14)
        self.assertEqual(store.next_feed_due(plant), date(2026, 11, 3))
        self.assertFalse(store.is_feed_due(plant, date(2026, 11, 2)))
        self.assertTrue(store.is_feed_due(plant, date(2026, 11, 3)))
        plant["feedings"].append("2026-11-01")
        self.assertEqual(store.last_fed(plant), date(2026, 11, 1))
        self.assertEqual(store.next_feed_due(plant), date(2026, 11, 15))

    def test_no_feed_interval_means_feeding_not_tracked(self):
        plant = store.make_plant("Fern", "", date(2026, 10, 20), 7)
        self.assertIsNone(store.feed_interval(plant))
        self.assertIsNone(store.next_feed_due(plant))
        self.assertFalse(store.is_feed_due(plant, TODAY))
        legacy = {
            "name": "Old",
            "species": "",
            "planted": "2026-10-01",
            "interval_days": 7,
            "waterings": [],
        }
        self.assertIsNone(store.feed_interval(legacy))
        self.assertEqual(store.feedings_of(legacy), [])

    def test_watering_moves_due_date(self):
        plant = store.make_plant("Fern", "", date(2026, 10, 20), 7)
        plant["waterings"].append("2026-10-30")
        self.assertEqual(store.last_watered(plant), date(2026, 10, 30))
        self.assertEqual(store.next_due(plant), date(2026, 11, 6))
        self.assertFalse(store.is_due(plant, TODAY))


class TestCommands(GardenLogTestCase):
    def test_add_then_list_shows_plant(self):
        self.add_fern()
        code, out, _ = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("Fern", out)
        self.assertIn("2026-10-27", out)  # next due
        self.assertIn("OVERDUE by 6d", out)

    def test_duplicate_add_is_rejected(self):
        self.add_fern()
        code, _, err = self.run_cli(["add", "fern", "--interval", "3"])
        self.assertEqual(code, 1)
        self.assertIn("already tracked", err)

    def test_add_rejects_zero_interval(self):
        code, _, err = self.run_cli(["add", "Ivy", "--interval", "0"])
        self.assertEqual(code, 1)
        self.assertIn("at least 1 day", err)

    def test_water_unknown_plant_is_friendly_error(self):
        code, _, err = self.run_cli(["water", "Ghost"])
        self.assertEqual(code, 1)
        self.assertIn("no plant named 'Ghost'", err)

    def test_water_clears_due_status(self):
        self.add_fern()
        code, out, _ = self.run_cli(["water", "Fern"])  # waters on TODAY
        self.assertEqual(code, 0)
        self.assertIn("Next due 2026-11-09", out)
        code, out, _ = self.run_cli(["due"])
        self.assertEqual(code, 0)
        self.assertIn("Nothing due", out)

    def test_water_with_explicit_past_date(self):
        self.add_fern()
        code, _, _ = self.run_cli(["water", "Fern", "--date", "2026-10-25"])
        self.assertEqual(code, 0)
        plant = store.find_plant(store.load_data(), "Fern")
        self.assertEqual(plant["waterings"], ["2026-10-25"])

    def test_due_lists_overdue_plant(self):
        self.add_fern()
        code, out, _ = self.run_cli(["due"])
        self.assertEqual(code, 0)
        self.assertIn("Fern", out)
        self.assertIn("6 day(s) overdue", out)

    def test_remove_deletes_plant(self):
        self.add_fern()
        code, out, _ = self.run_cli(["remove", "Fern"])
        self.assertEqual(code, 0)
        self.assertEqual(store.load_data()["plants"], [])
        code, _, err = self.run_cli(["remove", "Fern"])
        self.assertEqual(code, 1)
        self.assertIn("no plant named 'Fern'", err)

    def test_stats_counts_and_most_overdue(self):
        self.add_fern()
        self.run_cli(
            ["add", "Cactus", "--planted", "2026-10-01", "--interval", "30"]
        )
        self.run_cli(["water", "Cactus", "--date", "2026-10-31"])
        code, out, _ = self.run_cli(["stats"])
        self.assertEqual(code, 0)
        self.assertIn("Plants tracked: 2", out)
        self.assertIn("Waterings logged: 1", out)
        self.assertIn("Most overdue: Fern (6 day(s) past due)", out)

    def test_note_set_show_list_and_clear(self):
        self.add_fern()
        code, out, _ = self.run_cli(["note", "Fern"])
        self.assertEqual(code, 0)
        self.assertIn("has no note", out)
        code, out, _ = self.run_cli(["note", "Fern", "moved to the balcony"])
        self.assertEqual(code, 0)
        self.assertIn("Note saved for Fern: moved to the balcony", out)
        code, out, _ = self.run_cli(["note", "Fern"])
        self.assertEqual(code, 0)
        self.assertIn("Fern note: moved to the balcony", out)
        code, out, _ = self.run_cli(["list"])
        self.assertEqual(code, 0)
        self.assertIn("note: moved to the balcony", out)
        code, out, _ = self.run_cli(["note", "Fern", "--clear"])
        self.assertEqual(code, 0)
        plant = store.find_plant(store.load_data(), "Fern")
        self.assertEqual(store.plant_note(plant), "")

    def test_note_unknown_plant_is_friendly_error(self):
        code, _, err = self.run_cli(["note", "Ghost", "boo"])
        self.assertEqual(code, 1)
        self.assertIn("no plant named 'Ghost'", err)

    def test_note_rejects_blank_text(self):
        self.add_fern()
        code, _, err = self.run_cli(["note", "Fern", "   "])
        self.assertEqual(code, 1)
        self.assertIn("--clear", err)

    def test_export_writes_expected_csv_rows(self):
        self.add_fern()
        self.run_cli(["water", "Fern", "--date", "2026-10-25"])
        self.run_cli(["note", "Fern", "likes shade, apparently"])
        code, out, _ = self.run_cli(["export"])
        self.assertEqual(code, 0)
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows[0], cli.EXPORT_FIELDS)
        self.assertEqual(len(rows), 2)
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual(row["name"], "Fern")
        self.assertEqual(row["planted"], "2026-10-20")
        self.assertEqual(row["interval_days"], "7")
        self.assertEqual(row["note"], "likes shade, apparently")
        self.assertEqual(row["waterings_count"], "1")
        self.assertEqual(row["last_watered"], "2026-10-25")
        self.assertEqual(row["next_due"], "2026-11-01")
        self.assertEqual(row["waterings"], "2026-10-25")

    def test_export_to_file(self):
        self.add_fern()
        target = Path(self._tmp.name) / "out" / "plants.csv"
        code, out, _ = self.run_cli(["export", "--output", str(target)])
        self.assertEqual(code, 0)
        self.assertIn("Exported 1 plant(s)", out)
        text = target.read_text(encoding="utf-8")
        self.assertIn("name,species,planted", text)
        self.assertIn("Fern", text)

    def test_export_empty_garden_emits_header_only(self):
        code, out, _ = self.run_cli(["export"])
        self.assertEqual(code, 0)
        rows = list(csv.reader(io.StringIO(out)))
        self.assertEqual(rows, [cli.EXPORT_FIELDS])

    def test_feed_requires_a_schedule(self):
        self.add_fern()
        code, _, err = self.run_cli(["feed", "Fern"])
        self.assertEqual(code, 1)
        self.assertIn("no fertiliser schedule", err)

    def test_feed_records_and_clears_feed_due(self):
        self.run_cli(
            ["add", "Fern", "--planted", "2026-10-20", "--feed-interval", "10"]
        )
        code, out, _ = self.run_cli(["due"])
        self.assertEqual(code, 0)
        self.assertIn("needing fertiliser", out)
        self.assertIn("3 day(s) overdue", out)
        code, out, _ = self.run_cli(["feed", "Fern"])  # feeds on TODAY
        self.assertEqual(code, 0)
        self.assertIn("Next feed due 2026-11-12", out)
        code, out, _ = self.run_cli(["due"])
        self.assertEqual(code, 0)
        self.assertNotIn("fertiliser", out)

    def test_schedule_feed_set_show_and_off(self):
        self.add_fern()
        code, out, _ = self.run_cli(["schedule-feed", "Fern", "--every", "30"])
        self.assertEqual(code, 0)
        self.assertIn("every 30 day(s)", out)
        self.assertIn("2026-11-19", out)  # planted 2026-10-20 + 30 days
        code, out, _ = self.run_cli(["schedule-feed", "Fern"])
        self.assertEqual(code, 0)
        self.assertIn("feed every 30 day(s)", out)
        code, out, _ = self.run_cli(["schedule-feed", "Fern", "--off"])
        self.assertEqual(code, 0)
        code, _, err = self.run_cli(["feed", "Fern"])
        self.assertEqual(code, 1)
        self.assertIn("no fertiliser schedule", err)

    def test_add_rejects_zero_feed_interval(self):
        code, _, err = self.run_cli(["add", "Ivy", "--feed-interval", "0"])
        self.assertEqual(code, 1)
        self.assertIn("at least 1 day", err)

    def test_stats_counts_feedings(self):
        self.run_cli(
            ["add", "Fern", "--planted", "2026-10-20", "--feed-interval", "10"]
        )
        self.run_cli(["feed", "Fern", "--date", "2026-10-28"])
        code, out, _ = self.run_cli(["stats"])
        self.assertEqual(code, 0)
        self.assertIn("Feedings logged: 1", out)

    def test_export_includes_feeding_columns(self):
        self.run_cli(
            ["add", "Fern", "--planted", "2026-10-20", "--feed-interval", "14"]
        )
        self.run_cli(["feed", "Fern", "--date", "2026-10-28"])
        code, out, _ = self.run_cli(["export"])
        self.assertEqual(code, 0)
        rows = list(csv.reader(io.StringIO(out)))
        row = dict(zip(rows[0], rows[1]))
        self.assertEqual(row["feed_interval_days"], "14")
        self.assertEqual(row["feedings_count"], "1")
        self.assertEqual(row["last_fed"], "2026-10-28")
        self.assertEqual(row["next_feed_due"], "2026-11-11")
        self.assertEqual(row["feedings"], "2026-10-28")

    def test_data_roundtrip_through_json_file(self):
        self.add_fern()
        data = store.load_data()
        self.assertEqual(len(data["plants"]), 1)
        self.assertEqual(data["plants"][0]["planted"], "2026-10-20")
        self.assertTrue(self.data_file.exists())


if __name__ == "__main__":
    unittest.main()
