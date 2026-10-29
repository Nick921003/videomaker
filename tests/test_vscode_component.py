"""VS Code 元件的純函式（video_engine/components/vscode/*.js）：用 node 跑，斷言打在算出來的框與指令上。"""
import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine", "board"))
import compile as BC  # noqa: E402

PROBE = os.path.join(ROOT, "tests", "js", "vscode_probe.js")
NODE = shutil.which("node")


def compiled(name="vscode_full", edit=None):
	with open(os.path.join(ROOT, "video_engine", "board", "fixtures", name + ".scene.json"), encoding="utf-8") as f:
		doc = json.load(f)
	if edit:
		edit(doc)
	tl = BC.compile_scene(doc, None, BC.load_catalog())
	return tl["objects"]["vs"], [a for a in tl["actions"] if a["obj"] == "vs"], tl


def probe(cmd, desc, acts, ts, **kw):
	if not NODE:
		raise unittest.SkipTest("沒有 node")
	with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
		json.dump({"desc": desc, "acts": acts, "ts": ts, **kw}, f, ensure_ascii=False)
	try:
		r = subprocess.run([NODE, PROBE, cmd, f.name], capture_output=True, text=True, timeout=30)
	finally:
		os.unlink(f.name)
	if r.returncode:
		raise AssertionError(r.stderr)
	return json.loads(r.stdout)


def inside(b, r):
	return r["x"] - 0.5 <= b["x"] and r["y"] - 0.5 <= b["y"] and b["x"] + b["w"] <= r["x"] + r["w"] + 0.5 and b["y"] + b["h"] <= r["y"] + r["h"] + 0.5


def act_time(acts, act, k=0):
	return [a for a in acts if a["act"] == act][k]


class TestModel(unittest.TestCase):
	def test_每個宣告的錨點都有框(self):
		desc, acts, tl = compiled()
		ts = [0.0, tl["duration"] / 2, tl["duration"]]
		names = ["run", "gear", "explorer", "editor", "panel", "panel:end", "settings:search"]
		names += ["L%d" % n for n in range(1, len(desc["files"][desc["open"]]) + 1)]
		names += ["tab:" + f for f in desc["files"]] + ["file:" + f for f in desc["explorer"]]
		for t, an in zip(ts, probe("anchors", desc, acts, ts)):
			for n in names:
				self.assertIn(n, an, (t, n))
		menu = act_time(acts, "menu")
		an = probe("anchors", desc, acts, [menu["t1"] + 0.01])[0]
		for row in ("cmd", "settings", "ext"):
			self.assertIn(row, an)
		page = act_time(acts, "page")
		an = probe("anchors", desc, acts, [page["t1"] + 0.01])[0]
		self.assertIn("run_in_terminal", an)

	def test_錨點都在元件框內(self):
		desc, acts, tl = compiled()
		ts = [x / 4 * tl["duration"] for x in range(5)]
		lay = probe("layout", desc, acts, [0])[0]
		frame = {"x": 0, "y": 0, "w": lay["w"], "h": lay["h"]}
		for an in probe("anchors", desc, acts, ts):
			for n, b in an.items():
				self.assertTrue(inside(b, frame), (n, b))

	def test_版面不隨時間改變(self):
		desc, acts, tl = compiled()
		a, b = probe("layout", desc, acts, [0, tl["duration"]])
		self.assertEqual(a, b)

	def test_長程式自動捲到高亮行(self):
		def long(doc):
			doc["objects"][0]["files"]["hello.c"] = ["// %d" % i for i in range(1, 41)]
			doc["scenes"][0]["beats"][0]["do"].append({"act": "highlight", "target": "vs", "lines": [35], "file": "hello.c"})
			doc["scenes"][0]["beats"][0]["do"].insert(1, {"act": "open", "target": "vs", "file": "hello.c"})
		desc, acts, tl = compiled("vscode_min", long)
		h = act_time(acts, "highlight")
		lay = probe("layout", desc, acts, [0])[0]
		an = probe("anchors", desc, acts, [h["t1"] + 0.01])[0]
		self.assertTrue(inside(an["L35"], lay["regions"]["editor"]), an["L35"])
		self.assertGreater(an["L35"]["h"], 0)

	def test_run後input接在輸出之後(self):
		desc, acts, _ = compiled()
		inp = act_time(acts, "input")
		per = (inp["t1"] - inp["t0"]) / 2
		run = act_time(acts, "run")
		before, one, two = probe("state", desc, acts, [run["t1"] + 0.01, inp["t0"] + 0.01, inp["t1"] - 0.001])
		self.assertEqual(before["panel"]["lines"][-1], "請輸入成績: ")
		self.assertEqual(one["panel"]["lines"][-1], "請輸入成績: 8")
		self.assertEqual(two["panel"]["lines"][-1], "請輸入成績: 85")
		self.assertTrue(per > 0)

	def test_勾選設定項(self):
		desc, acts, _ = compiled()
		chk = act_time(acts, "check")
		a, b = probe("state", desc, acts, [chk["t0"] - 0.01, chk["t1"]])
		self.assertFalse(a["checks"]["run_in_terminal"])
		self.assertTrue(b["checks"]["run_in_terminal"])


if __name__ == "__main__":
	unittest.main()
