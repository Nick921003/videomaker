import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from workbench.library import Library, read_json, safe_path, unit_id, write_json
from workbench import server


class TestLibrary(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.root = Path(self.temp.name) / "units"
		self.library = Library(self.root)

	def test_unit_id_uses_exact_markdown(self):
		markdown = "# 教材\n內容。\n"
		self.assertEqual(unit_id(markdown), hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:12])
		self.assertNotEqual(unit_id(markdown), unit_id(markdown.rstrip()))

	def test_create_unit_reuses_original_material_and_meta(self):
		markdown = "# 同一份教材\n內容含空白。\n"
		uid, created = self.library.create_unit(markdown, " 原始標題 ", "source-1", "pdf")
		self.assertTrue(created)
		self.assertEqual(uid, unit_id(markdown))
		meta_path = self.library.path(uid, "meta.json")
		original = meta_path.read_bytes()
		self.assertEqual(self.library.create_unit(markdown, "另一標題", "source-2"), (uid, False))
		self.assertEqual(meta_path.read_bytes(), original)
		self.assertEqual(self.library.path(uid, "material.md").read_text(encoding="utf-8"), markdown)
		self.assertEqual(self.library.meta(uid)["title"], "原始標題")

	def test_source_ref_and_kind_round_trip(self):
		uid, _ = self.library.create_unit("教材", source_ref="upload-123", source_kind="pptx")
		meta = self.library.meta(uid)
		self.assertEqual(set(meta), {"title", "created_at", "source_ref", "source_kind"})
		self.assertEqual(meta["source_ref"], "upload-123")
		self.assertEqual(meta["source_kind"], "pptx")
		self.assertTrue(meta["created_at"].endswith("+00:00"))
		uid, _ = self.library.create_unit("另一份教材")
		self.assertIsNone(self.library.meta(uid)["source_ref"])
		self.assertEqual(self.library.meta(uid)["source_kind"], "md")

	def test_title_defaults_and_length_match_existing_behavior(self):
		for markdown, title, expected in (
			("\n# 推導標題\n內容", None, "推導標題"),
			("# 空白標題\n內容", "  ", "空白標題"),
			(" ", None, "未命名教材"),
			("長標題教材", "題" * 201, "題" * 200),
		):
			with self.subTest(markdown=markdown):
				uid, _ = self.library.create_unit(markdown, title)
				self.assertEqual(self.library.meta(uid)["title"], expected)

	def test_exists_and_unit_dir_require_valid_complete_units(self):
		uid, _ = self.library.create_unit("教材")
		self.assertTrue(self.library.exists(uid))
		self.assertEqual(self.library.unit_dir(uid), self.root / uid)
		incomplete = "a" * 12
		(self.root / incomplete).mkdir()
		for missing in ("0" * 12, incomplete, "../x", "bad-id", None):
			with self.subTest(uid=missing):
				self.assertFalse(self.library.exists(missing))
				with self.assertRaises(KeyError):
					self.library.unit_dir(missing)

	def test_unit_ids_are_newest_first_and_ignore_other_entries(self):
		older, _ = self.library.create_unit("舊教材")
		newer, _ = self.library.create_unit("新教材")
		for uid, at in ((older, "2026-10-01T00:00:00+00:00"), (newer, "2026-10-05T00:00:00+00:00")):
			meta = self.library.meta(uid)
			meta["created_at"] = at
			write_json(self.library.path(uid, "meta.json"), meta)
		(self.root / "uploads").mkdir()
		(self.root / ("a" * 12)).mkdir()
		(self.root / ("b" * 12)).symlink_to(Path(self.temp.name))
		self.assertEqual(self.library.unit_ids(), [newer, older])

	def test_plan_is_optional_and_reads_saved_json(self):
		uid, _ = self.library.create_unit("教材")
		self.assertIsNone(self.library.plan(uid))
		plan = {"stories": [{"id": "q1", "title": "問題"}]}
		write_json(self.library.path(uid, "plan.json"), plan)
		self.assertEqual(self.library.plan(uid), plan)
		self.library.plan(uid)["stories"].clear()
		self.assertEqual(self.library.plan(uid), plan)
		with self.assertRaises(KeyError):
			self.library.plan("0" * 12)

	def test_unit_path_rejects_traversal_and_symlink_escape(self):
		uid, _ = self.library.create_unit("教材")
		directory = self.library.unit_dir(uid)
		self.assertEqual(self.library.path(uid, "q1/voice/timing.json"), directory / "q1/voice/timing.json")
		(directory / "escape").symlink_to(self.root)
		for relative in ("../x", "escape/x", str(self.root / "outside.json")):
			with self.subTest(relative=relative), self.assertRaises(ValueError):
				self.library.path(uid, relative)


