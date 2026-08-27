import json
import os
import shutil
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


class TestFigureInRegion(unittest.TestCase):
	"""窄欄裡的 figure 必須改直排，而且每個項目的量測框都要留下——
	少一個，指到它的動作就靜默失效"""

	def _render(self, kind, items, n_bullets=3):
		els = [{"id": "p1_title", "type": "title", "text": "測試"}]
		for i in range(n_bullets):
			els.append({"id": f"p1_b{i}", "type": "bullet", "text": "條列"})
		els.append({"id": "p1_fig", "type": "figure", "kind": kind, "items": items})
		lesson = {"lesson_id": "t", "title": "t",
			"slides": [{"id": "p1", "elements": els}]}
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
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

	def test_每個項目都留下量測框(self):
		boxes = self._render("boxes", ["甲", "乙", "丙"])
		for i in (1, 2, 3):
			self.assertIn(f"p1_fig:i{i}", boxes)

	def test_項目都關在圖區內(self):
		import layout as L
		boxes = self._render("steps", ["甲", "乙", "丙", "丁"])
		reg = L.regions_for({"id": "p1", "elements": [
			{"id": "p1_title", "type": "title", "text": "t"},
			{"id": "p1_b0", "type": "bullet", "text": "x"},
			{"id": "p1_b1", "type": "bullet", "text": "x"},
			{"id": "p1_b2", "type": "bullet", "text": "x"},
			{"id": "p1_fig", "type": "figure", "kind": "steps",
				"items": ["甲", "乙", "丙", "丁"]}]}, 0)["figure"]
		for i in (1, 2, 3, 4):
			b = boxes[f"p1_fig:i{i}"]
			self.assertGreaterEqual(b["x"], reg["x"], f"i{i} 跑到圖區左邊外")
			self.assertLessEqual(b["x"] + b["w"], reg["x"] + reg["w"], f"i{i} 跑到圖區右邊外")
			self.assertLessEqual(b["y"] + b["h"], reg["y"] + reg["h"], f"i{i} 跑到圖區下面外")

	def test_窄欄時真的改成直排(self):
		# 直排的判準：項目之間 y 遞增而 x 相同
		boxes = self._render("boxes", ["甲", "乙", "丙"])
		a, b = boxes["p1_fig:i1"], boxes["p1_fig:i2"]
		self.assertEqual(a["x"], b["x"], "還是橫排")
		self.assertGreater(b["y"], a["y"])

	def test_compare_頁不會崩潰(self):
		# compare 分支有四處直接對 top 做整數運算，簽名改了卻沒改內文就會炸
		els = [{"id": "p1_title", "type": "title", "text": "測試"},
			{"id": "p1_b0", "type": "bullet", "text": "條列"},
			{"id": "p1_fig", "type": "figure", "kind": "compare",
				"left": {"title": "前", "items": ["甲", "乙"]},
				"right": {"title": "後", "items": ["丙"]}}]
		lesson = {"lesson_id": "t", "title": "t",
			"slides": [{"id": "p1", "elements": els}]}
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
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
		for k in ("p1_fig:l1", "p1_fig:l2", "p1_fig:r1"):
			self.assertIn(k, boxes)


class TestStageBulletCapacityGuard(unittest.TestCase):
	"""stage 版型的文字帶被 STAGE_TEXT_RATIO 封頂在內容卡四成高，但 render_slide
	的條列繪製迴圈是線性遞增、不看 reg["text"]["h"]。條列衝出封頂高度時就會畫進
	figure 區域——4 條 compare 條列正好踩線（bullets_h=408 > cap=296），這是
	prompt 規則 4 允許的合法輸入（2–4 條），不是假設情境。這裡跑真正的
	render_slides.main()，用量出來的實際框去比對 regions_for 切出的區域，
	光算 layout._stage() 的回傳值測不出繪製迴圈跟它對不對得上"""

	def _render(self, n_bullets):
		els = [{"id": "p1_title", "type": "title", "text": "測試"}]
		for i in range(n_bullets):
			els.append({"id": f"p1_b{i}", "type": "bullet", "text": f"條列 {i}"})
		els.append({"id": "p1_fig", "type": "figure", "kind": "compare",
			"left": {"title": "前", "items": ["甲"]},
			"right": {"title": "後", "items": ["乙"]}})
		lesson = {"lesson_id": "t", "title": "t",
			"slides": [{"id": "p1", "elements": els}]}
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
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

	def test_compare四條列每個量測框都在所屬區域內(self):
		n = 4
		boxes, sl = self._render(n)
		reg = L.regions_for(sl, 0)
		t = reg["text"]
		# 2px 容差：bullet_metrics 的 "+48" 是預算行高，跟 anchor="ma" 實際量出來的
		# 墨跡框（ascender 起點再往下一點才是真墨跡、外加字符本身的下沉量）有 ±2px
		# 落差，_stack／split 的既有頁面本來就有這個量級的誤差（跟這裡要修的 stage
		# 封頂溢版不是同一件事——那個是幾十到上百 px，這個是固定 2px），
		# 跟 Finding 3 的置中容差同一個量級，不在這次要修的範圍內
		INK_SLACK = 2
		for i in range(n):
			b = boxes[f"p1_b{i}"]
			self.assertGreaterEqual(b["y"], t["y"], f"p1_b{i} 跑到文字區上緣外")
			self.assertLessEqual(b["y"] + b["h"], t["y"] + t["h"] + INK_SLACK,
				f"p1_b{i} 跑到文字區下緣外，落進了 figure 區域")
		f_reg = reg["figure"]
		for k, b in boxes.items():
			if not k.startswith("p1_fig"):
				continue
			self.assertGreaterEqual(b["y"], f_reg["y"], f"{k} 跑到圖區上緣外")
			self.assertLessEqual(b["y"] + b["h"], f_reg["y"] + f_reg["h"],
				f"{k} 跑到圖區下緣外")


