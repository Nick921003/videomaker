"""PaperBoard 的決定性長紙面、段級音訊與無瀏覽器影片輸出。"""
import copy
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import wave
from functools import lru_cache

from PIL import Image, ImageColor, ImageDraw, ImageFont

ENGINE_DIR = Path(__file__).resolve().parent
# 舊繪製器是 CLI 模組，其 font helper 使用同目錄的 layout import。
if str(ENGINE_DIR) not in sys.path:
	sys.path.insert(0, str(ENGINE_DIR))
from render_slides import font_for_role

W, H, FPS = 1920, 1080, 24
VIEW_TOP, VIEW_BOTTOM = 118, 900
PANEL_X, PANEL_W, PAD, GAP = 230, 1460, 36, 110


@lru_cache(maxsize=1)
def _theme():
	return json.loads((ENGINE_DIR / "themes/paper.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=256)
def _font(role, size):
	path, index = font_for_role(_theme(), role)
	return ImageFont.truetype(path, max(1, round(size)), index=index)


def _canonical(board):
	try:
		from .paper_contract import canonical_board
	except ImportError:
		from paper_contract import canonical_board
	return canonical_board(board)


def _rect(x, y, w, h):
	return {"x": round(x), "y": round(y), "w": round(w), "h": round(h)}


def _text_units(text, keep_tokens=False):
	phrases = r'|[\u4e00-\u9fff]+' if keep_tokens == 'flow' else ''
	return re.findall(r'\\[A-Za-z]|#?[A-Za-z_][A-Za-z0-9_]*(?:\(\))?|[0-9]+(?:\.[0-9]+)?' + phrases + r'|.', text, re.DOTALL) if keep_tokens else text


def _wrap(text, font, width, keep_tokens=False):
	draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
	rows, current = [], ""
	units = []
	for unit in _text_units(text, keep_tokens):
		units.extend(unit if unit != '\n' and draw.textlength(unit, font=font) > width else [unit])
	for ch in units:
		if ch == "\n":
			rows.append(current)
			current = ""
		elif current and draw.textlength(current + ch, font=font) > width:
			rows.append(current)
			current = ch
		else:
			current += ch
	rows.append(current)
	return rows


def _all_values(board, object_id):
	obj = next(o for o in board["objects"] if o["id"] == object_id)
	variants = [obj["values"]]
	variants.extend(update["values"] for scene in board["scenes"] for step in scene["steps"] for update in step["updates"] if update["target"] == object_id)
	return variants


@lru_cache(maxsize=12)
def _layout_cached(board_json):
	board = json.loads(board_json)
	objects, y = [], 120
	measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
	for obj in board["objects"]:
		variants = _all_values(board, obj["id"])
		count, kind = max(map(len, variants)), obj["kind"]
		columns = 1 if kind == "code" else min(count, 4 if kind == "flow" else 3) if kind != "cells" else count
		available = PANEL_W - 2 * PAD
		gap = 24
		font_size = {"cells": 64, "flow": 38, "text": 40, "code": 42}[kind]
		wrap_mode = 'flow' if kind == 'flow' else kind == 'cells'
		if kind == "flow":
			# 流程以順序完整的一列優先；長標籤降欄數，不把第五步硬折回。
			words = [unit for values in variants for value in values for unit in _text_units(value, 'flow') if re.search(r'[A-Za-z0-9_]',unit)]
			for columns in range(count, 0, -1):
				candidate_width = (available - (columns - 1) * gap) / columns - 32
				if any(measure.textlength(word,font=_font('body',font_size)) > candidate_width for word in words):
					continue
				if all(len(_wrap(value, _font("body", font_size), candidate_width, wrap_mode)) <= 2 for values in variants for value in values):
					break
		cell_w = (available - (columns - 1) * gap) / columns
		if kind == "cells":
			units = [unit for values in variants for value in values for unit in _text_units(value, True) if unit != '\n']
			needed = max((measure.textlength(unit, font=_font("body", font_size)) for unit in units), default=0)
			cell_w = min(cell_w, max(180, math.ceil(needed) + 32))
			while font_size > 20 and any(measure.textlength(unit, font=_font("body", font_size)) > cell_w - 32 for unit in units):
				font_size -= 2
		width = cell_w - 32
		if kind == "code":
			while font_size > 16 and any(measure.textlength(v, font=_font("code", font_size)) > width for values in variants for v in values):
				font_size -= 2
		font = _font("code" if kind == "code" else "body", font_size)
		row_counts = [max((len(_wrap(values[i], font, width, wrap_mode)) if i < len(values) else 1 for values in variants)) for i in range(count)]
		row_h = round(font_size * 1.45)
		slot_h = max(140 if kind == "cells" else 90, max(row_counts) * row_h + 40)
		rows = math.ceil(count / columns)
		panel_h = 112 + rows * slot_h + (rows - 1) * gap + PAD
		panel = _rect(PANEL_X, y, PANEL_W, panel_h)
		label_text = " ".join(obj["label"].split())
		label_size = 38
		while measure.textlength(label_text, font=_font("title", label_size)) > available:
			label_size -= 1
		label = measure.textbbox((PANEL_X + PAD, y + PAD), label_text, font=_font("title", label_size), anchor="lt")
		elements = {obj["id"] + ":label": _rect(label[0], label[1], label[2] - label[0], label[3] - label[1])}
		slots = []
		x_start = PANEL_X + (PANEL_W - columns * cell_w - (columns - 1) * gap) / 2
		for i in range(count):
			slot = _rect(x_start + (i % columns) * (cell_w + gap), y + 112 + (i // columns) * (slot_h + gap), cell_w, slot_h)
			slots.append(slot)
			elements[f'{obj["id"]}:slot{i}'] = dict(slot)
			boxes = []
			for values in variants:
				if i >= len(values):
					continue
				for n, row in enumerate(_wrap(values[i], font, width, wrap_mode)):
					boxes.append(measure.textbbox((slot["x"] + 16, slot["y"] + 20 + n * row_h), row, font=font, anchor="lt"))
			if boxes:
				x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
				x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
				elements[f'{obj["id"]}:L{i + 1}' if kind == "code" else f'{obj["id"]}:i{i}'] = _rect(x0, y0, x1 - x0, y1 - y0)
		objects.append({"id": obj["id"], "kind": kind, "panel": panel, "slots": slots, "font_size": font_size, "label_size": label_size, "row_height": row_h, "elements": elements})
		y += panel_h + GAP
	by_id = {o["id"]: o for o in objects}
	compositions = {}
	for scene in board["scenes"]:
		for step in scene["steps"]:
			data = [oid for oid in step["visible"] if by_id[oid]["kind"] != "code"]
			if data and sum(by_id[oid]["kind"] == "code" for oid in step["visible"]) > 1:
				raise ValueError("paper 資料同場最多一個程式提示；多個程式物件請分步呈現")
			shown = data or step["visible"]
			# 依量測高度緊密排版，不讓遠處持續物件把主角縮小。
			placements, top = {}, 150
			for oid in shown:
				p = by_id[oid]["panel"]
				placements[oid] = _rect(PANEL_X, top, p["w"], p["h"])
				top += p["h"] + 28
			compositions[step["id"]] = {"objects": placements, "height": top - 150, "data": data,
				"code": [oid for oid in step["visible"] if by_id[oid]["kind"] == "code"] if data else []}
	return {"width": W, "height": y, "objects": objects, "compositions": compositions,
		"slides": [{"slide_id": scene["id"], "title": scene["title"], "elements": {key: box for o in objects for key, box in {o["id"]: o["panel"], **o["elements"]}.items()}} for scene in board["scenes"]]}

def layout_board(board):
	board = _canonical(board)
	return copy.deepcopy(_layout_cached(json.dumps(board, ensure_ascii=False, sort_keys=True)))


def _timeline(board, timeline):
	steps = [(scene, step) for scene in board["scenes"] for step in scene["steps"]]
	entries = timeline.get("steps", [])
	duration = timeline.get("duration")
	if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0 or len(entries) != len(steps):
		raise ValueError("paper timeline duration／steps 無效")
	previous = 0
	for entry, (scene, step) in zip(entries, steps):
		start, end = entry.get("start"), entry.get("end")
		if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (start, end)):
			raise ValueError("paper timeline 時間必須有限")
		if entry.get("scene_id") != scene["id"] or entry.get("step_id") != step["id"] or not previous <= start < end <= duration:
			raise ValueError("paper timeline IDs／順序／範圍無效")
		previous = end
	return steps


def _state_at(board, timeline, time_seconds):
	steps = _timeline(board, timeline)
	values = {o["id"]: list(o["values"]) for o in board["objects"]}
	state = {"values": values, "previous": copy.deepcopy(values), "visible": [], "revealed": {}, "changed": {}, "code_lines": {}, "code_hint_timing": {}, "step": None, "scene": None, "start": 0, "end": 0}
	for entry, (scene, step) in zip(timeline["steps"], steps):
		if time_seconds < entry["start"]:
			break
		state["previous"] = copy.deepcopy(values)
		state["changed"] = {}
		for oid in step["visible"]:
			if oid not in state["visible"]:
				state["revealed"][oid] = entry["start"]
		for update in step["updates"]:
			oid, new = update["target"], list(update["values"])
			old = values[oid]
			state["changed"][oid] = [i for i in range(max(len(old), len(new))) if (old[i] if i < len(old) else "") != (new[i] if i < len(new) else "")]
			values[oid] = new
		state["code_lines"] = {oid: line for oid, line in state["code_lines"].items() if oid in step["visible"]}
		state["code_hint_timing"] = {oid: timing for oid, timing in state["code_hint_timing"].items() if oid in step["visible"]}
		if step["code_line"] >= 0:
			state["code_lines"][step["focus"]] = step["code_line"]
			state["code_hint_timing"][step["focus"]] = (entry["start"], entry["end"])
		state.update(step=step, scene=scene, start=entry["start"], end=entry["end"], visible=list(step["visible"]))
	return state


def _ease(p):
	p = min(1, max(0, p))
	return p * p * (3 - 2 * p)


def _fade_color(foreground, background, opacity):
	fg, bg = ImageColor.getrgb(foreground), ImageColor.getrgb(background)
	return tuple(round(b + (f - b) * opacity) for f, b in zip(fg, bg))


def _target_camera(step, layout):
	composition = layout["compositions"][step["id"]]
	panels = list(composition["objects"].values())
	y0 = min(p["y"] for p in panels) - 30
	y1 = max(p["y"] + p["h"] for p in panels) + 30
	scale = min(.98, (VIEW_BOTTOM - VIEW_TOP - 40) / (y1 - y0))
	focus = composition["objects"].get(step["focus"], panels[0])
	center = (y0 + y1) / 2
	# 留出的安全邊距允許鏡頭跟焦，而非拉遠拍整張長紙。
	drift = max(-12, min(12, .04 * (focus["y"] + focus["h"] / 2 - center)))
	return (W / 2 + (12 if step["focus"] in composition["code"] else 0), center + drift, scale)


def _camera_at(board, timeline, layout, time_seconds):
	steps = _timeline(board, timeline)
	cam = _target_camera(steps[0][1], layout)
	previous_start, transition_from, transition_to, transition_duration = 0, cam, cam, 1
	for entry, (_, step) in zip(timeline["steps"], steps):
		if time_seconds < entry["start"]:
			break
		p = _ease((entry["start"] - previous_start) / transition_duration)
		cam = tuple(a + (b - a) * p for a, b in zip(transition_from, transition_to))
		transition_from, transition_to = cam, _target_camera(step, layout)
		previous_start = entry["start"]
		transition_duration = min(1.2, (entry["end"] - entry["start"]) * .3)
	p = _ease((time_seconds - previous_start) / transition_duration)
	return tuple(a + (b - a) * p for a, b in zip(transition_from, transition_to))


def _placements_at(board, timeline, layout, time_seconds):
	steps = _timeline(board, timeline)
	placements = {o["id"]: dict(o["panel"]) for o in layout["objects"]}
	previous_start, origin, target, duration = 0, dict(placements), dict(placements), 1
	previous_visible = set()
	for entry, (_, step) in zip(timeline["steps"], steps):
		if time_seconds < entry["start"]:
			break
		p = _ease((entry["start"] - previous_start) / duration)
		placements = {oid: {k: a[k] + (target[oid][k] - a[k]) * p for k in a} for oid, a in origin.items()}
		origin, target = placements, dict(placements)
		target.update(layout["compositions"][step["id"]]["objects"])
		# 重新出現的物件從本次版位進場；連續可見物件才沿途移動。
		for oid in step["visible"]:
			if oid not in previous_visible:
				origin[oid] = dict(target[oid])
		previous_visible = set(step["visible"])
		previous_start, duration = entry["start"], min(1.2, (entry["end"] - entry["start"]) * .3)
	p = _ease((time_seconds - previous_start) / duration)
	return {oid: {k: a[k] + (target[oid][k] - a[k]) * p for k in a} for oid, a in origin.items()}


def _hint_duration(state, oid):
	start, end = state["code_hint_timing"][oid]
	return max(1.4, end - start + 1.2)


def _hint_weight(state, t, oid):
	if not state["step"]:
		return 0
	if oid not in state["code_hint_timing"]:
		return 0
	start, end = state["code_hint_timing"][oid]
	visible_seconds = _hint_duration(state, oid)
	elapsed = t - start
	return _ease((elapsed - .28) / .18) * (1 - _ease((elapsed - visible_seconds + .6) / .6))


def _hint_reserve_weight(state, t, oid):
	if not state["step"] or oid not in state["code_hint_timing"]:
		return 0
	start, end = state["code_hint_timing"][oid]
	visible_seconds = _hint_duration(state, oid)
	elapsed = t - start
	# 先保留右側，再顯提示；提示完全退場後才把同一物件移回。
	return _ease(elapsed / .28) * (1 - _ease((elapsed - visible_seconds) / .55))


def _motion_progress(state, i, count, t):
	duration = max(.01, state["end"] - state["start"])
	p = (t - state["start"]) / duration
	delay = .40 * i / max(1, count - 1)
	return _ease((p - delay) / .48)


def _local_progress(state, i, count, t):
	duration = max(.01, state["end"] - state["start"])
	delay = min(.10, duration * .15 / max(1, count - 1)) * i
	return min(1, max(0, (t - state["start"] - delay) / min(.42, duration * .6)))


def _flow_connection(oid, index, previous, current, scale):
	start = (previous["x"] + previous["w"], previous["y"] + previous["h"] / 2)
	end = (current["x"], current["y"] + current["h"] / 2)
	path = [start, end]
	if current["y"] > previous["y"] + 2:
		start = (previous["x"] + previous["w"] / 2, previous["y"] + previous["h"])
		end = (current["x"] + current["w"] / 2, current["y"])
		gutter = (start[1] + end[1]) / 2
		path = [start, (start[0], gutter), (end[0], gutter), end]
	dx, dy = end[0] - path[-2][0], end[1] - path[-2][1]
	length = math.hypot(dx, dy)
	ux, uy = dx / length, dy / length
	head_length = 6 * scale
	head = [(end[0] - ux * head_length - uy * head_length, end[1] - uy * head_length + ux * head_length), end,
		(end[0] - ux * head_length + uy * head_length, end[1] - uy * head_length - ux * head_length)]
	points, padding = path + head, 3 * scale + 2
	x0, y0 = min(p[0] for p in points) - padding, min(p[1] for p in points) - padding
	x1, y1 = max(p[0] for p in points) + padding, max(p[1] for p in points) + padding
	return {"id": oid, "source_index": index - 1, "target_index": index, "start": start, "end": end,
		"path": path, "head": head, "bbox": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}}


def _curve(a, b, p):
	bend = min(160, max(60, abs(b[0] - a[0]) * .18))
	return (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p - math.sin(math.pi * p) * bend)


def frame_metadata(board, timeline, time_seconds):
	board = _canonical(board)
	layout = layout_board(board)
	state = _state_at(board, timeline, time_seconds)
	camera = _camera_at(board, timeline, layout, time_seconds)
	placements = _placements_at(board, timeline, layout, time_seconds)
	cx, cy, scale = camera
	step = state["step"]
	composition = layout["compositions"][step["id"]] if step else {"code": [], "data": []}
	hint_oid = step["focus"] if step and step["focus"] in composition["code"] else (composition["code"][0] if composition["code"] else None)
	weight = _hint_weight(state, time_seconds, hint_oid) if hint_oid else 0
	reserve_weight = _hint_reserve_weight(state, time_seconds, hint_oid) if hint_oid else 0
	objects = {}
	for geom in layout["objects"]:
		oid = geom["id"]
		if oid not in state["visible"]:
			continue
		base, place = geom["panel"], placements[oid]
		def transform(box):
			x = W / 2 + (place["x"] + box["x"] - base["x"] - cx) * scale
			y = (VIEW_TOP + VIEW_BOTTOM) / 2 + (place["y"] + box["y"] - base["y"] - cy) * scale
			w, h = box["w"] * scale, box["h"] * scale
			if composition["code"] and geom["kind"] != "code":
				# 同一物件縮到另一側，程式提示退場即返回原處。
				factor = 1 - .43 * reserve_weight
				x = W / 2 + (x - W / 2) * factor + W * .22 * reserve_weight
				w *= factor
				y = (VIEW_TOP + VIEW_BOTTOM) / 2 + (y - (VIEW_TOP + VIEW_BOTTOM) / 2) * factor
				h *= factor
			return {"x": x, "y": y, "w": w, "h": h}
		actual_scale = scale * (1 - .43 * reserve_weight if composition["code"] and geom["kind"] != "code" else 1)
		if oid in composition["objects"] and geom["font_size"] * actual_scale < 18:
			raise ValueError("paper 同時可見內容超出可讀版面；請分步呈現，不能縮成小字")
		objects[oid] = {"panel": transform(base), "slots": [transform(b) for b in geom["slots"]],
			"elements": {key: transform(b) for key, b in geom["elements"].items()},
			"scale": scale * (1 - .43 * reserve_weight if composition["code"] and geom["kind"] != "code" else 1)}
	hint = None
	if weight > .005:
		oid = hint_oid
		line = state["code_lines"].get(oid, 0)
		values = state["values"][oid]
		hint = {"id": oid, "lines": list(range(max(0, line - 1), min(len(values), line + 2))), "focus_line": line,
			"opacity": weight, "reserve_weight": reserve_weight, "panel": _rect(W * .055, VIEW_TOP + (VIEW_BOTTOM - VIEW_TOP) * .17, W * .40, (VIEW_BOTTOM - VIEW_TOP) * .60)}
	flights, scan, local_indices = [], None, []
	if step:
		motion = step.get("motion", "transform" if state["changed"] else "reveal")
		moving = {oid: list(indices) for oid, indices in state["changed"].items()}
		if motion == "scan" and "scan_output" in step:
			moving.pop(step["scan_output"], None)
		transfer_index = max(0, step.get("focus_index", -1))
		if motion == "transfer":
			indices = moving.setdefault(step["focus"], [])
			if transfer_index not in indices:
				indices.append(transfer_index)

		for oid, indices in moving.items():
			if oid not in objects:
				continue
			for rank, i in enumerate(indices):
				if i >= len(objects[oid]["slots"]):
					continue
				slot = objects[oid]["slots"][i]
				end = (slot["x"] + slot["w"] / 2, slot["y"] + slot["h"] / 2)
				source = objects.get(step.get("source")) if motion == "transfer" and oid == step["focus"] and i == transfer_index else None
				if source is None:
					local_indices.append((oid, i, _local_progress(state, rank, len(indices), time_seconds)))
					continue
				p = _motion_progress(state, rank, len(indices), time_seconds)
				if not 0 < p < 1:
					continue
				if source:
					ss = source["slots"][step.get("source_index", 0)]
					start = (ss["x"] + ss["w"] / 2, ss["y"] + ss["h"] / 2)
				else:
					start = (end[0] - 95, max(VIEW_TOP + 80, slot["y"] - 70))
				value = state["previous"][step["source"]][step.get("source_index", 0)] if source else (state["values"][oid][i] if i < len(state["values"][oid]) else "")
				flights.append({"id": oid, "index": i, "progress": p, "start": start, "end": end, "position": _curve(start, end, p), "path": [_curve(start, end, n / 24) for n in range(25)], "value": value, "motion": "transfer" if source else "transform", "draw_path": source is not None, "source_id": step["source"] if source else None, "source_index": step.get("source_index", 0) if source else None})
		if motion == "scan" and step["focus"] in objects:
			oid = step["focus"]
			slots = objects[oid]["slots"]
			stop = step.get("focus_index", -1)
			if stop == -1:
				stop = len(state["values"][oid]) - 1
			if stop >= 0:
				p = _ease((time_seconds - state["start"]) / max(.01, (state["end"] - state["start"]) * .68))
				index = min(stop, p * stop)
				lo, hi = math.floor(index), min(stop, math.ceil(index))
				a, b = slots[lo], slots[hi]
				scan_scale = objects[oid]["scale"]
				scan = {"id": oid, "index": stop if p == 1 else index, "scale": scan_scale, "position": (a["x"] + a["w"] / 2 + (b["x"] + b["w"] / 2 - a["x"] - a["w"] / 2) * (index - lo), a["y"] - 22 * scan_scale + (b["y"] - a["y"]) * (index - lo))}
	if scan and "scan_output" in step:
		output_id = step["scan_output"]
		output_geom = next(g for g in layout["objects"] if g["id"] == output_id)
		output_slot = objects[output_id]["slots"][0]
		factor = objects[output_id]["scale"]
		font = _font("body", output_geom["font_size"] * factor)
		measure_output = ImageDraw.Draw(Image.new("RGB", (1, 1)))
		stop = step.get("focus_index", -1)
		if stop == -1:
			stop = len(state["values"][step["focus"]]) - 1
		tokens = state["values"][step["focus"]][:stop + int(step.get("scan_include_stop", False))]
		progress = _ease((time_seconds - state["start"]) / max(.01, (state["end"] - state["start"]) * .68))
		units, arrived = progress * len(tokens), 0
		full_rows = _wrap("".join(tokens), _font("body", output_geom["font_size"]), output_geom["slots"][0]["w"] - 32)
		base = (output_slot["x"] + 16 * factor, output_slot["y"] + 20 * factor)
		for rank, value in enumerate(tokens):
			local = units - rank
			if local >= .82:
				arrived += 1
			if not 0 < local < .82:
				continue
			# 從來源格到最終輸出中該值的實測文字位置，不猜字母或終止符。
			offset = sum(len(v.replace("\n", "")) for v in tokens[:rank])
			end_offset = offset + len(value.replace("\n", ""))
			glyph_boxes, consumed = [], 0
			for row_index, row in enumerate(full_rows):
				lo, hi = max(0, offset - consumed), min(len(row), end_offset - consumed)
				if lo < hi:
					x = base[0] + measure_output.textlength(row[:lo], font=font)
					y = base[1] + row_index * output_geom["row_height"] * factor
					glyph_boxes.append(measure_output.textbbox((x, y), row[lo:hi], font=font, anchor="lt"))
				consumed += len(row)
			if glyph_boxes:
				end = ((min(b[0] for b in glyph_boxes) + max(b[2] for b in glyph_boxes)) / 2,
					(min(b[1] for b in glyph_boxes) + max(b[3] for b in glyph_boxes)) / 2)
			else:
				end = base
			ss = objects[step["focus"]]["slots"][rank]
			start = (ss["x"] + ss["w"] / 2, ss["y"] + ss["h"] / 2)
			flight_progress = _ease(local / .82)
			flights.append({"id": output_id, "index": 0, "progress": flight_progress, "start": start, "end": end,
				"position": _curve(start, end, flight_progress), "path": [_curve(start, end, n / 24) for n in range(25)],
				"value": value, "motion": "scan", "draw_path": True, "source_id": step["focus"], "source_index": rank})
		output_text = "".join(tokens[:arrived])
		prefix_rows = _wrap(output_text, _font("body", output_geom["font_size"]), output_geom["slots"][0]["w"] - 32)
		boxes = [measure_output.textbbox((base[0], base[1] + n * output_geom["row_height"] * factor), row, font=font, anchor="lt") for n, row in enumerate(prefix_rows)]
		x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
		x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
		scan.update(output_id=output_id, output_text=output_text, count=arrived,
			output_bbox={"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0})
	measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
	geometries = {g["id"]: g for g in layout["objects"]}
	for flight in flights:
		# 轉移保留來源的排字量測，不能把長註解擠成目的格的直欄。
		glyph_id = flight["source_id"] or flight["id"]
		geom, factor = geometries[glyph_id], objects[glyph_id]["scale"]
		glyph_index = flight["source_index"] if flight["source_id"] else flight["index"]
		font = _font("body", geom["font_size"] * factor)
		rows = _wrap(flight["value"], _font("body", geom["font_size"]), geom["slots"][glyph_index]["w"] - 32, 'flow' if geom['kind']=='flow' else geom["kind"] == "cells")
		flight["glyph"] = {"rows": rows, "font_size": geom["font_size"] * factor, "row_height": geom["row_height"] * factor, "scale": factor}
		def glyph_box(pos):
			boxes = [measure.textbbox((pos[0], pos[1] - len(rows) * geom["row_height"] * factor / 2 + n * geom["row_height"] * factor), row, font=font, anchor="mt") for n, row in enumerate(rows)]
			x0, y0, x1, y1 = min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)
			return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
		box = glyph_box(flight["position"])
		minimum_left = 24 + (W * .455) * reserve_weight
		maximum_right, minimum_top, maximum_bottom = W - 24, VIEW_TOP + 20, VIEW_BOTTOM - 20
		if flight["source_id"] is None:
			# 原地變字沒有跨物件來源，飛字須留在實測文字格內，避免遮住標題。
			slot = objects[flight["id"]]["slots"][flight["index"]]
			minimum_left, maximum_right = max(minimum_left, slot["x"]), min(maximum_right, slot["x"] + slot["w"])
			minimum_top, maximum_bottom = max(minimum_top, slot["y"]), min(maximum_bottom, slot["y"] + slot["h"])
		if box["w"] > maximum_right - minimum_left or box["h"] > maximum_bottom - minimum_top:
			raise ValueError("paper 來源飛值超出可讀版面；請縮短來源或分步呈現")
		dx = max(0, minimum_left - box["x"]) - max(0, box["x"] + box["w"] - maximum_right)
		dy = max(0, minimum_top - box["y"]) - max(0, box["y"] + box["h"] - maximum_bottom)
		flight["position"] = (flight["position"][0] + dx, flight["position"][1] + dy)
		flight["bbox"] = glyph_box(flight["position"])
		flight["path_bbox"] = {"x": min(p[0] for p in flight["path"]), "y": min(p[1] for p in flight["path"]), "w": max(p[0] for p in flight["path"]) - min(p[0] for p in flight["path"]), "h": max(p[1] for p in flight["path"]) - min(p[1] for p in flight["path"])}
	if scan:
		x, y = scan["position"]
		radius, padding = 12 * scan["scale"], 3
		label = objects[scan["id"]]["elements"][scan["id"] + ":label"]
		y = max(y, label["y"] + label["h"] + radius + padding + 2)
		scan["position"] = (x, y)
		scan["radius"] = radius
		scan["bbox"] = {"x": x - radius - padding, "y": y - radius - padding,
			"w": 2 * (radius + padding), "h": 2 * radius + 10 * scan["scale"] + 2 * padding}
	arrows = []
	for oid, obj in objects.items():
		if geometries[oid]["kind"] != "flow":
			continue
		for i in range(1, len(state["values"][oid])):
			a, b = obj["slots"][i - 1], obj["slots"][i]
			arrows.append(_flow_connection(oid, i, a, b, obj["scale"]))
	if hint:
		b = hint["panel"]
		font_size = 36
		while True:
			font = _font("code", font_size)
			rows_by_line = [_wrap(state["values"][hint["id"]][line], font, b["w"] - 72) for line in hint["lines"]]
			row_h = round(font_size * 1.4)
			if sum(len(rows) * row_h + 16 for rows in rows_by_line) <= b["h"] - 124:
				break
			font_size -= 1
			if font_size < 20:
				raise ValueError("paper code hint 超出可讀版面；請減少同時提示的程式內容")
		hint["elements"], hint["render_lines"] = {}, []
		top = b["y"] + 112
		for line, rows in zip(hint["lines"], rows_by_line):
			boxes = [measure.textbbox((b["x"] + 36, top + n * row_h), row, font=font, anchor="lt") for n, row in enumerate(rows)]
			x0, y0, x1, y1 = min(v[0] for v in boxes), min(v[1] for v in boxes), max(v[2] for v in boxes), max(v[3] for v in boxes)
			hint["elements"][f'{hint["id"]}:L{line + 1}'] = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
			hint["render_lines"].append({"line": line, "rows": rows, "top": top, "font_size": font_size, "row_height": row_h})
			top += len(rows) * row_h + 16

	value_changes = []
	for oid, index, progress in local_indices:
		geom, obj = geometries[oid], objects[oid]
		factor, slot = obj["scale"], obj["slots"][index]
		phases = {}
		for name, values, opacity in (("old", state["previous"][oid], 1 - _ease(progress * 2) if progress < .5 else 0), ("new", state["values"][oid], _ease((progress - .5) * 2) if progress >= .5 else 0)):
			if index >= len(values) or opacity <= .005:
				continue
			text = values[index]
			font, rows = _text_layout(text, "body", geom["font_size"], geom["slots"][index]["w"] - 32, factor, 'flow' if geom['kind']=='flow' else geom["kind"] == "cells")
			boxes = [measure.textbbox((slot["x"] + 16 * factor, slot["y"] + (20 + n * geom["row_height"]) * factor), row, font=font, anchor="lt") for n, row in enumerate(rows)]
			x0, y0, x1, y1 = min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)
			phases[name] = {"text": text, "opacity": opacity, "bbox": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}}
		value_changes.append({"id": oid, "index": index, "progress": progress, **phases})
	return {"camera": camera, "objects": objects, "code_hint": hint, "code_reserve_weight": reserve_weight, "flights": flights, "value_changes": value_changes, "scan": scan, "arrows": arrows}

def _pencil(draw, points, progress, color, width=3, phase=0):
	lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])]
	remaining = sum(lengths) * min(1, max(0, progress))
	for i, (a, b, length) in enumerate(zip(points, points[1:], lengths)):
		if remaining <= 0:
			break
		fraction = min(1, remaining / max(length, 1))
		end = (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)
		draw.line([a, end], fill=color, width=max(1, round(width)))
		# 固定微偏移的第二筆，不使用亂數或牆鐘時間。
		shift = 1.1 * math.sin(i + phase)
		draw.line([(a[0] + shift, a[1] + 1), (end[0] + shift, end[1] + 1)], fill=color, width=1)
		remaining -= length


