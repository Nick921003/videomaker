"""節奏驗證：可觀察的文字密度與語音／聚焦結構。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))
from validate import check_slide, load_lesson, spoken_lines


def index_for(elements):
	with tempfile.TemporaryDirectory() as tmp:
		path = os.path.join(tmp, "lesson.json")
		with open(path, "w", encoding="utf-8") as f:
			json.dump({"slides": [{"id": "p1", "elements": elements}]}, f)
		return load_lesson(path)["p1"]


def actions(*items):
	return {"slide_id": "p1", "actions": list(items)}


class TestPacingProfiles(unittest.TestCase):
	def test_圖中文字計入密度但程式碼不計入(self):
		idx = index_for([
			{"id": "title", "type": "title", "text": "標題"},
			{"id": "fig", "type": "figure", "kind": "compare",
				"left": {"title": "左邊", "items": ["甲乙"]},
				"right": {"title": "右邊", "items": ["丙丁"]}},
			{"id": "code", "type": "code", "lines": ["x" * 200]},
		])
		self.assertEqual(idx["display_chars"], 10)

	def test_高密度只警告且依觀眾程度調整(self):
		idx = index_for([{"id": "title", "type": "title", "text": "教" * 145}])
		slide = actions({"type": "speech", "text": "第一段"},
			{"type": "spotlight", "target": "title"},
			{"type": "speech", "text": "第二段"})
		general_errs, general_warns = check_slide(slide, idx)
		advanced_errs, advanced_warns = check_slide(slide, idx, audience_level="advanced")
		self.assertEqual(general_errs, [])
		self.assertEqual(advanced_errs, [])
		self.assertTrue(any("畫面文字" in w and "145" in w for w in general_warns))
		self.assertFalse(any("畫面文字" in w for w in advanced_warns))

	def test_單段旁白長度隨程度調整(self):
		idx = index_for([{"id": "title", "type": "title", "text": "標題"}])
		slide = actions({"type": "speech", "text": "講" * 62},
			{"type": "spotlight", "target": "title"},
			{"type": "speech", "text": "完"})
		_, begin_warns = check_slide(slide, idx, audience_level="beginner")
		_, general_warns = check_slide(slide, idx)
		self.assertTrue(any("單段講稿" in w for w in begin_warns))
		self.assertFalse(any("單段講稿" in w for w in general_warns))


class TestFocusAlignment(unittest.TestCase):
	def test_中文行號範圍展開且奇怪字串不使驗證崩潰(self):
		self.assertEqual(spoken_lines("第十行到第十三行，再看第 5 行"), {5, 10, 11, 12, 13})
		self.assertEqual(spoken_lines("第一二行"), set())

	def test_hidden_尚未揭露就聚焦是錯誤(self):
		idx = index_for([{"id": "b", "type": "bullet", "text": "重點", "hidden": True}])
		slide = actions({"type": "spotlight", "target": "b"},
			{"type": "speech", "text": "先講重點"},
			{"type": "reveal", "target": "b"},
			{"type": "speech", "text": "再講一次"})
		errs, _ = check_slide(slide, idx)
		self.assertTrue(any("尚未 reveal" in e and "b" in e for e in errs))

	def test_hidden_先揭露再聚焦可行(self):
		idx = index_for([{"id": "b", "type": "bullet", "text": "重點", "hidden": True}])
		slide = actions({"type": "reveal", "target": "b"},
			{"type": "spotlight", "target": "b"},
			{"type": "speech", "text": "第一段"},
			{"type": "speech", "text": "第二段"})
		errs, _ = check_slide(slide, idx)
		self.assertFalse(any("尚未 reveal" in e for e in errs))

	def test_口播行號落在聚焦範圍內(self):
		idx = index_for([{"id": "code", "type": "code", "lines": ["x"] * 15}])
		slide = actions({"type": "spotlight", "target": "code:L10-L13"},
			{"type": "speech", "text": "第十行到第十三行一起看"},
			{"type": "speech", "text": "這段是重點"})
		_, warns = check_slide(slide, idx)
		self.assertFalse(any("口播行號" in w for w in warns))

	def test_口播行號與聚焦不同會警告(self):
		idx = index_for([{"id": "code", "type": "code", "lines": ["x"] * 15}])
		slide = actions({"type": "laser", "target": "code:L5"},
			{"type": "speech", "text": "第六行宣告變數"},
			{"type": "speech", "text": "這段是重點"})
		_, warns = check_slide(slide, idx)
		self.assertTrue(any("口播行號" in w and "6" in w for w in warns))

	def test_沒有明確行號不猜測語意(self):
		idx = index_for([{"id": "code", "type": "code", "lines": ["x"] * 15}])
		slide = actions({"type": "laser", "target": "code:L5"},
			{"type": "speech", "text": "先宣告變數"},
			{"type": "speech", "text": "然後輸出"})
		_, warns = check_slide(slide, idx)
		self.assertFalse(any("口播行號" in w for w in warns))


class TestCLI(unittest.TestCase):
	def test_接受程度參數且拒絕未知程度(self):
		with tempfile.TemporaryDirectory() as tmp:
			lesson = os.path.join(tmp, "lesson.json")
			act = os.path.join(tmp, "actions.json")
			with open(lesson, "w", encoding="utf-8") as f:
				json.dump({"slides": [{"id": "p1", "elements": [
					{"id": "t", "type": "title", "text": "標題"}]}]}, f)
			with open(act, "w", encoding="utf-8") as f:
				json.dump({"slides": [actions({"type": "speech", "text": "第一段"},
					{"type": "spotlight", "target": "t"},
					{"type": "speech", "text": "第二段"})]}, f)
			cmd = [sys.executable, os.path.join(ROOT, "video_engine", "validate.py"), lesson, act]
			ok = subprocess.run(cmd + ["--audience", "beginner"], capture_output=True, text=True)
			legacy = subprocess.run(cmd + ["30"], capture_output=True, text=True)
			bad = subprocess.run(cmd + ["--audience", "unknown"], capture_output=True, text=True)
			self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
			self.assertIn("beginner", ok.stdout)
			self.assertEqual(legacy.returncode, 0, legacy.stdout + legacy.stderr)
			self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
	unittest.main()
