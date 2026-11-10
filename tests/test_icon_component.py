"""圖示元件改動前的基準：VS Code 元件的動作與錨點、printf 分鏡的產物，皆為純資料，不比 PNG。
重新產生基準（只在確定行為本來就該變時）：.venv/bin/python tests/test_icon_component.py --regen"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
from test_vscode_component import BC, SB, probe as _probe  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "icon_baseline")
SCENES = ("vscode_full", "vscode_tip")
STORY = os.path.join(ROOT, "docs", "experiments", "2026-10-22-vscode-printf", "video", "chalk-story")


def scene_actions(name):
	with open(os.path.join(ROOT, "video_engine", "board", "fixtures", name + ".scene.json"), encoding="utf-8") as f:
		doc = json.load(f)
	tl = BC.compile_scene(doc, None, BC.load_catalog())
	acts = [{k: v for k, v in a.items() if k != "spec"} for a in tl["actions"]]
	return tl, acts


def probe(*a, **kw):
	# 基準不准因為缺 node 而略過，原版 probe 會 skip
	try:
		return _probe(*a, **kw)
	except unittest.SkipTest:
		raise AssertionError("缺 node：圖示基準需要 node 跑 VS Code 元件的 state／anchors，請安裝 node 22")


def vscode_compiled():
	return {name: {"actions": scene_actions(name)[1]} for name in SCENES}


def vscode_probed():
	out = {"vscode_tip": {}}
	# tip 動作中點的 state／anchors
	tl, _ = scene_actions("vscode_tip")
	desc = tl["objects"]["vs"]
	vs = [a for a in tl["actions"] if a["obj"] == "vs"]
	tip = [a for a in vs if a["act"] == "tip"][0]
	ts = [(tip["t0"] + tip["t1"]) / 2, tip["t1"] - 0.001]
	out["vscode_tip"]["probe_ts"] = ts
	out["vscode_tip"]["state"] = probe("state", desc, vs, ts)
	out["vscode_tip"]["anchors"] = probe("anchors", desc, vs, ts)
	return out


def vscode_actions():
	out = vscode_compiled()
	out["vscode_tip"].update(vscode_probed()["vscode_tip"])
	return out


def printf_files():
	with open(os.path.join(STORY, "storyboard.json"), encoding="utf-8") as f:
		return SB.build(json.load(f))


def printf_screens():
	return json.loads(printf_files()["screens.json"])


def printf_storyboard_out():
	return {n: hashlib.md5(t.encode("utf-8")).hexdigest() for n, t in sorted(printf_files().items())}


GEN = {"vscode_actions.json": vscode_actions, "printf_screens.json": printf_screens,
	"printf_storyboard_out.json": printf_storyboard_out}


def load(name):
	with open(os.path.join(FIX, name), encoding="utf-8") as f:
		return json.load(f)


def norm(o):
	return json.loads(json.dumps(o, ensure_ascii=False))


class TestBaseline(unittest.TestCase):
	def test_vscode_編譯後動作不變(self):
		want = load("vscode_actions.json")
		got = norm(vscode_compiled())
		for name in SCENES:
			self.assertEqual(got[name]["actions"], want[name]["actions"], name)

	def test_vscode_tip_state與錨點不變(self):
		want = load("vscode_actions.json")["vscode_tip"]
		got = norm(vscode_probed())["vscode_tip"]
		for k in ("probe_ts", "state", "anchors"):
			self.assertEqual(got[k], want[k], k)

	def test_printf_screens_不變(self):
		self.assertEqual(norm(printf_screens()), load("printf_screens.json"))

	def test_printf_分鏡產物不變(self):
		self.assertEqual(printf_storyboard_out(), load("printf_storyboard_out.json"))

ICON_PROBE = os.path.join(ROOT, "tests", "js", "icon_probe.js")
NAMES = ["keyboard", "cross", "checklist", "branch", "bulb", "warning", "scale", "pencil", "loop", "question",
	"check", "play", "stop", "return", "file", "chat", "clock", "person", "hourglass", "tangle", "magnifier",
	"lock", "gear", "keycap", "mic", "headphones", "wave", "quote", "heart", "coin", "phone"]


def icon_probe(cmd, **q):
	node = shutil.which("node")
	if not node:
		raise AssertionError("缺 node：圖示形狀測試需要 node，請安裝 node 22")
	with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
		json.dump(q, f, ensure_ascii=False)
	try:
		r = subprocess.run([node, ICON_PROBE, cmd, f.name], capture_output=True, text=True, timeout=30)
	finally:
		os.unlink(f.name)
	if r.returncode:
		raise AssertionError(r.stderr)
	return json.loads(r.stdout)


class TestShapes(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.all = icon_probe("all")

	def test_名稱清單(self):
		names = icon_probe("names")
		self.assertEqual(len(names), 31)
		self.assertEqual(len(set(names)), 31)
		self.assertEqual(names, NAMES)

	def test_筆畫都在格子內(self):
		for n, r in self.all.items():
			for s in r["strokes"]:
				for x, y in s["pts"]:
					self.assertTrue(8 <= x <= 92 and 8 <= y <= 92, (n, s["part"], x, y))

	def test_筆畫格式(self):
		for n, r in self.all.items():
			st = r["strokes"]
			self.assertTrue(2 <= len(st) <= 12, (n, len(st)))
			self.assertEqual(st[0]["w"], "main", n)
			for s in st:
				self.assertGreaterEqual(len(s["pts"]), 2, n)
				self.assertIn(s["w"], ("main", "detail"), n)
				self.assertIsInstance(s["arc"], bool, n)
				self.assertTrue(isinstance(s["part"], str) and s["part"], n)
			self.assertEqual(icon_probe("count", name=n, opts={"text": "Ctrl"}), len(st), n)

	def test_弧線有取樣(self):
		for n, r in self.all.items():
			for s in r["strokes"]:
				if not s["arc"]:
					continue
				p = s["pts"]
				for a, b in zip(p, p[1:]):
					self.assertLessEqual(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5, 6.0001, (n, s["part"]))

	def test_決定性(self):
		for n in NAMES:
			o = {"text": "Ctrl"} if n == "keycap" else None
			self.assertEqual(icon_probe("strokes", name=n, opts=o), icon_probe("strokes", name=n, opts=o), n)

	def test_keycap_帶字(self):
		one = icon_probe("strokes", name="keycap", opts={"text": "Ctrl"})
		self.assertEqual(one["text"], "Ctrl")
		self.assertNotIn("w", one)
		# 組合鍵：每顆鍵帽一組筆畫、中間一個加號，整體比 100 寬；單顆的筆畫原封不動排在最前面
		combo = icon_probe("strokes", name="keycap", opts={"text": "Ctrl+Alt+M"})
		self.assertEqual([t["text"] for t in combo["texts"]], ["Ctrl", "Alt", "M"])
		self.assertNotIn("text", combo)
		self.assertEqual(len(combo["strokes"]), 3 * len(one["strokes"]) + 2 * 2)
		self.assertEqual(combo["strokes"][:len(one["strokes"])], one["strokes"])
		xs = [p[0] for s in combo["strokes"] for p in s["pts"]]
		self.assertTrue(0 <= min(xs) and max(xs) <= combo["w"] and combo["w"] > 300, (min(xs), max(xs), combo["w"]))
		self.assertEqual([t["cx"] for t in combo["texts"]], sorted(t["cx"] for t in combo["texts"]))
		for bad in ("Ctrl+", "+C", "A++B"):
			with self.assertRaises(AssertionError):
				icon_probe("strokes", name="keycap", opts={"text": bad})
		for bad in (None, {}, {"text": ""}):
			with self.assertRaises(AssertionError):
				icon_probe("strokes", name="keycap", opts=bad)

	def test_未知名稱(self):
		with self.assertRaises(AssertionError):
			icon_probe("strokes", name="nope")


class TestCatalog(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.cat = BC.load_catalog()
		cls.spec = cls.cat["types"]["icon"]

	def scene(self, **icon):
		objects = [{"id": "i", "type": "icon", **icon}]
		return {"version": 1, "id": "t", "objects": objects, "scenes": [{"id": "s", "layout": {"stack": ["i"]},
			"beats": [{"say": "好", "do": [{"act": "show", "target": "i"}]}]}]}

	def compile(self, **icon):
		return BC.compile_scene(self.scene(**icon), None, self.cat)

	def test_目錄筆畫數與形狀一致(self):
		self.assertEqual(self.spec["names"], NAMES)
		self.assertEqual(sorted(self.spec["strokes"]), sorted(NAMES))
		for n in NAMES:
			self.assertEqual(self.spec["strokes"][n], icon_probe("count", name=n, opts={"text": "Ctrl"}), n)

	def test_意思解析(self):
		tl = self.compile(name="唯讀")
		self.assertEqual(tl["objects"]["i"]["name"], "lock")
		self.assertEqual(tl["objects"]["i"]["_asked"], "唯讀")
		self.assertEqual(self.compile(name="lock")["objects"]["i"]["name"], "lock")

	def test_對不到意思要報錯(self):
		with self.assertRaises(ValueError) as cm:
			self.compile(name="等一下")
		self.assertIn("等待", str(cm.exception))
		self.assertIn("等一下", str(cm.exception))

	def test_最接近排序(self):
		means = [m for ms in self.spec["means"].values() for m in ms]
		self.assertIn("等待", BC.nearest_means("等一下", means))
		self.assertIn("錯誤", BC.nearest_means("錯了", means))
		self.assertEqual(len(BC.nearest_means("等一下", means)), 3)

	def test_重複意思載入就失敗(self):
		bad = json.loads(json.dumps(self.cat))
		bad["types"]["icon"]["means"]["clock"].append("等待")
		with self.assertRaises(ValueError) as cm:
			BC.check_icon_catalog(bad)
		for w in ("等待", "hourglass", "clock"):
			self.assertIn(w, str(cm.exception))

	def test_意思等於別的圖示名稱也算重複(self):
		bad = json.loads(json.dumps(self.cat))
		bad["types"]["icon"]["means"]["clock"].append("lock")
		with self.assertRaises(ValueError) as cm:
			BC.check_icon_catalog(bad)
		self.assertIn("lock", str(cm.exception))

	def test_means的鍵要等於names(self):
		bad = json.loads(json.dumps(self.cat))
		del bad["types"]["icon"]["means"]["coin"]
		with self.assertRaises(ValueError) as cm:
			BC.check_icon_catalog(bad)
		self.assertIn("coin", str(cm.exception))

	def test_keycap_缺字(self):
		with self.assertRaises(ValueError) as cm:
			self.compile(name="keycap")
		self.assertIn("text", str(cm.exception))
		self.assertEqual(self.compile(name="keycap", text="Ctrl")["objects"]["i"]["name"], "keycap")

	def test_size與tone要合法(self):
		with self.assertRaises(ValueError) as cm:
			self.compile(name="lock", size="xl")
		self.assertIn("size", str(cm.exception))
		with self.assertRaises(ValueError) as cm:
			self.compile(name="lock", tone="red")
		self.assertIn("tone", str(cm.exception))
		self.compile(name="lock", size="l", tone="warn")

	def test_既有fixture的gear還能編(self):
		self.assertEqual(self.compile(name="gear")["objects"]["i"]["name"], "gear")


class TestActions(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.cat = BC.load_catalog()

	def compile(self, beats, icons=("a",), names=None, scenes=None):
		names = names or {}
		objects = [{"id": i, "type": "icon", "name": names.get(i, "keyboard")} for i in icons]
		scenes = scenes or [{"id": "s", "layout": {"stack": list(icons)}, "beats": beats}]
		doc = {"version": 1, "id": "t", "objects": objects, "scenes": scenes}
		return BC.compile_scene(doc, None, self.cat)

	def acts(self, tl, act, obj=None):
		return [a for a in tl["actions"] if a["act"] == act and (obj is None or a["obj"] == obj)]

	def scene_end(self, tl, scene=0):
		return [b for b in tl["beats"] if b["scene"] == scene][-1]["t1"] - BC.END_MARGIN

	def test_draw_時長依筆畫(self):
		strokes = self.cat["types"]["icon"]["strokes"]
		tl = self.compile([{"say": "先畫一個勾，再畫一個鍵盤，這句話要夠長才不會被句尾夾住", "do": [
			{"act": "draw", "target": "c"}, {"act": "draw", "target": "k"}]}],
			icons=("c", "k"), names={"c": "check", "k": "keyboard"})
		c, k = self.acts(tl, "draw", "c")[0], self.acts(tl, "draw", "k")[0]
		self.assertAlmostEqual(c["t1"] - c["t0"], 0.5)
		self.assertAlmostEqual(k["t1"] - k["t0"], min(strokes["keyboard"] * 0.12, 1.6))
		self.assertAlmostEqual(k["t0"], c["t1"])

	def test_blink_until(self):
		beats = [{"say": "鍵盤在這裡一直閃", "do": [{"act": "draw", "target": "a"}, {"act": "blink", "target": "a", "until": "停下來"}]},
			{"say": "等到我說停下來為止", "do": []}]
		tl = self.compile(beats)
		b = self.acts(tl, "blink")[0]
		second = tl["beats"][1]
		self.assertTrue(second["t0"] < b["t1"] < second["t1"], (b["t1"], second))
		want = second["t0"] + (second["t1"] - second["t0"]) * second["say"].index("停下來") / len(second["say"])
		self.assertAlmostEqual(b["t1"], want)
		self.assertEqual(b["args"]["until_beat"], 1)
		self.assertEqual(b["args"]["until"], "停下來")
		beats[0]["do"][1].pop("until")
		tl = self.compile(beats)
		self.assertAlmostEqual(self.acts(tl, "blink")[0]["t1"], self.scene_end(tl))

	def test_blink後面的動作不被拖住(self):
		tl = self.compile([{"say": "先畫鍵盤讓它閃，接著再畫第二個鍵盤出來，這句也要夠長", "do": [
			{"act": "draw", "target": "a"}, {"act": "blink", "target": "a"}, {"act": "draw", "target": "b"}]}],
			icons=("a", "b"))
		da, bl, db = self.acts(tl, "draw", "a")[0], self.acts(tl, "blink")[0], self.acts(tl, "draw", "b")[0]
		self.assertAlmostEqual(db["t0"], da["t1"])
		self.assertNotAlmostEqual(db["t0"], self.scene_end(tl))
		self.assertAlmostEqual(bl["t1"], self.scene_end(tl))

	def test_with_prev接在blink後面跟著blink起跑(self):
		tl = self.compile([{"say": "先畫鍵盤讓它閃，同時畫第二個鍵盤出來，這句也要夠長", "do": [
			{"act": "draw", "target": "a"}, {"act": "blink", "target": "a"}, {"act": "draw", "target": "b", "with": "prev"}]}],
			icons=("a", "b"))
		self.assertAlmostEqual(self.acts(tl, "draw", "b")[0]["t0"], self.acts(tl, "blink")[0]["t0"])

	def test_until_不在這場(self):
		def doc(word, where):
			first = {"say": "鍵盤一直閃", "do": [{"act": "draw", "target": "a"}]}
			blink = {"act": "blink", "target": "a", "until": word}
			second = {"say": "第二句在這裡", "do": []}
			if where == "first":
				first["do"].append(blink)
			else:
				second["do"] = [blink]
			return [first, second]
		with self.assertRaises(ValueError) as cm:
			self.compile(doc("不存在的字", "first"))
		self.assertIn("不存在的字", str(cm.exception))
		self.assertIn("until", str(cm.exception))
		# 寫成上一句的字
		with self.assertRaises(ValueError) as cm:
			self.compile(doc("一直閃", "second"))
		self.assertIn("一直閃", str(cm.exception))
		self.assertIn("until", str(cm.exception))
		# 同一句自己的字也不行，要在這句之後
		with self.assertRaises(ValueError) as cm:
			self.compile(doc("鍵盤", "first"))
		self.assertIn("until", str(cm.exception))
		# 下一場的字也不行
		scenes = [{"id": "s1", "layout": {"stack": ["a"]}, "beats": [{"say": "鍵盤一直閃", "do": [
			{"act": "draw", "target": "a"}, {"act": "blink", "target": "a", "until": "下一場"}]}]},
			{"id": "s2", "layout": {"stack": ["a"]}, "beats": [{"say": "這是下一場", "do": []}]}]
		with self.assertRaises(ValueError) as cm:
			self.compile(None, scenes=scenes)
		self.assertIn("下一場", str(cm.exception))

	def test_第一個動作要是draw(self):
		for first in ("blink", "erase"):
			with self.assertRaises(ValueError) as cm:
				self.compile([{"say": "鍵盤", "do": [{"act": first, "target": "a"}]}])
			self.assertIn("先 draw", str(cm.exception))
		# 跨句也算：第一句畫 a，第二句才第一次動 b 就 blink
		with self.assertRaises(ValueError) as cm:
			self.compile([{"say": "畫鍵盤", "do": [{"act": "draw", "target": "a"}]},
				{"say": "另一個閃", "do": [{"act": "blink", "target": "b"}]}], icons=("a", "b"))
		self.assertIn("先 draw", str(cm.exception))
		self.compile([{"say": "鍵盤", "do": [{"act": "show", "target": "a"}, {"act": "blink", "target": "a"}]}])
		self.compile([{"say": "鍵盤", "do": [{"act": "draw", "target": "a"}, {"act": "erase", "target": "a"}]}])


CALLOUT_PROBE = os.path.join(ROOT, "tests", "js", "callout_probe.js")
PW_PY = os.path.expanduser("~/.local/share/pipx/venvs/webwright/bin/python")
CHECK = os.path.join(ROOT, "video_engine", "board", "check.py")


def callout_probe(cmd, **q):
	node = shutil.which("node")
	if not node:
		raise AssertionError("缺 node：標註框測試需要 node，請安裝 node 22")
	with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
		json.dump(q, f, ensure_ascii=False)
	try:
		r = subprocess.run([node, CALLOUT_PROBE, cmd, f.name], capture_output=True, text=True, timeout=30)
	finally:
		os.unlink(f.name)
	if r.returncode:
		raise AssertionError(r.stderr)
	return json.loads(r.stdout)


def board_check(case, name):
	"""分鏡 → compile → build → check.py；沒瀏覽器時 skip，但 E2E_GEOM=1 必須真的跑（不准檢查自己壞掉卻顯示通過）"""
	import build as BB
	strict = os.environ.get("E2E_GEOM") == "1"
	if not os.path.exists(PW_PY):
		if strict:
			case.fail("E2E_GEOM=1 但沒有 webwright 的 Playwright：" + PW_PY)
		case.skipTest("沒有 webwright 的 Playwright")
	with open(os.path.join(ROOT, "video_engine", "board", "fixtures", name + ".scene.json"), encoding="utf-8") as f:
		doc = json.load(f)
	tl = BC.compile_scene(doc, None, BC.load_catalog())
	with tempfile.TemporaryDirectory() as d:
		BB.build(tl, d)
		r = subprocess.run([PW_PY, CHECK, d], capture_output=True, text=True, timeout=600)
		report = os.path.join(d, "check.json")
		if not os.path.exists(report):
			if not strict and "Executable doesn't exist" in r.stderr:
				case.skipTest("Playwright 沒裝 chromium")
			case.fail("量測閘沒有跑完：" + r.stderr[-600:])
		with open(report, encoding="utf-8") as f:
			return r.returncode, r.stdout, json.load(f)


class TestCallout(unittest.TestCase):
	SIZE = {"w": 200, "h": 48, "f": 1}

	def place(self, anchor, bounds, obstacles=(), size=None):
		return callout_probe("place", anchor=anchor, size=size or self.SIZE, bounds=bounds, obstacles=list(obstacles))

	def test_常數照抄vscode(self):
		self.assertEqual(callout_probe("consts"), {"PAD": 22, "ARROW": 16})

	def test_size(self):
		s = callout_probe("size", text="abcd", charW=10, style={"size": 22})
		self.assertEqual((s["w"], s["h"]), (40 + 44, 48))
		s = callout_probe("size", text="abcd", charW=10, style={"size": 44})
		self.assertEqual((s["w"], s["h"]), (40 + 88, 96))

	def test_place_四邊(self):
		wide = {"x": 0, "y": 0, "w": 1000, "h": 600}
		mid = {"x": 400, "y": 280, "w": 100, "h": 40}
		p = self.place(mid, wide)
		self.assertEqual(p["side"], "right")
		self.assertGreaterEqual(p["box"]["x"], mid["x"] + mid["w"])
		self.assertTrue(mid["x"] + mid["w"] <= p["tip"][0] <= p["box"]["x"])
		# 錨點貼著右緣：右邊放不下，換左
		edge = {"x": 900, "y": 280, "w": 100, "h": 40}
		p = self.place(edge, wide)
		self.assertEqual(p["side"], "left")
		self.assertLessEqual(p["box"]["x"] + p["box"]["w"], edge["x"])
		self.assertTrue(p["box"]["x"] + p["box"]["w"] <= p["tip"][0] <= edge["x"])
		# 很窄：左右都放不下，換上
		narrow = {"x": 0, "y": 0, "w": 300, "h": 600}
		a = {"x": 100, "y": 280, "w": 100, "h": 40}
		p = self.place(a, narrow)
		self.assertEqual(p["side"], "top")
		self.assertLessEqual(p["box"]["y"] + p["box"]["h"], a["y"])
		self.assertTrue(p["box"]["y"] + p["box"]["h"] <= p["tip"][1] <= a["y"])
		above = {"x": 0, "y": 0, "w": 300, "h": 270}
		below = {"x": 0, "y": 330, "w": 300, "h": 270}
		self.assertEqual(self.place(a, narrow, [above])["side"], "bottom")
		# 右邊被擋：換左
		self.assertEqual(self.place(mid, wide, [{"x": 520, "y": 200, "w": 400, "h": 200}])["side"], "left")
		# 四邊都塞住
		self.assertIsNone(self.place(a, narrow, [above, below]))
		for p in (self.place(mid, wide), self.place(edge, wide), self.place(a, narrow)):
			b = p["box"]
			self.assertTrue(b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["w"] <= 1000 and b["y"] + b["h"] <= 600, p)

	def test_place_貼邊時沿邊滑進來(self):
		bounds = {"x": 0, "y": 0, "w": 1000, "h": 600}
		a = {"x": 10, "y": 280, "w": 60, "h": 40}
		p = self.place(a, bounds, [{"x": 100, "y": 250, "w": 800, "h": 100}])
		self.assertEqual(p["side"], "top")
		self.assertEqual(p["box"]["x"], 0)
		self.assertTrue(p["box"]["x"] < p["tip"][0] < p["box"]["x"] + p["box"]["w"])
		self.assertEqual(p["tip"][0], 40)

	def test_endTime(self):
		acts = [{"act": "callout", "obj": "a", "t0": 1.0}, {"act": "draw", "obj": "b", "t0": 2.0},
			{"act": "blink", "obj": "a", "t0": 3.0}]
		self.assertEqual(callout_probe("endTime", acts=acts, i=0, untilT=None, sceneEnd=10.0), 3.0)
		self.assertEqual(callout_probe("endTime", acts=acts, i=0, untilT=5.0, sceneEnd=10.0), 5.0)
		self.assertEqual(callout_probe("endTime", acts=acts, i=0, untilT=None, sceneEnd=2.5), 2.5)
		self.assertEqual(callout_probe("endTime", acts=acts[:2], i=0, untilT=None, sceneEnd=10.0), 10.0)
		# 同時起跑的（with: prev）不算「下一個」
		same = [acts[0], {"act": "circle", "obj": "a", "t0": 1.0}, acts[2]]
		self.assertEqual(callout_probe("endTime", acts=same, i=0, untilT=None, sceneEnd=10.0), 3.0)

	def compile(self, beats, icons=("a", "b")):
		objects = [{"id": i, "type": "icon", "name": "keyboard"} for i in icons]
		doc = {"version": 1, "id": "t", "objects": objects, "scenes": [{"id": "s", "layout": {"row": list(icons)}, "beats": beats}]}
		return BC.compile_scene(doc, None, BC.load_catalog())

	def test_目錄(self):
		self.assertEqual(BC.load_catalog()["generic_actions"]["callout"],
			{"dur": 0.3, "req": ["text"], "opt": ["tone", "until"], "blocks": True})

	def test_編譯_until與不當prev(self):
		beats = [{"say": "先畫鍵盤，旁邊掛一個提示，再畫第二個鍵盤，這句話要夠長", "do": [
			{"act": "draw", "target": "a"}, {"act": "callout", "target": "a", "text": "輸入", "until": "收起來"},
			{"act": "draw", "target": "b"}]},
			{"say": "講到這裡提示就收起來", "do": []}]
		tl = self.compile(beats)
		da, co, db = [a for a in tl["actions"] if a["act"] in ("draw", "callout")]
		self.assertAlmostEqual(co["t1"] - co["t0"], 0.3)
		self.assertAlmostEqual(db["t0"], da["t1"])
		self.assertEqual(co["args"]["until_beat"], 1)
		second = tl["beats"][1]
		want = second["t0"] + (second["t1"] - second["t0"]) * second["say"].index("收起來") / len(second["say"])
		self.assertAlmostEqual(co["args"]["until_t"], want)
		beats[0]["do"][1].pop("until")
		self.assertNotIn("until_t", [a for a in self.compile(beats)["actions"] if a["act"] == "callout"][0]["args"])
		bad = json.loads(json.dumps(beats))
		bad[0]["do"][1]["until"] = "不存在的字"
		with self.assertRaises(ValueError) as cm:
			self.compile(bad)
		self.assertIn("until", str(cm.exception))
		bad[0]["do"][1].pop("until")
		bad[0]["do"][1]["tone"] = "red"
		with self.assertRaises(ValueError) as cm:
			self.compile(bad)
		self.assertIn("red", str(cm.exception))
		bad[0]["do"][1].pop("tone")
		bad[0]["do"][1].pop("text")
		with self.assertRaises(ValueError) as cm:
			self.compile(bad)
		self.assertIn("text", str(cm.exception))

	def test_callout_邊緣_過閘(self):
		code, out, report = board_check(self, "callout_edges")
		self.assertEqual(code, 0, out + json.dumps(report["problems"], ensure_ascii=False))
		self.assertTrue(report["ok"])

	def test_callout_塞不下要失敗(self):
		code, out, report = board_check(self, "callout_full")
		self.assertEqual(code, 1, out)
		self.assertTrue(any("四邊都放不下" in p for p in report["problems"]), report["problems"])


EXPORT = os.path.join(ROOT, "video_engine", "components", "icon", "export_png.py")
BOXES = """
import json, os, sys
sys.path.insert(0, os.path.join(%r, "video_engine", "board"))
from playwright.sync_api import sync_playwright
d, times = sys.argv[1], json.loads(sys.argv[2])
out = {}
with sync_playwright() as p:
	b = p.chromium.launch()
	pg = b.new_page(viewport={"width": 1920, "height": 1080})
	pg.goto("file://" + os.path.join(d, "player.html") + "?export")
	pg.wait_for_function("window.boardReady === true", timeout=60000)
	for oid, t, cap in times:
		info = pg.evaluate("t => board.seek(t)", t)
		out[oid] = {"panel": [x for x in info["boxes"] if x["owner"] == oid and x["role"] == "panel"],
			"caption": pg.evaluate("([g, t]) => board.anchor(g, t)", [oid + ":caption", t]) if cap else None}
	b.close()
