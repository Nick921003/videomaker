#!/usr/bin/env python3
"""全幅解說場景。內容只來自 lesson 元素，輸出沿用 slides 的框與 PNG 契約。"""
import os

from PIL import Image, ImageDraw, ImageFont

from layout import H, W, rect


FONT_DIR = "/usr/share/fonts/opentype/noto"
FACES = {
	"regular-tc": (os.path.join(FONT_DIR, "NotoSansCJK-Regular.ttc"), 3),
	"bold-tc": (os.path.join(FONT_DIR, "NotoSansCJK-Bold.ttc"), 3),
	"mono-tc": (os.path.join(FONT_DIR, "NotoSansCJK-Regular.ttc"), 8),
}
MARGIN_X = W // 20
MARGIN_Y = H // 15
RIGHT = W - MARGIN_X
BOTTOM = H - MARGIN_Y
BODY_TOP = H // 4


def _inside(box):
	if box["w"] <= 0 or box["h"] <= 0 or box["x"] < 0 or box["y"] < 0 or box["x"] + box["w"] > W or box["y"] + box["h"] > H:
		raise ValueError(f"explainer element overflows canvas: {box}")
	return box


def _font(theme, role, size):
	face = theme.get("typography", {}).get(role, "regular-tc")
	if face not in FACES:
		raise ValueError(f"unsupported explainer font: {face}")
	path, index = FACES[face]
	return ImageFont.truetype(path, size, index=index)


def _text(targets, measure, guard, theme, raw, region, role, size, floor, color, align="left"):
	"""量測後才畫字；字級下限仍放不下就明確失敗。"""
	text = guard.sanitize(raw)
	if not text:
		raise ValueError("unsupported empty explainer text")
	x0, y0, x1, y1 = region
	x = x0 if align == "left" else (x0 + x1) // 2
	anchor = "lt" if align == "left" else "mt"
	for point in range(size, floor - 1, -1):
		font = _font(theme, role, point)
		lines = text.split("\n")
		line_step = point + 5
		parts = [(line, y0 + index * line_step) for index, line in enumerate(lines)]
		line_boxes = [measure.textbbox((x, line_y), line, font=font, anchor=anchor)
			for line, line_y in parts]
		bounds = (min(box[0] for box in line_boxes), min(box[1] for box in line_boxes),
			max(box[2] for box in line_boxes), max(box[3] for box in line_boxes))
		if bounds[0] >= x0 and bounds[1] >= y0 and bounds[2] <= x1 and bounds[3] <= y1:
			for draw in targets:
				for line, line_y in parts:
					draw.text((x, line_y), line, font=font, fill=color, anchor=anchor)
			return _inside(rect(*bounds))
	raise ValueError(f"explainer text cannot fit: {text[:48]!r} in {region}")


def _targets(base_draw, full_draw, el):
	return (full_draw,) if el.get("hidden") else (base_draw, full_draw)


def _header(slide, guard, theme, base_draw, full_draw, boxes):
	for el in slide["elements"]:
		if el["type"] == "title":
			boxes[el["id"]] = _text(_targets(base_draw, full_draw, el), full_draw, guard, theme,
				el["text"], (MARGIN_X + 32, MARGIN_Y, RIGHT, MARGIN_Y + 88),
				"title", 68, 32, theme["text"]["title"])
		elif el["type"] == "subtitle":
			boxes[el["id"]] = _text(_targets(base_draw, full_draw, el), full_draw, guard, theme,
				el["text"], (MARGIN_X + 34, MARGIN_Y + 105, RIGHT, MARGIN_Y + 155),
				"subtitle", 34, 21, theme["text"]["subtitle"])


def _wrapped_statement(raw, guard, theme, measure, role, width):
	"""長句在窄欄折成兩行，保留原文與較大的字級。"""
	text = guard.sanitize(raw)
	font = _font(theme, role, 41)
	if "\n" in text or measure.textlength(text, font=font) <= width:
		return text
	choices = []
	for cut in range(1, len(text)):
		first, second = text[:cut], text[cut:]
		if not first.strip() or not second.strip():
			continue
		w1 = measure.textlength(first, font=font)
		w2 = measure.textlength(second, font=font)
		if max(w1, w2) <= width:
			# 先在標點或空格斷行，避免把「函式」等詞切開。
			natural = first.rstrip()[-1] in "，、。；：,.!?！？" or first.endswith(" ") or second.startswith(" ")
			choices.append((not natural, abs(w1 - w2), cut, first, second))
	if not choices:
		return text
	_, _, _, first, second = min(choices)
	return first + "\n" + second


