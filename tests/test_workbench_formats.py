import copy
from dataclasses import is_dataclass
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from workbench import formats, server
from workbench.formats import stages
from tests.workbench_shapes import SHAPES, assert_shape


ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "video_engine/board"
PLAN = {
	"stories": [{"id": "q1", "sec": 60}, {"id": "q2", "sec": 75}, {"id": "q3", "sec": 70}],
	"highlight": {"stories": ["q3", "q1", "q2"], "total_sec": 205},
}


class TestRegistry(unittest.TestCase):
	def test_public_matches_committed_contract_and_shape(self):
		contract = json.loads((ROOT / "workbench/web/mock/formats.json").read_text(encoding="utf-8"))
		value = formats.public()
		self.assertEqual(value, contract)
		assert_shape(value, SHAPES["formats"])
		self.assertEqual(json.loads(json.dumps(value)), value)

	def test_public_returns_independent_metadata(self):
		value = formats.public()
		value["formats"][0]["steps"][0]["name"] = "changed"
		value["stages"][0]["steps"].clear()
		self.assertNotEqual(formats.public(), value)

	def test_available_modules_validate_and_have_stable_order(self):
		modules = formats.list_formats()
		self.assertEqual([module.FORMAT["id"] for module in modules],
			["video", "highlight", "mindmap", "slides"])
		for module in modules:
			with self.subTest(format=module.FORMAT["id"]):
				formats.validate(module.FORMAT, module)
				self.assertIs(formats.get_format(module.FORMAT["id"]), module)
		modules.clear()
		self.assertEqual(len(formats.list_formats()), 4)
		for fid in ("unknown", "comic", "ingest"):
			with self.subTest(id=fid), self.assertRaises(KeyError):
				formats.get_format(fid)

	def test_planned_formats_validate(self):
		for fmt in formats.public()["formats"][4:]:
			with self.subTest(format=fmt["id"]):
				formats.validate(fmt)

	def test_import_rejects_invalid_registry_with_format_error(self):
		for mutation in (
			"del formats.video.FORMAT['id']",
			"formats.video.FORMAT['steps'].append(formats.video.FORMAT['steps'][0])",
			"formats.planned.PLANNED[0]['commands'] = []",
			"formats.stages.INGEST['steps'][0]['paid'] = 1",
		):
			code = "\n".join([
				"import importlib", "from workbench import formats", mutation,
				"try:", "\timportlib.reload(formats)",
				"except Exception as error:", "\tassert type(error).__name__ == 'FormatError', repr(error)",
				"else:", "\traise AssertionError('invalid registry imported successfully')",
			])
			with self.subTest(mutation=mutation):
				result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
					capture_output=True, text=True)
				self.assertEqual(result.returncode, 0, result.stderr)

	def test_duplicate_step_id_rejected(self):
		module = formats.get_format("video")
		fmt = copy.deepcopy(module.FORMAT)
		fmt["steps"].append(copy.deepcopy(fmt["steps"][0]))
		with self.assertRaises(formats.FormatError):
			formats.validate(fmt, module)

	def test_missing_fields_and_invalid_metadata_rejected(self):
		module = formats.get_format("video")
		for key in ("id", "name", "scope", "status", "preview", "steps"):
			fmt = copy.deepcopy(module.FORMAT)
			del fmt[key]
			with self.subTest(missing=key), self.assertRaises(formats.FormatError):
				formats.validate(fmt, module)
		for key, value in (("id", 1), ("name", None), ("scope", "other"),
			("status", "unknown"), ("preview", "png"), ("steps", {})):
			fmt = copy.deepcopy(module.FORMAT)
			fmt[key] = value
			with self.subTest(field=key), self.assertRaises(formats.FormatError):
				formats.validate(fmt, module)
		for key in ("id", "name", "model", "paid", "cost", "detail"):
			for missing in (True, False):
				fmt = copy.deepcopy(module.FORMAT)
				if missing:
					del fmt["steps"][0][key]
				else:
					fmt["steps"][0][key] = 1
				with self.subTest(step_field=key, missing=missing), self.assertRaises(formats.FormatError):
					formats.validate(fmt, module)
		fmt = copy.deepcopy(module.FORMAT)
		fmt["steps"] = [None]
		with self.assertRaises(formats.FormatError):
			formats.validate(fmt, module)
		with self.assertRaises(formats.FormatError):
			formats.validate(None)

	def test_available_requires_callable_module_interface(self):
		module = formats.get_format("video")
		with self.assertRaises(formats.FormatError):
			formats.validate(module.FORMAT)
		for key in ("estimate_usd", "commands", "outputs", "is_done"):
			interface = {name: getattr(module, name) for name in ("estimate_usd", "commands", "outputs", "is_done")}
			interface[key] = None
			with self.subTest(function=key), self.assertRaises(formats.FormatError):
				formats.validate(module.FORMAT, SimpleNamespace(**interface))

	def test_planned_rejects_commands_steps_and_invalid_notes(self):
		base = formats.public()["formats"][4]
		for key, value in (("commands", []), ("steps", formats.get_format("video").FORMAT["steps"]),
			("planned_note", None), ("planned_note", {}),
			("planned_note", {"order": True, "why": "reason"}),
			("planned_note", {"order": 1, "why": 2})):
			fmt = copy.deepcopy(base)
			fmt[key] = value
			with self.subTest(field=key, value=value), self.assertRaises(formats.FormatError):
				formats.validate(fmt)
		with self.assertRaises(formats.FormatError):
			formats.validate(base, SimpleNamespace(commands=None))

	def test_item_format_maps_points_and_unit_items(self):
		for item in ("q1", "q2", "q3"):
			self.assertEqual(formats.item_format(PLAN, item), "video")
		for item in ("highlight", "mindmap", "slides"):
			self.assertEqual(formats.item_format(None, item), item)
		for plan, item in ((None, "q1"), ({}, "q1"), (PLAN, "q4"), (PLAN, "comic")):
			with self.subTest(item=item, plan=plan), self.assertRaises(KeyError):
				formats.item_format(plan, item)


