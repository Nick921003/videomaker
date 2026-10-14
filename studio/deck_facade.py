"""線上簡報工作的安全狀態、進度與產物審核。"""

from copy import deepcopy
import logging
from pathlib import Path
import re
import threading
import uuid

from studio.deck_builder import build_deck
from studio.deck_contracts import DeckError
from studio.pptx_export import export_pptx
from studio.video_facade import FacadeError
from video_engine.usage import UsageLedger, capture_call


_CAPABILITY_ID = "slides.lesson_deck.v1"


class DeckJobFacade:
	def __init__(self, job_id, plan_id, source, snapshot_path, source_store, slot,
		owner, instruction, complete_json):
		self.job_id = job_id
		self.plan_id = plan_id
		self.source = deepcopy(source)
		self.snapshot_path = snapshot_path
		self.source_store = source_store
		self.slot = slot
		self.owner = owner
		self.instruction = instruction
		self.complete_json = complete_json
		self._lock = threading.RLock()
		self._status = "queued"
		self._pct = 0
		self._stage = None
		self._events = []
		self._error = None
		self._deck = None
		self._artifact = None
		self._pptx_bytes = None
		self._released = False
		self.usage = UsageLedger()

	def close(self):
		# 執行中的供應商請求無法中斷；完成後仍會釋放快照與 slot。
		pass

	def _event(self, name, stage):
		self._events.append({"seq": len(self._events) + 1, "event": name,
			"payload": {"event": name, "stage": stage}})

	def _release(self):
		with self._lock:
			if self._released:
				return
			self._released = True
		self.source_store.release_path(self.snapshot_path)
		self.slot.release(self.owner)

	def start(self):
		try:
			with self._lock:
				self._status = "running"
				self._stage = "draft"
				self._pct = 10
				self._event("stage_start", "draft")
			material = Path(self.snapshot_path).read_text(encoding="utf-8")
			complete = lambda *args: capture_call(self.usage, 'deck', self.complete_json, *args)
			deck = build_deck(material, self.instruction, complete)
			with self._lock:
				self._event("stage_end", "draft")
				self._stage = "validate"
				self._pct = 75
				self._event("stage_start", "validate")
				self._deck = deck
				self._event("stage_end", "validate")
				self._stage = "publish"
				self._pct = 95
				self._event("stage_start", "publish")
				self._make_artifact()
				self._event("stage_end", "publish")
				self._status = "done"
				self._pct = 100
		except (DeckError, OSError, UnicodeError) as exc:
			logging.warning("deck job 失敗: %s", type(exc).__name__)
			with self._lock:
				self._status = "failed"
				self._error = {"code": "deck_failed", "safe_message": "簡報生成或驗證失敗，請檢查教材內容後重試"}
				self._event("stage_fail", self._stage)
		except Exception:
			logging.exception("deck job 未預期失敗")
			with self._lock:
				self._status = "failed"
				self._error = {"code": "deck_failed", "safe_message": "簡報工作失敗，請檢查本機服務"}
				self._event("stage_fail", self._stage)
		finally:
			self._release()

	def _make_artifact(self):
		artifact_id = "artifact-" + uuid.uuid4().hex
		base = f"/api/studio/artifacts/{artifact_id}/content"
		self._artifact = {"artifact_id": artifact_id, "kind": "deck",
			"capability_id": _CAPABILITY_ID, "source_revision": self.source["revision"],
			"status": "needs_review", "preview": {"type": "deck", "url": base},
			"download": None, "validation": {"status": "passed", "messages": []}}

	def snapshot(self):
		with self._lock:
			return {"job_id": self.job_id, "status": self._status, "pct": self._pct,
				"stage": self._stage, "capability_id": _CAPABILITY_ID,
				"error": deepcopy(self._error), "source": deepcopy(self.source),
				"plan_id": self.plan_id, "artifacts": self.artifacts(), "usage":self.usage.summary()}

	def events_after(self, seq):
		if not isinstance(seq, int) or isinstance(seq, bool) or seq < 0:
			raise FacadeError("invalid_cursor", "事件游標不正確")
		with self._lock:
			return deepcopy(self._events[seq:])

	def get_review(self):
		raise FacadeError("review_conflict", "簡報請在成果頁審核")

	def submit_review(self, segments):
		raise FacadeError("review_conflict", "簡報沒有講稿審核階段")

	def artifacts(self):
		with self._lock:
			return [deepcopy(self._artifact)] if self._artifact else []

	def artifact_content(self, artifact_id):
		with self._lock:
			if self._artifact is None or artifact_id != self._artifact["artifact_id"]:
				raise FacadeError("artifact_missing", "找不到簡報產物")
			return deepcopy(self._deck)


	def pptx_content(self, artifact_id):
		with self._lock:
			if self._artifact is None or artifact_id != self._artifact["artifact_id"]:
				raise FacadeError("artifact_missing", "找不到簡報產物")
			if self._artifact["status"] != "approved":
				raise FacadeError("artifact_conflict", "簡報需先核可才能下載")
			if self._pptx_bytes is None:
				self._pptx_bytes = export_pptx(self._deck)
			return self._pptx_bytes

	def review_artifact(self, artifact_id, decision):
		if decision not in ("approve", "reject"):
			raise FacadeError("invalid_decision", "產物審核決定不正確")
		with self._lock:
			if self._artifact is None or artifact_id != self._artifact["artifact_id"]:
				raise FacadeError("artifact_missing", "找不到簡報產物")
			if self._artifact["status"] != "needs_review":
				raise FacadeError("artifact_conflict", "產物已完成審核")
			if decision == "approve" and self._pptx_bytes is None:
				try:
					self._pptx_bytes = export_pptx(self._deck)
				except Exception as exc:
					logging.exception("deck PPTX 匯出失敗")
					raise FacadeError("export_failed", "可編輯 PPTX 暫時無法建立") from exc
			self._artifact["status"] = "approved" if decision == "approve" else "rejected"
			if decision == "approve":
				name = Path(self.source["original_name"]).stem
				name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._") or "lesson"
				self._artifact["download"] = {"file_name": name + ".pptx",
					"url": self._artifact["preview"]["url"] + "?download=1"}
			return deepcopy(self._artifact)
