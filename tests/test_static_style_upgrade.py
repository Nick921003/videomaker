import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import layout as L
import render_slides as R


def luminance(color):
	values = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
		for v in (c / 255 for c in color)]
	return sum(a * b for a, b in zip(values, (0.2126, 0.7152, 0.0722)))


def contrast(a, b):
	x, y = sorted((luminance(a), luminance(b)))
	return (y + 0.05) / (x + 0.05)


class TestLectureTheme(unittest.TestCase):
	def test_palette_contrast_and_font_roles(self):
		th = R.load_theme("lecture")
		self.assertEqual(th["name"], "lecture")
		for role in ("title", "subtitle", "bullet", "callout"):
			self.assertGreaterEqual(contrast(th["text"][role], th["card"]["fill"]), 4.5)
		for role in ("normal", "keyword", "preproc"):
			self.assertGreaterEqual(contrast(th["code"][role], th["code"]["bg"]), 4.5)
		self.assertGreaterEqual(contrast(th["figure"]["heading_text"],
			th["figure"]["heading"]), 4.5)
		self.assertEqual(R.font_for_role(th, "code")[1], 8)
		self.assertEqual(R.font_for_role(th, "title")[1], 3)
		self.assertEqual(R.font_for_role(R.load_theme("warm"), "code"), (R.CJK_FONT, 0))

	def test_code_font_is_monospace(self):
		font_path, face = R.font_for_role(R.load_theme("lecture"), "code")
		font = ImageFont.truetype(font_path, 28, index=face)
		draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
		self.assertAlmostEqual(draw.textlength("iiii", font=font),
			draw.textlength("WWWW", font=font), delta=1)


class TestLectureRender(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, self.dir, True)
		self.guard = R.FontGuard(R.CJK_FONT)
		self.theme = R.load_theme("lecture")

	def slide(self, code_line):
		return {"id": "p1", "elements": [
			{"id": "t", "type": "title", "text": "迴圈入門"},
			{"id": "s", "type": "subtitle", "text": "每一步都看得清楚"},
			{"id": "c", "type": "code", "lines": [code_line]},
		]}

	def test_output_color_geometry_and_determinism(self):
		boxes, _, full_path = R.render_slide(self.slide("int total = 0;"), self.guard,
			self.theme, self.dir, 1)
		with Image.open(full_path) as image:
			self.assertEqual(image.getpixel((0, 0)), self.theme["canvas"]["bg"])
			self.assertEqual(image.getpixel((140, 300)), self.theme["code"]["bg"])
		with open(full_path, "rb") as f:
			first = hashlib.sha256(f.read()).hexdigest()
		R.render_slide(self.slide("int total = 0;"), self.guard, self.theme, self.dir, 1)
		with open(full_path, "rb") as f:
			self.assertEqual(hashlib.sha256(f.read()).hexdigest(), first)
		for eid in ("t", "s"):
			b = boxes[eid]
			self.assertGreaterEqual(b["x"], L.HEADER_BOX[0])
			self.assertLessEqual(b["x"] + b["w"], L.HEADER_BOX[2])
		self.assertIn("c:L1", boxes)
		self.assertLessEqual(boxes["c:L1"]["x"] + boxes["c:L1"]["w"], L.CODE_BOX[2])

	def test_real_lesson_roles_and_hidden_reveal(self):
		with open(os.path.join(ROOT, "video_engine/examples/c_loop.lesson.json"),
			encoding="utf-8") as f:
			lesson = json.load(f)
		for idx in (1, 3):
			slide = lesson["slides"][idx - 1]
			boxes, base_path, full_path = R.render_slide(slide, self.guard,
				self.theme, self.dir, idx)
			for el in slide["elements"]:
				self.assertIn(el["id"], boxes)
				panel = L.HEADER_BOX if el["type"] in ("title", "subtitle") else (
					L.CODE_BOX if el["type"] == "code" else L.CONTENT_BOX)
				for key, box in boxes.items():
					if key == el["id"] or key.startswith(el["id"] + ":"):
						self.assertGreaterEqual(box["x"], panel[0], key)
						self.assertGreaterEqual(box["y"], panel[1], key)
						self.assertLessEqual(box["x"] + box["w"], panel[2], key)
						self.assertLessEqual(box["y"] + box["h"], panel[3], key)
			if idx == 1:
				with Image.open(base_path) as base, Image.open(full_path) as full:
					diff = ImageChops.difference(base, full)
					self.assertIsNotNone(diff.crop((boxes["p1_b"]["x"],
						boxes["p1_b"]["y"], boxes["p1_b"]["x"] + boxes["p1_b"]["w"],
						boxes["p1_b"]["y"] + boxes["p1_b"]["h"])).getbbox())

	def test_long_code_line_shrinks_or_fails_explicitly(self):
		long_line = "int value = " + "a" * 110 + ";"
		boxes, _, _ = R.render_slide(self.slide(long_line), self.guard, self.theme,
			self.dir, 1)
		self.assertLessEqual(boxes["c:L1"]["x"] + boxes["c:L1"]["w"], L.CODE_BOX[2])
		with self.assertRaisesRegex(ValueError, "code.*無法放進"):
			R.render_slide(self.slide("W" * 3000), self.guard, self.theme, self.dir, 1)

	def test_warm_remains_default_and_unchanged(self):
		self.assertEqual(R.DEFAULT_THEME, "warm")
		boxes, _, full_path = R.render_slide(self.slide("int total = 0;"), self.guard,
			R.load_theme("warm"), self.dir, 1)
		self.assertIn("c:L1", boxes)
		with Image.open(full_path) as image:
			self.assertEqual(image.getpixel((0, 0)), R.load_theme("warm")["canvas"]["bg"])


if __name__ == "__main__":
	unittest.main()
