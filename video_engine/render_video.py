#!/usr/bin/env python3
"""影片渲染：依 timeline.json 逐格合成畫面，接上音軌後由 FFmpeg 封裝。

用法：.venv/bin/python video_engine/render_video.py <lesson.json> [輸出目錄]

效果全部由時間軸驅動，這支程式不認識任何投影片內容，也不含任何座標常數。

效果語彙：
  螢光筆　文字重點由左往右刷過暖色底，不壓暗其他內容
  區域壓暗　只有程式碼走讀才壓暗，而且只壓程式碼區塊
  底線畫出　雷射改成由左往右畫出的底線，比細線明顯
  左移淡入　reveal 從左側平移進場
  交叉淡化　換頁不硬切
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw
from scipy.io import wavfile

HL_WIPE_MS = 380      # 螢光筆刷過的時間
DIM_IN_MS = 420       # 程式碼區域壓暗的淡入
UL_WIPE_MS = 260      # 底線畫出
REVEAL_SHIFT = 26     # 左移淡入的位移
TRANS_MS = 350        # 換頁交叉淡化
UL_H = 5


def ease_out(p):
	return 1.0 if p >= 1 else 1 - pow(2, -10 * p)


def ease_in_out(p):
	p = max(0.0, min(1.0, p))
	return 3 * p * p - 2 * p * p * p


def rgb(hex_str):
	h = hex_str.lstrip("#")
	return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def load_theme(name):
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "themes", f"{name}.json")
	return json.load(open(path, encoding="utf-8"))


def build_audio(timeline, out_wav):
	"""把各段語音放到時間軸上的正確位置，中間補靜音"""
	segs = [(n["start_ms"], n["wav"]) for s in timeline["scenes"] for n in s["narration"]]
	if not segs:
		raise SystemExit("時間軸沒有任何語音")
	sr, _ = wavfile.read(segs[0][1])
	track = np.zeros(int(timeline["total_ms"] / 1000 * sr) + sr // 2, dtype=np.int32)
	for start_ms, wav in segs:
		s_sr, data = wavfile.read(wav)
		if s_sr != sr:
			raise SystemExit(f"取樣率不一致：{wav}")
		mono = data[:, 0] if data.ndim > 1 else data
		at = int(start_ms / 1000 * sr)
		track[at:at + len(mono)] += mono.astype(np.int32)
	track = np.clip(track, -32768, 32767).astype(np.int16)
	wavfile.write(out_wav, sr, track)
	return sr, len(track) / sr


def apply_reveals(frame, full, scene, t):
	"""hidden 元素從左側平移淡入"""
	for r in scene["reveals"]:
		if t < r["start_ms"]:
			continue
		p = ease_out(min(1.0, (t - r["start_ms"]) / r["ms"])) if r["ms"] else 1.0
		b = r["box"]
		x, y, w, h = b["x"], b["y"], b["w"], b["h"]
		shift = int(REVEAL_SHIFT * (1 - p))
		dx = max(0, x - shift)
		patch = full[y:y + h, x:x + w].astype(np.float32)
		dst = frame[y:y + h, dx:dx + w]
		if dst.shape[:2] != patch.shape[:2]:
			continue
		frame[y:y + h, dx:dx + w] = (dst.astype(np.float32) * (1 - p) + patch * p).astype(np.uint8)
	return frame


def apply_highlight(frame, box, t, start_ms, hl):
	"""螢光筆：正片疊底刷過重點，深色文字仍然清楚"""
	p = ease_out(min(1.0, (t - start_ms) / HL_WIPE_MS))
	b = box
	w = int(b["w"] * p)
	if w <= 0:
		return frame
	region = frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + w].astype(np.float32)
	tint = np.array(hl, dtype=np.float32) / 255.0
	frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + w] = np.clip(region * tint, 0, 255).astype(np.uint8)
	return frame


def apply_code_focus(frame, eff, t, fade_rgb, border_rgb):
	"""程式碼走讀：未聚焦的行往底色淡出（不是壓黑），目標行保持原亮度並加左側色條"""
	p = min(1.0, (t - eff["start_ms"]) / DIM_IN_MS)
	region = eff.get("region")
	b = eff["box"]
	if not region:
		return frame
	rx, ry, rw, rh = region["x"], region["y"], region["w"], region["h"]
	keep = frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]].copy()
	patch = frame[ry:ry + rh, rx:rx + rw].astype(np.float32)
	fade = np.array(fade_rgb, dtype=np.float32)
	a = eff.get("dim", 0.62) * ease_out(p)
	frame[ry:ry + rh, rx:rx + rw] = (patch * (1 - a) + fade * a).astype(np.uint8)
	frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]] = keep
	# 左側範圍括號：豎線由上往下畫出，上下各一短勾標出涵蓋幾行
	col = np.array(border_rgb, dtype=np.uint8)
	bx = max(0, b["x"] - 16)
	grow = ease_out(p)
	spine = int(b["h"] * grow)
	if spine > 0:
		frame[b["y"]:b["y"] + spine, bx:bx + 4] = col
	if grow > 0.85:
		tick = int(14 * (grow - 0.85) / 0.15)
		frame[b["y"]:b["y"] + 4, bx:bx + tick] = col
		frame[b["y"] + b["h"] - 4:b["y"] + b["h"], bx:bx + tick] = col
	return frame


def apply_underline(img, eff, t, col):
	"""雷射改成底線由左往右畫出，收尾淡出"""
	span = max(1, eff["end_ms"] - eff["start_ms"])
	life = (t - eff["start_ms"]) / span
	fade = 1.0 if life < 0.72 else max(0.0, (1 - life) / 0.28)
	if fade <= 0:
		return img
	b = eff["box"]
	p = ease_out(min(1.0, (t - eff["start_ms"]) / UL_WIPE_MS))
	w = int(b["w"] * p)
	y = b["y"] + b["h"] - UL_H
	d = ImageDraw.Draw(img, "RGBA")
	d.rectangle([b["x"], y, b["x"] + w, y + UL_H], fill=col + (int(255 * fade),))
	if p >= 1:
		r = 9
		cx = b["x"] + b["w"]
		d.ellipse([cx - r, y + UL_H // 2 - r, cx + r, y + UL_H // 2 + r],
			fill=col + (int(230 * fade),))
	return img


def zoom(img, cx, cy, scale, canvas):
	if scale <= 1.001:
		return img
	W, H = canvas["width"], canvas["height"]
	vw, vh = W / scale, H / scale
	x0 = min(max(0, cx - vw / 2), W - vw)
	y0 = min(max(0, cy - vh / 2), H - vh)
	return img.resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + vw, y0 + vh))


def apply_camera(img, cam, t, canvas):
	p = ease_in_out((t - cam["start_ms"]) / cam["ms"]) if cam["ms"] else 1.0
	W, H = canvas["width"], canvas["height"]
	if cam["box"] is None:
		return zoom(img, W / 2, H / 2, 1 + (cam.get("from_scale", 1.35) - 1) * (1 - p), canvas)
	b = cam["box"]
	return zoom(img, b["x"] + b["w"] / 2, b["y"] + b["h"] / 2,
		1 + (cam["scale"] - 1) * p, canvas)


def active(items, t):
	return [i for i in items if i["start_ms"] <= t < i.get("end_ms", 10 ** 9)]


def main():
	if len(sys.argv) < 2:
		print(__doc__)
		return 2
	lesson = json.load(open(sys.argv[1], encoding="utf-8"))
	out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
		os.path.dirname(os.path.abspath(__file__)), "out", lesson["lesson_id"]
	)
	timeline = json.load(open(os.path.join(out_dir, "timeline.json"), encoding="utf-8"))
	theme = load_theme(timeline.get("theme") or lesson.get("theme", "warm"))
	fx = theme["effects"]
	fade_rgb, hl_rgb = rgb(fx["code_fade"]), rgb(fx["highlight"])
	ul_rgb, bar_rgb = rgb(fx["underline"]), rgb(fx["spotlight_border"])

	canvas, fps = timeline["canvas"], timeline["fps"]
	W, H = canvas["width"], canvas["height"]
	master_wav = os.path.join(out_dir, "master.wav")
	print("組音軌…")
	build_audio(timeline, master_wav)

	pages = {s["slide_id"]: (
		np.array(Image.open(s["base_png"]).convert("RGB")),
		np.array(Image.open(s["full_png"]).convert("RGB")),
	) for s in timeline["scenes"]}

	# 用輸出目錄名，才不會跟 lesson_id 不一致（同一份教材可能跑多種設定）
	out_mp4 = os.path.join(out_dir, os.path.basename(out_dir.rstrip("/")) + ".mp4")
	total_frames = int(timeline["total_ms"] / 1000 * fps)
	proc = subprocess.Popen([
		"ffmpeg", "-y", "-loglevel", "error",
		"-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
		"-i", master_wav,
		"-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
		"-c:a", "aac", "-b:a", "192k", "-shortest", out_mp4,
	], stdin=subprocess.PIPE)

	print(f"渲染 {total_frames} 格 @ {fps}fps…")
	t0 = time.time()
	last_idx, last_frame, trans_from, trans_until = -1, None, None, 0.0

	for f in range(total_frames):
		t = f * 1000 / fps
		idx = next((i for i, s in enumerate(timeline["scenes"])
			if s["start_ms"] <= t < s["end_ms"]), len(timeline["scenes"]) - 1)
		scene = timeline["scenes"][idx]
		base, full = pages[scene["slide_id"]]
		frame = base.copy()
		frame = apply_reveals(frame, full, scene, t)

		for eff in active([e for e in scene["effects"] if e["type"] == "spotlight"], t):
			if eff.get("style") == "code":
				frame = apply_code_focus(frame, eff, t, fade_rgb, bar_rgb)
			else:
				frame = apply_highlight(frame, eff["box"], t, eff["start_ms"], hl_rgb)

		img = Image.fromarray(frame)
		for eff in active([e for e in scene["effects"] if e["type"] == "laser"], t):
			img = apply_underline(img, eff, t, ul_rgb)

		cams = active(scene["camera"], t)
		if cams:
			img = apply_camera(img, cams[-1], t, canvas)
		# 沒有鏡頭動作就維持靜止：連續次像素縮放會讓中文字與程式碼一直重取樣發糊

		arr = np.asarray(img).copy()

		# 換頁交叉淡化：記住上一頁最後一格，新頁前 TRANS_MS 內混合
		if idx != last_idx:
			trans_from, trans_until = last_frame, t + TRANS_MS
			last_idx = idx
		if trans_from is not None and t < trans_until:
			a = ease_out(1 - (trans_until - t) / TRANS_MS)
			arr = (trans_from.astype(np.float32) * (1 - a) + arr.astype(np.float32) * a).astype(np.uint8)
		last_frame = arr

		proc.stdin.write(arr.tobytes())
		if f % (fps * 15) == 0:
			print(f"  {f / max(1, total_frames) * 100:4.0f}%", flush=True)

	proc.stdin.close()
	proc.wait()
	dur = time.time() - t0
	print(f"\n完成：{out_mp4}")
	print(f"影片 {total_frames / fps:.1f} 秒　檔案 {os.path.getsize(out_mp4) / 1e6:.1f} MB")
	print(f"渲染耗時 {dur:.0f} 秒（{total_frames / dur:.1f} 格/秒）")
	return 0


if __name__ == "__main__":
	sys.exit(main())
