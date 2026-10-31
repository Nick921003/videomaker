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
		self.assertEqual(icon_probe("strokes", name="keycap", opts={"text": "Ctrl"})["text"], "Ctrl")
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
