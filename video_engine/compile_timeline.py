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

import motion
from motion import (CAMERA_MS, MIN_GAP_MS, REVEAL_MS_CARD, REVEAL_MS_HERO,
	REVEAL_MS_SMALL, SCAN_DELAY_MS, STAGGER_BUDGET_MS, STAGGER_MS, TRANS_MS)

FPS = 30
LASER_MS = 1200
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


def check_figure_subitems(boxes, kind, ref, sid, diags):
	"""B.5: spotlight 或 laser 指向含有子項目的示意圖整體時發出 WARN"""
	if kind not in ("spotlight", "laser"):
		return
	sub_keys = [k for k in boxes if re.match(rf"^{re.escape(ref)}:(i\d+|l\d+|r\d+)", k)]
	if sub_keys:
		sub_list = ", ".join(sorted(sub_keys))
		diags.append({"level": "warn", "slide": sid,
			"msg": f"{kind} 指向含有子項目的示意圖整體「{ref}」，應指向具體子項目（如 {sub_list}）"})


def calc_camera_scale(box, canvas):
	"""B.4: 計算聚光燈推近倍率：反向隨目標面積縮放，上限 1.4 倍，≥8% 不推近"""
	share = (box["w"] * box["h"]) / float(canvas["width"] * canvas["height"])
	if share >= 0.08:
		return share, None
	# 小於等於 1% 的小目標推滿 1.4 倍，1%~8% 反向平滑遞減至 ~1.05
	if share <= 0.01:
		scale = 1.4
	else:
		scale = round(min(1.4, 1.4 - ((share - 0.01) / 0.07) * 0.35), 2)
	return share, scale


def compile_slide(slide_actions, boxes, canvas, durations, sid, cursor):
	"""展開一頁的動作，回傳（場景, 新的游標時間, 診斷）"""
	scene = {"slide_id": sid, "start_ms": cursor, "narration": [], "effects": [],
		"reveals": [], "camera": []}
	diags = []
	t = cursor

	seq = 0
	for i, a in enumerate(slide_actions):
		kind = a["type"]
		seq += 0 if kind in BLOCKING else 1

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
				scene["camera"].append({"start_ms": t, "box": None, "scale": 1.0,
					"ms": CAMERA_MS, "seq": seq})
				continue
			box = resolve_box(boxes, a.get("target", ""), canvas)
			if box is None:
				diags.append({"level": "warn", "slide": sid, "msg": f"camera 找不到 {a.get('target')}，略過"})
				continue
			scene["camera"].append({"start_ms": t, "box": box,
				"scale": a.get("scale", 1.35), "ms": CAMERA_MS, "seq": seq})
			continue

		box = resolve_box(boxes, a.get("target", ""), canvas)
		if box is None:
			diags.append({"level": "warn", "slide": sid, "msg": f"{kind} 找不到 {a.get('target')}，略過"})
			continue

		ref = a.get("target", "")
		is_code = ":L" in ref
		if kind == "spotlight":
			# 文字與示意圖聚光燈：壓暗周圍＋配鏡頭推近
			eff = {"type": "spotlight", "start_ms": t, "end_ms": None, "box": box,
				"style": "code" if is_code else "text", "target": ref,
				"dim": a.get("dim", 0.62), "seq": seq}
			if is_code:
				eff["region"] = boxes.get(ref.split(":")[0])
			scene["effects"].append(eff)
			check_figure_subitems(boxes, kind, ref, sid, diags)

			# 推近只配給程式區塊，跟壓暗綁在一起。
			# 圖與條列配了推近反而暈——實測整片幾乎每一格都在做 LANCZOS 縮放，
			# 渲染時間從 95 秒變成 400 秒，畫面上卻看不出好處
			if is_code:
				share, scale = calc_camera_scale(box, canvas)
				if scale is not None:
					# 顯式 camera 動作由 LLM 產生、沒有幾何概念，實測會在聚光燈
					# 亮起的同時把鏡頭往後拉。同一時刻以自動配的為準
					scene["camera"] = [c for c in scene["camera"] if c["start_ms"] != t]
					scene["camera"].append({"start_ms": t, "box": box, "scale": scale,
						"ms": CAMERA_MS, "seq": seq, "auto": True, "target": ref})
		elif kind == "laser":
			scene["effects"].append({"type": "laser", "start_ms": t, "end_ms": t + LASER_MS,
				"box": box, "target": ref, "pad": BOX_PAD, "seq": seq})
			check_figure_subitems(boxes, kind, ref, sid, diags)
		elif kind == "reveal":
			scene["reveals"].append({"start_ms": t, "ms": reveal_ms(box, canvas),
				"box": box, "seq": seq})

	scene["end_ms"] = t
	settle_starts(scene)
	mark_first_scan(scene)
	clamp_lifetimes(scene)
	diags += lint_motion(scene)
	return scene, t, diags


