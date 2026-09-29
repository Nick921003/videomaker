import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import render_video as RV
import motion as M


class TestSpotStyle(unittest.TestCase):
	"""壓暗只用在程式碼走讀。

	使用者實測回報：為了襯一個標題把整頁壓暗，讀起來是「畫面壞了」不是「看這裡」。
	標題、條列、示意圖項目一律走螢光筆
	"""

	def test_程式碼專用效果(self):
		self.assertEqual(RV.spot_style({"style": "code", "target": "p3_code:L4"}), "code")

	def test_其餘一律同一種聚焦記號(self):
		for target in ("p1_title", "p1_sub", "p2_a", "p2_c",
				"p2_fig:i2", "p1_fig:l1", "p1_fig:r2", "p1_fig:caption"):
			self.assertEqual(RV.spot_style({"target": target}), "focus", target)

	def test_沒有_target_也不壓暗(self):
		self.assertEqual(RV.spot_style({}), "focus")


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

	def test_聚焦記號不改目標文字像素(self):
		original = self._frame()
		b = self.BOX
		original[b["y"] + 20:b["y"] + 50, b["x"] + 20:b["x"] + 160] = (22, 44, 60)
		f = RV.apply_focus_mark(original.copy(), self._eff(), 2500, (160, 90, 162))
		self.assertTrue(np.array_equal(
			f[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]],
			original[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]]))

	def test_聚焦記號在目標框外且其他區域不變(self):
		original = self._frame()
		f = RV.apply_focus_mark(original.copy(), self._eff(), 2500, (160, 90, 162))
		b = self.BOX
		self.assertFalse(np.array_equal(
			f[b["y"] + 10:b["y"] + b["h"] - 10, b["x"] - 14:b["x"] - 8],
			original[b["y"] + 10:b["y"] + b["h"] - 10, b["x"] - 14:b["x"] - 8]))
		self.assertTrue(np.array_equal(f[0:100, 0:100], original[0:100, 0:100]))

	def test_雷射與聚光燈使用相同聚焦記號(self):
		original = self._frame()
		laser = RV.apply_focus_mark(original.copy(), self._eff(type="laser"), 2500, (160, 90, 162))
		spotlight = RV.apply_focus_mark(original.copy(), self._eff(type="spotlight"), 2500, (160, 90, 162))
		self.assertTrue(np.array_equal(laser, spotlight))


class TestThemeFocusContrast(unittest.TestCase):
	@staticmethod
	def _luminance(hex_color):
		channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
		linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
			for c in channels]
		return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722)))

	@classmethod
	def _contrast(cls, a, b):
		la, lb = cls._luminance(a), cls._luminance(b)
		return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)

	def test_lecture_聚焦軌在淺底和程式深底都清楚(self):
		th = RV.load_theme("lecture")
		fx = th["effects"]
		self.assertGreaterEqual(self._contrast(fx["focus"], th["card"]["fill"]), 3.0)
		self.assertGreaterEqual(self._contrast(fx["focus_on_dark"], th["code"]["bg"]), 3.0)


class TestExplainerTransition(unittest.TestCase):
	def test_場景式過場不畫固定卡片(self):
		canvas = {"width": 1920, "height": 1080}
		th = RV.load_theme("explainer")
		frame = RV.transition_surface(canvas, th, "explainer")
		expected = np.array(RV.rgb(th["canvas"]["bg"]), dtype=np.uint8)
		self.assertTrue(np.all(frame == expected))


class TestUnifiedFocusTiming(unittest.TestCase):
	def test_聚光與雷射使用相同聚焦入場時間(self):
		self.assertEqual(M.enter_ms({"type": "spotlight", "style": "text"}),
			M.enter_ms({"type": "laser"}))


class TestSemanticFocusPixels(unittest.TestCase):
	BOX = {"x": 45, "y": 35, "w": 220, "h": 110}

	def _frame(self):
		frame = np.full((200, 360, 3), 245, dtype=np.uint8)
		frame[65:100, 70:235] = (22, 48, 59)
		return frame

	def _effect(self, shape):
		return {"box": self.BOX, "focus_shape": shape, "start_ms": 0, "end_ms": 3000}

	def test_text_underline_appears_below_glyphs_and_draws_progressively(self):
		original = self._frame()
		partial = RV.apply_semantic_focus(original.copy(), self._effect("underline"), 55, (160, 90, 162))
		full = RV.apply_semantic_focus(original.copy(), self._effect("underline"), 700, (160, 90, 162))
		self.assertTrue(np.array_equal(full[65:100, 70:235], original[65:100, 70:235]))
		self.assertTrue(np.array_equal(full[0:25, :], original[0:25, :]))
		self.assertGreater(np.count_nonzero(full != original), np.count_nonzero(partial != original))
		self.assertGreater(np.count_nonzero(full[130:145] != original[130:145]), 0)

	def test_figure_outline_encircles_without_covering_content(self):
		original = self._frame()
		partial = RV.apply_semantic_focus(original.copy(), self._effect("outline"), 55, (160, 90, 162))
		full = RV.apply_semantic_focus(original.copy(), self._effect("outline"), 700, (160, 90, 162))
		self.assertTrue(np.array_equal(full[65:100, 70:235], original[65:100, 70:235]))
		self.assertTrue(np.array_equal(full[0:25, :], original[0:25, :]))
		self.assertGreater(np.count_nonzero(full != original), np.count_nonzero(partial != original))
		self.assertGreater(np.count_nonzero(full[35:145, 45:265] != original[35:145, 45:265]), 0)


if __name__ == "__main__":
	unittest.main()
