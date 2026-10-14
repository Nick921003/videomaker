"""既有 Job 的工作台視圖：安全快照、審稿與產物生命週期。"""

from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import re
import shutil
import threading
import uuid
from urllib.parse import quote

from jobstate import REVIEW_SEC
from script_gate import read_segments, revalidate, write_segments
from video_engine.ingest import lesson_id_for
from video_engine.usage import UsageLedger


_STUDIO_STEM = re.compile(r"studio_job_[0-9a-f]{32}_[0-9a-f]{32}")


def cleanup_studio_outputs(examples_root, out_root, preserve_dirs=()):
	"""只清除此工作台專用名稱的暫存 JSON 與輸出目錄。"""
	examples = Path(examples_root)
	if examples.is_dir() and not examples.is_symlink():
		for path in examples.iterdir():
			if path.is_symlink() or not path.is_file():
				continue
			stem = path.name.split(".", 1)[0]
			if _STUDIO_STEM.fullmatch(stem) and path.name in (
				f"{stem}.lesson.json", f"{stem}.actions.json", f"{stem}.actions.json.orig"):
				path.unlink()
	out = Path(out_root)
	preserve = {Path(path).absolute() for path in preserve_dirs}
	if out.is_dir() and not out.is_symlink():
		for path in out.iterdir():
			if path.absolute() in preserve:
				continue
			if path.is_symlink() or not path.is_dir() or not _STUDIO_STEM.fullmatch(path.name):
				continue
			shutil.rmtree(path)


class FacadeError(RuntimeError):
	def __init__(self, code, safe_message):
		super().__init__(safe_message)
		self.code = code
		self.safe_message = safe_message


def public_error(raw, stage):
	if stage in ("lesson", "slides", "actions", "validate", "storyboard", "synth", "timeline", "video"):
		return {"code": "stage_failed", "safe_message": f"{stage} 階段失敗，請檢查本機服務"}
	return {"code": "job_failed", "safe_message": "影片工作失敗，請檢查本機服務"}


