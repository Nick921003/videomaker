import hashlib
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile

from workbench import server as BS
from workbench.library import Library, read_json, write_json
from tests.fixtures.make_pptx import make
from tests.workbench_shapes import SHAPES, assert_shape


PLAN = {
	"unit_title": "第一支程式", "scope": {"covers": ["編譯流程"], "not_covers": ["指標與動態記憶體配置"]},
	"stories": [
		{"id": "q1", "question": "為什麼只裝編輯器還不能執行程式？", "also_asks": ["編輯器跟編譯器到底差在哪裡？"],
			"title": "工具分工", "sec": 60, "objectives": [1], "screens": [], "show": "展示工具分工"},
		{"id": "q2", "question": "為什麼終端機找不到指令？", "also_asks": ["環境變數是什麼意思？"],
			"title": "環境設定", "sec": 75, "objectives": [2], "screens": ["win11.search"], "show": "展示搜尋步驟"},
		{"id": "q3", "question": "編譯的四個階段是什麼？", "also_asks": [],
			"title": "編譯流程", "sec": 70, "objectives": [3], "screens": [], "show": "展示生產線"}],
	"glossary": [{"term": "<=", "say_as": "小於等於"}],
	"highlight": {"question": "這個單元的核心觀念有哪些？", "also_asks": ["快速複習全部內容"],
		"stories": ["q1", "q2", "q3"], "total_sec": 205, "why": "串起核心觀念"}}
SCENE = {"scenes": [{"beats": [{"say": "第一句"}, {"say": "第二句"}, {"say": "第三句"}]}]}


class FakeRunner:
	def __init__(self):
		self.commands = []
		self.fail = None
		self.warning = False
		self.entered = threading.Event()
		self.release = threading.Event()
		self.release.set()

	def __call__(self, command, log):
		self.commands.append(command)
		self.entered.set()
		if not self.release.wait(5):
			raise RuntimeError("測試 runner 等待逾時")
		cli = Path(command[1]).name
		for n in range(45):
			log(f"測試輸出 {n}")
		if cli == self.fail:
			if cli == "export.py":
				Path(command[3]).write_bytes(b"partial mp4")
			log("@error gemini_busy 暫時忙碌")
			return 2
		if cli == "author.py":
			directory = Path(command[4])
			write_json(directory / ("plan.json" if command[2] == "plan" else command[5] + ".scene.json"),
				PLAN if command[2] == "plan" else SCENE)
			with (directory / "usage.jsonl").open("a", encoding="utf-8") as handle:
				handle.write(json.dumps({"item": "analysis" if command[2] == "plan" else command[5], "usd": 0.025}) + "\n")
		elif cli == "compose.py":
			write_json(Path(command[4]), SCENE)
		elif cli == "narrate.py":
			directory = Path(command[3])
			write_json(directory / "timing.json", [{"t0": 0.2, "t1": 61}])
			(directory / "master.wav").write_bytes(b"fake audio")
			if self.warning:
				log("@warn tts_missing 第 3 句")
		elif cli == "compile.py":
			write_json(Path(command[3]), {"duration": 61.2})
		elif cli == "build.py":
			Path(command[3]).mkdir(parents=True, exist_ok=True)
		elif cli == "export.py":
			Path(command[3]).write_bytes(b"fake mp4")
		elif cli in ("run_mindmap.py", "run_slides.py"):
			directory = Path(command[2])
			if cli == "run_mindmap.py":
				(directory / "mindmap").mkdir(exist_ok=True)
				(directory / "mindmap/mindmap.svg").write_text("<svg/>", encoding="utf-8")
			else:
				write_json(directory / "slides/deck.json", {"slides": []})
				(directory / "slides/deck.pptx").write_bytes(b"fake pptx")
		elif cli == "run_normalize.py":
			uid, _ = Library(Path(command[3])).create_unit("# 整理後教材\n內容", source_kind="pptx")
			log("@unit " + uid)
		return 0


