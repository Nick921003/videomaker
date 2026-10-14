from copy import deepcopy
import unittest

from studio.contracts import (ContractError, assert_canonical_plan, canonicalize_plan, generation_plan_schema, normalize_plan_request)


SOURCE = {"kind": "upload", "ref": "material:abc123", "revision": "sha256:" + "a" * 64}


def draft(**overrides):
	value = {
		"contract_version": "1.0", "status": "ready", "summary": "建立影片",
		"source": deepcopy(SOURCE), "questions": [], "warnings": [],
		"steps": [{"step_id": "video-1", "action": "artifact.generate",
			"capability_id": "video.micro_lesson.v1",
			"options": {"duration_seconds": 90, "layout": "auto"}, "requires": []}],
	}
	value.update(overrides)
	return value


class TestPlanRequest(unittest.TestCase):
	def test_request_has_closed_fields_and_complete_source_revision(self):
		valid = {"contract_version": "1.0", "instruction": "做成 90 秒影片", "source": SOURCE}
		self.assertEqual(normalize_plan_request(valid), valid)
		for change in ({"learner_context": {}}, {"contract_version": "2.0"},
			{"source": dict(SOURCE, revision="sha256:abcd")},
			{"source": dict(SOURCE, ref="/home/user/material.md")},
			{"instruction": ""}):
			with self.subTest(change=change), self.assertRaises(ContractError):
				normalize_plan_request(dict(valid, **change))


class TestCanonicalPlan(unittest.TestCase):
	def test_server_owns_template_and_review_gate_without_mutating_draft(self):
		value = draft()
		plan = canonicalize_plan(value)
		self.assertEqual(plan["steps"][0]["template_id"], "video.micro_lesson.default.v1")
		self.assertEqual(plan["steps"][0]["review_gate"], "script")
		self.assertNotIn("template_id", value["steps"][0])
		assert_canonical_plan(plan)

	def test_draft_cannot_supply_server_owned_fields(self):
		for injected in ({"review_gate": "none"}, {"template_id": "evil.v1"}):
			value = draft()
			value["steps"][0].update(injected)
			with self.subTest(injected=injected), self.assertRaises(ContractError):
				canonicalize_plan(value)

	def test_rejects_bad_options_and_unavailable_capabilities(self):
		for options in ({"duration_seconds": True, "layout": "auto"},
			{"duration_seconds": 29, "layout": "auto"},
			{"duration_seconds": 90, "layout": "stage"},
			{"duration_seconds": 90, "layout": "auto", "shell": "x"}):
			value = draft()
			value["steps"][0]["options"] = options
			with self.subTest(options=options), self.assertRaises(ContractError):
				canonicalize_plan(value)
		for capability_id in ("comic.misconception_story.v1", "shell.anything.v1"):
			value = draft()
			value["steps"][0]["capability_id"] = capability_id
			with self.subTest(capability_id=capability_id), self.assertRaises(ContractError):
				canonicalize_plan(value)

	def test_ready_plan_requires_exactly_one_video_step(self):
		for mutate in (
			lambda value: value.update(steps=[]),
			lambda value: value["steps"].append(dict(value["steps"][0], step_id="video-2")),
			lambda value: value["steps"][0].update(action="shell.exec"),
			lambda value: value["steps"][0].update(requires=["other"]),
		):
			value = draft()
			mutate(value)
			with self.subTest(value=value), self.assertRaises(ContractError):
				canonicalize_plan(value)

	def test_clarification_has_questions_and_no_steps(self):
		value = draft(status="needs_clarification", steps=[], questions=[{"code": "media", "message": "想做哪種教材？"}])
		self.assertEqual(canonicalize_plan(value), value)
		for change in ({"questions": []}, {"steps": draft()["steps"]}):
			with self.subTest(change=change), self.assertRaises(ContractError):
				canonicalize_plan(dict(value, **change))

	def test_rejects_unknown_fields_and_forged_canonical_plan(self):
		with self.assertRaises(ContractError):
			canonicalize_plan(draft(shell="rm"))
		plan = canonicalize_plan(draft())
		plan["steps"][0]["review_gate"] = "none"
		with self.assertRaises(ContractError):
			assert_canonical_plan(plan)

	def test_ai_schema_cannot_supply_server_fields(self):
		step = generation_plan_schema({"video.micro_lesson.v1"})["properties"]["steps"]["items"]
		self.assertFalse(step["additionalProperties"])
		self.assertNotIn("template_id", step["properties"])
		self.assertNotIn("review_gate", step["properties"])

	def test_malformed_json_values_raise_contract_error(self):
		for capability_id in ([], {}, None, 7):
			value = draft()
			value["steps"][0]["capability_id"] = capability_id
			with self.subTest(capability_id=capability_id), self.assertRaises(ContractError):
				canonicalize_plan(value)
