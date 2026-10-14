from collections import defaultdict
import hashlib
import json
from pathlib import Path
import unittest
from xml.etree import ElementTree

from studio.deck_contracts import canonical_deck
from studio.mindmap import canonical_mindmap, render_mindmap_svg
from tests.workbench_shapes import SHAPES, assert_shape


MOCK_DIR = Path(__file__).resolve().parents[1] / "workbench/web/mock"
JSON_SHAPES = {
	"formats.json": SHAPES["formats"],
	"units.json": [SHAPES["unit_summary"]],
	"unit-new.json": SHAPES["unit"],
	"unit-analyzed.json": SHAPES["unit"],
	"unit-analyzed-12.json": SHAPES["unit"],
	"unit-done.json": SHAPES["unit"],
	"job-running.json": SHAPES["job"],
	"job-failed.json": SHAPES["job"],
	"queue-idle.json": SHAPES["queue"],
	"queue-busy.json": SHAPES["queue"],
	"usage.json": SHAPES["usage"],
	"manifest.json": SHAPES["manifest"],
	"ask-story.json": SHAPES["ask"],
	"ask-story-unmade.json": SHAPES["ask"],
	"ask-no-match.json": SHAPES["ask"],
	"ask-out-of-scope.json": SHAPES["ask"],
	"upload.json": SHAPES["upload"],
	"key-points-review.json": SHAPES["key_points"],
}
QUESTIONS = (
	"for 迴圈每一圈做了什麼？",
	"為什麼我的迴圈多跑一次？",
	"while 和 for 怎麼選？",
	"迴圈為什麼停不下來？",
	"巢狀迴圈怎麼數次數？",
)
QUOTES = (
	"for 迴圈每一圈依序檢查條件、執行本體、更新變數。",
	"邊界條件決定迴圈執行幾次，< 與 <= 可能相差一次。",
	"for 適合次數明確的重複，while 適合依條件持續執行。",
	"條件一直成立且變數沒有更新時，迴圈可能停不下來。",
	"巢狀迴圈中，內圈對每一次外圈都會完整執行。",
)
MATERIAL = "# 迴圈\n\n迴圈讓程式依條件重複執行。\n" + "\n".join(QUOTES) + "\n"


def load_mock(name):
	return json.loads((MOCK_DIR / name).read_text(encoding="utf-8"))


def example_mindmap():
	points = load_mock("unit-analyzed.json")["analysis"]["points"]
	labels = ("每圈過程", "邊界判斷", "形式選擇", "停止條件", "次數計算")
	return {
		"contract_version": "1.0", "title": "理解迴圈", "root_id": "loop",
		"nodes": [
			{"id": "loop", "label": "迴圈", "explanation": "依條件重複執行程式。",
				"source_quote": "迴圈讓程式依條件重複執行。"},
			*({"id": point["id"], "label": point["title"], "explanation": quote,
				"source_quote": quote} for point, quote in zip(points, QUOTES)),
		],
		"edges": [
			{"from": "loop", "to": point["id"], "label": label, "source_quote": quote}
			for point, label, quote in zip(points, labels, QUOTES)
		],
	}


