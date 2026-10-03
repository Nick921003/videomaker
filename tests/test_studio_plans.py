import unittest

from studio.contracts import ContractError, canonicalize_plan
from studio.plans import PlanStore
from tests.test_studio_contracts import draft


class TestPlanStore(unittest.TestCase):
	def test_id_is_opaque_and_records_are_independent_copies(self):
		store = PlanStore()
		plan = canonicalize_plan(draft())
		record = store.save_canonical(plan)
		self.assertRegex(record.plan_id, r"^[0-9a-f]{32}$")
		plan["summary"] = "caller changed"
		record.plan["summary"] = "returned changed"
		got = store.get(record.plan_id)
		self.assertEqual(got.plan["summary"], "建立影片")
		got.plan["summary"] = "retrieved changed"
		self.assertEqual(store.get(record.plan_id).plan["summary"], "建立影片")
		self.assertIsNone(store.get("unknown"))

	def test_private_instruction_is_saved_for_deck_generation(self):
		store = PlanStore()
		record = store.save_canonical(canonicalize_plan(draft()), instruction="請強調範例")
		self.assertEqual(store.get(record.plan_id).instruction, "請強調範例")
		self.assertNotIn("instruction", store.get(record.plan_id).plan)

	def test_rejects_noncanonical_and_evicts_oldest(self):
		store = PlanStore()
		with self.assertRaises(ContractError):
			store.save_canonical(draft())
		store.MAX_PLANS = 2
		ids = [store.save_canonical(canonicalize_plan(draft(summary=str(i)))).plan_id for i in range(3)]
		self.assertIsNone(store.get(ids[0]))
		self.assertIsNotNone(store.get(ids[1]))
		self.assertIsNotNone(store.get(ids[2]))