class TestStudio(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.out = Path(self.temp.name) / "units"
		self.runner = FakeRunner()
		self.studio = BS.Studio(self.out, command_runner=self.runner, tts_mode="gemini")
		self.addCleanup(self.studio.close)
		self.addCleanup(self.runner.release.set)
		self.static = Path(self.temp.name) / "web"
		self.static.mkdir()
		(self.static / "index.html").write_text("工作台", encoding="utf-8")
		(self.static / "embed.html").write_text("<!doctype html><title>嵌入</title>", encoding="utf-8")
		(self.static / "app.mjs").write_text("const ready = true;", encoding="utf-8")
		self.server = BS.StudioHTTPServer(("127.0.0.1", 0), self.studio, web_dir=self.static)
		self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
		self.thread.start()
		self.addCleanup(self.stop_http)

	def stop_http(self):
		self.server.shutdown()
		self.server.server_close()
		self.thread.join(2)

	def request(self, method, path, payload=None, headers=None, raw=None):
		connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
		try:
			body = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
			connection.request(method, path, body=body, headers=headers or {})
			response = connection.getresponse()
			return response.status, dict(response.getheaders()), response.read()
		finally:
			connection.close()

	def api(self, method, path, payload=None, expected=200, shape=None, **kwargs):
		status, headers, body = self.request(method, path, payload, **kwargs)
		self.assertEqual(status, expected, body)
		self.assertIn("application/json", headers["Content-Type"])
		value = json.loads(body)
		if expected >= 400:
			assert_shape(value, SHAPES["api_error"])
		elif shape:
			assert_shape(value, SHAPES[shape])
		elif method == "POST":
			if path == "/api/v1/units":
				assert_shape(value, {"unit_id": str, "created": bool})
			elif path.endswith("/generate"):
				assert_shape(value, {"job_ids": [str]})
			else:
				assert_shape(value, {"job_id": (str, None)})
		return value

	def unit(self, analyzed=True):
		result = self.api("POST", "/api/v1/units", {"markdown": "# 第一支程式\nC 語言教材。", "title": "測試教材",
			"source_ref": {"platform": "bridgeai", "revision": "1"}})
		uid = result["unit_id"]
		directory = self.out / uid
		if analyzed:
			write_json(directory / "plan.json", PLAN)
		return uid, directory

	def wait_job(self, jid):
		deadline = time.monotonic() + 5
		while time.monotonic() < deadline:
			job = self.api("GET", "/api/v1/jobs/" + jid, shape="job")
			if job["state"] in ("done", "failed"):
				return job
			time.sleep(0.01)
		self.fail("工作未結束")

	def test_create_reuse_list_and_analysis_shape(self):
		uid, directory = self.unit(analyzed=False)
		self.assertEqual(uid, hashlib.sha256("# 第一支程式\nC 語言教材。".encode()).hexdigest()[:12])
		original = (directory / "meta.json").read_bytes()
		self.assertFalse(self.api("POST", "/api/v1/units", {"markdown": "# 第一支程式\nC 語言教材。"})["created"])
		self.assertEqual((directory / "meta.json").read_bytes(), original)
		detail = self.api("GET", f"/api/v1/units/{uid}", shape="unit")
		self.assertIsNone(detail["analysis"])
		self.assertEqual(detail["source_ref"], {"platform": "bridgeai", "revision": "1"})
		write_json(directory / "plan.json", PLAN)
		detail = self.api("GET", f"/api/v1/units/{uid}", shape="unit")
		self.assertEqual(detail["analysis"]["points"], PLAN["stories"])
		self.assertEqual(detail["analysis"]["highlight"]["points"], ["q1", "q2", "q3"])
		self.assertEqual([i["item"] for i in detail["items"]], ["q1", "q2", "q3", "highlight", "mindmap", "slides"])
		units = self.api("GET", "/api/v1/units")
		assert_shape(units, [SHAPES["unit_summary"]])
		self.assertEqual(units[0]["points"], 3)
		self.assertTrue(units[0]["analyzed"])
		self.api("GET", "/api/v1/formats", shape="formats")

	def test_analysis_conflict_and_already_analyzed(self):
		uid, _ = self.unit(analyzed=False)
		self.runner.release.clear()
		jid = self.api("POST", f"/api/v1/units/{uid}/analyze")["job_id"]
		self.assertTrue(self.runner.entered.wait(2))
		self.api("POST", f"/api/v1/units/{uid}/analyze", expected=409)
		self.runner.release.set()
		self.assertEqual(self.wait_job(jid)["state"], "done")
		self.assertEqual(self.api("POST", f"/api/v1/units/{uid}/analyze"), {"job_id": None, "analyzed": True})
		self.assertEqual([Path(c[1]).name for c in self.runner.commands], ["selftest.py", "author.py"])

	def test_generate_order_all_formats_and_manifest(self):
		uid, directory = self.unit()
		result = self.api("POST", f"/api/v1/units/{uid}/generate", {"items": ["slides", "q2", "mindmap", "q1", "highlight", "q2"]})
		jobs = [self.wait_job(jid) for jid in result["job_ids"]]
		self.assertEqual([j["item"] for j in jobs], ["q2", "q1", "highlight", "mindmap", "slides"])
		self.assertTrue(all(j["state"] == "done" for j in jobs), jobs)
		detail = self.api("GET", f"/api/v1/units/{uid}", shape="unit")
		q2 = next(i for i in detail["items"] if i["item"] == "q2")
		self.assertEqual((q2["status"], q2["duration"], q2["files"]), ("done", 61.2, {"video": "q2/video.mp4"}))
		self.assertAlmostEqual(q2["cost_usd"], 0.025)
		assert_shape(read_json(directory / "manifest.json"), SHAPES["manifest"])
		manifest = self.api("GET", f"/api/v1/units/{uid}/manifest", shape="manifest")
		self.assertEqual(len(manifest["products"]), 5)
		self.assertEqual(manifest["products"][0]["embed_url"], f"/embed/{uid}/q1")
		self.api("GET", "/api/v1/usage", shape="usage")
		units = self.api("GET", "/api/v1/units")
		assert_shape(units, [SHAPES["unit_summary"]])
		self.assertEqual(units[0]["products"], {"video": 2, "highlight": True, "mindmap": True, "slides": True})
		self.assertEqual(self.api("POST", f"/api/v1/units/{uid}/generate", {"items": ["q1", "slides"]}), {"job_ids": []})

	def test_queue_skips_active_items(self):
		uid, _ = self.unit()
		self.runner.release.clear()
		first = self.api("POST", f"/api/v1/units/{uid}/generate", {"items": ["q1"]})["job_ids"][0]
		self.assertTrue(self.runner.entered.wait(2))
		second = self.api("POST", f"/api/v1/units/{uid}/generate", {"items": ["q1", "q2"]})["job_ids"]
		self.assertEqual(len(second), 1)
		queue = self.api("GET", "/api/v1/queue", shape="queue")
		self.assertEqual(queue["running"]["job_id"], first)
		self.assertEqual([j["job_id"] for j in queue["queued"]], second)
		self.assertEqual([i["status"] for i in self.api("GET", f"/api/v1/units/{uid}", shape="unit")["items"]][:3], ["running", "queued", "none"])
		self.runner.release.set()
		for jid in [first, *second]:
			self.assertEqual(self.wait_job(jid)["state"], "done")
		self.api("GET", "/api/v1/queue", shape="queue")

	def test_retry_resume_and_partial_export_not_done(self):
		uid, directory = self.unit()
		write_json(directory / "q1.failed.json", {"last": {}})
		self.runner.fail = "export.py"
		jid = self.api("POST", f"/api/v1/units/{uid}/generate", {"items": ["q1"]})["job_ids"][0]
		self.assertEqual(self.wait_job(jid)["state"], "failed")
		self.assertIn("--resume", self.runner.commands[0])
		item = self.api("GET", f"/api/v1/units/{uid}", shape="unit")["items"][0]
		self.assertEqual(item["status"], "failed")
		self.assertEqual(item["files"], {})
		self.runner.fail = None
		retry = self.api("POST", f"/api/v1/jobs/{jid}/retry")["job_id"]
		self.assertNotEqual(jid, retry)
		self.assertEqual(self.wait_job(retry)["state"], "done")
		self.api("POST", f"/api/v1/jobs/{retry}/retry", expected=409)

	def test_warning_renarrate_ignores_done_and_latest_warnings(self):
		uid, directory = self.unit()
		self.runner.warning = True
		jid = self.api("POST", f"/api/v1/units/{uid}/generate", {"items": ["q1"]})["job_ids"][0]
		job = self.wait_job(jid)
		self.assertEqual(job["state"], "done")
		self.assertIsNone(job["error"])
		warning = [{"code": "tts_missing", "detail": "第 3 句"}]
		self.assertEqual(job["warnings"], warning)
		self.assertEqual(self.api("GET", f"/api/v1/units/{uid}", shape="unit")["items"][0]["warnings"], warning)
		self.runner.warning = False
		self.runner.commands.clear()
		redo = self.api("POST", f"/api/v1/units/{uid}/items/q1/renarrate", {"beats": [3, 1]})["job_id"]
		self.assertEqual(self.wait_job(redo)["state"], "done")
		self.assertEqual([Path(c[1]).name for c in self.runner.commands], ["narrate.py", "compile.py", "build.py", "check.py", "export.py"])
		self.assertEqual(self.runner.commands[0][-2:], ["--redo", "3,1"])
		item = self.api("GET", f"/api/v1/units/{uid}", shape="unit")["items"][0]
		self.assertEqual((item["job_id"], item["warnings"]), (redo, []))
		self.runner.fail = "check.py"
		failed = self.api("POST", f"/api/v1/units/{uid}/items/q1/renarrate", {"beats": [1]})["job_id"]
		self.assertEqual(self.wait_job(failed)["state"], "failed")
		self.runner.fail = None
		self.runner.commands.clear()
		retry = self.api("POST", f"/api/v1/jobs/{failed}/retry")["job_id"]
		self.assertEqual(self.wait_job(retry)["state"], "done")
		self.assertEqual(self.runner.commands[0][-2:], ["--redo", "1"])

	def test_renarrate_validates_beats_format_scene_and_conflict(self):
		uid, directory = self.unit()
		self.api("POST", f"/api/v1/units/{uid}/items/q1/renarrate", {"beats": [1]}, expected=409)
		write_json(directory / "q1.scene.json", SCENE)
		for beats in ([], [0], [-1], [4], [True], [1.0], ["1"], "1"):
			self.api("POST", f"/api/v1/units/{uid}/items/q1/renarrate", {"beats": beats}, expected=400)
		self.api("POST", f"/api/v1/units/{uid}/items/mindmap/renarrate", {"beats": [1]}, expected=400)
		self.runner.release.clear()
		jid = self.api("POST", f"/api/v1/units/{uid}/items/q1/renarrate", {"beats": [1]})["job_id"]
		self.assertTrue(self.runner.entered.wait(2))
		self.api("POST", f"/api/v1/units/{uid}/items/q1/renarrate", {"beats": [1]}, expected=409)
		self.runner.release.set()
		self.wait_job(jid)

	def upload(self, filename="lesson.pptx", data=None, expected=200):
		if data is None:
			path = Path(self.temp.name) / "lesson.pptx"
			make(path, [("迴圈", ["每圈檢查條件"]), ("邊界", ["留意多跑一次"])])
			data = path.read_bytes()
		body = (f'--test-boundary\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
			'Content-Type: application/octet-stream\r\n\r\n').encode() + data + b'\r\n--test-boundary--\r\n'
		return self.api("POST", "/api/v1/uploads", expected=expected, shape="upload", raw=body,
			headers={"Content-Type": "multipart/form-data; boundary=test-boundary"})

	def test_upload_real_pptx_and_normalize_unit_marker(self):
		upload = self.upload()
		self.assertEqual((upload["kind"], upload["pages"]), ("pptx", 2))
		self.assertGreater(upload["chars"], 0)
		self.assertLessEqual(len(upload["excerpt"]), 400)
		self.assertEqual(self.runner.commands, [])
		draft = self.out.parent / "uploads" / upload["upload_id"]
		self.assertEqual(read_json(draft / "upload.json")["filename"], "lesson.pptx")
		self.assertTrue((draft / "extracted.md").is_file())
		jid = self.api("POST", f'/api/v1/uploads/{upload["upload_id"]}/normalize')["job_id"]
		job = self.wait_job(jid)
		self.assertEqual(job["state"], "done")
		self.assertIsNotNone(job["unit_id"])
		self.api("GET", f'/api/v1/units/{job["unit_id"]}', shape="unit")
		self.assertTrue((self.out / job["unit_id"] / "manifest.json").is_file())

	def test_failed_normalize_retry_conflicts_for_the_same_draft(self):
		upload = self.upload()
		path = f'/api/v1/uploads/{upload["upload_id"]}/normalize'
		self.runner.fail = "run_normalize.py"
		failed = self.api("POST", path)["job_id"]
		job = self.wait_job(failed)
		self.assertEqual(job["state"], "failed")
		self.assertIsNone(job["unit_id"])
		self.runner.fail = None
		self.runner.entered.clear()
		self.runner.release.clear()
		retry = self.api("POST", f"/api/v1/jobs/{failed}/retry")["job_id"]
		self.assertTrue(self.runner.entered.wait(2))
		self.api("POST", f"/api/v1/jobs/{failed}/retry", expected=409)
		self.api("POST", path, expected=409)
		self.runner.release.set()
		self.assertEqual(self.wait_job(retry)["state"], "done")

	def test_upload_limits_invalid_multipart_and_unknown_draft(self):
		self.upload(data=b"x" * (5 * 1024 * 1024 + 1), expected=413)
		self.upload(filename="lesson.txt", data=b"text", expected=400)
		self.upload(filename="../lesson.pdf", data=b"%PDF-", expected=400)
		self.api("POST", "/api/v1/uploads", raw=b"bad", expected=400)
		for text in ("\n".join(f"## 第 {i} 頁\n內容" for i in range(1, 32)), "## 第 1 頁\n" + "字" * 60001):
			with patch("workbench.uploads.extract_text", return_value=text):
				self.upload(filename="lesson.pdf", data=b"%PDF-fake", expected=413)
		self.api("POST", "/api/v1/uploads/missing/normalize", expected=404)
		self.assertEqual(self.runner.commands, [])

	def test_upload_counts_blank_slides_toward_page_limit(self):
		path = Path(self.temp.name) / "blanks.pptx"
		make(path, [("", [])] * 3 + [("最後一頁", ["內容"])])
		self.assertEqual(self.upload(data=path.read_bytes())["pages"], 4)
		make(path, [("", [])] * 30 + [("最後一頁", ["內容"])])
		self.upload(data=path.read_bytes(), expected=413)

	def test_corrupt_pptx_xml_returns_json_bad_request(self):
		path = Path(self.temp.name) / "broken.pptx"
		make(path, [("教材", ["內容"])])
		data = io.BytesIO()
		with zipfile.ZipFile(path) as original, zipfile.ZipFile(data, "w") as modified:
			for member in original.infolist():
				modified.writestr(member, b"<broken" if member.filename == "ppt/presentation.xml" else original.read(member.filename))
		self.upload(data=data.getvalue(), expected=400)

	def test_ask_has_real_shapes_and_no_generation(self):
		uid, _ = self.unit()
		for question, kind in (("編輯器跟編譯器到底差在哪裡？", "story"), ("請整理重點", "highlight"),
			("Python", "out_of_scope"), ("指標與動態記憶體配置", "out_of_scope"), ("今晚的月亮好圓", "no_match")):
			answer = self.api("POST", "/api/v1/ask", {"unit_id": uid, "question": question}, shape="ask")
			self.assertEqual(answer["kind"], kind)
		self.assertEqual(self.runner.commands, [])

	def test_static_embed_range_traversal_and_removed_routes(self):
		uid, directory = self.unit()
		(directory / "q1").mkdir()
		(directory / "q1/video.mp4").write_bytes(b"0123456789")
		manifest = self.api("GET", f"/api/v1/units/{uid}/manifest", shape="manifest")
		self.assertEqual(len(manifest["products"]), 1)
		for range_value, expected in (("bytes=2-5", b"2345"), ("bytes=7-", b"789"), ("bytes=-3", b"789")):
			status, headers, body = self.request("GET", f"/media/{uid}/q1/video.mp4", headers={"Range": range_value})
			self.assertEqual((status, body), (206, expected))
			self.assertIn("Content-Range", headers)
			self.assertEqual(headers["Content-Type"], "video/mp4")
		self.assertEqual(self.request("GET", f"/media/{uid}/q1/video.mp4", headers={"Range": "bytes=99-"})[0], 416)
		status, headers, _ = self.request("GET", "/?mock=1")
		self.assertEqual((status, headers["Location"]), (302, "/web/index.html?mock=1"))
		self.assertEqual(self.request("GET", "/web/index.html")[2].decode(), "工作台")
		self.assertIn("javascript", self.request("GET", "/web/app.mjs")[1]["Content-Type"])
		status, headers, body = self.request("GET", f"/embed/{uid}/q1")
		self.assertEqual(status, 200)
		self.assertIn("text/html", headers["Content-Type"])
		self.assertIn(b"<!doctype html>", body)
		(directory / "escape").symlink_to(self.static / "index.html")
		(self.static / "escape").symlink_to(directory / "meta.json")
		for path in ("/web/../server.py", "/web/%2e%2e/server.py", "/web/escape", f"/media/{uid}/../other/meta.json",
			f"/media/{uid}/escape", f"/embed/{uid}/unknown", "/api/units", "/api/pipelines", "/api/jobs/missing", "/studio/index.html"):
			self.api("GET", path, expected=404)
		self.api("POST", "/api/units", {"markdown": "教材"}, expected=404)

	def test_validation_codes_and_atomic_generate_validation(self):
		for payload in ({"markdown": " "}, [], {"markdown": "教材", "source_ref": "bad"}):
			self.assertEqual(self.api("POST", "/api/v1/units", payload, expected=400)["error"]["code"], "bad_request")
		self.api("GET", "/api/v1/units/000000000000", expected=404)
		self.api("GET", "/api/v1/jobs/missing", expected=404)
		uid, directory = self.unit(analyzed=False)
		self.api("POST", f"/api/v1/units/{uid}/generate", {"items": ["q1"]}, expected=409)
		write_json(directory / "plan.json", PLAN)
		for items in (["q1", "comic"], ["../q1"], ["unknown"], "q1", [None]):
			self.api("POST", f"/api/v1/units/{uid}/generate", {"items": items}, expected=400)
		self.assertEqual(self.runner.commands, [])
		self.api("POST", "/api/v1/units", raw=b'{"unused":' + b'[' * 1100 + b'0' + b']' * 1100 + b'}', expected=400)
		self.api("POST", "/api/v1/units", raw=b'{"markdown":NaN}', expected=400)

	def test_output_symlink_fails_before_narrate(self):
		uid, directory = self.unit()
		(directory / "q1").mkdir()
		(directory / "q1/voice").symlink_to(self.static, target_is_directory=True)
		jid = self.api("POST", f"/api/v1/units/{uid}/generate", {"items": ["q1"]})["job_ids"][0]
		self.assertEqual(self.wait_job(jid)["state"], "failed")
		self.assertNotIn("narrate.py", [Path(c[1]).name for c in self.runner.commands])

	def test_legacy_batch_failure_preserves_completed_and_reused_points(self):
		uid, directory = self.unit()
		self.studio.close()
		for item in ("q1", "q3"):
			(directory / item).mkdir()
			(directory / item / "video.mp4").write_bytes(b"complete video")
		write_json(directory / "jobs" / ("a" * 32 + ".json"), {
			"job_id": "a" * 32, "unit_id": uid, "kind": "stories", "stories": ["q3"], "target": "q3",
			"completed": ["q3"], "state": "done", "log": [], "error": None, "created_at": "2026-10-04"})
		write_json(directory / "jobs" / ("b" * 32 + ".json"), {
			"job_id": "b" * 32, "unit_id": uid, "kind": "stories", "stories": ["q1", "q2", "q3"], "target": "q2",
			"completed": ["q1"], "state": "failed", "log": [], "error": None, "created_at": "2026-10-05"})
		self.studio = BS.Studio(self.out, command_runner=self.runner, tts_mode="gemini")
		self.addCleanup(self.studio.close)
		self.server.studio = self.studio
		items = self.api("GET", f"/api/v1/units/{uid}", shape="unit")["items"]
		self.assertEqual([item["status"] for item in items[:3]], ["done", "failed", "done"])


class TestTTSHealth(unittest.TestCase):
	def test_http_500_is_up_and_refused_is_down(self):
		with patch.object(BS.http.client, "HTTPConnection") as connection:
			connection.return_value.getresponse.return_value.status = 500
			self.assertTrue(BS.tts_health())
			connection.return_value.request.side_effect = ConnectionRefusedError()
			self.assertFalse(BS.tts_health())


if __name__ == "__main__":
	unittest.main()
