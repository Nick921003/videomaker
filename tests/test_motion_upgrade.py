import json
import os
import shutil
import subprocess
import tempfile
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

from compile_timeline import intro_for
import render_video as RV
from motion import INTRO_TOTAL_MS


class TestHookIntroMetadata(unittest.TestCase):
	def test_首張_hook_只取實測標題框(self):
		slide = {"role": "hook", "elements": [
			{"id": "p1_title", "type": "title"},
			{"id": "p1_sub", "type": "subtitle"},
			{"id": "p1_body", "type": "bullet"},
		]}
		boxes = {
			"p1_title": {"x": 80, "y": 80, "w": 120, "h": 45},
			"p1_sub": {"x": 100, "y": 150, "w": 100, "h": 25},
			"p1_body": {"x": 100, "y": 350, "w": 400, "h": 50},
		}
		self.assertEqual(intro_for(slide, boxes, 0), {
			"start_ms": 0, "title": boxes["p1_title"], "subtitle": boxes["p1_sub"],
		})

	def test_非_hook_或缺標題框不產生_intro(self):
		slide = {"role": "concept", "elements": [{"id": "t", "type": "title"}]}
		self.assertIsNone(intro_for(slide, {"t": {"x": 0, "y": 0, "w": 10, "h": 10}}, 1000))
		slide["role"] = "hook"
		self.assertIsNone(intro_for(slide, {}, 0))


class TestTimelineTheme(unittest.TestCase):
	def test_影片時間線沿用實際繪製的主題(self):
		fixture = os.path.join(ROOT, "tests", "fixtures", "regression", "c_struct")
		with tempfile.TemporaryDirectory() as out:
			shutil.copy(os.path.join(fixture, "durations.json"), out)
			with open(os.path.join(fixture, "layout.json"), encoding="utf-8") as fh:
				layout = json.load(fh)
			layout["theme"] = "lecture"
			with open(os.path.join(out, "layout.json"), "w", encoding="utf-8") as fh:
				json.dump(layout, fh)
			cmd = [sys.executable, os.path.join(ROOT, "video_engine", "compile_timeline.py"),
				os.path.join(ROOT, "video_engine", "examples", "c_struct.lesson.json"),
				os.path.join(ROOT, "video_engine", "examples", "c_struct.actions.json"), out]
			proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
			self.assertEqual(proc.returncode, 0, proc.stderr)
			with open(os.path.join(out, "timeline.json"), encoding="utf-8") as fh:
				timeline = json.load(fh)
			self.assertEqual(timeline["theme"], "lecture")


class TestIntroPixels(unittest.TestCase):
	def test_起終點及影響區域(self):
		full = np.full((220, 240, 3), 245, dtype=np.uint8)
		full[90:108, 110:170] = (20, 20, 20)
		full[155:167, 120:160] = (70, 40, 30)
		intro = {"start_ms": 0,
			"title": {"x": 110, "y": 90, "w": 60, "h": 18},
			"subtitle": {"x": 120, "y": 155, "w": 40, "h": 12}}
		clean = np.full_like(full, 245)
		start = RV.apply_intro(full.copy(), full, intro, 0, (245, 245, 245))
		self.assertTrue(np.array_equal(start, clean))
		mid = RV.apply_intro(full.copy(), full, intro, 300, (245, 245, 245))
		self.assertFalse(np.array_equal(mid, start))
		self.assertFalse(np.array_equal(mid, full))
		end = RV.apply_intro(full.copy(), full, intro, INTRO_TOTAL_MS, (245, 245, 245))
		self.assertTrue(np.array_equal(end, full))
		outside = np.ones(full.shape[:2], bool)
		outside[74:108, 110:170] = False
		outside[145:167, 120:160] = False
		self.assertTrue(np.array_equal(mid[outside], full[outside]))


class TestSurfaceTransitionPixels(unittest.TestCase):
	def test_新舊內容在時間上完全分開(self):
		old = np.full((12, 160, 3), (20, 30, 40), dtype=np.uint8)
		new = np.full((12, 160, 3), (220, 210, 200), dtype=np.uint8)
		surface = np.full((12, 160, 3), (100, 110, 120), dtype=np.uint8)
		self.assertTrue(np.array_equal(RV.dip_to_surface(old, new, surface, 0), old))
		self.assertTrue(np.array_equal(RV.dip_to_surface(old, new, surface, 0.5), surface))
		self.assertTrue(np.array_equal(RV.dip_to_surface(old, new, surface, 1), new))
		out = RV.dip_to_surface(old, new, surface, 0.25)
		incoming = RV.dip_to_surface(old, new, surface, 0.75)
		self.assertTrue(np.all(out >= old))
		self.assertTrue(np.all(out <= surface))
		self.assertTrue(np.all(incoming >= surface))
		self.assertTrue(np.all(incoming <= new))


if __name__ == "__main__":
	unittest.main()
