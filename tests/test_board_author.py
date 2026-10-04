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
		return {"scope": {"covers": ["環境建立"]}, "stories": [{**base, **seg, "id": f"q{k}"} for k in range(n)],
			"highlight": {"stories": [f"q{k}" for k in range(min(n, 3))] if n >= 3 else ["q0", "q0", "q0"], "total_sec": 200}}

	def test_重點片要挑三到五支既有的問題(self):
		plan = self.plan(n=4)
		plan["highlight"]["stories"] = ["q0", "q9"]
		self.assertTrue(any("highlight" in p for p in BA.plan_problems(plan, MD)))

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


class TestGlossary(unittest.TestCase):
	def test_詞彙表自動把英文術語換成中文唸法(self):
		doc = {"scenes": [{"beats": [{"say": "在終端機打 gcc，系統去讀 PATH。"}, {"say": "按下 Windows 鍵"}]}]}
		BA.apply_glossary(doc, [{"term": "GCC", "say_as": "編譯器"}, {"term": "PATH", "say_as": "路徑變數"}])
		beats = doc["scenes"][0]["beats"]
		self.assertEqual(beats[0]["spoken"], "在終端機打 編譯器，系統去讀 路徑變數。")
		self.assertNotIn("spoken", beats[1])
		self.assertFalse(BA.narration_problems(doc, 1) and any("英文" in p for p in BA.narration_problems(doc, 1)))


class TestLetters(unittest.TestCase):
	def test_單獨字母自動換台灣口語唸法(self):
		doc = {"scenes": [{"beats": [{"say": "C 是編譯式語言，-o 指定檔名。"}]}]}
		BA.apply_glossary(doc, [])
		self.assertEqual(doc["scenes"][0]["beats"][0]["spoken"], "西 是編譯式語言，-o 指定檔名。")  # 貼著符號的字母是程式碼，不硬唸
		self.assertFalse(any("英文" in p for p in BA.narration_problems(doc, 1)))


class TestBudget(unittest.TestCase):
	def test_最壞情況會超過上限就拒絕呼叫(self):
		with tempfile.TemporaryDirectory() as d:
			b = BA.Budget(os.path.join(d, "usage.jsonl"), 0.10)
			b.guard("claude-opus-5-5", 1000, 1000)
			usd = b.record("scene", "claude-opus-5-5", {"in": 1000, "out": 3000, "cache_read": 0, "cache_write": 0})
			self.assertAlmostEqual(usd, (1000 * 4 + 3000 * 20) / 1e6)
			# 同樣用量：Opus 最壞 US$0.185 會超過剩餘預算，Gemini 最壞 US$0.034 不會
			with self.assertRaises(BA.BudgetExceeded):
				b.guard("claude-opus-5-5", 5000, 8000)
			b.guard("gemini-3.8-flash", 5000, 8000)


class TestMarks(unittest.TestCase):
	def scene(self, acts):
		return {"scenes": [{"id": "loop", "beats": [{"say": "x", "do": acts}]}]}

	def test_每場標註超過三個要退件(self):
		doc = self.scene([{"act": "circle", "target": "a"}, {"act": "underline", "target": "b"}, {"act": "arrow", "target": "a", "to": "b"}, {"act": "brace", "target": "c", "range": [0, 1]}])
		problems = BA.mark_problems(doc)
		self.assertEqual(len(problems), 1)
		self.assertIn("loop", problems[0])

	def test_同一物件逐列圈只算一個(self):
		doc = self.scene([{"act": "circle", "target": f"cycle:r{i}"} for i in range(4)] + [{"act": "arrow", "target": "cycle:r3", "to": "cycle:r0"}])
		self.assertEqual(BA.mark_problems(doc), [])


DOC = {"objects": [{"id": "a", "type": "note", "text": "甲"}, {"id": "b", "type": "note", "text": "乙"}],
	"scenes": [{"id": "s1", "beats": [{"say": "第一句話", "do": []}]}, {"id": "s2", "beats": [{"say": "第二句話", "do": []}]}]}


