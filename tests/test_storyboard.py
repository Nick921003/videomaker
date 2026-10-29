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


VS = {"type": "vscode", "id": "vs", "files": {"score.c": ["int main(void) {", "}"]}, "panel": "output"}


def screen_sample(do2):
	sb = sample()
	sb["chapters"][0]["pages"][1] = {"template": "screen", "kind": "vscode", "screen": dict(VS), "lines": [
		{"say": "我們按右上角這個三角形，跑跑看。", "do": [{"act": "click", "target": "cursor", "on": "vs:run", "cue": "跑跑看"},
			{"act": "circle", "target": "vs:run", "cue": "三角形", "tone": "warn"}]},
		{"say": "輸出面板只有一行 Running。", "do": do2},
	]}
	return sb


class TestScreenPage(unittest.TestCase):
	def test_screen頁寫進screens_json(self):
		out = build(screen_sample([{"act": "run", "target": "vs", "output": ["[Running]"], "cue": "Running"}]))
		scr = json.loads(out["screens.json"])[0]
		self.assertEqual(scr["lines"], [3, 4])
		self.assertEqual(scr["screen"]["id"], "vs")
		self.assertEqual(scr["screen"]["open"], "score.c")
		self.assertEqual([a["act"] for a in scr["do"]["3"]], ["click", "circle"])
		run = scr["do"]["4"][0]
		self.assertEqual((run["act"], run["cue"], run["args"]["output"]), ("run", "Running", ["[Running]"]))
		self.assertEqual(scr["do"]["3"][1]["args"]["tone"], "warn")
		self.assertGreater(run["dur"], 0)
		self.assertTrue(run["blocks"])
		self.assertFalse(scr["do"]["3"][1]["blocks"])

	def test_screen頁cue不在旁白要擋(self):
		with self.assertRaisesRegex(ValueError, "跑跑看囉"):
			build(screen_sample([{"act": "run", "target": "vs", "cue": "跑跑看囉"}]))

	def test_screen頁錨點不存在要擋(self):
		with self.assertRaisesRegex(ValueError, "tab:hello.c"):
			build(screen_sample([{"act": "circle", "target": "vs:tab:hello.c"}]))

	def test_舊的screen頁沒有screen欄位照舊(self):
		self.assertEqual(json.loads(build(sample())["screens.json"]), [{"lines": [3], "kind": "vscode"}])


if __name__ == "__main__":
	unittest.main()
