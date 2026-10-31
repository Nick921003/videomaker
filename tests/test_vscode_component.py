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
sys.path.insert(0, os.path.join(ROOT, "video_engine", "explainer"))
import storyboard as SB  # noqa: E402

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


with open(os.path.join(ROOT, "video_engine", "themes", "vscode_dark.json"), encoding="utf-8") as _f:
	THEME = json.load(_f)
COLOR_FIELDS = ("fill", "stroke", "color")


def theme_has(key):
	v = THEME
	for k in key.split("."):
		v = v.get(k) if isinstance(v, dict) else None
	return isinstance(v, str)


class TestPaint(unittest.TestCase):
	def test_指令顏色都是主題鍵(self):
		desc, acts, tl = compiled()
		for ops in probe("ops", desc, acts, [x / 6 * tl["duration"] for x in range(7)]):
			self.assertTrue(ops)
			for op in ops:
				for f in COLOR_FIELDS:
					if f in op:
						self.assertTrue(theme_has(op[f]), (op["op"], f, op[f]))

	def test_所有指令都在元件框內(self):
		desc, acts, tl = compiled()
		lay = probe("layout", desc, acts, [0])[0]
		frame = {"x": 0, "y": 0, "w": lay["w"], "h": lay["h"]}
		for ops in probe("ops", desc, acts, [x / 6 * tl["duration"] for x in range(7)]):
			for op in ops:
				if op["op"] == "rect":
					self.assertTrue(inside(op, frame), op)
				elif op["op"] == "text":
					x0 = op["x"] - (op["w"] if op.get("align") == "end" else op["w"] / 2 if op.get("align") == "middle" else 0)
					self.assertTrue(inside({"x": x0, "y": op["y"] - op["size"] / 2, "w": op["w"], "h": op["size"]}, frame), op)

	def test_長輸出截斷不溢出(self):
		long = "[Running] cd \"c:\\Users\\student\\c_homework\\\" && gcc score.c -o score && " + "很長的路徑" * 30
		def edit(doc):
			doc["scenes"][0]["beats"][0]["do"].append({"act": "run", "target": "vs", "output": [long]})
		desc, acts, _ = compiled("vscode_min", edit)
		run = act_time(acts, "run", 1)
		lay = probe("layout", desc, acts, [0])[0]
		p = lay["regions"]["panel"]
		ops = probe("ops", desc, acts, [run["t1"] + 0.01])[0]
		texts = [o for o in ops if o["op"] == "text" and p["y"] < o["y"] < p["y"] + p["h"]]
		self.assertTrue(any(o["str"].endswith("…") for o in texts), [o["str"] for o in texts])
		for o in texts:
			self.assertLessEqual(o["x"] + o["w"], p["x"] + p["w"] + 0.5, o)


	def test_字級倍率放大字與行距但版面框不變(self):
		desc, acts, _ = compiled()
		big = dict(desc, _text=1.6)
		a, b = probe("layout", desc, acts, [0])[0], probe("layout", big, acts, [0])[0]
		self.assertEqual((a["w"], a["h"]), (b["w"], b["h"]))
		self.assertAlmostEqual(b["m"]["ui"], a["m"]["ui"] * 1.6)
		self.assertAlmostEqual(b["m"]["pitch"], a["m"]["pitch"] * 1.6)
		ops = probe("ops", big, acts, [0])[0]
		self.assertGreaterEqual(min(o["size"] for o in ops if o["op"] == "text" and not o.get("detail")), 20 * 1.6 - 0.01)

	def test_頁面打開時底下的字不畫(self):
		desc, acts, _ = compiled()
		page = act_time(acts, "page")
		ops = probe("ops", desc, acts, [page["t1"] + 0.01])[0]
		self.assertFalse([o for o in ops if o["op"] == "text" and o["str"] == "score.c"])

	def test_標題列選單字不壓到搜尋框(self):
		desc, acts, _ = compiled()
		ops = probe("ops", desc, acts, [0])[0]
		box = [o for o in ops if o["op"] == "rect" and o.get("fill") == "titleBox"][0]
		words = [o for o in ops if o["op"] == "text" and o["str"] in ("檔案", "編輯", "選取項目", "檢視", "移至", "執行", "終端機", "說明") and o["y"] < box["y"] + box["h"]]
		self.assertTrue(words)
		for o in words:
			self.assertLessEqual(o["x"] + o["w"], box["x"], o["str"])

	def test_svg決定性(self):
		desc, acts, tl = compiled()
		a, b = probe("svg", desc, acts, [tl["duration"] / 2, tl["duration"] / 2], theme=THEME)
		self.assertEqual(a, b)
		self.assertTrue(a.startswith("<svg"))
		self.assertNotIn("NaN", a)
		self.assertNotIn("undefined", a)

	def test_元件不寫死色碼也不讀時鐘(self):
		hexes = re.compile(r"#[0-9a-fA-F]{3,8}\b")
		banned = re.compile(r"Math\.random|Date\.now|performance\.now|new Date\(")
		for dirpath, _, files in os.walk(os.path.join(ROOT, "video_engine", "components")):
			for name in files:
				if name.endswith(".js"):
					with open(os.path.join(dirpath, name), encoding="utf-8") as f:
						src = f.read()
					self.assertIsNone(hexes.search(src), name)
					self.assertIsNone(banned.search(src), name)