def reveal_ms(box, canvas):
	"""進場時長依元素佔畫面的比例分級：小的快、大的慢，才不會每個元素都同一種節奏"""
	share = (box["w"] * box["h"]) / float(canvas["width"] * canvas["height"])
	if share < 0.02:
		return REVEAL_MS_SMALL
	if share < 0.10:
		return REVEAL_MS_CARD
	return REVEAL_MS_HERO


def settle_starts(scene):
	"""把同一刻擠在一起的動態起點排開，並讓頁首的動態等換頁交叉淡化走完。

	動作只寫語意代號、不寫時間碼（三層契約），所以「什麼時候動」全部落在編譯期。
	非阻塞動作連著寫會全部落在同一毫秒，一起蹦出來讀成一整塊；每頁第一個動作
	又必然落在頁首，撞上換頁淡化等於白做。這兩件事 LLM 無從避免，得在這裡解。

	排開順序照原始動作順序（seq），間距：reveal 之間 60ms，異類之間 80ms。
	每組總延後量壓在 STAGGER_BUDGET_MS 內，不然視覺會落後講稿太多。"""
	items = ([("reveal", r) for r in scene["reveals"]]
		+ [(e["type"], e) for e in scene["effects"]]
		+ [("camera", c) for c in scene["camera"]])
	if not items:
		return
	groups = {}
	for kind, it in items:
		groups.setdefault(it["start_ms"], []).append((kind, it))

	floor = scene["start_ms"] + TRANS_MS   # 換頁淡化走完前不要動
	prev_end = None
	for base in sorted(groups):
		group = sorted(groups[base], key=lambda p: p[1].get("seq", 0))
		at = max(base, floor)
		if prev_end is not None:
			at = max(at, prev_end)
		budget = at + STAGGER_BUDGET_MS
		last_kind = None
		for kind, it in group:
			if last_kind is not None:
				gap = STAGGER_MS if (kind == "reveal" and last_kind == "reveal") else MIN_GAP_MS
				at = min(at + gap, budget)
			it["start_ms"] = int(at)
			last_kind = kind
		prev_end = at


def mark_first_scan(scene):
	"""掃描線只在該頁第一次進入程式碼走讀時掃一趟。
	每次聚焦都掃會變成裝飾，掃一次才是「開始讀這段程式碼」的宣告。
	起掃時間另外記——第一個聚焦通常就落在頁首，會跟換頁淡化撞在一起"""
	for e in scene["effects"]:
		if e["type"] == "spotlight" and e.get("style") == "code":
			e["scan"] = True
			e["scan_at"] = max(e["start_ms"], scene["start_ms"] + SCAN_DELAY_MS)
			return


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

	# 鏡頭動作時序與前後狀態銜接
	scene["camera"].sort(key=lambda c: c["start_ms"])
	cams = scene["camera"]
	for a, b in zip(cams, cams[1:]):
		a["end_ms"] = b["start_ms"]
	if cams:
		cams[-1]["end_ms"] = end

	prev_box = None
	prev_scale = 1.0
	for c in cams:
		c["from_box"] = prev_box
		c["from_scale"] = prev_scale
		prev_box = c.get("box")
		prev_scale = c.get("scale", 1.0)


def lint_motion(scene):
	"""時序 lint：settle_starts 排得開的都排掉了，這裡只報排不掉的。

	編排閘管語意（target 解不解得開、密度會不會太高），這裡管時間軸。
	效果活太短是講稿驅動的——那段語音就是那麼短，只能回頭改講稿。"""
	diags = []
	sid = scene["slide_id"]
	for e in scene["effects"]:
		in_ms = motion.enter_ms(e)
		out_ms = motion.exit_ms(in_ms)
		life = e["end_ms"] - e["start_ms"]
		if life < in_ms + out_ms:
			diags.append({"level": "warn", "slide": sid,
				"msg": f"{e['type']} {e.get('target')} 只活 {life}ms，"
					f"畫不完進場 {in_ms}ms＋退場 {out_ms:.0f}ms，會抽動——把那段講稿講長一點"})

	# 安全網：settle_starts 若哪天改壞了，這兩條會叫
	starts = ([("reveal", r["start_ms"]) for r in scene["reveals"]]
		+ [(e["type"], e["start_ms"]) for e in scene["effects"]]
		+ [("camera", c["start_ms"]) for c in scene["camera"]])
	for kind, t in starts:
		if t < scene["start_ms"] + TRANS_MS:
			diags.append({"level": "error", "slide": sid,
				"msg": f"{kind} 在換頁淡化走完前 {t - scene['start_ms']}ms 起動，settle_starts 沒排開"})
	starts.sort(key=lambda p: p[1])
	for (k0, t0), (k1, t1) in zip(starts, starts[1:]):
		if t1 - t0 < (STAGGER_MS if k0 == k1 == "reveal" else MIN_GAP_MS):
			diags.append({"level": "error", "slide": sid,
				"msg": f"{k0} 與 {k1} 只差 {t1 - t0}ms，settle_starts 沒排開"})
	return diags


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
