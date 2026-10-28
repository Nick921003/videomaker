"""f5_story 的分頁與句間空檔；不載入模型。需要 f5 環境（~/.venvs/f5tts），缺套件就跳過。"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("soundfile", "torch", "torchaudio", "numpy"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def story(n, chapters, end=None):
	"""n 句、每句 1 秒、句間 0.3 秒；chapters＝[(key, 第一句, 最後一句)]"""
	lines = [{"i": i, "start": (i - 1) * 1.3, "end": (i - 1) * 1.3 + 1.0} for i in range(1, n + 1)]
	chs = [{"key": k, "start": lines[a - 1]["start"] - 0.1, "end": lines[b - 1]["end"] + 0.1} for k, a, b in chapters]
	return {"lines": lines, "chapters": chs, "end": {"line": end} if end else None}


@unittest.skipUnless(HAS_DEPS, "需要 f5 環境：~/.venvs/f5tts/bin/python -m unittest tests.test_f5_story")
class F5StoryLayoutTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		sys.path.insert(0, os.path.join(ROOT, "video_engine", "explainer"))
		import f5_story
		cls.F = f5_story

	def folder(self, pages=None, screens=None):
		d = tempfile.mkdtemp()
		for name, data in (("pages.json", pages), ("screens.json", screens)):
			if data is not None:
				with open(os.path.join(d, name), "w") as f:
					json.dump(data, f)
		return d

	def test_gap_same_page_keeps_base(self):
		self.assertEqual(self.F.gap_after(1, 2, {1: ("p", 0), 2: ("p", 0)}, 0.3), 0.3)

	def test_gap_page_change_leaves_time_for_eraser(self):
		self.assertEqual(self.F.gap_after(1, 2, {1: ("p", 0), 2: ("p", 1)}, 0.3), self.F.ERASE_GAP)
		self.assertEqual(self.F.gap_after(1, 2, {1: ("p", 0), 2: ("p", 1)}, 3.0), 3.0)

	def test_gap_to_closing_line_leaves_time_for_pan(self):
		self.assertEqual(self.F.gap_after(1, 2, {1: ("p", 0)}, 0.3), self.F.TRAVEL_GAP)

	def test_gap_into_and_out_of_screen(self):
		where = {1: ("p", 0), 2: ("s", 0), 3: ("s", 0), 4: ("p", 1)}
		self.assertEqual(self.F.gap_after(1, 2, where, 0.3), self.F.SCREEN_GAP)
		self.assertEqual(self.F.gap_after(2, 3, where, 0.3), 0.3)
		self.assertEqual(self.F.gap_after(3, 4, where, 0.3), self.F.SCREEN_GAP)

	def test_screen_lines_are_not_pages(self):
		s = story(5, [("a", 1, 2), ("b", 3, 5)])
		d = self.folder(pages=[[1, 2], [5]], screens=[{"lines": [3, 4], "kind": "vscode"}])
		pages, screens = self.F.make_pages(s, d)
		self.assertEqual(pages, [[1, 2], [5]])
		self.assertEqual(screens, [{"lines": [3, 4], "kind": "vscode"}])

	def test_pages_and_screens_must_cover_every_line_once(self):
		s = story(4, [("a", 1, 4)])
		with self.assertRaises(SystemExit):
			self.F.make_pages(s, self.folder(pages=[[1, 2], [3]], screens=[{"lines": [3, 4], "kind": "vscode"}]))

	def test_screen_must_stay_in_one_chapter(self):
		s = story(4, [("a", 1, 2), ("b", 3, 4)])
		with self.assertRaises(SystemExit):
			self.F.make_pages(s, self.folder(pages=[[1], [4]], screens=[{"lines": [2, 3], "kind": "vscode"}]))

	def test_recap_voice_starts_after_recap_and_stretches_it(self):
		# 複習頁開始後稍等再講，講完還要留時間看圖；本來就夠長就不縮
		start, end = self.F.recap_window(70.0, 78.0, 3.0)
		self.assertEqual(start, 70.0 + self.F.RECAP_LEAD)
		self.assertEqual(end, 78.0)
		start, end = self.F.recap_window(70.0, 72.0, 3.0)
		self.assertEqual(end, start + 3.0 + self.F.RECAP_TAIL)

	def test_recap_waits_for_a_page_travel_after_the_last_line(self):
		# 結語不再拉遠看全貌，直接換頁到複習頁，所以要留一般換頁的時間
		self.assertEqual(self.F.recap_start(80.0, 80.0), 80.0 + self.F.TRAVEL_GAP - 0.65)
		self.assertEqual(self.F.recap_start(90.0, 80.0), 90.0)

	def test_default_pairs_without_files(self):
		s = story(3, [("a", 1, 3)])
		self.assertEqual(self.F.make_pages(s, self.folder()), ([[1, 2], [3]], []))

	def test_holds_default_empty(self):
		self.assertEqual(self.F.load_pauses(self.folder(), "holds.json"), {})

	def test_holds_keys_become_line_numbers(self):
		d = self.folder()
		with open(os.path.join(d, "holds.json"), "w") as f:
			json.dump({"15": 1.0, "24": 1.2}, f)
		self.assertEqual(self.F.load_pauses(d, "holds.json"), {15: 1.0, 24: 1.2})

	def test_holds_reject_negative(self):
		d = self.folder()
		with open(os.path.join(d, "holds.json"), "w") as f:
			json.dump({"3": -0.5}, f)
		with self.assertRaises(SystemExit):
			self.F.load_pauses(d, "holds.json")


if __name__ == "__main__":
	unittest.main()
