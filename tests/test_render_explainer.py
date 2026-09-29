import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest

from PIL import Image, ImageChops, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

from render_explainer import _wrapped_statement, render_explainer_scene
from render_slides import CJK_FONT, FontGuard, load_theme


def contrast(a, b):
	def luminance(c):
		v = [n / 255 for n in c]
		v = [n / 12.92 if n <= 0.04045 else ((n + 0.055) / 1.055) ** 2.4 for n in v]
		return sum(x * w for x, w in zip(v, (0.2126, 0.7152, 0.0722)))
	light, dark = sorted((luminance(a), luminance(b)), reverse=True)
	return (light + 0.05) / (dark + 0.05)


class TestExplainerArtifacts(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		with open(os.path.join(ROOT, "video_engine", "examples", "c_loop.lesson.json"), encoding="utf-8") as f:
			cls.slides = json.load(f)["slides"]
		cls.guard = FontGuard(CJK_FONT)
		cls.theme = load_theme("explainer")

	def render(self, slide, idx=1):
		with tempfile.TemporaryDirectory() as temp:
			boxes, base_path, full_path = render_explainer_scene(slide, self.guard, self.theme, temp, idx)
			with Image.open(base_path) as im:
				base = im.copy()
			with Image.open(full_path) as im:
				full = im.copy()
			return boxes, base, full

	def assert_boxes_on_canvas(self, boxes):
		for key, box in boxes.items():
			with self.subTest(key=key):
				self.assertGreater(box["w"], 0)
				self.assertGreater(box["h"], 0)
				self.assertGreaterEqual(box["x"], 0)
				self.assertGreaterEqual(box["y"], 0)
				self.assertLessEqual(box["x"] + box["w"], 1920)
				self.assertLessEqual(box["y"] + box["h"], 1080)

	def test_four_semantic_scenes_preserve_addressable_boxes(self):
		for idx, slide in enumerate(self.slides, start=1):
			with self.subTest(role=slide["role"]):
				boxes, base, full = self.render(slide, idx)
				self.assertEqual(base.size, (1920, 1080))
				self.assertEqual(full.size, base.size)
				for el in slide["elements"]:
					self.assertIn(el["id"], boxes)
					if el["type"] == "code":
						for line in range(1, len(el["lines"]) + 1):
							self.assertIn(f"{el['id']}:L{line}", boxes)
					if el["type"] == "figure":
						if el["kind"] == "compare":
							for side, prefix in (("left", "l"), ("right", "r")):
								for item in range(1, len(el[side]["items"]) + 1):
									self.assertIn(f"{el['id']}:{prefix}{item}", boxes)
						else:
							for item in range(1, len(el["items"]) + 1):
								self.assertIn(f"{el['id']}:i{item}", boxes)
						if el.get("caption"):
							self.assertIn(f"{el['id']}:caption", boxes)
				self.assert_boxes_on_canvas(boxes)

	def test_hidden_text_only_appears_in_full_at_its_measured_position(self):
		slide = self.slides[0]
		boxes, base, full = self.render(slide)
		hidden = [boxes[e["id"]] for e in slide["elements"] if e.get("hidden")]
		diff = ImageChops.difference(base, full)
		self.assertIsNotNone(diff.getbbox())
		for box in hidden:
			crop = diff.crop((box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"]))
			self.assertIsNotNone(crop.getbbox())
		mask = Image.new("1", base.size, 0)
		from PIL import ImageDraw
		pen = ImageDraw.Draw(mask)
		for box in hidden:
			pen.rectangle((box["x"], box["y"], box["x"] + box["w"] - 1, box["y"] + box["h"] - 1), fill=1)
		outside = ImageChops.difference(base, full).convert("L")
		outside.paste(0, mask=mask)
		self.assertIsNone(outside.getbbox())

	def test_no_legacy_card_frame_and_output_is_deterministic(self):
		boxes, base, full = self.render(self.slides[0])
		bg = self.theme["canvas"]["bg"]
		for corner in ((80, 60), (1840, 60), (80, 240), (1840, 980)):
			self.assertEqual(base.getpixel(corner), bg)
		with tempfile.TemporaryDirectory() as temp:
			first = render_explainer_scene(self.slides[0], self.guard, self.theme, os.path.join(temp, "a"), 1)
			second = render_explainer_scene(self.slides[0], self.guard, self.theme, os.path.join(temp, "b"), 1)
			for first_path, second_path in zip(first[1:], second[1:]):
				with open(first_path, "rb") as source, open(second_path, "rb") as repeat:
					self.assertEqual(hashlib.sha256(source.read()).digest(), hashlib.sha256(repeat.read()).digest())

	def test_code_line_numbers_align_with_measured_line_rows(self):
		slide = self.slides[2]
		boxes, _, full = self.render(slide, 3)
		code = next(el for el in slide["elements"] if el["type"] == "code")
		background = self.theme["code"]["bg"]
		for index, line in enumerate(code["lines"], start=1):
			row = boxes[f"{code['id']}:L{index}"]
			self.assertLessEqual(boxes[code["id"]]["y"], row["y"])
			self.assertLessEqual(row["y"] + row["h"], boxes[code["id"]]["y"] + boxes[code["id"]]["h"])
			code_left = boxes[code["id"]]["x"]
			numbers = full.crop((code_left + 20, row["y"], row["x"] - 25, row["y"] + row["h"]))
			num_ink = ImageChops.difference(numbers, Image.new("RGB", numbers.size, background)).getbbox()
			self.assertIsNotNone(num_ink)
			if line:
				text = full.crop((row["x"], row["y"], row["x"] + row["w"], row["y"] + row["h"]))
				text_ink = ImageChops.difference(text, Image.new("RGB", text.size, background)).getbbox()
				self.assertIsNotNone(text_ink)
				self.assertLessEqual(abs(num_ink[1] - text_ink[1]), 3)

	def test_hidden_figure_main_box_includes_its_caption(self):
		slide = copy.deepcopy(self.slides[1])
		figure = next(el for el in slide["elements"] if el["type"] == "figure")
		figure["hidden"] = True
		figure["caption"] = "結束字元決定字串終點"
		boxes, base, full = self.render(slide, 2)
		main = boxes[figure["id"]]
		caption = boxes[f"{figure['id']}:caption"]
		self.assertLessEqual(caption["y"] + caption["h"], main["y"] + main["h"])
		self.assertNotEqual(base.crop((caption["x"], caption["y"], caption["x"] + caption["w"], caption["y"] + caption["h"])).tobytes(),
			full.crop((caption["x"], caption["y"], caption["x"] + caption["w"], caption["y"] + caption["h"])).tobytes())

	def test_single_model_item_reveal_includes_wide_caption(self):
		slide = copy.deepcopy(self.slides[1])
		figure = next(el for el in slide["elements"] if el["type"] == "figure")
		figure["items"] = ["起始"]
		figure["hidden"] = True
		figure["caption"] = "先決定起點，再決定要繼續執行的條件，最後每輪都必須有讓條件改變的更新步驟"
		boxes, _, _ = self.render(slide, 2)
		main = boxes[figure["id"]]
		caption = boxes[f"{figure['id']}:caption"]
		self.assertLessEqual(main["x"], caption["x"])
		self.assertGreaterEqual(main["x"] + main["w"], caption["x"] + caption["w"])

	def test_wrapped_chinese_sentence_prefers_punctuation_boundary(self):
		source = "指定內容要用字串複製函式，一個字元一個字元搬"
		canvas = Image.new("RGB", (1920, 1080))
		wrapped = _wrapped_statement(source, self.guard, self.theme, ImageDraw.Draw(canvas), "bullet", 760)
		self.assertEqual(wrapped.replace("\n", ""), source)
		self.assertTrue(wrapped.split("\n")[0].endswith("，"))

	def test_long_pitfall_sentence_wraps_at_readable_size(self):
		boxes, _, _ = self.render(self.slides[4], 5)
		self.assertGreaterEqual(boxes["p5_a"]["h"], 60)
		self.assertLess(boxes["p5_a"]["x"] + boxes["p5_a"]["w"], boxes["p5_c"]["x"])

	def test_pitfall_with_three_bullets_does_not_overlap_figure(self):
		slide = copy.deepcopy(self.slides[4])
		slide["elements"].insert(-1, {"id": "p5_d", "type": "bullet", "text": "再檢查下一輪條件是否真的會變"})
		boxes, _, _ = self.render(slide, 5)
		for bullet in ("p5_a", "p5_b", "p5_d"):
			self.assertLessEqual(boxes[bullet]["y"] + boxes[bullet]["h"], boxes["p5_fig"]["y"] - 16)

	def test_motion_focus_color_is_absent_from_static_scenes(self):
		focus = self.theme["effects"]["focus"]
		focus_dark = self.theme["effects"]["focus_on_dark"]
		for slide in self.slides:
			_, _, full = self.render(slide)
			colors = set(full.get_flattened_data())
			self.assertFalse(focus in colors)
			self.assertFalse(focus_dark in colors)

	def test_unsupported_scene_fails_explicitly(self):
		with tempfile.TemporaryDirectory() as temp:
			with self.assertRaisesRegex(ValueError, "unsupported"):
				render_explainer_scene({"id": "blank", "role": "concept", "elements": []}, self.guard, self.theme, temp, 1)

	def test_theme_text_and_focus_have_readable_contrast(self):
		th = self.theme
		self.assertGreaterEqual(contrast(th["text"]["title"], th["canvas"]["bg"]), 4.5)
		self.assertGreaterEqual(contrast(th["text"]["bullet"], th["canvas"]["bg"]), 4.5)
		self.assertGreaterEqual(contrast(th["code"]["normal"], th["code"]["bg"]), 4.5)
		self.assertGreaterEqual(contrast(th["effects"]["focus"], th["canvas"]["bg"]), 3.0)
		self.assertGreaterEqual(contrast(th["effects"]["focus_on_dark"], th["code"]["bg"]), 3.0)


if __name__ == "__main__":
	unittest.main()
