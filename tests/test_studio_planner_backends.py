import unittest

from studio.planner_backends import PlannerBackendError, RulePlannerBackend, StructuredAiPlannerBackend
from tests.test_studio_contracts import SOURCE


REQUEST = {"contract_version": "1.0", "instruction": "做成 90 秒的微課程影片", "source": SOURCE}


class TestRulePlanner(unittest.TestCase):
	def test_single_video_instruction_becomes_ready_draft(self):
		plan = RulePlannerBackend().plan(REQUEST, [], {})
		self.assertEqual(plan["status"], "ready")
		self.assertEqual(plan["source"], SOURCE)
		self.assertEqual(plan["steps"][0]["capability_id"], "video.micro_lesson.v1")
		self.assertEqual(plan["steps"][0]["options"]["duration_seconds"], 90)

	def test_ambiguous_or_planned_media_requires_clarification(self):
		for instruction in ("做成影片和漫畫", "做成心智圖", "整理一下", "做成 1000 秒影片"):
			with self.subTest(instruction=instruction):
				plan = RulePlannerBackend().plan(dict(REQUEST, instruction=instruction), [], {})
				self.assertEqual(plan["status"], "needs_clarification")
				self.assertEqual(plan["steps"], [])
				self.assertTrue(plan["questions"])


	def test_deck_and_pptx_intents_follow_catalog_availability(self):
		from studio.catalog import public_catalog
		catalog = public_catalog()
		for item in catalog:
			if item["id"] == "slides.lesson_deck.v1": item["availability"] = "planned"
		for instruction in ("做線上簡報", "做成 PPTX", "做影片和簡報"):
			with self.subTest(instruction=instruction):
				plan = RulePlannerBackend().plan(dict(REQUEST, instruction=instruction), catalog, {})
				self.assertEqual(plan["status"], "needs_clarification")
		for item in catalog:
			if item["id"] == "slides.lesson_deck.v1":
				item["availability"] = "available"
		plan = RulePlannerBackend().plan(dict(REQUEST, instruction="做線上簡報"), catalog, {})
		self.assertEqual(plan["status"], "ready")
		self.assertEqual(plan["steps"][0]["capability_id"], "slides.lesson_deck.v1")
		for instruction in ("做影片和簡報", "下載 PPTX"):
			with self.subTest(instruction=instruction):
				plan = RulePlannerBackend().plan(dict(REQUEST, instruction=instruction), catalog, {})
				self.assertEqual(plan["status"], "needs_clarification")

	def test_mindmap_intent_follows_catalog(self):
		from studio.catalog import public_catalog
		catalog = public_catalog()
		plan = RulePlannerBackend().plan(dict(REQUEST, instruction="做成心智圖"), catalog, {})
		self.assertEqual(plan["status"], "ready")
		self.assertEqual(plan["steps"][0]["capability_id"], "mindmap.concept_overview.v1")
		for item in catalog:
			if item["id"] == "mindmap.concept_overview.v1": item["availability"] = "planned"
		self.assertEqual(RulePlannerBackend().plan(dict(REQUEST, instruction="做成心智圖"), catalog, {})["status"], "needs_clarification")


class TestStructuredAiPlanner(unittest.TestCase):
	def test_passes_request_catalog_and_schema_to_injected_callable(self):
		seen = []
		def complete(system, user, schema):
			seen.append((system, user, schema))
			return {"source": SOURCE, "status": "needs_clarification", "questions": []}
		backend = StructuredAiPlannerBackend(complete)
		self.assertEqual(backend.plan(REQUEST, ["catalog"], {"schema": True})["source"], SOURCE)
		self.assertEqual(seen[0][1], {"request": REQUEST, "catalog": ["catalog"]})
		self.assertEqual(seen[0][2], {"schema": True})

	def test_provider_failures_never_expose_exception_text(self):
		for exc, code in ((TimeoutError("Bearer secret /home/pjw92"), "planner_timeout"),
			(RuntimeError("Bearer secret /home/pjw92"), "planner_unavailable")):
			def fail(*args):
				raise exc
			with self.subTest(exc=exc), self.assertRaises(PlannerBackendError) as context:
				StructuredAiPlannerBackend(fail).plan(REQUEST, [], {})
			self.assertEqual(context.exception.code, code)
			self.assertNotIn("secret", context.exception.safe_message)

	def test_rejects_wrong_shape_or_source(self):
		for raw, code in (([], "invalid_planner_response"),
			({"source": dict(SOURCE, ref="material:other")}, "source_changed")):
			with self.subTest(raw=raw), self.assertRaises(PlannerBackendError) as context:
				StructuredAiPlannerBackend(lambda *_: raw).plan(REQUEST, [], {})
			self.assertEqual(context.exception.code, code)
