"""storyboard_to_scene：同一份黑板分鏡轉成手帳 scene.json／timing.json，兩邊都經編譯器驗證。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

from video_engine.board import compile as BC
from video_engine.explainer.storyboard import build
from video_engine.explainer.storyboard_to_scene import to_scene, to_timing

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VS = {"type": "vscode", "id": "vs", "files": {"score.c": ["int main(void) {", "}"]}, "panel": "output"}


def sb3():
	"""置中、雙欄、電腦畫面各一頁，加結語與複習"""
	return {
		"title": "T", "subtitle": "S",
		"chapters": [
			{"id": "a", "title": "甲", "pages": [
				{"template": "center", "spine": "骨一", "objects": [{"type": "icon", "id": "warn", "name": "警告"}],
					"lines": [{"say": "先小心這裡。", "lead": 1.0, "do": [{"act": "draw", "target": "warn"}]},
						{"say": "它會閃一下。", "do": [{"act": "blink", "target": "warn", "cue": "閃"}]}]},
				{"template": "two-col", "spine": "骨二", "objects": [
					{"type": "note", "id": "left", "text": "左邊", "col": "left"},
					{"type": "icon", "id": "ok", "name": "check", "col": "right"}],
					"lines": [{"say": "左邊寫字，右邊打勾。", "do": [{"act": "write", "target": "left"}, {"act": "draw", "target": "ok", "cue": "打勾"}]}]},
			]},
			{"id": "b", "title": "乙", "pages": [
				{"template": "screen", "kind": "vscode", "spine": "骨三", "screen": dict(VS), "lines": [
					{"say": "我們按右上角這個三角形，跑跑看。", "do": [{"act": "click", "target": "cursor", "on": "vs:run", "cue": "跑跑看"}]}]},
			]},
		],
		"end": {"emphasis": "E", "say": "就這樣。"},
		"recap": {"center": "C", "tagline": "G", "length": 8, "say": "複習一下。", "items": ["小心 | 先停", "打勾 | 完成"]},
	}


def story(lines, recap_say=None):
	"""lines＝[(start, end, lead)]；最後一筆是結語"""
	s = {"lines": [{"i": k + 1, "start": a, "end": b, "lead": ld} for k, (a, b, ld) in enumerate(lines)]}
	if recap_say:
		s["recap"] = {"start": recap_say[0] - 0.6, "end": recap_say[1] + 2.5, "say": {"text": "複習一下。", "start": recap_say[0], "end": recap_say[1]}}
	return s


class TestToScene(unittest.TestCase):
	def test_置中雙欄電腦畫面(self):
		sc = to_scene(sb3())
		ids = [s["id"] for s in sc["scenes"]]
		self.assertEqual(ids, ["a_p1", "a_p2", "b_p1", "recap"])
		self.assertEqual(sc["scenes"][0]["title"], "甲")
		self.assertEqual(sc["scenes"][0]["layout"], {"stack": ["warn"]})
		self.assertEqual(sc["scenes"][1]["layout"], {"row": [{"stack": ["left"]}, {"stack": ["ok"]}]})
		self.assertEqual(sc["scenes"][2]["layout"], {"stack": ["vs"]})
		objs = {o["id"]: o for o in sc["objects"]}
		self.assertEqual(objs["cursor"]["type"], "cursor")
		self.assertNotIn("col", objs["left"])
		# 結語接在最後一個正文 scene，複習頁是 list
		self.assertEqual(sc["scenes"][2]["beats"][-1]["say"], "就這樣。")
		self.assertEqual(sc["scenes"][3]["beats"][0]["say"], "複習一下。")
		self.assertEqual(objs[sc["scenes"][3]["layout"]["stack"][0]]["rows"], ["小心 | 先停", "打勾 | 完成"])
		BC.Compiler(sc, None, BC.load_catalog()).run()

	def test_同一份分鏡兩邊都驗過(self):
		sb = sb3()
		out = build(sb)
		chalk = sum(len(v) for b in json.loads(out["objects.json"]) for v in b["do"].values())
		chalk += sum(len(v) for s in json.loads(out["screens.json"]) for v in s.get("do", {}).values())
		c = BC.Compiler(to_scene(sb), None, BC.load_catalog())
		c.run()
		recap = sum(1 for a in c.actions if self_scene(c, a) == "recap")
		self.assertEqual(len(c.actions) - recap, chalk)

	def test_id重複要報錯(self):
		sb = sb3()
		sb["chapters"][0]["pages"][1]["objects"][1]["id"] = "warn"
		with self.assertRaisesRegex(ValueError, "warn"):
			to_scene(sb)

	def test_電腦畫面兩段只放一個游標(self):
		sb = sb3()
		vs2 = dict(VS, id="vs2")
		sb["chapters"][1]["pages"].append({"template": "screen", "screen": vs2, "lines": [{"say": "再按一次跑跑看。", "do": [
			{"act": "click", "target": "cursor", "on": "vs2:run", "cue": "跑跑看"}]}]})
		sc = to_scene(sb)
		self.assertEqual([o["id"] for o in sc["objects"]].count("cursor"), 1)
		BC.Compiler(sc, None, BC.load_catalog()).run()


def self_scene(c, a):
	return c.doc["scenes"][a["scene"]]["id"]


class TestTiming(unittest.TestCase):
	def test_先畫後講(self):
		s = story([(2.0, 4.0, 1.0), (4.5, 6.0, 0.0), (8.0, 10.0, 0.0), (13.0, 16.0, 0.0), (17.0, 18.0, 0.0)], recap_say=(20.0, 21.0))
		tm = to_timing(s)
		self.assertEqual(len(tm), 6)
		self.assertEqual((tm[0]["t0"], tm[0]["draw"]), (2.0, 1.0))
		self.assertEqual(tm[1]["draw"], 4.5)
		self.assertEqual((tm[5]["t0"], tm[5]["t1"]), (20.0, 21.0))
		tl = BC.Compiler(to_scene(sb3()), tm, BC.load_catalog()).run()
		acts = [a for a in tl["actions"] if a["beat"] == 0]
		# 第一句第一個動作從 draw 起跑；字幕仍對著聲音
		self.assertAlmostEqual(acts[0]["t0"], 1.0)
		self.assertEqual(tl["beats"][0]["t0"], 2.0)
		self.assertEqual(tl["subtitles"][0]["t0"], 2.0)
		# 有 cue 的動作照 cue 對齊，不受 draw 影響
		blink = next(a for a in tl["actions"] if a["act"] == "blink")
		b = tl["beats"][1]
		want = b["t0"] + (b["t1"] - b["t0"]) * b["say"].index("閃") / len(b["say"]) - BC.CUE_LEAD
		self.assertAlmostEqual(blink["t0"], max(want, tl["beats"][0]["t1"]))

	def test_lead比空檔長(self):
		tm = to_timing(story([(2.0, 4.0, 0.0), (4.5, 6.0, 2.0)]))
		self.assertEqual(tm[1]["draw"], 4.0)
		self.assertEqual(tm[1]["t0"], 4.5)

	def test_第一句lead不小於零(self):
		self.assertEqual(to_timing(story([(0.5, 2.0, 2.0)]))[0]["draw"], 0.0)

	def test_draw不能晚於t0(self):
		sc = to_scene(sb3())
		tm = to_timing(story([(2.0, 4.0, 0.0), (4.5, 6.0, 0.0), (8.0, 10.0, 0.0), (13.0, 16.0, 0.0), (17.0, 18.0, 0.0)], recap_say=(20.0, 21.0)))
		tm[1]["draw"] = 5.0
		with self.assertRaisesRegex(ValueError, "draw"):
			BC.Compiler(sc, tm, BC.load_catalog()).run()

	def test_換場第一句等鏡頭到位(self):
		tm = to_timing(story([(2.0, 4.0, 0.0), (4.5, 6.0, 0.0), (7.0, 8.0, 3.0), (13.0, 16.0, 0.0), (17.0, 18.0, 0.0)], recap_say=(20.0, 21.0)))
		self.assertEqual(tm[2]["draw"], 6.0)
		tl = BC.Compiler(to_scene(sb3()), tm, BC.load_catalog()).run()
		first = next(a for a in tl["actions"] if a["beat"] == 2)
		self.assertAlmostEqual(first["t0"], 6.0 - BC.SCENE_CAM_EARLY + BC.SCENE_CAM_DUR)


class TestCli(unittest.TestCase):
	def test_有story才寫timing(self):
		d, out = tempfile.mkdtemp(), tempfile.mkdtemp()
		with open(os.path.join(d, "storyboard.json"), "w", encoding="utf-8") as f:
			json.dump(sb3(), f, ensure_ascii=False)
		cmd = [sys.executable, os.path.join(ROOT, "video_engine", "explainer", "storyboard_to_scene.py"), d, out]
		r = subprocess.run(cmd, capture_output=True, text=True)
		self.assertEqual(r.returncode, 0, r.stderr)
		self.assertTrue(os.path.exists(os.path.join(out, "scene.json")))
		self.assertFalse(os.path.exists(os.path.join(out, "timing.json")))
		with open(os.path.join(d, "story.json"), "w", encoding="utf-8") as f:
			json.dump(story([(2.0, 4.0, 1.0), (4.5, 6.0, 0.0), (8.0, 10.0, 0.0), (13.0, 16.0, 0.0), (17.0, 18.0, 0.0)], recap_say=(20.0, 21.0)), f)
		r = subprocess.run(cmd, capture_output=True, text=True)
		self.assertEqual(r.returncode, 0, r.stderr)
		with open(os.path.join(out, "timing.json"), encoding="utf-8") as f:
			self.assertEqual(len(json.load(f)), 6)


if __name__ == "__main__":
	unittest.main()
