#!/usr/bin/env python3
"""圖示 → PNG（文章配圖與 31 格總表）。單張圖，不是影片。

用法（要有 Playwright 的 Python，例：~/.local/share/pipx/venvs/webwright/bin/python）：
  export_png.py <out.png> [--name N | --sheet] [--skin flat|pencil|chalk] [--text T] [--tone ink]

--name 的 N 可以寫圖示名稱或任何一個意思；keycap 要加 --text。--sheet 出 6 欄總表（手帳版取 icon_sheet 分鏡）。
flat 是仿真皮膚：IconSVG 等粗線，顏色取手帳主題；pencil 把分鏡編譯、build 後跳到最後一刻截一張；
chalk 開黑板的 tools/icon_sheet.html（?t=end），只出總表。
"""
import argparse
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ENGINE, "board"))

import build as BB  # noqa: E402
import compile as BC  # noqa: E402

COLS = 6
CELL = (300, 250)
SHEET_ICON = 128
SINGLE_ICON = 512
FONT = "'Noto Sans CJK TC', 'Noto Sans CJK', sans-serif"
CHALK_SHEET = os.path.join(ENGINE, "explainer", "chalk", "tools", "icon_sheet.html")
SHEET_SCENE = os.path.join(ENGINE, "board", "fixtures", "icon_sheet.scene.json")


def load(*parts):
	with open(os.path.join(ENGINE, *parts), encoding="utf-8") as f:
		return json.load(f)


def shot(page, path, **kw):
	page.evaluate("document.fonts.ready")
	page.screenshot(path=path, **kw)


def render_flat(out, names, text, tone, single):
	"""names 是 [(圖示名稱, 標籤)]；色取手帳主題的語氣色，底色取畫布色。"""
	from playwright.sync_api import sync_playwright
	theme, tones = load("themes", "notebook.json"), load("themes", "tones.json")
	path = tones["board"][tone].split(".")
	color = theme
	for k in path:
		color = color[k]
	js = "".join(open(os.path.join(HERE, n), encoding="utf-8").read() for n in ("shapes.js", "svg.js"))
	cols, px = (1, SINGLE_ICON) if single else (COLS, SHEET_ICON)
	data = json.dumps({"names": names, "text": text, "color": color, "muted": theme["text"]["muted"], "bg": theme["canvas"]["bg"],
		"cols": cols, "px": px, "cell": [px + 72, px + 90] if single else CELL, "font": FONT}, ensure_ascii=False)
	html = ("<!doctype html><meta charset='utf-8'><style>html,body{margin:0}</style><body><script>" + js + "var D=" + data + ";"
		"document.body.style.background=D.bg;var g=document.createElement('div');"
		"g.style.cssText='display:grid;grid-template-columns:repeat('+D.cols+','+D.cell[0]+'px);width:'+D.cols*D.cell[0]+'px';"
		"D.names.forEach(function(n){var c=document.createElement('div');"
		"c.style.cssText='height:'+D.cell[1]+'px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:12px';"
		"c.innerHTML=IconSVG.render(n[0],{text:D.text||'Ctrl'},D.color,D.px)+'<div style=\"font:'+(D.px>200?36:22)+'px '+D.font+';color:'+D.muted+'\">'+n[1]+'</div>';"
		"g.appendChild(c)});document.body.appendChild(g);</script>")
	with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as f:
		f.write(html)
	try:
		with sync_playwright() as p:
			b = p.chromium.launch()
			pg = b.new_page(viewport={"width": cols * (px + 72 if single else CELL[0]), "height": 400}, device_scale_factor=1)
			pg.goto("file://" + f.name)
			shot(pg, out, full_page=True)
			b.close()
	finally:
		os.unlink(f.name)


def render_pencil(out, doc):
	from playwright.sync_api import sync_playwright
	tl = BC.compile_scene(doc, None, BC.load_catalog())
	with tempfile.TemporaryDirectory() as d:
		BB.build(tl, d)
		with sync_playwright() as p:
			b = p.chromium.launch()
			pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
			pg.goto("file://" + os.path.join(d, "player.html") + "?export")
			pg.wait_for_function("window.boardReady === true", timeout=60000)
			failed = pg.evaluate("window.boardFailed || null")
			if failed:
				raise SystemExit("手帳播放器載入失敗：" + failed)
			pg.evaluate("t => board.seek(t)", tl["duration"])
			pg.evaluate("document.fonts.ready")
			pg.locator("#board").screenshot(path=out)
			b.close()


def render_chalk(out):
	from playwright.sync_api import sync_playwright
	if not os.path.exists(CHALK_SHEET):
		raise SystemExit("找不到黑板總表頁（icon_sheet.html）：" + CHALK_SHEET)
	with sync_playwright() as p:
		b = p.chromium.launch()
		pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
		errors = []
		pg.on("pageerror", lambda e: errors.append(str(e)))
		pg.goto("file://" + CHALK_SHEET + "?t=end")
		pg.wait_for_function("window.sheetReady === true", timeout=60000)
		if errors:
			raise SystemExit("黑板總表頁出錯：" + errors[0])
		shot(pg, out)
		b.close()


def single_scene(name, text, tone):
	obj = {"id": "icon", "type": "icon", "name": name, "tone": tone, "size": "l"}
	if text:
		obj["text"] = text
	return {"version": 1, "title": "圖示", "tag": "配圖", "corner_note": "單張圖示", "objects": [obj],
		"scenes": [{"id": "s", "layout": {"stack": ["icon"]}, "beats": [{"say": "畫出這個圖示。", "do": [{"act": "draw", "target": "icon"}]}]}]}


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("out")
	g = ap.add_mutually_exclusive_group(required=True)
	g.add_argument("--name")
	g.add_argument("--sheet", action="store_true")
	ap.add_argument("--skin", choices=("flat", "pencil", "chalk"), default="flat")
	ap.add_argument("--text")
	ap.add_argument("--tone", default="ink")
	a = ap.parse_args()
	os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
	cat = BC.load_catalog()["types"]["icon"]
	if a.skin == "chalk":
		if not a.sheet:
			raise SystemExit("chalk 只出總表（--sheet）")
		render_chalk(a.out)
	elif a.sheet:
		if a.skin == "pencil":
			with open(SHEET_SCENE, encoding="utf-8") as f:
				render_pencil(a.out, json.load(f))
		else:
			render_flat(a.out, [(n, n) for n in cat["names"]], a.text, a.tone, False)
	else:
		# 意思解析交給編譯器，對不到會列出最接近的三個
		doc = single_scene(a.name, a.text, a.tone)
		name = BC.compile_scene(doc, None, BC.load_catalog())["objects"]["icon"]["name"]
		if a.skin == "pencil":
			render_pencil(a.out, doc)
		else:
			render_flat(a.out, [(name, name)], a.text, a.tone, True)
	print(a.out)


if __name__ == "__main__":
	main()
