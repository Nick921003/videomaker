import copy
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine", "board"))

import compile as BC

CATALOG = BC.load_catalog()


def scene_doc(beats_a=None, beats_b=None, objects=None):
	objects = objects if objects is not None else [
		{"id": "q", "type": "note", "text": "問句"},
		{"id": "arr", "type": "cells", "count": 6, "values": [None] * 6},
		{"id": "src", "type": "note", "text": "\"Alice\"", "style": "code"},
		{"id": "out", "type": "output", "max_text": "Alice"},
	]
	return {
		"version": 1, "title": "t", "objects": objects,
		"scenes": [
			{"id": "a", "title": "A", "layout": {"stack": ["q"]}, "beats": beats_a or [
				{"say": "一二三四五", "do": [{"act": "write", "target": "q"}]},
			]},
			{"id": "b", "title": "B", "keep": ["arr"], "layout": {"stack": ["src", "arr", "out"]}, "beats": beats_b or [
				{"say": "六七八九十", "do": []},
			]},
		],
	}


def compiled(doc, timing=None):
	return BC.compile_scene(doc, timing, CATALOG)


class TestBeatTiming(unittest.TestCase):
	def test_無實測時依字數估算並含句間與換場停頓(self):
		tl = compiled(scene_doc())
		b0, b1 = tl["beats"]
		self.assertAlmostEqual(b0["t0"], BC.LEAD_IN)
		self.assertAlmostEqual(b0["t1"] - b0["t0"], 5 * BC.SEC_PER_CHAR)
		self.assertAlmostEqual(b1["t0"], b0["t1"] + BC.BEAT_GAP + BC.SCENE_GAP)
		self.assertAlmostEqual(tl["duration"], b1["t1"] + BC.TAIL)

	def test_有實測時用實測起訖(self):
		tl = compiled(scene_doc(), [{"t0": 0.3, "t1": 2.0}, {"t0": 3.0, "t1": 5.5}])
		self.assertEqual([(b["t0"], b["t1"]) for b in tl["beats"]], [(0.3, 2.0), (3.0, 5.5)])

	def test_實測筆數不符要報錯(self):
		with self.assertRaises(ValueError):
			compiled(scene_doc(), [{"t0": 0.3, "t1": 2.0}])

	def test_字幕從本句起點顯示到下一句起點(self):
		tl = compiled(scene_doc(), [{"t0": 0.3, "t1": 2.0}, {"t0": 3.0, "t1": 5.5}])
		self.assertEqual(tl["subtitles"][0], {"t0": 0.3, "t1": 3.0, "text": "一二三四五"})
		self.assertAlmostEqual(tl["subtitles"][1]["t1"], tl["duration"])


