import hashlib
import http.client
import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from video_engine.board import studio_server as BS


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "video_engine/out/author_20261004f/plan.json"
PLAN = {
	"unit_title": "第一支程式", "scope": {"covers": ["編譯流程"], "not_covers": ["指標與動態記憶體配置"]},
	"stories": [
		{"id": "q1", "question": "為什麼只裝編輯器還不能執行程式？", "also_asks": ["編輯器跟編譯器到底差在哪裡？"],
			"title": "工具分工", "sec": 60, "objectives": [1], "screens": [], "show": "展示工具分工"},
		{"id": "q2", "question": "為什麼終端機找不到指令？", "also_asks": ["環境變數是什麼意思？"],
			"title": "環境設定", "sec": 75, "objectives": [2], "screens": ["win11.search"], "show": "展示搜尋步驟"},
		{"id": "q3", "question": "編譯的四個階段是什麼？", "also_asks": [],
			"title": "編譯流程", "sec": 70, "objectives": [3], "screens": [], "show": "展示生產線"}],
	"highlight": {"question": "這個單元的核心觀念有哪些？", "also_asks": ["快速複習全部內容"],
		"stories": ["q1", "q2", "q3"], "total_sec": 205, "why": "串起核心觀念"}}


def write_json(path, value):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class FakeRunner:
	def __init__(self):
		self.commands = []
		self.fail = None
		self.fail_target = None
		self.entered = threading.Event()
		self.release = threading.Event()
		self.release.set()
		self.export_entered = threading.Event()
		self.export_release = threading.Event()
		self.export_release.set()

	def __call__(self, command, log):
		self.commands.append(command)
		self.entered.set()
		if not self.release.wait(5):
			raise RuntimeError("測試 runner 等待逾時")
		cli = Path(command[1]).name
		for n in range(45):
			log(f"測試輸出 {n}")
		if cli == self.fail and (self.fail_target is None or any(self.fail_target in Path(arg).parts for arg in command[2:])):
			if cli == "export.py":
				Path(command[3]).write_bytes(b"partial mp4")
			return 2
		if cli == "author.py":
			directory = Path(command[4])
			if command[2] == "plan":
				write_json(directory / "plan.json", PLAN)
			else:
				write_json(directory / (command[5] + ".scene.json"), {"version": 1})
			with (directory / "usage.jsonl").open("a", encoding="utf-8") as handle:
				handle.write(json.dumps({"usd": 0.015 if command[2] == "plan" else 0.025}) + "\n")
		elif cli == "compose.py":
			write_json(Path(command[4]), {"version": 1})
		elif cli == "narrate.py":
			directory = Path(command[3])
			write_json(directory / "timing.json", [{"t0": 0.2, "t1": 61}])
			(directory / "master.wav").write_bytes(b"fake audio")
		elif cli == "compile.py":
			write_json(Path(command[3]), {"duration": 61.2})
		elif cli == "build.py":
			directory = Path(command[3])
			directory.mkdir(parents=True, exist_ok=True)
			(directory / "player.html").write_text("測試播放器", encoding="utf-8")
		elif cli == "export.py":
			Path(command[3]).write_bytes(b"fake mp4")
			write_json(Path(command[3]).with_suffix(".export.json"), {"duration": 61.2})
			self.export_entered.set()
			if not self.export_release.wait(5):
				raise RuntimeError("測試出片等待逾時")
		return 0


