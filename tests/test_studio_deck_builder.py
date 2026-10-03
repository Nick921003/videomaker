from copy import deepcopy
import unittest

from studio.deck_builder import build_deck, validate_source_quotes
from studio.deck_contracts import DeckError
from tests.test_studio_deck_contracts import sample_deck as legacy_deck, sample_deck_v11 as sample_deck, self_study_deck


MATERIAL = "迴圈可重複執行。for n in range(3) 是範例。終止條件很重要。更新變數以免無限迴圈。"


class TestDeckBuilder(unittest.TestCase):
	def test_new_generation_rejects_legacy_response_even_when_provider_ignores_schema(self):
		with self.assertRaisesRegex(DeckError, "1.1"):
			build_deck(MATERIAL, "學生自讀", lambda *_: (legacy_deck(), {}))

	def test_generation_schema_and_prompt_target_visible_self_study(self):
		def complete(system, _user, schema):
			self.assertEqual(schema["properties"]["contract_version"], {"const": "1.1"})
			slide_schema = schema["properties"]["slides"]["items"]
			self.assertIn("takeaway", slide_schema["required"])
			self.assertIn("concept", slide_schema["properties"]["layout"]["enum"])
			blocks = slide_schema["properties"]["blocks"]["items"]["anyOf"]
			concept = next(b for b in blocks if b["properties"]["type"] == {"const": "concept"})
			self.assertEqual(concept["required"], ["type", "center", "items"])
			self.assertEqual(concept["properties"]["items"]["items"]["required"], ["title", "text"])
			for phrase in ("takeaway", "concept", "方向", "依內容", "支持"):
				self.assertIn(phrase, system)
			return self_study_deck(), {}
		self.assertEqual(build_deck(MATERIAL, "學生自讀", complete)["contract_version"], "1.1")

	def test_provider_schema_keeps_bounds_in_application_validator(self):
		def complete(_system, _user, schema):
			def walk(value):
				if isinstance(value, dict):
					if value.get("type") == "array":
						self.assertIn(value.get("minItems", 0), (0, 1))
						self.assertNotIn("maxItems", value)
					self.assertNotIn("oneOf", value)
					for child in value.values():
						walk(child)
				elif isinstance(value, list):
					for child in value:
						walk(child)
			walk(schema)
			blocks = schema["properties"]["slides"]["items"]["properties"]["blocks"]["items"]
			self.assertIn("anyOf", blocks)
			compare = next(block for block in blocks["anyOf"] if block["properties"]["type"] == {"const": "compare"})
			for side in ("left", "right"):
				self.assertEqual(compare["properties"][side]["required"], ["title", "items"])
			return sample_deck(), {}
		build_deck(MATERIAL, "做成線上簡報", complete)

	def test_calls_completion_once_and_preserves_canonical_content(self):
		calls = []
		candidate = sample_deck()
		def complete(system, user, schema):
			calls.append((system, user, schema))
			return candidate, {"in": 1, "out": 2}
		deck = build_deck(MATERIAL, "做成線上簡報", complete)
		self.assertEqual(deck, candidate)
		self.assertIsNot(deck, candidate)
		self.assertEqual(len(calls), 1)
		self.assertIn("做成線上簡報", calls[0][1])
		self.assertIn(MATERIAL, calls[0][1])

	def test_rejects_source_limit_before_completion(self):
		called = []
		with self.assertRaises(DeckError):
			build_deck("字" * 30001, "做簡報", lambda *_: called.append(1))
		self.assertEqual(called, [])

	def test_rejects_hallucinated_quotes_and_bad_candidates(self):
		candidate = sample_deck()
		candidate["slides"][0]["source_quote"] = "教材完全沒有這句"
		for value in (candidate, {"contract_version": "1.0", "title": "x", "slides": []},
			{**sample_deck(), "script": "evil"}):
			with self.subTest(value=value), self.assertRaises(DeckError):
				build_deck(MATERIAL, "做簡報", lambda *_: (value, {}))

	def test_discontinuous_but_exact_sentences_narrow_to_one_source_anchor(self):
		candidate = sample_deck()
		candidate["slides"][0]["source_quote"] = "迴圈可重複執行。終止條件很重要。"
		deck = build_deck(MATERIAL, "做簡報", lambda *_: (candidate, {}))
		self.assertEqual(deck["slides"][0]["source_quote"], "迴圈可重複執行。")
		self.assertEqual(candidate["slides"][0]["source_quote"], "迴圈可重複執行。終止條件很重要。")
		candidate["slides"][0]["source_quote"] += "教材沒說過這句。"
		with self.assertRaises(DeckError):
			build_deck(MATERIAL, "做簡報", lambda *_: (candidate, {}))

	def test_quotes_match_whitespace_normalized_material(self):
		candidate = deepcopy(sample_deck())
		candidate["slides"][0]["source_quote"] = "迴圈可\n重複執行"
		validate_source_quotes(candidate, "迴圈可   重複執行。" + MATERIAL)

	def test_rejects_unreadable_export_before_artifact(self):
		candidate = sample_deck()
		candidate["slides"][2]["blocks"][0]["left"]["items"] = ["認識概念之間的差別" * 6] * 4
		with self.assertRaisesRegex(DeckError, "最低可讀字級"):
			build_deck(MATERIAL, "做簡報", lambda *_: (candidate, {}))

	def test_provider_error_is_safe(self):
		def fail(*_):
			raise RuntimeError("secret-token /private/path")
		with self.assertRaises(DeckError) as context:
			build_deck(MATERIAL, "做簡報", fail)
		self.assertNotIn("secret-token", str(context.exception))
