#!/usr/bin/env python3
"""VS Code 元件描述 → PNG（文章配圖，取代實機截圖）。

用法（要有 Playwright 的 Python，例：~/.local/share/pipx/venvs/webwright/bin/python）：
  export_png.py <desc.json> <out.png> [--t 秒] [--size 1600x1000]

desc.json 是一個 vscode 物件，或 {"object": {...}, "do": [動作...]}；動作格式同分鏡（board scene.json）。
描述先交給手帳的編譯器驗證並排時間（配圖沒有旁白，動作的 cue 不用），--t 不給就取全部動作做完的畫面。
字型用系統的 Noto Sans CJK TC 與 DejaVu Sans Mono：離線、每次一樣，也比影片用的圓體更像實機。
"""
import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ENGINE, "board"))

import compile as BC  # noqa: E402

FONTS = {"sans": "'Noto Sans CJK TC', 'Noto Sans CJK', sans-serif", "mono": "'DejaVu Sans Mono', 'Noto Sans Mono CJK TC', monospace"}


def timeline(desc):
	obj = dict(desc.get("object", desc))
	obj.setdefault("id", "vs")
	obj["type"] = "vscode"
	doc = {"version": 1, "objects": [obj, {"id": "cursor", "type": "cursor"}],
		"scenes": [{"id": "s", "layout": {"stack": [obj["id"]]}, "beats": [{"say": "畫面", "do": [{**{k: v for k, v in a.items() if k != "cue"}, "target": a.get("target") or obj["id"]} for a in desc.get("do", [])]}]}]}
	tl = BC.compile_scene(doc, None, BC.load_catalog())
	return tl["objects"][obj["id"]], [a for a in tl["actions"] if a["obj"] == obj["id"]], tl["duration"]


def page(desc, acts, t, size):
	js = "".join(open(os.path.join(HERE, n), encoding="utf-8").read() for n in ("model.js", "paint.js", "svg.js"))
	with open(os.path.join(ENGINE, "themes", "vscode_dark.json"), encoding="utf-8") as f:
		theme = f.read()
	data = json.dumps({"desc": desc, "acts": acts, "t": t, "size": size, "fonts": FONTS}, ensure_ascii=False)
	return ("<!doctype html><meta charset='utf-8'><style>html,body{margin:0;background:#000}</style><body><script>" + js +
		"var D=" + data + ",T=" + theme + ";var st=VSCodeModel.state(D.desc,D.acts,D.t,D.size);"
		"document.body.innerHTML=VSCodeSVG.render(VSCodePaint.ops(D.desc,st,D.t,D.size),T,D.size,D.fonts);</script>")


def render_png(desc, out, t=None, size=(1600, 1000)):
	from playwright.sync_api import sync_playwright
	obj, acts, dur = timeline(desc)
	html = page(obj, acts, dur if t is None else t, list(size))
	with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
		f.write(html)
	try:
		with sync_playwright() as p:
			b = p.chromium.launch()
			pg = b.new_page(viewport={"width": size[0], "height": size[1]}, device_scale_factor=1)
			pg.goto("file://" + f.name)
			pg.evaluate("document.fonts.ready")
			pg.screenshot(path=out)
			b.close()
	finally:
		os.unlink(f.name)


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("desc")
	ap.add_argument("out")
	ap.add_argument("--t", type=float)
	ap.add_argument("--size", default="1600x1000")
	a = ap.parse_args()
	with open(a.desc, encoding="utf-8") as f:
		desc = json.load(f)
	render_png(desc, a.out, a.t, tuple(int(x) for x in a.size.split("x")))
	print(a.out)


if __name__ == "__main__":
	main()