class TestActionTiming(unittest.TestCase):
	def timed(self, do, say="把字母放進去然後結束", timing=None):
		doc = scene_doc(beats_b=[{"say": say, "do": do}])
		return compiled(doc, timing or [{"t0": 0.0, "t1": 1.0}, {"t0": 2.0, "t1": 12.0}])

	def test_cue_依字元位置比例定起點(self):
		tl = self.timed([{"act": "show", "target": "src", "cue": "放進去"}])
		act = tl["actions"][-1]
		self.assertAlmostEqual(act["t0"], 2.0 + 10.0 * (3 / 10))

	def test_cue_不在句中要報錯(self):
		with self.assertRaises(ValueError):
			self.timed([{"act": "show", "target": "src", "cue": "不存在"}])

	def test_無cue接續前一動作終點_with_prev_同起點(self):
		tl = self.timed([
			{"act": "show", "target": "src"},
			{"act": "show", "target": "out"},
			{"act": "point", "target": "arr", "index": 0, "with": "prev"},
		])
		a, b, c = tl["actions"][-3:]
		self.assertAlmostEqual(a["t0"], 2.0)
		self.assertAlmostEqual(b["t0"], a["t1"])
		self.assertAlmostEqual(c["t0"], b["t0"])

	def test_序列動作撐滿到下一個錨定的阻擋動作(self):
		tl = self.timed([
			{"act": "fill", "target": "arr", "from": "src", "values": ["A", "l", "i", "c", "e", "\\0"]},
			{"act": "stop", "target": "arr", "index": 5, "cue": "結束"},
		], timing=[{"t0": 0.0, "t1": 1.0}, {"t0": 2.0, "t1": 6.0}])
		fill, stop = tl["actions"][-2:]
		self.assertAlmostEqual(fill["t1"], stop["t0"] - BC.SEQ_MARGIN)
		self.assertEqual(fill["n"], 6)

	def test_序列動作不超過每項上限(self):
		tl = self.timed([{"act": "fill", "target": "arr", "values": ["A", "l"]}])
		fill = tl["actions"][-1]
		self.assertAlmostEqual(fill["t1"] - fill["t0"], 2 * 0.6)

	def test_時間不足時夾在下限並警告趕(self):
		tl = self.timed([
			{"act": "scan", "target": "arr", "range": [0, 4], "to": "out"},
			{"act": "stop", "target": "arr", "index": 5, "cue": "把"},
		], say="把字母放進去然後結束")
		scan = tl["actions"][-2]
		self.assertAlmostEqual(scan["t1"] - scan["t0"], 5 * 0.3)
		self.assertTrue(any("趕" in w for w in tl["warnings"]))

	def test_非阻擋動作不截斷序列(self):
		tl = self.timed([
			{"act": "fill", "target": "arr", "values": ["A", "l", "i"]},
			{"act": "focus", "target": "arr:i1", "cue": "然後"},
		])
		fill = tl["actions"][-2]
		self.assertAlmostEqual(fill["t1"] - fill["t0"], 3 * 0.6)

	def test_scan_由編譯器算出讀到的字元(self):
		tl = self.timed([
			{"act": "fill", "target": "arr", "values": ["A", "l", "i", "c", "e", "\\0"]},
			{"act": "scan", "target": "arr", "range": [0, 4], "to": "out"},
		])
		self.assertEqual(tl["actions"][-1]["args"]["chars"], ["A", "l", "i", "c", "e"])


class TestValidation(unittest.TestCase):
	def test_錨點前綴不是已知物件要報錯(self):
		doc = scene_doc(beats_b=[{"say": "六七八", "do": [{"act": "circle", "target": "nope:i1"}]}])
		with self.assertRaises(ValueError):
			compiled(doc)

	def test_錨點超出格數要報錯(self):
		doc = scene_doc(beats_b=[{"say": "六七八", "do": [{"act": "circle", "target": "arr:i6"}]}])
		with self.assertRaises(ValueError):
			compiled(doc)

	def test_layout_引用不存在的物件要報錯(self):
		doc = scene_doc()
		doc["scenes"][0]["layout"] = {"stack": ["q", "ghost"]}
		with self.assertRaises(ValueError):
			compiled(doc)

	def test_缺必填參數要報錯(self):
		doc = scene_doc(beats_b=[{"say": "六七八", "do": [{"act": "fill", "target": "arr"}]}])
		with self.assertRaises(ValueError):
			compiled(doc)


class TestGaps(unittest.TestCase):
	def test_未知型別退化成note並記缺口(self):
		objs = [{"id": "q", "type": "note", "text": "問句"}, {"id": "arr", "type": "cells", "count": 6},
			{"id": "src", "type": "flowchart", "fallback": "原始碼→執行檔"}, {"id": "out", "type": "output"}]
		tl = compiled(scene_doc(objects=objs))
		self.assertEqual(tl["objects"]["src"]["type"], "note")
		self.assertEqual(tl["objects"]["src"]["text"], "原始碼→執行檔")
		self.assertEqual(tl["gaps"][0]["wanted"], "flowchart")

	def test_不支援的動作略過並記缺口(self):
		doc = scene_doc(beats_b=[{"say": "六七八", "do": [{"act": "explode", "target": "arr"}]}])
		tl = compiled(doc)
		self.assertFalse(any(a["act"] == "explode" for a in tl["actions"]))
		self.assertEqual(tl["gaps"][0]["wanted"], "cells.explode")


