import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import render_video as RV


class TestSpotStyle(unittest.TestCase):
	"""壓暗只用在程式碼走讀。

	使用者實測回報：為了襯一個標題把整頁壓暗，讀起來是「畫面壞了」不是「看這裡」。
	標題、條列、示意圖項目一律走螢光筆
	"""

	def test_程式碼專用效果(self):
		self.assertEqual(RV.spot_style({"style": "code", "target": "p3_code:L4"}), "code")

	def test_其餘一律螢光筆(self):
		for target in ("p1_title", "p1_sub", "p2_a", "p2_c",
				"p2_fig:i2", "p1_fig:l1", "p1_fig:r2", "p1_fig:caption"):
			self.assertEqual(RV.spot_style({"target": target}), "highlight", target)

	def test_沒有_target_也不壓暗(self):
		self.assertEqual(RV.spot_style({}), "highlight")


class TestSpotlightPixels(unittest.TestCase):
	"""效果要用像素驗，不能只看有沒有走到那條分支——
	這個專案出過「效果實作了但畫面上什麼都沒發生」"""

	BOX = {"x": 400, "y": 300, "w": 200, "h": 100}

	def _eff(self, **kw):
		e = {"box": self.BOX, "start_ms": 0, "end_ms": 5000, "dim": 0.62}
		e.update(kw)
		return e

	def _frame(self):
		return np.full((1080, 1920, 3), 240, dtype=np.uint8)

	def _outside_mean(self, frame):
		m = np.ones(frame.shape[:2], bool)
		b = self.BOX
		m[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]] = False
		return frame[m].mean()

	def test_壓暗要真的把保留區以外變暗(self):
		f = RV.apply_spotlight(self._frame(), self._eff(), 2500, (42, 35, 28), self.BOX)
		self.assertLess(self._outside_mean(f), 240 * 0.85,
			"保留區以外沒有明顯變暗——這正是修之前的狀況（實測整片亮度全程 238-240）")

	def test_壓暗保留的是程式碼卡而非單行(self):
		# 保留區是整張程式碼卡，卡內哪幾行被強調由 apply_code_focus 處理。
		# 若這裡改成保留 eff["box"]（單行），整塊程式碼會連同頁面一起被壓暗
		import layout as L
		f = RV.apply_spotlight(self._frame(), self._eff(), 2500, (42, 35, 28), L.rect(*L.CODE_BOX))
		x0, y0, x1, y1 = L.CODE_BOX
		self.assertGreater(f[y0 + 10:y1 - 10, x0 + 10:x1 - 10].mean(), 240 * 0.95,
			"程式碼卡內部被壓暗了")

	def test_螢光筆不准動框外(self):
		f = RV.apply_highlight(self._frame(), self._eff(), 2500, (242, 217, 160))
		self.assertAlmostEqual(self._outside_mean(f), 240.0, places=3,
			msg="螢光筆只該刷目標框，動到框外就會變成整頁染色")


if __name__ == "__main__":
	unittest.main()