class TestShapeChecker(unittest.TestCase):
	def test_exports_required_contracts(self):
		self.assertEqual(set(SHAPES), {
			"formats", "unit_summary", "unit", "analysis", "item", "job",
			"job_error", "queue", "usage", "manifest", "ask", "api_error", "upload", "key_points",
		})

	def test_accepts_nested_lists_nullable_and_numeric_types(self):
		shape = {"points": [{"sec": (int, float), "note": (str, None)}]}
		assert_shape({"points": [{"sec": 60, "note": None}, {"sec": 60.5, "note": "旁白"}]}, shape)
		assert_shape({"points": []}, shape)

	def test_reports_first_missing_nested_key(self):
		with self.assertRaisesRegex(AssertionError, r"\$\.points\[0\]\.question"):
			assert_shape({"points": [{}]}, {"points": [{"question": str, "title": str}]})

	def test_reports_wrong_type_at_custom_path(self):
		with self.assertRaisesRegex(AssertionError, r"response\.points\[0\]\.sec"):
			assert_shape({"points": [{"sec": "60"}]}, {"points": [{"sec": int}]}, path="response")

	def test_rejects_wrong_containers(self):
		for value, shape in (([], {}), ({}, [str]), ("points", [str])):
			with self.subTest(value=value), self.assertRaisesRegex(AssertionError, r"\$"):
				assert_shape(value, shape)

	def test_boolean_is_not_a_number(self):
		for shape in (int, float, (int, float)):
			with self.subTest(shape=shape), self.assertRaises(AssertionError):
				assert_shape(True, shape)
		with self.assertRaises(AssertionError):
			assert_shape(1, bool)

	def test_nullable_nested_shape_keeps_error_path(self):
		shape = {"analysis": ({"points": [{"id": str}]}, None)}
		assert_shape({"analysis": None}, shape)
		assert_shape({"analysis": {"points": [{"id": "q1"}]}}, shape)
		with self.assertRaisesRegex(AssertionError, r"\$\.analysis\.points\[0\]\.id"):
			assert_shape({"analysis": {"points": [{}]}}, shape)

	def test_dynamic_maps_validate_keys_and_values(self):
		assert_shape({"files": {"video": "q2/video.mp4"}}, {"files": {str: str}})
		for files in ({"video": 42}, {42: "q2/video.mp4"}):
			with self.subTest(files=files), self.assertRaisesRegex(AssertionError, r"\$\.files"):
				assert_shape({"files": files}, {"files": {str: str}})

	def test_job_rejects_weird_step_state(self):
		job = load_mock("job-running.json")
		job["steps"][0]["state"] = "weird"
		with self.assertRaisesRegex(AssertionError, r"\$\.steps\[0\]\.state"):
			assert_shape(job, SHAPES["job"])

	def test_job_accepts_all_documented_step_states(self):
		job = load_mock("job-running.json")
		for state in ("pending", "running", "done", "failed", "skipped"):
			with self.subTest(state=state):
				job["steps"][0]["state"] = state
				assert_shape(job, SHAPES["job"])

	def test_job_accepts_nullable_stage_fields(self):
		job = load_mock("job-running.json")
		job.update(unit_id=None, item="ingest", format="ingest", state="queued", current=None)
		assert_shape(job, SHAPES["job"])

	def test_item_and_job_reject_unknown_status(self):
		for name, value, field in (
			("item", load_mock("unit-analyzed.json")["items"][0], "status"),
			("job", load_mock("job-running.json"), "state"),
		):
			value[field] = "weird"
			with self.subTest(name=name), self.assertRaises(AssertionError):
				assert_shape(value, SHAPES[name])

	def test_api_and_job_error_shapes(self):
		error = {"code": "too_large", "reason": "超過上限", "advice": "拆小再上傳"}
		assert_shape({"error": error}, SHAPES["api_error"])
		assert_shape({**error, "retry": False}, SHAPES["job_error"])
		with self.assertRaisesRegex(AssertionError, r"\$\.retry"):
			assert_shape(error, SHAPES["job_error"])
		with self.assertRaisesRegex(AssertionError, r"\$\.error\.advice"):
			assert_shape({"error": {"code": "too_large", "reason": "超過上限"}}, SHAPES["api_error"])

	def test_optional_source_reference_is_opaque(self):
		unit = load_mock("unit-new.json")
		for source_ref in (None, {"platform": "bridgeai", "revision": "r1"}):
			unit["source_ref"] = source_ref
			assert_shape(unit, SHAPES["unit"])


