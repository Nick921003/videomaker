from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
from unittest.mock import patch
import json
import time
import unittest

from studio.execution import ExecutionSlot
from studio.sources import SourceStore
from studio.video_facade import FacadeError, VideoJobFacade, cleanup_studio_outputs


class TestStudioOutputCleanup(unittest.TestCase):
	def test_only_generated_studio_outputs_are_removed(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp); examples = root / "examples"; out = root / "out"
			examples.mkdir(); out.mkdir()
			stem = "studio_job_" + "a"*32 + "_" + "b"*32
			generated = examples / f"{stem}.lesson.json"; generated.write_text("temporary")
			other = examples / "teacher.lesson.json"; other.write_text("keep")
			video_dir = out / stem; video_dir.mkdir(); (video_dir / "video.mp4").write_bytes(b"x")
			protected = root / "protected"; protected.write_text("keep")
			(out / ("studio_job_" + "c"*32 + "_" + "d"*32)).symlink_to(protected)
			cleanup_studio_outputs(examples, out)
			self.assertFalse(generated.exists()); self.assertFalse(video_dir.exists())
			self.assertTrue(other.exists()); self.assertEqual(protected.read_text(), "keep")

class TestVideoJobFacade(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		root = Path(self.tmp.name)
		self.store = SourceStore(root / "materials")
		self.addCleanup(self.store.close)
		self.source = self.store.add_upload("lesson.txt", b"hello")
		self.snapshot = self.store.snapshot_for_job(self.source["ref"], self.source["revision"], "job1")
		self.out_dir = root / "out"
		self.reserved = self.out_dir / Path(self.snapshot).stem.lstrip(".")
		self.reserved.mkdir(parents=True)
		self.video = self.reserved / "lesson.mp4"
		self.video.write_bytes(b"video")
		self.job = SimpleNamespace(status="done", pct=100, stage=None, error=None,
			events=[], video_path=str(self.video), out_dir=str(self.out_dir),
			material_path=self.snapshot, review_deadline=None)
		self.slot = ExecutionSlot()
		self.assertTrue(self.slot.claim("studio:job1"))
		self.facade = VideoJobFacade(self.job, "job1", "plan1", self.source,
			self.snapshot, self.store, self.slot, "studio:job1")
		self.addCleanup(self.facade.close)

	def test_status_derives_from_job_and_artifact_created_once(self):
		self.assertEqual(self.facade.snapshot()["status"], "done")
		manifest = self.facade.finalize_artifact()
		self.assertEqual(manifest["status"], "needs_review")
		self.assertEqual(self.facade.finalize_artifact()["artifact_id"], manifest["artifact_id"])
		self.assertEqual(len(self.facade.artifacts()), 1)
		self.assertNotIn(self.tmp.name, str(self.facade.snapshot()))
		self.assertEqual(self.facade.artifact_content(manifest["artifact_id"]), str(self.video))

	def test_reject_is_terminal_and_review_race_has_one_winner(self):
		artifact_id = self.facade.finalize_artifact()["artifact_id"]
		barrier = threading.Barrier(3)
		results = []
		def decide(action):
			barrier.wait()
			try:
				self.facade.review_artifact(artifact_id, action)
				results.append("ok")
			except FacadeError as exc:
				results.append(exc.code)
		threads = [threading.Thread(target=decide, args=(action,)) for action in ("approve", "reject")]
		for thread in threads: thread.start()
		barrier.wait()
		for thread in threads: thread.join()
		self.assertEqual(sorted(results), ["artifact_conflict", "ok"])
		with self.assertRaises(FacadeError):
			self.facade.review_artifact(artifact_id, "approve")

	def test_outside_or_missing_video_never_becomes_artifact(self):
		self.job.video_path = str(Path(self.tmp.name) / "outside.mp4")
		with self.assertRaises(FacadeError):
			self.facade.finalize_artifact()
		self.assertEqual(self.facade.artifacts(), [])

	def test_raw_job_error_and_event_tail_never_leave_facade(self):
		self.job.status = "failed"
		self.job.stage = "synth"
		self.job.error = "Bearer secret /home/user/file traceback"
		self.job.events = [{"event": "stage_fail", "stage": "synth",
			"tail": ["Bearer secret /home/user/file traceback"]}]
		snapshot = self.facade.snapshot()
		events = self.facade.events_after(0)
		self.assertEqual(snapshot["status"], "failed")
		self.assertNotIn("secret", str(snapshot) + str(events))
		self.assertEqual(events[0]["seq"], 1)
		self.assertEqual(self.facade.events_after(1), [])

	def test_review_data_and_single_resume(self):
		actions = Path(self.tmp.name) / "actions.json"
		actions.write_text(json.dumps({"slides": [{"slide_id": "p1", "actions": [
			{"type": "speech", "text": "原稿"}]}]}), encoding="utf-8")
		layout = self.reserved / "layout.json"
		layout.write_text(json.dumps({"slides": [{"slide_id": "p1"}]}), encoding="utf-8")
		preview = self.reserved / "slide_01_full.png"
		preview.write_bytes(b"png")
		lock = threading.Lock()
		resumed = []
		def claim():
			with lock:
				if self.job.status != "awaiting_review":
					return False
				self.job.status = "running"
				return True
		def resume():
			resumed.append(True)
			self.job.status = "done"
		self.job.status = "awaiting_review"
		self.job.actions_path = str(actions)
		self.job.actions_backup = str(actions) + ".orig"
		self.job.layout_path = str(layout)
		self.job.lesson_path = str(Path(self.tmp.name) / "lesson.json")
		self.job.sec = 90
		self.job.retried = False
		self.job.clock = lambda: 1000
		self.job.review_deadline = 1060
		self.job.claim = claim
		self.job.resume = resume
		data = self.facade.get_review()
		self.assertEqual(data["segments"][0]["text"], "原稿")
		self.assertTrue(data["slides"][0]["preview_url"].endswith("/p1"))
		self.assertEqual(self.facade.slide_path("p1"), str(preview))
		barrier = threading.Barrier(3)
		results = []
		def submit():
			barrier.wait()
			try:
				results.append(self.facade.submit_review([])["ok"])
			except FacadeError as exc:
				results.append(exc.code)
		threads = [threading.Thread(target=submit) for _ in range(2)]
		for thread in threads: thread.start()
		barrier.wait()
		for thread in threads: thread.join()
		deadline = time.monotonic() + 2
		while not resumed and time.monotonic() < deadline:
			time.sleep(0.01)
		self.assertEqual(resumed, [True])
		self.assertCountEqual(results, [True, "review_conflict"])

	def test_invalid_review_reopens_deadline_without_releasing_slot(self):
		actions = Path(self.tmp.name) / "actions.json"
		actions.write_text(json.dumps({"slides": [{"slide_id": "p1", "actions": [
			{"type": "speech", "text": "原稿"}]}]}), encoding="utf-8")
		self.job.status = "awaiting_review"
		self.job.actions_path = str(actions)
		self.job.actions_backup = str(actions) + ".orig"
		self.job.lesson_path = str(Path(self.tmp.name) / "lesson.json")
		self.job.sec = 90
		self.job.retried = False
		self.job.clock = lambda: 1000
		self.job.review_expired = lambda: False
		self.job.claim = lambda: setattr(self.job, "status", "running") or True
		with patch("studio.video_facade.revalidate", return_value=["講稿無效"]):
			result = self.facade.submit_review([{"slide_id": "p1", "idx": 0, "text": "錯誤"}])
		self.assertFalse(result["ok"])
		self.assertEqual(self.job.status, "awaiting_review")
		self.assertEqual(self.job.review_deadline, 1060)
		self.assertEqual(self.slot.owner(), "studio:job1")
		self.assertEqual(json.loads(actions.read_text())["slides"][0]["actions"][0]["text"], "原稿")

	def test_event_and_review_errors_are_sanitized(self):
		self.job.events = [{"event": "Bearer secret", "stage": "/home/user/file"}]
		self.assertNotIn("secret", str(self.facade.events_after(0)))
		self.assertNotIn("/home/", str(self.facade.events_after(0)))
		actions = Path(self.tmp.name) / "actions.json"
		actions.write_text(json.dumps({"slides": [{"slide_id": "p1", "actions": [
			{"type": "speech", "text": "原稿"}]}]}), encoding="utf-8")
		self.job.status = "awaiting_review"
		self.job.actions_path = str(actions)
		self.job.actions_backup = str(actions) + ".orig"
		self.job.lesson_path = str(Path(self.tmp.name) / "lesson.json")
		self.job.sec = 90
		self.job.retried = False
		self.job.clock = lambda: 1000
		self.job.review_expired = lambda: False
		self.job.claim = lambda: setattr(self.job, "status", "running") or True
		with patch("studio.video_facade.revalidate", return_value=["Bearer secret /home/user/file traceback"]):
			result = self.facade.submit_review([{"slide_id": "p1", "idx": 0, "text": "錯誤"}])
		self.assertNotIn("secret", str(result))
		self.assertNotIn("/home/", str(result))
		self.assertEqual(set(result["errors"][0]), {"code", "safe_message"})

	def test_close_stops_review_timer(self):
		self.facade.close()
		self.assertTrue(self.facade._stop.is_set())
