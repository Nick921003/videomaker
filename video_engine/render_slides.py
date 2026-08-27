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

from layout import (
	CENTER_X, CODE_BOX, CODE_X, CONTENT_BOX, FIG_GAP,
	FIG_ROW_H, H, HEADER_BOX, SUB_Y, TITLE_Y, W, bullet_metrics, code_metrics,
	code_top, count_bullets, fig_box_width, fig_height, fig_vertical, regions_for,
)

CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
THEME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes")
DEFAULT_THEME = "warm"


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


def draw_text_block(targets, measure, text, y, font, color, region=None, align="center"):
	"""在指定區域內畫一行文字。

	align="center" 沿用舊行為（畫布中線 + "ma" 錨點），"left" 錨在區域左緣。
	region 只有靠左時會用到——標題與副標永遠置中於 HEADER_BOX，不吃區域
	"""
	if align == "left":
		if not region:
			# 沒有 region 就不知道左緣在哪，call site 明顯是漏傳，
			# 悄悄退回置中只會讓錯位的畫面看起來像正常輸出
			raise ValueError("draw_text_block: align=\"left\" 需要 region")
		x, anchor = region["x"], "la"
	else:
		x, anchor = CENTER_X, "ma"
	for d in targets:
		d.text((x, y), text, font=font, fill=color, anchor=anchor)
	return ink_box(measure, (x, y), text, font, anchor=anchor)