class TestPartialRepair(unittest.TestCase):
	def test_問題能對到場景(self):
		self.assertEqual(BA.problem_scenes(DOC, ["版面：t=1.0 場景 s2 的 b 在全景時字太小"]), {"s2"})
		self.assertEqual(BA.problem_scenes(DOC, ["旁白夾英文單字 ['x']，請加 spoken 改中文說法：第一句話"]), {"s1"})
		self.assertEqual(BA.problem_scenes(DOC, ["編譯失敗：s2/beat0/highlight 缺參數 line"]), {"s2"})

	def test_有任何問題對不到場景就整份重寫(self):
		self.assertIsNone(BA.problem_scenes(DOC, ["版面：t=1.0 場景 s2 的 b 字太小", "旁白 300 字約 58 秒，目標 70 秒"]))

	def test_合併只換掉回傳的場景與物件(self):
		patch = {"scenes": [{"id": "s2", "beats": [{"say": "改過的", "do": []}]}], "objects": [{"id": "b", "type": "note", "text": "丙"}, {"id": "c", "type": "note", "text": "丁"}]}
		out = BA.merge_patch(DOC, patch)
		self.assertEqual([s["id"] for s in out["scenes"]], ["s1", "s2"])
		self.assertEqual(out["scenes"][1]["beats"][0]["say"], "改過的")
		self.assertEqual(out["scenes"][0], DOC["scenes"][0])
		self.assertEqual([o["text"] for o in out["objects"]], ["甲", "丙", "丁"])
		self.assertEqual(DOC["scenes"][1]["beats"][0]["say"], "第二句話")

	def test_合併可以把一場拆成兩場(self):
		patch = {"scenes": [{"id": "s1", "beats": [{"say": "前半", "do": []}]}, {"id": "s1b", "beats": [{"say": "後半", "do": []}]}]}
		out = BA.merge_patch(DOC, patch)
		self.assertEqual([s["id"] for s in out["scenes"]], ["s1", "s1b", "s2"])

	def test_合併只有新場景時接在最後(self):
		out = BA.merge_patch(DOC, {"scenes": [{"id": "zz", "beats": []}]})
		self.assertEqual([s["id"] for s in out["scenes"]], ["s1", "s2", "zz"])

	def test_合併格式不對要報錯(self):
		with self.assertRaises(ValueError):
			BA.merge_patch(DOC, {"scenes": [{"beats": []}]})

	def test_重寫只送出問題場景並用指定的重寫模型(self):
		calls = []
		replies = [json.dumps(DOC, ensure_ascii=False), json.dumps({"scenes": [{"id": "s2", "beats": [{"say": "好了", "do": []}]}]}, ensure_ascii=False)]

		def fake(budget, stage, system, messages, target, light=False):
			calls.append((target, light, messages))
			return replies[len(calls) - 1]
		validate = lambda d: [] if d["scenes"][1]["beats"][0]["say"] == "好了" else ["版面：t=1 場景 s2 的 b 字太小"]
		orig, BA.call = BA.call, fake
		try:
			doc, repairs = BA.converse(None, "scene", "sys", "教材", validate, target="anthropic:x", repair_target="google:y", scenes_of=BA.problem_scenes)
		finally:
			BA.call = orig
		self.assertEqual(repairs, 1)
		self.assertEqual(doc["scenes"][0], DOC["scenes"][0])
		self.assertEqual([c[0] for c in calls], ["anthropic:x", "google:y"])
		self.assertTrue(calls[1][1])
		ask = calls[1][2][-1]["content"]
		self.assertIn("s2", ask)
		self.assertEqual(calls[1][2][0]["content"], "教材")