class VideoJobFacade:
	def __init__(self, job, job_id, plan_id, source, snapshot_path, source_store, slot, owner):
		self.job = job
		self.usage = getattr(job, 'usage', None) or UsageLedger()
		self.job_id = job_id
		self.plan_id = plan_id
		self.source = deepcopy(source)
		self.snapshot_path = snapshot_path
		self.source_store = source_store
		self.slot = slot
		self.owner = owner
		self.reserved_dir = Path(job.out_dir) / lesson_id_for(snapshot_path)
		self._lock = threading.RLock()
		self._artifact = None
		self._artifact_path = None
		self._released = False
		self._stop = threading.Event()

	def close(self):
		self._stop.set()

	def _video_file(self):
		path = getattr(self.job, "video_path", None)
		if not path:
			raise FacadeError("artifact_missing", "影片檔案尚未完成")
		video = Path(path)
		reserved = self.reserved_dir
		try:
			if reserved.is_symlink() or video.is_symlink() or video.parent.resolve() != reserved.resolve():
				raise OSError("output containment")
			if not video.is_file() or video.stat().st_size <= 0:
				raise OSError("output missing")
		except OSError as exc:
			raise FacadeError("artifact_missing", "影片檔案缺失或無法使用") from exc
		return video

	def completion_check(self, job):
		try:
			self._video_file()
		except FacadeError as exc:
			return exc.safe_message
		return None

	def _release_if_terminal(self):
		with self._lock:
			if self._released or self.job.status not in ("done", "failed"):
				return
			self._released = True
			self._stop.set()
			self.source_store.release_path(self.snapshot_path)
			self.slot.release(self.owner)

	def start(self):
		try:
			self.job.start()
		except Exception as exc:
			logging.exception("studio job 啟動失敗")
			self.job.status = "failed"
			self.job.error = str(exc)
		if self.job.status == "awaiting_review":
			threading.Thread(target=self._review_timer, daemon=True).start()
		else:
			if self.job.status == "done":
				try:
					self.finalize_artifact()
				except FacadeError:
					self.job.status = "failed"
			self._release_if_terminal()

	def _review_timer(self):
		while not self._stop.is_set() and self.job.status == "awaiting_review":
			if self.job.review_expired() and self.job.claim():
				self.job.notice = "倒數結束，已用原稿繼續"
				self._resume_async()
				return
			self._stop.wait(0.5)

	def _resume_async(self):
		threading.Thread(target=self._run_resume, daemon=True).start()

	def _run_resume(self):
		try:
			self.job.resume()
			if self.job.status == "done":
				self.finalize_artifact()
		except Exception as exc:
			logging.exception("studio job 續跑失敗")
			self.job.status = "failed"
			self.job.error = str(exc)
		finally:
			self._release_if_terminal()

	def snapshot(self):
		self._release_if_terminal()
		with self._lock:
			return {"job_id": self.job_id, "status": self.job.status, "pct": self.job.pct,
				"stage": self.job.stage, "capability_id": "video.micro_lesson.v1",
				"error": public_error(self.job.error, self.job.stage) if self.job.status == "failed" else None,
				"source": deepcopy(self.source), "plan_id": self.plan_id,
				"artifacts": self.artifacts(), "usage":self.usage.summary()}

	def events_after(self, seq):
		if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
			raise FacadeError("invalid_cursor", "事件游標不正確")
		events = list(self.job.events)
		result = []
		for index, event in enumerate(events, start=1):
			if index <= seq:
				continue
			event_name = event.get("event")
			if event_name not in ("stage_start", "stage_end", "stage_fail"):
				event_name = "unknown_event"
			stage = event.get("stage")
			if stage not in ("lesson", "slides", "actions", "validate", "storyboard", "synth", "timeline", "video"):
				stage = None
			payload = {"event": event_name, "stage": stage}
			if event_name == "stage_fail":
				payload["error"] = public_error(event.get("tail"), stage)
			result.append({"seq": index, "event": payload["event"], "payload": payload})
		return result

	def get_review(self):
		if self.job.status != "awaiting_review":
			raise FacadeError("review_conflict", "現在不在講稿審核階段")
		try:
			segments = read_segments(self.job.actions_path)
			with open(self.job.layout_path, encoding="utf-8") as handle:
				layout = json.load(handle)
			slides = [{"slide_id": item["slide_id"],
				"preview_url": f"/api/studio/jobs/{self.job_id}/slides/{quote(item['slide_id'], safe='')}"}
				for item in layout["slides"]]
		except (OSError, ValueError, KeyError, TypeError) as exc:
			logging.exception("studio 審稿資料讀取失敗")
			raise FacadeError("review_unavailable", "講稿預覽目前無法讀取") from exc
		return {"segments": segments, "deadline": self.job.review_deadline, "slides": slides}

	def submit_review(self, segments):
		if not isinstance(segments, list):
			raise FacadeError("invalid_review", "講稿格式不正確")
		if not self.job.claim():
			raise FacadeError("review_conflict", "講稿審核已由另一個請求處理")
		notice = None
		try:
			if segments:
				shutil.copyfile(self.job.actions_path, self.job.actions_backup)
				write_segments(self.job.actions_path, segments)
				try:
					errors = revalidate(self.job.lesson_path, self.job.actions_path, self.job.sec)
				except Exception:
					logging.exception("studio 講稿重驗失敗")
					errors = ["講稿驗證暫時無法完成"]
				if errors:
					shutil.copyfile(self.job.actions_backup, self.job.actions_path)
					if not self.job.retried:
						self.job.retried = True
						self.job.status = "awaiting_review"
						self.job.review_deadline = self.job.clock() + REVIEW_SEC
						threading.Thread(target=self._review_timer, daemon=True).start()
						return {"ok": False, "errors": [{"code": "script_invalid",
							"safe_message": "講稿未通過驗證，請檢查長度、用詞與動作目標"}],
							"deadline": self.job.review_deadline, "notice": None}
					notice = "講稿兩次未通過驗證，已用原稿繼續"
		except Exception as exc:
			logging.exception("studio 審稿提交失敗")
			self.job.status = "failed"
			self.job.error = str(exc)
			self._release_if_terminal()
			raise FacadeError("review_failed", "講稿審核失敗") from exc
		self.job.notice = notice
		self._resume_async()
		return {"ok": True, "errors": [], "deadline": None, "notice": notice}

	def slide_path(self, slide_id):
		if not isinstance(slide_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", slide_id):
			raise FacadeError("slide_missing", "找不到投影片")
		try:
			with open(self.job.layout_path, encoding="utf-8") as handle:
				ids = [item["slide_id"] for item in json.load(handle)["slides"]]
			index = ids.index(slide_id) + 1
			path = Path(self.job.layout_path).parent / f"slide_{index:02d}_full.png"
			if path.is_symlink() or not path.is_file() or path.parent.resolve() != self.reserved_dir.resolve():
				raise OSError("slide missing")
		except (OSError, ValueError, KeyError, TypeError) as exc:
			raise FacadeError("slide_missing", "找不到投影片") from exc
		return str(path)

	def finalize_artifact(self):
		with self._lock:
			if self._artifact is not None:
				return deepcopy(self._artifact)
			if self.job.status != "done":
				raise FacadeError("artifact_not_ready", "影片尚未完成")
			video = self._video_file()
			artifact_id = "artifact-" + uuid.uuid4().hex
			name = Path(self.source["original_name"]).stem
			name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._") or "video"
			file_name = name + ".mp4"
			base = f"/api/studio/artifacts/{artifact_id}/content"
			self._artifact = {"artifact_id": artifact_id, "kind": "video",
				"capability_id": "video.micro_lesson.v1", "source_revision": self.source["revision"],
				"status": "needs_review", "preview": {"type": "video", "url": base},
				"download": {"file_name": file_name, "url": base + "?download=1"},
				"validation": {"status": "passed", "messages": []}}
			self._artifact_path = str(video)
			return deepcopy(self._artifact)

	def artifacts(self):
		with self._lock:
			return [deepcopy(self._artifact)] if self._artifact else []

	def artifact_content(self, artifact_id):
		with self._lock:
			if self._artifact is None or artifact_id != self._artifact["artifact_id"]:
				raise FacadeError("artifact_missing", "找不到影片產物")
			self._video_file()
			return self._artifact_path

	def review_artifact(self, artifact_id, decision):
		if decision not in ("approve", "reject"):
			raise FacadeError("invalid_decision", "產物審核決定不正確")
		with self._lock:
			if self._artifact is None or artifact_id != self._artifact["artifact_id"]:
				raise FacadeError("artifact_missing", "找不到影片產物")
			if self._artifact["status"] != "needs_review":
				raise FacadeError("artifact_conflict", "產物已完成審核")
			self._artifact["status"] = "approved" if decision == "approve" else "rejected"
			return deepcopy(self._artifact)