class TestStudio(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.out = Path(self.temp.name) / "units"
		self.runner = FakeRunner()
		self.health_calls = []
		self.tts_up = True
		self.studio = BS.Studio(self.out, command_runner=self.runner, tts_checker=self.health, tts_mode="sovits")
		self.addCleanup(self.studio.close)
		self.static = Path(self.temp.name) / "studio"
		self.static.mkdir()
		(self.static / "index.html").write_text("影片工作室", encoding="utf-8")
		(self.static / "app.js").write_text("const ready = true;", encoding="utf-8")
		shutil.copyfile(ROOT / "video_engine/board/studio/pipelines.json", self.static / "pipelines.json")
		self.server = BS.StudioHTTPServer(("127.0.0.1", 0), self.studio, studio_dir=self.static)
		self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
		self.thread.start()
		self.addCleanup(self.stop_http)

	def stop_http(self):
		self.server.shutdown()
		self.server.server_close()
		self.thread.join(2)

	def health(self):
		self.health_calls.append(True)
		return self.tts_up

	def request(self, method, path, payload=None, headers=None):
		connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
		try:
			body = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
			connection.request(method, path, body=body, headers=headers or {})
			response = connection.getresponse()
			return response.status, dict(response.getheaders()), response.read()
		finally:
			connection.close()

	def api(self, method, path, payload=None, expected=200):
		status, headers, body = self.request(method, path, payload)
		self.assertEqual(status, expected, body)
		self.assertIn("application/json", headers["Content-Type"])
		return json.loads(body)

	def unit(self, planned=True, fixture=False):
		result = self.api("POST", "/api/units", {"markdown": "# 第一支程式\nC 語言教材。", "title": "測試教材"})
		unit = result["unit_id"]
		directory = self.out / unit
		if planned:
			if fixture and FIXTURE.exists():
				shutil.copyfile(FIXTURE, directory / "plan.json")
			else:
				write_json(directory / "plan.json", PLAN)
		return unit, directory

	def wait_job(self, job_id):
		deadline = time.monotonic() + 5
		while time.monotonic() < deadline:
			job = self.api("GET", "/api/jobs/" + job_id)
			if job["state"] in ("done", "failed"):
				return job
			time.sleep(0.01)
		self.fail("工作未結束")

	def test_unit_id_hash_reuse_and_listing_without_plan(self):
		markdown = "# 同一份教材\n內容含空白。\n"
		first = self.api("POST", "/api/units", {"markdown": markdown})
		self.assertTrue(first["created"])
		self.assertEqual(first["unit_id"], hashlib.sha256(markdown.encode()).hexdigest()[:12])
		meta = (self.out / first["unit_id"] / "meta.json").read_bytes()
		second = self.api("POST", "/api/units", {"markdown": markdown, "title": "不同標題"})
		self.assertEqual(second, {"unit_id": first["unit_id"], "created": False})
		self.assertEqual(meta, (self.out / first["unit_id"] / "meta.json").read_bytes())
		listing = self.api("GET", "/api/units")
		self.assertEqual(len(listing), 1)
		self.assertEqual(listing[0]["title"], "同一份教材")
		self.assertEqual(set(listing[0]), {"unit_id", "title", "created_at", "planned", "videos", "spent_usd"})
		self.assertFalse(listing[0]["planned"])
		self.assertEqual(listing[0]["videos"], 0)
		detail = self.api("GET", "/api/units/" + first["unit_id"])
		self.assertIsNone(detail["plan"])
		self.assertEqual(detail["jobs"], [])
		self.assertFalse(detail["planned"])

	def test_fixture_detail_estimates_and_usage(self):
		unit, directory = self.unit(fixture=True)
		(directory / "usage.jsonl").write_text('{"usd":0.015}\n{"usd":0.025}\n', encoding="utf-8")
		detail = self.api("GET", "/api/units/" + unit)
		self.assertTrue(detail["planned"])
		self.assertAlmostEqual(detail["spent_usd"], 0.04)
		self.assertIn("scope", detail["plan"])
		stories = detail["plan"]["stories"]
		for story in stories:
			for key in ("id", "question", "also_asks", "title", "sec", "objectives", "screens", "show"):
				self.assertIn(key, story)
			self.assertEqual(story["status"], "none")
			self.assertIsNone(story["video"])
			self.assertIsNone(story["duration"])
			self.assertIsNone(story["cost_usd"])
			self.assertEqual(story["estimate_usd"], BS.ESTIMATE_USD)
		highlight_ids = detail["plan"]["highlight"]["stories"]
		self.assertAlmostEqual(detail["plan"]["highlight"]["estimate_usd"], BS.ESTIMATE_USD * len(highlight_ids))
		q = highlight_ids[0]
		(directory / q).mkdir()
		(directory / q / "video.mp4").write_bytes(b"video")
		write_json(directory / q / "video.export.json", {"duration": 61.2})
		detail = self.api("GET", "/api/units/" + unit)
		story = next(s for s in detail["plan"]["stories"] if s["id"] == q)
		self.assertEqual(story["status"], "done")
		self.assertEqual(story["video"], f"/media/{unit}/{q}/video.mp4")
		self.assertEqual(story["duration"], 61.2)
		self.assertEqual(story["estimate_usd"], 0)
		self.assertAlmostEqual(detail["plan"]["highlight"]["estimate_usd"], BS.ESTIMATE_USD * (len(highlight_ids) - 1))
		self.assertEqual(self.api("GET", "/api/units")[0]["videos"], 1)

	def test_ask_alias_highlight_scope_and_no_match(self):
		unit, directory = self.unit()
		for question, kind, story in (
			("編輯器跟編譯器到底差在哪裡？", "story", "q1"),
			("請整理重點", "highlight", None),
			("整個單元我都看不懂", "highlight", None),
			("快速複習全部內容", "highlight", None),
			("這個單元的核心觀念有哪些？", "highlight", None),
			("指標與動態記憶體配置", "out_of_scope", None),
			("Python", "out_of_scope", None),
			("今晚的月亮好圓", "no_match", None)):
			with self.subTest(question=question):
				answer = self.api("POST", "/api/ask", {"unit_id": unit, "question": question})
				self.assertEqual(answer["kind"], kind)
				self.assertEqual(answer["story"], story)
				self.assertIsNone(answer["video"])
				self.assertIsInstance(answer["score"], (int, float))
				self.assertTrue(answer["reason"])
		(directory / "q1").mkdir()
		(directory / "q1/video.mp4").write_bytes(b"video")
		answer = self.api("POST", "/api/ask", {"unit_id": unit, "question": PLAN["stories"][0]["also_asks"][0]})
		self.assertEqual(answer["video"], f"/media/{unit}/q1/video.mp4")
		self.assertEqual(self.runner.commands, [])

	def test_plan_job_reuse_and_story_cli_order(self):
		unit, directory = self.unit(planned=False)
		self.runner.release.clear()
		job_id = self.api("POST", f"/api/units/{unit}/plan")["job_id"]
		self.assertTrue(self.runner.entered.wait(2))
		self.assertEqual(self.api("POST", f"/api/units/{unit}/plan")["job_id"], job_id)
		self.runner.release.set()
		self.assertEqual(self.wait_job(job_id)["state"], "done")
		self.assertEqual(self.api("POST", f"/api/units/{unit}/plan"), {"job_id": None, "planned": True})
		job_id = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q2", "q1", "q2"]})["job_id"]
		job = self.wait_job(job_id)
		self.assertEqual(job["state"], "done", job)
		self.assertEqual([Path(c[1]).name for c in self.runner.commands], ["selftest.py", "author.py"] +
			["author.py", "narrate.py", "compile.py", "build.py", "check.py", "export.py"] * 2)
		self.assertEqual(self.runner.commands[0][2:], ["--quick"])
		self.assertEqual(self.runner.commands[2][5], "q2")
		self.assertEqual(self.runner.commands[8][5], "q1")
		for command in self.runner.commands:
			cli = Path(command[1]).name
			self.assertEqual(command[0], str(BS.PLAYWRIGHT_PY if cli in ("check.py", "export.py") else BS.PROJECT_PY))
			if cli == "author.py":
				self.assertEqual(command[command.index("--model") + 1], "google:gemini-3.8-flash")
				self.assertEqual(command[command.index("--budget-usd") + 1], "0.50")
		self.assertEqual(self.runner.commands[3][2:], [str(directory / "q2.scene.json"), str(directory / "q2/voice"), "--tts", "sovits"])
		self.assertIn("--timing", self.runner.commands[4])
		self.assertIn("--audio", self.runner.commands[5])
		self.assertEqual(self.runner.commands[7][2:], [str(directory / "q2/player"), str(directory / "q2/video.mp4")])
		self.assertEqual(len(self.health_calls), 3)
		self.assertLessEqual(len(job["log"]), 40)
		self.assertIn("測試輸出 44", job["log"])
		self.assertAlmostEqual(job["spent_usd"], 0.065)
		persisted = json.loads((directory / "jobs" / (job_id + ".json")).read_text(encoding="utf-8"))
		self.assertEqual(persisted["state"], "done")
		detail = self.api("GET", "/api/units/" + unit)
		self.assertIn(job_id, detail["jobs"])
		self.assertEqual(detail["plan"]["stories"][0]["cost_usd"], 0.025)
		self.assertEqual(self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1", "q2"]}), {"job_id": None})

	def test_highlight_only_generates_missing_scenes(self):
		unit, directory = self.unit()
		write_json(directory / "q1.scene.json", {"version": 1})
		job_id = self.api("POST", f"/api/units/{unit}/videos", {"highlight": True})["job_id"]
		job = self.wait_job(job_id)
		self.assertEqual(job["state"], "done", job)
		self.assertEqual([Path(c[1]).name for c in self.runner.commands],
			["author.py", "author.py", "compose.py", "narrate.py", "compile.py", "build.py", "check.py", "export.py"])
		self.assertEqual([c[5] for c in self.runner.commands[:2]], ["q2", "q3"])
		self.assertEqual(self.runner.commands[2][2:], [str(directory / "plan.json"), str(directory), str(directory / "highlight.scene.json")])
		self.assertFalse((directory / "q2/video.mp4").exists())
		self.assertTrue((directory / "highlight/video.mp4").exists())
		detail = self.api("GET", "/api/units/" + unit)
		self.assertEqual(detail["plan"]["highlight"]["estimate_usd"], 0)
		self.assertEqual(detail["plan"]["highlight"]["status"], "done")
		self.assertEqual(self.api("POST", f"/api/units/{unit}/videos", {"highlight": True}), {"job_id": None})

	def test_single_queue_and_active_status(self):
		unit, directory = self.unit()
		self.runner.release.clear()
		first = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"]
		self.assertTrue(self.runner.entered.wait(2))
		second = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q2"]})["job_id"]
		self.assertEqual(self.api("GET", "/api/jobs/" + second)["state"], "queued")
		self.assertEqual(len(self.runner.commands), 1)
		stories = self.api("GET", "/api/units/" + unit)["plan"]["stories"]
		self.assertEqual([s["status"] for s in stories], ["running", "queued", "none"])
		self.runner.release.set()
		self.assertEqual(self.wait_job(first)["state"], "done")
		self.assertEqual(self.wait_job(second)["state"], "done")

	def test_tts_failure_and_command_failure_stop_the_job(self):
		unit, directory = self.unit()
		self.tts_up = False
		job_id = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"]
		job = self.wait_job(job_id)
		self.assertEqual(job["state"], "failed")
		self.assertEqual(job["error"], "配音伺服器沒開（:9880）")
		self.assertEqual([Path(c[1]).name for c in self.runner.commands], ["author.py"])
		self.tts_up = True
		self.runner.fail = "check.py"
		job_id = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"]
		job = self.wait_job(job_id)
		self.assertEqual(job["state"], "failed")
		self.assertIn("驗證", job["error"])
		self.assertNotIn("export.py", [Path(c[1]).name for c in self.runner.commands])
		self.assertEqual(sum(Path(c[1]).name == "author.py" for c in self.runner.commands), 1)
		self.assertEqual(self.api("GET", "/api/units/" + unit)["plan"]["stories"][0]["status"], "failed")

	def test_overlap_job_failure_preserves_reused_video(self):
		unit, _ = self.unit()
		self.runner.release.clear()
		self.runner.fail, self.runner.fail_target = "check.py", "q2"
		first = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"]
		self.assertTrue(self.runner.entered.wait(2))
		second = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q2", "q1"]})["job_id"]
		self.runner.release.set()
		self.assertEqual(self.wait_job(first)["state"], "done")
		self.assertEqual(self.wait_job(second)["state"], "failed")
		stories = self.api("GET", "/api/units/" + unit)["plan"]["stories"]
		self.assertEqual(stories[0]["status"], "done")
		self.assertEqual(stories[0]["video"], f"/media/{unit}/q1/video.mp4")
		self.assertEqual(stories[1]["status"], "failed")
		self.assertEqual(sum(Path(c[1]).name == "export.py" for c in self.runner.commands), 1)

	def test_successful_overlap_does_not_narrate_or_export_twice(self):
		unit, _ = self.unit()
		self.runner.release.clear()
		self.addCleanup(self.runner.release.set)
		first = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"]
		self.assertTrue(self.runner.entered.wait(2))
		second = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1", "q2"]})["job_id"]
		self.runner.release.set()
		self.assertEqual(self.wait_job(first)["state"], "done")
		self.assertEqual(self.wait_job(second)["state"], "done")
		for cli in ("narrate.py", "export.py"):
			self.assertEqual(sum(Path(c[1]).name == cli for c in self.runner.commands), 2)

	def test_generated_scenes_have_no_remaining_model_estimate(self):
		unit, directory = self.unit()
		for story in PLAN["stories"]:
			write_json(directory / (story["id"] + ".scene.json"), {"version": 1})
		plan = self.api("GET", "/api/units/" + unit)["plan"]
		self.assertEqual(plan["highlight"]["estimate_usd"], 0)
		self.assertTrue(all(story["estimate_usd"] == 0 for story in plan["stories"]))
		self.assertTrue(all(story["status"] == "none" for story in plan["stories"]))

	def test_only_current_story_runs_while_remaining_stories_queue(self):
		unit, _ = self.unit()
		self.runner.release.clear()
		self.addCleanup(self.runner.release.set)
		job_id = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1", "q2", "q3"]})["job_id"]
		self.assertTrue(self.runner.entered.wait(2))
		stories = self.api("GET", "/api/units/" + unit)["plan"]["stories"]
		self.assertEqual([story["status"] for story in stories], ["running", "queued", "queued"])
		self.runner.release.set()
		self.assertEqual(self.wait_job(job_id)["state"], "done")

	def test_partial_export_is_unavailable_and_can_be_retried(self):
		unit, directory = self.unit()
		self.runner.fail = "export.py"
		job = self.wait_job(self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"])
		self.assertEqual(job["state"], "failed")
		self.assertTrue((directory / "q1/video.mp4").exists())
		story = self.api("GET", "/api/units/" + unit)["plan"]["stories"][0]
		self.assertEqual(story["status"], "failed")
		self.assertIsNone(story["video"])
		self.runner.fail = None
		job = self.wait_job(self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"])
		self.assertEqual(job["state"], "done")
		self.assertEqual(self.api("GET", "/api/units/" + unit)["plan"]["stories"][0]["status"], "done")

	def test_plan_selftest_failure_does_not_call_author(self):
		unit, _ = self.unit(planned=False)
		self.runner.fail = "selftest.py"
		job = self.wait_job(self.api("POST", f"/api/units/{unit}/plan")["job_id"])
		self.assertEqual(job["state"], "failed")
		self.assertEqual([Path(c[1]).name for c in self.runner.commands], ["selftest.py"])

	def test_running_export_is_not_a_completed_video(self):
		unit, _ = self.unit()
		self.runner.export_release.clear()
		self.addCleanup(self.runner.export_release.set)
		job_id = self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"]
		self.assertTrue(self.runner.export_entered.wait(2))
		self.assertEqual(self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]})["job_id"], job_id)
		story = self.api("GET", "/api/units/" + unit)["plan"]["stories"][0]
		self.assertEqual(story["status"], "running")
		self.assertIsNone(story["video"])
		self.runner.export_release.set()
		self.assertEqual(self.wait_job(job_id)["state"], "done")

	def test_restart_marks_unfinished_jobs_failed(self):
		unit, directory = self.unit()
		self.studio.close()
		for n, state in enumerate(("queued", "running", "done")):
			write_json(directory / "jobs" / (f"{n:032x}.json"), {
				"job_id": f"{n:032x}", "unit_id": unit, "kind": "plan", "state": state,
				"stage": "規劃", "log": [], "spent_usd": 0, "error": None})
		restored = BS.Studio(self.out, command_runner=self.runner, tts_checker=self.health, tts_mode="sovits")
		self.addCleanup(restored.close)
		for n in (0, 1):
			job = restored.get_job(f"{n:032x}")
			self.assertEqual(job["state"], "failed")
			self.assertIn("重啟", job["error"])
			self.assertEqual(json.loads((directory / "jobs" / (f"{n:032x}.json")).read_text())["state"], "failed")
		self.assertEqual(restored.get_job(f"{2:032x}")["state"], "done")
		self.assertEqual(self.runner.commands, [])

	def test_corrupt_job_does_not_prevent_other_jobs_recovering(self):
		unit, directory = self.unit()
		self.studio.close()
		job_id = "f" * 32
		write_json(directory / "jobs" / (job_id + ".json"), {
			"job_id": job_id, "unit_id": unit, "kind": "plan", "state": "running", "stage": "規劃", "log": []})
		(directory / "jobs" / ("0" * 32 + ".json")).write_text("{", encoding="utf-8")
		restored = BS.Studio(self.out, command_runner=self.runner, tts_checker=self.health, tts_mode="sovits")
		self.addCleanup(restored.close)
		self.assertEqual(restored.get_job(job_id)["state"], "failed")
		self.assertEqual(self.runner.commands, [])

	def test_static_media_range_and_traversal(self):
		unit, directory = self.unit()
		(directory / "q1").mkdir()
		(directory / "q1/video.mp4").write_bytes(b"0123456789")
		status, headers, body = self.request("GET", f"/media/{unit}/q1/video.mp4", headers={"Range": "bytes=2-5"})
		self.assertEqual((status, body), (206, b"2345"))
		self.assertEqual(headers["Content-Range"], "bytes 2-5/10")
		self.assertEqual(headers["Content-Type"], "video/mp4")
		self.assertEqual(headers["Content-Length"], "4")
		for value, expected in (("bytes=7-", b"789"), ("bytes=-3", b"789")):
			status, _, body = self.request("GET", f"/media/{unit}/q1/video.mp4", headers={"Range": value})
			self.assertEqual((status, body), (206, expected))
		status, headers, _ = self.request("GET", f"/media/{unit}/q1/video.mp4", headers={"Range": "bytes=20-30"})
		self.assertEqual(status, 416)
		self.assertEqual(headers["Content-Range"], "bytes */10")
		status, headers, _ = self.request("GET", "/?mock=1")
		self.assertEqual((status, headers["Location"]), (302, "/studio/index.html?mock=1"))
		self.assertEqual(self.request("GET", "/studio/index.html")[2].decode(), "影片工作室")
		self.assertEqual(self.request("GET", "/studio/app.js")[0], 200)
		self.assertIn("application/json", self.request("GET", f"/media/{unit}/plan.json")[1]["Content-Type"])
		(directory / "escape").symlink_to(self.static / "index.html")
		for path in ("/studio/%2e%2e/studio_server.py", f"/media/{unit}/../other/meta.json", f"/media/{unit}/escape"):
			with self.subTest(path=path):
				self.api("GET", path, expected=404)

	def test_validation_and_pipeline_shape(self):
		self.api("POST", "/api/units", {"markdown": " "}, expected=400)
		self.api("POST", "/api/units", [], expected=400)
		self.api("GET", "/api/units/000000000000", expected=404)
		self.api("GET", "/api/jobs/missing", expected=404)
		unit, _ = self.unit(planned=False)
		self.api("POST", f"/api/units/{unit}/videos", {"stories": ["q1"]}, expected=409)
		self.api("POST", "/api/ask", {"unit_id": unit, "question": "問題"}, expected=409)
		unit, _ = self.unit()
		for payload in ({"stories": ["../q1"]}, {"stories": "q1"}, {"highlight": False}, {"stories": ["q1"], "highlight": True}):
			self.api("POST", f"/api/units/{unit}/videos", payload, expected=400)
		formats = self.api("GET", "/api/pipelines")["formats"]
		self.assertEqual({f["id"] for f in formats}, {"video", "mindmap", "slides"})
		for item in formats:
			self.assertTrue(item["total"])
			for step in item["steps"]:
				self.assertEqual(set(step), {"name", "model", "cost", "detail"})
		self.assertEqual(formats[0]["steps"][0]["model"], "google:gemini-3.8-flash")

	def test_deep_json_returns_json_error(self):
		connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
		self.addCleanup(connection.close)
		connection.request("POST", "/api/units", body='{"unused":' + '[' * 1100 + '0' + ']' * 1100 + '}')
		response = connection.getresponse()
		self.assertEqual(response.status, 400)
		self.assertIn("error", json.loads(response.read()))


class TestTTSHealth(unittest.TestCase):
	def test_http_500_is_up_and_refused_is_down(self):
		with patch.object(BS.http.client, "HTTPConnection") as connection:
			connection.return_value.getresponse.return_value.status = 500
			self.assertTrue(BS.tts_health())
			connection.assert_called_with("127.0.0.1", 9880, timeout=3)
			connection.return_value.request.assert_called_with("GET", "/tts")
			connection.return_value.request.side_effect = ConnectionRefusedError()
			self.assertFalse(BS.tts_health())


	def test_gemini_配音不需要本機伺服器且花費含配音(self):
		root = Path(tempfile.mkdtemp())
		gem = BS.Studio(root / "gem", command_runner=lambda *a, **k: 0, tts_checker=lambda: False, tts_mode="gemini")
		try:
			self.assertTrue(gem.tts_available)
		finally:
			gem.close()
		directory = root / "spent"
		(directory / "q1" / "voice").mkdir(parents=True)
		(directory / "usage.jsonl").write_text('{"usd": 0.1}\n', encoding="utf-8")
		(directory / "q1" / "voice" / "tts_usage.jsonl").write_text('{"usd": 0.02}\n{"usd": 0.01}\n', encoding="utf-8")
		self.assertAlmostEqual(BS.spent_usd(directory), 0.13)


if __name__ == "__main__":
	unittest.main()
