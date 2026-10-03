import unittest

from studio.catalog import CAPABILITIES, capability_ids, capability_index, get_capability, public_catalog
from video_engine.layout import LAYOUT_MODES


class TestCatalog(unittest.TestCase):
	def test_ids_and_templates_are_unique_and_versioned(self):
		ids = [item["id"] for item in CAPABILITIES]
		templates = [item["template_id"] for item in CAPABILITIES]
		self.assertEqual(len(ids), len(set(ids)))
		self.assertEqual(len(templates), len(set(templates)))
		self.assertTrue(all(value.endswith(".v1") for value in ids + templates))
		self.assertEqual(capability_ids(), set(ids))

	def test_video_and_online_deck_are_available(self):
		available = [item["id"] for item in CAPABILITIES if item["availability"] == "available"]
		self.assertEqual(available, ["video.micro_lesson.v1", "slides.lesson_deck.v1", "mindmap.concept_overview.v1"])
		self.assertEqual(len(CAPABILITIES), 8)
		self.assertTrue(all("review_gate" in item and "options" in item for item in CAPABILITIES))

	def test_video_options_match_engine(self):
		video = get_capability("video.micro_lesson.v1")
		self.assertEqual(tuple(video["options"]["layout"]["enum"]), LAYOUT_MODES)
		self.assertNotIn("stage", video["options"]["layout"]["enum"])
		self.assertEqual(video["review_gate"], "script")
		self.assertEqual(video["options"]["duration_seconds"]["default"], 110)

	def test_public_and_lookup_are_independent_copies(self):
		public = public_catalog()
		public[0]["options"]["layout"]["enum"].append("evil")
		lookup = capability_index()
		lookup["video.micro_lesson.v1"]["label"] = "changed"
		self.assertNotIn("evil", get_capability("video.micro_lesson.v1")["options"]["layout"]["enum"])
		self.assertEqual(get_capability("video.micro_lesson.v1")["label"], "微課程影片")
		self.assertTrue(all("handler" not in item for item in public))
		self.assertIsNone(get_capability("unknown.v1"))
