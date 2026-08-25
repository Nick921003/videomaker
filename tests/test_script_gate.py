import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from script_gate import read_segments, revalidate, write_segments

LESSON = os.path.join(ROOT, "video_engine/examples/c_string.lesson.json")
ACTIONS = os.path.join(ROOT, "video_engine/examples/c_string.actions.json")


class TestScriptGate(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, self.dir)
		self.actions = os.path.join(self.dir, "a.json")
		shutil.copy(ACTIONS, self.actions)

	def test_抽出所有_speech_段落(self):
		segs = read_segments(self.actions)
		self.assertTrue(len(segs) >= 10)
		self.assertTrue(all(set(s) == {"slide_id", "idx", "text"} for s in segs))
		with open(ACTIONS, encoding="utf-8") as f:
			raw = json.load(f)
		total = sum(1 for s in raw["slides"] for a in s["actions"] if a["type"] == "speech")
		self.assertEqual(len(segs), total)

	def test_回寫後文字有變且其他欄位不動(self):
		segs = read_segments(self.actions)
		edited = segs[0]
		edited["text"] = "改過的講稿內容"
		write_segments(self.actions, segs)
		self.assertEqual(read_segments(self.actions)[0]["text"], "改過的講稿內容")

		# 深度比對：把同一筆編輯套到記憶體裡的原始結構，兩邊逐欄位相等，
		# 才抓得出「非 text 欄位被動到」，不會只靠數量和 type 序列漏看
		with open(ACTIONS, encoding="utf-8") as f:
			expected = json.load(f)
		for slide in expected["slides"]:
			if slide["slide_id"] == edited["slide_id"]:
				slide["actions"][edited["idx"]]["text"] = edited["text"]
				break
		with open(self.actions, encoding="utf-8") as f:
			after = json.load(f)
		self.assertEqual(after, expected)

	def test_原稿重驗要通過(self):
		self.assertEqual(revalidate(LESSON, self.actions, None), [])

	def test_改成唸函式名要被擋(self):
		segs = read_segments(self.actions)
		segs[0]["text"] = "我們用 strcpy 把字串複製過去"
		write_segments(self.actions, segs)
		errs = revalidate(LESSON, self.actions, None)
		self.assertTrue(any("strcpy" in e for e in errs), errs)

	def test_驗證器本身炸掉要丟例外而不是回報通過(self):
		# lesson_path 打錯路徑，load_lesson 會在印任何東西之前就丟例外，
		# stdout 是空的——驗證器必須被判定成沒跑完，不能被當成「通過」
		bad_lesson = os.path.join(self.dir, "not_exist.lesson.json")
		with self.assertRaises(RuntimeError):
			revalidate(bad_lesson, self.actions, None)


if __name__ == "__main__":
	unittest.main()