PW_PY = os.path.expanduser("~/.local/share/pipx/venvs/webwright/bin/python")
EXPORT = os.path.join(ROOT, "video_engine", "components", "vscode", "export_png.py")


class TestExport(unittest.TestCase):
	def test_png兩次輸出逐位元組相同(self):
		if not os.path.exists(PW_PY):
			self.skipTest("沒有 webwright 的 Playwright")
		import hashlib
		from PIL import Image
		with open(os.path.join(ROOT, "video_engine", "board", "fixtures", "vscode_full.scene.json"), encoding="utf-8") as f:
			doc = json.load(f)
		desc = {"object": doc["objects"][0], "do": [a for a in doc["scenes"][0]["beats"][1]["do"] if a["act"] in ("run", "input")]}
		with tempfile.TemporaryDirectory() as d:
			src = os.path.join(d, "a.json")
			with open(src, "w", encoding="utf-8") as f:
				json.dump(desc, f, ensure_ascii=False)
			outs = []
			for k in range(2):
				out = os.path.join(d, "%d.png" % k)
				r = subprocess.run([PW_PY, EXPORT, src, out, "--size", "1280x800"], capture_output=True, text=True, timeout=120)
				self.assertEqual(r.returncode, 0, r.stderr)
				with open(out, "rb") as f:
					outs.append(hashlib.md5(f.read()).hexdigest())
			self.assertEqual(outs[0], outs[1])
			with Image.open(os.path.join(d, "0.png")) as im:
				self.assertEqual(im.size, (1280, 800))


def mini(do, panel="output", pages=None):
	"""一個場景、一句話的小描述，動作依序排；回傳 (desc, acts, tl)"""
	def edit(doc):
		doc["objects"][0]["panel"] = panel
		if pages:
			doc["objects"][0]["pages"] = pages
		doc["scenes"][0]["beats"][0]["do"] = [{"act": "show", "target": "vs"}] + do
	return compiled("vscode_min", edit)


class TestMoreActions(unittest.TestCase):
	def test_面板切換各自保留內容(self):
		desc, acts, tl = mini([{"act": "run", "target": "vs", "output": ["[Running] a"]},
			{"act": "panel", "target": "vs", "name": "terminal"}, {"act": "print", "target": "vs", "lines": ["PS> b"]},
			{"act": "panel", "target": "vs", "name": "output"}])
		sw = act_time(acts, "panel")
		a, b, c = probe("state", desc, acts, [sw["t0"] - 0.01, act_time(acts, "print")["t1"] - 0.001, tl["duration"]])
		self.assertEqual((a["panel"]["kind"], a["panel"]["lines"]), ("output", ["[Running] a"]))
		self.assertEqual((b["panel"]["kind"], b["panel"]["lines"]), ("terminal", ["PS> b"]))
		self.assertEqual(c["panel"]["lines"], ["[Running] a"])

	def test_面板分頁與每行都有錨點(self):
		desc, acts, tl = mini([{"act": "run", "target": "vs", "output": ["[Running] a", "請輸入成績: "]}])
		an = probe("anchors", desc, acts, [tl["duration"]])[0]
		for n in ("ptab:output", "ptab:terminal", "P1", "P2"):
			self.assertIn(n, an)
		self.assertLess(an["P1"]["y"], an["P2"]["y"])

	def test_P是絕對行號各種字級都指同一行(self):
		out = ["line %d" % i for i in range(1, 13)]
		desc, acts, tl = mini([{"act": "run", "target": "vs", "output": out}])
		for fs in (None, 1.6):
			d = dict(desc, _text=fs) if fs else desc
			an = probe("anchors", d, acts, [tl["duration"]])[0]
			self.assertEqual(an["P12"]["y"], an["panel:end"]["y"], fs)
			self.assertEqual(an["P1"]["h"], 0, fs)
			self.assertGreater(an["P12"]["h"], 0, fs)

	def test_唯讀提示框到下一個動作就收(self):
		desc, acts, tl = mini([{"act": "run", "target": "vs", "output": ["請輸入成績: "]},
			{"act": "tip", "target": "vs", "text": "無法在唯讀編輯器中編輯"}, {"act": "stop", "target": "vs"}])
		tip, stop = act_time(acts, "tip"), act_time(acts, "stop")
		a, b = probe("state", desc, acts, [tip["t1"] - 0.001, stop["t0"] + 0.01])
		self.assertEqual(a["tip"], "無法在唯讀編輯器中編輯")
		self.assertIsNone(b["tip"])
		self.assertIn("tip", probe("anchors", desc, acts, [tip["t1"] - 0.001])[0])

	def test_設定搜尋框逐字打入(self):
		desc, acts, _ = mini([{"act": "page", "target": "vs", "name": "settings"}, {"act": "type", "target": "vs", "text": "run in terminal"}], pages=["settings"])
		ty = act_time(acts, "type")
		a, b, c = probe("state", desc, acts, [ty["t0"] - 0.01, ty["t0"] + 0.01, ty["t1"]])
		self.assertEqual(a["search"], "")
		self.assertEqual(b["search"], "r")
		self.assertEqual(c["search"], "run in terminal")
		ops = probe("ops", desc, acts, [ty["t0"] + 0.01])[0]
		self.assertFalse([o for o in ops if o["op"] == "text" and o["str"].startswith("Run In Terminal")])

	def test_輸出照實機上色(self):
		desc, acts, tl = mini([{"act": "run", "target": "vs", "output": ["[Running] cd x", "[Done] exited with code=1 in 2 seconds", "ld.exe: cannot open output file score.exe: Permission denied"]}])
		ops = probe("ops", desc, acts, [tl["duration"]])[0]
		color = {o["str"]: o["color"] for o in ops if o["op"] == "text"}
		self.assertEqual(color["[Running]"], "link")
		self.assertEqual(color["[Done]"], "link")
		self.assertEqual(color[" exited with code=1"], "stop")
		self.assertEqual(color["ld.exe: cannot open output file score.exe: Permission denied"], "stop")


