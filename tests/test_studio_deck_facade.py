from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pptx import Presentation
from studio.deck_facade import DeckJobFacade
from studio.execution import ExecutionSlot
from studio.sources import SourceStore
from studio.video_facade import FacadeError
from tests.test_studio_deck_builder import MATERIAL
from tests.test_studio_deck_contracts import sample_deck_v11 as sample_deck


class TestDeckJobFacade(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.store = SourceStore(Path(self.tmp.name))
		self.addCleanup(self.store.close)
		self.source = self.store.add_upload("lesson.txt", MATERIAL.encode())
		self.slot = ExecutionSlot()
		self.assertTrue(self.slot.claim("deck:test"))
		self.snapshot = self.store.snapshot_for_job(self.source["ref"], self.source["revision"], "test")

	def facade(self, complete):
		return DeckJobFacade("a" * 32, "p" * 32, self.source, self.snapshot,
			self.store, self.slot, "deck:test", "做成線上簡報", complete)

	def test_success_releases_resources_and_reviews_deck(self):
		facade = self.facade(lambda *_: (sample_deck(), {}))
		facade.start()
		snapshot = facade.snapshot()
		self.assertEqual(snapshot["status"], "done")
		self.assertEqual(snapshot["capability_id"], "slides.lesson_deck.v1")
		self.assertEqual([item["event"] for item in facade.events_after(0)],
			["stage_start", "stage_end", "stage_start", "stage_end", "stage_start", "stage_end"])
		self.assertIsNone(self.slot.owner())
		self.assertFalse(Path(self.snapshot).exists())
		artifact = snapshot["artifacts"][0]
		self.assertEqual(artifact["kind"], "deck")
		self.assertEqual(facade.artifact_content(artifact["artifact_id"]), sample_deck())
		with self.assertRaises(FacadeError):
			facade.get_review()
		facade.review_artifact(artifact["artifact_id"], "approve")
		with self.assertRaises(FacadeError):
			facade.review_artifact(artifact["artifact_id"], "reject")

	def test_usage_survives_validation_failure_and_snapshot_replays(self):
		deck = sample_deck()
		deck['slides'][0]['source_quote'] = '教材沒有這段內容'
		facade = self.facade(lambda *_: (deck, {'provider':'anthropic','model':'claude-opus-5-5','in':100,'out':200}))
		facade.start()
		self.assertEqual(facade.snapshot()['status'], 'failed')
		self.assertEqual(facade.snapshot()['usage']['total_tokens'], 300)
		self.assertEqual(facade.snapshot()['usage']['call_count'], 1)
		self.assertEqual(facade.snapshot()['usage'], facade.snapshot()['usage'])


	def test_export_requires_approval_and_reuses_deck_without_completion(self):
		calls = []
		def complete(*_):
			calls.append(1)
			return sample_deck(), {}
		facade = self.facade(complete)
		facade.start()
		artifact_id = facade.artifacts()[0]["artifact_id"]
		with self.assertRaises(FacadeError):
			facade.pptx_content(artifact_id)
		approved = facade.review_artifact(artifact_id, "approve")
		self.assertEqual(approved["download"]["file_name"], "lesson.pptx")
		first = facade.pptx_content(artifact_id)
		self.assertEqual(first, facade.pptx_content(artifact_id))
		self.assertEqual(len(Presentation(BytesIO(first)).slides), 4)
		self.assertEqual(len(calls), 1)


	def test_export_failure_does_not_approve_artifact(self):
		facade = self.facade(lambda *_: (sample_deck(), {}))
		facade.start()
		artifact_id = facade.artifacts()[0]["artifact_id"]
		with patch("studio.deck_facade.export_pptx", side_effect=RuntimeError("secret token")):
			with self.assertRaises(FacadeError) as context:
				facade.review_artifact(artifact_id, "approve")
		self.assertEqual(context.exception.code, "export_failed")
		self.assertNotIn("secret", context.exception.safe_message)
		self.assertEqual(facade.artifacts()[0]["status"], "needs_review")

	def test_invalid_model_result_is_safe_and_releases_resources(self):
		def fail(*_):
			raise RuntimeError("secret /private/path")
		facade = self.facade(fail)
		facade.start()
		snapshot = facade.snapshot()
		self.assertEqual(snapshot["status"], "failed")
		self.assertNotIn("secret", str(snapshot))
		self.assertEqual(snapshot["artifacts"], [])
		self.assertIsNone(self.slot.owner())
		self.assertFalse(Path(self.snapshot).exists())
