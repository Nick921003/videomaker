import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv/bin/python")


@unittest.skipUnless(os.environ.get("E2E") == "1", "設 E2E=1 才跑，會真的呼叫 LLM 與 TTS")
class TestEndToEnd(unittest.TestCase):
	def test_pptx_進去_mp4_出來(self):
		sys.path.insert(0, os.path.join(ROOT, "tests/fixtures"))
		import make_pptx
		deck = os.path.join(ROOT, "video_engine/materials/_e2e_deck.pptx")
		make_pptx.make(deck, [
			["C 語言的布林值", "C89 沒有 bool 型態", "非零即真，零為假"],
			["實務寫法", "用 int 代替", "或 include stdbool.h"],
		], {1: "重點是初學者常以為 C 有 bool，其實 C89 沒有。"})
		r = subprocess.run([PY, os.path.join(ROOT, "video_engine/run.py"), deck, "--sec", "60"],
			capture_output=True, text=True, timeout=900)
		self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
		mp4 = os.path.join(ROOT, "video_engine/out/_e2e_deck/_e2e_deck.mp4")
		self.assertTrue(os.path.exists(mp4))
		self.assertGreater(os.path.getsize(mp4), 100_000)


if __name__ == "__main__":
	unittest.main()
