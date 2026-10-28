import unittest

from video_engine.explainer.sync_film import merge_keys, srt


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


if __name__ == "__main__":
	unittest.main()
