import threading
import unittest

from studio.execution import ExecutionSlot


class TestExecutionSlot(unittest.TestCase):
	def test_only_owner_can_release(self):
		slot = ExecutionSlot()
		self.assertTrue(slot.claim("legacy"))
		self.assertFalse(slot.claim("studio"))
		self.assertEqual(slot.owner(), "legacy")
		with self.assertRaises(RuntimeError):
			slot.release("studio")
		self.assertEqual(slot.owner(), "legacy")
		slot.release("legacy")
		self.assertIsNone(slot.owner())
		self.assertTrue(slot.claim("studio"))

	def test_competing_callers_exactly_one_wins(self):
		for _ in range(50):
			slot = ExecutionSlot()
			barrier = threading.Barrier(3)
			results = []
			def contender(owner):
				barrier.wait()
				results.append(slot.claim(owner))
			workers = [threading.Thread(target=contender, args=(owner,)) for owner in ("legacy", "studio")]
			for worker in workers:
				worker.start()
			barrier.wait()
			for worker in workers:
				worker.join()
			self.assertEqual(sorted(results), [False, True])

	def test_none_cannot_be_owner(self):
		slot = ExecutionSlot()
		with self.assertRaises(ValueError):
			slot.claim(None)
		self.assertIsNone(slot.owner())
