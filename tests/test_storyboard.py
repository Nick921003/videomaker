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


def board_sample(template="center", objects=None, do=None, lines=None):
	sb = sample()
	sb["chapters"][0]["pages"][0] = {"template": template, "spine": "骨甲", "objects": objects if objects is not None else [
		{"type": "icon", "id": "i1", "name": "警告"}, {"type": "icon", "id": "i2", "name": "check"}],
		"lines": lines or [{"say": "小心這裡。", "do": do if do is not None else [{"act": "draw", "target": "i1"}]}, {"say": "二。"}]}
	return sb


def icon(i, **kw):
	return {"type": "icon", "id": "i%d" % i, "name": "check"} | kw


class TestBoardPage(unittest.TestCase):
	def test_objects頁產出(self):
		out = build(board_sample())
		bd = json.loads(out["objects.json"])
		self.assertEqual(len(bd), 1)
		self.assertEqual(bd[0]["lines"], [1, 2])
		self.assertEqual(bd[0]["template"], "center")
		a = bd[0]["do"]["1"][0]
		self.assertEqual(a["act"], "draw")
		self.assertGreater(a["dur"], 0)
		self.assertEqual([o["id"] for o in bd[0]["objects"]], ["i1", "i2"])
		self.assertEqual(json.loads(out["pages.json"]), [[1, 2], [4]])

	def test_until動作dur是null且換成全片句號(self):
		sb = board_sample(do=[{"act": "draw", "target": "i1"}, {"act": "blink", "target": "i1", "until": "二"}], lines=None)
		sb["chapters"][0]["pages"][0]["lines"][0]["do"][1]["until"] = "二"
		a = json.loads(build(sb)["objects.json"])[0]["do"]["1"][1]
		self.assertIsNone(a["dur"])
		self.assertEqual(a["args"]["until_line"], 2)
		self.assertNotIn("until_beat", a["args"])

	def test_置中最多三個(self):
		with self.assertRaisesRegex(ValueError, "3"):
			build(board_sample(objects=[icon(i) for i in range(4)], do=[]))

	def test_雙欄每欄最多兩個(self):
		objs = [icon(i, col="left") for i in range(3)]
		with self.assertRaisesRegex(ValueError, "2"):
			build(board_sample("two-col", objs, do=[]))

	def test_雙欄缺col(self):
		with self.assertRaisesRegex(ValueError, "col"):
			build(board_sample("two-col", [icon(0, col="left"), icon(1)], do=[]))

	def test_雙欄正常(self):
		bd = json.loads(build(board_sample("two-col", [icon(0, col="left"), icon(1, col="right")], do=[{"act": "draw", "target": "i0"}]))["objects.json"])
		self.assertEqual(bd[0]["template"], "two-col")

	def test_黑板沒有粉筆皮膚的元件(self):
		for t in ("list", "foo"):
			with self.assertRaisesRegex(ValueError, t):
				build(board_sample(objects=[{"type": t, "id": "x"}], do=[]))

	def test_意思對不到也在分鏡階段擋(self):
		with self.assertRaises(ValueError):
			build(board_sample(objects=[{"type": "icon", "id": "i1", "name": "等一下"}], do=[]))

	def test_note第一個動作要write或show(self):
		objs = [{"type": "note", "id": "n1", "text": "字"}]
		with self.assertRaisesRegex(ValueError, "n1"):
			build(board_sample(objects=objs, do=[{"act": "circle", "target": "n1"}]))
		build(board_sample(objects=objs, do=[{"act": "write", "target": "n1"}]))

	def test_沒有objects頁就不產objects檔(self):
		self.assertNotIn("objects.json", build(sample()))


if __name__ == "__main__":
	unittest.main()
