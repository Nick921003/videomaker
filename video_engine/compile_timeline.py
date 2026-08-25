#!/usr/bin/env python3
"""時間軸編譯器：把 index 域的動作序列展開成 wall-clock 時間軸。

用法：.venv/bin/python video_engine/compile_timeline.py <lesson.json> <actions.json> [輸出目錄]

純函式：只讀 layout.json 的實測幾何與 durations.json 的實測音長，
不碰 GPU、不碰 FFmpeg。輸出 timeline.json 與 subtitles.srt。
"""
import json
import os
import re
import sys

FPS = 30
LASER_MS = 1200
REVEAL_MS = 320
CAMERA_MS = 600
MAX_HOLD_MS = 9000    # 強調效果最長停留，避免整頁一直掛著
PAUSE_DEFAULT_MS = 300
BOX_PAD = 16
BLOCKING = {"speech", "pause"}

REF_RE = re.compile(r"^([a-z0-9_]+)(?::L(\d+)(?:-L(\d+))?)?$")



def resolve_box(boxes, ref, canvas):
	"""元素代號 → 實測方框。行範圍會取聯集，figure 部件直接查表。找不到回 None"""
	if ref in boxes:
		b = boxes[ref]
		x, y = max(0, b["x"] - BOX_PAD), max(0, b["y"] - BOX_PAD)
		return {"x": round(x), "y": round(y),
			"w": round(min(canvas["width"] - x, b["w"] + BOX_PAD * 2)),
			"h": round(min(canvas["height"] - y, b["h"] + BOX_PAD * 2))}
	m = REF_RE.match(ref)
	if not m:
		return None
	base, lo, hi = m.group(1), m.group(2), m.group(3)
	if lo is None:
		box = boxes.get(base)
		parts = [box] if box else []
	else:
		lo, hi = int(lo), int(hi or lo)
		parts = [boxes[f"{base}:L{i}"] for i in range(lo, hi + 1) if f"{base}:L{i}" in boxes]
	if not parts:
		return None

	x = min(p["x"] for p in parts)
	y = min(p["y"] for p in parts)
	w = max(p["x"] + p["w"] for p in parts) - x
	h = max(p["y"] + p["h"] for p in parts) - y
	# 加安全邊距，並夾在畫布內
	x, y = max(0, x - BOX_PAD), max(0, y - BOX_PAD)
	w = min(canvas["width"] - x, w + BOX_PAD * 2)
	h = min(canvas["height"] - y, h + BOX_PAD * 2)
	return {"x": round(x), "y": round(y), "w": round(w), "h": round(h)}


def compile_slide(slide_actions, boxes, canvas, durations, sid, cursor):
	"""展開一頁的動作，回傳（場景, 新的游標時間, 診斷）"""
	scene = {"slide_id": sid, "start_ms": cursor, "narration": [], "effects": [],
		"reveals": [], "camera": []}
	diags = []
	t = cursor

	for i, a in enumerate(slide_actions):
		kind = a["type"]

		if kind == "speech":
			rec = durations.get(f"{sid}#{i}")
			if not rec:
				diags.append({"level": "error", "slide": sid, "msg": f"第 {i} 個動作缺少音檔時長"})
				continue
			ms = int(rec["duration"] * 1000)
			scene["narration"].append({
				"start_ms": t, "end_ms": t + ms, "wav": rec["wav"], "text": rec["text"],
			})
			t += ms
			continue

		if kind == "pause":
			t += a.get("ms", PAUSE_DEFAULT_MS)
			continue

		# 以下皆為非阻塞：只是觸發，不推進游標
		if kind == "camera":
			if a.get("reset"):
				scene["camera"].append({"start_ms": t, "box": None, "scale": 1.0, "ms": CAMERA_MS})
				continue
			box = resolve_box(boxes, a.get("target", ""), canvas)
			if box is None:
				diags.append({"level": "warn", "slide": sid, "msg": f"camera 找不到 {a.get('target')}，略過"})
				continue
			scene["camera"].append({"start_ms": t, "box": box,
				"scale": a.get("scale", 1.35), "ms": CAMERA_MS})
			continue

		box = resolve_box(boxes, a.get("target", ""), canvas)
		if box is None:
			diags.append({"level": "warn", "slide": sid, "msg": f"{kind} 找不到 {a.get('target')}，略過"})
			continue

		ref = a.get("target", "")
		is_code = ":L" in ref
		if kind == "spotlight":
			# 文字用螢光筆，程式碼才壓暗（只壓程式碼區塊，不壓整頁）
			eff = {"type": "spotlight", "start_ms": t, "end_ms": None, "box": box,
				"style": "code" if is_code else "text", "target": ref}
			if is_code:
				eff["region"] = boxes.get(ref.split(":")[0])
				eff["dim"] = a.get("dim", 0.62)
			scene["effects"].append(eff)
		elif kind == "laser":
			scene["effects"].append({"type": "laser", "start_ms": t, "end_ms": t + LASER_MS,
				"box": box, "target": ref})
		elif kind == "reveal":
			scene["reveals"].append({"start_ms": t, "ms": REVEAL_MS, "box": box})

	scene["end_ms"] = t
	clamp_lifetimes(scene)
	return scene, t, diags


