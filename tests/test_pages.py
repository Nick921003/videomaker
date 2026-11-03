"""pages.py：草稿片的分頁與先畫後講；不需要 GPU，一般 .venv 就能跑。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPLAINER = os.path.join(ROOT, "video_engine", "explainer")
sys.path.insert(0, EXPLAINER)
import pages as P  # noqa: E402


def draft(n=4):
	"""story.py --dry 的形狀：n 句、每句 2 秒、句間 0.4 秒、一章，最後一句是結語"""
	lines = []
	for i in range(1, n + 1):
		a = round((i - 1) * 2.4 + 0.4, 3)
		lines.append({"i": i, "text": f"第{i}句", "start": a, "end": a + 2.0, "words": [["第", a], [str(i), a + 1.0]]})
	return {"title": "t", "duration": lines[-1]["end"] + 0.5, "narration": "audio/narration.wav", "draft": True,
		"lines": lines, "chapters": [{"key": "a", "start": 0.3, "end": lines[-1]["end"] + 0.1}],
		"end": {"line": n, "start": lines[-1]["start"]}}


class PagesTest(unittest.TestCase):
	def folder(self, story, **files):
		d = tempfile.mkdtemp()
		for name, data in dict(files, story=story).items():
			with open(os.path.join(d, name + ".json"), "w", encoding="utf-8") as f:
				json.dump(data, f, ensure_ascii=False)
		return d

	def run_cli(self, d):
		return subprocess.run([sys.executable, os.path.join(EXPLAINER, "pages.py"), d], capture_output=True, text=True)

	def read(self, d):
		return json.load(open(os.path.join(d, "story.json"), encoding="utf-8"))

	def test_pages_不碰torch(self):
		code = "import sys; sys.path.insert(0, %r); import pages; assert not {'torch', 'numpy', 'soundfile'} & set(sys.modules)" % EXPLAINER
		r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
		self.assertEqual(r.returncode, 0, r.stderr)

	def test_草稿套用(self):
		d = self.folder(draft(), pages=[[1], [2, 3]], leads={"2": 1.5}, holds={"1": 0.5})
		r = self.run_cli(d)
		self.assertEqual(r.returncode, 0, r.stderr)
		s = self.read(d)
		self.assertTrue(s["draft"])
		self.assertEqual(s["pages"], [[1], [2, 3]])
		L = {x["i"]: x for x in s["lines"]}
		self.assertEqual(L[2]["lead"], 1.5)
		self.assertEqual(L[1]["hold"], 0.5)
		self.assertEqual(L[3]["lead"], 0.0)
		# 換頁要留板擦時間，再加上一句的 hold 與這句的 lead，圖才畫得完
		self.assertAlmostEqual(L[2]["start"] - L[1]["end"], P.ERASE_GAP + 0.5 + 1.5, places=3)
		# 草稿沿用骨架估計的長度，逐字時間跟著句子平移
		self.assertAlmostEqual(L[2]["end"] - L[2]["start"], 2.0, places=3)
		self.assertAlmostEqual(L[2]["words"][0][1], L[2]["start"], places=3)
		self.assertGreaterEqual(s["duration"], s["lines"][-1]["end"])

	def test_重跑不會越疊越歪(self):
		d = self.folder(draft(), pages=[[1], [2, 3]], leads={"2": 1.5})
		self.run_cli(d)
		first = self.read(d)
		self.assertEqual(self.run_cli(d).returncode, 0)
		self.assertEqual(self.read(d), first)

	def test_非草稿拒絕(self):
		s = draft()
		s["draft"] = False
		r = self.run_cli(self.folder(s))
		self.assertNotEqual(r.returncode, 0)

	def test_沒有分頁檔就兩句一頁(self):
		s = P.apply_leads(draft(5), self.folder(draft(5)))
		self.assertEqual(s["pages"], [[1, 2], [3, 4]])
		self.assertEqual(s["screens"], [])

	def test_給實測長度就照實測排(self):
		starts = []
		s = P.apply_leads(draft(3), self.folder(draft(3), pages=[[1, 2]]), seconds=[1.0, 3.0, 2.0], starts=starts)
		self.assertEqual([round(x["end"] - x["start"], 3) for x in s["lines"]], [1.0, 3.0, 2.0])
		self.assertEqual([round(x, 3) for x in starts], [x["start"] for x in s["lines"]])


if __name__ == "__main__":
	unittest.main()
