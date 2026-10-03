"""教學狀態的正反向控制；不要求正式引擎理解原型。"""
import unittest
from state_model import output_at, validate_beats


class StateTests(unittest.TestCase):
	def test_nul_stops_before_unknown_tail(self):
		self.assertEqual(output_at(list("Alice") + ["\0", "X"], 6), "Alice")
		self.assertEqual(output_at(list("Alice") + ["\0", "X"], 99), "Alice")

	def test_each_prefix(self):
		for count in range(6):
			self.assertEqual(output_at(list("Alice") + ["\0"], count), "Alice"[:count])

	def test_rejects_nul_as_printed_character(self):
		beats = [{"phase": "setup"}, {"phase": "copy"}]
		beats += [{"phase": "scan", "index": i, "output_after": "Alice"[:i+1]} for i in range(5)]
		beats += [{"phase": "stop", "index": 5, "output_after": "Alice\\0"},
			{"phase": "summary"}, {"phase": "question"}]
		with self.assertRaisesRegex(ValueError, "stop"):
			validate_beats(beats)
		beats[7]["output_after"] = "Alice"
		validate_beats(beats)

	def test_rejects_skipped_letter(self):
		beats = [{"phase": "setup"}, {"phase": "copy"}]
		beats += [{"phase": "scan", "index": i, "output_after": "Alice"[:i+1]} for i in range(5)]
		beats += [{"phase": "stop", "index": 5, "output_after": "Alice"},
			{"phase": "summary"}, {"phase": "question"}]
		beats[4]["output_after"] = "Alc"
		with self.assertRaisesRegex(ValueError, "scan"):
			validate_beats(beats)


if __name__ == "__main__":
	unittest.main()
