from copy import deepcopy
import unittest
from unittest.mock import patch

from studio.deck_contracts import DeckError, canonical_deck
from studio.contracts import ContractError, canonicalize_plan


def sample_deck():
	return {
		"contract_version": "1.0", "title": "Python 迴圈",
		"slides": [
			{"slide_id": "s1", "role": "hook", "title": "先想一想", "layout": "bullets",
				"blocks": [{"type": "bullets", "items": ["迴圈可重複執行", "條件決定何時停止"]}],
				"speaker_notes": "請學生舉例。", "source_quote": "迴圈可重複執行"},
			{"slide_id": "s2", "role": "example", "title": "程式範例", "layout": "code",
				"blocks": [{"type": "code", "language": "python", "lines": ["for n in range(3):", "    print(n)"]}],
				"speaker_notes": "逐行解釋。", "source_quote": "for n in range(3)"},
			{"slide_id": "s3", "role": "pitfall", "title": "比較兩種寫法", "layout": "compare",
				"blocks": [{"type": "compare", "left": {"title": "正確", "items": ["有終止條件"]},
					"right": {"title": "錯誤", "items": ["無終止條件"]}}],
				"speaker_notes": "討論無限迴圈。", "source_quote": "終止條件"},
			{"slide_id": "s4", "role": "summary", "title": "實作步驟", "layout": "steps",
				"blocks": [{"type": "steps", "items": ["設定初值", "檢查條件", "更新變數"]}],
				"speaker_notes": "複習。", "source_quote": "更新變數"},
		],
	}


def sample_deck_v11():
	deck = sample_deck()
	deck["contract_version"] = "1.1"
	for slide in deck["slides"]:
		slide["takeaway"] = "讀完這頁，確認條件與更新如何讓迴圈結束。"
	return deck


def self_study_deck():
	deck = sample_deck_v11()
	deck["slides"][0]["layout"] = "concept"
	deck["slides"][0]["blocks"] = [{"type": "concept", "center": "迴圈",
		"items": [{"title": "條件", "text": "決定是否繼續"},
			{"title": "更新", "text": "讓狀態向終止前進"}]}]
	return deck