print(json.dumps(out))
""" % ROOT


def need_browser(case):
	strict = os.environ.get("E2E_GEOM") == "1"
	if not os.path.exists(PW_PY):
		if strict:
			case.fail("E2E_GEOM=1 但沒有 webwright 的 Playwright：" + PW_PY)
		case.skipTest("沒有 webwright 的 Playwright")


def load_scene(name):
	with open(os.path.join(ROOT, "video_engine", "board", "fixtures", name + ".scene.json"), encoding="utf-8") as f:
		return json.load(f)


class TestSkins(unittest.TestCase):
	def test_icon_full_涵蓋全部圖示與動作(self):
		doc = load_scene("icon_full")
		icons = [o for o in doc["objects"] if o["type"] == "icon"]
		tl = BC.compile_scene(doc, None, BC.load_catalog())
		self.assertEqual(sorted(tl["objects"][o["id"]]["name"] for o in icons), sorted(NAMES))
		acts = {a["act"] for a in tl["actions"]}
		self.assertTrue({"draw", "blink", "erase", "callout"} <= acts, acts)
		self.assertTrue(any(o.get("caption") for o in icons))
		self.assertTrue(any(tl["objects"][o["id"]]["name"] == "keycap" for o in icons))

	def test_icon_sheet_三十一格(self):
		doc = load_scene("icon_sheet")
		tl = BC.compile_scene(doc, None, BC.load_catalog())
		icons = [o for o in tl["objects"].values() if o["type"] == "icon"]
		self.assertEqual(sorted(o["name"] for o in icons), sorted(NAMES))
		self.assertTrue(all(o.get("caption") for o in icons))

	def test_每個圖示都有框(self):
		need_browser(self)
		import build as BB
		doc = load_scene("icon_full")
		tl = BC.compile_scene(doc, None, BC.load_catalog())
		times = []
		for o in doc["objects"]:
			if o["type"] != "icon":
				continue
			first = [a for a in tl["actions"] if a["obj"] == o["id"] and a["act"] in ("draw", "show")][0]
			times.append([o["id"], first["t1"] + 0.05, bool(o.get("caption"))])
		with tempfile.TemporaryDirectory() as d:
			BB.build(tl, d)
			r = subprocess.run([PW_PY, "-c", BOXES, d, json.dumps(times)], capture_output=True, text=True, timeout=300)
			self.assertEqual(r.returncode, 0, r.stderr[-800:])
		got = json.loads(r.stdout)
		for oid, _, cap in times:
			self.assertTrue(got[oid]["panel"], oid + " 沒有 panel 框")
			if cap:
				self.assertIsNotNone(got[oid]["caption"], oid + " 沒有 :caption 框")
			else:
				self.assertIsNone(got[oid]["caption"], oid)

	def test_icon_full_過量測閘(self):
		code, out, report = board_check(self, "icon_full")
		self.assertEqual(code, 0, out + json.dumps(report["problems"], ensure_ascii=False))
		self.assertTrue(report["ok"])

	def test_icon_sheet_過量測閘(self):
		code, out, report = board_check(self, "icon_sheet")
		self.assertEqual(code, 0, out + json.dumps(report["problems"], ensure_ascii=False))

	def test_svg_格式(self):
		svg = icon_probe("svg", name="keycap", opts={"text": "Ctrl"}, color="var(--ink)", px=64)
		for want in ('stroke-linecap="round"', 'stroke-linejoin="round"', 'stroke="var(--ink)"', 'width="64"', ">Ctrl<"):
			self.assertIn(want, svg)
		self.assertEqual(svg, icon_probe("svg", name="keycap", opts={"text": "Ctrl"}, color="var(--ink)", px=64))
		for n in NAMES:
			self.assertTrue(icon_probe("svg", name=n, opts={"text": "Ctrl"}, color="red", px=32).startswith("<svg"), n)

	def test_svg_決定性(self):
		need_browser(self)
		with tempfile.TemporaryDirectory() as d:
			sums = []
			for i in range(2):
				out = os.path.join(d, f"s{i}.png")
				r = subprocess.run([PW_PY, EXPORT, out, "--sheet", "--skin", "flat"], capture_output=True, text=True, timeout=300)
				self.assertEqual(r.returncode, 0, r.stderr[-800:])
				with open(out, "rb") as f:
					sums.append(hashlib.md5(f.read()).hexdigest())
			self.assertEqual(sums[0], sums[1])

	def test_不寫色碼(self):
		import re
		for rel in ("components/icon/svg.js", "components/icon/shapes.js", "board/runtime/components/icon.js"):
			with open(os.path.join(ROOT, "video_engine", rel), encoding="utf-8") as f:
				self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,6}\b", f.read()), rel)


CHALK_PROBE = os.path.join(ROOT, "tests", "js", "chalk_probe.js")
CHALK_KIT = os.path.join(ROOT, "video_engine", "explainer", "chalk", "kit")


def chalk_probe(cmd, **q):
	node = shutil.which("node")
	if not node:
		raise AssertionError("缺 node：粉筆皮膚測試需要 node，請安裝 node 22")
	with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
		json.dump(q, f, ensure_ascii=False)
	try:
		r = subprocess.run([node, CHALK_PROBE, cmd, f.name], capture_output=True, text=True, timeout=30)
	finally:
		os.unlink(f.name)
	if r.returncode:
		raise AssertionError(r.stderr)
	return json.loads(r.stdout)


class TestChalk(unittest.TestCase):
	BOX = {"x": 40, "y": 60, "w": 180, "h": 180}

	def test_常數(self):
		c = chalk_probe("consts")
		self.assertEqual(c["SIZE"], {"s": 180, "m": 270, "l": 390})
		self.assertEqual(c["STYLES"], {"headline": 90, "body": 69, "accent": 69, "code": 69, "small": 57})
		self.assertEqual(c["MIN"], 45)

	def test_粉筆路徑在框內(self):
		import re
		b = self.BOX
		allp = chalk_probe("paths", box=b)
		self.assertEqual(len(allp), 31)
		for name, ps in allp.items():
			self.assertTrue(ps, name)
			for p in ps:
				nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", p["d"])]
				for x, y in zip(nums[0::2], nums[1::2]):
					self.assertTrue(b["x"] <= x <= b["x"] + b["w"] and b["y"] <= y <= b["y"] + b["h"], (name, x, y))
				self.assertIn(p["w"], (9, 6.75), name)
				self.assertGreater(p["len"], 0, name)

	def test_筆畫長度分配時間(self):
		acts = [{"act": "draw", "t0": 2.0, "t1": 3.2}]
		r = chalk_probe("perform", obj={"name": "magnifier"}, box=self.BOX, acts=acts)
		strokes = [e for e in r["log"] if e["kind"] == "S"]
		paths = chalk_probe("paths", box=self.BOX)["magnifier"]
		self.assertEqual(len(strokes), len(paths))
		self.assertAlmostEqual(sum(s["dur"] for s in strokes), 1.2, places=6)
		self.assertAlmostEqual(strokes[0]["t"], 2.0, places=6)
		for a, b in zip(strokes, strokes[1:]):
			self.assertAlmostEqual(a["t"] + a["dur"], b["t"], places=6)
		total = sum(p["len"] for p in paths)
		for s, p in zip(strokes, paths):
			self.assertEqual(s["d"], p["d"])
			self.assertAlmostEqual(s["dur"], 1.2 * p["len"] / total, places=6)
			self.assertEqual(s["opt"]["kind"], "draw")

	def test_keycap_字用T寫(self):
		r = chalk_probe("perform", obj={"name": "keycap", "text": "Ctrl"}, box=self.BOX, acts=[{"act": "draw", "t0": 0, "t1": 1}])
		self.assertEqual(len([e for e in r["log"] if e["kind"] == "T"]), 1)

	def test_blink與erase走套件(self):
		acts = [{"act": "draw", "t0": 0, "t1": 1}, {"act": "blink", "t0": 2, "t1": 4}, {"act": "erase", "t0": 5, "t1": 5.4}]
		r = chalk_probe("perform", obj={"name": "bulb"}, box=self.BOX, acts=acts)
		fades = [e for e in r["log"] if e["kind"] == "fade"]
		self.assertEqual([f["t0"] for f in fades], [2.5, 3.5])
		self.assertTrue(all(f["to"] == 0 and f["back"] in (3.0, 4.0) for f in fades))
		x = [e for e in r["log"] if e["kind"] == "X"]
		self.assertEqual(len(x), 1)
		self.assertEqual((x[0]["t0"], x[0]["dur"]), (5, 0.4))

	def test_note_換行(self):
		text = "這是一句大約四十個字的測試句子用來檢查斷行是否會超出指定的寬度範圍而且要夠長才行啦"[:40]
		r = chalk_probe("layout", text=text, style="body", maxW=600, maxH=300)
		self.assertNotIn("error", r)
		self.assertGreaterEqual(r["size"], 30)
		self.assertLessEqual(len(r["lines"]) * r["size"] * 1.3, 300)
		self.assertEqual("".join(r["lines"]), text)
		for ln in r["lines"]:
			self.assertLessEqual(len(ln) * r["size"], 600)

	def test_note_英文以詞斷行(self):
		r = chalk_probe("layout", text="printf prints the formatted text to screen", style="small", maxW=300, maxH=400)
		for ln in r["lines"]:
			self.assertFalse(ln.startswith(" "))
		self.assertEqual(" ".join(r["lines"]).split(), "printf prints the formatted text to screen".split())

	def test_note_放不下要報錯(self):
		text = "放不下" * 67
		r = chalk_probe("layout", text=text, style="body", maxW=300, maxH=200)
		self.assertIn("error", r)
		self.assertIn(text, r["error"])

	def test_note_縮字級(self):
		r = chalk_probe("layout", text="粉筆" * 20, style="headline", maxW=900, maxH=200)
		self.assertLess(r["size"], 90)
		self.assertEqual((90 - r["size"]) % 6, 0)

	def test_note_write用seq逐字(self):
		obj = {"text": "請輸入成績", "style": "accent"}
		r = chalk_probe("note", obj=obj, box={"x": 10, "y": 20, "w": 600, "h": 200}, acts=[{"act": "write", "t0": 1, "t1": 3}])
		seqs = [e for e in r["log"] if e["kind"] == "seq"]
		self.assertTrue(seqs)
		self.assertEqual(seqs[0]["parts"][0][1], "cy")

	def test_粉筆總表_寫得出來且決定性(self):
		need_browser(self)
		with tempfile.TemporaryDirectory() as d:
			sums = []
			for i in range(2):
				out = os.path.join(d, f"c{i}.png")
				r = subprocess.run([PW_PY, EXPORT, out, "--sheet", "--skin", "chalk"], capture_output=True, text=True, timeout=300)
				self.assertEqual(r.returncode, 0, r.stderr[-800:])
				with open(out, "rb") as f:
					sums.append(hashlib.md5(f.read()).hexdigest())
			self.assertEqual(sums[0], sums[1])

	def test_不寫色碼與不用opacity(self):
		import re
		for fn in ("icon.chalk.js", "note.chalk.js"):
			with open(os.path.join(CHALK_KIT, fn), encoding="utf-8") as f:
				src = f.read()
			self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,6}\b", src), fn)
			self.assertNotIn("style.opacity", src, fn)
			self.assertNotRegex(src, r"Math\.random|Date\.now|performance\.now|new Date\(", fn)

	def test_總表不借成品資料夾(self):
		# out/ 底下是各支片的成品，搬動或重產就會讓總表壞掉；字型子集也只含那支片的字
		sheet = os.path.join(CHALK_KIT, "..", "tools", "icon_sheet.html")
		with open(sheet, encoding="utf-8") as f:
			src = f.read()
		self.assertNotIn("out/", src)
		for ref in __import__("re").findall(r'(?:src|href)="([^"]+)"|url\("([^"]+)"\)', src):
			path = ref[0] or ref[1]
			self.assertTrue(os.path.exists(os.path.join(os.path.dirname(sheet), path)), path)


BOARD_PROBE = os.path.join(ROOT, "tests", "js", "board_probe.js")
CHALK = os.path.join(ROOT, "video_engine", "explainer", "chalk")
STARTER = os.path.join(CHALK, "starter")
BOARD_CHECK = os.path.join(CHALK, "board_check.py")
PRINTF_FILM = os.path.join(ROOT, "video_engine", "out", "vscode_printf_chalk")
STARTER_FILES = ("index.html", "beats.js", "hyperframes.json", "package.json", "meta.json", "fonts.json", "AGENTS.md",
	"CLAUDE.md", "STARTER.md", "tools/sfx.sh", "tools/sfx.py", "tools/anchor_check.py")
# printf 片一頁粉筆頁的 area（PAD 48、標題下 104、圖區高 668），拿來比格子
PRINTF_AREA = {"P": "P", "x": 48, "y": 104, "w": 1744, "h": 668}


def board_probe(cmd, **q):
	node = shutil.which("node")
	if not node:
		raise AssertionError("缺 node：黑板轉接測試需要 node，請安裝 node 22")
	with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
		json.dump(q, f, ensure_ascii=False)
	try:
		r = subprocess.run([node, BOARD_PROBE, cmd, f.name], capture_output=True, text=True, timeout=30)
	finally:
		os.unlink(f.name)
	if r.returncode:
		raise AssertionError(r.stderr)
	return json.loads(r.stdout)


def mini_story():
	"""兩句、逐字時間的小 story：第 1 句 1.0 秒開口（lead 0.5），第 2 句 4.0 秒"""
	def line(i, text, start, lead=0):
		words = [[c, round(start + 0.2 * k, 3)] for k, c in enumerate(text)]
		return {"i": i, "text": text, "start": start, "end": round(start + 0.2 * len(text), 3), "words": words, "lead": lead}
	return {"title": "t", "duration": 8, "lines": [line(1, "小心這裡要等一下", 1.0, 0.5), line(2, "二號句子在這", 4.0)]}


def board_page(objects, do1, do2=(), template="center", st=None):
	"""用分鏡的 board_actions 編出真正的 objects.json 一頁（格式與 Task 7 的產物相同）"""
	st = st or mini_story()
	pg = {"template": template, "objects": objects, "lines": [{"say": st["lines"][0]["text"], "do": list(do1)}, {"say": st["lines"][1]["text"], "do": list(do2)}]}
	objs, do = SB.board_actions(pg, 1)
	return {"lines": [1, 2], "template": template, "objects": objs, "do": do}


def m_icons(n, col=None, size="m"):
	return [{"type": "icon", "id": "i%d" % k, "name": "check", "size": size} | ({"col": col} if col else {}) for k in range(n)]


def inside(b, box):
	return b["x"] >= box["x"] and b["y"] >= box["y"] and b["x"] + b["w"] <= box["x"] + box["w"] and b["y"] + b["h"] <= box["y"] + box["h"]


def make_film(d, boards):
	"""從 starter 開一支片：printf 的 story（含電腦畫面）加上指定的 boards，字型借 printf 片的子集"""
	sys.path.insert(0, os.path.join(ROOT, "video_engine", "explainer"))
	import sync_film as SF
	shutil.copytree(STARTER, d, dirs_exist_ok=True)
	SF.copy_components(d)
	with open(os.path.join(STORY, "story.json"), encoding="utf-8") as f:
		story = json.load(f)
	for name, merge in (("keys.json", SF.merge_keys), ("screens.json", SF.merge_screens)):
		with open(os.path.join(STORY, name), encoding="utf-8") as f:
			merge(story, json.load(f))
	story["boards"] = boards
	with open(os.path.join(d, "lib", "story.js"), "w", encoding="utf-8") as f:
		f.write("window.STORY = " + json.dumps(story, ensure_ascii=False) + ";\n")
	shutil.copytree(os.path.join(PRINTF_FILM, "assets", "fonts"), os.path.join(d, "assets", "fonts"), dirs_exist_ok=True)


def printf_board(note_text="請輸入成績"):
	"""printf 片第 5、6 句那頁改成置中頁：鍵盤圖示＋一句粉筆字，閃到「空的」，callout 掛在圖示旁"""
	with open(os.path.join(STORY, "story.json"), encoding="utf-8") as f:
		lines = {L["i"]: L["text"] for L in json.load(f)["lines"]}
	pg = {"template": "center", "objects": [{"type": "icon", "id": "kb", "name": "輸入"}, {"type": "note", "id": "n1", "text": note_text}],
		"lines": [{"say": lines[5], "do": [{"act": "draw", "target": "kb"}, {"act": "write", "target": "n1", "cue": "請輸入成績"},
			{"act": "callout", "target": "kb", "text": "等你打字"}, {"act": "blink", "target": "kb", "until": "空的"}]},
			{"say": lines[6], "do": []}]}
	objs, do = SB.board_actions(pg, 5)
	return {"lines": [5, 6], "template": "center", "objects": objs, "do": do}


def run_board_check(case, film):
	need_browser(case)
	r = subprocess.run([PW_PY, BOARD_CHECK, film], capture_output=True, text=True, timeout=300)
	if not os.environ.get("E2E_GEOM") == "1" and "Executable doesn't exist" in r.stderr:
		case.skipTest("Playwright 沒裝 chromium")
	return r


class TestBoardChalk(unittest.TestCase):
	def test_tpl_與printf相同(self):
		with open(os.path.join(PRINTF_FILM, "index.html"), encoding="utf-8") as f:
			src = f.read()
		head = "tpl: function (li, kind) {"
		body = src[src.index(head) + len(head): src.index("\n          head: head,")]
		body = body[:body.rindex("}")]
		for area in (PRINTF_AREA, {"P": "P", "x": 47, "y": 103, "w": 1745, "h": 667}):
			for kind in ("center", "two-col", "other"):
				self.assertEqual(board_probe("tpl", area=area, kind=kind), board_probe("printf_tpl", body=body, area=area, kind=kind), (area, kind))

	def test_grid_置中頁用黑板自己的大格子(self):
		# 置中頁比 printf 的格子大、仍在圖區內且置中；雙欄照 BoardTpl
		for area in (PRINTF_AREA, {"P": "P", "x": 47, "y": 103, "w": 1745, "h": 667}):
			g, t = board_probe("grid", area=area, kind="center"), board_probe("tpl", area=area, kind="center")
			self.assertGreater(g["w"], t["w"])
			self.assertGreater(g["h"], t["h"])
			self.assertTrue(inside(g, area), g)
			self.assertLessEqual(abs(g["cx"] - t["cx"]), 1)
			self.assertLessEqual(abs(g["cy"] - t["cy"]), 1)
			self.assertEqual(board_probe("grid", area=area, kind="two-col"), board_probe("tpl", area=area, kind="two-col"))

	def test_place_置中(self):
		tpl = {"P": "P", "x": 100, "y": 50, "w": 1200, "h": 800, "cx": 700, "cy": 450}
		bd = {"template": "center", "objects": m_icons(3)}
		got = board_probe("place", board=bd, tpl=tpl, sizes={"i%d" % k: {"w": 180, "h": 180} for k in range(3)})
		boxes = [got["i%d" % k] for k in range(3)]
		for b in boxes:
			self.assertTrue(inside(b, tpl), b)
			self.assertLessEqual(abs(b["x"] + b["w"] / 2 - tpl["cx"]), 1, b)
			self.assertEqual((b["w"], b["h"]), (180, 180))
		for a, b in zip(boxes, boxes[1:]):
			self.assertEqual(b["y"] - (a["y"] + a["h"]), 60)
		top, bottom = boxes[0]["y"] - tpl["y"], tpl["y"] + tpl["h"] - (boxes[-1]["y"] + boxes[-1]["h"])
		self.assertLessEqual(abs(top - bottom), 1)

	def test_place_太高就等比縮小(self):
		tpl = board_probe("tpl", area=PRINTF_AREA, kind="center")
		got = board_probe("place", board={"template": "center", "objects": m_icons(3)}, tpl=tpl, sizes={"i%d" % k: {"w": 180, "h": 180} for k in range(3)})
		boxes = [got["i%d" % k] for k in range(3)]
		self.assertTrue(all(inside(b, tpl) for b in boxes), boxes)
		self.assertTrue(all(b["w"] == b["h"] == boxes[0]["w"] < 180 for b in boxes), boxes)

	def test_place_雙欄(self):
		tpl = board_probe("tpl", area=PRINTF_AREA, kind="two-col")
		objs = m_icons(2, "left") + [{"type": "icon", "id": "r0", "name": "check", "col": "right"}]
		sizes = {o["id"]: {"w": 180, "h": 180} for o in objs}
		got = board_probe("place", board={"template": "two-col", "objects": objs}, tpl=tpl, sizes=sizes)
		for oid in ("i0", "i1"):
			self.assertTrue(inside(got[oid], tpl["left"]), got[oid])
		self.assertTrue(inside(got["r0"], tpl["right"]), got["r0"])
		self.assertEqual(got["i1"]["y"] - (got["i0"]["y"] + got["i0"]["h"]), 60)

	def test_place_圖示少就放大(self):
		# 黑板自己的風格：圖示佔不到圖區一半時放大（sizes 標 grow 的才放大，文字不放大）
		tpl = board_probe("tpl", area=PRINTF_AREA, kind="center")
		one = board_probe("place", board={"template": "center", "objects": m_icons(1)}, tpl=tpl, sizes={"i0": {"w": 180, "h": 180, "grow": True}})["i0"]
		self.assertEqual(one["w"], one["h"])
		self.assertGreaterEqual(one["h"], 300)
		self.assertLessEqual(one["h"], tpl["h"] * 0.7)
		self.assertTrue(inside(one, tpl), one)
		self.assertLessEqual(abs(one["x"] + one["w"] / 2 - tpl["cx"]), 1)
		# 旁邊有文字時文字不放大，圖示仍比原本大
		objs = m_icons(1) + [{"type": "note", "id": "n1", "text": "字"}]
		got = board_probe("place", board={"template": "center", "objects": objs}, tpl=tpl, sizes={"i0": {"w": 180, "h": 180, "grow": True}, "n1": {"w": 400, "h": 60}})
		self.assertEqual((got["n1"]["w"], got["n1"]["h"]), (400, 60))
		self.assertGreater(got["i0"]["h"], 180)
		self.assertEqual(got["n1"]["y"] - (got["i0"]["y"] + got["i0"]["h"]), 60)
		# 雙欄：兩邊圖示放大到同一個大小
		tpl2 = board_probe("tpl", area=PRINTF_AREA, kind="two-col")
		objs = [{"type": "icon", "id": "a", "name": "check", "col": "left"}, {"type": "icon", "id": "b", "name": "check", "col": "right"},
			{"type": "note", "id": "n", "text": "字", "col": "right"}]
		got = board_probe("place", board={"template": "two-col", "objects": objs}, tpl=tpl2,
			sizes={"a": {"w": 180, "h": 180, "grow": True}, "b": {"w": 180, "h": 180, "grow": True}, "n": {"w": 300, "h": 60}})
		self.assertEqual(got["a"]["h"], got["b"]["h"])
		self.assertGreater(got["a"]["h"], 180)
		self.assertTrue(inside(got["a"], tpl2["left"]) and inside(got["b"], tpl2["right"]) and inside(got["n"], tpl2["right"]), got)

	def test_place_置中橫排(self):
		tpl = board_probe("tpl", area=PRINTF_AREA, kind="center")
		bd = {"template": "center", "dir": "row", "objects": m_icons(2)}
		got = board_probe("place", board=bd, tpl=tpl, sizes={"i%d" % k: {"w": 180, "h": 180, "grow": True} for k in range(2)})
		a, b = got["i0"], got["i1"]
		self.assertEqual(a["y"], b["y"])
		self.assertGreater(b["x"], a["x"] + a["w"])
		self.assertTrue(inside(a, tpl) and inside(b, tpl), got)
		# 整組左右置中
		self.assertLessEqual(abs((a["x"] + b["x"] + b["w"]) / 2 - tpl["cx"]), 1)
		self.assertLessEqual(abs(a["y"] + a["h"] / 2 - tpl["cy"]), 1)
		bad = board_probe("place", board={"template": "two-col", "dir": "row", "objects": m_icons(1, "left")}, tpl=board_probe("tpl", area=PRINTF_AREA, kind="two-col"), sizes={"i0": {"w": 180, "h": 180}})
		self.assertIn("error", bad)

	def test_mountAll_組合鍵橫排(self):
		import re
		st = mini_story()
		bd = board_page([{"type": "icon", "id": "k", "name": "keycap", "text": "Ctrl+C"}], [{"act": "draw", "target": "k"}])
		r = board_probe("mountAll", story=st, area=PRINTF_AREA, boards=[bd])
		self.assertEqual(r["problems"], [])
		texts = [e for e in r["log"] if e["kind"] == "T"]
		self.assertEqual([t["segs"][0][0] for t in texts], ["Ctrl", "C"])
		# 兩顆鍵帽左右排：字同高、C 在 Ctrl 右邊
		self.assertAlmostEqual(texts[0]["y"] + texts[0]["size"] * 0.65, texts[1]["y"] + texts[1]["size"] * 0.65, delta=1)
		self.assertGreater(texts[1]["x"], texts[0]["x"])
		xs = [float(x) for s in r["log"] if s["kind"] == "S" for x, _ in re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", s["d"])]
		ys = [float(y) for s in r["log"] if s["kind"] == "S" for _, y in re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", s["d"])]
		self.assertGreater(max(xs) - min(xs), 1.8 * (max(ys) - min(ys)))
		a = PRINTF_AREA
		self.assertTrue(a["x"] <= min(xs) and max(xs) <= a["x"] + a["w"] and a["y"] <= min(ys) and max(ys) <= a["y"] + a["h"])

	def test_place_放不下要報錯(self):
		tpl = {"P": "P", "x": 0, "y": 0, "w": 1200, "h": 300, "cx": 600, "cy": 150}
		got = board_probe("place", board={"template": "center", "objects": m_icons(3, size="l")}, tpl=tpl, sizes={"i%d" % k: {"w": 260, "h": 260} for k in range(3)})
		self.assertIn("error", got)

	def test_checkSchedule_抓到until(self):
		st = mini_story()
		good = board_page(m_icons(1), [{"act": "draw", "target": "i0"}, {"act": "blink", "target": "i0", "until": "句子"}])
		self.assertEqual(board_probe("checkSchedule", boards=[good], story=st), [])
		bad = json.loads(json.dumps(good))
		bad["do"]["1"][1]["args"]["until"] = "沒有這幾個字"
		self.assertTrue(board_probe("checkSchedule", boards=[bad], story=st))
		cue = json.loads(json.dumps(good))
		cue["do"]["1"][0]["cue"] = "不在句子裡"
		self.assertTrue(board_probe("checkSchedule", boards=[cue], story=st))
		stray = json.loads(json.dumps(good))
		stray["do"]["3"] = stray["do"].pop("1")
		self.assertTrue(board_probe("checkSchedule", boards=[stray], story=st))

	def test_mountAll_標註框放不下就收小圖示(self):
		# 雙欄各一個圖示放到最大時，標註框四邊都沒位置；圖示要讓出空間，不能報放不下
		st = mini_story()
		objs = [{"type": "icon", "id": "a", "name": "play", "col": "left"}, {"type": "icon", "id": "b", "name": "hourglass", "col": "right"}]
		bd = board_page(objs, [{"act": "draw", "target": "a"}, {"act": "draw", "target": "b"}, {"act": "callout", "target": "b", "text": "在等輸入"}])
		bd["template"] = "two-col"
		r = board_probe("mountAll", story=st, area=PRINTF_AREA, boards=[bd])
		self.assertEqual(r["problems"], [])

	def test_mountAll_照逐字時間畫(self):
		st = mini_story()
		objs = [{"type": "icon", "id": "i0", "name": "keyboard"}, {"type": "note", "id": "n1", "text": "請輸入成績"}]
		bd = board_page(objs, [{"act": "draw", "target": "i0"}, {"act": "write", "target": "n1", "cue": "等一下"},
			{"act": "blink", "target": "i0", "until": "句子"}, {"act": "callout", "target": "i0", "text": "看這裡", "until": "在這"}])
		r = board_probe("mountAll", story=st, area=PRINTF_AREA, boards=[bd])
		self.assertEqual(r["problems"], [])
		self.assertEqual(r["render"], "function")
		span = lambda li, text: [w[1] for w in st["lines"][li - 1]["words"]][st["lines"][li - 1]["text"].index(text)]
		strokes = [e for e in r["log"] if e["kind"] == "S"]
		icon = [s for s in strokes if s["w"] in (9, 6.75)]
		# 沒有 cue 的 draw 從開口前 lead 秒起畫；在那之前什麼都不出現
		self.assertAlmostEqual(min(e["t"] for e in strokes), 0.5)
		self.assertAlmostEqual(icon[0]["t"], 0.5)
		seqs = [e for e in r["log"] if e["kind"] == "seq"]
		self.assertAlmostEqual(seqs[0]["t0"], span(1, "等一下"))
		fades = [e for e in r["log"] if e["kind"] == "fade"]
		blink = [f for f in fades if f.get("back") is not None]
		self.assertTrue(blink)
		self.assertTrue(all(f["t0"] < span(2, "句子") for f in blink), blink)
		# callout 收在 until 那幾個字開口時
		gone = [f for f in fades if f.get("back") is None and f["to"] == 0]
		self.assertEqual(len(gone), 1)
		self.assertAlmostEqual(gone[0]["t0"], span(2, "在這"))
		# 所有粉筆都在這頁的區域內
		import re
		a = PRINTF_AREA
		for s in strokes:
			nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", s["d"])]
			for x, y in zip(nums[0::2], nums[1::2]):
				self.assertTrue(a["x"] <= x <= a["x"] + a["w"] and a["y"] <= y <= a["y"] + a["h"], (x, y))

	def test_mountAll_放不下收進problems(self):
		st = mini_story()
		long = board_page([{"type": "note", "id": "n1", "text": "放不下" * 200}], [{"act": "write", "target": "n1"}])
		ok = board_page(m_icons(1), [{"act": "draw", "target": "i0"}])
		r =board_probe("mountAll", story=st, area=PRINTF_AREA, boards=[long, ok])
		self.assertEqual(len(r["problems"]), 1, r["problems"])
		self.assertIn("放不下", r["problems"][0])
		# 一頁出錯不中斷整片：另一頁照畫
		self.assertTrue([e for e in r["log"] if e["kind"] == "S"])
		tall = board_page(m_icons(3, size="l"), [{"act": "draw", "target": "i0"}])
		low = dict(PRINTF_AREA, h=200)
		self.assertTrue(board_probe("mountAll", story=st, area=low, boards=[tall])["problems"])

	def test_mountAll_黑板不會畫的動作要報(self):
		st = mini_story()
		bd = board_page(m_icons(1), [{"act": "draw", "target": "i0"}, {"act": "focus", "target": "i0"}])
		r = board_probe("mountAll", story=st, area=PRINTF_AREA, boards=[bd])
		self.assertTrue(any("focus" in p for p in r["problems"]), r["problems"])

	def test_mountAll_圈選與底線(self):
		import re
		st = mini_story()
		objs = [{"type": "icon", "id": "i0", "name": "keyboard"}, {"type": "note", "id": "n1", "text": "請輸入成績"}]
		bd = board_page(objs, [{"act": "draw", "target": "i0"}, {"act": "write", "target": "n1"}],
			[{"act": "circle", "target": "i0", "cue": "二號"}, {"act": "underline", "target": "n1", "cue": "句子", "tone": "ok"}])
		r = board_probe("mountAll", story=st, area=PRINTF_AREA, boards=[bd])
		self.assertEqual(r["problems"], [])
		span = lambda li, text: [w[1] for w in st["lines"][li - 1]["words"]][st["lines"][li - 1]["text"].index(text)]
		pts = lambda d: [(float(x), float(y)) for x, y in re.findall(r"(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)", d)]
		strokes = [e for e in r["log"] if e["kind"] == "S"]
		# 分鏡沒寫語氣時編譯器補 accent；圈和底線在 cue 那幾個字開口時畫
		ring = [s for s in strokes if s["tone"] == "accent"]
		under = [s for s in strokes if s["tone"] == "ok"]
		self.assertEqual((len(ring), len(under)), (1, 1), strokes)
		self.assertAlmostEqual(ring[0]["t"], span(2, "二號"))
		self.assertAlmostEqual(under[0]["t"], span(2, "句子"))
		# 圈把圖示整個圍住：圖示每一筆都落在圈的外接框裡
		icon = [p for s in strokes if s["tone"] == "ink" for p in pts(s["d"])]
		rp = pts(ring[0]["d"])
		rx0, rx1, ry0, ry1 = min(x for x, _ in rp), max(x for x, _ in rp), min(y for _, y in rp), max(y for _, y in rp)
		for x, y in icon:
			self.assertTrue(rx0 < x < rx1 and ry0 < y < ry1, (x, y))
		# 底線在字的下面
		note = [e for e in r["log"] if e["kind"] == "seq"][0]
		self.assertGreater(min(y for _, y in pts(under[0]["d"])), note["y"] + note["size"])
		a = PRINTF_AREA
		for x, y in rp + pts(under[0]["d"]):
			self.assertTrue(a["x"] <= x <= a["x"] + a["w"] and a["y"] <= y <= a["y"] + a["h"], (x, y))

	def test_mountAll_圖示擦掉時圈也收掉(self):
		st = mini_story()
		bd = board_page(m_icons(1), [{"act": "draw", "target": "i0"}],
			[{"act": "circle", "target": "i0", "cue": "二號"}, {"act": "erase", "target": "i0", "cue": "在這"}])
		r = board_probe("mountAll", story=st, area=PRINTF_AREA, boards=[bd])
		self.assertEqual(r["problems"], [])
		t = [w[1] for w in st["lines"][1]["words"]][st["lines"][1]["text"].index("在這")]
		gone = [f for f in r["log"] if f["kind"] == "fade" and f["to"] == 0 and f.get("back") is None]
		self.assertEqual(len(gone), 1, gone)
		self.assertAlmostEqual(gone[0]["t0"], t)

	def test_starter_beats是空樣板(self):
		import re
		with open(os.path.join(STARTER, "beats.js"), encoding="utf-8") as f:
			src = f.read()
		# 字串裡的空白（"use strict"）要留著，其餘空白與註解都去掉
		parts = re.split(r'("[^"]*")', re.sub(r"/\*.*?\*/|//[^\n]*", "", src, flags=re.S))
		code = "".join(x if x.startswith('"') else re.sub(r"\s", "", x) for x in parts)
		self.assertEqual(code, 'window.Beats=function(api){"use strict";};')

	def test_starter_檔案齊全(self):
		for rel in STARTER_FILES:
			self.assertTrue(os.path.isfile(os.path.join(STARTER, rel)), rel)

	def test_starter_掛上黑板轉接(self):
		with open(os.path.join(STARTER, "index.html"), encoding="utf-8") as f:
			src = f.read()
		order = ["lib/components/icon/shapes.js", "lib/components/callout/callout.js", "lib/kit/board_tpl.js",
			"lib/kit/icon.chalk.js", "lib/kit/note.chalk.js", "lib/kit/board.chalk.js", "beats.js"]
		at = [src.index('src="%s"' % s) for s in order]
		self.assertEqual(at, sorted(at))
		self.assertIn("ChalkBoard.mountAll(API, D.boards)", src)
		self.assertIn("window.__boardProblems = boards ? boards.problems : [];", src)
		self.assertIn("boards && boards.render(t)", src)
		self.assertIn("BoardTpl.tpl(API.area(li), kind)", src)

	def test_sync_film_帶上黑板轉接與kit(self):
		sys.path.insert(0, os.path.join(ROOT, "video_engine", "explainer"))
		import sync_film as SF
		with tempfile.TemporaryDirectory() as d:
			SF.copy_components(d)
			for rel in ("lib/kit/board.chalk.js", "lib/kit/board_tpl.js", "lib/core.js", "lib/sfxlib.py", "lib/kit/kit.js",
				"lib/kit/kit.css", "lib/kit/chalk-mask.png", "lib/kit/grain.svg", "lib/kit/chalklog.mjs",
				"lib/components/icon/shapes.js", "lib/components/callout/callout.js"):
				self.assertTrue(os.path.exists(os.path.join(d, rel)), rel)

	def test_不寫色碼與純函式(self):
		import re
		for fn in ("board.chalk.js", "board_tpl.js"):
			with open(os.path.join(CHALK_KIT, fn), encoding="utf-8") as f:
				src = f.read()
			self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,6}\b", src), fn)
			self.assertNotIn("style.opacity", src, fn)
			self.assertNotRegex(src, r"Math\.random|Date\.now|performance\.now|new Date\(", fn)
		with open(os.path.join(CHALK_KIT, "board_tpl.js"), encoding="utf-8") as f:
			self.assertNotIn("document", f.read())

	def test_screen_check_也查黑板頁(self):
		node = shutil.which("node")
		if not node:
			raise AssertionError("缺 node")
		with tempfile.TemporaryDirectory() as d:
			make_film(d, [printf_board()])
			r = subprocess.run([node, os.path.join(CHALK, "screen_check.js"), d], capture_output=True, text=True, timeout=60)
			self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
			self.assertIn("黑板頁", r.stdout)
			bad = printf_board()
			[a for a in bad["do"]["5"] if a["act"] == "blink"][0]["args"]["until"] = "沒有這幾個字"
			make_film(d, [bad])
			r = subprocess.run([node, os.path.join(CHALK, "screen_check.js"), d], capture_output=True, text=True, timeout=60)
			self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

	def test_board_check_沒掛上要失敗(self):
		with tempfile.TemporaryDirectory() as d:
			with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
				f.write("<!doctype html><meta charset='utf-8'><body>沒有黑板轉接</body>")
			r = run_board_check(self, d)
			self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

	def test_board_check_starter片(self):
		with tempfile.TemporaryDirectory() as d:
			make_film(d, [printf_board()])
			r = run_board_check(self, d)
			self.assertEqual(r.returncode, 0, r.stdout + r.stderr[-800:])
		with tempfile.TemporaryDirectory() as d:
			make_film(d, [printf_board("放不下" * 200)])
			r = run_board_check(self, d)
			self.assertEqual(r.returncode, 1, r.stdout + r.stderr[-800:])
			self.assertIn("放不下", r.stdout)


if __name__ == "__main__":
	if sys.argv[1:] == ["--regen"]:
		os.makedirs(FIX, exist_ok=True)
		for fn, gen in GEN.items():
			path = os.path.join(FIX, fn)
			old = open(path, encoding="utf-8").read() if os.path.exists(path) else None
			text = json.dumps(gen(), ensure_ascii=False, indent="\t", sort_keys=True) + "\n"
			with open(path, "w", encoding="utf-8") as f:
				f.write(text)
			print(("未變 " if old == text else "已改 ") + fn)
	else:
		unittest.main()