class TestRestoreTerms(unittest.TestCase):
	def test_字幕裡的人造唸法換回原名但一般用語不動(self):
		glossary = [{"term": "VS Code", "say_as": "微軟編輯器"}, {"term": "GCC", "say_as": "編譯器"}]
		doc = {"scenes": [{"beats": [{"say": "微軟編輯器也要整個重開，編譯器才找得到。"}, {"say": "清單讀好了，微軟編輯器也要重開。"}]}]}
		BA.restore_terms(doc, glossary, "教材：安裝 VS Code 與 GCC 編譯器")
		self.assertEqual(doc["scenes"][0]["beats"][0]["say"], "VS Code 也要整個重開，編譯器才找得到。")
		self.assertEqual(doc["scenes"][0]["beats"][1]["say"], "清單讀好了，VS Code 也要重開。")
		dup = {"scenes": [{"beats": [{"say": "計數迴圈 for 的括號裡"}]}]}
		BA.restore_terms(dup, [{"term": "for", "say_as": "計數迴圈"}], "教材：for 迴圈")
		self.assertEqual(dup["scenes"][0]["beats"][0]["say"], "for 的括號裡")


def op_doc(*presets):
	objs = [{"id": f"w{i}", "preset": p} for i, p in enumerate(presets)]
	scenes = [{"id": f"s{i}", "layout": {"stack": [f"w{i}"]}, "beats": [{"say": "按這裡", "do": [{"act": "show", "target": f"w{i}"}]}]} for i in range(len(presets))]
	return {"objects": objs, "scenes": scenes}


class TestScreens(unittest.TestCase):
	def test_必演畫面都有依序出現就過(self):
		need = ["win11.sys_props", "win11.env_vars", "win11.edit_env_var"]
		self.assertEqual(BA.screen_problems(op_doc("win11.search", *need), need), [])

	def test_漏了必演畫面要退件並說出是哪個(self):
		need = ["win11.sys_props", "win11.env_vars", "win11.edit_env_var"]
		problems = BA.screen_problems(op_doc("win11.sys_props", "win11.edit_env_var"), need)
		self.assertEqual(len(problems), 1)
		self.assertIn("環境變數", problems[0])

	def test_順序顛倒要退件(self):
		need = ["win11.env_vars", "win11.edit_env_var"]
		problems = BA.screen_problems(op_doc("win11.edit_env_var", "win11.env_vars"), need)
		self.assertTrue(problems and "順序" in problems[0], problems)

	def test_規劃的必演畫面要是內建樣板(self):
		self.assertEqual(BA.unknown_screens(["win11.env_vars", "win11.nope"]), ["win11.nope"])


class TestNarrationCode(unittest.TestCase):
	def beat(self, say):
		return {"scenes": [{"id": "s1", "beats": [{"say": say}]}]}

	def test_單獨字母照唸但程式符號旁的字母不硬唸(self):
		doc = BA.apply_glossary(self.beat("C 語言加上 -o 參數"), [])
		spoken = doc["scenes"][0]["beats"][0]["spoken"]
		self.assertIn("西", spoken)
		self.assertIn("-o", spoken)

	def test_唸程式符號要退件並說改講作用(self):
		doc = BA.apply_glossary(self.beat("按 Ctrl+S 存檔，再加 -o 參數"), [])
		problems = BA.narration_problems(doc, 1)
		self.assertTrue(any("程式" in p and "作用" in p for p in problems), problems)

	def test_詞彙表可以給程式符號唸法(self):
		glossary = [{"term": "-o", "say_as": "輸出檔名參數"}, {"term": "Ctrl+S", "say_as": "存檔快捷鍵"}]
		doc = BA.apply_glossary(self.beat("按 Ctrl+S 存檔，再加 -o 參數"), glossary)
		self.assertEqual(doc["scenes"][0]["beats"][0]["spoken"], "按 存檔快捷鍵 存檔，再加 輸出檔名參數 參數")

	def test_唸法撞名要退件(self):
		glossary = [{"term": "GCC", "say_as": "編譯器"}]
		doc = BA.apply_glossary(self.beat("gcc 負責呼叫編譯器，產生執行檔"), glossary)
		problems = BA.narration_problems(doc, 1, glossary)
		self.assertTrue(any("撞" in p and "gcc 負責呼叫編譯器" in p for p in problems), problems)
		ok = BA.apply_glossary(self.beat("gcc 會把程式翻成執行檔"), glossary)
		self.assertFalse(any("撞" in p for p in BA.narration_problems(ok, 1, glossary)))


