import unittest

import os
import tempfile

from video_engine.explainer.sync_film import copy_components, merge_keys, merge_screens, srt


class TestSyncFilm(unittest.TestCase):
	def test_merge_keys(self):
		s = merge_keys({"lines": [{"i": 1}, {"i": 2}]}, {"2": "緩衝區"})
		self.assertNotIn("key", s["lines"][0])
		self.assertEqual(s["lines"][1]["key"], "緩衝區")

	def test_srt_cues_and_split(self):
		long = "在輸出面板跑，中間像隔了一道牆，字卡在緩衝區出不去。"
		out = srt({"lines": [
			{"text": "短句。", "start": 1.0, "end": 2.5},
			{"text": long, "start": 3.0, "end": 7.0},
		]})
		self.assertIn("1\n00:00:01,000 --> 00:00:02,500\n短句。\n", out)
		cues = [c for c in out.strip().split("\n\n")]
		self.assertEqual(len(cues), 3)
		joined = "".join(c.split("\n")[2] for c in cues[1:])
		self.assertEqual(joined, long)
		self.assertTrue(cues[2].split("\n")[1].endswith("00:00:07,000"))


	def test_merge_screens(self):
		s = merge_screens({"screens": [{"lines": [1, 2], "kind": "vscode"}, {"lines": [5], "kind": "vscode"}]},
			[{"lines": [1, 2], "kind": "vscode", "screen": {"id": "vs"}, "do": {"1": []}}])
		self.assertEqual(s["screens"][0]["screen"], {"id": "vs"})
		self.assertEqual(s["screens"][0]["do"], {"1": []})
		self.assertNotIn("screen", s["screens"][1])

	def test_copy_components(self):
		with tempfile.TemporaryDirectory() as d:
			copy_components(d)
			for rel in ("lib/components/vscode/model.js", "lib/components/vscode/paint.js", "lib/components/vscode/svg.js", "lib/kit/vscode.chalk.js", "lib/themes.js"):
				self.assertTrue(os.path.exists(os.path.join(d, rel)), rel)
			with open(os.path.join(d, "lib/themes.js"), encoding="utf-8") as f:
				js = f.read()
			self.assertIn("window.VSCODE_THEME = ", js)
			self.assertIn("window.TONES = ", js)


if __name__ == "__main__":
	unittest.main()
