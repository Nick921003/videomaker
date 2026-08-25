import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv/bin/python")


class TestJsonEvents(unittest.TestCase):
	def test_帶旗標時_stderr_是每行一則_JSON(self):
		# 只跑到 slides，不呼叫 LLM：lesson 階段用既有的 examples 當快取跳過
		r = subprocess.run(
			[PY, os.path.join(ROOT, "video_engine/run.py"),
				os.path.join(ROOT, "video_engine/materials/c_string.md"),
				"--from", "slides", "--until", "slides", "--json-events"],
			capture_output=True, text=True)
		self.assertEqual(r.returncode, 0, r.stderr)
		events = [json.loads(l) for l in r.stderr.splitlines() if l.startswith("{")]
		kinds = [(e["event"], e["stage"]) for e in events]
		self.assertIn(("stage_start", "slides"), kinds)
		self.assertIn(("stage_end", "slides"), kinds)
		end = next(e for e in events if e["event"] == "stage_end")
		self.assertIsInstance(end["sec"], float)

	def test_不帶旗標時_stderr_沒有_JSON(self):
		r = subprocess.run(
			[PY, os.path.join(ROOT, "video_engine/run.py"),
				os.path.join(ROOT, "video_engine/materials/c_string.md"),
				"--from", "slides", "--until", "slides"],
			capture_output=True, text=True)
		self.assertEqual(r.returncode, 0, r.stderr)
		self.assertNotIn('{"event"', r.stderr)


if __name__ == "__main__":
	unittest.main()
