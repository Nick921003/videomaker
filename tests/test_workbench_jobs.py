from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import wave

from workbench import formats, jobs
from workbench.library import Library, write_json
from tests.workbench_shapes import SHAPES, assert_shape


class TestMarkers(unittest.TestCase):
	def test_parse_table(self):
		for line, expected in (
			("@step validate\n", ("step", "validate")),
			("@unit abc123", ("unit", "abc123")),
			("@error budget 已花 US$0.50", ("error", "budget", "已花 US$0.50")),
			("@error selftest", ("error", "selftest", "")),
			("@warn tts_missing 第 3 句", ("warn", "tts_missing", "第 3 句")),
			("@warn note", ("warn", "note", "")),
			("ordinary output", None), ("prefix @step plan", None),
			("@step", None), ("@step plan extra", None), ("@unit", None),
			("@error", None), ("@other x", None)):
			with self.subTest(line=line):
				self.assertEqual(jobs.parse_marker(line), expected)

	def test_classify_explicit_codes_and_retry_policy(self):
		self.assertEqual(set(jobs.ERRORS), {"gemini_busy", "repair_exhausted", "quote_mismatch",
			"budget", "selftest", "too_large", "interrupted", "unknown"})
		for code in jobs.ERRORS:
			with self.subTest(code=code):
				error = jobs.classify(code, "第 2 句", ["one", "two", "three", "four"])
				assert_shape(error, SHAPES["job_error"])
				self.assertEqual(error["code"], code)
				self.assertEqual(error["retry"], code not in {"budget", "selftest", "too_large"})
		self.assertEqual(jobs.classify("tts_missing", "第 2 句", [])["code"], "unknown")
		self.assertIn("第一個；第二個", jobs.classify("repair_exhausted", "第一個；第二個", [])["reason"])

	def test_classify_fallback_and_unknown_tail(self):
		for tail in ("429", "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "Timeout", "Time out", "timed out"):
			with self.subTest(tail=tail):
				self.assertEqual(jobs.classify(None, "", [tail])["code"], "gemini_busy")
		error = jobs.classify("unrecognized", "detail", ["old", "one", "two", "three"])
		self.assertEqual(error["code"], "unknown")
		self.assertNotIn("old", error["reason"])
		self.assertIn("one\ntwo\nthree", error["reason"])
		self.assertEqual(jobs.classify("budget", "", ["429"])["code"], "budget")


class TestStepTracker(unittest.TestCase):
	def tracker(self):
		return jobs.StepTracker(["selftest", "storyboard", "validate", "repair", "narrate", "render"])

	def test_skip_repair_and_finish(self):
		tracker = self.tracker()
		tracker.enter("validate")
		tracker.enter("narrate")
		self.assertEqual(tracker.current, "narrate")
		tracker.finish(True)
		self.assertEqual([s["state"] for s in tracker.states()],
			["skipped", "skipped", "done", "skipped", "done", "skipped"])
		self.assertIsNone(tracker.current)

	def test_repair_can_return_to_validate(self):
		tracker = self.tracker()
		for step in ("validate", "repair", "validate", "narrate"):
			tracker.enter(step)
		self.assertEqual([s["state"] for s in tracker.states()][2:5], ["done", "done", "running"])
		tracker.finish(False)
		self.assertEqual(tracker.states()[4], {"id": "narrate", "state": "failed"})
		self.assertEqual(tracker.current, "narrate")

	def test_same_step_and_unrecognized_markers(self):
		tracker = self.tracker()
		tracker.enter("render")
		tracker.enter("render")
		tracker.enter("other")
		self.assertEqual(tracker.current, "render")
		self.assertEqual(sum(s["state"] == "running" for s in tracker.states()), 1)


class TestJobQueue(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.library = Library(Path(self.temp.name) / "units")
		self.uid, _ = self.library.create_unit("# 教材\n內容")
		self.directory = self.library.unit_dir(self.uid)
		write_json(self.directory / "plan.json", {"stories": [{"id": "q1", "sec": 60}, {"id": "q2", "sec": 60}]})
		self.commands = []

	def queue(self, runner, registry=formats):
		queue = jobs.JobQueue(self.library, runner, registry)
		self.addCleanup(queue.close)
		return queue

	def wait(self, queue, jid):
		deadline = time.monotonic() + 3
		while time.monotonic() < deadline:
			job = queue.get(jid)
			assert_shape(job, SHAPES["job"])
			if job["state"] in ("done", "failed"):
				return job
			time.sleep(0.005)
		self.fail("工作未結束")

	def fake(self, argv, on_line):
		self.commands.append(argv)
		if Path(argv[1]).name == "author.py":
			for step in ("selftest", "storyboard", "validate", "repair", "validate"):
				on_line("@step " + step)
		for index in range(45):
			on_line(f"line {index}")
		return 0

	def test_registry_commands_markers_shapes_and_log_bound(self):
		queue = self.queue(self.fake)
		jid = queue.enqueue(self.uid, "q1")
		job = self.wait(queue, jid)
		self.assertEqual(job["state"], "done")
		self.assertEqual(job["format"], "video")
		self.assertTrue(all(step["state"] == "done" for step in job["steps"]))
		self.assertEqual(len(job["log"]), 40)
		self.assertEqual(job["log"][-1], "line 44")
		self.assertEqual(len(self.commands), 6)
		self.assertEqual(self.commands[-1][0], str(jobs.PLAYWRIGHT_PY))
		persisted = json.loads((self.directory / "jobs" / (jid + ".json")).read_text())
		self.assertEqual(persisted["state"], "done")
		assert_shape(persisted, SHAPES["job"])
		assert_shape(queue.queue(), SHAPES["queue"])
		job["log"].append("external mutation")
		self.assertNotIn("external mutation", queue.get(jid)["log"])

	def test_one_job_at_a_time_and_queue_snapshots(self):
		entered, release = threading.Event(), threading.Event()
		def runner(argv, on_line):
			self.commands.append(argv)
			entered.set()
			if not release.wait(3):
				raise RuntimeError("測試等待逾時")
			return 0
		queue = self.queue(runner)
		self.addCleanup(release.set)
		first = queue.enqueue(self.uid, "q1")
		self.assertTrue(entered.wait(1))
		second = queue.enqueue(self.uid, "q2")
		snapshot = queue.queue()
		assert_shape(snapshot, SHAPES["queue"])
		self.assertEqual(snapshot["running"]["job_id"], first)
		self.assertEqual([job["job_id"] for job in snapshot["queued"]], [second])
		self.assertEqual(len(self.commands), 1)
		release.set()
		self.assertEqual(self.wait(queue, first)["state"], "done")
		self.assertEqual(self.wait(queue, second)["state"], "done")

	def test_failure_retry_refreshes_resume_commands(self):
		failed = True
		def runner(argv, on_line):
			if failed:
				write_json(self.directory / "q1.failed.json", {"last": {}})
				on_line("@step validate")
				on_line("@error repair_exhausted 問題一；問題二")
				return 2
			return self.fake(argv, on_line)
		queue = self.queue(runner)
		first = queue.enqueue(self.uid, "q1")
		job = self.wait(queue, first)
		self.assertEqual(job["error"]["code"], "repair_exhausted")
		self.assertEqual(job["steps"][2]["state"], "failed")
		failed = False
		second = queue.retry(first)
		self.assertNotEqual(first, second)
		self.assertEqual(self.wait(queue, second)["state"], "done")
		self.assertIn("--resume", self.commands[0])
		with self.assertRaises(ValueError):
			queue.retry(second)

	def test_nonretryable_and_unmarked_failures(self):
		for code, line in (("budget", "@error budget 上限"), ("gemini_busy", "HTTP 429"), ("unknown", "bad input")):
			with self.subTest(code=code):
				def runner(argv, on_line):
					on_line(line)
					return 1
				queue = self.queue(runner)
				jid = queue.enqueue(self.uid, "q1")
				self.assertEqual(self.wait(queue, jid)["error"]["code"], code)
				if code == "budget":
					with self.assertRaises(ValueError):
						queue.retry(jid)
				queue.close()

	def test_runner_exception_fails_and_next_job_runs(self):
		calls = 0
		def runner(argv, on_line):
			nonlocal calls
			calls += 1
			if calls == 1:
				raise OSError("missing executable")
			return 0
		queue = self.queue(runner)
		first = queue.enqueue(self.uid, "q1")
		second = queue.enqueue(self.uid, "q2")
		self.assertEqual(self.wait(queue, first)["state"], "failed")
		self.assertEqual(self.wait(queue, second)["state"], "done")

	def test_spent_is_usage_delta_including_tts(self):
		(self.directory / "usage.jsonl").write_text('{"usd":0.2}\n', encoding="utf-8")
		def runner(argv, on_line):
			with (self.directory / "usage.jsonl").open("a") as handle:
				handle.write('{"usd":0.01}\n{bad}\n{"usd":NaN}\n')
			voice = self.directory / "q1/voice"
			voice.mkdir(parents=True, exist_ok=True)
			with (voice / "tts_usage.jsonl").open("a") as handle:
				handle.write('{"usd":0.002}\n')
			return 0
		queue = self.queue(runner)
		job = self.wait(queue, queue.enqueue(self.uid, "q1"))
		self.assertAlmostEqual(job["spent_usd"], 6 * 0.012)

	def test_restored_running_job_preserves_spending(self):
		(self.directory / "usage.jsonl").write_text('{"usd":0.20}\n{"usd":0.05}\n', encoding="utf-8")
		jid = "a" * 32
		write_json(self.directory / "jobs" / (jid + ".json"), {
			"job_id": jid, "unit_id": self.uid, "item": "q1", "format": "video", "state": "running",
			"steps": [{"id": "storyboard", "state": "running"}], "current": "storyboard",
			"log": [], "spent_usd": 0, "error": None, "_before": 0.20})
		queue = self.queue(self.fake)
		job = queue.get(jid)
		self.assertEqual(job["error"]["code"], "interrupted")
		self.assertAlmostEqual(job["spent_usd"], 0.05)

	def test_ingest_unit_marker_excludes_existing_usage(self):
		(self.directory / "usage.jsonl").write_text('{"usd":0.20}\n', encoding="utf-8")
		def runner(argv, on_line):
			with (self.directory / "usage.jsonl").open("a") as handle:
				handle.write('{"usd":0.01}\n')
			on_line("@unit " + self.uid)
			return 0
		queue = self.queue(runner)
		jid = queue.enqueue_stage(None, "ingest", [formats.Command("normalize", ["normalize.py"])])
		self.assertAlmostEqual(self.wait(queue, jid)["spent_usd"], 0.01)

	def test_error_marker_stops_pipeline_even_with_legacy_zero_exit(self):
		def runner(argv, on_line):
			self.commands.append(argv)
			on_line("@error selftest 元件不正確")
			return 0
		queue = self.queue(runner)
		jid = queue.enqueue_stage(self.uid, "analysis", [formats.Command("selftest", ["test.py"]), formats.Command("plan", ["test.py"])])
		job = self.wait(queue, jid)
		self.assertEqual(job["state"], "failed")
		self.assertEqual(job["error"]["code"], "selftest")
		self.assertEqual(len(self.commands), 1)

	def test_warnings_are_persisted_without_failing_and_legacy_marker_is_a_warning(self):
		def runner(argv, on_line):
			on_line("@warn tts_missing 第 3 句")
			on_line("@warn note 可繼續")
			on_line("@error tts_missing 第 5 句")
			return 0
		queue = self.queue(runner)
		jid = queue.enqueue_stage(self.uid, "analysis", [formats.Command("plan", ["test.py"])])
		job = self.wait(queue, jid)
		self.assertEqual(job["state"], "done")
		self.assertIsNone(job["error"])
		self.assertEqual(job["warnings"], [{"code": "tts_missing", "detail": "第 3 句"},
			{"code": "note", "detail": "可繼續"}, {"code": "tts_missing", "detail": "第 5 句"}])
		queue.close()
		restored = self.queue(self.fake)
		self.assertEqual(restored.get(jid)["warnings"], job["warnings"])

	def test_analysis_and_ingest_unit_marker_persistence(self):
		queue = self.queue(self.fake)
		view = formats.UnitView(self.uid, self.directory, self.library.plan(self.uid))
		analysis = queue.enqueue_stage(self.uid, "analysis", formats.stages.analysis_commands(view))
		job = self.wait(queue, analysis)
		self.assertEqual((job["item"], job["format"]), ("analysis", "analysis"))
		self.assertEqual([s["id"] for s in job["steps"]], ["selftest", "plan"])
		queue.close()
		entered, release = threading.Event(), threading.Event()
		def runner(argv, on_line):
			entered.set()
			release.wait(3)
			on_line("@unit " + self.uid)
			return 0
		queue = self.queue(runner)
		self.addCleanup(release.set)
		jid = queue.enqueue_stage(None, "ingest", [formats.Command("normalize", ["normalize.py"])])
		self.assertTrue(entered.wait(1))
		path = self.library.root.parent / "jobs" / (jid + ".json")
		self.assertTrue(path.is_file())
		release.set()
		self.assertEqual(self.wait(queue, jid)["unit_id"], self.uid)
		queue.close()
		restored = self.queue(self.fake)
		assert_shape(restored.get(jid), SHAPES["job"])
		self.assertEqual(restored.get(jid)["unit_id"], self.uid)

	def test_restore_interrupted_jobs_and_ignore_corrupt_files(self):
		for index, state in enumerate(("queued", "running", "done", "failed")):
			jid = f"{index:032x}"
			write_json(self.directory / "jobs" / (jid + ".json"), {
				"job_id": jid, "unit_id": self.uid, "item": "q1", "format": "video", "state": state,
				"steps": [{"id": "storyboard", "state": "running"}], "current": "storyboard",
				"log": [], "spent_usd": 0, "error": None})
		(self.directory / "jobs" / ("f" * 32 + ".json")).write_text("{", encoding="utf-8")
		queue = self.queue(self.fake)
		for index in (0, 1):
			job = queue.get(f"{index:032x}")
			assert_shape(job, SHAPES["job"])
			self.assertEqual(job["state"], "failed")
			self.assertEqual(job["error"]["code"], "interrupted")
			self.assertEqual(job["steps"][0]["state"], "failed")
		self.assertEqual(queue.get(f"{2:032x}")["state"], "done")
		self.assertEqual(self.commands, [])

	def test_restore_unitless_stage_can_retry(self):
		queue = self.queue(lambda argv, on_line: 1)
		jid = queue.enqueue_stage(None, "ingest", [formats.Command("normalize", ["normalize.py"])])
		self.wait(queue, jid)
		queue.close()
		queue = self.queue(self.fake)
		self.assertEqual(self.wait(queue, queue.retry(jid))["state"], "done")

	def test_restore_rejects_jobs_that_break_shapes(self):
		base = {"unit_id": self.uid, "item": "q1", "format": "video", "state": "failed",
			"steps": [{"id": "storyboard", "state": "failed"}], "current": "storyboard",
			"log": [], "spent_usd": 0, "error": jobs.classify("budget", "", [])}
		changes = ({"steps": [{"id": "storyboard", "state": "weird"}]}, {"log": [3]},
			{"spent_usd": True}, {"error": {"code": "unknown"}}, {"item": None}, {"warnings": None}, {"warnings": [{"code": 1, "detail": "bad"}]})
		for index, changed in enumerate(changes):
			jid = f"{index:032x}"
			write_json(self.directory / "jobs" / (jid + ".json"), {**base, **changed, "job_id": jid})
		queue = self.queue(self.fake)
		for index in range(len(changes)):
			with self.subTest(index=index), self.assertRaises(KeyError):
				queue.get(f"{index:032x}")

	def test_closed_queue_rejects_new_work(self):
		queue = self.queue(self.fake)
		queue.close()
		queue.close()
		with self.assertRaises(ValueError):
			queue.enqueue(self.uid, "q1")

	def test_default_runner_environment(self):
		with patch.object(jobs.subprocess, "Popen") as popen:
			process = popen.return_value.__enter__.return_value
			process.stdout = iter(["@step plan\n", "hello\n"])
			process.wait.return_value = 0
			lines = []
			with patch.dict(os.environ, {"JOB_TEST": "kept", "VIDEO_ENGINE_LLM": "old"}):
				self.assertEqual(jobs.run_command(["python", "test.py"], lines.append), 0)
			self.assertEqual(popen.call_args.kwargs["env"]["VIDEO_ENGINE_LLM"], formats.MODEL)
			self.assertEqual(popen.call_args.kwargs["env"]["JOB_TEST"], "kept")
			self.assertEqual(lines, ["@step plan", "hello"])


class TestCLIMarkers(unittest.TestCase):
	def load(self, name):
		path = Path(__file__).resolve().parents[1] / "video_engine/board" / (name + ".py")
		spec = importlib.util.spec_from_file_location("workbench_test_" + name, path)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		return module

	def test_selftest_failure_marker_preserves_exit_and_first_problem(self):
		module = self.load("selftest")
		output = io.StringIO()
		with redirect_stdout(output), patch.object(module.sys, "argv", ["selftest.py", "--force"]), \
			patch.object(module, "stamp", return_value="test"), \
			patch.object(module.BC, "load_catalog", return_value={}), \
			patch.object(module, "corpus", return_value=[("fixture", "strict", "scene", "unused")]), \
			patch.object(module, "run_one", return_value=("fixture", "strict", ["第一個錯誤", "第二個錯誤"], None)), \
			patch.object(module.glob, "glob", return_value=[]), patch.object(module, "coverage", return_value=[]), \
			patch.object(module, "print", wraps=print, create=True) as printed:
			with self.assertRaises(SystemExit) as error:
				module.main()
		self.assertEqual(error.exception.code, 1)
		self.assertIn("@error selftest 第一個錯誤", output.getvalue())
		marker = next(call for call in printed.call_args_list if str(call.args[0]).startswith("@error"))
		self.assertTrue(marker.kwargs["flush"])

	def test_narrate_missing_words_marker_preserves_outputs_and_success_exit(self):
		module = self.load("narrate")
		with tempfile.TemporaryDirectory() as directory:
			scene = Path(directory) / "scene.json"
			write_json(scene, {"scenes": [{"beats": [{"say": "先看看畫面"}]}]})
			voice = Path(directory) / "voice"
			def synth(text, wav, *args):
				with wave.open(wav, "wb") as handle:
					handle.setnchannels(1)
					handle.setsampwidth(2)
					handle.setframerate(24000)
					handle.writeframes(b"\0\0" * 12000)
				return {}, True, {"usd": 0.001}
			def asr(jobs, out):
				return {job["wav"]: {"ok": False, "problems": ["漏字"], "missing": ["畫面"], "heard": "先看看"} for job in jobs}
			output = io.StringIO()
			with redirect_stdout(output), patch.object(module.sys, "argv", ["narrate.py", str(scene), str(voice), "--english", "off"]), \
				patch("llm.load_env"), patch.object(module.gemini_tts, "synth_gemini", side_effect=synth) as called, \
				patch.object(module, "asr_check", side_effect=asr), \
				patch.object(module, "print", wraps=print, create=True) as printed:
				self.assertIsNone(module.main())
			self.assertEqual(called.call_count, module.MAX_ROUNDS)
			self.assertIn("@warn tts_missing 第 1 句", output.getvalue())
			self.assertNotIn("@error", output.getvalue())
			marker = next(call for call in printed.call_args_list if str(call.args[0]).startswith("@warn"))
			self.assertTrue(marker.kwargs["flush"])
			self.assertTrue((voice / "master.wav").is_file())
			self.assertTrue((voice / "timing.json").is_file())
			self.assertFalse(json.loads((voice / "narration.json").read_text())["beats"][0]["ok"])


if __name__ == "__main__":
	unittest.main()
