import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import render_slides as R


class TestCodeMetrics(unittest.TestCase):
	"""prompt 允許 8–16 行，但固定 42px 行距 15 行就貼齊底線、16 行溢出 42px"""

	def test_十五行以內維持原本的行距與字級(self):
		# 既有五份教材最長 15 行。這裡若變了，所有舊教材的畫面都會跟著變
		for n in range(1, 16):
			self.assertEqual(R.code_metrics(n), (R.CODE_STEP, R.CODE_SIZE), f"{n} 行")

	def test_任何行數都不能超出_CODE_BOX(self):
		for n in range(1, 41):
			step, size = R.code_metrics(n)
			bottom = R.CODE_Y0 + n * step
			self.assertLessEqual(bottom, R.CODE_BOX[3],
				f"{n} 行的底端 y={bottom} 超出 CODE_BOX 底線 {R.CODE_BOX[3]}")
			self.assertLessEqual(size, step, f"{n} 行的字級比行距大，會上下相疊")

	def test_十六行是原本會爆版的那一格(self):
		step, size = R.code_metrics(16)
		self.assertLess(step, R.CODE_STEP, "16 行必須縮行距，不然溢出 42px")
		self.assertLessEqual(R.CODE_Y0 + 16 * step, R.CODE_BOX[3])


class TestCodeBoxesInsideCard(unittest.TestCase):
	"""行號代號（p1_code:L7）的量測框是動畫的座標來源，
	跑出卡片外的話聚光燈與雷射就打在空白處"""

	def _render(self, n_lines):
		lesson = {
			"lesson_id": "t",
			"title": "t",
			"slides": [{
				"id": "p1",
				"elements": [
					{"id": "p1_title", "type": "title", "text": "測試"},
					{"id": "p1_code", "type": "code", "lang": "c",
						"lines": [f"int line_{i};" for i in range(1, n_lines + 1)]},
				],
			}],
		}
		d = tempfile.mkdtemp()
		self.addCleanup(__import__("shutil").rmtree, d, True)
		path = os.path.join(d, "t.lesson.json")
		with open(path, "w", encoding="utf-8") as f:
			json.dump(lesson, f)
		old = sys.argv
		sys.argv = ["render_slides.py", path, d]
		try:
			self.assertEqual(R.main(), 0)
		finally:
			sys.argv = old
		with open(os.path.join(d, "layout.json"), encoding="utf-8") as f:
			return json.load(f)["slides"][0]["boxes"]

	def test_二十行的每一行都關在卡片內(self):
		boxes = self._render(20)
		for i in range(1, 21):
			b = boxes[f"p1_code:L{i}"]
			self.assertGreaterEqual(b["y"], R.CODE_BOX[1], f"L{i} 跑到卡片上緣外")
			self.assertLessEqual(b["y"] + b["h"], R.CODE_BOX[3], f"L{i} 跑到卡片下緣外")


if __name__ == "__main__":
	unittest.main()