def _statement(el, x, y, width, height, guard, theme, base_draw, full_draw):
	targets = _targets(base_draw, full_draw, el)
	color = theme["text"]["callout"] if el["type"] == "callout" else theme["text"]["bullet"]
	label_text = _wrapped_statement(el["text"], guard, theme, full_draw, el["type"], width - 30)
	label = _text(targets, full_draw, guard, theme, label_text,
		(x + 30, y, x + width, y + height), el["type"], 41, 19, color)
	bar_top = y + 5
	bar_bottom = min(y + height, max(bar_top + 25, label["y"] + label["h"]))
	for draw in targets:
		draw.rounded_rectangle((x, bar_top, x + 8, bar_bottom), radius=4,
			fill=theme["text"]["callout"] if el["type"] == "callout" else theme["figure"]["edge"])
	return _inside(rect(x, y, max(x + 9, label["x"] + label["w"]), max(bar_bottom + 1, label["y"] + label["h"])))


def _statements(elements, start_y, guard, theme, base_draw, full_draw, boxes):
	if not elements:
		return
	space = BOTTOM - start_y
	step = min(92, space // len(elements))
	if step < 49:
		raise ValueError("explainer statements cannot fit")
	for index, el in enumerate(elements):
		boxes[el["id"]] = _statement(el, MARGIN_X + 8, start_y + index * step,
			RIGHT - MARGIN_X - 16, step - 8, guard, theme, base_draw, full_draw)


def _caption(el, center_x, y, width, guard, theme, base_draw, full_draw, boxes):
	if not el.get("caption"):
		return y
	boxes[f"{el['id']}:caption"] = _text(_targets(base_draw, full_draw, el), full_draw,
		guard, theme, el["caption"],
		(center_x - width // 2, y, center_x + width // 2, y + 44),
		"caption", 26, 18, theme["text"]["subtitle"], align="center")
	return y + 52


def _figure_bounds(el, boxes, main):
	if el.get("caption"):
		caption = boxes[f"{el['id']}:caption"]
		main = rect(min(main["x"], caption["x"]), min(main["y"], caption["y"]),
			max(main["x"] + main["w"], caption["x"] + caption["w"]),
			max(main["y"] + main["h"], caption["y"] + caption["h"]))
	return _inside(main)


def _compare(el, x, y, width, height, guard, theme, base_draw, full_draw, boxes):
	targets = _targets(base_draw, full_draw, el)
	left, right = el.get("left", {}), el.get("right", {})
	rows = max(len(left.get("items", [])), len(right.get("items", [])), 1)
	row_step = min(100, (height - 80) // rows)
	if row_step < 60:
		raise ValueError("explainer comparison cannot fit")
	used_h = 80 + rows * row_step
	gap = width // 20
	col_w = (width - gap) // 2
	center = x + col_w + gap // 2
	for draw in targets:
		draw.line((center, y + 10, center, y + used_h - 15), fill=theme["figure"]["edge"], width=3)
	for side, prefix, side_x in ((left, "l", x), (right, "r", x + col_w + gap)):
		_text(targets, full_draw, guard, theme, side.get("title", ""),
			(side_x + 14, y + 2, side_x + col_w - 14, y + 64),
			"figure_heading", 52, 23, theme["figure"]["heading"])
		for index, item in enumerate(side.get("items", []), start=1):
			item_y = y + 78 + (index - 1) * row_step
			ink = _text(targets, full_draw, guard, theme, item,
				(side_x + 50, item_y, side_x + col_w - 16, item_y + row_step - 12),
				"figure", 45, 18, theme["text"]["bullet"])
			marker_y = item_y + min(18, row_step // 4)
			for draw in targets:
				draw.ellipse((side_x + 14, marker_y, side_x + 29, marker_y + 15),
					fill=theme["figure"]["edge"])
			boxes[f"{el['id']}:{prefix}{index}"] = _inside(rect(side_x + 14, item_y,
				max(side_x + 30, ink["x"] + ink["w"]),
				max(marker_y + 16, ink["y"] + ink["h"])))
	end = _caption(el, x + width // 2, y + used_h + 8, width, guard, theme, base_draw, full_draw, boxes)
	# reveal 指到 figure ID 時也必須帶出 caption 的整個範圍。
	boxes[el["id"]] = _figure_bounds(el, boxes, rect(x, y, x + width, y + used_h))
	return end


def _model(el, x, y, width, cell_height, guard, theme, base_draw, full_draw, boxes):
	items = el.get("items", [])
	if not items:
		raise ValueError("unsupported empty explainer model")
	count = len(items)
	gap = min(38, width // max(1, count * 7))
	cell_w = min(520, (width - gap * (count - 1)) // count)
	if cell_w < 130:
		raise ValueError("explainer model cannot fit")
	used_w = count * cell_w + (count - 1) * gap
	first_x = x + (width - used_w) // 2
	targets = _targets(base_draw, full_draw, el)
	for index, item in enumerate(items, start=1):
		cell_x = first_x + (index - 1) * (cell_w + gap)
		cell = _inside(rect(cell_x, y, cell_x + cell_w, y + cell_height))
		for draw in targets:
			draw.rounded_rectangle((cell_x, y, cell_x + cell_w - 1, y + cell_height - 1),
				radius=22, fill=theme["figure"]["fill"], outline=theme["figure"]["edge"], width=3)
		_text(targets, full_draw, guard, theme, item,
			(cell_x + 15, y + 28, cell_x + cell_w - 15, y + cell_height - 17),
			"figure", 64, 17, theme["text"]["bullet"], align="center")
		boxes[f"{el['id']}:i{index}"] = cell
		if el["kind"] == "steps" and index < count:
			mid_y = y + cell_height // 2
			arrow_x = cell_x + cell_w + gap // 2
			for draw in targets:
				draw.polygon((arrow_x - 9, mid_y - 10, arrow_x + 10, mid_y, arrow_x - 9, mid_y + 10),
					fill=theme["figure"]["heading"])
	end = _caption(el, x + width // 2, y + cell_height + 22, width, guard, theme, base_draw, full_draw, boxes)
	boxes[el["id"]] = _figure_bounds(el, boxes, rect(first_x, y, first_x + used_w, y + cell_height))
	return end


def _code(el, guard, theme, base_draw, full_draw, boxes):
	lines = [guard.sanitize(raw, keep_indent=True) for raw in el.get("lines", [])]
	if not lines:
		raise ValueError("unsupported empty explainer code")
	area = _inside(rect(MARGIN_X, BODY_TOP + 20, RIGHT, BOTTOM))
	targets = _targets(base_draw, full_draw, el)
	for draw in targets:
		draw.rounded_rectangle((area["x"], area["y"], RIGHT - 1, BOTTOM - 1), radius=24,
			fill=theme["code"]["bg"])
	lang = guard.sanitize(el.get("lang", "C")).upper()
	_text(targets, full_draw, guard, theme, lang,
		(MARGIN_X + 42, area["y"] + 16, MARGIN_X + 190, area["y"] + 53),
		"caption", 24, 17, theme["code"]["keyword"])
	text_x = MARGIN_X + 142
	max_width = RIGHT - text_x - 48
	step = min(58, (area["h"] - 105) // len(lines))
	if step < 22:
		raise ValueError("explainer code has too many lines")
	top = area["y"] + 70 + max(0, (area["h"] - 95 - step * len(lines)) // 2)
	for point in range(min(43, step - 6), 13, -1):
		font = _font(theme, "code", point)
		if all(full_draw.textlength(line, font=font) <= max_width for line in lines):
			break
	else:
		raise ValueError("explainer code line cannot fit")
	for index, line in enumerate(lines, start=1):
		line_y = top + (index - 1) * step
		if line_y + step > BOTTOM - 20:
			raise ValueError("explainer code line overflows")
		for draw in targets:
			draw.text((MARGIN_X + 43, line_y), f"{index:02d}", font=_font(theme, "caption", 20),
				fill=theme["code"]["keyword"], anchor="lt")
			if line:
				color = theme["code"]["preproc"] if line.lstrip().startswith("#") else (
					theme["code"]["keyword"] if "typedef" in line or "int " in line else theme["code"]["normal"])
				draw.text((text_x, line_y), line, font=font, fill=color, anchor="lt")
		width = max(40, int(full_draw.textlength(line, font=font)) + 2)
		boxes[f"{el['id']}:L{index}"] = _inside(rect(text_x, line_y, text_x + width, line_y + step))
	boxes[el["id"]] = area


def _pitfall(slide, figure, guard, theme, base_draw, full_draw, boxes):
	bullets = [el for el in slide["elements"] if el["type"] == "bullet"]
	callouts = [el for el in slide["elements"] if el["type"] == "callout"]
	if len(bullets) > 3 or len(callouts) > 2:
		raise ValueError("explainer pitfall statements cannot fit")
	left_w = (RIGHT - MARGIN_X) // 2 - 65
	for index, el in enumerate(bullets):
		boxes[el["id"]] = _statement(el, MARGIN_X + 6, BODY_TOP + 90 + index * 126,
			left_w, 100, guard, theme, base_draw, full_draw)
	for index, el in enumerate(callouts):
		boxes[el["id"]] = _statement(el, MARGIN_X + left_w + 110,
			BODY_TOP + 125 + index * 145, left_w, 115, guard, theme, base_draw, full_draw)
	if figure is not None:
		statement_end = max((box["y"] + box["h"] for key, box in boxes.items()
			if key in {el["id"] for el in bullets + callouts}), default=BODY_TOP)
		if figure["kind"] == "compare":
			figure_y = max(BODY_TOP + 430, statement_end + 24)
			_compare(figure, MARGIN_X + 28, figure_y, RIGHT - MARGIN_X - 56,
				BOTTOM - figure_y - 8, guard, theme, base_draw, full_draw, boxes)
		elif figure["kind"] in ("boxes", "steps"):
			figure_y = max(BODY_TOP + 520, statement_end + 24)
			_model(figure, MARGIN_X + 28, figure_y, RIGHT - MARGIN_X - 56,
				120, guard, theme, base_draw, full_draw, boxes)
		else:
			raise ValueError(f"unsupported explainer figure: {figure['kind']}")


def render_explainer_scene(slide, guard, theme, out_dir, idx):
	"""渲染語意場景，回傳 (boxes, base_png, full_png)。未支援的頁面明確 ValueError。"""
	elements = slide.get("elements", [])
	figures = [el for el in elements if el["type"] == "figure"]
	codes = [el for el in elements if el["type"] == "code"]
	unsupported = [el for el in elements if el["type"] not in ("title", "subtitle", "bullet", "callout", "figure", "code")]
	if unsupported or len(figures) > 1 or len(codes) > 1 or (figures and codes):
		raise ValueError(f"unsupported explainer scene: {slide.get('id')}")
	figure = figures[0] if figures else None
	code = codes[0] if codes else None
	role = slide.get("role")
	if role == "pitfall" and code is None:
		scene = "pitfall"
	elif code is not None and not any(el["type"] in ("bullet", "callout") for el in elements):
		scene = "code"
	elif figure is not None and figure.get("kind") == "compare":
		scene = "compare"
	elif figure is not None and figure.get("kind") in ("boxes", "steps"):
		scene = "model"
	else:
		raise ValueError(f"unsupported explainer scene: {slide.get('id')}")
	base = Image.new("RGB", (W, H), theme["canvas"]["bg"])
	full = Image.new("RGB", (W, H), theme["canvas"]["bg"])
	base_draw, full_draw = ImageDraw.Draw(base), ImageDraw.Draw(full)
	boxes = {}
	_header(slide, guard, theme, base_draw, full_draw, boxes)
	if scene == "code":
		_code(code, guard, theme, base_draw, full_draw, boxes)
	elif scene == "pitfall":
		_pitfall(slide, figure, guard, theme, base_draw, full_draw, boxes)
	elif scene == "compare":
		end = _compare(figure, MARGIN_X + 8, BODY_TOP + 40, RIGHT - MARGIN_X - 16,
			560, guard, theme, base_draw, full_draw, boxes)
		_statements([el for el in elements if el["type"] in ("bullet", "callout")],
			max(BODY_TOP + 440, end + 40), guard, theme, base_draw, full_draw, boxes)
	else:
		end = _model(figure, MARGIN_X + 8, BODY_TOP + 93, RIGHT - MARGIN_X - 16,
			160, guard, theme, base_draw, full_draw, boxes)
		_statements([el for el in elements if el["type"] in ("bullet", "callout")],
			max(BODY_TOP + 390, end + 46), guard, theme, base_draw, full_draw, boxes)
	for box in boxes.values():
		_inside(box)
	os.makedirs(out_dir, exist_ok=True)
	base_png = os.path.join(out_dir, f"slide_{idx:02d}_base.png")
	full_png = os.path.join(out_dir, f"slide_{idx:02d}_full.png")
	base.save(base_png)
	full.save(full_png)
	return boxes, base_png, full_png