def _text_layout(text, role, font_size, width, scale=1, keep_tokens=False):
	draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
	font = _font(role, font_size * scale)
	rows = _wrap(text, _font(role, font_size), width, keep_tokens)
	size = max(1, round(font_size * scale))
	while size > 1 and any(draw.textlength(row, font=font) > width * scale for row in rows):
		size -= 1
		font = _font(role, size)
	return font, rows


def _draw_text(draw, text, xy, role, font_size, color, width, row_h, scale=1, keep_tokens=False):
	font, rows = _text_layout(text, role, font_size, width, scale, keep_tokens)
	for i, row in enumerate(rows):
		draw.text((xy[0], xy[1] + i * row_h * scale), row, font=font, fill=color, anchor="lt")


@lru_cache(maxsize=24)
def _subtitle_cues_cached(board_json, timeline_json):
	try:
		from .paper_subtitles import build_subtitle_cues, validate_subtitle_cues
	except ImportError:
		from paper_subtitles import build_subtitle_cues, validate_subtitle_cues
	board, timeline = json.loads(board_json), json.loads(timeline_json)
	if "subtitle_cues" in timeline:
		return validate_subtitle_cues(board, timeline, timeline["subtitle_cues"])
	return build_subtitle_cues(board, timeline)


def frame_at(board, timeline, time_seconds, size=(1920, 1080)):
	board = _canonical(board)
	if not math.isfinite(time_seconds):
		raise ValueError("paper time 必須有限")
	layout = layout_board(board)
	state = _state_at(board, timeline, time_seconds)
	meta = frame_metadata(board, timeline, time_seconds)
	th = _theme()
	image = Image.new("RGB", (W, H), th["canvas"]["bg"])
	draw = ImageDraw.Draw(image)
	cx, cy, scale = meta["camera"]
	for x in range(-W, 2 * W, 54):
		sx = W / 2 + (x - cx) * scale
		draw.line([(sx, VIEW_TOP), (sx, VIEW_BOTTOM)], fill=th["canvas"]["grid"], width=1)
	world_start = int(cy - H / scale) // 54 * 54
	for y in range(world_start, int(cy + H / scale), 54):
		sy = (VIEW_TOP + VIEW_BOTTOM) / 2 + (y - cy) * scale
		draw.line([(0, sy), (W, sy)], fill=th["canvas"]["grid"], width=1)
	_pencil(draw, [(188 + 3 * math.sin(i), VIEW_TOP + i * (VIEW_BOTTOM - VIEW_TOP) / 12) for i in range(13)], 1, th["canvas"]["margin"], 2)
	step = state["step"]
	local_changes = {(item["id"], item["index"]):item for item in meta["value_changes"]}
	flow_connections = {(item["id"], item["target_index"]):item for item in meta["arrows"]}
	for geom in layout["objects"]:
		oid = geom["id"]
		if oid not in meta["objects"]:
			continue
		g = meta["objects"][oid]
		if geom["kind"] == "code" and any(o["kind"] != "code" and o["id"] in state["visible"] for o in layout["objects"]):
			continue
		panel, factor = g["panel"], g["scale"]
		age = time_seconds - state["revealed"][oid]
		duration = max(.01, state["end"] - state["start"])
		reveal = _ease(age / min(.6, duration * .35))
		def outline(box, progress, color, fill=None, phase=0):
			phase += math.floor(time_seconds * 12) % 3
			x, y, w, h = (box[k] for k in ("x", "y", "w", "h"))
			if fill:
				draw.rectangle((x, y, x + w, y + h), fill=fill)
			points = [(x + w * j / 8 + 1.4 * factor * math.sin(j * 2 + phase), y + 1.4 * factor * math.sin(j + phase)) for j in range(9)]
			points += [(x + w + 1.4 * factor * math.sin(j + phase), y + h * j / 8) for j in range(1, 9)]
			points += [(x + w * (1 - j / 8), y + h + 1.4 * factor * math.sin(j + phase)) for j in range(1, 9)]
			points += [(x + 1.4 * factor * math.sin(j + phase), y + h * (1 - j / 8)) for j in range(1, 9)]
			_pencil(draw, points, progress, color, 3 * factor, phase)
		if geom["kind"] == "code":
			outline(panel, reveal, th["code"]["bg"], th["code"]["bg"])
		label = g["elements"][oid + ":label"]
		if reveal > .03:
			_draw_text(draw, next(o["label"] for o in board["objects"] if o["id"] == oid), (label["x"], label["y"]), "title", geom["label_size"], th["code"]["normal"] if geom["kind"] == "code" else th["text"]["muted"], geom["panel"]["w"] - 2 * PAD, 48, factor)
			_pencil(draw, [(label["x"], label["y"] + label["h"] + 12 * factor), (label["x"] + min(label["w"] + 80 * factor, panel["w"] - 2 * PAD * factor), label["y"] + label["h"] + 12 * factor)], reveal, th["text"]["accent"], 3 * factor)
		values = state["values"][oid]
		changes = state["changed"].get(oid, [])
		if meta["scan"] and meta["scan"].get("output_id") == oid:
			values, changes = [meta["scan"]["output_text"]], []
		for i, slot in enumerate(g["slots"]):
			if i >= len(values):
				continue
			sp = _ease((age - min(.10, duration * .15 / max(1, len(values) - 1)) * i) / min(.6, duration * .3))
			if geom["kind"] in ("cells", "flow"):
				outline(slot, sp, th["effects"]["pencil"], th["card"]["fill"] if sp > .03 else None, i)
			elif geom["kind"] == "text":
				# 文字是紙上相連節點，不是全幅清單卡。
				_pencil(draw, [(slot["x"], slot["y"] + slot["h"]), (slot["x"] + slot["w"], slot["y"] + slot["h"])], sp, th["effects"]["pencil"], 2 * factor, i)
			if geom["kind"] == "flow" and i:
				connection = flow_connections[(oid, i)]
				_pencil(draw, connection["path"], sp, th["text"]["accent"], 2 * factor)
				_pencil(draw, connection["head"], sp, th["text"]["accent"], 2 * factor)
			p = _motion_progress(state, changes.index(i), len(changes), time_seconds) if i in changes else 1
			role = "code" if geom["kind"] == "code" else "body"
			color = th["code"]["normal"] if role == "code" else th["text"]["body"]
			if role == "code" and state["code_lines"].get(oid) == i:
				draw.rectangle((slot["x"], slot["y"], slot["x"] + slot["w"], slot["y"] + slot["h"]), fill=th["code"]["highlight"])
			pos = (slot["x"] + 16 * factor, slot["y"] + 20 * factor)
			if sp > .1 or age > duration:
				local = local_changes.get((oid, i))
				if local:
					# 原位變字先退舊字，再進新字；不捏造跨物件飛行來源。
					background = th["card"]["fill"] if geom["kind"] in ("cells", "flow") else th["canvas"]["bg"]
					for phase in ("old", "new"):
						if phase in local:
							entry = local[phase]
							_draw_text(draw, entry["text"], pos, role, geom["font_size"], _fade_color(color, background, entry["opacity"]), geom["slots"][i]["w"] - 32, geom["row_height"], factor, 'flow' if geom['kind']=='flow' else geom["kind"] == "cells")
				elif p >= 1:
					_draw_text(draw, values[i], pos, role, geom["font_size"], color, geom["slots"][i]["w"] - 32, geom["row_height"], factor, 'flow' if geom['kind']=='flow' else geom["kind"] == "cells")
	for flight in meta["flights"]:
		oid, i, pos = flight["id"], flight["index"], flight["position"]
		glyph = flight["glyph"]
		factor = glyph["scale"]
		# 飛行文字與 metadata 共用來源字級、行距與完整文字。
		path = flight["path"]
		if flight["draw_path"]:
			_pencil(draw, path, flight["progress"], th["canvas"]["margin"], factor)
		font = _font("body", glyph["font_size"])
		rows = glyph["rows"]
		for n, row in enumerate(rows):
			draw.text((pos[0], pos[1] - len(rows) * glyph["row_height"] / 2 + n * glyph["row_height"]), row, font=font, fill=th["text"]["accent"], anchor="mt")
	if meta["scan"]:
		x, y = meta["scan"]["position"]
		factor, radius = meta["scan"]["scale"], meta["scan"]["radius"]
		points = [(x + radius * math.cos(n * math.tau / 32), y + radius * math.sin(n * math.tau / 32)) for n in range(33)]
		_pencil(draw, points, 1, th["text"]["accent"], 3 * factor)
		_pencil(draw, [(x - 5 * factor, y + radius + 2 * factor), (x, y + radius + 10 * factor),
			(x + 5 * factor, y + radius + 2 * factor)], 1, th["text"]["accent"], 3 * factor)
	hint = meta["code_hint"]
	if hint:
		b = hint["panel"]
		layer = Image.new("RGBA", (W, H))
		ld = ImageDraw.Draw(layer)
		ld.rectangle((b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]), fill=th["code"]["bg"])
		ld.text((b["x"] + 36, b["y"] + 34), "執行到這一行", font=_font("body", 38), fill=th["code"]["normal"], anchor="lt")
		for entry in hint["render_lines"]:
			ty = entry["top"]
			if entry["line"] == hint["focus_line"]:
				ld.rectangle((b["x"] + 22, ty - 8, b["x"] + b["w"] - 22, ty + len(entry["rows"]) * entry["row_height"]), fill=th["code"]["highlight"])
			for n, row in enumerate(entry["rows"]):
				ld.text((b["x"] + 36, ty + n * entry["row_height"]), row, font=_font("code", entry["font_size"]), fill=th["code"]["normal"], anchor="lt")
		layer.putalpha(layer.getchannel("A").point(lambda a: round(a * hint["opacity"])))
		image.paste(layer, (0, 0), layer)
		draw = ImageDraw.Draw(image)
	draw.rectangle((0, 0, W, VIEW_TOP), fill=th["canvas"]["bg"])
	draw.rectangle((0, VIEW_BOTTOM, W, H), fill=th["canvas"]["bg"])
	title = " ".join((state["scene"]["title"] if state["scene"] else board["title"]).split())
	font_size = 46
	while draw.textlength(title, font=_font("title", font_size)) > W - 160:
		font_size -= 2
	draw.text((72, 38), title, font=_font("title", font_size), fill=th["text"]["title"], anchor="lt")
	try:
		from .paper_subtitles import subtitle_at
	except ImportError:
		from paper_subtitles import subtitle_at
	# 以完整內容為 cache key；外部修改 timeline 會重新驗 ID、全文與時間。
	cues = _subtitle_cues_cached(json.dumps(board, ensure_ascii=False, sort_keys=True), json.dumps(timeline, ensure_ascii=False, sort_keys=True))
	caption = subtitle_at(cues, time_seconds)
	rows = _wrap(caption, _font("body", 40), W - 200)
	for i, row in enumerate(rows):
		draw.text((W / 2, 952 + i * 48), row, font=_font("body", 40), fill=th["text"]["body"], anchor="mt")
	return image if tuple(size) == (W, H) else image.resize(size, Image.Resampling.LANCZOS)

