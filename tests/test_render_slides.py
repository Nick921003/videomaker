import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import layout as L
import render_slides as R


class TestCodeMetrics(unittest.TestCase):
	"""prompt 允許 8–16 行，但固定 42px 行距 15 行就貼齊底線、16 行溢出 42px"""

	def test_十五行以內維持原本的行距與字級(self):
		# 既有五份教材最長 15 行。這裡若變了，所有舊教材的畫面都會跟著變
		for n in range(1, 16):
			self.assertEqual(L.code_metrics(n), (L.CODE_STEP, L.CODE_SIZE), f"{n} 行")

	def test_任何行數都不能超出_CODE_BOX(self):
		for n in range(1, 41):
			step, size = L.code_metrics(n)
			bottom = L.CODE_Y0 + n * step
			self.assertLessEqual(bottom, L.CODE_BOX[3],
				f"{n} 行的底端 y={bottom} 超出 CODE_BOX 底線 {L.CODE_BOX[3]}")
			self.assertLessEqual(size, step, f"{n} 行的字級比行距大，會上下相疊")

	def test_十六行是原本會爆版的那一格(self):
		step, size = L.code_metrics(16)
		self.assertLess(step, L.CODE_STEP, "16 行必須縮行距，不然溢出 42px")
		self.assertLessEqual(L.CODE_Y0 + 16 * step, L.CODE_BOX[3])


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
			self.assertGreaterEqual(b["y"], L.CODE_BOX[1], f"L{i} 跑到卡片上緣外")
			self.assertLessEqual(b["y"] + b["h"], L.CODE_BOX[3], f"L{i} 跑到卡片下緣外")


class TestBulletBoxMatchesRegionsFor(unittest.TestCase):
	"""layout.py 裡的 test_版位高度與繪製遞增量必須同源 只比對 layout._stack() 跟
	layout.bullet_metrics() 兩者的回傳值——兩邊現在活在同一個模組，_stack 跟 render_slide
	的繪製迴圈各自改吃不同行距來源那種歷史分歧（曾經 738 vs 768）不會被那則測試擋住。
	這裡改跑一次真正的 render_slides.main()，用量出來的實際框去比對 regions_for 的文字區域，
	才是在驗證兩個檔案真的沒有分岔，不是在複誦同一個模組的算式"""

	def _render_bullets(self, n):
		lesson = {
			"lesson_id": "t",
			"title": "t",
			"slides": [{
				"id": "p1",
				"elements": [
					{"id": "p1_title", "type": "title", "text": "測試"},
					{"id": "p1_sub", "type": "subtitle", "text": "s"},
				] + [
					{"id": f"p1_b{i}", "type": "bullet", "text": f"項目 {i}"}
					for i in range(n)
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
			boxes = json.load(f)["slides"][0]["boxes"]
		return boxes, lesson["slides"][0]

	def test_七條時最後一條的實測框落在_regions_for_的文字區域內(self):
		# 7 條是自適應 step 第一次跟舊固定常數分岔的地方（738 vs 768）
		n = 7
		boxes, sl = self._render_bullets(n)
		last = boxes[f"p1_b{n - 1}"]
		text_region = L.regions_for(sl, 0)["text"]
		self.assertGreaterEqual(last["y"], text_region["y"],
			"最後一條的框跑到 regions_for 算出的文字區域上緣外")
		self.assertLessEqual(last["y"] + last["h"], text_region["y"] + text_region["h"],
			"最後一條的框跑到 regions_for 算出的文字區域下緣外")


if __name__ == "__main__":
	unittest.main()
