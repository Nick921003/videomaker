import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(ROOT, "video_engine", "board")
sys.path.insert(0, BOARD)

import compile as BC
import compose as CO


def load(name):
	with open(os.path.join(BOARD, "examples", f"{name}.scene.json"), encoding="utf-8") as f:
		return json.load(f)


PLAN = {"unit_title": "環境建立：VS Code + GCC", "glossary": [{"term": "PATH", "say_as": "路徑變數"}, {"term": "gcc", "say_as": "編譯器"}],
	"stories": [{"id": "a", "title": "PATH 是什麼"}, {"id": "b", "title": "怎麼把 gcc 加進去"}]}


class TestCompose(unittest.TestCase):
	def setUp(self):
		self.doc = CO.compose(PLAN, [load("env_path"), load("env_path_howto")], ["a", "b"])

	def test_cli_reports_source_version_error_without_writing_output(self):
		import tempfile
		from pathlib import Path
		from unittest.mock import patch
		import contextlib
		import io
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			(root / "meta.json").write_text("{}")
			(root / "plan.json").write_text(json.dumps({**PLAN, "highlight": {"stories": ["a"]}}))
			(root / "a.scene.json").write_text(json.dumps(load("env_path")))
			out = root / "combined.scene.json"
			stream = io.StringIO()
			with patch.object(sys, "argv", ["compose.py", str(root / "plan.json"), str(root), str(out)]), patch("workbench.material.composite_provenance", side_effect=ValueError("教材版本不一致")), contextlib.redirect_stdout(stream):
				with self.assertRaises(SystemExit) as caught:
					CO.main()
			self.assertEqual(caught.exception.code, 1)
			self.assertIn("@error material_version", stream.getvalue())
			self.assertFalse(out.exists())

	def test_兩支都有term也不撞名且能編譯(self):
		ids = [o["id"] for o in self.doc["objects"]]
		self.assertEqual(len(ids), len(set(ids)))
		self.assertIn("c1_term", ids)
		self.assertIn("c2_term", ids)
		tl = BC.compile_scene(self.doc, None, BC.load_catalog())
		self.assertEqual(tl["gaps"], [])

	def test_引用一併改寫但錨點後半不動(self):
		acts = [a for s in self.doc["scenes"] for b in s["beats"] for a in b["do"]]
		self.assertIn({"act": "arrow", "target": "c1_term:cmd", "to": "c1_path:title", "with": "prev"}, acts)
		self.assertTrue(any(a.get("on") == "c2_sysprops:envbtn" for a in acts))

	def test_目錄過場在每支之前且標題唸法套詞彙表(self):
		ids = [s["id"] for s in self.doc["scenes"]]
		self.assertEqual(ids[0], "toc0")
		self.assertIn("toc1", ids)
		self.assertEqual(ids[-1], "outro")
		toc1 = next(s for s in self.doc["scenes"] if s["id"] == "toc1")
		self.assertEqual(toc1["beats"][0]["spoken"], "第二個重點：怎麼把 編譯器 加進去。")
		self.assertEqual(self.doc["scenes"][0]["beats"][0]["say"], "這支影片用兩個重點，帶你看懂環境建立：VS Code + GCC。")

	def test_程式產生的旁白都不夾英文(self):
		import narrate
		PLAN["glossary"].append({"term": "VS Code", "say_as": "編輯器"})
		doc = CO.compose(PLAN, [load("env_path"), load("env_path_howto")], ["a", "b"])
		PLAN["glossary"].pop()
		for s in doc["scenes"]:
			if s["id"].startswith("toc") or s["id"] == "outro":
				for b in s["beats"]:
					self.assertIsNone(narrate.speech_problems(b.get("spoken") or b["say"]), b)


if __name__ == "__main__":
	unittest.main()
