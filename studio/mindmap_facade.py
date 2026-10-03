"""心智圖工作的安全狀態、事件與產物審核。"""

from copy import deepcopy
import logging
from pathlib import Path
import re
import threading
import uuid

from studio.mindmap import MindmapError, build_mindmap, canonical_mindmap, render_mindmap_svg
from studio.video_facade import FacadeError
from video_engine.usage import UsageLedger, capture_call


_CAPABILITY_ID = "mindmap.concept_overview.v1"


class MindmapJobFacade:
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
		self._map = None
		self._svg = None
		self._source_text = None
		self._artifact = None
		self._released = False
		self.usage = UsageLedger()

	@classmethod
	def restore_completed(cls, snapshot, mindmap, source_text):
		"""從已驗證的結果重繪 SVG；不再呼叫模型。"""
		if (not isinstance(snapshot, dict) or snapshot.get("status") != "done" or
			snapshot.get("capability_id") != _CAPABILITY_ID or
			not isinstance(source_text, str) or not source_text.strip() or
			len(snapshot.get("artifacts", [])) != 1):
			raise MindmapError("無法還原心智圖成果")
		artifact = snapshot["artifacts"][0]
		source = snapshot.get("source")
		if (not isinstance(artifact, dict) or artifact.get("kind") != "mindmap" or
			not isinstance(source, dict) or artifact.get("source_revision") != source.get("revision")):
			raise MindmapError("心智圖來源版本不一致")
		mindmap = canonical_mindmap(mindmap)
		normalized = re.sub(r"\s+", " ", source_text).strip()
		for item in mindmap["nodes"] + mindmap["edges"]:
			if re.sub(r"\s+", " ", item["source_quote"]).strip() not in normalized:
				raise MindmapError("心智圖引用無法在原文定位")
		obj = cls(snapshot["job_id"], snapshot["plan_id"], source,
			None, None, None, None, "", None)
		obj._status = "done"
		obj._pct = 100
		obj._stage = "publish"
		obj._map = mindmap
		obj._source_text = normalized
		obj._svg = render_mindmap_svg(mindmap, normalized)
		obj._artifact = deepcopy(artifact)
		obj._released = True
		obj.usage = UsageLedger.restore(snapshot.get('usage'))
		return obj

	def close(self):
		# 供應商請求執行中無法中斷；完成時仍釋放快照與 slot。
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
			complete = lambda *args: capture_call(self.usage, 'mindmap', self.complete_json, *args)
			mindmap = build_mindmap(material, self.instruction, complete)
			with self._lock:
				self._event("stage_end", "draft")
				self._stage = "validate"
				self._pct = 75
				self._event("stage_start", "validate")
			svg = render_mindmap_svg(mindmap, material)
			with self._lock:
				self._map = mindmap
				self._svg = svg
				self._source_text = re.sub(r"\s+", " ", material).strip()
				self._event("stage_end", "validate")
				self._stage = "publish"
				self._pct = 95
				self._event("stage_start", "publish")
				artifact_id = "artifact-" + uuid.uuid4().hex
				self._artifact = {"artifact_id": artifact_id, "kind": "mindmap",
					"capability_id": _CAPABILITY_ID, "source_revision": self.source["revision"],
					"status": "needs_review", "preview": {"type": "mindmap",
						"url": f"/api/studio/artifacts/{artifact_id}/content"},
					"download": None, "validation": {"status": "passed", "messages": []}}
				self._event("stage_end", "publish")
				self._status = "done"
				self._pct = 100
		except (MindmapError, OSError, UnicodeError) as exc:
			category = type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__
			logging.warning("mindmap job 生成或驗證失敗 (%s)", category)
			with self._lock:
				self._status = "failed"
				self._error = {"code": "mindmap_failed", "safe_message": "心智圖生成或來源驗證失敗，請檢查教材後重試"}
				self._event("stage_fail", self._stage)
		except Exception:
			logging.exception("mindmap job 未預期失敗")
			with self._lock:
				self._status = "failed"
				self._error = {"code": "mindmap_failed", "safe_message": "心智圖工作失敗，請檢查本機服務"}
				self._event("stage_fail", self._stage)
		finally:
			self._release()

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
		raise FacadeError("review_conflict", "心智圖請在成果頁審核")

	def submit_review(self, segments):
		raise FacadeError("review_conflict", "心智圖沒有講稿審核階段")

	def artifacts(self):
		with self._lock:
			return [deepcopy(self._artifact)] if self._artifact else []

	def _check_artifact(self, artifact_id):
		if self._artifact is None or artifact_id != self._artifact["artifact_id"]:
			raise FacadeError("artifact_missing", "找不到心智圖產物")

	def artifact_content(self, artifact_id):
		with self._lock:
			self._check_artifact(artifact_id)
			return deepcopy(self._map)

	def source_content(self):
		with self._lock:
			if self._source_text is None:
				raise FacadeError("source_unavailable", "心智圖原文尚未可用")
			return {"revision": self.source["revision"], "text": self._source_text}

	def svg_content(self, artifact_id, download=False):
		with self._lock:
			self._check_artifact(artifact_id)
			if download and self._artifact["status"] != "approved":
				raise FacadeError("artifact_conflict", "心智圖需先核可才能下載")
			return self._svg

	def review_artifact(self, artifact_id, decision):
		if decision not in ("approve", "reject"):
			raise FacadeError("invalid_decision", "產物審核決定不正確")
		with self._lock:
			self._check_artifact(artifact_id)
			if self._artifact["status"] != "needs_review":
				raise FacadeError("artifact_conflict", "產物已完成審核")
			self._artifact["status"] = "approved" if decision == "approve" else "rejected"
			if decision == "approve":
				name = Path(self.source["original_name"]).stem
				name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._") or "lesson"
				self._artifact["download"] = {"file_name": name + "-mindmap.svg",
					"url": self._artifact["preview"]["url"] + "?download=1"}
			return deepcopy(self._artifact)
