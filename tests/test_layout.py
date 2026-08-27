import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import layout as L


def slide(*types, kind=None, n_bullets=0, hidden=()):
	"""照 lesson.schema 的形狀捏一頁，只帶版型會用到的欄位"""
	els = [{"id": "p1_title", "type": "title", "text": "t"},
		{"id": "p1_sub", "type": "subtitle", "text": "s"}]
	for i in range(n_bullets):
		els.append({"id": f"p1_b{i}", "type": "bullet", "text": "x",
			"hidden": i in hidden})
	for t in types:
		if t == "figure":
			els.append({"id": "p1_fig", "type": "figure", "kind": kind or "boxes",
				"items": ["a", "b"]})
		elif t == "code":
			els.append({"id": "p1_code", "type": "code", "lang": "c",
				"lines": ["int a;"] * 10})
	return {"id": "p1", "elements": els}


def two_figs(n_bullets=3, hidden=()):
	"""兩張圖逼 pick_variant 選 stack：單張非 compare 圖現在走 split（見 layout.pick_variant），
	要讓 fixture 帶著 figure 又確定落在 stack 分支，只能走「圖數不等於 1」這條路"""
	sl = slide("figure", n_bullets=n_bullets, hidden=hidden)
	sl["elements"].append({"id": "p1_fig2", "type": "figure", "kind": "boxes", "items": ["a", "b"]})
	return sl


class TestRegionsStack(unittest.TestCase):
	def _regions(self, sl, index=0):
		"""regions_for 只有 split／stage 有自己的分支，其餘都吃 _stack。
		fixture 選錯分支的話，底下的斷言只是巧合成立——這裡先擋住這種漂移，
		不管日後 pick_variant 怎麼改，這個類別測的東西永遠是 _stack 本身。
		注意：code 頁的區域雖然也吃 _stack，但 variant 標籤會被覆蓋成 "code"，
		所以帶 code 元素的 fixture 不能餵進這裡——那個組合測試搬去了 TestRegionsCode"""
		r = L.regions_for(sl, index)
		self.assertEqual(r["variant"], "stack")
		return r

	def test_文字區域關在內容卡裡(self):
		r = self._regions(two_figs(n_bullets=3))
		t = r["text"]
		self.assertGreaterEqual(t["x"], L.CONTENT_BOX[0])
		self.assertGreaterEqual(t["y"], L.CONTENT_BOX[1])
		self.assertLessEqual(t["x"] + t["w"], L.CONTENT_BOX[2])
		self.assertLessEqual(t["y"] + t["h"], L.CONTENT_BOX[3])

	def test_hidden_不影響版位(self):
		# base 與 full 是同一份版位算出來的。這裡若不同，浮現時裁出來的就是錯位畫面
		a = self._regions(two_figs(n_bullets=3))
		b = self._regions(two_figs(n_bullets=3, hidden=(1, 2)))
		self.assertEqual(a, b)

	def test_stack_文字區寬度必須等於_BULLET_MAX_W(self):
		# 內容卡內寬是 1760，比 BULLET_MAX_W 寬 110px。這裡若用了內寬，
		# Task 3A 把 fit_font 上限改讀區域寬時，文字會突然可以貼到卡片邊。
		# 不能帶 figure：單張非 compare 圖會走 split，寬度就不是 BULLET_MAX_W 了
		r = self._regions(slide(n_bullets=3))
		self.assertEqual(r["text"]["w"], L.BULLET_MAX_W)

	def test_沒有程式碼的頁面_code_區域是_None(self):
		r = self._regions(two_figs(n_bullets=3))
		self.assertIsNone(r["code"])

	def test_版位高度與繪製遞增量必須同源(self):
		# _stack 與 render_slide 的繪製迴圈都改吃 bullet_metrics 的自適應
		# 行距。只改一邊的話 7 條就分歧：_stack 算 738、繪製迴圈實際走 768
		for n in (3, 7, 12):
			step, _ = L.bullet_metrics(n)
			r = self._regions(slide(n_bullets=n))
			self.assertEqual(r["text"]["h"], (n - 1) * step + 48, f"{n} 條")