class TestVisibilityAndEpochs(unittest.TestCase):
	def test_動作會自動顯示被指到的物件(self):
		tl = compiled(scene_doc())
		self.assertAlmostEqual(tl["visibility"]["q"][0][0], tl["actions"][0]["t0"])

	def test_hide_結束可見區間(self):
		doc = scene_doc(beats_b=[{"say": "六七八九十", "do": [
			{"act": "show", "target": "src"}, {"act": "hide", "target": "src"}]}])
		tl = compiled(doc)
		show, hide = tl["actions"][-2:]
		self.assertEqual(tl["visibility"]["src"], [[show["t0"], hide["t1"]]])

	def test_換場時keep的物件改住新場景_版面只含本場可見物件(self):
		doc = scene_doc(beats_a=[{"say": "一二三四五", "do": [{"act": "write", "target": "q"}, {"act": "show", "target": "arr"}]}])
		doc["scenes"][0]["layout"] = {"stack": ["q", "arr"]}
		tl = compiled(doc)
		last = tl["epochs"][-1]
		self.assertEqual(last["scene"], 1)
		self.assertEqual(last["tree"], {"stack": ["arr"]})

	def test_單一子節點的容器會攤平(self):
		self.assertEqual(BC.filter_tree({"row": ["a", {"stack": ["b", "c"]}]}, {"b"}), {"stack": ["b"]})
		self.assertIsNone(BC.filter_tree({"row": ["a"]}, set()))


if __name__ == "__main__":
	unittest.main()


def one_scene(objects, do, say="一二三四五", **scene):
	return {"version": 1, "objects": objects, "scenes": [{"id": "s", "beats": [{"say": say, "do": do}], **scene}]}


class TestCodexReview(unittest.TestCase):
	"""2026-10-03 Codex 對抗審查找到的十個案例。"""

	def test_不支援的首個動作改成show且下一動作正常接續(self):
		tl = compiled(one_scene([{"id": "q", "type": "note", "text": "Q"}], [{"act": "explode", "target": "q"}, {"act": "show", "target": "q"}]))
		first, second = tl["actions"]
		self.assertEqual((first["act"], first["t0"]), ("show", BC.LEAD_IN))
		self.assertAlmostEqual(second["t0"], first["t1"])

	def test_退化物件即使動作全被略過也要顯示保底文字(self):
		doc = one_scene([{"id": "f", "type": "flowchart", "fallback": "A→B"}], [{"act": "trace", "target": "f"}], say="把內容呈現出來", layout={"stack": ["f"]})
		tl = compiled(doc)
		self.assertTrue(tl["visibility"]["f"])
		self.assertEqual(tl["epochs"][-1]["tree"], {"stack": ["f"]})
		self.assertEqual({g["kind"] for g in tl["gaps"]}, {"type", "action"})

	def test_舊場景延後的動作不會把keep的物件拉回舊場(self):
		doc = {"version": 1, "objects": [{"id": "q", "type": "note", "text": "Q"}, {"id": "p", "type": "note", "text": "P"}], "scenes": [
			{"id": "a", "layout": {"stack": ["q"]}, "beats": [{"say": "一二三四五", "do": [
				{"act": "show", "target": "q"}, {"act": "circle", "target": "q"}, {"act": "underline", "target": "q"}]}]},
			{"id": "b", "keep": ["q"], "layout": {"stack": ["q", "p"]}, "beats": [{"say": "六七八九十", "do": [{"act": "show", "target": "p", "cue": "九"}]}]}]}
		tl = compiled(doc, [{"t0": 0, "t1": 1}, {"t0": 1, "t1": 3}])
		self.assertEqual(tl["epochs"][-1]["tree"], {"stack": ["q", "p"]})

	def test_say_必須是字串(self):
		with self.assertRaises(ValueError):
			compiled(one_scene([{"id": "q", "type": "note", "text": "Q"}], [{"act": "show", "target": "q"}], say=123), [{"t0": 0, "t1": 2}])

	def test_序列窗口認得with_prev繼承的起點(self):
		doc = one_scene([{"id": "arr", "type": "cells", "count": 6}, {"id": "q", "type": "note", "text": "Q"}], [
			{"act": "fill", "target": "arr", "values": ["A", "B", "C", "D", "E", "F"]},
			{"act": "show", "target": "q", "cue": "八"},
			{"act": "stop", "target": "arr", "index": 5, "with": "prev"}], say="一二三四五六七八九十")
		tl = compiled(doc, [{"t0": 0, "t1": 4}])
		fill, show, stop = tl["actions"]
		self.assertAlmostEqual(stop["t0"], 2.8)
		self.assertAlmostEqual(fill["t1"], 2.8 - BC.SEQ_MARGIN)

	def test_同時刻的hide與show依動作順序(self):
		tl = compiled(one_scene([{"id": "q", "type": "note", "text": "Q"}], [
			{"act": "show", "target": "q"}, {"act": "hide", "target": "q"}, {"act": "show", "target": "q", "with": "prev"}]))
		self.assertIsNone(tl["visibility"]["q"][-1][1])

	def test_timing_拒絕倒置與負時間(self):
		doc = one_scene([{"id": "q", "type": "note", "text": "Q"}], [{"act": "show", "target": "q", "cue": "五"}])
		for bad in ([{"t0": 3, "t1": 2}], [{"t0": -5, "t1": -3}]):
			with self.assertRaises(ValueError):
				compiled(doc, bad)

	def test_cells_索引與範圍都要驗證(self):
		objs = [{"id": "c", "type": "cells", "count": 2, "values": ["A", "B"]}, {"id": "k", "type": "code", "lines": ["x"]}]
		for act in ({"act": "fill", "target": "c", "start": -1, "values": ["X"]}, {"act": "fill", "target": "c", "start": 1, "values": ["X", "Y"]},
				{"act": "point", "target": "c", "index": 2}, {"act": "stop", "target": "c", "index": -1},
				{"act": "brace", "target": "c", "range": [1, 0], "label": "x"}, {"act": "highlight", "target": "k", "line": 99}):
			with self.assertRaises(ValueError, msg=act):
				compiled(one_scene(objs, [act]))

	def test_append_以錨點為target時仍計入該清單(self):
		tl = compiled(one_scene([{"id": "l", "type": "list", "rows": ["a"]}], [
			{"act": "append", "target": "l:title", "text": "b"}, {"act": "circle", "target": "l:r1"}], say="新增然後圈起"))
		self.assertEqual(tl["actions"][-1]["target"], "l:r1")

	def test_terminal_行錨點有上限(self):
		with self.assertRaises(ValueError):
			compiled(one_scene([{"id": "t", "type": "terminal"}], [
				{"act": "print", "target": "t", "lines": ["a"]}, {"act": "circle", "target": "t:line999"}], say="印出後圈選"))


