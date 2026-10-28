"""tools/video_skills_sync.py：哪些檔不帶、掃描擋什麼、清單怎麼展開（不碰 git、不連網）。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
import video_skills_sync as vs  # noqa: E402


class SyncTest(unittest.TestCase):
	def test_skips_media_outputs_and_secrets(self):
		for rel in ("audio/f5/x.wav", "renders/b24.mp4", "out/film/index.html", "a/__pycache__/m.pyc",
				"w.safetensors", ".env", "node_modules/x/index.js", "chalk-story/audio/narration.wav", "assets/img/stuck.png"):
			self.assertTrue(vs.skipped(rel), rel)
		for rel in ("beats.js", "assets/fonts/huninn.woff2", "board/presets/win11/env_vars.json", "README.md"):
			self.assertFalse(vs.skipped(rel), rel)

	def test_scan_catches_keys_and_personal_paths(self):
		self.assertTrue(vs.scan("key = 'sk-" + "a" * 30 + "'"))
		self.assertTrue(vs.scan("AKIA" + "A" * 16))
		self.assertTrue(vs.scan("/mnt/g/我的雲端硬碟/x"))
		self.assertTrue(vs.scan("C:\\Users\\pjw92\\c_homework"))
		# 示範用的假帳號不算外洩
		self.assertEqual(vs.scan("C:\\Users\\student\\AppData"), [])
		self.assertEqual(vs.scan("printf(\"請輸入成績: \");"), [])

	def test_plan_expands_dirs_and_respects_skips(self):
		with tempfile.TemporaryDirectory() as d:
			root = Path(d)
			(root / "pkg/audio").mkdir(parents=True)
			(root / "pkg/a.py").write_text("x")
			(root / "pkg/audio/n.wav").write_text("x")
			(root / "doc.md").write_text("x")
			old = vs.INCLUDE
			try:
				vs.INCLUDE = [("pkg", "lib/pkg"), ("doc.md", "docs/doc.md")]
				got = sorted(d for _, d in vs.plan(root))
			finally:
				vs.INCLUDE = old
			self.assertEqual(got, ["docs/doc.md", "lib/pkg/a.py"])

	def test_plan_fails_on_missing_source(self):
		old = vs.INCLUDE
		try:
			vs.INCLUDE = [("nope", "nope")]
			with self.assertRaises(SystemExit):
				vs.plan(Path(tempfile.gettempdir()))
		finally:
			vs.INCLUDE = old

	def test_real_include_list_is_clean(self):
		# 真的清單展開後不能有金鑰、本機路徑或超大檔：這就是推送前的閘
		self.assertEqual(vs.problems(vs.plan()), [])

	def test_real_include_list_carries_its_imports(self):
		# 影片相關改動後清單漏帶依賴，搬過去才壞（2026-10-28 第一次搬就漏了 workbench）
		self.assertEqual(vs.missing_imports(vs.plan()), [])

	def test_missing_imports_finds_unlisted_local_module(self):
		with tempfile.TemporaryDirectory() as d:
			root = Path(d)
			(root / "pkg").mkdir()
			(root / "pkg/a.py").write_text("import helper\nfrom pkg import b\nimport json\n")
			(root / "pkg/b.py").write_text("")
			(root / "helper.py").write_text("")
			files = [(root / "pkg/a.py", "pkg/a.py"), (root / "pkg/b.py", "pkg/b.py")]
			self.assertEqual([m for _, m, _ in vs.missing_imports(files, root)], ["helper"])


if __name__ == "__main__":
	unittest.main()
