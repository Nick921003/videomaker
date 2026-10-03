#!/usr/bin/env python3
"""瀏覽器量測閘：越界、重疊、縮放下限、決定性。

用法（需 webwright venv 的 Playwright）：
  ~/.local/share/pipx/venvs/webwright/bin/python video_engine/board/check.py <播放器目錄>

通過不代表好看，只代表沒出界、沒疊字、可任意跳轉。結果寫入 <目錄>/check.json，失敗 exit 1。
"""
import argparse
import hashlib
import json
import os
import sys

from playwright.sync_api import sync_playwright

W, H, HEADER, FOOTER = 1920, 1080, 96, 160
VIEW = (0, HEADER, W, H - FOOTER)
MOVE = 0.7
SCALE_MIN = 0.55
TOL = 1.5


def inside(b, rect):
	x0, y0, x1, y1 = rect
	return b["x"] >= x0 - TOL and b["y"] >= y0 - TOL and b["x"] + b["w"] <= x1 + TOL and b["y"] + b["h"] <= y1 + TOL


def overlap(a, b):
	dx = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
	dy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
	return dx > TOL and dy > TOL


def sample_times(tl):
	ts = {0.0, tl["duration"]}
	for a in tl["actions"]:
		ts.update({a["t0"], (a["t0"] + a["t1"]) / 2, a["t1"] + 0.05})
	for e in tl["epochs"]:
		ts.add(e["t"] + MOVE + 0.05)
	for s in tl["scenes"]:
		ts.add(s["t_enter"] + 1.1)
	for b in tl["beats"]:
		ts.add((b["t0"] + b["t1"]) / 2)
	return sorted({round(min(max(t, 0), tl["duration"]), 2) for t in ts})


def check_frame(info, objects):
	problems = []
	for e in info["errors"]:
		problems.append(f"JS 錯誤：{e}")
	settled = not info["moving"] and info["camera"]["settled"] and abs(info["camera"]["z"] - 1) < 1e-3
	solid = []
	for b in info["boxes"]:
		if b["role"] == "subtitle" and not inside(b, (0, H - FOOTER, W, H - 20)):
			problems.append(f"字幕超出字幕帶：{b.get('value')}")
		if b["role"] == "header" and not inside(b, (0, 0, W, HEADER)) and not inside(b, (0, H - FOOTER, W, H)):
			problems.append(f"頁首／角落文字越界：{b.get('value')}")
		if b["owner"] in objects and b["role"] in ("text", "panel") and info["alpha"].get(b["owner"], 0) >= 0.99 and b["alpha"] >= 0.99:
			solid.append(b)
	if settled:
		for b in solid:
			# 只檢查當前版面的物件；舊場景的歷史物件本來就在畫面外
			if b["owner"] in info["members"] and not inside(b, VIEW):
				problems.append(f"{b['owner']} 的{b['role']}超出鏡頭視窗：{b.get('value', '')} {round(b['x'])},{round(b['y'])},{round(b['w'])}x{round(b['h'])}")
		for i, a in enumerate(solid):
			for b in solid[i + 1:]:
				if a["owner"] != b["owner"] and overlap(a, b) and inside(a, VIEW) and inside(b, VIEW):
					problems.append(f"{a['owner']} 與 {b['owner']} 重疊：{a.get('value', a['role'])} / {b.get('value', b['role'])}")
	return problems


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("player_dir")
	ap.add_argument("--partial", action="store_true", help="開發中：允許目錄裡的元件尚未全部註冊")
	args = ap.parse_args()
	root = os.path.abspath(args.player_dir)
	with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog.json"), encoding="utf-8") as f:
		catalog = json.load(f)
	url = "file://" + os.path.join(root, "player.html") + "?export"
	problems, frames = [], 0
	with sync_playwright() as p:
		browser = p.chromium.launch()
		page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
		page.on("pageerror", lambda e: problems.append(f"頁面錯誤：{e}"))
		page.goto(url)
		page.wait_for_function("window.boardReady === true", timeout=60000)
		failed = page.evaluate("window.boardFailed || null")
		if failed:
			problems.append(f"載入失敗：{failed}")
		else:
			tl = page.evaluate("BOARD_DATA.timeline")
			objects = set(tl["objects"])
			types = set(page.evaluate("board.types"))
			if types != set(catalog["types"]) and not (args.partial and types <= set(catalog["types"])):
				problems.append(f"已註冊元件 {sorted(types)} ≠ 目錄 {sorted(catalog['types'])}")
			for s in page.evaluate("board.scales()"):
				if s["members"] and s["scale"] < SCALE_MIN:
					problems.append(f"t={s['t']:.2f} 場景 {s['scene']} 版面縮到 {s['scale']:.2f} < {SCALE_MIN}：{s['members']}")
			for t in sample_times(tl):
				info = page.evaluate("t => board.seek(t)", t)
				frames += 1
				problems += [f"t={t:.2f} {m}" for m in check_frame(info, objects)]
			canvas = page.locator("#board")
			shot = lambda t: hashlib.sha256((page.evaluate("t => (board.seek(t), 0)", t), canvas.screenshot())[1]).hexdigest()
			probe = [round(tl["duration"] * k, 2) for k in (0.23, 0.51, 0.87)]
			first = {t: shot(t) for t in probe}
			for t in reversed(probe):
				if shot(t) != first[t]:
					problems.append(f"t={t} 往回跳轉後畫面不同（不決定性）")
			page.reload()
			page.wait_for_function("window.boardReady === true", timeout=60000)
			if shot(probe[1]) != first[probe[1]]:
				problems.append(f"t={probe[1]} 重新載入後畫面不同（不決定性）")
		browser.close()
	# 同一問題在相鄰取樣點重複出現時只留一筆，方便閱讀
	seen, unique = set(), []
	for m in problems:
		key = m.split(" ", 1)[-1]
		if key not in seen:
			seen.add(key)
			unique.append(m)
	report = {"frames": frames, "ok": not unique, "problems": unique}
	with open(os.path.join(root, "check.json"), "w", encoding="utf-8") as f:
		json.dump(report, f, ensure_ascii=False, indent=1)
	print(f"量測閘：取樣 {frames} 格，{'通過' if not unique else f'{len(unique)} 個問題'}")
	for m in unique[:40]:
		print("  " + m)
	sys.exit(0 if not unique else 1)


if __name__ == "__main__":
	main()