class TestFloatingAndNamedAnchors(unittest.TestCase):
	def catalog(self):
		cat = copy.deepcopy(CATALOG)
		cat["types"]["panel"] = {"req": ["parts"], "opt": [], "anchors": ["{key}"], "actions": {}}
		cat["types"]["pointer"] = {"req": [], "opt": [], "floating": True, "anchors": [], "actions": {
			"click": {"dur": 0.8, "req": ["on"], "anchor_args": ["on"], "blocks": True}}}
		return cat

	def doc(self, on="w:ok"):
		return one_scene([{"id": "w", "type": "panel", "parts": [{"button": "確定", "id": "ok"}, {"rows": [{"id": "r1", "text": "x"}]}]},
			{"id": "m", "type": "pointer"}], [{"act": "show", "target": "w"}, {"act": "click", "target": "m", "on": on}], layout={"stack": ["w"]})

	def test_具名錨點取自物件內宣告的id(self):
		tl = BC.compile_scene(self.doc("w:r1"), None, self.catalog())
		self.assertEqual(tl["actions"][-1]["args"]["on"], "w:r1")

	def test_未宣告的具名錨點要報錯(self):
		with self.assertRaises(ValueError):
			BC.compile_scene(self.doc("w:nope"), None, self.catalog())

	def test_浮動物件不進版面也不觸發漏列警告(self):
		tl = BC.compile_scene(self.doc(), None, self.catalog())
		self.assertEqual(tl["epochs"][-1]["tree"], {"stack": ["w"]})
		self.assertFalse(any("沒列到" in w for w in tl["warnings"]))
		self.assertTrue(tl["visibility"]["m"])
