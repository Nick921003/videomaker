import gc
import json
import os
import subprocess
import sys
import tempfile
import unittest
import warnings


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "video_engine", "render_slides.py")
COMPILE = os.path.join(ROOT, "video_engine", "compile_timeline.py")
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

from compile_timeline import compile_slide
from render_slides import load_theme


def sample_lesson():
	return {
		"lesson_id": "visual_style_contract", "title": "視覺模式測試", "theme": "lecture",
		"slides": [
			{"id": "p1", "role": "hook", "elements": [
				{"id": "p1_title", "type": "title", "text": "字元模型"},
				{"id": "p1_fig", "type": "figure", "kind": "boxes", "items": ["A", "\\0"]},
			]},
			{"id": "p2", "role": "concept", "elements": [
				{"id": "p2_title", "type": "title", "text": "結尾"},
				{"id": "p2_b", "type": "bullet", "text": "內容要可讀"},
			]},
		],
	}


class TestVisualStylePipeline(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.lesson = os.path.join(self.tmp.name, "lesson.json")
		with open(self.lesson, "w", encoding="utf-8") as f:
			json.dump(sample_lesson(), f, ensure_ascii=False)

	def render(self, out, *opts):
		result = subprocess.run([sys.executable, RENDER, self.lesson, out, *opts],
			capture_output=True, text=True, timeout=30)
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		with open(os.path.join(out, "layout.json"), encoding="utf-8") as f:
			return json.load(f)

	def test_default_cards_keeps_png_bytes_and_records_style(self):
		default_dir = os.path.join(self.tmp.name, "default")
		explicit_dir = os.path.join(self.tmp.name, "explicit")
		default = self.render(default_dir)
		explicit = self.render(explicit_dir, "--visual-style", "cards")
		self.assertEqual(default["visual_style"], "cards")
		self.assertEqual(default["theme"], "lecture")
		self.assertEqual(explicit["visual_style"], "cards")
		for index, (a, b) in enumerate(zip(default["slides"], explicit["slides"]), start=1):
			self.assertEqual(a["visual_style"], "cards")
			self.assertEqual(b["visual_style"], "cards")
			for kind in ("base", "full"):
				name = f"slide_{index:02d}_{kind}.png"
				with open(os.path.join(default_dir, name), "rb") as fa, open(os.path.join(explicit_dir, name), "rb") as fb:
					self.assertEqual(fa.read(), fb.read(), name)

	def test_explainer_uses_scene_renderer_and_diagnoses_page_fallback(self):
		out = os.path.join(self.tmp.name, "explainer")
		layout = self.render(out, "--visual-style", "explainer")
		self.assertEqual(layout["visual_style"], "explainer")
		self.assertEqual(layout["theme"], "explainer")
		self.assertEqual([page["visual_style"] for page in layout["slides"]], ["explainer", "cards"])
		self.assertIn("p1_fig:i1", layout["slides"][0]["boxes"])
		self.assertIn("p1_fig:i2", layout["slides"][0]["boxes"])
		self.assertIn("p2_b", layout["slides"][1]["boxes"])
		self.assertTrue(any(d["slide"] == "p2" and "unsupported" in d["msg"]
			for d in layout["diagnostics"]))

	def test_timeline_carries_requested_and_effective_page_styles(self):
		out = os.path.join(self.tmp.name, "timeline")
		layout = self.render(out, "--visual-style", "explainer")
		with open(os.path.join(out, "durations.json"), "w", encoding="utf-8") as f:
			json.dump({}, f)
		actions = {"slides": [{"slide_id": page["slide_id"], "actions": []}
			for page in layout["slides"]]}
		actions_path = os.path.join(self.tmp.name, "actions.json")
		with open(actions_path, "w", encoding="utf-8") as f:
			json.dump(actions, f)
		result = subprocess.run([sys.executable, COMPILE, self.lesson, actions_path, out],
			capture_output=True, text=True, timeout=30)
		self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
		with open(os.path.join(out, "timeline.json"), encoding="utf-8") as f:
			timeline = json.load(f)
		self.assertEqual(timeline["visual_style"], "explainer")
		self.assertEqual([scene["visual_style"] for scene in timeline["scenes"]], ["explainer", "cards"])


	def test_explainer_hook_focus_waits_for_intro_without_extending_narration(self):
		actions = {"slides": [
			{"slide_id": "p1", "actions": [
				{"type": "spotlight", "target": "p1_title"},
				{"type": "speech", "text": "字元模型"},
			]},
			{"slide_id": "p2", "actions": []},
		]}
		actions_path = os.path.join(self.tmp.name, "hook.actions.json")
		with open(actions_path, "w", encoding="utf-8") as f:
			json.dump(actions, f, ensure_ascii=False)
		for style, expected_start in (("cards", 420), ("explainer", 600)):
			with self.subTest(style=style):
				out = os.path.join(self.tmp.name, f"hook-{style}")
				self.render(out, "--visual-style", style)
				with open(os.path.join(out, "durations.json"), "w", encoding="utf-8") as f:
					json.dump({"p1#1": {"duration": 1.5, "wav": "placeholder.wav", "text": "字元模型"}}, f)
				result = subprocess.run([sys.executable, COMPILE, self.lesson, actions_path, out],
					capture_output=True, text=True, timeout=30)
				self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
				with open(os.path.join(out, "timeline.json"), encoding="utf-8") as f:
					first = json.load(f)["scenes"][0]
				self.assertEqual(first["effects"][0]["start_ms"], expected_start)
				self.assertLessEqual(first["effects"][0]["end_ms"], first["narration"][0]["end_ms"])


	def test_code_focus_timeline_has_no_text_scanning_metadata(self):
		boxes = {
			"p1_code": {"x": 100, "y": 300, "w": 1000, "h": 400},
			"p1_code:L1": {"x": 140, "y": 360, "w": 300, "h": 56},
		}
		scene, _, _ = compile_slide([
			{"type": "spotlight", "target": "p1_code:L1"},
			{"type": "speech", "text": "讀第一行"},
		], boxes, {"width": 1920, "height": 1080},
			{"p1#1": {"duration": 2.0, "wav": "placeholder.wav", "text": "讀第一行"}},
			"p1", 0)
		focus = scene["effects"][0]
		self.assertEqual(focus["region"], boxes["p1_code"])
		self.assertNotIn("scan", focus)
		self.assertNotIn("scan_at", focus)


	def test_short_hook_does_not_emit_focus_with_negative_lifetime(self):
		boxes = {"p1_title": {"x": 100, "y": 100, "w": 400, "h": 70}}
		scene, _, diags = compile_slide([
			{"type": "spotlight", "target": "p1_title"},
			{"type": "speech", "text": "字"},
		], boxes, {"width": 1920, "height": 1080},
			{"p1#1": {"duration": 0.4, "wav": "placeholder.wav", "text": "字"}},
			"p1", 0, intro_floor_ms=600)
		self.assertEqual(scene["effects"], [])
		self.assertEqual(scene["end_ms"], 400)
		self.assertTrue(any("片頭" in d["msg"] for d in diags))


	def test_theme_loader_closes_palette_file(self):
		with warnings.catch_warnings(record=True) as seen:
			warnings.simplefilter("always", ResourceWarning)
			load_theme("lecture")
			gc.collect()
		self.assertEqual([w for w in seen if issubclass(w.category, ResourceWarning)
			and "lecture.json" in str(w.message)], [])


	def test_visual_style_flag_requires_a_value(self):
		result = subprocess.run([sys.executable, RENDER, self.lesson,
			os.path.join(self.tmp.name, "missing-style"), "--visual-style"],
			capture_output=True, text=True, timeout=30)
		self.assertEqual(result.returncode, 2)
		self.assertIn("缺少", result.stdout)


	def test_short_hook_keeps_hidden_reveal_until_it_finishes(self):
		boxes = {"p1_hidden": {"x": 100, "y": 300, "w": 220, "h": 60}}
		scene, cursor, _ = compile_slide([
			{"type": "reveal", "target": "p1_hidden"},
			{"type": "speech", "text": "字"},
		], boxes, {"width": 1920, "height": 1080},
			{"p1#1": {"duration": 0.4, "wav": "placeholder.wav", "text": "字"}},
			"p1", 0, intro_floor_ms=600)
		self.assertEqual(len(scene["reveals"]), 1)
		reveal = scene["reveals"][0]
		self.assertEqual(reveal["start_ms"], 600)
		self.assertGreaterEqual(scene["end_ms"], reveal["start_ms"] + reveal["ms"] + 200)
		self.assertEqual(cursor, scene["end_ms"])

	def test_fixed_duration_laser_moves_its_end_with_staggered_start(self):
		boxes = {"p1_title": {"x": 100, "y": 100, "w": 400, "h": 70}}
		for floor, expected in ((None, 420), (600, 600)):
			with self.subTest(floor=floor):
				scene, _, _ = compile_slide([
					{"type": "laser", "target": "p1_title"},
					{"type": "speech", "text": "讀標題"},
				], boxes, {"width": 1920, "height": 1080},
					{"p1#1": {"duration": 2.0, "wav": "placeholder.wav", "text": "讀標題"}},
					"p1", 0, intro_floor_ms=floor)
				laser = scene["effects"][0]
				self.assertEqual(laser["start_ms"], expected)
				self.assertEqual(laser["end_ms"] - laser["start_ms"], 1200)


class TestSemanticFocusShapes(unittest.TestCase):
	def test_target_semantics_choose_mark_not_action_name(self):
		import compile_timeline as CT
		slide = {"elements": [
			{"id": "p1_code", "type": "code"},
			{"id": "p1_text", "type": "callout"},
			{"id": "p1_fig", "type": "figure", "kind": "boxes", "caption": "記憶體"},
		]}
		kinds = CT.element_types_for_slide(slide)
		boxes = {key: {"x": 100 + i * 180, "y": 200, "w": 100, "h": 80}
			for i, key in enumerate(("p1_code:L1", "p1_text", "p1_fig:i1", "p1_fig:caption"))}
		actions = []
		for target in boxes:
			for kind in ("spotlight", "laser"):
				actions.extend(({"type": kind, "target": target}, {"type": "pause", "ms": 1600}))
		scene, _, _ = CT.compile_slide(actions, boxes, {"width": 1920, "height": 1080},
			{}, "p1", 0, element_types=kinds)
		expected = {"p1_code:L1": "rail", "p1_text": "underline",
			"p1_fig:i1": "outline", "p1_fig:caption": "underline"}
		for effect in scene["effects"]:
			self.assertEqual(effect["focus_shape"], expected[effect["target"]])

	def test_legacy_compiler_does_not_add_new_focus_shape(self):
		boxes = {"p1_text": {"x": 100, "y": 200, "w": 300, "h": 70}}
		scene, _, _ = compile_slide([{"type": "laser", "target": "p1_text"},
			{"type": "pause", "ms": 1600}], boxes, {"width": 1920, "height": 1080},
			{}, "p1", 0)
		self.assertNotIn("focus_shape", scene["effects"][0])


if __name__ == "__main__":
	unittest.main()