class TestJSONAndPaths(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.root = Path(self.temp.name)

	def test_safe_path_resolves_inside_root_and_rejects_escape(self):
		self.assertEqual(safe_path(self.root, "nested/../value.json"), self.root / "value.json")
		(self.root / "escape").symlink_to(self.root.parent)
		for relative in ("../x", "escape/x", str(self.root) + "-other/value.json"):
			with self.subTest(relative=relative), self.assertRaises(ValueError):
				safe_path(self.root, relative)

	def test_read_json_default_unicode_and_invalid_json(self):
		path = self.root / "data.json"
		self.assertIsNone(read_json(path))
		default = {"missing": True}
		self.assertIs(read_json(path, default), default)
		path.write_text('{"title": "教材"}', encoding="utf-8")
		self.assertEqual(read_json(path), {"title": "教材"})
		path.write_text("{", encoding="utf-8")
		with self.assertRaises(json.JSONDecodeError):
			read_json(path, default)

	def test_write_json_replaces_atomically_and_preserves_unicode(self):
		path = self.root / "nested/data.json"
		write_json(path, {"title": "原始"})
		replace = os.replace
		def inspect_replace(temporary, target):
			self.assertEqual(read_json(target), {"title": "原始"})
			self.assertEqual(read_json(temporary), {"title": "新教材"})
			replace(temporary, target)
		with patch("workbench.library.os.replace", side_effect=inspect_replace) as replaced:
			write_json(path, {"title": "新教材"})
			replaced.assert_called_once()
		self.assertEqual(read_json(path), {"title": "新教材"})
		self.assertIn("新教材", path.read_text(encoding="utf-8"))
		self.assertFalse(path.with_suffix(".tmp").exists())

	def test_write_json_rejects_nonfinite_values_without_overwriting(self):
		path = self.root / "data.json"
		write_json(path, {"usd": 0.5})
		with self.assertRaises(ValueError):
			write_json(path, {"usd": float("nan")})
		self.assertEqual(read_json(path), {"usd": 0.5})


class TestServerLibraryPaths(unittest.TestCase):
	def test_invalid_metadata_does_not_prevent_server_startup(self):
		for contents in ("{}", "{", "null", '{"created_at": 5}'):
			with self.subTest(contents=contents), tempfile.TemporaryDirectory() as temporary:
				library = Library(Path(temporary) / "units")
				uid, _ = library.create_unit("教材")
				library.path(uid, "meta.json").write_text(contents, encoding="utf-8")
				valid_uid, _ = library.create_unit("正常教材")
				job_id = "0" * 32
				write_json(library.path(valid_uid, f"jobs/{job_id}.json"), {
					"job_id": job_id, "unit_id": valid_uid, "kind": "plan", "state": "done"})
				studio = server.Studio(library.root, command_runner=lambda *args: 0, tts_mode="gemini")
				try:
					self.assertEqual(library.unit_ids(), [valid_uid, uid])
					self.assertEqual(studio.get_job(job_id)["state"], "done")
				finally:
					studio.close()

	def test_static_path_escape_keeps_404_error(self):
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			static = root / "web"
			static.mkdir()
			outside = root / "outside.mjs"
			write_json(outside, {"formats": []})
			(static / "app.mjs").symlink_to(outside)
			handler = object.__new__(server.StudioHandler)
			handler.server = SimpleNamespace(studio=None, web_dir=static)
			handler.command = "GET"
			handler.path = "/web/app.mjs"
			with self.assertRaises(server.APIError) as error:
				handler._dispatch()
			self.assertEqual(error.exception.status, 404)

	def test_plan_escape_is_404_and_corrupt_json_stays_a_data_error(self):
		with tempfile.TemporaryDirectory() as temporary:
			root = Path(temporary)
			studio = server.Studio(root / "units", command_runner=lambda *args: 0, tts_mode="gemini")
			try:
				uid = studio.create_unit({"markdown": "教材"})["unit_id"]
				path = studio.library.path(uid, "plan.json")
				outside = root / "plan.json"
				write_json(outside, {"stories": [{"id": "q1"}]})
				path.symlink_to(outside)
				for read in (lambda: studio.get_unit(uid), lambda: studio.enqueue_generate(uid, {"items": ["q1"]})):
					with self.assertRaises(server.APIError) as error:
						read()
					self.assertEqual(error.exception.status, 404)
				path.unlink()
				path.write_text("{", encoding="utf-8")
				with self.assertRaises(json.JSONDecodeError):
					studio.get_unit(uid)
			finally:
				studio.close()


if __name__ == "__main__":
	unittest.main()
