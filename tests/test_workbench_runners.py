import contextlib
from datetime import datetime
import importlib
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from tests.fixtures.make_pptx import make
from tests.test_studio_deck_builder import MATERIAL as DECK_MATERIAL
from tests.test_studio_deck_contracts import sample_deck_v11
from tests.test_studio_mindmap import MATERIAL as MAP_MATERIAL, sample_map
from workbench import formats, usage
from workbench.formats import stages
from workbench.jobs import parse_marker
from workbench.library import Library, read_json, write_json


ROOT = Path(__file__).resolve().parents[1]
MODEL = "gemini-3.8-flash"


def call_usage():
	return {"provider": "google", "model": MODEL, "in": 100, "out": 40,
		"thinking": 10, "total": 150, "cache_read": 20, "prompt": "PRIVATE"}


class TestWorkbenchRunners(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.root = Path(self.temp.name)
		self.library = Library(self.root / "units")
		self.runners = {}
		for name in ("mindmap", "slides", "normalize"):
			module = f"workbench.run_{name}"
			self.assertIsNotNone(importlib.util.find_spec(module), f"missing B5 runner: {module}")
			self.runners[name] = importlib.import_module(module)
		self.environment = patch.dict(os.environ, {"VIDEO_ENGINE_LLM": "google:" + MODEL})
		self.environment.start()
		self.addCleanup(self.environment.stop)

	def unit(self, material):
		uid, _ = self.library.create_unit(material)
		return self.library.unit_dir(uid)

	def run_main(self, name, argv, complete=None):
		output = StringIO()
		with contextlib.redirect_stdout(output):
			status = self.runners[name].main(list(map(str, argv)), complete)
		return status, [parse_marker(line) for line in output.getvalue().splitlines()], output.getvalue()

	def rows(self, directory):
		return [json.loads(line) for line in (directory / "usage.jsonl").read_text(encoding="utf-8").splitlines()]

	def assert_usage(self, directory, item, step="generate", count=1):
		rows = self.rows(directory)
		self.assertEqual(len(rows), count)
		for row in rows:
			self.assertEqual((row["item"], row["step"], row["model"]), (item, step, MODEL))
			self.assertEqual((row["in"], row["out"]), (100, 50))
			self.assertAlmostEqual(row["usd"], 0.000249)
			self.assertEqual(row["cache_read_input_tokens"], 20)
			self.assertIsNotNone(datetime.fromisoformat(row["at"]).tzinfo)
			self.assertNotIn("PRIVATE", json.dumps(row))
		self.assertEqual(len(usage.read_unit(directory)), count)

	def test_mindmap_writes_valid_outputs_and_registry_markers(self):
		directory = self.unit(MAP_MATERIAL)
		def complete(_system, user, _schema):
			self.assertEqual(json.loads(user), {"instruction": "整理這份教材的概念與關係", "material": MAP_MATERIAL})
			self.assertNotIn("@step validate", sys.stdout.getvalue())
			return sample_map(), call_usage()
		status, markers, _ = self.run_main("mindmap", [directory], complete)
		self.assertEqual(status, 0)
		self.assertEqual(markers, [("step", step["id"]) for step in formats.get_format("mindmap").FORMAT["steps"]])
		self.assertEqual(read_json(directory / "mindmap/mindmap.json"), sample_map())
		svg = (directory / "mindmap/mindmap.svg").read_bytes()
		self.assertTrue(svg.startswith(b"<svg"))
		self.assertIn(MAP_MATERIAL.encode(), svg)
		self.assert_usage(directory, "mindmap")

	def test_slides_exports_real_pptx_and_registry_outputs(self):
		directory = self.unit(DECK_MATERIAL)
		def complete(_system, user, _schema):
			self.assertEqual(json.loads(user)["instruction"], "把這份教材做成線上簡報")
			return sample_deck_v11(), call_usage()
		status, markers, _ = self.run_main("slides", [directory], complete)
		self.assertEqual(status, 0)
		self.assertEqual(markers, [("step", "generate"), ("step", "validate"), ("step", "export")])
		self.assertEqual(read_json(directory / "slides/deck.json"), sample_deck_v11())
		with zipfile.ZipFile(directory / "slides/deck.pptx") as archive:
			self.assertIn("ppt/slides/slide1.xml", archive.namelist())
			self.assertIn("迴圈".encode(), archive.read("ppt/slides/slide1.xml"))
		view = formats.UnitView(directory.name, directory, None)
		self.assertTrue(formats.get_format("slides").is_done(view, "slides"))
		self.assertEqual(formats.get_format("slides").outputs(view, "slides"),
			{"deck": "slides/deck.json", "pptx": "slides/deck.pptx"})
		self.assert_usage(directory, "slides")

	def test_default_completion_stage_and_model_environment(self):
		for name, material, candidate, stage in (
			("mindmap", MAP_MATERIAL, sample_map(), "mindmap"),
			("slides", DECK_MATERIAL, sample_deck_v11(), "deck"),
		):
			with self.subTest(name=name):
				directory = self.unit(material)
				os.environ.pop("VIDEO_ENGINE_LLM", None)
				with patch("video_engine.llm.complete_json", return_value=(candidate, call_usage())) as complete:
					status, _, _ = self.run_main(name, [directory])
				self.assertEqual(status, 0)
				self.assertEqual(complete.call_args.kwargs, {"stage": stage})
				self.assertEqual(os.environ["VIDEO_ENGINE_LLM"], "google:" + MODEL)
				self.assert_usage(directory, name)
		os.environ["VIDEO_ENGINE_LLM"] = "anthropic:claude-opus-5-5"
		with patch("video_engine.llm.complete_json", return_value=(sample_map(), call_usage())):
			self.assertEqual(self.run_main("mindmap", [self.unit(MAP_MATERIAL)])[0], 0)
		self.assertEqual(os.environ["VIDEO_ENGINE_LLM"], "anthropic:claude-opus-5-5")

	def test_bad_quotes_fail_validation_and_keep_paid_usage(self):
		for name, material, candidate, section in (
			("mindmap", MAP_MATERIAL, sample_map(), "nodes"),
			("slides", DECK_MATERIAL, sample_deck_v11(), "slides"),
		):
			with self.subTest(name=name):
				directory = self.unit(material)
				candidate[section][0]["source_quote"] = "教材没有這句"
				status, markers, _ = self.run_main(name, [directory], lambda *_: (candidate, call_usage()))
				self.assertEqual(status, 1)
				self.assertEqual(markers[:2], [("step", "generate"), ("step", "validate")])
				self.assertEqual(markers[-1][:2], ("error", "quote_mismatch"))
				self.assertFalse(formats.get_format(name).is_done(formats.UnitView(directory.name, directory, None), name))
				self.assert_usage(directory, name)

	def test_contract_errors_are_not_mislabeled_as_quote_errors(self):
		for name, material in (("mindmap", MAP_MATERIAL), ("slides", DECK_MATERIAL)):
			with self.subTest(name=name):
				status, markers, _ = self.run_main(name, [self.unit(material)], lambda *_: ({}, call_usage()))
				self.assertEqual(status, 1)
				self.assertEqual(markers[-1][:2], ("error", "unknown"))

	def test_captured_provider_calls_are_appended_without_double_counting(self):
		from video_engine.usage import report_usage
		directory = self.unit(MAP_MATERIAL)
		write_json(directory / "keep.json", {"keep": True})
		def complete(*_):
			report_usage("google", MODEL, call_usage())
			report_usage("google", MODEL, call_usage())
			return sample_map(), call_usage()
		for count in (2, 4):
			self.assertEqual(self.run_main("mindmap", [directory], complete)[0], 0)
			self.assert_usage(directory, "mindmap", count=count)
		self.assertEqual(read_json(directory / "keep.json"), {"keep": True})

	def test_missing_usage_still_records_the_call(self):
		directory = self.unit(MAP_MATERIAL)
		self.assertEqual(self.run_main("mindmap", [directory], lambda *_: (sample_map(), {}))[0], 0)
		row = self.rows(directory)[0]
		self.assertEqual((row["item"], row["step"]), ("mindmap", "generate"))
		self.assertFalse(row["reported"])
		self.assertEqual(len(usage.read_unit(directory)), 1)

	def test_busy_provider_failure_is_safe_and_retains_usage(self):
		from video_engine.usage import report_usage
		for name, material in (("mindmap", MAP_MATERIAL), ("slides", DECK_MATERIAL)):
			with self.subTest(name=name):
				directory = self.unit(material)
				def complete(*_):
					report_usage("google", MODEL, call_usage())
					raise RuntimeError("503 UNAVAILABLE PRIVATE-token /private/path")
				status, markers, output = self.run_main(name, [directory], complete)
				self.assertEqual(status, 1)
				self.assertEqual(markers[-1][:2], ("error", "gemini_busy"))
				self.assertNotIn("PRIVATE", output)
				self.assertNotIn("/private/path", output)
				self.assert_usage(directory, name)

	def test_source_limit_and_budget_block_calls_before_payment(self):
		for name in ("mindmap", "slides"):
			with self.subTest(name=name):
				directory = self.unit("字" * 30001)
				complete = Mock(side_effect=AssertionError("paid call"))
				status, markers, _ = self.run_main(name, [directory], complete)
				self.assertEqual((status, markers[-1][:2]), (1, ("error", "too_large")))
				complete.assert_not_called()
				directory = self.unit(MAP_MATERIAL if name == "mindmap" else DECK_MATERIAL)
				(directory / "usage.jsonl").write_text('{"item":"analysis","usd":0.5}\n', encoding="utf-8")
				status, markers, _ = self.run_main(name, [directory], complete)
				self.assertEqual((status, markers[-1][:2]), (1, ("error", "budget")))
				complete.assert_not_called()
				self.assertEqual(len(self.rows(directory)), 1)

	def upload(self, pages=1):
		directory = self.root / f"upload-{pages}"
		directory.mkdir()
		make(directory / "lesson.pptx", [("光合作用", ["Photosynthesis converts light into energy."])] * pages)
		write_json(directory / "upload.json", {"filename": "lesson.pptx", "kind": "pptx", "title": "原始教材"})
		return directory

	def normalize_response(self, _system, request, pdf_bytes):
		self.assertIn("Photosynthesis", request)
		self.assertIsNone(pdf_bytes)
		return {"title": "Photosynthesis", "pages": [{"page": 1,
			"clean_text": "Photosynthesis converts light into energy.",
			"verified_quotes": ["Photosynthesis converts light into energy."],
			"visual_notes": [], "uncertainties": []}]}, call_usage()

	def test_normalize_extracts_original_and_creates_unit_with_ingest_usage(self):
		upload = self.upload()
		for count in (1, 2):
			status, markers, _ = self.run_main("normalize", [upload, self.library.root], self.normalize_response)
			self.assertEqual(status, 0)
			self.assertEqual(markers[:2], [("step", "extract"), ("step", "normalize")])
			self.assertEqual(markers[-1][0], "unit")
			directory = self.library.unit_dir(markers[-1][1])
			self.assertEqual(self.library.meta(directory.name)["source_kind"], "pptx")
			self.assertEqual(self.library.meta(directory.name)["title"], "原始教材")
			self.assertIn("原文摘錄", (directory / "material.md").read_text(encoding="utf-8"))
			self.assert_usage(directory, "ingest", "normalize", count=count)
			self.assertEqual(len(self.library.unit_ids()), 1)

	def test_default_normalize_captures_usage_from_existing_llm_adapter(self):
		upload = self.upload()
		with patch("studio.material_normalizer.complete_ingest_text_json", side_effect=
			lambda system, request: self.normalize_response(system, request, None)) as complete:
			status, markers, _ = self.run_main("normalize", [upload, self.library.root])
		self.assertEqual(status, 0)
		complete.assert_called_once()
		self.assert_usage(self.library.unit_dir(markers[-1][1]), "ingest", "normalize")

	def test_normalize_pdf_passes_original_visual_bytes(self):
		upload = self.root / "pdf-upload"
		upload.mkdir()
		pdf = b"%PDF-offline fixture"
		(upload / "lesson.pdf").write_bytes(pdf)
		write_json(upload / "upload.json", {"filename": "lesson.pdf", "kind": "pdf", "title": None})
		def runner(system, request, pdf_bytes):
			self.assertEqual(pdf_bytes, pdf)
			return self.normalize_response(system, request, None)
		with patch("workbench.run_normalize.extract_text", return_value="## 第 1 頁\nPhotosynthesis converts light into energy."):
			status, markers, _ = self.run_main("normalize", [upload, self.library.root], runner)
		self.assertEqual(status, 0)
		self.assertEqual(self.library.meta(markers[-1][1])["source_kind"], "pdf")
		self.assertEqual(self.library.meta(markers[-1][1])["title"], "Photosynthesis")

	def test_normalize_rejects_page_and_file_limits_before_ai(self):
		complete = Mock(side_effect=AssertionError("paid call"))
		upload = self.upload(pages=31)
		status, markers, _ = self.run_main("normalize", [upload, self.library.root], complete)
		self.assertEqual((status, markers[-1][:2]), (1, ("error", "too_large")))
		complete.assert_not_called()
		upload = self.upload()
		(upload / "lesson.pptx").write_bytes(b"x" * (5 * 1024 * 1024 + 1))
		with patch("workbench.run_normalize.extract_text", side_effect=AssertionError("extract oversized file")):
			status, markers, _ = self.run_main("normalize", [upload, self.library.root], complete)
		self.assertEqual((status, markers[-1][:2]), (1, ("error", "too_large")))
		self.assertEqual(self.library.unit_ids(), [])

	def test_normalize_rejects_invalid_metadata_and_escaping_source(self):
		upload = self.upload()
		complete = Mock(side_effect=AssertionError("paid call"))
		for metadata in (None, {"filename": "../outside.pptx", "kind": "pptx", "title": None},
			{"filename": "lesson.pptx", "kind": "pdf", "title": None}):
			with self.subTest(metadata=metadata):
				write_json(upload / "upload.json", metadata)
				status, markers, _ = self.run_main("normalize", [upload, self.library.root], complete)
				self.assertEqual((status, markers[-1][:2]), (1, ("error", "unknown")))
		complete.assert_not_called()
		self.assertEqual(self.library.unit_ids(), [])

	def test_normalize_failure_records_usage_without_creating_unit(self):
		upload = self.upload()
		status, markers, _ = self.run_main("normalize", [upload, self.library.root],
			lambda *_: ({"title": "bad", "pages": []}, call_usage()))
		self.assertEqual(status, 1)
		self.assertEqual(markers[-1][:2], ("error", "unknown"))
		self.assertFalse(any(marker and marker[0] == "unit" for marker in markers))
		self.assertEqual(self.library.unit_ids(), [])
		self.assert_usage(upload, "ingest", "normalize")

	def test_registry_scripts_run_directly_from_another_directory_without_network(self):
		directory = self.unit("字" * 30001)
		view = formats.UnitView(directory.name, directory, None)
		commands = [formats.get_format(name).commands(view, name)[0] for name in ("mindmap", "slides")]
		commands.extend(stages.ingest_commands(self.upload(pages=31), self.library.root))
		for command in commands:
			with self.subTest(script=command.argv[0]):
				environment = dict(os.environ)
				environment.pop("PYTHONPATH", None)
				result = subprocess.run([sys.executable, *command.argv], cwd=self.root,
					env=environment, capture_output=True, text=True, timeout=15)
				self.assertEqual(result.returncode, 1, result.stderr)
				markers = [parse_marker(line) for line in result.stdout.splitlines()]
				self.assertEqual(markers[-1][:2], ("error", "too_large"))
				self.assertEqual(result.stderr, "")


if __name__ == "__main__":
	unittest.main()