class TestCompileState(unittest.TestCase):
	"""編譯時照書寫順序推演當下狀態：指到當下不存在的位置，執行期只會安靜地不畫"""

	def compile(self, do, **obj):
		def edit(doc):
			doc["objects"][0].update({"files": {"a.c": ["x"] * 10, "b.c": ["y", "z"]}, "open": "a.c"}, **obj)
			doc["scenes"][0]["beats"][0]["do"] = [{"act": "show", "target": "vs"}] + do
		return compiled("vscode_min", edit)

	def test_換檔後標的行要在當下開著的檔(self):
		self.compile([{"act": "circle", "target": "vs:L5"}])
		with self.assertRaisesRegex(ValueError, "b.c 只有 2 行"):
			self.compile([{"act": "open", "target": "vs", "file": "b.c"}, {"act": "circle", "target": "vs:L5"}])

	def test_highlight沒寫file就用當下開著的檔(self):
		with self.assertRaisesRegex(ValueError, "lines 超出行數"):
			self.compile([{"act": "open", "target": "vs", "file": "b.c"}, {"act": "highlight", "target": "vs", "lines": [5]}])
		with self.assertRaisesRegex(ValueError, "不在 files"):
			self.compile([{"act": "highlight", "target": "vs", "file": "nope.c", "lines": [1]}])

	def test_P只到面板當下印出的行(self):
		run = {"act": "run", "target": "vs", "output": ["[Running] a", "b"]}
		self.compile([run, {"act": "circle", "target": "vs:P2"}])
		with self.assertRaisesRegex(ValueError, "只有 2 行"):
			self.compile([run, {"act": "circle", "target": "vs:P3"}])
		with self.assertRaisesRegex(ValueError, "只有 0 行"):
			self.compile([run, {"act": "panel", "target": "vs", "name": "terminal"}, {"act": "circle", "target": "vs:P1"}])

	def test_選單項目只在選單開著時能指(self):
		click = {"act": "click", "target": "cursor", "on": "vs:settings"}
		self.compile([{"act": "menu", "target": "vs", "name": "gear"}, click], menus=["gear"], pages=["settings"])
		with self.assertRaisesRegex(ValueError, "沒開 gear 選單"):
			self.compile([click], menus=["gear"])
		with self.assertRaisesRegex(ValueError, "沒開 gear 選單"):
			self.compile([{"act": "menu", "target": "vs", "name": "gear"}, {"act": "page", "target": "vs", "name": "settings"}, click], menus=["gear"], pages=["settings"])
		with self.assertRaisesRegex(ValueError, "設定頁沒開"):
			self.compile([{"act": "click", "target": "cursor", "on": "vs:settings:search"}])