class TestPickVariant(unittest.TestCase):
	def test_有程式碼一律走_code(self):
		self.assertEqual(L.pick_variant(slide("code")), "code")

	def test_compare_走_stage(self):
		self.assertEqual(L.pick_variant(slide("figure", kind="compare", n_bullets=3)), "stage")

	def test_boxes_與_steps_走_split(self):
		for k in ("boxes", "steps"):
			self.assertEqual(L.pick_variant(slide("figure", kind=k, n_bullets=3)), "split", k)

	def test_純文字頁走_stack(self):
		self.assertEqual(L.pick_variant(slide(n_bullets=3)), "stack")

	def test_多張圖退回_stack(self):
		# split 只切出一塊 figure 區域，兩張圖都從那塊的頂端起畫會完全疊在一起。
		# schema 沒限制每頁一張，只有 prompt 有——擋在這裡才擋得住
		sl = slide("figure", kind="boxes", n_bullets=2)
		sl["elements"].append({"id": "p1_fig2", "type": "figure", "kind": "steps",
			"items": ["a", "b"]})
		self.assertEqual(L.pick_variant(sl), "stack")

	def test_有_image_退回_stack(self):
		# image 是寫死座標貼上去的（render_slides 的 pos = ((W-w)//2, 320)），
		# 不吃區域。放進分欄版型會被條列壓在上面
		sl = slide(n_bullets=2)
		sl["elements"].append({"id": "p1_img", "type": "image", "src": "x.png"})
		self.assertEqual(L.pick_variant(sl), "stack")


class TestRegionsSplit(unittest.TestCase):
	def _r(self, index, n_bullets=3):
		return L.regions_for(slide("figure", kind="boxes", n_bullets=n_bullets), index)

	def test_文字與圖不重疊(self):
		for index in (0, 1):
			r = self._r(index)
			t, f = r["text"], r["figure"]
			self.assertTrue(t["x"] + t["w"] <= f["x"] or f["x"] + f["w"] <= t["x"],
				f"第 {index} 頁的文字欄與圖欄重疊了")

	def test_中溝正好六十像素(self):
		# 初稿的算式在 half 扣掉 COL_GAP 之後又在兩欄內側各扣一次 COL_PAD，
		# 中溝膨脹成 140px、每欄無故少 40px
		r = self._r(0)
		t, f = r["text"], r["figure"]
		gap = f["x"] - (t["x"] + t["w"])
		self.assertEqual(gap, L.COL_GAP)

	def test_欄寬是八一零(self):
		self.assertEqual(self._r(0)["text"]["w"], 810)

	def test_兩欄都關在內容卡裡(self):
		r = self._r(0)
		for key in ("text", "figure"):
			b = r[key]
			self.assertGreaterEqual(b["x"], L.CONTENT_BOX[0], key)
			self.assertLessEqual(b["x"] + b["w"], L.CONTENT_BOX[2], key)

	def test_兩欄的_y_也關在內容卡裡(self):
		# 上面那則只驗 x：COL_PAD 若哪天算 y 算錯，兩欄可能上下溢出內容卡卻沒有測試擋住
		r = self._r(0)
		for key in ("text", "figure"):
			b = r[key]
			self.assertGreaterEqual(b["y"], L.CONTENT_BOX[1], key)
			self.assertLessEqual(b["y"] + b["h"], L.CONTENT_BOX[3], key)

	def test_奇偶頁鏡像(self):
		# 同一堂課出現兩頁同 kind 的 figure 時（c_loop 的 p1 與 p4 都是 compare），
		# 純內容驅動會讓它們長得一樣
		self.assertLess(self._r(0)["text"]["x"], self._r(1)["text"]["x"])

	def test_文字欄靠左對齊(self):
		self.assertEqual(self._r(0)["text_align"], "left")

	def test_條列太多時降級為_stack(self):
		# 降級檢查放這裡而不是留到 Task 5：split 一啟用就需要它，
		# 中間留一個 Task 的防禦空窗沒有道理
		self.assertEqual(self._r(0, n_bullets=12)["variant"], "stack")

	def test_實際會出現的條數不會被誤降級(self):
		# prompt 規則 4 給 2–4 條，實測語料最多 3 條
		for n in (2, 3, 4):
			self.assertEqual(self._r(0, n_bullets=n)["variant"], "split", f"{n} 條")

	def test_hidden_不影響版位(self):
		a = L.regions_for(slide("figure", kind="boxes", n_bullets=3), 0)
		b = L.regions_for(slide("figure", kind="boxes", n_bullets=3, hidden=(1, 2)), 0)
		self.assertEqual(a, b)


