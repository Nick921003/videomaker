import json
import os
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(ROOT, "video_engine", "board")
sys.path.insert(0, BOARD)

import build as BB
import compile as BC

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


class TestBuild(unittest.TestCase):
	def test_產出目錄自給自足且帶主題與目錄(self):
		with open(os.path.join(BOARD, "examples", "c_string.scene.json"), encoding="utf-8") as f:
			tl = BC.compile_scene(json.load(f), None, BC.load_catalog())
		with tempfile.TemporaryDirectory() as d:
			BB.build(tl, d)
			for rel in ("player.html", "board_data.js", "runtime/core.js", "runtime/layout.js", "runtime/player.js", "runtime/components/note.js"):
				self.assertTrue(os.path.exists(os.path.join(d, rel)), rel)
			with open(os.path.join(d, "player.html"), encoding="utf-8") as f:
				page = f.read()
			self.assertNotIn("<!-- COMPONENTS -->", page)
			self.assertIn('src="runtime/components/note.js"', page)
			with open(os.path.join(d, "board_data.js"), encoding="utf-8") as f:
				data = json.loads(f.read().removeprefix("window.BOARD_DATA = ").rstrip().rstrip(";"))
			self.assertEqual(data["theme"]["name"], "notebook")
			self.assertIn("cells", data["catalog"]["types"])
			self.assertIsNone(data["audio"])

	def test_runtime_不寫死任何色碼(self):
		for dirpath, _, files in os.walk(os.path.join(BOARD, "runtime")):
			for name in files:
				if name.endswith(".js"):
					with open(os.path.join(dirpath, name), encoding="utf-8") as f:
						self.assertIsNone(HEX.search(f.read()), f"{name} 寫死色碼")

	def test_runtime_不讀時鐘也不用亂數(self):
		banned = re.compile(r"Math\.random|Date\.now|performance\.now|new Date\(")
		for dirpath, _, files in os.walk(os.path.join(BOARD, "runtime")):
			for name in files:
				if name.endswith(".js"):
					with open(os.path.join(dirpath, name), encoding="utf-8") as f:
						self.assertIsNone(banned.search(f.read()), f"{name} 讀時鐘或用亂數")


if __name__ == "__main__":
	unittest.main()
