import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(ROOT, "video_engine", "board")
sys.path.insert(0, BOARD)

import author as BA

with open(os.path.join(BOARD, "examples", "env_setup.md"), encoding="utf-8") as f:
	MD = f.read()


class TestMaterial(unittest.TestCase):
	def test_學習目標取自教材編號清單(self):
		obj = BA.objectives_of(MD)
		self.assertEqual(len(obj), 7)
		self.assertIn("編輯器", obj[0])

	def test_依標題取出段落且不含下一個同級標題(self):
		sec = BA.section(MD, "2.2.1 PATH 是什麼？為什麼需要設定它？")
		self.assertTrue(sec.startswith("#### 2.2.1"))
		self.assertIn("依序到 PATH 清單", sec)
		self.assertNotIn("2.2.2 Windows", sec)


class TestPlanGate(unittest.TestCase):
	def plan(self, n=1, **seg):
		base = {"id": "q1", "question": "為什麼打 gcc 說找不到？", "title": "t", "objectives": [1, 2, 3, 4, 5, 6, 7], "sec": 60, "after": [], "sources": ["2.2.1 PATH 是什麼？為什麼需要設定它？"]}
		return {"scope": {"covers": ["環境建立"]}, "stories": [{**base, **seg, "id": f"q{k}"} for k in range(n)]}

	def test_超過十支要求合併(self):
		self.assertTrue(any("太碎" in p for p in BA.plan_problems(self.plan(n=11), MD)))

	def test_引用區塊裡的標題也認得(self):
		self.assertEqual(BA.plan_problems(self.plan(sources=["macOS"]), MD), [])

	def test_合格計畫沒有問題(self):
		self.assertEqual(BA.plan_problems(self.plan(), MD), [])

	def test_覆蓋閘抓到漏掉的學習目標(self):
		self.assertTrue(any("覆蓋閘" in p for p in BA.plan_problems(self.plan(objectives=[1, 2]), MD)))

	def test_來源標題必須逐字存在(self):
		self.assertTrue(any("sources" in p for p in BA.plan_problems(self.plan(sources=["PATH 是什麼"]), MD)))

	def test_片長要在40到90秒(self):
		self.assertTrue(any("sec" in p for p in BA.plan_problems(self.plan(sec=120), MD)))


class TestNarrationGate(unittest.TestCase):
	def doc(self, *says):
		return {"scenes": [{"beats": [{"say": s} if isinstance(s, str) else s for s in says]}]}

	def test_逐字母縮寫要求改spoken(self):
		probs = BA.narration_problems(self.doc("輸入 GCC 指令" + "很" * 300), 60)
		self.assertTrue(any("縮寫" in p for p in probs))
		ok = BA.narration_problems(self.doc({"say": "輸入 GCC 指令", "spoken": "輸入編譯器指令"}, "很" * 300), 60)
		self.assertFalse(any("縮寫" in p for p in ok))

	def test_旁白長度偏離目標要增刪(self):
		self.assertTrue(any("目標" in p for p in BA.narration_problems(self.doc("太短了"), 60)))
		self.assertFalse(any("目標" in p for p in BA.narration_problems(self.doc("很" * 312), 60)))


class TestBudget(unittest.TestCase):
	def test_最壞情況會超過上限就拒絕呼叫(self):
		with tempfile.TemporaryDirectory() as d:
			b = BA.Budget(os.path.join(d, "usage.jsonl"), 0.10)
			b.guard(1000, 1000)
			usd = b.record("scene", {"in": 1000, "out": 3000, "cache_read": 0, "cache_write": 0})
			self.assertAlmostEqual(usd, (1000 * 4 + 3000 * 20) / 1e6)
			with self.assertRaises(BA.BudgetExceeded):
				b.guard(10000, 12000)


if __name__ == "__main__":
	unittest.main()
