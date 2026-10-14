import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from studio.sources import SourceError, SourceStore


class TestSourceStore(unittest.TestCase):
	def test_normalization_failure_and_retry_keep_usage_without_recounting_reuse(self):
		from video_engine.usage import report_usage
		from studio.material_normalizer import NormalizationError
		source = self.store.add_upload('test.txt', b'material')
		def failed(record):
			report_usage('google', 'gemini-3.8-flash', {'in':10,'out':20,'thinking':5})
			raise NormalizationError('invalid material')
		with self.assertRaises(SourceError) as caught:
			self.store.normalize(source['ref'], source['revision'], failed)
		self.assertEqual(caught.exception.source['normalization_usage']['total_tokens'],35)
		result = self.store.normalize(source['ref'], source['revision'], lambda _:('整理後',
			{'provider':'google','model':'gemini-3.8-flash','in':1,'out':2,'thinking':3}))
		self.assertEqual(result['normalization_usage']['total_tokens'],41)
		self.assertEqual(result['normalization_usage']['call_count'],2)
		reused = self.store.normalize(source['ref'], source['revision'], lambda _:self.fail('no repeated call'))
		self.assertEqual(reused['normalization_usage'],result['normalization_usage'])
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.root = Path(self.tmp.name)
		self.store = SourceStore(self.root)
		self.addCleanup(self.store.close)

	def test_upload_public_payload_and_immutable_job_snapshot(self):
		public = self.store.add_upload("teacher.txt", b"hello\n")
		self.assertEqual(public["kind"], "upload")
		self.assertRegex(public["ref"], r"^material:[0-9a-f]{32}$")
		self.assertEqual(public["revision"], "sha256:" + hashlib.sha256(b"hello\n").hexdigest())
		self.assertNotIn("path", str(public).lower())
		self.assertNotIn(str(self.root), str(public))
		record = self.store.resolve(public["ref"], public["revision"])
		self.assertEqual(Path(record.material_path).read_bytes(), b"hello\n")
		snapshot = Path(self.store.snapshot_for_job(public["ref"], public["revision"], "job1"))
		self.assertTrue(snapshot.name.startswith(".studio_job_"))
		self.assertEqual(snapshot.read_bytes(), b"hello\n")
		self.assertEqual(snapshot.stat().st_mode & 0o777, 0o600)
		self.store.release_path(snapshot)
		self.assertFalse(snapshot.exists())

	def test_changed_or_missing_material_is_stale(self):
		public = self.store.add_upload("teacher.md", b"original")
		record = self.store.resolve(public["ref"], public["revision"])
		Path(record.material_path).write_bytes(b"changed")
		with self.assertRaises(SourceError) as context:
			self.store.snapshot_for_job(public["ref"], public["revision"], "job1")
		self.assertEqual(context.exception.code, "stale_source")
		self.assertFalse(any(p.name.startswith(".studio_job_") for p in self.root.iterdir()))
		Path(record.material_path).unlink()
		with self.assertRaises(SourceError) as context:
			self.store.resolve(public["ref"], public["revision"])
		self.assertEqual(context.exception.code, "stale_source")

	def test_missing_ref_and_limits(self):
		with self.assertRaises(SourceError) as context:
			self.store.resolve("material:unknown", "sha256:" + "a" * 64)
		self.assertEqual(context.exception.code, "source_missing")
		self.store.MAX_SOURCES = 1
		self.store.add_upload("one.txt", b"one")
		with self.assertRaises(SourceError) as context:
			self.store.add_upload("two.txt", b"two")
		self.assertEqual(context.exception.code, "source_limit")

	def test_cleanup_only_reserved_regular_files(self):
		keep = self.root / "teacher.md"
		keep.write_text("keep")
		outside = self.root / "outside.md"
		outside.write_text("outside")
		link = self.root / ".studio_source_link.md"
		link.symlink_to(outside)
		orphan = self.root / ".studio_job_orphan.md"
		orphan.write_text("orphan")
		self.store.cleanup_orphans()
		self.assertFalse(orphan.exists())
		self.assertTrue(link.is_symlink())
		self.assertEqual(keep.read_text(), "keep")
		self.assertEqual(outside.read_text(), "outside")

	def test_upload_rejects_material_too_long_for_ai_before_model_call(self):
		with self.assertRaises(SourceError) as context:
			self.store.add_upload("long.txt", b"a" * 60001)
		self.assertEqual(context.exception.code, "invalid_upload")
		self.assertIn("6 萬字", context.exception.safe_message)
		self.assertFalse(any(self.root.glob(".studio_source_*")))

	def test_delete_and_close_release_owned_files(self):
		public = self.store.add_upload("teacher.txt", b"hello")
		owned = set(self.root.iterdir())
		self.assertTrue(owned)
		self.store.remove(public["ref"])
		self.assertTrue(all(not p.exists() for p in owned))
		public = self.store.add_upload("teacher.txt", b"next")
		self.store.close()
		self.assertFalse(any(p.name.startswith(".studio_source_") for p in self.root.iterdir()))

	def test_preview_uses_normalized_newlines_and_bad_ref_is_safe(self):
		public = self.store.add_upload("windows.txt", b"a\r\nb\r\n")
		self.assertEqual(public["preview_excerpt"], "a\nb\n")
		with self.assertRaises(SourceError):
			self.store.resolve([], public["revision"])
