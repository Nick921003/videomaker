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
		segs[0]["text"] = "改過的講稿內容"
		write_segments(self.actions, segs)
		self.assertEqual(read_segments(self.actions)[0]["text"], "改過的講稿內容")
		with open(ACTIONS, encoding="utf-8") as f:
			before = json.load(f)
		with open(self.actions, encoding="utf-8") as f:
			after = json.load(f)
		self.assertEqual(len(before["slides"]), len(after["slides"]))
		for b, a in zip(before["slides"], after["slides"]):
			self.assertEqual(len(b["actions"]), len(a["actions"]))
			self.assertEqual([x["type"] for x in b["actions"]], [x["type"] for x in a["actions"]])

	def test_原稿重驗要通過(self):
		self.assertEqual(revalidate(LESSON, self.actions, None), [])

	def test_改成唸函式名要被擋(self):
		segs = read_segments(self.actions)
		segs[0]["text"] = "我們用 strcpy 把字串複製過去"
		write_segments(self.actions, segs)
		errs = revalidate(LESSON, self.actions, None)
		self.assertTrue(any("strcpy" in e for e in errs), errs)


if __name__ == "__main__":
	unittest.main()