def draw_figure(targets, measure, el, th, region, guard):
	"""畫示意圖。每個項目都量測，動作可以單獨指到 fig_id:i2

	region 取代舊的 top 參數與畫布中線 CENTER_X：split 給窄欄時橫排會放不下，
	改吃直排；compare 一律在自己拿到的區域內垂直置中，不假設全寬
	"""
	fill, edge = th["figure"]["fill"], th["figure"]["edge"]
	alt, ink = th["figure"]["alt"], th["text"]["bullet"]
	accent = th["text"]["callout"]
	boxes, eid, kind = {}, el["id"], el["kind"]
	items = [guard.sanitize(t) for t in el.get("items", [])]
	top = region["y"]
	cx = region["x"] + region["w"] // 2

	if kind in ("boxes", "steps"):
		n = max(1, len(items))
		gap = FIG_GAP + (34 if kind == "steps" else 0)   # steps 要留箭頭空間
		# 橫直排判準跟 layout.fig_height 共用同一顆 fig_vertical，
		# 兩邊各自重算的話量出來的高度會跟實際畫的分岔
		vertical = fig_vertical(el, region["w"])

		if vertical:
			# 窄欄放不下橫排，改直排：每格寬吃滿欄寬（扣 40px 內距），水平置中於 cx，
			# 整塊在區域內垂直置中——這樣才不會貼著區域上緣
			w = fig_box_width(el, region["w"])
			total = FIG_ROW_H * n + gap * (n - 1)
			x = cx - w // 2
			# 置中要問 layout.fig_height，不能只拿本體高度：自己重算一份的話
			# caption 的預留空間會被漏掉，整塊被往下推、caption 疊出區域外（見 C2）
			y0 = region["y"] + max(0, (region["h"] - fig_height(el, region["w"])) // 2)
			y = y0
			for i, text in enumerate(items, start=1):
				font = fit_font(measure, text, CJK_FONT, 34, w - 28, floor=18)
				for d in targets:
					d.rounded_rectangle([x, y, x + w, y + FIG_ROW_H], radius=8,
						fill=fill, outline=edge, width=2)
					d.text((x + w // 2, y + FIG_ROW_H // 2), text, font=font, fill=ink, anchor="mm")
					if kind == "steps" and i < n:
						# 直排箭頭改指向下：底邊在上、頂點在下
						ay = y + FIG_ROW_H + gap // 2
						d.polygon([(cx - 11, ay - 11), (cx + 11, ay - 11), (cx, ay + 11)], fill=accent)
				boxes[f"{eid}:i{i}"] = {"x": x, "y": y, "w": w, "h": FIG_ROW_H}
				y += FIG_ROW_H + gap
			boxes[eid] = {"x": x, "y": y0, "w": w, "h": total}
			bottom = y0 + total
		else:
			w = fig_box_width(el, region["w"])
			total = w * n + gap * (n - 1)
			x = cx - total // 2
			for i, text in enumerate(items, start=1):
				font = fit_font(measure, text, CJK_FONT, 34, w - 28, floor=18)
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
			boxes[eid] = {"x": cx - total // 2, "y": top, "w": total, "h": FIG_ROW_H}
			bottom = top + FIG_ROW_H

	else:   # compare：左右對照
		mid = 60
		panel_w = (region["w"] - mid) // 2
		# rows 得先算出 h，才能把整塊往區域中央挪
		rows = max(len(el.get("left", {}).get("items", [])),
			len(el.get("right", {}).get("items", [])))
		h = 64 + rows * 74
		# panel_top 是垂直置中後的實際起點，跟函式開頭那個「區域頂緣」的 top 是兩碼事，
		# 同名互相覆蓋只是巧合正確，改個名字讓兩種意思各自有名字。
		# 置中要問 layout.fig_height（含 caption），不能只拿 h：h 只是面板本體高度，
		# 自己重算一份的話 caption 會被漏算，整塊被往下推、caption 疊出區域外（見 C2）
		panel_top = region["y"] + max(0, (region["h"] - fig_height(el, region["w"])) // 2)
		x0 = cx - (panel_w * 2 + mid) // 2
		for side, px in ((el.get("left", {}), x0), (el.get("right", {}), x0 + panel_w + mid)):
			title = guard.sanitize(side.get("title", ""))
			tf = fit_font(measure, title, CJK_FONT, 30, panel_w - 24, floor=18)
			for d in targets:
				d.rounded_rectangle([px, panel_top, px + panel_w, panel_top + 52], radius=8, fill=edge)
				d.text((px + panel_w // 2, panel_top + 26), title, font=tf, fill=fill, anchor="mm")
			y = panel_top + 64
			for j, raw in enumerate(side.get("items", []), start=1):
				text = guard.sanitize(raw)
				f = fit_font(measure, text, CJK_FONT, 28, panel_w - 32, floor=16)
				for d in targets:
					d.rounded_rectangle([px, y, px + panel_w, y + 62], radius=6,
						fill=alt, outline=edge, width=1)
					d.text((px + panel_w // 2, y + 31), text, font=f, fill=ink, anchor="mm")
				boxes[f"{eid}:{'l' if px == x0 else 'r'}{j}"] = {
					"x": px, "y": y, "w": panel_w, "h": 62}
				y += 74
		for d in targets:
			cy = panel_top + h // 2
			d.polygon([(cx - 16, cy - 14), (cx + 16, cy), (cx - 16, cy + 14)],
				fill=accent)
		boxes[eid] = {"x": x0, "y": panel_top, "w": panel_w * 2 + mid, "h": h}
		bottom = panel_top + h

	if el.get("caption"):
		cap = guard.sanitize(el["caption"])
		cf = fit_font(measure, cap, CJK_FONT, 26, region["w"], floor=18)
		for d in targets:
			d.text((cx, bottom + 12), cap, font=cf, fill=th["text"]["subtitle"], anchor="ma")
		boxes[f"{eid}:caption"] = ink_box(measure, (cx, bottom + 12), cap, cf, anchor="ma")
	return boxes


def render_slide(slide, guard, th, out_dir, idx, mode="auto", seed=0):
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

	# 版位交給 regions_for 算，這裡只取畫圖要用的起點
	reg = regions_for(slide, idx - 1, mode=mode, seed=seed)      # idx 從 1 起算，版型用 0 起算的頁次
	bullet_y = reg["text"]["y"]
	fig_y = reg["figure"]["y"] if reg["figure"] else bullet_y
	n_bullets = count_bullets(slide)
	bullet_step, bullet_size = bullet_metrics(n_bullets)
	# 只有多圖頁才需要游標依序往下排；單圖頁維持原樣整區交給 draw_figure 置中
	n_figs = sum(1 for e in slide["elements"] if e["type"] == "figure")

	for el in slide["elements"]:
		eid, etype = el["id"], el["type"]
		hidden = el.get("hidden", False)
		targets = [df] if hidden else [db, df]

		if etype == "title":
			text = guard.sanitize(el["text"])
			font = fit_font(df, text, CJK_FONT, 54, 1600)
			boxes[eid] = draw_text_block(targets, df, text, TITLE_Y, font, th["text"]["title"])

		elif etype == "subtitle":
			text = guard.sanitize(el["text"])
			font = fit_font(df, text, CJK_FONT, 30, 1600)
			boxes[eid] = draw_text_block(targets, df, text, SUB_Y, font, th["text"]["subtitle"])

		elif etype in ("bullet", "callout"):
			text = guard.sanitize(el["text"])
			font = fit_font(df, text, CJK_FONT, bullet_size, reg["text"]["w"])
			color = th["text"]["callout"] if etype == "callout" else th["text"]["bullet"]
			boxes[eid] = draw_text_block(targets, df, text, bullet_y, font, color,
				reg["text"], reg["text_align"])
			bullet_y += bullet_step

		elif etype == "code":
			step, size = code_metrics(len(el["lines"]))
			font = ImageFont.truetype(CJK_FONT, size)
			top = code_top(len(el["lines"]), step)  # 整塊垂直置中，CODE_BOX 外框本身不動；step 沿用上面算好的，不重算
			for i, raw in enumerate(el["lines"], start=1):
				line = guard.sanitize(raw, keep_indent=True)
				y = top + (i - 1) * step
				if line:
					for d in targets:
						d.text((CODE_X, y), line, font=font, fill=code_color(line, th))
				# 空行也要記錄，行號才不會錯位
				width = df.textlength(line, font=font) if line else 0
				boxes[f"{eid}:L{i}"] = {
					"x": CODE_X,
					"y": y,
					"w": max(width, 40),
					"h": step,
					"baseline": y + step,
				}
			boxes[eid] = reg["code"]      # 版位交給 regions_for 算，這裡不重算 CODE_BOX 的 rect

		elif etype == "figure":
			if n_figs > 1:
				# 多圖依序往下排：只給它自己會畫出來的高度，不是「剩餘空間」，
				# 這樣區域內置中就是 no-op，等於接續著上一張排下去，不會蓋到下一張的地盤
				fig_h = fig_height(el, reg["figure"]["w"])
				if fig_y < CONTENT_BOX[1] or fig_y + fig_h > CONTENT_BOX[3]:
					# 疊起來超出內容卡是容量問題，不是排版問題——
					# 寧可整頁失敗逼上層調教材或版型，也不要默默畫到卡片外
					raise ValueError(
						f"{slide['id']} 的 figure {eid} 疊加後超出 CONTENT_BOX："
						f"y={fig_y} h={fig_h}，卡片可用範圍是 {CONTENT_BOX[1]}–{CONTENT_BOX[3]}"
					)
				fig_region = {
					"x": reg["figure"]["x"], "y": fig_y,
					"w": reg["figure"]["w"], "h": fig_h,
				}
				fig_y += fig_h + 40
			else:
				fig_region = reg["figure"]
			boxes.update(draw_figure(targets, df, el, th, fig_region, guard))

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


def opt(name, default=None):
	return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else default


def main():
	if len(sys.argv) < 2:
		print(__doc__)
		return 2
	with open(sys.argv[1], encoding="utf-8") as f:
		lesson = json.load(f)
	out_dir = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else os.path.join(
		os.path.dirname(os.path.abspath(__file__)), "out", lesson["lesson_id"]
	)
	layout_mode = opt("--layout", "auto")
	seed = int(opt("--seed", 0))
	os.makedirs(out_dir, exist_ok=True)

	guard = FontGuard(CJK_FONT)
	theme_name = lesson.get("theme", DEFAULT_THEME)
	th = load_theme(theme_name)
	print(f"主題：{th['label']}（{theme_name}）")
	layout = {
		"lesson_id": lesson["lesson_id"],
		"canvas": {"width": W, "height": H},
		"theme": theme_name,
		"mode": layout_mode,
		"seed": seed,
		"slides": [],
	}

	for idx, slide in enumerate(lesson["slides"], start=1):
		print(f"[{idx}/{len(lesson['slides'])}] {slide['id']}")
		boxes, base_png, full_png = render_slide(slide, guard, th, out_dir, idx, mode=layout_mode, seed=seed)
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
