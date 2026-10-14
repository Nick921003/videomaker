from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date, datetime, timezone
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.workbench_shapes import SHAPES, assert_shape
from workbench import server


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "video_engine/board"))
import author as BA


PLAN = {"stories": [{"id": "q2", "title": "每一圈"}, {"id": "q1", "title": "邊界"}]}


def row(item="q1", at="2026-10-05T10:00:00", usd=0.02, model="gemini-3.8-flash", step="storyboard"):
	return {"at": at, "item": item, "step": step, "model": model, "in": 100, "out": 200, "usd": usd}


class TestReadUnit(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.directory = Path(self.temp.name)

	def write_rows(self, relative, rows):
		path = self.directory / relative
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text("".join(json.dumps(value) + "\n" for value in rows), encoding="utf-8")
		return path

	def test_missing_usage_is_empty_and_free(self):
		from workbench import usage
		self.assertEqual(usage.read_unit(self.directory), [])
		self.assertEqual(usage.unit_spent(self.directory), 0.0)

	def test_unknown_cost_survives_read_and_summary_as_known_subtotal(self):
		from workbench import usage
		self.write_rows("usage.jsonl", [row(usd=0.02), row(usd=None),
			{**row(usd=0.0), "estimated_cost_usd": None, "reported": False}])
		rows = usage.read_unit(self.directory)
		self.assertEqual(len(rows), 3)
		self.assertEqual(sum(bool(value.get("cost_unknown")) for value in rows), 2)
		result = usage.summarize([("u1", "教材", PLAN, rows)], date(2026, 10, 5))
		self.assertEqual(result["totals"]["unknown_calls"], 2)
		self.assertEqual(result["totals"]["unknown_today"], 2)
		self.assertAlmostEqual(result["totals"]["all"], 0.02)
		self.assertEqual(result["units"][0]["unknown_calls"], 2)
		self.assertEqual(result["units"][0]["items"][0]["unknown_calls"], 2)
		self.assertEqual(sum(bool(call.get("cost_unknown")) for call in result["units"][0]["items"][0]["calls"]), 2)
		assert_shape(result, SHAPES["usage"])

	def test_legacy_plan_and_scene_mapping(self):
		from workbench import usage
		self.write_rows("usage.jsonl", [
			{"at": "2026-10-04T10:00:00", "stage": "plan", "model": "gemini-3.8-flash", "in": 100, "out": 200, "usd": 0.01},
			{"at": "2026-10-05T10:00:00", "stage": "scene", "model": "gemini-3.8-flash", "in": 100, "out": 200, "usd": 0.02},
		])
		self.assertEqual(usage.read_unit(self.directory), [
			row("analysis", "2026-10-04T10:00:00", 0.01, step="plan"), row("video"),
		])

	def test_tagged_author_rows_map_stage_without_losing_item(self):
		from workbench import usage
		self.write_rows("usage.jsonl", [
			{"stage": "scene", "item": "q2", "usd": 0.02},
			{"stage": "plan", "item": "analysis", "usd": 0.01},
			{"stage": "scene", "item": None, "usd": 0.03},
		])
		self.assertEqual([(value["item"], value["step"]) for value in usage.read_unit(self.directory)],
			[("q2", "storyboard"), ("analysis", "plan"), ("video", "storyboard")])

	def test_unified_rows_keep_step_and_cache_counts(self):
		from workbench import usage
		rows = [dict(row(item, step="generate"), cache_read=25, cache_write=50)
			for item in ("mindmap", "slides", "highlight", "ingest")]
		self.write_rows("usage.jsonl", rows)
		self.assertEqual(usage.read_unit(self.directory), rows)

	def test_tts_infers_folder_and_uses_mtime_only_for_missing_at(self):
		from workbench import usage
		path = self.write_rows("q2/voice/tts_usage.jsonl", [
			{"model": "gemini-3.8-flash-tts", "in": 5, "out": 8, "usd": 0.003, "beat": "b1"},
			{"at": "2026-10-04T09:00:00", "model": "gemini-3.8-flash-tts", "in": 9, "out": 10, "usd": 0.004},
		])
		modified = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
		os.utime(path, (modified.timestamp(), modified.timestamp()))
		self.write_rows("highlight/voice/tts_usage.jsonl", [{"usd": 0.005}])
		rows = usage.read_unit(self.directory)
		point_calls = [value for value in rows if value["item"] == "q2"]
		self.assertEqual(point_calls, [
			row("q2", modified.isoformat(), 0.003, "gemini-3.8-flash-tts", "narrate") | {"in": 5, "out": 8},
			row("q2", "2026-10-04T09:00:00", 0.004, "gemini-3.8-flash-tts", "narrate") | {"in": 9, "out": 10},
		])
		self.assertEqual([(value["item"], value["step"]) for value in rows if value["item"] == "highlight"],
			[("highlight", "narrate")])
		self.assertAlmostEqual(usage.unit_spent(self.directory), 0.012)

	def test_partial_and_invalid_rows_do_not_hide_valid_costs(self):
		from workbench import usage
		path = self.write_rows("usage.jsonl", [{"usd": 0.1}, None, [], {"usd": "bad"}, {"usd": True}, {"usd": float("nan")}])
		with path.open("a", encoding="utf-8") as handle:
			handle.write('\n{"usd":')
		self.write_rows("q1/voice/tts_usage.jsonl", [{"usd": 0.02}])
		self.assertAlmostEqual(usage.unit_spent(self.directory), 0.12)
		summary = usage.summarize([("u1", "迴圈", PLAN, usage.read_unit(self.directory))], date(2026, 10, 5))
		assert_shape(summary, SHAPES["usage"])

	def test_invalid_optional_fields_still_produce_usage_shape(self):
		from workbench import usage
		self.write_rows("usage.jsonl", [{"at": 7, "item": 4, "step": {}, "stage": [],
			"model": 2, "in": "3", "out": True, "usd": 0.01}])
		rows = usage.read_unit(self.directory)
		self.assertEqual([(value["item"], value["step"], value["model"], value["in"], value["out"]) for value in rows],
			[("video", "", "unknown", 0, 0)])
		assert_shape(usage.summarize([("u1", "迴圈", PLAN, rows)], date(2026, 10, 5)), SHAPES["usage"])

	def test_usage_paths_cannot_escape_unit(self):
		from workbench import usage
		with tempfile.TemporaryDirectory() as outside:
			external = Path(outside) / "usage.jsonl"
			external.write_text('{"usd": 1}\n', encoding="utf-8")
			(self.directory / "usage.jsonl").symlink_to(external)
			with self.assertRaises(ValueError):
				usage.read_unit(self.directory)

	def test_tts_paths_cannot_escape_unit(self):
		from workbench import usage
		with tempfile.TemporaryDirectory() as outside:
			voice = Path(outside) / "voice"
			voice.mkdir()
			(voice / "tts_usage.jsonl").write_text('{"usd": 1}\n', encoding="utf-8")
			(self.directory / "q1").symlink_to(outside, target_is_directory=True)
			with self.assertRaises(ValueError):
				usage.read_unit(self.directory)


class TestSummary(unittest.TestCase):
	def test_totals_models_items_and_shape(self):
		from workbench import usage
		units = [
			("u1", "迴圈", PLAN, [row("analysis", "2026-10-04T10:00:00", 0.01, step="plan"), row(usd=0.02),
				row(at="2026-10-05T11:00:00", usd=0.03, model="gemini-3.8-flash-tts", step="narrate")]),
			("u2", "字串", None, [row("slides", usd=0.04), row("video", "2026-10-03T10:00:00", 0.05, "claude-opus-5-5")]),
		]
		before = deepcopy(units)
		result = usage.summarize(units, date(2026, 10, 5))
		assert_shape(result, SHAPES["usage"])
		self.assertAlmostEqual(result["totals"]["today"], 0.09)
		self.assertAlmostEqual(result["totals"]["all"], 0.15)
		self.assertEqual(result["totals"]["by_model"],
			{"gemini-3.8-flash": 0.07, "gemini-3.8-flash-tts": 0.03, "claude-opus-5-5": 0.05})
		by_unit = {unit["unit_id"]: unit for unit in result["units"]}
		self.assertEqual(by_unit["u1"]["title"], "迴圈")
		self.assertAlmostEqual(by_unit["u1"]["usd"], 0.06)
		self.assertAlmostEqual(by_unit["u2"]["usd"], 0.09)
		items = {item["item"]: item for item in by_unit["u1"]["items"]}
		self.assertEqual(items["analysis"]["label"], "教材分析")
		self.assertEqual(items["q1"]["label"], "第 2 點影片：邊界")
		self.assertAlmostEqual(items["q1"]["usd"], 0.05)
		self.assertEqual([call["step"] for call in items["q1"]["calls"]], ["narrate", "storyboard"])
		self.assertEqual(units, before)

	def test_calls_sort_by_instant_with_mixed_iso_timestamps(self):
		from workbench import usage
		rows = [row(at="2026-10-05T10:00:00+08:00"), row(at="2026-10-05T04:00:00Z"),
			row(at="2026-10-05T03:00:00")]
		result = usage.summarize([("u1", "迴圈", PLAN, rows)], date(2026, 10, 5))
		self.assertEqual([call["at"] for call in result["units"][0]["items"][0]["calls"]],
			[rows[1]["at"], rows[2]["at"], rows[0]["at"]])

	def test_today_uses_the_recorded_calendar_date(self):
		from workbench import usage
		rows = [row(at="2026-10-05T00:30:00+08:00", usd=0.1), row(at="2026-10-04T23:30:00Z", usd=0.2)]
		result = usage.summarize([("u1", "迴圈", PLAN, rows)], date(2026, 10, 5))
		self.assertAlmostEqual(result["totals"]["today"], 0.1)

	def test_empty_summary_and_units_pass_shape(self):
		from workbench import usage
		for units in ([], [("u1", "未分析", None, [])]):
			with self.subTest(units=units):
				result = usage.summarize(units, date(2026, 10, 5))
				assert_shape(result, SHAPES["usage"])
				self.assertEqual(result["totals"], {"today": 0.0, "all": 0.0, "by_model": {}})
				if units:
					self.assertEqual(result["units"], [{"unit_id": "u1", "title": "未分析", "usd": 0.0, "items": []}])

	def test_labels_follow_story_order_and_fixed_names(self):
		from workbench import usage
		labels = {"highlight": "重點片", "mindmap": "心智圖", "slides": "簡報", "analysis": "教材分析",
			"ingest": "教材整理", "video": "影片（未標點）"}
		self.assertEqual(usage.item_label("q2", PLAN), "第 1 點影片：每一圈")
		for item, label in labels.items():
			with self.subTest(item=item):
				self.assertEqual(usage.item_label(item, None), label)
		self.assertEqual(usage.item_label("q1", None), "q1")


class TestAuthorTagging(unittest.TestCase):
	def test_record_adds_item_and_preserves_cost_and_stage(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "usage.jsonl"
			budget = BA.Budget(path, 0.5, item="q2")
			cost = budget.record("scene", "gemini-3.8-flash", {"in": 100, "out": 200, "cache_read": 50, "cache_write": 0})
			value = json.loads(path.read_text(encoding="utf-8"))
			self.assertEqual((value["item"], value["stage"]), ("q2", "scene"))
			self.assertAlmostEqual(cost, (100 * 0.75 + 200 * 3.75 + 50 * 0.075) / 1e6)
			self.assertEqual(value["usd"], round(cost, 5))

	def test_budget_item_is_optional(self):
		with tempfile.TemporaryDirectory() as directory:
			path = Path(directory) / "usage.jsonl"
			budget = BA.Budget(path, 0.5)
			budget.record("plan", "gemini-3.8-flash", {"in": 100, "out": 200, "cache_read": 0, "cache_write": 0})
			self.assertIsNone(json.loads(path.read_text(encoding="utf-8"))["item"])

	def test_cli_tags_plan_and_scene_without_paid_calls(self):
		for stage, segment, item in (("plan", None, "analysis"), ("scene", "q2", "q2"), ("scene", "highlight", "highlight")):
			with self.subTest(stage=stage, segment=segment), tempfile.TemporaryDirectory() as directory:
				def fake_stage(*args):
					budget = args[2] if stage == "plan" else args[3]
					budget.record(stage, "gemini-3.8-flash", {"in": 100, "out": 200, "cache_read": 0, "cache_write": 0})
				argv = ["author.py", stage, "unused.md", directory] + ([segment] if segment else [])
				with patch.object(BA.sys, "argv", argv), patch("llm.load_env"), \
					patch.object(BA, "do_plan", side_effect=fake_stage), patch.object(BA, "do_scene", side_effect=fake_stage), \
					redirect_stdout(io.StringIO()):
					BA.main()
				value = json.loads((Path(directory) / "usage.jsonl").read_text(encoding="utf-8"))
				self.assertEqual(value["item"], item)


class TestServerUsage(unittest.TestCase):
	def test_unit_detail_uses_usage_helper(self):
		from workbench import usage
		with tempfile.TemporaryDirectory() as directory:
			studio = server.Studio(Path(directory) / "units", command_runner=lambda *args: 0)
			try:
				uid = studio.create_unit({"markdown": "# 迴圈"})["unit_id"]
				with patch.object(usage, "unit_spent", return_value=0.123) as spent:
					self.assertEqual(studio.get_unit(uid)["spent_usd"], 0.123)
					spent.assert_called_once_with(studio.library.unit_dir(uid))
			finally:
				studio.close()


if __name__ == "__main__":
	unittest.main()
