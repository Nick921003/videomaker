import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import layout as L
import render_slides as R


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


class TestRegionsStack(unittest.TestCase):
	def test_文字區域關在內容卡裡(self):
		r = L.regions_for(slide("figure", n_bullets=3), 0)
		t = r["text"]
		self.assertGreaterEqual(t["x"], L.CONTENT_BOX[0])
		self.assertGreaterEqual(t["y"], L.CONTENT_BOX[1])
		self.assertLessEqual(t["x"] + t["w"], L.CONTENT_BOX[2])
		self.assertLessEqual(t["y"] + t["h"], L.CONTENT_BOX[3])

	def test_hidden_不影響版位(self):
		# base 與 full 是同一份版位算出來的。這裡若不同，浮現時裁出來的就是錯位畫面
		a = L.regions_for(slide("figure", n_bullets=3), 0)
		b = L.regions_for(slide("figure", n_bullets=3, hidden=(1, 2)), 0)
		self.assertEqual(a, b)

	def test_stack_文字區寬度必須等於_BULLET_MAX_W(self):
		# 內容卡內寬是 1760，比 BULLET_MAX_W 寬 110px。這裡若用了內寬，
		# Task 3A 把 fit_font 上限改讀區域寬時，文字會突然可以貼到卡片邊
		r = L.regions_for(slide("figure", n_bullets=3), 0)
		self.assertEqual(r["text"]["w"], L.BULLET_MAX_W)

	def test_沒有程式碼的頁面_code_區域是_None(self):
		self.assertIsNone(L.regions_for(slide("figure", n_bullets=3), 0)["code"])

	def test_有程式碼的頁面_code_區域等於_CODE_BOX(self):
		r = L.regions_for(slide("code"), 0)
		self.assertEqual(r["code"], L.rect(*L.CODE_BOX))

	def test_文字區塊高度與繪製迴圈實際消耗一致(self):
		# render_slides 的條列迴圈固定以 BULLET_STEP（120）遞增，不理會
		# bullet_metrics 的自適應行距。regions_for 算區塊高度時若改用
		# bullet_metrics 的 step，7 條起兩邊就分歧：738（自適應 115px 行距）
		# vs 768（render_slides 實際消耗的 120px 行距）。12 條分歧更大。
		# 3 條落在分歧點之前，兩種算法本來就同值，用來確認測試本身沒寫錯
		for n in (3, 7, 12):
			r = L.regions_for(slide(n_bullets=n), 0)
			consumed = (n - 1) * R.BULLET_STEP + 48
			self.assertEqual(r["text"]["h"], consumed, f"{n} 條")


if __name__ == "__main__":
	unittest.main()