class TestFormatCommands(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.unit = formats.UnitView("0123456789ab", Path(self.temp.name), copy.deepcopy(PLAN))

	def test_command_and_unit_view_dataclasses(self):
		self.assertTrue(is_dataclass(self.unit))
		self.assertEqual(self.unit.tts_mode, "gemini")
		command = formats.Command("generate", ["script.py"])
		self.assertTrue(is_dataclass(command))
		self.assertEqual(command.python, "project")

	def render_chain(self, item, scene):
		directory = self.unit.dir / item
		return [
			formats.Command("narrate", [str(BOARD / "narrate.py"), str(scene),
				str(directory / "voice"), "--tts", self.unit.tts_mode]),
			formats.Command("render", [str(BOARD / "compile.py"), str(scene),
				str(directory / "timeline.json"), "--timing", str(directory / "voice/timing.json"),
				"--gaps", str(directory / "gaps.jsonl")]),
			formats.Command("render", [str(BOARD / "build.py"), str(directory / "timeline.json"),
				str(directory / "player"), "--audio", str(directory / "voice/master.wav")]),
			formats.Command("render", [str(BOARD / "check.py"), str(directory / "player")], "playwright"),
			formats.Command("render", [str(BOARD / "export.py"), str(directory / "player"),
				str(directory / "video.mp4")], "playwright"),
		]

	def scene_command(self, item, step="storyboard", resume=False):
		return formats.Command(step, [str(BOARD / "author.py"), "scene",
			str(self.unit.dir / "material.md"), str(self.unit.dir), item,
			*(["--resume"] if resume else []), "--model", "google:gemini-3.8-flash", "--budget-usd", "0.50"])

	def test_video_commands_exact_sequence_and_interpreters(self):
		module = formats.get_format("video")
		scene = self.unit.dir / "q2.scene.json"
		self.assertEqual(module.commands(self.unit, "q2"),
			[self.scene_command("q2"), *self.render_chain("q2", scene)])
		(self.unit.dir / "q2.failed.json").write_text("{}", encoding="utf-8")
		self.assertEqual(module.commands(self.unit, "q2"),
			[self.scene_command("q2", resume=True), *self.render_chain("q2", scene)])
		self.assertNotIn("--resume", module.commands(self.unit, "q1")[0].argv)
		scene.write_text("{}", encoding="utf-8")
		self.assertEqual(module.commands(self.unit, "q2"), self.render_chain("q2", scene))

	def test_highlight_missing_scenes_in_plan_order_then_compose_and_render(self):
		module = formats.get_format("highlight")
		(self.unit.dir / "q1.scene.json").write_text("{}", encoding="utf-8")
		(self.unit.dir / "q2.failed.json").write_text("{}", encoding="utf-8")
		scene = self.unit.dir / "highlight.scene.json"
		compose = formats.Command("compose", [str(BOARD / "compose.py"),
			str(self.unit.dir / "plan.json"), str(self.unit.dir), str(scene)])
		self.assertEqual(module.commands(self.unit, "highlight"), [
			self.scene_command("q3", "scenes"), self.scene_command("q2", "scenes", resume=True),
			compose, *self.render_chain("highlight", scene)])
		for item in ("q2", "q3"):
			(self.unit.dir / f"{item}.scene.json").write_text("{}", encoding="utf-8")
		self.assertEqual(module.commands(self.unit, "highlight"), [compose, *self.render_chain("highlight", scene)])

	def test_video_and_highlight_match_server_queue_commands(self):
		for item in ("q2", "highlight"):
			for state in ("missing", "failed", "existing"):
				with self.subTest(item=item, state=state):
					for story in PLAN["stories"]:
						for suffix in ("scene", "failed"):
							(self.unit.dir / f"{story['id']}.{suffix}.json").unlink(missing_ok=True)
						if state != "missing":
							suffix = "failed" if state == "failed" else "scene"
							(self.unit.dir / f"{story['id']}.{suffix}.json").write_text("{}", encoding="utf-8")
					module = formats.get_format(formats.item_format(PLAN, item))
					commands = module.commands(self.unit, item)
					expected = [[str(server.PLAYWRIGHT_PY if command.python == "playwright" else server.PROJECT_PY),
						*command.argv] for command in commands]
					actual = []
					def runner(argv, log):
						actual.append(argv)
						return 0
					library = SimpleNamespace(root=self.unit.dir.parent,
						unit_ids=lambda: [], unit_dir=lambda uid: self.unit.dir,
						path=lambda uid, relative: self.unit.dir / relative, plan=lambda uid: PLAN)
					job_queue = server.JobQueue(library, runner, formats, tts_mode=self.unit.tts_mode)
					try:
						jid = job_queue.enqueue(self.unit.id, item)
						deadline = time.monotonic() + 3
						while job_queue.get(jid)["state"] in ("queued", "running") and time.monotonic() < deadline:
							time.sleep(0.005)
						self.assertEqual(job_queue.get(jid)["state"], "done")
					finally:
						job_queue.close()
					self.assertEqual(actual, expected)

	def test_sovits_is_forwarded_for_both_video_formats(self):
		self.unit.tts_mode = "sovits"
		for fid, item in (("video", "q1"), ("highlight", "highlight")):
			with self.subTest(format=fid):
				command = next(command for command in formats.get_format(fid).commands(self.unit, item)
					if command.step == "narrate")
				self.assertEqual(command.argv[-2:], ["--tts", "sovits"])

	def test_stage_commands_exact_arguments(self):
		self.assertEqual(stages.analysis_commands(self.unit), [
			formats.Command("selftest", [str(BOARD / "selftest.py"), "--quick"]),
			formats.Command("plan", [str(BOARD / "author.py"), "plan", str(self.unit.dir / "material.md"),
				str(self.unit.dir), "--model", "google:gemini-3.8-flash", "--budget-usd", "0.50"]),
		])
		self.assertEqual(stages.ingest_commands(self.unit.dir, self.unit.dir.parent), [
			formats.Command("normalize", [str(ROOT / "workbench/run_normalize.py"),
				str(self.unit.dir), str(self.unit.dir.parent)]),
		])

	def test_mindmap_and_slides_use_future_runner_scripts(self):
		for fid in ("mindmap", "slides"):
			with self.subTest(format=fid):
				self.assertEqual(formats.get_format(fid).commands(self.unit, fid), [
					formats.Command("generate", [str(ROOT / f"workbench/run_{fid}.py"), str(self.unit.dir)]),
				])

	def test_estimates(self):
		video = formats.get_format("video")
		highlight = formats.get_format("highlight")
		self.assertAlmostEqual(video.estimate_usd(self.unit, "q1"), 0.053)
		self.assertAlmostEqual(highlight.estimate_usd(self.unit, "highlight"), 0.1515)
		(self.unit.dir / "q1.scene.json").write_text("{}", encoding="utf-8")
		self.assertAlmostEqual(highlight.estimate_usd(self.unit, "highlight"), 0.1215)
		(self.unit.dir / "q1.failed.json").write_text("{}", encoding="utf-8")
		self.assertAlmostEqual(video.estimate_usd(self.unit, "q1"), 0.053)
		for fid in ("mindmap", "slides"):
			self.assertEqual(formats.get_format(fid).estimate_usd(self.unit, fid), 0.01)

	def test_outputs_only_existing_files_and_nonempty_completion(self):
		for fid, item, relative, files in (
			("video", "q2", "q2/video.mp4", {"video": "q2/video.mp4"}),
			("highlight", "highlight", "highlight/video.mp4", {"video": "highlight/video.mp4"}),
			("mindmap", "mindmap", "mindmap/mindmap.svg", {"svg": "mindmap/mindmap.svg"}),
			("slides", "slides", "slides/deck.pptx", {"pptx": "slides/deck.pptx"}),
		):
			with self.subTest(format=fid):
				module = formats.get_format(fid)
				self.assertEqual(module.outputs(self.unit, item), {})
				self.assertFalse(module.is_done(self.unit, item))
				path = self.unit.dir / relative
				path.parent.mkdir(parents=True, exist_ok=True)
				path.mkdir()
				self.assertEqual(module.outputs(self.unit, item), {})
				self.assertFalse(module.is_done(self.unit, item))
				path.rmdir()
				path.touch()
				self.assertEqual(module.outputs(self.unit, item), files)
				self.assertFalse(module.is_done(self.unit, item))
				path.write_bytes(b"product")
				self.assertEqual(module.outputs(self.unit, item), files)
				self.assertTrue(module.is_done(self.unit, item))
		deck = self.unit.dir / "slides/deck.json"
		deck.write_text("{}", encoding="utf-8")
		self.assertEqual(formats.get_format("slides").outputs(self.unit, "slides"),
			{"deck": "slides/deck.json", "pptx": "slides/deck.pptx"})

	def test_command_building_does_not_run_subprocesses_or_write_artifacts(self):
		before = list(self.unit.dir.rglob("*"))
		with patch("subprocess.Popen", side_effect=AssertionError("unexpected subprocess")):
			stages.analysis_commands(self.unit)
			stages.ingest_commands(self.unit.dir, self.unit.dir.parent)
			for module in formats.list_formats():
				item = "q1" if module.FORMAT["scope"] == "point" else module.FORMAT["id"]
				module.commands(self.unit, item)
		self.assertEqual(list(self.unit.dir.rglob("*")), before)


if __name__ == "__main__":
	unittest.main()
