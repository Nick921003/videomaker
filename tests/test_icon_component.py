"""圖示元件改動前的基準：VS Code 元件的動作與錨點、printf 分鏡的產物，皆為純資料，不比 PNG。
重新產生基準（只在確定行為本來就該變時）：.venv/bin/python tests/test_icon_component.py --regen"""
import hashlib
import json
import os
import sys
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
