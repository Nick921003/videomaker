#!/usr/bin/env python3
"""投影片繪製器：讀 lesson.json，畫出 1080p 底圖，並吐出實測幾何 layout.json。

用法：.venv/bin/python video_engine/render_slides.py <lesson.json> [輸出目錄]

每頁產兩張圖：
  slide_XX_base.png — hidden 元素不畫（進場狀態）
  slide_XX_full.png — 全部畫上（reveal 動作從這張裁圖疊回去）
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
THEME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
DEFAULT_THEME = "warm"
W, H = 1920, 1080

HEADER_BOX = (80, 60, 1840, 200)
CONTENT_BOX = (80, 240, 1840, 980)
CODE_BOX = (130, 280, 1790, 940)

TITLE_Y, SUB_Y = 80, 148
BULLET_Y0, BULLET_STEP = 310, 120
CENTER_X = W // 2
BULLET_MAX_W = 1650
CODE_X, CODE_Y0, CODE_STEP = 170, 310, 42


def rgb(hex_str):
	h = hex_str.lstrip("#")
	return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def load_theme(name):
	"""配色一律走 theme 檔，繪製器不寫死任何顏色"""
	path = os.path.join(THEME_DIR, f"{name}.json")
	if not os.path.exists(path):
		raise SystemExit(f"找不到主題 {name}，可用：{sorted(f[:-5] for f in os.listdir(THEME_DIR))}")
	t = json.load(open(path, encoding="utf-8"))
	for group in ("canvas", "card", "text", "code", "effects"):
		for k, v in t.get(group, {}).items():
			if isinstance(v, str) and v.startswith("#"):
				t[group][k] = rgb(v)
	return t


class FontGuard:
	"""字型缺字攔截：畫不出來的字元一律換成安全符號"""

	def __init__(self, path, index=0):
		self.cmap = set()
		tt = TTFont(path, fontNumber=index)
		for table in tt["cmap"].tables:
			self.cmap.update(table.cmap.keys())
		tt.close()

	def sanitize(self, text, keep_indent=False):
		"""keep_indent=True 時保留行首空白（程式碼縮排不能被剝掉）"""
		out, dropped = [], []
		for ch in text:
			if ch == "\n" or ord(ch) in self.cmap:
				out.append(ch)
			else:
				dropped.append(ch)
		if dropped:
			print(f"  缺字已移除：{''.join(dropped)}")
		clean = "".join(out)
		return clean if keep_indent else clean.strip()


def fit_font(draw, text, path, size, max_w, floor=24):
	"""字太寬就縮，縮到底線為止"""
	while size > floor:
		font = ImageFont.truetype(path, size)
		if draw.textlength(text, font=font) <= max_w:
			return font
		size -= 2
	return ImageFont.truetype(path, floor)


def code_color(line, th):
	if line.startswith("#"):
		return th["code"]["preproc"]
	if "typedef" in line or "int " in line:
		return th["code"]["keyword"]
	return th["code"]["normal"]


def ink_box(draw, xy, text, font, anchor=None):
	x0, y0, x1, y1 = draw.textbbox(xy, text, font=font, anchor=anchor)
	return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "baseline": y1}


def draw_centered(targets, measure, text, y, font, color):
	"""以畫布中線置中，回傳實測墨水框"""
	for d in targets:
		d.text((CENTER_X, y), text, font=font, fill=color, anchor="ma")
	return ink_box(measure, (CENTER_X, y), text, font, anchor="ma")


FIG_MAX_W = 1560
FIG_ROW_H = 104
FIG_GAP = 26
FIG_CAPTION_H = 46


def fig_height(el):
	"""先算高度，才能把整塊內容垂直置中"""
	cap = FIG_CAPTION_H if el.get("caption") else 0
	if el["kind"] == "compare":
		n = max(len(el.get("left", {}).get("items", [])), len(el.get("right", {}).get("items", [])))
		return 64 + n * 74 + cap
	return FIG_ROW_H + cap


def draw_figure(targets, measure, el, th, top, guard):
	"""畫示意圖。每個項目都量測，動作可以單獨指到 fig_id:i2"""
	fill, edge = th["figure"]["fill"], th["figure"]["edge"]
	alt, ink = th["figure"]["alt"], th["text"]["bullet"]
	accent = th["text"]["callout"]
	boxes, eid, kind = {}, el["id"], el["kind"]
	items = [guard.sanitize(t) for t in el.get("items", [])]

	if kind in ("boxes", "steps"):
		n = max(1, len(items))
		gap = FIG_GAP + (34 if kind == "steps" else 0)   # steps 要留箭頭空間
		w = min(360, (FIG_MAX_W - gap * (n - 1)) // n)
		total = w * n + gap * (n - 1)
		x = CENTER_X - total // 2
		for i, text in enumerate(items, start=1):
			font = fit_font(measure, text, CJK_FONT, 30, w - 28, floor=18)
			for d in targets:
				d.rounded_rectangle([x, top, x + w, top + FIG_ROW_H], radius=8,
					fill=fill, outline=edge, width=2)
				d.text((x + w // 2, top + FIG_ROW_H // 2), text, font=font, fill=ink, anchor="mm")
				if kind == "steps" and i < n:
					ax = x + w + gap // 2
					cy = top + FIG_ROW_H // 2
					d.polygon([(ax - 11, cy - 11), (ax + 11, cy), (ax - 11, cy + 11)], fill=accent)
			boxes[f"{eid}:i{i}"] = {"x": x, "y": top, "w": w, "h": FIG_ROW_H}
			x += w + gap
		boxes[eid] = {"x": CENTER_X - total // 2, "y": top, "w": total, "h": FIG_ROW_H}
		bottom = top + FIG_ROW_H

	else:   # compare：左右對照
		panel_w, mid = 700, 60
		x0 = CENTER_X - (panel_w * 2 + mid) // 2
		rows = 0
		for side, px in ((el.get("left", {}), x0), (el.get("right", {}), x0 + panel_w + mid)):
			title = guard.sanitize(side.get("title", ""))
			tf = fit_font(measure, title, CJK_FONT, 28, panel_w - 24, floor=18)
			for d in targets:
				d.rounded_rectangle([px, top, px + panel_w, top + 52], radius=8, fill=edge)
				d.text((px + panel_w // 2, top + 26), title, font=tf, fill=fill, anchor="mm")
			y = top + 64
			for j, raw in enumerate(side.get("items", []), start=1):
				text = guard.sanitize(raw)
				f = fit_font(measure, text, CJK_FONT, 26, panel_w - 32, floor=16)
				for d in targets:
					d.rounded_rectangle([px, y, px + panel_w, y + 62], radius=6,
						fill=alt, outline=edge, width=1)
					d.text((px + panel_w // 2, y + 31), text, font=f, fill=ink, anchor="mm")
				boxes[f"{eid}:{'l' if px == x0 else 'r'}{j}"] = {
					"x": px, "y": y, "w": panel_w, "h": 62}
				y += 74
			rows = max(rows, len(side.get("items", [])))
		h = 64 + rows * 74
		for d in targets:
			cy = top + h // 2
			d.polygon([(CENTER_X - 16, cy - 14), (CENTER_X + 16, cy), (CENTER_X - 16, cy + 14)],
				fill=accent)
		boxes[eid] = {"x": x0, "y": top, "w": panel_w * 2 + mid, "h": h}
		bottom = top + h

	if el.get("caption"):
		cap = guard.sanitize(el["caption"])
		cf = fit_font(measure, cap, CJK_FONT, 26, FIG_MAX_W, floor=18)
		for d in targets:
			d.text((CENTER_X, bottom + 12), cap, font=cf, fill=th["text"]["subtitle"], anchor="ma")
		boxes[f"{eid}:caption"] = ink_box(measure, (CENTER_X, bottom + 12), cap, cf, anchor="ma")
	return boxes


def render_slide(slide, guard, th, out_dir, idx):
	"""畫一頁，回傳該頁的 boxes 與兩張圖的路徑"""
	bg = th["canvas"]["bg"]
	base = Image.new("RGB", (W, H), bg)
	full = Image.new("RGB", (W, H), bg)
	db, df = ImageDraw.Draw(base), ImageDraw.Draw(full)
	boxes = {}

	for d in (db, df):
		d.rectangle(HEADER_BOX, fill=th["card"]["fill"], outline=th["card"]["edge"], width=th["card"]["width"])
		d.rectangle(CONTENT_BOX, fill=th["card"]["fill"], outline=th["card"]["edge"], width=th["card"]["width"])

	has_code = any(e["type"] == "code" for e in slide["elements"])
	if has_code:
		for d in (db, df):
			d.rectangle(CODE_BOX, fill=th["code"]["bg"], outline=th["code"]["edge"], width=2)

	# 條列與示意圖視為同一塊內容，一起垂直置中於內容卡
	n_bullets = sum(1 for e in slide["elements"] if e["type"] in ("bullet", "callout"))
	figs = [e for e in slide["elements"] if e["type"] == "figure"]
	bullets_h = (n_bullets - 1) * BULLET_STEP + 48 if n_bullets else 0
	figs_h = sum(fig_height(f) + 40 for f in figs)
	block_h = bullets_h + figs_h
	bullet_y = (CONTENT_BOX[1] + (CONTENT_BOX[3] - CONTENT_BOX[1] - block_h) // 2
		if block_h else BULLET_Y0)
	fig_y = bullet_y + bullets_h + (40 if bullets_h else 0)

	for el in slide["elements"]:
		eid, etype = el["id"], el["type"]
		hidden = el.get("hidden", False)
		targets = [df] if hidden else [db, df]

		if etype == "title":
			text = guard.sanitize(el["text"])
			font = fit_font(df, text, CJK_FONT, 54, 1600)
			boxes[eid] = draw_centered(targets, df, text, TITLE_Y, font, th["text"]["title"])

		elif etype == "subtitle":
			text = guard.sanitize(el["text"])
			font = fit_font(df, text, CJK_FONT, 30, 1600)
			boxes[eid] = draw_centered(targets, df, text, SUB_Y, font, th["text"]["subtitle"])

		elif etype in ("bullet", "callout"):
			text = guard.sanitize(el["text"])
			font = fit_font(df, text, CJK_FONT, 38, BULLET_MAX_W)
			color = th["text"]["callout"] if etype == "callout" else th["text"]["bullet"]
			boxes[eid] = draw_centered(targets, df, text, bullet_y, font, color)
			bullet_y += BULLET_STEP

		elif etype == "code":
			font = ImageFont.truetype(CJK_FONT, 28)
			x0, y0, x1, y1 = CODE_BOX
			whole = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
			for i, raw in enumerate(el["lines"], start=1):
				line = guard.sanitize(raw, keep_indent=True)
				y = CODE_Y0 + (i - 1) * CODE_STEP
				if line:
					for d in targets:
						d.text((CODE_X, y), line, font=font, fill=code_color(line, th))
				# 空行也要記錄，行號才不會錯位
				width = df.textlength(line, font=font) if line else 0
				boxes[f"{eid}:L{i}"] = {
					"x": CODE_X,
					"y": y,
					"w": max(width, 40),
					"h": CODE_STEP,
					"baseline": y + CODE_STEP,
				}
			boxes[eid] = whole

		elif etype == "figure":
			boxes.update(draw_figure(targets, df, el, th, fig_y, guard))
			fig_y += fig_height(el) + 40

		elif etype == "image":
			src = el["src"]
			im = Image.open(src).convert("RGB")
			im.thumbnail((1400, 560))
			pos = ((W - im.width) // 2, 320)
			for d, canvas in ((db, base), (df, full)):
				if d in targets:
					canvas.paste(im, pos)
			boxes[eid] = {"x": pos[0], "y": pos[1], "w": im.width, "h": im.height}

		else:
			raise ValueError(f"未知元素型態：{etype}")

	base_png = os.path.join(out_dir, f"slide_{idx:02d}_base.png")
	full_png = os.path.join(out_dir, f"slide_{idx:02d}_full.png")
	base.save(base_png)
	full.save(full_png)
	return boxes, base_png, full_png


def main():
	if len(sys.argv) < 2:
		print(__doc__)
		return 2
	lesson = json.load(open(sys.argv[1], encoding="utf-8"))
	out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
		os.path.dirname(os.path.abspath(__file__)), "out", lesson["lesson_id"]
	)
	os.makedirs(out_dir, exist_ok=True)

	guard = FontGuard(CJK_FONT)
	theme_name = lesson.get("theme", DEFAULT_THEME)
	th = load_theme(theme_name)
	print(f"主題：{th['label']}（{theme_name}）")
	layout = {
		"lesson_id": lesson["lesson_id"],
		"canvas": {"width": W, "height": H},
		"theme": theme_name,
		"slides": [],
	}

	for idx, slide in enumerate(lesson["slides"], start=1):
		print(f"[{idx}/{len(lesson['slides'])}] {slide['id']}")
		boxes, base_png, full_png = render_slide(slide, guard, th, out_dir, idx)
		layout["slides"].append({
			"slide_id": slide["id"],
			"png": base_png,
			"png_full": full_png,
			"boxes": boxes,
		})
		print(f"  元素 {len(boxes)} 個已量測")

	layout_path = os.path.join(out_dir, "layout.json")
	json.dump(layout, open(layout_path, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
	print(f"\n輸出：{out_dir}")
	print(f"幾何：{layout_path}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
