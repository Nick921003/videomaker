from copy import deepcopy
import unittest

from studio.contracts import ContractError
from studio.planner import plan_request
from studio.planner_backends import RulePlannerBackend
from studio.plans import PlanStore
from tests.test_studio_planner_backends import REQUEST


class TestPlanRequestFlow(unittest.TestCase):
	def test_rule_request_returns_saved_canonical_plan(self):
		store = PlanStore()
		record = plan_request(REQUEST, RulePlannerBackend(), store)
		self.assertRegex(record.plan_id, r"^[0-9a-f]{32}$")
		self.assertEqual(record.plan["steps"][0]["template_id"], "video.micro_lesson.default.v1")
		self.assertEqual(store.get(record.plan_id).plan, record.plan)

	def test_backend_cannot_swap_source_or_add_shell_field(self):
		class Fake:
			def __init__(self, mutate):
				self.mutate = mutate
			def plan(self, request, catalog, schema):
				value = RulePlannerBackend().plan(request, catalog, schema)
				self.mutate(value)
				return value
		for mutate in (lambda plan: plan.update(source=dict(plan["source"], ref="material:other")),
			lambda plan: plan["steps"][0].update(shell="evil")):
			store = PlanStore()
			with self.subTest(mutate=mutate), self.assertRaises(ContractError):
				plan_request(REQUEST, Fake(mutate), store)
			self.assertEqual(store._items, {})

	def test_request_is_normalized_before_backend_and_not_mutated(self):
		payload = deepcopy(REQUEST)
		payload["instruction"] = "  做成 90 秒影片  "
		seen = []
		class Capture:
			def plan(self, request, catalog, schema):
				seen.append(request)
				return RulePlannerBackend().plan(request, catalog, schema)
		plan_request(payload, Capture(), PlanStore())
		self.assertEqual(seen[0]["instruction"], "做成 90 秒影片")
		self.assertEqual(payload["instruction"], "  做成 90 秒影片  ")
