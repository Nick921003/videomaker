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

W, H, HEADER, FOOTER = 1920, 1080, 96, 160
VIEW = (0, HEADER, W, H - FOOTER)
MOVE = 0.7
SCALE_MIN = 0.55
TOL = 1.5
# 全景靜止時物件文字的最小實際字級（字幕 40px）。再小在筆電上縮放播放就讀不出來
MIN_FONT = 20


def inside(b, rect):
	x0, y0, x1, y1 = rect
	return b["x"] >= x0 - TOL and b["y"] >= y0 - TOL and b["x"] + b["w"] <= x1 + TOL and b["y"] + b["h"] <= y1 + TOL


def overlap(a, b):
	dx = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
	dy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
	return dx > TOL and dy > TOL


def crosses(pts, b):
	"""折線是否穿進框內（框內縮 TOL，貼邊不算）；逐段做線段與矩形相交（Liang–Barsky），不靠取樣。"""
	x0, y0, x1, y1 = b["x"] + TOL, b["y"] + TOL, b["x"] + b["w"] - TOL, b["y"] + b["h"] - TOL
	if x0 >= x1 or y0 >= y1:
		return False
	for (ax, ay), (bx, by) in zip(pts, pts[1:]):
		dx, dy, lo, hi = bx - ax, by - ay, 0.0, 1.0
		for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
			if p == 0:
				if q <= 0:
					break
			else:
				r = q / p
				if p < 0:
					lo = max(lo, r)
				else:
					hi = min(hi, r)
		else:
			if lo < hi:
				return True
	return False


def owned(b, s):
	"""框屬於標記本來就該碰的目標：中心落在目標裡，或把目標整個包住（外框）。鄰行只是貼邊，不算。"""
	cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
	if s["x"] - TOL <= cx <= s["x"] + s["w"] + TOL and s["y"] - TOL <= cy <= s["y"] + s["h"] + TOL:
		return True
	return b["x"] <= s["x"] + TOL and b["y"] <= s["y"] + TOL and b["x"] + b["w"] >= s["x"] + s["w"] - TOL and b["y"] + b["h"] >= s["y"] + s["h"] - TOL


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