class TestGlossaryPlan(unittest.TestCase):
	def test_不同用語唸成同一個要退件(self):
		plan = {"glossary": [{"term": "GCC", "say_as": "編譯器"}, {"term": "cc1", "say_as": "編譯器"}]}
		self.assertTrue(any("唸成同一個" in p for p in BA.glossary_problems(plan)))
		self.assertEqual(BA.glossary_problems({"glossary": [{"term": "GCC / gcc", "say_as": "編譯器"}]}), [])


class TestSymbolsAndRepeats(unittest.TestCase):
	def beat(self, say):
		return {"scenes": [{"id": "s1", "beats": [{"say": say}]}]}

	def test_純符號也套唸法而且長的先換(self):
		glossary = [{"term": "<", "say_as": "小於"}, {"term": "<=", "say_as": "小於等於"}, {"term": "+=", "say_as": "累加運算"}]
		doc = BA.apply_glossary(self.beat("條件寫 <= 還是 <，再用 += 加上去"), glossary)
		self.assertEqual(doc["scenes"][0]["beats"][0]["spoken"], "條件寫 小於等於 還是 小於，再用 累加運算 加上去")

	def test_唸法跟後面的字重複要退件(self):
		glossary = [{"term": "for", "say_as": "計數迴圈"}]
		doc = BA.apply_glossary(self.beat("for 迴圈的三個部分"), glossary)
		problems = BA.narration_problems(doc, 1, glossary)
		self.assertTrue(any("重複" in p for p in problems), problems)


class TestAutoFocus(unittest.TestCase):
	def test_太擠的場景開場自動推近到第一個動作(self):
		doc = {"scenes": [{"id": "arr", "beats": [{"say": "a", "do": [{"act": "show", "target": "code"}]}, {"say": "b", "do": [{"act": "brace", "target": "cells", "range": [0, 4]}, {"act": "wide"}]}]}]}
		self.assertTrue(BA.auto_focus(doc, ["版面：t=3 場景 arr 的 code 在全景時字太小：最小 14px"]))
		self.assertEqual(doc["scenes"][0]["beats"][0]["do"][-1], {"act": "focus", "target": "cells"})
		self.assertFalse(any(a["act"] == "wide" for b in doc["scenes"][0]["beats"] for a in b["do"]))
		self.assertFalse(BA.auto_focus(doc, ["版面：t=3 場景 arr 的 code 在全景時字太小：最小 14px"]))


class TestTone(unittest.TestCase):
	def test_驚嘆號只留前兩個(self):
		doc = {"scenes": [{"id": "a", "beats": [{"say": "成立！"}, {"say": "也成立！"}, {"say": "又成立！", "spoken": "又成立！"}]}]}
		BA.tone_down(doc)
		self.assertEqual([b["say"] for b in doc["scenes"][0]["beats"]], ["成立！", "也成立！", "又成立。"])
		self.assertEqual(doc["scenes"][0]["beats"][2]["spoken"], "又成立。")

	def test_重複的旁白要退件並對到場景(self):
		doc = {"scenes": [{"id": "a", "beats": [{"say": "五格的編號是零到四。"}]}, {"id": "b", "beats": [{"say": "五格的編號是零到四。"}]}]}
		problems = [p for p in BA.narration_problems(doc, 1) if "重複" in p]
		self.assertEqual(len(problems), 1)
		self.assertEqual(BA.problem_scenes(doc, problems), {"a", "b"})


class TestCrowd(unittest.TestCase):
	def test_每場最多兩個主要物件_small_note_不算(self):
		doc = {"objects": [{"id": "c", "type": "code"}, {"id": "a", "type": "cells"}, {"id": "v", "type": "vars"}, {"id": "n", "type": "note", "style": "small"}],
			"scenes": [{"id": "ok", "layout": {"stack": ["c", "a", "n"]}, "beats": []}, {"id": "bad", "layout": {"row": ["c", {"stack": ["a", "v"]}]}, "beats": []}]}
		problems = BA.crowd_problems(doc)
		self.assertEqual(len(problems), 1)
		self.assertIn("場景 bad ", problems[0])


if __name__ == "__main__":
	unittest.main()