class TestMultiFigureStacking(unittest.TestCase):
	"""多圖頁必須依序往下排，不能互相覆蓋、也不能跑出 CONTENT_BOX——
	單圖頁沒有這個問題，它拿到的是整塊 reg["figure"]，不用跟別人搶位置。

	用 compare + boxes（不是兩個都用 boxes/steps）是刻意選擇：compare 不論寬度
	一律置中，是重現「舊版把每張圖都塞進『剩餘空間』再置中」這個缺陷
	最小、最不逼近版面極限的方式。純橫排的 boxes／steps 兩張疊在一起反而
	測不出舊版的 bug——舊版橫排本來就不置中（直接用 region["y"] 當起點），
	fig_height 對橫排算出來的高度本來就對，cursor 兩邊都不會錯。
	要用 boxes/steps 逼出這個 bug 得讓其中一張直排，但 5 項 boxes 直排要
	624px，CONTENT_BOX 只有 740px 高，扣掉間距根本放不下第二張圖——
	這正是 test_容量超出時明確失敗 要驗的情境。
	"""

	def _render(self, figs):
		els = [{"id": "p1_title", "type": "title", "text": "測試"}] + figs
		lesson = {"lesson_id": "t", "title": "t",
			"slides": [{"id": "p1", "elements": els}]}
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
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

	def test_兩個_figure_元素依序堆疊不重疊(self):
		figs = [
			{"id": "p1_figA", "type": "figure", "kind": "compare",
				"left": {"title": "前", "items": ["甲1", "甲2", "甲3"]},
				"right": {"title": "後", "items": ["乙1", "乙2", "乙3"]}},
			{"id": "p1_figB", "type": "figure", "kind": "boxes",
				"items": ["丙1", "丙2", "丙3"]},
		]
		boxes = self._render(figs)

		for k in ("p1_figA:l1", "p1_figA:l2", "p1_figA:l3",
				"p1_figA:r1", "p1_figA:r2", "p1_figA:r3"):
			self.assertIn(k, boxes, f"figA 少了 {k}")
		for i in (1, 2, 3):
			self.assertIn(f"p1_figB:i{i}", boxes, f"figB 少了 i{i}")

		def overlap(b1, b2):
			x = b1["x"] < b2["x"] + b2["w"] and b2["x"] < b1["x"] + b1["w"]
			y = b1["y"] < b2["y"] + b2["h"] and b2["y"] < b1["y"] + b1["h"]
			return x and y

		a_boxes = {k: v for k, v in boxes.items() if k.startswith("p1_figA")}
		b_boxes = {k: v for k, v in boxes.items() if k.startswith("p1_figB")}
		for ka, a in a_boxes.items():
			for kb, b in b_boxes.items():
				self.assertFalse(overlap(a, b), f"{ka} 跟 {kb} 重疊了：{a} / {b}")

		for k, b in boxes.items():
			if not k.startswith("p1_fig"):
				continue
			self.assertGreaterEqual(b["x"], 0, f"{k} 跑到畫布左邊外")
			self.assertGreaterEqual(b["y"], 0, f"{k} 跑到畫布上邊外")
			self.assertLessEqual(b["x"] + b["w"], L.W, f"{k} 跑到畫布右邊外")
			self.assertLessEqual(b["y"] + b["h"], L.H, f"{k} 跑到畫布下邊外")
			self.assertGreaterEqual(b["x"], L.CONTENT_BOX[0], f"{k} 跑到 CONTENT_BOX 左緣外")
			self.assertGreaterEqual(b["y"], L.CONTENT_BOX[1], f"{k} 跑到 CONTENT_BOX 上緣外")
			self.assertLessEqual(b["x"] + b["w"], L.CONTENT_BOX[2], f"{k} 跑到 CONTENT_BOX 右緣外")
			self.assertLessEqual(b["y"] + b["h"], L.CONTENT_BOX[3], f"{k} 跑到 CONTENT_BOX 下緣外")

	def test_容量超出時明確失敗(self):
		# 5 項 boxes 在 1760px 圖區裡放不下橫排（need=1904>1760），只能直排，
		# 直排要 624px；CONTENT_BOX 只有 740px 高，扣掉間距跟第二張圖，
		# 怎麼排都會超出卡片——這是內容量超出容量的問題，不是排版算式的問題，
		# 應該炸得響亮，不是默默把箱子畫到卡片外
		figs = [
			{"id": "p1_figA", "type": "figure", "kind": "boxes",
				"items": ["甲1", "甲2", "甲3", "甲4", "甲5"]},
			{"id": "p1_figB", "type": "figure", "kind": "steps",
				"items": ["乙1", "乙2", "乙3", "乙4"]},
		]
		els = [{"id": "p1_title", "type": "title", "text": "測試"}] + figs
		lesson = {"lesson_id": "t", "title": "t",
			"slides": [{"id": "p1", "elements": els}]}
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
		path = os.path.join(d, "t.lesson.json")
		with open(path, "w", encoding="utf-8") as f:
			json.dump(lesson, f)
		old = sys.argv
		sys.argv = ["render_slides.py", path, d]
		try:
			with self.assertRaises(ValueError):
				R.main()
		finally:
			sys.argv = old


if __name__ == "__main__":
	unittest.main()