def check_frame(info, objects, scene_ids=()):
	problems = []
	for e in info["errors"]:
		problems.append(f"JS 錯誤：{e}")
	still = not info["moving"] and info["camera"]["settled"]
	settled = still and abs(info["camera"]["z"] - 1) < 1e-3
	scene = scene_ids[info["scene"]] if info["scene"] < len(scene_ids) else info["scene"]
	solid = []
	for b in info["boxes"]:
		if b["role"] == "subtitle" and not inside(b, (0, H - FOOTER, W, H - 20)):
			problems.append(f"字幕超出字幕帶：{b.get('value')}")
		if b["role"] == "header" and not inside(b, (0, 0, W, HEADER)) and not inside(b, (0, H - FOOTER, W, H)):
			problems.append(f"頁首／角落文字越界：{b.get('value')}")
		if b["owner"] in objects and b["role"] in ("text", "panel", "label") and info["alpha"].get(b["owner"], 0) >= 0.99 and b["alpha"] >= 0.99:
			solid.append(b)
	if settled:
		small = {}
		for b in solid:
			font = b["h"] / 1.24
			if b["owner"] in info["members"] and b["role"] == "text" and font < MIN_FONT - 0.5:
				small.setdefault(b["owner"], []).append(font)
		# 彙整成一句可執行的修改建議（給 LLM 修正用，逐段列出它反而抓不到重點）
		for owner, fonts in small.items():
			others = [m for m in info["members"] if m != owner]
			hint = f"跟 {others} 同框；讓它單獨一場，或" if others else ""
			problems.append(f"場景 {scene} 的 {owner} 在全景時字太小：最小 {min(fonts):.0f}px（< {MIN_FONT}，共 {len(fonts)} 段），"
				f"版面縮放 {info['scale']:.2f}。{hint}從它出現的那句就 focus 到要看的部分，直到換場都不要 wide")
		for b in solid:
			# 只檢查當前版面的物件；舊場景的歷史物件本來就在畫面外
			if b["owner"] in info["members"] and not inside(b, VIEW):
				problems.append(f"場景 {scene} 的 {b['owner']} 的{b['role']}超出鏡頭視窗：{b.get('value', '')} {round(b['x'])},{round(b['y'])},{round(b['w'])}x{round(b['h'])}")
		for i, a in enumerate(solid):
			for b in solid[i + 1:]:
				if not (overlap(a, b) and inside(a, VIEW) and inside(b, VIEW)):
					continue
				if a["owner"] != b["owner"]:
					problems.append(f"場景 {scene} 的 {a['owner']} 與 {b['owner']} 重疊：{a.get('value', a['role'])} / {b.get('value', b['role'])}")
				elif {a["role"], b["role"]} <= {"text", "label"}:
					# 同一物件內的文字互疊也是 bug（例：框內兩段字擠在同一行、小標壓到內文）
					problems.append(f"場景 {scene} 的 {a['owner']} 內文字互疊：{a.get('value')} / {b.get('value')}")
	if still:
		# 標記（圈、底線、箭頭與箭頭標籤）：不能蓋到別的字或框；推近的鏡頭也要檢查
		marks = [b for b in info["boxes"] if b["owner"] == "mark" and b["alpha"] >= 0.99]
		for m in [m for m in marks if any(not isinstance(m[k], (int, float)) for k in ("x", "y", "w", "h"))]:
			problems.append(f"場景 {scene} 的標記 {m.get('kind') or m.get('value')} 座標無效（runtime 算出 NaN）")
			marks.remove(m)
		labels = [m for m in marks if m["role"] == "mark-label"]
		for i, m in enumerate(labels):
			if not inside(m, VIEW):
				problems.append(f"場景 {scene} 的標註文字「{m['value']}」超出鏡頭")
			for b in solid + labels[i + 1:]:
				if overlap(m, b):
					problems.append(f"場景 {scene} 的標註文字「{m['value']}」蓋到 {b['owner']} 的「{b.get('value', '框')}」：拿掉標籤或少一個標註")
		for m in marks:
			if m["role"] != "stroke":
				continue
			# NaN 從瀏覽器傳回來會變 None：是 runtime 的 bug，回報而不是讓量測閘崩潰
			if any(not isinstance(v, (int, float)) for pt in m["pts"] for v in pt):
				problems.append(f"場景 {scene} 的{m['kind']}（{m['target']}）座標無效（runtime 算出 NaN）")
				continue
			for b in solid:
				if any(owned(b, s) for s in m.get("skip", [])):
					continue
				if crosses(m["pts"], b):
					problems.append(f"場景 {scene} 的{m['kind']}（{m['target']}）穿過 {b['owner']} 的「{b.get('value', '框')}」：換一個起訖、改版面，或拿掉這個標註")
	return problems


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("player_dir")
	ap.add_argument("--partial", action="store_true", help="開發中：允許目錄裡的元件尚未全部註冊")
	args = ap.parse_args()
	# 延後匯入：check_frame 是純函式，單元測試不需要 Playwright
	from playwright.sync_api import sync_playwright
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
					problems.append(f"t={s['t']:.2f} 場景 {tl['scenes'][s['scene']]['id']} 版面縮到 {s['scale']:.2f} < {SCALE_MIN}：{s['members']}")
			# 錨點必須能只靠 state 算出（不靠 draw 的副作用），否則鏡頭預算與跨物件標記會靜默失效
			for act in tl["actions"]:
				targets = [act["target"]] if act["target"] and ":" in act["target"] else []
				targets += [v for k, v in act["args"].items() if k in ("to", "from") and isinstance(v, str) and ":" in v]
				for target in targets:
					for t in (act["t0"] + 0.01, act["t1"]):
						if page.evaluate("([g, t]) => board.anchor(g, t)", [target, t]) is None:
							problems.append(f"t={t:.2f} 場景 {tl['scenes'][act['scene']]['id']} 的錨點 {target} 無法由 anchors() 解析（{act['act']}）")
			for t in sample_times(tl):
				info = page.evaluate("t => board.seek(t)", t)
				frames += 1
				problems += [f"t={t:.2f} {m}" for m in check_frame(info, objects, [s["id"] for s in tl["scenes"]])]
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
