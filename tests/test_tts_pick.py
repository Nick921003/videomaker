"""tts_f5.pick 的打分與挑選（純函式，不載入 ASR／模型）。"""
import importlib.util
import unittest

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("numpy", "soundfile", "pypinyin"))


@unittest.skipUnless(HAS_DEPS, "需要 f5 環境：~/.venvs/f5tts/bin/python -m unittest tests.test_tts_pick")
class PickTest(unittest.TestCase):
	def setUp(self):
		from tts_f5 import pick
		self.p = pick

	def test_norm_ignores_spacing_case_punct_and_digits(self):
		self.assertEqual(self.p.norm("加一行 F flush。"), self.p.norm("加一行fflush"))
		self.assertEqual(self.p.norm("輸入 85，按 Enter"), self.p.norm("輸入八十五按enter"))
		self.assertEqual(self.p.norm("「請輸入成績」"), "請輸入成績")

	def test_cer_ignores_homophones(self):
		# Paraformer 把「程式」聽成「城市」、「裡」寫成「裏」：念法一樣，不算錯
		self.assertEqual(self.p.cer("跑程式，都卡在這裡。", "跑城市都卡在這裏"), 0.0)
		self.assertGreater(self.p.cer("用 VS Code 跑程式", "用 VS Code 的跑程式"), 0.0)

	def test_cer(self):
		self.assertEqual(self.p.cer("用 VS Code 跑", "用vs code跑"), 0.0)
		self.assertAlmostEqual(self.p.cer("加一行 fflush", "加一行 s flush"), 1 / 9)
		self.assertEqual(self.p.cer("", ""), 0.0)

	def test_rise_flat_rising_falling(self):
		import numpy as np
		flat = [0] * 5 + [200] * 40 + [0] * 5
		up = [0] * 5 + list(np.linspace(200, 260, 40)) + [0] * 5
		down = [0] * 5 + list(np.linspace(220, 180, 40))
		self.assertAlmostEqual(self.p.rise_st(flat), 0.0)
		self.assertGreater(self.p.rise_st(up), 2.0)
		self.assertLess(self.p.rise_st(down), 0.0)
		self.assertEqual(self.p.rise_st([0] * 10 + [200] * 3), 0.0)

	def test_rise_uses_last_voiced_run(self):
		# 前面一段大上揚、後面一段平：只看最後一段
		import numpy as np
		f0 = list(np.linspace(150, 300, 30)) + [0] * 10 + [200] * 20
		self.assertAlmostEqual(self.p.rise_st(f0), 0.0)

	def test_choose_prefers_passing_candidates(self):
		c = [
			{"cer": 0.3, "rise": 0.0, "dev": 0.0, "gap": 0.2},   # 念錯
			{"cer": 0.0, "rise": 4.0, "dev": 0.0, "gap": 0.2},   # 句尾飄
			{"cer": 0.05, "rise": 0.5, "dev": 0.1, "gap": 0.2},  # 及格
		]
		self.assertEqual(self.p.choose(c), (2, False))

	def test_choose_question_ignores_rise(self):
		c = [{"cer": 0.1, "rise": 0.0, "dev": 0.0, "gap": 0.2}, {"cer": 0.0, "rise": 5.0, "dev": 0.0, "gap": 0.2}]
		self.assertEqual(self.p.choose(c, question=True), (1, False))
		self.assertEqual(self.p.choose(c), (0, False))

	def test_choose_all_fail_is_suspicious_but_still_picks(self):
		c = [{"cer": 0.5, "rise": 0.0, "dev": 0.0, "gap": 0.2}, {"cer": 0.3, "rise": 0.0, "dev": 0.0, "gap": 0.2}]
		self.assertEqual(self.p.choose(c), (1, True))

	def test_choose_tie_keeps_first(self):
		c = [{"cer": 0.0, "rise": 0.0, "dev": 0.0, "gap": 0.2}] * 3
		self.assertEqual(self.p.choose(c), (0, False))


if __name__ == "__main__":
	unittest.main()