class TestRegionsStage(unittest.TestCase):
	def _r(self, n_bullets=3):
		"""跟 TestRegionsStack 的 _regions 同一道防線：_stage 若被還原成
		無條件退回 _stack，這裡先擋住——不然底下四則斷言只是巧合成立在
		_stack 的幾何上，_stage 真退化了也測不出來"""
		r = L.regions_for(slide("figure", kind="compare", n_bullets=n_bullets), 0)
		self.assertEqual(r["variant"], "stage")
		return r

	def test_版型真的是_stage(self):
		self.assertEqual(self._r()["variant"], "stage")

	def test_文字在上_圖在下_不重疊(self):
		r = self._r()
		self.assertLessEqual(r["text"]["y"] + r["text"]["h"], r["figure"]["y"])

	def test_圖區比_split_的欄位寬(self):
		# compare 走 stage 的唯一理由就是它需要寬度
		stage = self._r()["figure"]["w"]
		split = L.regions_for(slide("figure", kind="boxes", n_bullets=3), 0)["figure"]["w"]
		self.assertGreater(stage, split)

	def test_文字帶不超過內容卡四成高(self):
		card_h = L.CONTENT_BOX[3] - L.CONTENT_BOX[1]
		self.assertLessEqual(self._r()["text"]["h"], card_h * 0.4)

	def test_圖區關在內容卡裡(self):
		f = self._r()["figure"]
		self.assertGreaterEqual(f["x"], L.CONTENT_BOX[0])
		self.assertLessEqual(f["x"] + f["w"], L.CONTENT_BOX[2])
		self.assertLessEqual(f["y"] + f["h"], L.CONTENT_BOX[3])


class TestRegionsCode(unittest.TestCase):
	def test_版型與區域都要對(self):
		# 光測 code_metrics／code_top 是不夠的：regions_for 對 code 頁
		# 回傳錯結構或根本沒實作，那兩個函式照樣是綠的
		r = L.regions_for(slide("code"), 0)
		self.assertEqual(r["variant"], "code")
		self.assertEqual(r["code"], L.rect(*L.CODE_BOX))
		self.assertIsNone(r["figure"])

	def test_程式碼整塊垂直置中(self):
		step, _ = L.code_metrics(10)
		top = L.code_top(10)
		above = top - L.CODE_BOX[1]
		below = L.CODE_BOX[3] - (top + 10 * step)
		self.assertLessEqual(abs(above - below), 2, "上下留白差超過 2px 就不算置中")

	def test_置中後仍不溢出(self):
		for n in range(1, 41):
			step, _ = L.code_metrics(n)
			top = L.code_top(n)
			self.assertGreaterEqual(top, L.CODE_BOX[1], f"{n} 行")
			self.assertLessEqual(top + n * step, L.CODE_BOX[3], f"{n} 行")
			# 光測不溢出擋不住 code_top 被還原成固定 CODE_Y0：code_metrics 的
			# 行距封頂本來就保證不溢出，跟有沒有置中無關。這裡才是真的在測
			# 置中——上下留白要接近，不是只测有沒有超出底線
			above = top - L.CODE_BOX[1]
			below = L.CODE_BOX[3] - (top + n * step)
			self.assertLessEqual(abs(above - below), 2, f"{n} 行的上下留白差超過 2px，不算置中")


if __name__ == "__main__":
	unittest.main()
