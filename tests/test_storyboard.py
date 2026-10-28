import json
import unittest

from video_engine.explainer.storyboard import build


def sample(template="center"):
	return {
		"title": "T", "subtitle": "S",
		"chapters": [
			{"id": "a", "title": "甲", "notes": ["n1"], "pages": [
				{"template": template, "spine": "骨甲", "lines": [{"say": "一。", "key": "K1", "lead": 2.0}, {"say": "二。", "hold": 0.5}]},
				{"template": "screen", "kind": "vscode", "lines": [{"say": "三。", "lead": 1.0}]},
			]},
			{"id": "b", "title": "乙", "pages": [{"template": "two-col", "lines": [{"say": "四。"}]}]},
		],
		"end": {"emphasis": "E", "say": "五。"},
		"recap": {"center": "C", "tagline": "G", "length": 8, "say": "R", "items": ["x | y"]},
	}


class TestStoryboard(unittest.TestCase):
	def test_numbering_pages_screens(self):
		out = build(sample())
		self.assertEqual(json.loads(out["pages.json"]), [[1, 2], [4]])
		self.assertEqual(json.loads(out["screens.json"]), [{"lines": [3], "kind": "vscode"}])
		self.assertEqual(json.loads(out["leads.json"]), {"1": 2.0, "3": 1.0})
		self.assertEqual(json.loads(out["holds.json"]), {"2": 0.5})
		self.assertEqual(json.loads(out["keys.json"]), {"1": "K1"})

	def test_script_md_order(self):
		md = build(sample())["script.md"]
		body = [l for l in md.splitlines() if l.endswith("。")]
		self.assertEqual(body, ["一。", "二。", "三。", "四。", "五。"])
		self.assertIn("## a | 甲", md)
		self.assertIn("> n1", md)
		self.assertIn("## end\nemphasis: E\n五。", md)

	def test_review_spine_first(self):
		rv = build(sample())["review.md"]
		self.assertLess(rv.index("- 甲｜骨甲"), rv.index("### 骨甲（center）"))
		self.assertIn("1. 一。　〔K1〕", rv)
		self.assertIn("5. 五。", rv)

	def test_unknown_template_fails(self):
		with self.assertRaises(ValueError):
			build(sample("three-col"))


if __name__ == "__main__":
	unittest.main()