class TestChalkAdapter(unittest.TestCase):
	def test_黑板轉接的動作時間取自逐字時間(self):
		if not NODE:
			self.skipTest("沒有 node")
		screen = {"lines": [2, 3], "screen": {"id": "vs"}, "do": {
			"2": [{"act": "circle", "target": "vs:run", "obj": "vs", "args": {"tone": "warn"}, "n": None, "cue": "三角形", "dur": 0.7},
				{"act": "run", "target": "vs", "obj": "vs", "args": {"output": ["x"]}, "n": None, "cue": None, "dur": 0.8, "blocks": True},
				{"act": "input", "target": "vs", "obj": "vs", "args": {"text": "85"}, "n": 2, "cue": None, "dur": 0.24, "blocks": True}],
		}}
		with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
			json.dump({"screen": screen, "spans": {"2": {"三角形": [2.0, 2.4]}}, "starts": {"2": 1.0, "3": 5.0}}, f, ensure_ascii=False)
		try:
			r = subprocess.run([NODE, PROBE, "schedule", f.name], capture_output=True, text=True, timeout=30)
		finally:
			os.unlink(f.name)
		self.assertEqual(r.returncode, 0, r.stderr)
		acts = json.loads(r.stdout)
		circle, run, inp = acts
		self.assertEqual((circle["t0"], circle["t1"]), (2.0, 2.7))
		self.assertEqual(circle["line"], 2)
		# 沒寫 cue 的動作從開始畫的時刻起跑，會擋路的動作一個接一個
		self.assertEqual((run["t0"], run["t1"]), (1.0, 1.8))
		self.assertAlmostEqual(inp["t0"], 1.8)
		self.assertAlmostEqual(inp["t1"], 2.04)

	def screen(self, do):
		"""走分鏡的真流程（storyboard 交給手帳編譯器）做出一段電腦畫面，動作都不寫 cue、一個接一個"""
		pg = {"screen": {"id": "vs", "files": {"a.c": ["int main(void) {", "}"]}, "menus": ["gear"], "pages": ["settings"]},
			"lines": [{"say": "點齒輪再點設定。", "do": do}]}
		obj, acts = SB.screen_actions(pg, 1)
		return {"lines": [1], "screen": obj, "do": acts}

	def chalk(self, cmd, screen, ts=None, spans=None):
		return probe(cmd, None, None, ts, screen=screen, spans={"1": spans or {}}, starts={"1": 0.0})

	def test_選單關掉後游標照樣走到下一個目標(self):
		scr = self.screen([{"act": "click", "target": "cursor", "on": "vs:gear"}, {"act": "menu", "target": "vs", "name": "gear"},
			{"act": "click", "target": "cursor", "on": "vs:settings"}, {"act": "page", "target": "vs", "name": "settings"},
			{"act": "click", "target": "cursor", "on": "vs:settings:search"}])
		end = 20.0
		got = self.chalk("cursor", scr, ts=[end])
		own = [a for a in got["acts"] if a["obj"] == "vs"]
		box = probe("anchors", scr["screen"], own, [end])[0]["settings:search"]
		p = got["pts"][0]["p"]
		# 舊版每格重查：設定頁打開後 vs:settings 沒有框，游標就停在齒輪上
		self.assertAlmostEqual(p[0], box["x"] + box["w"] / 2, delta=1)
		self.assertAlmostEqual(p[1], box["y"] + box["h"] / 2, delta=1)

	def test_時間軸錨點閘擋下選單沒開就點選單項目(self):
		ok = self.screen([{"act": "menu", "target": "vs", "name": "gear"}, {"act": "click", "target": "cursor", "on": "vs:settings"}])
		self.assertEqual(self.chalk("check", ok), [])
		# 編譯照書寫順序看是「選單開了才圈」，但圈跟著 cue 提早到開口時，選單要等點完齒輪才開：只有照時間排才看得出來
		bad = self.screen([{"act": "click", "target": "cursor", "on": "vs:gear"}, {"act": "menu", "target": "vs", "name": "gear"},
			{"act": "circle", "target": "vs:settings", "cue": "點齒輪"}])
		problems = self.chalk("check", bad, spans={"點齒輪": [0.0, 0.3]})
		self.assertTrue(problems and all("vs:settings" in s for s in problems), problems)

	def test_printf片的電腦畫面錨點都量得到(self):
		if not NODE:
			self.skipTest("沒有 node")
		r = subprocess.run([NODE, os.path.join(ROOT, "video_engine", "explainer", "chalk", "screen_check.js"),
			os.path.join(ROOT, "video_engine", "out", "vscode_printf_chalk")], capture_output=True, text=True, timeout=60)
		self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
	unittest.main()
