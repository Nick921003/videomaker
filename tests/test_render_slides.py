import json
import os
import shutil
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import layout as L
import render_slides as R


def ink_slack(size):
	"""實測字身下緣超出「名目字高」的最大值，取代用猜的容差。

	bullet_metrics 的 +48 是平的高度預算，不是量出來的字身下緣。用同一支字型
	（跟 render_slides 畫條列同一支）真的畫幾個已知會有下伸部的字元——
	拉丁 gjpqy、全形「，」——量出墨跡框底端（anchor="la" 時 y=0 對齊字身頂，
	textbbox 的 y1 就是墨跡實際伸到多下面）超出 size 多少，取最大值"""
	font = ImageFont.truetype(R.CJK_FONT, size)
	draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
	worst = 0
	for ch in "gjpqy，":
		bottom = draw.textbbox((0, 0), ch, font=font, anchor="la")[3]
		worst = max(worst, bottom - size)
	return max(worst, 0)


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


class TestCorpusInvariants(unittest.TestCase):
	"""五份現成教材是唯一的真實樣本，每個不變量都要對它們成立"""

	LESSONS = ("c_loop", "c_string", "c_struct", "c_struct_combo", "c_struct_v3")

	def _lesson(self, name):
		with open(os.path.join(ROOT, "video_engine/examples", f"{name}.lesson.json"),
				encoding="utf-8") as f:
			return json.load(f)

	def _render(self, name):
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
		old = sys.argv
		sys.argv = ["render_slides.py",
			os.path.join(ROOT, "video_engine/examples", f"{name}.lesson.json"), d]
		try:
			self.assertEqual(R.main(), 0)
		finally:
			sys.argv = old
		with open(os.path.join(d, "layout.json"), encoding="utf-8") as f:
			return json.load(f), d

	def test_每個可定址代號都有量測框(self):
		# 只查元素 id 是不夠的：figure 的子代號（:i、:l、:r、:caption）
		# 才是動作真正指到的東西，漏掉的話這則測試會在版型改壞時仍然全綠
		for name in self.LESSONS:
			lay, _ = self._render(name)
			lesson = self._lesson(name)
			for page, sl in zip(lay["slides"], lesson["slides"]):
				bx = page["boxes"]
				for el in sl["elements"]:
					eid = el["id"]
					self.assertIn(eid, bx, f"{name} {eid}")
					if el["type"] == "code":
						for i in range(1, len(el["lines"]) + 1):
							self.assertIn(f"{eid}:L{i}", bx, f"{name} {eid}:L{i}")
					elif el["type"] == "figure":
						if el["kind"] in ("boxes", "steps"):
							for i in range(1, len(el.get("items", [])) + 1):
								self.assertIn(f"{eid}:i{i}", bx, f"{name} {eid}:i{i}")
						else:
							for j in range(1, len(el.get("left", {}).get("items", [])) + 1):
								self.assertIn(f"{eid}:l{j}", bx, f"{name} {eid}:l{j}")
							for j in range(1, len(el.get("right", {}).get("items", [])) + 1):
								self.assertIn(f"{eid}:r{j}", bx, f"{name} {eid}:r{j}")
						if el.get("caption"):
							self.assertIn(f"{eid}:caption", bx, f"{name} {eid}:caption")

	def test_所有框都在畫布內(self):
		import layout as L
		for name in self.LESSONS:
			lay, _ = self._render(name)
			for page in lay["slides"]:
				for key, b in page["boxes"].items():
					self.assertGreaterEqual(b["x"], 0, f"{name} {key}")
					self.assertGreaterEqual(b["y"], 0, f"{name} {key}")
					self.assertLessEqual(b["x"] + b["w"], L.W, f"{name} {key}")
					self.assertLessEqual(b["y"] + b["h"], L.H, f"{name} {key}")

	def test_五份教材各自連跑兩次都逐位元組相同(self):
		import hashlib

		def digest(name):
			_, d = self._render(name)
			h = hashlib.md5()
			for f in sorted(os.listdir(d)):
				if f.endswith(".png"):
					with open(os.path.join(d, f), "rb") as fh:
						h.update(fh.read())
			return h.hexdigest()

		for name in self.LESSONS:
			self.assertEqual(digest(name), digest(name), f"{name} 引入了非決定性")

	def test_條列框也要關在文字區內(self):
		# 先前的 bounds check 只查 figure 與 code 的框，從沒查過條列。
		# bullet_metrics 的 +48 是平的高度預算，不是量測出來的字身下緣——
		# 實測墨跡會溢出 0–4px 且跟內容有關（結尾是全形「，」的頁面最多）。
		# 容差要從真的字型量出來，不要猜一個數字
		import layout as L
		slack = ink_slack(L.BULLET_SIZE)      # 見上方輔助函式，實測字身下緣
		for name in self.LESSONS:
			lay, _ = self._render(name)
			lesson = self._lesson(name)
			for i, (page, sl) in enumerate(zip(lay["slides"], lesson["slides"])):
				reg = L.regions_for(sl, i)["text"]
				for el in sl["elements"]:
					if el["type"] not in ("bullet", "callout"):
						continue
					b = page["boxes"][el["id"]]
					self.assertGreaterEqual(b["y"], reg["y"] - slack,
						f"{name} {el['id']} 跑到文字區上緣外")
					self.assertLessEqual(b["y"] + b["h"], reg["y"] + reg["h"] + slack,
						f"{name} {el['id']} 跑到文字區下緣外")

	def test_條列溢出不得侵入圖區(self):
		# 上一則允許小幅溢出，這一則守的是真正要緊的事：條列的量測框不得
		# 跟圖區產生真正的矩形相交。
		#
		# 舊寫法只查 y 軸（b.y+b.h <= figure.y），隱含「文字帶永遠疊在圖區
		# 正上方」——stack／stage 兩種版型確實如此，但 split 版型是左右
		# 分欄、文字跟圖區同一個 y 帶，只是 x 不重疊。舊寫法在 split 頁上
		# 把「同 y、不同 x」的正常並排誤判成侵入，四份教材、24 個
		# （lesson, slide, element）都是假警報，x 範圍其實完全不相交。
		# 兩個矩形要「同時」在 x 軸與 y 軸都重疊才算真的相交，只查一軸守
		# 不住這個不變量，四種版型都通用的寫法才是這條測試該長的樣子
		import layout as L
		for name in self.LESSONS:
			lay, _ = self._render(name)
			lesson = self._lesson(name)
			for i, (page, sl) in enumerate(zip(lay["slides"], lesson["slides"])):
				r = L.regions_for(sl, i)
				if not r["figure"]:
					continue
				fig = r["figure"]
				for el in sl["elements"]:
					if el["type"] not in ("bullet", "callout"):
						continue
					b = page["boxes"][el["id"]]
					x_overlap = b["x"] < fig["x"] + fig["w"] and fig["x"] < b["x"] + b["w"]
					y_overlap = b["y"] < fig["y"] + fig["h"] and fig["y"] < b["y"] + b["h"]
					self.assertFalse(x_overlap and y_overlap,
						f"{name} slide={sl['id']} el={el['id']} 侵入圖區：\n"
						f"  bullet_box={b}\n  figure_region={fig}")

	def test_每份教材至少用到兩種版型(self):
		# 這輪的目的就是消除單調。四種版型全部實作了但沒有一頁走到，
		# 測試照樣全綠——這裡把「目的達成了沒有」也變成可驗的
		import layout as L
		for name in self.LESSONS:
			used = {L.pick_variant(sl) for sl in self._lesson(name)["slides"]}
			self.assertGreaterEqual(len(used), 2, f"{name} 只用到 {used}")


if __name__ == "__main__":
	unittest.main()