class TestDeckContract(unittest.TestCase):
	def test_self_study_requires_bounded_visible_takeaway(self):
		deck = self_study_deck()
		self.assertEqual(canonical_deck(deck), deck)
		for value in (None, "", "字" * 121):
			candidate = deepcopy(deck)
			if value is None:
				del candidate["slides"][0]["takeaway"]
			else:
				candidate["slides"][0]["takeaway"] = value
			with self.subTest(value=value), self.assertRaises(DeckError):
				canonical_deck(candidate)

	def test_concept_limits_and_closed_fields(self):
		for count in (2, 3, 4):
			deck = self_study_deck()
			deck["slides"][0]["blocks"][0]["items"] = [{"title": "關係", "text": "原因與結果"}] * count
			self.assertEqual(canonical_deck(deck), deck)
		for change in (lambda b: b.update(center="字" * 41),
			lambda b: b.update(items=b["items"][:1]),
			lambda b: b.update(items=b["items"] * 3),
			lambda b: b.update(url="https://example.com"),
			lambda b: b["items"][0].update(title="字" * 33),
			lambda b: b["items"][0].update(text="字" * 81),
			lambda b: b["items"][0].update(extra="x")):
			deck = self_study_deck()
			change(deck["slides"][0]["blocks"][0])
			with self.assertRaises(DeckError):
				canonical_deck(deck)

	def test_legacy_version_keeps_its_closed_fields_and_layouts(self):
		deck = sample_deck()
		deck["slides"][0]["takeaway"] = "不能偽裝成舊版"
		with self.assertRaises(DeckError):
			canonical_deck(deck)
		deck = self_study_deck()
		deck["contract_version"] = "1.0"
		for slide in deck["slides"]:
			del slide["takeaway"]
		with self.assertRaises(DeckError):
			canonical_deck(deck)

	def test_accepts_all_v1_layouts_and_returns_deep_copy(self):
		candidate = sample_deck()
		result = canonical_deck(candidate)
		self.assertEqual(result, candidate)
		self.assertIsNot(result, candidate)
		result["slides"][0]["blocks"][0]["items"][0] = "改掉"
		self.assertEqual(candidate["slides"][0]["blocks"][0]["items"][0], "迴圈可重複執行")

	def test_rejects_bad_slide_count_or_duplicate_ids(self):
		candidate = sample_deck()
		for slides in (candidate["slides"][:2], candidate["slides"] * 4):
			with self.subTest(count=len(slides)), self.assertRaises(DeckError):
				canonical_deck({**candidate, "slides": slides})
		duplicate = deepcopy(candidate)
		duplicate["slides"][1]["slide_id"] = "s1"
		with self.assertRaises(DeckError):
			canonical_deck(duplicate)

	def test_rejects_unknown_fields_and_block_shapes(self):
		for path, value in (
			("root", {**sample_deck(), "script": "alert(1)"}),
			("slide", None), ("unknown_block", None), ("mismatch", None),
		):
			candidate = sample_deck()
			if path == "root":
				candidate = value
			elif path == "slide":
				candidate["slides"][0]["href"] = "https://example.com"
			elif path == "unknown_block":
				candidate["slides"][0]["blocks"] = [{"type": "html", "html": "<script>"}]
			else:
				candidate["slides"][0]["blocks"] = [{"type": "code", "language": "python", "lines": ["pass"]}]
			with self.subTest(path=path), self.assertRaises(DeckError):
				canonical_deck(candidate)

	def test_rejects_text_and_collection_limits(self):
		candidate = sample_deck()
		candidate["slides"][0]["title"] = "字" * 121
		with self.assertRaises(DeckError):
			canonical_deck(candidate)
		candidate = sample_deck()
		candidate["slides"][0]["blocks"][0]["items"] = ["項"] * 6
		with self.assertRaises(DeckError):
			canonical_deck(candidate)
		candidate = sample_deck()
		candidate["slides"][1]["blocks"][0]["lines"] = ["print(1)"] * 17
		with self.assertRaises(DeckError):
			canonical_deck(candidate)

	def test_steps_allow_six_short_actions_but_reject_seven(self):
		candidate = sample_deck()
		candidate["slides"][3]["blocks"][0]["items"] = ["動作"] * 6
		self.assertEqual(len(canonical_deck(candidate)["slides"][3]["blocks"][0]["items"]), 6)
		candidate["slides"][3]["blocks"][0]["items"].append("動作")
		with self.assertRaises(DeckError):
			canonical_deck(candidate)

	def test_does_not_accept_server_owned_metadata_from_model(self):
		candidate = sample_deck()
		for key in ("source_revision", "template_id", "review_gate", "artifact_id"):
			with self.subTest(key=key), self.assertRaises(DeckError):
				canonical_deck({**candidate, key: "forged"})


class TestNonVideoPlanGate(unittest.TestCase):
	def test_planned_pptx_direct_generation_remains_unavailable(self):
		from tests.test_studio_contracts import draft
		value = draft()
		value["steps"][0]["capability_id"] = "pptx.editable_deck.v1"
		value["steps"][0]["options"] = {}
		with self.assertRaises(ContractError):
			canonicalize_plan(value)

	def test_available_registered_nonvideo_can_use_generic_plan_contract(self):
		from studio.catalog import get_capability
		from tests.test_studio_contracts import draft
		value = draft()
		value["steps"][0]["capability_id"] = "slides.lesson_deck.v1"
		value["steps"][0]["options"] = {}
		deck_capability = get_capability("slides.lesson_deck.v1")
		deck_capability["availability"] = "available"
		with patch("studio.contracts.get_capability", return_value=deck_capability):
			plan = canonicalize_plan(value)
		self.assertEqual(plan["steps"][0]["review_gate"], "content")