def render_previews(board, out_dir):
	board = _canonical(board)
	out = Path(out_dir)
	out.mkdir(parents=True, exist_ok=True)
	layout = layout_board(board)
	steps, cursor = [], 0
	for scene in board["scenes"]:
		for step in scene["steps"]:
			steps.append({"scene_id": scene["id"], "step_id": step["id"], "start": cursor, "end": cursor + 1.5})
			cursor += 1.7
	timeline = {"steps": steps, "duration": cursor}
	for i, scene in enumerate(board["scenes"], 1):
		last = next(e for e in reversed(steps) if e["scene_id"] == scene["id"])
		frame_at(board, timeline, last["end"]).save(out / f"slide_{i:02d}_full.png")
	(out / "layout.json").write_text(json.dumps(layout, ensure_ascii=False, indent=2), encoding="utf-8")
	return layout


def _srt_time(seconds):
	ms = round(seconds * 1000)
	return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def compile_paper_audio(board, wavs, out_dir):
	board = _canonical(board)
	out = Path(out_dir)
	out.mkdir(parents=True, exist_ok=True)
	chunks, entries = [], []
	format_key, cursor = None, 0
	for scene in board["scenes"]:
		for step in scene["steps"]:
			with wave.open(str(wavs[step["id"]]), "rb") as wav:
				fmt = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype())
				if fmt[0] != 1 or fmt[1] != 2 or fmt[2] <= 0 or fmt[3] != "NONE":
					raise ValueError("paper audio 需要 mono PCM16 WAV")
				if format_key is not None and fmt != format_key:
					raise ValueError("paper audio WAV 格式必須一致")
				format_key = fmt
				n = wav.getnframes()
				pcm = wav.readframes(n)
				if n <= 0 or len(pcm) != n * 2:
					raise ValueError("paper audio WAV 空白或不完整")
			sr = fmt[2]
			entry = {"scene_id": scene["id"], "step_id": step["id"], "start": cursor / sr, "end": (cursor + n) / sr}
			entries.append(entry)
			pause = round(sr * .18)
			chunks.extend([pcm, b"\0\0" * pause])
			cursor += n + pause
	with wave.open(str(out / "master.wav"), "wb") as master:
		master.setparams((1, 2, format_key[2], 0, "NONE", "not compressed"))
		for chunk in chunks:
			master.writeframes(chunk)
	timeline = {"duration": cursor / format_key[2], "sample_rate": format_key[2], "steps": entries}
	try:
		from .paper_subtitles import build_subtitle_cues
	except ImportError:
		from paper_subtitles import build_subtitle_cues
	fragment_path = out / "speech_fragments.json"
	fragments = json.loads(fragment_path.read_text(encoding="utf-8")) if fragment_path.exists() else None
	timeline["subtitle_cues"] = build_subtitle_cues(board, timeline, fragments)
	subtitles = [f'{i}\n{_srt_time(cue["start"])} --> {_srt_time(cue["end"])}\n{cue["text"]}\n' for i, cue in enumerate(timeline["subtitle_cues"], 1)]
	(out / "subtitles.srt").write_text("\n".join(subtitles), encoding="utf-8")
	(out / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
	return timeline


def _cancelled(cancelled):
	return cancelled is not None and (cancelled.is_set() if hasattr(cancelled, "is_set") else cancelled())


def _stop_process(process):
	if process.poll() is None:
		try:
			process.terminate()
		except ProcessLookupError:
			pass
		try:
			process.wait(timeout=3)
		except subprocess.TimeoutExpired:
			process.kill()
			process.wait()


def render_paper_video(board, timeline, master_audio, video_path, cancelled=None):
	video = Path(video_path)
	partial = video.with_name(video.stem + ".part.mp4")
	if video.exists() or partial.exists():
		raise FileExistsError("paper video 輸出已存在")
	if _cancelled(cancelled):
		raise RuntimeError("paper video cancelled")
	board = _canonical(board)
	_timeline(board, timeline)
	video.parent.mkdir(parents=True, exist_ok=True)
	duration = timeline["duration"]
	# 先以 exclusive create 取得 partial 所有權，清理只能刪除此工作建立的檔案。
	partial_fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
	os.close(partial_fd)
	command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-i", str(master_audio), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", str(duration), str(partial)]
	process = None
	watcher, watcher_stop = None, threading.Event()
	try:
		with tempfile.TemporaryFile() as log:
			process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
			def watch_cancel():
				while not watcher_stop.wait(.05):
					if _cancelled(cancelled):
						_stop_process(process)
						return
			if cancelled is not None:
				watcher = threading.Thread(target=watch_cancel, daemon=True)
				watcher.start()
			for index in range(math.ceil(duration * FPS)):
				if _cancelled(cancelled):
					raise RuntimeError("paper video cancelled")
				try:
					process.stdin.write(frame_at(board, timeline, index / FPS).tobytes())
				except OSError:
					if _cancelled(cancelled):
						raise RuntimeError("paper video cancelled") from None
					raise
			try:
				process.stdin.close()
			except OSError:
				if _cancelled(cancelled):
					raise RuntimeError("paper video cancelled") from None
				raise
			while True:
				if _cancelled(cancelled):
					raise RuntimeError("paper video cancelled")
				try:
					status = process.wait(timeout=.2)
					break
				except subprocess.TimeoutExpired:
					continue
			if status:
				log.seek(0)
				raise RuntimeError(f'paper FFmpeg exit {status}: {log.read(4096).decode("utf-8", "replace")}')
		if _cancelled(cancelled):
			raise RuntimeError("paper video cancelled")
		# link 是不可覆寫的原子發佈，即使另一工作同時寫入也保留對方產物。
		os.link(partial, video)
		partial.unlink()
		return video
	finally:
		watcher_stop.set()
		if process is not None:
			_stop_process(process)
			if watcher is not None:
				watcher.join(timeout=4)
			if process.stdin and not process.stdin.closed:
				try:
					process.stdin.close()
				except OSError:
					pass
		if partial.exists():
			partial.unlink()