class TestWorkbenchMocks(unittest.TestCase):
	def test_mock_inventory(self):
		self.assertEqual({path.name for path in MOCK_DIR.iterdir()} - {"preview.mp4", "preview.pptx"},
			set(JSON_SHAPES) | {"deck.json", "mindmap.svg"})

	def test_api_json_shapes(self):
		for name, shape in JSON_SHAPES.items():
			with self.subTest(file=name):
				assert_shape(load_mock(name), shape)

	def test_format_registry_and_unique_step_ids(self):
		registry = load_mock("formats.json")
		self.assertEqual([stage["id"] for stage in registry["stages"]], ["ingest", "analysis"])
		available = [fmt for fmt in registry["formats"] if fmt["status"] == "available"]
		planned = [fmt for fmt in registry["formats"] if fmt["status"] == "planned"]
		self.assertEqual([fmt["id"] for fmt in available], ["video", "highlight", "mindmap", "slides"])
		self.assertEqual([fmt["id"] for fmt in planned],
			["comic", "podcast", "interactive_text", "worked_example", "quiz"])
		steps = {
			"video": ["selftest", "storyboard", "validate", "repair", "narrate", "render"],
			"highlight": ["scenes", "compose", "narrate", "render"],
			"mindmap": ["generate", "validate", "render"],
			"slides": ["generate", "validate", "export"],
		}
		for fmt in registry["stages"] + registry["formats"]:
			with self.subTest(format=fmt["id"]):
				ids = [step["id"] for step in fmt["steps"]]
				self.assertEqual(len(ids), len(set(ids)))
				if fmt["id"] in steps:
					self.assertEqual(ids, steps[fmt["id"]])
				if fmt["status"] == "planned":
					self.assertEqual(fmt["steps"], [])
					self.assertNotIn("commands", fmt)
					self.assertIsNotNone(fmt["planned_note"])
				else:
					self.assertIsNone(fmt["planned_note"])
				for step in fmt["steps"]:
					if step["paid"]:
						self.assertTrue(step["model"].startswith("google:gemini-3.8-flash"))
						if fmt["id"] in ("mindmap", "slides"):
							self.assertEqual(step["cost"], "試跑後填入")
		self.assertEqual([fmt["planned_note"]["order"] for fmt in planned], [1, 2, 3, 4, 5])

	def test_loop_analysis_and_unit_snapshots(self):
		new = load_mock("unit-new.json")
		analyzed = load_mock("unit-analyzed.json")
		done = load_mock("unit-done.json")
		self.assertIsNone(new["analysis"])
		self.assertEqual(new["items"], [])
		self.assertEqual(new["spent_usd"], 0)
		self.assertEqual(analyzed["analysis"], done["analysis"])
		points = analyzed["analysis"]["points"]
		self.assertEqual([point["id"] for point in points], ["q1", "q2", "q3", "q4", "q5"])
		self.assertEqual([point["question"] for point in points], list(QUESTIONS))
		self.assertEqual([item["item"] for item in analyzed["items"]],
			["q1", "q2", "q3", "q4", "q5", "highlight", "mindmap", "slides"])
		self.assertTrue(all(item["status"] == "none" and not item["files"] for item in analyzed["items"]))
		for unit in (new, analyzed, done):
			self.assertEqual(unit["unit_id"], hashlib.sha256(MATERIAL.encode("utf-8")).hexdigest()[:12])
			self.assertEqual(unit["title"], "迴圈")
			self.assertEqual(unit["source_ref"], done["source_ref"])
		selected = analyzed["analysis"]["highlight"]["points"]
		self.assertTrue(set(selected) <= {point["id"] for point in points})
		self.assertEqual(analyzed["analysis"]["highlight"]["total_sec"],
			sum(point["sec"] for point in points if point["id"] in selected))

	def test_running_repair_and_failed_job(self):
		running = load_mock("job-running.json")
		self.assertEqual((running["item"], running["state"], running["current"]), ("q2", "running", "repair"))
		states = {step["id"]: step["state"] for step in running["steps"]}
		self.assertEqual(states["storyboard"], "done")
		self.assertEqual(states["validate"], "done")
		self.assertEqual(states["repair"], "running")
		self.assertIsNone(running["error"])
		failed = load_mock("job-failed.json")
		self.assertEqual((failed["item"], failed["state"]), ("q4", "failed"))
		self.assertEqual(failed["error"], {
			"code": "gemini_busy", "reason": "Gemini 暫時忙碌或連線中斷",
			"advice": "等 1–2 分鐘再按「重試」", "retry": True,
		})
		self.assertEqual({step["id"]: step["state"] for step in failed["steps"]}[failed["current"]], "failed")
		for job in (running, failed):
			self.assertLessEqual(len(job["log"]), 40)
			format_steps = next(fmt["steps"] for fmt in load_mock("formats.json")["formats"]
				if fmt["id"] == job["format"])
			self.assertEqual([step["id"] for step in job["steps"]], [step["id"] for step in format_steps])

	def test_idle_and_busy_queues(self):
		self.assertEqual(load_mock("queue-idle.json"), {"running": None, "queued": []})
		busy = load_mock("queue-busy.json")
		self.assertEqual(busy["running"], load_mock("job-running.json"))
		self.assertTrue(busy["queued"])
		for job in busy["queued"]:
			self.assertEqual(job["state"], "queued")
			self.assertIsNone(job["current"])
			self.assertTrue(all(step["state"] == "pending" for step in job["steps"]))

	def test_manifest_and_unit_summary_match_completed_items(self):
		unit = load_mock("unit-done.json")
		manifest = load_mock("manifest.json")
		done = {item["item"]: item for item in unit["items"] if item["status"] == "done"}
		self.assertEqual({product["item"] for product in manifest["products"]}, set(done))
		self.assertEqual(manifest["unit_id"], unit["unit_id"])
		self.assertEqual(manifest["source_ref"], unit["source_ref"])
		for product in manifest["products"]:
			self.assertEqual(product["embed_url"], f"/embed/{unit['unit_id']}/{product['item']}")
			for key in ("format", "label", "files", "duration", "cost_usd"):
				self.assertEqual(product[key], done[product["item"]][key])
		summary, = load_mock("units.json")
		self.assertEqual(summary["unit_id"], unit["unit_id"])
		self.assertTrue(summary["analyzed"])
		self.assertEqual(summary["points"], 5)
		self.assertEqual(summary["products"], {
			"video": sum(item["format"] == "video" for item in done.values()),
			**{fmt: fmt in done for fmt in ("highlight", "mindmap", "slides")},
		})
		self.assertEqual(summary["spent_usd"], unit["spent_usd"])

	def test_usage_totals_match_calls_and_unit_costs(self):
		usage = load_mock("usage.json")
		models = defaultdict(float)
		today = 0
		unit = load_mock("unit-done.json")
		usage_unit, = usage["units"]
		self.assertEqual(usage_unit["unit_id"], unit["unit_id"])
		for item in usage_unit["items"]:
			self.assertAlmostEqual(item["usd"], sum(call["usd"] for call in item["calls"]))
			self.assertEqual([call["at"] for call in item["calls"]],
				sorted((call["at"] for call in item["calls"]), reverse=True))
			for call in item["calls"]:
				models[call["model"]] += call["usd"]
				if call["at"].startswith("2026-10-05"):
					today += call["usd"]
		self.assertEqual(set(usage["totals"]["by_model"]), set(models))
		for model, usd in models.items():
			self.assertAlmostEqual(usage["totals"]["by_model"][model], usd)
		self.assertAlmostEqual(usage["totals"]["today"], today)
		self.assertAlmostEqual(usage["totals"]["all"], sum(models.values()))
		self.assertAlmostEqual(usage_unit["usd"], sum(item["usd"] for item in usage_unit["items"]))
		self.assertAlmostEqual(unit["spent_usd"], usage_unit["usd"])
		costs = {item["item"]: item["usd"] for item in usage_unit["items"]}
		for item in unit["items"]:
			if item["cost_usd"] is not None:
				self.assertAlmostEqual(item["cost_usd"], costs.get(item["item"], 0))

	def test_ask_story_and_out_of_scope(self):
		story = load_mock("ask-story.json")
		self.assertEqual((story["kind"], story["story"]), ("story", "q2"))
		self.assertGreaterEqual(story["score"], 0.18)
		unit = load_mock("unit-done.json")
		video = next(item["files"]["video"] for item in unit["items"] if item["item"] == "q2")
		self.assertEqual(story["video"], f"/media/{unit['unit_id']}/{video}")
		out = load_mock("ask-out-of-scope.json")
		self.assertEqual(out["kind"], "out_of_scope")
		self.assertEqual(out["reason"], "這份教材沒有教這個")
		self.assertIsNone(out["story"])
		self.assertIsNone(out["video"])

	def test_deck_uses_real_contract_and_loop_quotes(self):
		deck = load_mock("deck.json")
		assert_shape(deck, {"contract_version": str, "title": str, "slides": [{
			"slide_id": str, "role": str, "title": str, "layout": str,
			"blocks": [dict], "speaker_notes": str, "source_quote": str,
		}]})
		self.assertEqual(canonical_deck(deck), deck)
		self.assertEqual(deck["title"], "迴圈")
		for slide in deck["slides"]:
			self.assertIn(slide["source_quote"], MATERIAL)

	def test_svg_is_canonical_renderer_output(self):
		svg = (MOCK_DIR / "mindmap.svg").read_bytes()
		assert_shape(svg, bytes)
		mindmap = canonical_mindmap(example_mindmap())
		for entry in mindmap["nodes"] + mindmap["edges"]:
			self.assertIn(entry["source_quote"], MATERIAL)
		self.assertEqual(svg, render_mindmap_svg(mindmap, MATERIAL))
		root = ElementTree.fromstring(svg)
		ns = "{http://www.w3.org/2000/svg}"
		self.assertEqual(root.tag, ns + "svg")
		self.assertEqual(root.find(ns + "title").text, "理解迴圈")
		self.assertEqual({node.attrib["data-node-id"] for node in root.findall(ns + "g")},
			{"loop", "q1", "q2", "q3", "q4", "q5"})


if __name__ == "__main__":
	unittest.main()
