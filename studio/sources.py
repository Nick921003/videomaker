"""教材來源的私有檔案索引與工作專用快照。"""

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import threading
import uuid

from video_engine.ingest import SUPPORTED, extract_text
from studio.material_normalizer import NormalizationError, check_normalization_limits, normalize_material
from video_engine.usage import UsageLedger, capture_call


class SourceError(RuntimeError):
	def __init__(self, code, safe_message):
		super().__init__(safe_message)
		self.code = code
		self.safe_message = safe_message


@dataclass(frozen=True)
class SourceRecord:
	ref: str
	revision: str
	material_path: str
	original_name: str
	original_size: int
	raw_path: str
	public: dict
	extracted_path: str
	extracted_revision: str | None = None


class SourceStore:
	MAX_SOURCES = 20
	MAX_TOTAL_BYTES = 50 * 1024 * 1024

	def __init__(self, workspace_dir):
		self.root = Path(workspace_dir).absolute()
		self.root.mkdir(parents=True, exist_ok=True)
		self._items = {}
		self._normalization_usage = {}
		self._owned = set()
		self._lock = threading.RLock()
		self.cleanup_orphans()

	def _owned_path(self, path):
		path = Path(path).absolute()
		return (path.parent == self.root and
			path.name.startswith((".studio_source_", ".studio_job_")))

	def _unlink(self, path):
		path = Path(path).absolute()
		if not self._owned_path(path) or path.is_symlink() or not path.is_file():
			return
		path.unlink()
		self._owned.discard(path)

	def cleanup_orphans(self):
		with self._lock:
			for path in self.root.iterdir():
				self._unlink(path)

	def _write_new(self, path, content):
		fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
		try:
			with os.fdopen(fd, "wb") as handle:
				handle.write(content)
		except BaseException:
			self._unlink(path)
			raise
		self._owned.add(Path(path))

	def add_upload(self, original_name, blob):
		if not isinstance(original_name, str) or not original_name or original_name != os.path.basename(original_name.replace("\\", "/")):
			raise SourceError("invalid_upload", "檔名不符合要求")
		if not isinstance(blob, bytes):
			raise SourceError("invalid_upload", "教材內容不符合要求")
		ext = Path(original_name).suffix.lower()
		if ext not in SUPPORTED:
			raise SourceError("unsupported_format", "只接受 .md、.txt、.pptx 或 .pdf")
		with self._lock:
			if len(self._items) >= self.MAX_SOURCES:
				raise SourceError("source_limit", "教材暫存數量已滿")
			uid = uuid.uuid4().hex
			raw = self.root / f".studio_source_{uid}_raw{ext}"
			normalized = self.root / f".studio_source_{uid}_normalized.md"
			try:
				self._write_new(raw, blob)
				text = extract_text(str(raw))
				check_normalization_limits(text, ext)
				content = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
				if not content.strip():
					raise ValueError("教材沒有可用文字")
				if sum(Path(item.material_path).stat().st_size for item in self._items.values()) + len(content) > self.MAX_TOTAL_BYTES:
					raise SourceError("source_limit", "教材暫存容量已滿")
				self._write_new(normalized, content)
			except SourceError:
				self._unlink(raw)
				self._unlink(normalized)
				raise
			except (ValueError, UnicodeError, OSError) as exc:
				self._unlink(raw)
				self._unlink(normalized)
				message = str(exc) if isinstance(exc, NormalizationError) else "教材無法讀取或沒有可用文字"
				raise SourceError("invalid_upload", message) from exc
			revision = "sha256:" + hashlib.sha256(content).hexdigest()
			ref = "material:" + uid
			public = {"kind": "upload", "ref": ref, "revision": revision,
				"original_name": original_name, "original_size": len(blob),
				"preview_excerpt": text[:500], "normalization_status": "pending",
				"extracted_excerpt": text[:2000]}
			record = SourceRecord(ref, revision, str(normalized), original_name, len(blob), str(raw), public, str(normalized), revision)
			self._items[ref] = record
			return dict(public)

	def _completed_retry(self, ref, revision):
		record = self._items.get(ref)
		if record is None or record.public.get("normalization_status") != "complete":
			return None
		if revision not in (record.revision, record.extracted_revision):
			return None
		self.resolve(ref, record.revision)
		if revision == record.extracted_revision:
			path = Path(record.extracted_path)
			if path.is_symlink() or not path.is_file() or "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() != revision:
				raise SourceError("stale_source", "教材已不存在或已變更")
		return dict(record.public)

	def normalize(self, ref, revision, normalizer=normalize_material):
		"""確認後整理教材；舊抽取稿保留，成功時原子切換公開 revision。"""
		with self._lock:
			completed = self._completed_retry(ref, revision)
			if completed is not None:
				return completed
			record = self.resolve(ref, revision)
			ledger = self._normalization_usage.setdefault(ref, UsageLedger())
		def fail(message, cause=None):
			with self._lock:
				record.public['normalization_usage'] = ledger.summary()
				source = dict(record.public)
			error = SourceError('normalization_failed', message)
			error.source = source
			raise error from cause
		try:
			cleaned, usage = capture_call(ledger, 'ingest', normalizer, record)
		except NormalizationError as exc:
			fail(str(exc), exc)
		except Exception as exc:
			fail('AI 整理失敗，原始抽取內容仍可保留；請稍後重試', exc)
		if not isinstance(cleaned, str) or not cleaned.strip():
			fail('AI 整理結果沒有可用文字')
		content = cleaned.encode("utf-8")
		if len(content) > 2 * 1024 * 1024:
			fail('AI 整理結果超過大小限制')
		with self._lock:
			completed = self._completed_retry(ref, revision)
			if completed is not None:
				return completed
			current = self.resolve(ref, revision)
			uid = ref.removeprefix("material:")
			path = self.root / f".studio_source_{uid}_ai_{uuid.uuid4().hex}.md"
			try:
				self._write_new(path, content)
				new_revision = "sha256:" + hashlib.sha256(content).hexdigest()
				public = dict(current.public, revision=new_revision,
					preview_excerpt=cleaned[:2000], normalization_status="complete",
					normalization_model=usage.get("model", "unknown") if isinstance(usage, dict) else "unknown",
					normalization_usage=ledger.summary())
				if isinstance(usage, dict) and usage.get("normalization_attention"):
					public["normalization_attention"] = usage["normalization_attention"]
				self._items[ref] = SourceRecord(ref, new_revision, str(path), current.original_name,
					current.original_size, current.raw_path, public, current.extracted_path, current.extracted_revision)
			except BaseException:
				self._unlink(path)
				raise
			return dict(public)

	def resolve(self, ref, revision):
		if not isinstance(ref, str) or not isinstance(revision, str):
			raise SourceError("source_missing", "教材來源不存在")
		with self._lock:
			record = self._items.get(ref)
			if record is None:
				raise SourceError("source_missing", "教材來源不存在")
			if revision != record.revision:
				raise SourceError("stale_source", "教材版本已變更，請重新上傳")
			path = Path(record.material_path)
			try:
				if path.is_symlink() or not path.is_file():
					raise OSError("not regular")
				content = path.read_bytes()
			except OSError as exc:
				raise SourceError("stale_source", "教材已不存在或已變更") from exc
			if "sha256:" + hashlib.sha256(content).hexdigest() != record.revision:
				raise SourceError("stale_source", "教材已不存在或已變更")
			return record

	def snapshot_for_job(self, ref, revision, job_id):
		with self._lock:
			record = self.resolve(ref, revision)
			content = Path(record.material_path).read_bytes()
			if "sha256:" + hashlib.sha256(content).hexdigest() != revision:
				raise SourceError("stale_source", "教材已不存在或已變更")
			if not isinstance(job_id, str) or not job_id.replace("-", "").isalnum():
				raise SourceError("invalid_job", "工作 ID 不符合要求")
			path = self.root / f".studio_job_{job_id}_{uuid.uuid4().hex}.md"
			self._write_new(path, content)
			return str(path)

	def release_path(self, path):
		with self._lock:
			self._unlink(path)

	def remove(self, ref):
		if not isinstance(ref, str):
			raise SourceError("source_missing", "教材來源不存在")
		with self._lock:
			record = self._items.pop(ref, None)
			self._normalization_usage.pop(ref, None)
			if record is None:
				raise SourceError("source_missing", "教材來源不存在")
			self._unlink(record.raw_path)
			self._unlink(record.material_path)
			self._unlink(record.extracted_path)

	def close(self, preserve_paths=()):
		with self._lock:
			preserve = {Path(path).absolute() for path in preserve_paths}
			for path in tuple(self._owned):
				if Path(path).absolute() not in preserve:
					self._unlink(path)
			self._items.clear()
			self._normalization_usage.clear()
