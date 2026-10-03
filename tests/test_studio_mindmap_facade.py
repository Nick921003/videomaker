from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio.execution import ExecutionSlot
from studio.mindmap_facade import MindmapJobFacade
from studio.sources import SourceStore
from studio.video_facade import FacadeError
from tests.test_studio_mindmap import MATERIAL, sample_map


class TestMindmapJobFacade(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.store = SourceStore(Path(self.tmp.name))
		self.addCleanup(self.store.close)
		self.source = self.store.add_upload("lesson.txt", MATERIAL.encode())
		self.slot = ExecutionSlot()
		self.assertTrue(self.slot.claim("mindmap:test"))
		self.snapshot = self.store.snapshot_for_job(self.source["ref"], self.source["revision"], "test")

	def facade(self, complete):
		return MindmapJobFacade("a" * 32, "p" * 32, self.source, self.snapshot,
			self.store, self.slot, "mindmap:test", "做成心智圖", complete)

	def test_approval_controls_download_and_frees_snapshot(self):
		facade = self.facade(lambda *_: (sample_map(), {}))
		facade.start()
		self.assertEqual(facade.snapshot()["status"], "done")
		self.assertIsNone(self.slot.owner())
		self.assertFalse(Path(self.snapshot).exists())
		self.assertEqual(facade.source_content()["revision"], self.source["revision"])
		self.assertIn(MATERIAL, facade.source_content()["text"])
		artifact = facade.artifacts()[0]
		self.assertEqual(facade.artifact_content(artifact["artifact_id"]), sample_map())
		with self.assertRaises(FacadeError):
			facade.svg_content(artifact["artifact_id"], download=True)
		facade.review_artifact(artifact["artifact_id"], "approve")
		self.assertIn(b"<svg", facade.svg_content(artifact["artifact_id"], download=True))
		with self.assertRaises(FacadeError):
			facade.review_artifact(artifact["artifact_id"], "reject")

	def test_completed_map_can_be_redrawn_without_model_call(self):
		facade = self.facade(lambda *_: (sample_map(), {'provider':'anthropic','model':'claude-opus-5-5','in':10,'out':20}))
		facade.start()
		artifact_id = facade.artifacts()[0]["artifact_id"]
		restored = MindmapJobFacade.restore_completed(
			facade.snapshot(), facade.artifact_content(artifact_id), facade.source_content()["text"])
		self.assertEqual(restored.snapshot()["status"], "done")
		self.assertEqual(restored.snapshot()['usage'],facade.snapshot()['usage'])
		self.assertEqual(restored.artifacts()[0]["status"], "needs_review")
		self.assertIn(b'data-node-id="condition"', restored.svg_content(artifact_id))
		restored.review_artifact(artifact_id, "approve")
		self.assertEqual(restored.svg_content(artifact_id, download=True), restored.svg_content(artifact_id))

	def test_invalid_model_output_fails_safely_and_frees_slot(self):
		def fail(*_):
			raise RuntimeError("secret /private/path")
		facade = self.facade(fail)
		with patch("studio.mindmap_facade.logging.warning") as warning:
			facade.start()
		state = facade.snapshot()
		self.assertEqual(state["status"], "failed")
		self.assertNotIn("secret", str(state))
		self.assertIn("RuntimeError", str(warning.call_args))
		self.assertNotIn("secret", str(warning.call_args))
		self.assertEqual(state["artifacts"], [])
		self.assertIsNone(self.slot.owner())
		self.assertFalse(Path(self.snapshot).exists())
