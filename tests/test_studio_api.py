import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import serve
from studio.sources import SourceStore
from studio.plans import PlanStore


class NoRead(io.BytesIO):
	def read(self, *args):
		raise AssertionError("超限 body 不可被讀取")


class TestBoundedBody(unittest.TestCase):
	def test_invalid_content_length_is_rejected(self):
		for headers in ({}, {"Content-Length": "abc"}, {"Content-Length": "-1"}):
			with self.subTest(headers=headers), self.assertRaises(serve.RequestBodyError) as context:
				serve.read_request_body(io.BytesIO(b""), headers, 10)
			self.assertIn(context.exception.status, (400, 411))

	def test_oversize_is_rejected_without_reading_and_short_body_is_400(self):
		with self.assertRaises(serve.RequestBodyError) as context:
			serve.read_request_body(NoRead(b""), {"Content-Length": "11"}, 10)
		self.assertEqual(context.exception.status, 413)
		self.assertTrue(context.exception.close)
		with self.assertRaises(serve.RequestBodyError) as context:
			serve.read_request_body(io.BytesIO(b"abc"), {"Content-Length": "5"}, 10)
		self.assertEqual(context.exception.status, 400)


class TestStudioHttp(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.store = SourceStore(Path(self.tmp.name))
		self.addCleanup(self.store.close)
		patcher = patch.object(serve, "_source_store", self.store)
		patcher.start()
		self.addCleanup(patcher.stop)
		plan_patcher = patch.object(serve, "_plan_store", PlanStore(), create=True)
		plan_patcher.start()
		self.addCleanup(plan_patcher.stop)
		self.srv = serve.make_server(0)
		threading.Thread(target=self.srv.serve_forever, daemon=True).start()
		self.addCleanup(self.srv.server_close)
		self.addCleanup(self.srv.shutdown)
		self.port = self.srv.server_address[1]

	def request(self, method, path, body=None, headers=None):
		conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
		try:
			conn.request(method, path, body=body, headers=headers or {})
			response = conn.getresponse()
			content = response.read()
			return response.status, dict(response.getheaders()), json.loads(content) if content else None
		finally:
			conn.close()

	def session(self):
		status, _, payload = self.request("GET", "/api/studio/session")
		self.assertEqual(status, 200)
		return payload["csrf_token"]

	def test_session_catalog_and_mutation_csrf(self):
		token = self.session()
		self.assertGreater(len(token), 30)
		status, _, payload = self.request("GET", "/api/studio/catalog")
		self.assertEqual(status, 200)
		self.assertEqual(len(payload["capabilities"]), 8)
		for headers in ({}, {"X-Studio-CSRF": "wrong"},
			{"X-Studio-CSRF": token, "Origin": "https://evil.example"}):
			with self.subTest(headers=headers):
				status, response_headers, _ = self.request("POST", "/jobs", body=b"bad", headers=headers)
				self.assertEqual(status, 403)
				self.assertNotIn("Access-Control-Allow-Origin", response_headers)

	def test_source_upload_and_delete(self):
		token = self.session()
		boundary = "STUDIOBOUNDARY"
		body = (b"--STUDIOBOUNDARY\r\n"
			b'Content-Disposition: form-data; name="file"; filename="lesson.txt"\r\n'
			b"Content-Type: text/plain\r\n\r\nhello\n"
			b"\r\n--STUDIOBOUNDARY--\r\n")
		headers = {"X-Studio-CSRF": token, "Content-Type": f"multipart/form-data; boundary={boundary}"}
		status, _, payload = self.request("POST", "/api/studio/sources", body=body, headers=headers)
		self.assertEqual(status, 201)
		source = payload["source"]
		self.assertEqual(source["preview_excerpt"], "hello\n")
		self.assertNotIn(self.tmp.name, str(payload))
		status, _, _ = self.request("DELETE", "/api/studio/sources/" + source["ref"], headers={"X-Studio-CSRF": token})
		self.assertEqual(status, 200)
		self.assertFalse(list(Path(self.tmp.name).glob(".studio_source_*")))

	def test_normalization_requires_csrf_and_passes_source_revision(self):
		source = self.store.add_upload("lesson.txt", b"hello")
		path = "/api/studio/sources/" + source["ref"].replace(":", "%3A") + "/normalize"
		body = json.dumps({"revision": source["revision"]}).encode()
		with patch.object(self.store, "normalize", return_value=dict(source, normalization_status="complete")) as run:
			status, _, payload = self.request("POST", path, body=body)
			self.assertEqual(status, 403)
			run.assert_not_called()
			status, _, payload = self.request("POST", path, body=body,
				headers={"X-Studio-CSRF": self.session(), "Content-Type": "application/json"})
			self.assertEqual(status, 200)
			self.assertEqual(payload["source"]["normalization_status"], "complete")
			run.assert_called_once_with(source["ref"], source["revision"])

	def test_failed_normalization_http_keeps_actual_usage(self):
		from video_engine.usage import report_usage
		from studio.material_normalizer import NormalizationError
		source = self.store.add_upload('lesson.txt',b'hello')
		original = self.store.normalize
		def failed(record):
			report_usage('google','gemini-3.8-flash',{'in':10,'out':20,'thinking':5})
			raise NormalizationError('整理引文驗證失敗')
		with patch.object(self.store,'normalize',side_effect=lambda ref,revision:original(ref,revision,failed)):
			status, _, payload = self.request('POST',f"/api/studio/sources/{source['ref']}/normalize",
				json.dumps({'revision':source['revision']}).encode(),
				{'X-Studio-CSRF':self.session(),'Content-Type':'application/json'})
		self.assertEqual(status,422)
		self.assertEqual(payload['source']['normalization_usage']['total_tokens'],35)
		self.assertEqual(payload['source']['revision'],source['revision'])

	def test_normalize_http_accepts_reflowed_quote_and_updates_source(self):
		source = self.store.add_upload("wrapped.txt", "雨水經過濾網\n進入儲水桶。".encode())
		calls = []
		def runner(system, request, pdf_bytes):
			calls.append(1)
			return {"title":"雨水收集", "pages":[{"page":1,
				"clean_text":"雨水經過濾網進入儲水桶。",
				"verified_quotes":["雨水經過濾網進入儲水桶。"],
				"visual_notes":[], "uncertainties":[]}]}, {"model":"gemini-3.8-flash"}
		from studio.material_normalizer import normalize_material
		normalize = self.store.normalize
		with patch.object(self.store, "normalize", side_effect=lambda ref, revision:
			normalize(ref, revision, lambda record: normalize_material(record, runner))):
			path = "/api/studio/sources/" + source["ref"].replace(":", "%3A") + "/normalize"
			headers = {"X-Studio-CSRF":self.session(), "Content-Type":"application/json"}
			body = json.dumps({"revision":source["revision"]}).encode()
			status, _, payload = self.request("POST", path, body, headers=headers)
			second_status, _, second = self.request("POST", path, body, headers=headers)
		self.assertEqual(status, 200)
		self.assertEqual(second_status, 200)
		self.assertEqual(second["source"], payload["source"])
		self.assertEqual(len(calls), 1)
		self.assertEqual(payload["source"]["normalization_status"], "complete")
		self.assertNotEqual(payload["source"]["revision"], source["revision"])
		self.assertIn("雨水經過濾網\n  進入儲水桶。", payload["source"]["preview_excerpt"])

	def test_malformed_upload_returns_safe_error(self):
		token = self.session()
		headers = {"X-Studio-CSRF": token, "Content-Type": "multipart/form-data; boundary=BAD"}
		status, _, payload = self.request("POST", "/api/studio/sources", body=b"broken", headers=headers)
		self.assertEqual(status, 400)
		self.assertNotIn("/home/", str(payload))

	def test_plan_checks_source_and_returns_saved_canonical_plan_without_tts(self):
		token = self.session()
		source = self.store.add_upload("lesson.txt", b"hello")
		request = {"contract_version": "1.0", "instruction": "做成 90 秒影片",
			"source": {key: source[key] for key in ("kind", "ref", "revision")}}
		headers = {"X-Studio-CSRF": token, "Content-Type": "application/json"}
		with patch.object(serve, "tts_ready", side_effect=AssertionError("規劃不可探 TTS")):
			status, _, payload = self.request("POST", "/api/studio/plans", json.dumps(request).encode(), headers)
		self.assertEqual(status, 201)
		self.assertRegex(payload["plan_id"], r"^[0-9a-f]{32}$")
		self.assertEqual(payload["plan"]["steps"][0]["review_gate"], "script")
		self.assertEqual(serve._plan_store.get(payload["plan_id"]).plan, payload["plan"])

	def test_missing_and_stale_source_fail_before_planning(self):
		token = self.session()
		source = self.store.add_upload("lesson.txt", b"hello")
		base = {"contract_version": "1.0", "instruction": "做成 90 秒影片",
			"source": {key: source[key] for key in ("kind", "ref", "revision")}}
		headers = {"X-Studio-CSRF": token, "Content-Type": "application/json"}
		missing = json.loads(json.dumps(base))
		missing["source"]["ref"] = "material:missing"
		status, _, payload = self.request("POST", "/api/studio/plans", json.dumps(missing).encode(), headers)
		self.assertEqual(status, 404)
		self.assertEqual(payload["code"], "source_missing")
		Path(self.store.resolve(source["ref"], source["revision"]).material_path).write_bytes(b"changed")
		status, _, payload = self.request("POST", "/api/studio/plans", json.dumps(base).encode(), headers)
		self.assertEqual(status, 409)
		self.assertEqual(payload["code"], "stale_source")

	def test_job_route_uses_saved_plan_and_sanitizes_failure(self):
		token = self.session()
		source = self.store.add_upload("lesson.txt", b"hello")
		request = {"contract_version": "1.0", "instruction": "做成 90 秒影片",
			"source": {key: source[key] for key in ("kind", "ref", "revision")}}
		headers = {"X-Studio-CSRF": token, "Content-Type": "application/json"}
		status, _, planned = self.request("POST", "/api/studio/plans", json.dumps(request).encode(), headers)
		self.assertEqual(status, 201)
		with patch.object(serve, "tts_ready", return_value=False):
			status, _, payload = self.request("POST", "/api/studio/jobs", json.dumps({"plan_id": planned["plan_id"]}).encode(), headers)
		self.assertEqual(status, 503)
		self.assertFalse(list(Path(self.tmp.name).glob(".studio_job_*")))
		def fail_runner(material, sec, layout=None, seed=None):
			return lambda first, last: iter([{"event": "stage_fail", "stage": "lesson", "code": 1,
				"tail": ["Bearer secret /home/user/file traceback"]}])
		with patch.object(serve, "tts_ready", return_value=True), patch.object(serve, "real_runner", side_effect=fail_runner):
			status, _, payload = self.request("POST", "/api/studio/jobs", json.dumps({"plan_id": planned["plan_id"]}).encode(), headers)
		self.assertEqual(status, 201)
		job_id = payload["job_id"]
		import time
		deadline = time.monotonic() + 2
		while time.monotonic() < deadline:
			status, _, snapshot = self.request("GET", "/api/studio/jobs/" + job_id)
			if snapshot["status"] == "failed": break
			time.sleep(0.01)
		self.assertEqual(snapshot["status"], "failed")
		self.assertNotIn("secret", str(snapshot))
		self.assertFalse(list(Path(self.tmp.name).glob(".studio_job_*")))

	def test_job_rejects_missing_plan_and_busy_slot(self):
		token = self.session()
		headers = {"X-Studio-CSRF": token, "Content-Type": "application/json"}
		status, _, payload = self.request("POST", "/api/studio/jobs", b'{"plan_id":"missing"}', headers)
		self.assertEqual(status, 404)
		self.assertEqual(payload["code"], "plan_missing")
		source = self.store.add_upload("lesson.txt", b"hello")
		request = {"contract_version": "1.0", "instruction": "做成 90 秒影片",
			"source": {key: source[key] for key in ("kind", "ref", "revision")}}
		_, _, planned = self.request("POST", "/api/studio/plans", json.dumps(request).encode(), headers)
		self.assertTrue(serve._execution_slot.claim("other"))
		try:
			with patch.object(serve, "tts_ready", return_value=True):
				status, _, payload = self.request("POST", "/api/studio/jobs", json.dumps({"plan_id": planned["plan_id"]}).encode(), headers)
			self.assertEqual(status, 409)
			self.assertEqual(payload["code"], "execution_busy")
			self.assertFalse(list(Path(self.tmp.name).glob(".studio_job_*")))
		finally:
			serve._execution_slot.release("other")

	def test_studio_home_and_legacy_demo_are_both_accessible(self):
		for route, marker in (("/", "多模態教材工作台"), ("/legacy", "VideoMaker 現場展示系統")):
			with self.subTest(route=route):
				conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
				try:
					conn.request("GET", route)
					response = conn.getresponse()
					self.assertEqual(response.status, 200)
					self.assertIn(marker, response.read().decode())
				finally: conn.close()

	def test_static_resources_use_exact_routes(self):
		for path, kind in (("/assets/styles.css", "text/css"),
			("/assets/js/api.mjs", "javascript"), ("/assets/js/state.mjs", "javascript"),
			("/assets/js/render.mjs", "javascript"), ("/assets/js/app.mjs", "javascript")):
			with self.subTest(path=path):
				conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
				try:
					conn.request("GET", path)
					response = conn.getresponse()
					self.assertEqual(response.status, 200)
					self.assertIn(kind, response.getheader("Content-Type"))
					self.assertTrue(response.read())
				finally:
					conn.close()
		for path in ("/assets/nope.mjs", "/assets/js/../app.mjs", "/assets/js/%2e%2e/app.mjs", "/assets/styles.css.bak", "/assets/js/app.mjs%00"):
			with self.subTest(path=path):
				status, _, _ = self.request("GET", path)
				self.assertEqual(status, 404)

	def test_studio_job_read_routes_use_facade_and_reject_bad_cursor(self):
		token = self.session()
		class FakeFacade:
			def snapshot(self): return {"job_id": "jobx", "status": "failed", "artifacts": []}
			def events_after(self, seq): return [{"seq": 1, "event": "stage_start", "payload": {"stage": "lesson"}}]
			def get_review(self): return {"segments": [], "deadline": 123, "slides": []}
			def artifacts(self): return []
		with patch.dict(serve._studio_jobs, {"jobx": FakeFacade()}):
			status, _, payload = self.request("GET", "/api/studio/jobs/jobx/review")
			self.assertEqual((status, payload["deadline"]), (200, 123))
			status, _, payload = self.request("GET", "/api/studio/jobs/jobx/artifacts")
			self.assertEqual((status, payload["artifacts"]), (200, []))
			status, _, payload = self.request("GET", "/api/studio/jobs/jobx/events?after=-1")
			self.assertEqual((status, payload["code"]), (400, "invalid_cursor"))
			status, _, payload = self.request("POST", "/api/studio/jobs/jobx/review", b'{"segments":{}}',
				{"X-Studio-CSRF": token, "Content-Type": "application/json"})
			self.assertEqual((status, payload["code"]), (400, "invalid_review"))

	def test_artifact_stream_range_review_and_terminal_events(self):
		token = self.session()
		artifact_id = "artifact-" + "a" * 32
		video = Path(self.tmp.name) / "private.mp4"
		video.write_bytes(b"0123456789")
		class FakeFacade:
			status = "needs_review"
			def artifacts(self): return [{"artifact_id":artifact_id, "status":self.status,
				"download":{"file_name":"lesson.mp4"}}]
			def artifact_content(self, given): return str(video)
			def review_artifact(self, given, decision):
				if decision not in ("approve", "reject"): raise serve.FacadeError("invalid_decision", "審核決定不正確")
				if self.status != "needs_review": raise serve.FacadeError("artifact_conflict", "已完成審核")
				self.status = "approved" if decision == "approve" else "rejected"
				return self.artifacts()[0]
			def events_after(self, seq): return [{"seq":1,"event":"stage_end","payload":{"stage":"video"}}] if seq < 1 else []
			def snapshot(self): return {"job_id":"jobx","status":"done","artifacts":self.artifacts()}
			def slide_path(self, slide_id): return str(video) if slide_id == "p1" else None
		facade = FakeFacade()
		with patch.dict(serve._studio_jobs, {"jobx":facade}):
			path = "/api/studio/artifacts/" + artifact_id + "/content"
			for range_header, expected, data in ((None,200,b"0123456789"),("bytes=2-4",206,b"234"),
				("bytes=99-",416,b"")):
				with self.subTest(range_header=range_header):
					conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
					try:
						conn.request("GET", path+"?download=1", headers={"Range":range_header} if range_header else {})
						response = conn.getresponse()
						self.assertEqual(response.status, expected)
						self.assertEqual(response.read(), data)
						if expected != 416: self.assertIn('filename="lesson.mp4"', response.getheader("Content-Disposition"))
					finally: conn.close()
			status, _, payload = self.request("POST", "/api/studio/artifacts/"+artifact_id+"/review",
				b'{"decision":"invalid"}', {"X-Studio-CSRF":token,"Content-Type":"application/json"})
			self.assertEqual((status,payload["code"]),(400,"invalid_decision"))
			status, _, payload = self.request("POST", "/api/studio/artifacts/"+artifact_id+"/review",
				b'{"decision":"approve"}', {"X-Studio-CSRF":token,"Content-Type":"application/json"})
			self.assertEqual((status,payload["artifact"]["status"]),(200,"approved"))
			status, _, payload = self.request("POST", "/api/studio/artifacts/"+artifact_id+"/review",
				b'{"decision":"reject"}', {"X-Studio-CSRF":token,"Content-Type":"application/json"})
			self.assertEqual((status,payload["code"]),(409,"artifact_conflict"))
			conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
			try:
				conn.request("GET", "/api/studio/jobs/jobx/events?after=0")
				response = conn.getresponse()
				body = response.read().decode()
				self.assertEqual(response.status,200)
				self.assertIn("id: 1",body)
				self.assertIn("event: snapshot",body)
			finally: conn.close()


	def test_deck_plan_job_preview_and_approval_without_tts(self):
		from copy import deepcopy
		from studio import catalog as catalog_module
		from tests.test_studio_deck_builder import MATERIAL
		from tests.test_studio_deck_contracts import sample_deck_v11 as sample_deck
		import time
		token = self.session()
		source = self.store.add_upload("lesson.txt", MATERIAL.encode())
		request = {"contract_version": "1.0", "instruction": "做線上簡報",
			"source": {key: source[key] for key in ("kind", "ref", "revision")}}
		headers = {"X-Studio-CSRF": token, "Content-Type": "application/json"}
		available = deepcopy(catalog_module.CAPABILITIES)
		for item in available:
			if item["id"] == "slides.lesson_deck.v1": item["availability"] = "available"
		with (patch.object(catalog_module, "CAPABILITIES", available),
			patch.object(serve, "tts_ready", side_effect=AssertionError("Deck 不應檢查 TTS")),
			patch.object(serve, "complete_json", return_value=(sample_deck(),
				{'provider':'anthropic','model':'claude-opus-5-5','in':100,'out':200}))):
			status, _, planned = self.request("POST", "/api/studio/plans", json.dumps(request).encode(), headers)
			self.assertEqual(status, 201)
			self.assertEqual(planned["plan"]["steps"][0]["capability_id"], "slides.lesson_deck.v1")
			status, _, created = self.request("POST", "/api/studio/jobs",
				json.dumps({"plan_id": planned["plan_id"]}).encode(), headers)
			self.assertEqual(status, 201)
			deadline = time.monotonic() + 2
			while time.monotonic() < deadline:
				status, _, snapshot = self.request("GET", "/api/studio/jobs/" + created["job_id"])
				if snapshot["status"] in ("done", "failed"): break
				time.sleep(0.01)
			self.assertEqual(snapshot["status"], "done")
			self.assertEqual(snapshot['usage']['total_tokens'],300)
			self.assertAlmostEqual(snapshot['usage']['estimated_cost_usd'],.0044)
			artifact = snapshot["artifacts"][0]
			status, _, deck = self.request("GET", artifact["preview"]["url"])
			self.assertEqual(status, 200)
			self.assertEqual(deck, sample_deck())
			status, _, review = self.request("POST", "/api/studio/artifacts/"+artifact["artifact_id"]+"/review",
				b'{"decision":"approve"}', headers)
			self.assertEqual((status, review["artifact"]["status"]), (200, "approved"))
			conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
			try:
				conn.request("GET", review["artifact"]["download"]["url"])
				response = conn.getresponse()
				pptx_bytes = response.read()
				self.assertEqual(response.status, 200)
				self.assertIn("presentationml.presentation", response.getheader("Content-Type"))
				self.assertIn('filename="lesson.pptx"', response.getheader("Content-Disposition"))
				from pptx import Presentation
				self.assertEqual(len(Presentation(io.BytesIO(pptx_bytes)).slides), 4)
			finally: conn.close()
			self.assertFalse(list(Path(self.tmp.name).glob(".studio_job_*")))


	def test_mindmap_job_preview_review_and_svg_download(self):
		from tests.test_studio_mindmap import MATERIAL, sample_map
		late_material = "前" * 600 + MATERIAL
		import time
		token = self.session()
		source = self.store.add_upload("lesson.txt", late_material.encode())
		request = {"contract_version": "1.0", "instruction": "做成心智圖",
			"source": {key: source[key] for key in ("kind", "ref", "revision")}}
		headers = {"X-Studio-CSRF": token, "Content-Type": "application/json"}
		with (patch.object(serve, "tts_ready", side_effect=AssertionError("心智圖不應檢查 TTS")),
			patch.object(serve, "complete_json", return_value=(sample_map(), {}))):
			status, _, planned = self.request("POST", "/api/studio/plans", json.dumps(request).encode(), headers)
			self.assertEqual(status, 201)
			self.assertEqual(planned["plan"]["steps"][0]["template_id"], "mindmap.concept_overview.default.v1")
			status, _, created = self.request("POST", "/api/studio/jobs",
				json.dumps({"plan_id": planned["plan_id"]}).encode(), headers)
			self.assertEqual(status, 201)
			deadline = time.monotonic() + 2
			while time.monotonic() < deadline:
				status, _, snapshot = self.request("GET", "/api/studio/jobs/" + created["job_id"])
				if snapshot["status"] in ("done", "failed"): break
				time.sleep(0.01)
			self.assertEqual(snapshot["status"], "done", snapshot.get("error"))
			artifact = snapshot["artifacts"][0]
			self.assertEqual(artifact["kind"], "mindmap")
			self.assertNotIn("條件控制是否繼續", source["preview_excerpt"])
			status, _, full_source = self.request("GET", "/api/studio/jobs/" + created["job_id"] + "/source")
			self.assertEqual(status, 200)
			self.assertEqual(full_source["revision"], source["revision"])
			self.assertGreater(full_source["text"].index("條件控制是否繼續"), 500)
			self.assertNotIn(self.tmp.name, str(full_source))
			status, _, _ = self.request("DELETE", "/api/studio/sources/" + source["ref"], headers=headers)
			self.assertEqual(status, 200)
			self.assertEqual(self.request("GET", "/api/studio/jobs/" + created["job_id"] + "/source")[2], full_source)
			status, _, data = self.request("GET", artifact["preview"]["url"])
			self.assertEqual((status, data), (200, sample_map()))
			def raw(path):
				conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
				try:
					conn.request("GET", path)
					response = conn.getresponse()
					return response.status, dict(response.getheaders()), response.read()
				finally: conn.close()
			status, svg_headers, svg = raw(artifact["preview"]["url"] + "?view=svg")
			self.assertEqual(status, 200)
			self.assertIn("image/svg+xml", svg_headers["Content-Type"])
			self.assertIn(b"<svg", svg)
			self.assertIn("完整教材", svg.decode())
			self.assertIn("條件控制是否繼續", svg.decode())
			self.assertEqual(raw(artifact["preview"]["url"] + "?download=1")[0], 409)
			status, _, approved = self.request("POST", "/api/studio/artifacts/"+artifact["artifact_id"]+"/review",
				b'{"decision":"approve"}', headers)
			self.assertEqual((status, approved["artifact"]["status"]), (200, "approved"))
			status, download_headers, downloaded = raw(approved["artifact"]["download"]["url"])
			self.assertEqual((status, downloaded), (200, svg))
			self.assertIn('filename="lesson-mindmap.svg"', download_headers["Content-Disposition"])
			self.assertEqual(self.request("GET", "/api/studio/jobs/"+created["job_id"]+"/artifacts")[2]["artifacts"][0]["status"], "approved")
			self.assertFalse(list(Path(self.tmp.name).glob(".studio_job_*")))

	def test_legacy_upload_respects_studio_execution_slot(self):
		token = self.session()
		body = (b"--X\r\n" b'Content-Disposition: form-data; name="file"; filename="lesson.txt"\r\n'
			b"Content-Type: text/plain\r\n\r\nhello\r\n--X--\r\n")
		headers = {"X-Studio-CSRF": token, "Content-Type": "multipart/form-data; boundary=X"}
		self.assertTrue(serve._execution_slot.claim("studio:busy"))
		try:
			fake_runner = lambda *args, **kwargs: (lambda first, last: iter([
				{"event": "stage_fail", "stage": "lesson", "code": 1}]))
			with (patch.object(serve, "_job", None), patch.object(serve, "MATERIALS", self.tmp.name),
				patch.object(serve, "OUT", self.tmp.name), patch.object(serve, "tts_ready", return_value=True),
				patch.object(serve, "real_runner", side_effect=fake_runner)):
				status, _, payload = self.request("POST", "/jobs", body, headers)
			self.assertEqual(status, 409)
			self.assertFalse(list(Path(self.tmp.name).glob("lesson*")))
		finally:
			serve._execution_slot.release("studio:busy")