def clamp_lifetimes(scene):
	"""聚光燈講完那段就收，畫面回到全亮；不再一路壓暗到頁尾"""
	end = scene["end_ms"]
	spots = [e for e in scene["effects"] if e["type"] == "spotlight"]
	narr = scene["narration"]
	for i, sp in enumerate(spots):
		# 它引出的那段語音講完就結束
		after = [n for n in narr if n["start_ms"] >= sp["start_ms"]]
		stop = after[0]["end_ms"] if after else sp["start_ms"] + MAX_HOLD_MS
		nxt = spots[i + 1]["start_ms"] if i + 1 < len(spots) else end
		sp["end_ms"] = min(stop, nxt, sp["start_ms"] + MAX_HOLD_MS, end)
	for e in scene["effects"]:
		e["end_ms"] = min(e["end_ms"] if e["end_ms"] is not None else end, end)

	cams = scene["camera"]
	for a, b in zip(cams, cams[1:]):
		a["end_ms"] = b["start_ms"]
	if cams:
		cams[-1]["end_ms"] = end


def to_srt(cues):
	def stamp(ms):
		h, ms = divmod(ms, 3600000)
		m, ms = divmod(ms, 60000)
		s, ms = divmod(ms, 1000)
		return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

	out = []
	for n, c in enumerate(cues, start=1):
		out.append(f"{n}\n{stamp(c['start_ms'])} --> {stamp(c['end_ms'])}\n{c['text']}\n")
	return "\n".join(out)


def main():
	if len(sys.argv) < 3:
		print(__doc__)
		return 2
	lesson = json.load(open(sys.argv[1], encoding="utf-8"))
	actions = json.load(open(sys.argv[2], encoding="utf-8"))
	out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
		os.path.dirname(os.path.abspath(__file__)), "out", lesson["lesson_id"]
	)

	layout = json.load(open(os.path.join(out_dir, "layout.json"), encoding="utf-8"))
	durations = json.load(open(os.path.join(out_dir, "durations.json"), encoding="utf-8"))
	canvas = layout["canvas"]
	pages = {s["slide_id"]: s for s in layout["slides"]}

	timeline = {"lesson_id": lesson["lesson_id"], "fps": FPS, "canvas": canvas,
		"scenes": [], "subtitles": [], "diagnostics": []}
	cursor = 0

	for slide in actions["slides"]:
		sid = slide["slide_id"]
		page = pages[sid]
		scene, cursor, diags = compile_slide(
			slide["actions"], page["boxes"], canvas, durations, sid, cursor
		)
		scene["base_png"] = page["png"]
		scene["full_png"] = page["png_full"]
		timeline["scenes"].append(scene)
		timeline["diagnostics"] += diags
		for n in scene["narration"]:
			timeline["subtitles"].append({"start_ms": n["start_ms"], "end_ms": n["end_ms"],
				"text": n["text"]})

	timeline["total_ms"] = cursor
	tl_path = os.path.join(out_dir, "timeline.json")
	srt_path = os.path.join(out_dir, "subtitles.srt")
	json.dump(timeline, open(tl_path, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
	open(srt_path, "w", encoding="utf-8").write(to_srt(timeline["subtitles"]))

	print(f"總長 {cursor / 1000:.1f} 秒，{len(timeline['scenes'])} 個場景")
	for s in timeline["scenes"]:
		spots = sum(1 for e in s["effects"] if e["type"] == "spotlight")
		lasers = sum(1 for e in s["effects"] if e["type"] == "laser")
		print(f"  {s['slide_id']}  {s['start_ms'] / 1000:6.1f}s → {s['end_ms'] / 1000:6.1f}s"
			f"　語音 {len(s['narration'])}　聚光 {spots}　雷射 {lasers}"
			f"　浮現 {len(s['reveals'])}　鏡頭 {len(s['camera'])}")
	for d in timeline["diagnostics"]:
		print(f"  {d['level'].upper()} [{d['slide']}] {d['msg']}")
	print(f"時間軸：{tl_path}")
	print(f"字幕　：{srt_path}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
