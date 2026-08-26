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
  掃描線　　程式碼首次走讀時一道光等速掃過，表示「正在逐行讀」
  退場淡出　所有強調效果收尾都淡掉，不再瞬間消失
  依序進場　同時觸發的多個 reveal 由上到下錯開，不會整塊蹦出來
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image
from scipy.io import wavfile

from motion import (CAMERA_MS, DIM_IN_MS, EXIT_RATIO, HL_WIPE_MS, SCAN_MS,
	TRANS_MS, UL_WIPE_MS)

REVEAL_SHIFT = 30     # 左移淡入的位移；再大就是動作疲勞，再小就看不出方向
UL_H = 6              # 底線中段最寬處
REVEAL_OVERSHOOT = 0.05   # 落位過衝，紙感材質上限（教學內容偏穩重，不用彈性材質的 15–25%）
CAM_OVERSHOOT = 0.02      # 鏡頭推近的過衝，像真的攝影機推到定位再回穩
SCAN_ALPHA = 0.30     # 掃描線最濃處
SCAN_TAIL = 46        # 掃描線拖尾長度（像素）        # 掃描線拖尾長度（像素）


def _bezier(x1, y1, x2, y2):
	"""標準 cubic-bezier，牛頓法解 t 再取 y"""
	def curve(a, b, t):
		u = 1 - t
		return 3 * u * u * t * a + 3 * u * t * t * b + t * t * t

	def f(p):
		p = max(0.0, min(1.0, p))
		if p <= 0 or p >= 1:
			return p
		t = p
		for _ in range(6):
			dx = curve(x1, x2, t) - p
			if abs(dx) < 1e-5:
				break
			d = 3 * (1 - t) ** 2 * x1 + 6 * (1 - t) * t * (x2 - x1) + 3 * t * t * (1 - x2)
			if abs(d) < 1e-6:
				break
			t = max(0.0, min(1.0, t - dx / d))
		return curve(y1, y2, t)
	return f


# 進場用 ease-out、退場用 ease-in、畫面內位移用 ease-in-out——三者不可互換，
# 混用就是「動起來很機械」的來源。數值取自 Material Design 3 的標準曲線。
ease_enter = _bezier(0.05, 0.7, 0.1, 1)    # 進場：一開始就衝出去，尾巴慢慢收
ease_exit = _bezier(0.3, 0, 1, 1)          # 退場：慢慢起步，最後加速離開
ease_move = _bezier(0.2, 0, 0, 1)          # 畫面內位移：鏡頭、換頁


_BACK_C1 = {}


def back_c1(overshoot):
	"""解出 back-out 的係數 c1，讓峰值恰好是 1 + overshoot。
	峰值 = 4c1³ / (27(c1+1)²)，沒有漂亮的解析解，用二分法算一次就快取起來"""
	if overshoot not in _BACK_C1:
		lo, hi = 0.0, 10.0
		for _ in range(60):
			mid = (lo + hi) / 2
			if 4 * mid ** 3 / (27 * (mid + 1) ** 2) < overshoot:
				lo = mid
			else:
				hi = mid
		_BACK_C1[overshoot] = (lo + hi) / 2
	return _BACK_C1[overshoot]


def back_out(p, overshoot):
	"""落位過衝：衝過頭一點再回穩，峰值 1 + overshoot。等速停死會很死板"""
	c1 = back_c1(overshoot)
	q = max(0.0, min(1.0, p)) - 1
	return 1 + (c1 + 1) * q ** 3 + c1 * q ** 2


def exit_alpha(t, end_ms, in_ms):
	"""效果收尾：退場時長 = 進場的 70%，不再瞬間消失"""
	out_ms = in_ms * EXIT_RATIO
	left = end_ms - t
	if left >= out_ms:
		return 1.0
	return max(0.0, 1 - ease_exit(1 - left / out_ms))


def blend(frame, y0, y1, x0, x1, col, a):
	"""把一塊純色以 a 疊上去；a < 1 用混色而不是硬蓋，效果才淡得掉"""
	if y1 <= y0 or x1 <= x0 or a <= 0:
		return
	dst = frame[y0:y1, x0:x1].astype(np.float32)
	frame[y0:y1, x0:x1] = (dst * (1 - a) + col * a).astype(np.uint8)


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


def apply_reveals(frame, full, scene, t, canvas_w):
	"""hidden 元素從左側平移淡入。位移帶微幅過衝，透明度不過衝——
	亮度衝過頭會變成閃一下。同時觸發的多個元素在編譯期就錯開了（見 compile_timeline）"""
	for r in scene["reveals"]:
		if t < r["start_ms"]:
			continue
		raw = min(1.0, (t - r["start_ms"]) / r["ms"]) if r["ms"] else 1.0
		a = ease_enter(raw)
		pos = back_out(raw, REVEAL_OVERSHOOT)
		b = r["box"]
		x, y, w, h = b["x"], b["y"], b["w"], b["h"]
		shift = int(round(REVEAL_SHIFT * (1 - pos)))
		dx = min(max(0, x - shift), max(0, canvas_w - w))
		patch = full[y:y + h, x:x + w].astype(np.float32)
		dst = frame[y:y + h, dx:dx + w]
		if dst.shape[:2] != patch.shape[:2]:
			continue
		frame[y:y + h, dx:dx + w] = (dst.astype(np.float32) * (1 - a) + patch * a).astype(np.uint8)
	return frame


def apply_highlight(frame, eff, t, hl):
	"""螢光筆：正片疊底刷過重點，深色文字仍然清楚。收尾用退場曲線淡掉"""
	b = eff["box"]
	p = ease_enter(min(1.0, (t - eff["start_ms"]) / HL_WIPE_MS))
	out = exit_alpha(t, eff["end_ms"], HL_WIPE_MS)
	w = int(b["w"] * p)
	if w <= 0 or out <= 0:
		return frame
	region = frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + w].astype(np.float32)
	tint = 1 - (1 - np.array(hl, dtype=np.float32) / 255.0) * out
	frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + w] = np.clip(region * tint, 0, 255).astype(np.uint8)
	return frame


def apply_scan(frame, region, start_ms, t, col, out):
	"""掃描線：等速由上往下掃過整塊程式碼一趟，帶漸層拖尾。
	等速是命門——加了緩動會讀成「有人在拖進度條」，而不是「機器在讀」。
	只掃程式碼區塊內，漏出去就變成掃整個畫面。"""
	prog = (t - start_ms) / SCAN_MS
	if prog < 0 or prog > 1:
		return frame
	rx, ry, rw, rh = region["x"], region["y"], region["w"], region["h"]
	head = min(ry + int(prog * rh), ry + rh)
	top = max(ry, head - SCAN_TAIL)
	edge = min(1.0, prog / 0.12) * min(1.0, (1 - prog) / 0.12)
	c = np.array(col, dtype=np.float32)
	if head > top:
		rows = np.arange(top, head, dtype=np.float32)
		a = ((rows - top) / max(1.0, head - top)) ** 2 * SCAN_ALPHA * out * edge
		strip = frame[top:head, rx:rx + rw].astype(np.float32)
		a3 = a[:, None, None]
		frame[top:head, rx:rx + rw] = (strip * (1 - a3) + c * a3).astype(np.uint8)
	blend(frame, head, min(head + 2, ry + rh), rx, rx + rw, c, SCAN_ALPHA * 1.6 * out * edge)
	return frame


def apply_code_focus(frame, eff, t, fade_rgb, border_rgb):
	"""程式碼走讀：未聚焦的行往底色淡出（不是壓黑），目標行保持原亮度並加左側範圍括號。
	該頁第一次進入走讀時，另有一道掃描線掃過整塊程式碼——程式碼本身全程靜止，只有光在動"""
	region = eff.get("region")
	if not region:
		return frame
	p = min(1.0, (t - eff["start_ms"]) / DIM_IN_MS)
	out = exit_alpha(t, eff["end_ms"], DIM_IN_MS)
	if out <= 0:
		return frame
	b = eff["box"]
	rx, ry, rw, rh = region["x"], region["y"], region["w"], region["h"]
	keep = frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]].copy()
	patch = frame[ry:ry + rh, rx:rx + rw].astype(np.float32)
	fade = np.array(fade_rgb, dtype=np.float32)
	a = eff.get("dim", 0.62) * ease_enter(p) * out
	frame[ry:ry + rh, rx:rx + rw] = (patch * (1 - a) + fade * a).astype(np.uint8)
	frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]] = keep
	if eff.get("scan"):
		frame = apply_scan(frame, region, eff.get("scan_at", eff["start_ms"]), t, border_rgb, out)
	# 左側範圍括號：豎線由上往下畫出，上下各一短勾標出涵蓋幾行
	col = np.array(border_rgb, dtype=np.float32)
	bx = max(0, b["x"] - 16)
	grow = ease_enter(p)
	spine = int(b["h"] * grow)
	blend(frame, b["y"], b["y"] + spine, bx, bx + 4, col, out)
	if grow > 0.85:
		tick = int(14 * (grow - 0.85) / 0.15)
		blend(frame, b["y"], b["y"] + 4, bx, bx + tick, col, out)
		blend(frame, b["y"] + b["h"] - 4, b["y"] + b["h"], bx, bx + tick, col, out)
	return frame


def apply_underline(frame, eff, t, col):
	"""馬克筆底線：貼著字底由左往右一筆畫出。中段最寬、首尾略細、邊緣輕微毛糙，
	這三件事讓它讀起來像人拿筆劃的，而不是 CSS 畫的框線。
	沒有筆尖圓點——那是裝飾雜訊，不帶任何教學資訊。"""
	b = eff["box"]
	pad = eff.get("pad", 0)
	total = max(1, b["w"] - pad * 2)
	p = ease_enter(min(1.0, (t - eff["start_ms"]) / UL_WIPE_MS))
	out = exit_alpha(t, eff["end_ms"], UL_WIPE_MS)
	w = int(total * p)
	if w <= 0 or out <= 0:
		return frame
	x0 = b["x"] + pad
	cy = b["y"] + b["h"] - pad + 1      # 貼著文字底部，離遠了會讀成分隔線
	hgt = UL_H + 3
	y0 = int(cy - hgt / 2)
	if y0 < 0 or y0 + hgt > frame.shape[0] or x0 + w > frame.shape[1]:
		return frame
	xs = np.arange(w, dtype=np.float32)
	u = np.clip(xs / max(1.0, total - 1), 0, 1)
	# clip 是必要的：float32 的 π 略大於真值，u=1 時 sin 會是極小負數，開根號變 NaN
	half = UL_H / 2 * (0.6 + 0.4 * np.clip(np.sin(np.pi * u), 0, 1) ** 0.5)
	rough = 0.35 * (np.sin(xs * 0.9) + np.sin(xs * 0.31))      # 太糙會讀成故障
	center = hgt / 2 + rough * 0.5
	rows = np.arange(hgt, dtype=np.float32)[:, None]
	a = np.clip(half + rough - np.abs(rows - center) + 0.5, 0, 1) * out
	strip = frame[y0:y0 + hgt, x0:x0 + w].astype(np.float32)
	c = np.array(col, dtype=np.float32)
	frame[y0:y0 + hgt, x0:x0 + w] = (strip * (1 - a[:, :, None]) + c * a[:, :, None]).astype(np.uint8)
	return frame


def zoom(img, cx, cy, scale, canvas):
	if scale <= 1.001:
		return img
	W, H = canvas["width"], canvas["height"]
	vw, vh = W / scale, H / scale
	x0 = min(max(0, cx - vw / 2), W - vw)
	y0 = min(max(0, cy - vh / 2), H - vh)
	# LANCZOS 而不是 BILINEAR：推近時中文字與等寬程式碼的筆畫才不會糊掉
	return img.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + vw, y0 + vh))


def apply_camera(img, cam, t, canvas):
	p = ease_move((t - cam["start_ms"]) / cam["ms"]) if cam["ms"] else 1.0
	W, H = canvas["width"], canvas["height"]
	if cam["box"] is None:
		return zoom(img, W / 2, H / 2, 1 + (cam.get("from_scale", 1.35) - 1) * (1 - p), canvas)
	b = cam["box"]
	# 推近帶微幅過衝：推到定位再回穩，比等速停住像真的攝影機
	q = back_out((t - cam["start_ms"]) / cam["ms"], CAM_OVERSHOOT) if cam["ms"] else 1.0
	return zoom(img, b["x"] + b["w"] / 2, b["y"] + b["h"] / 2,
		1 + (cam["scale"] - 1) * q, canvas)


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
		"-c:a", "aac", "-b:a", "192k", "-shortest",
		# moov 預設寫在檔尾，瀏覽器得整支拉完才知道時長。搬到檔頭才串得動
		"-movflags", "+faststart", out_mp4,
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
		frame = apply_reveals(frame, full, scene, t, W)

		for eff in active([e for e in scene["effects"] if e["type"] == "spotlight"], t):
			if eff.get("style") == "code":
				frame = apply_code_focus(frame, eff, t, fade_rgb, bar_rgb)
			else:
				frame = apply_highlight(frame, eff, t, hl_rgb)

		for eff in active([e for e in scene["effects"] if e["type"] == "laser"], t):
			frame = apply_underline(frame, eff, t, ul_rgb)

		# 沒有鏡頭動作就完全不進 PIL 重取樣：連續次像素縮放會讓中文字與程式碼發糊
		cams = active(scene["camera"], t)
		if cams:
			arr = np.asarray(apply_camera(Image.fromarray(frame), cams[-1], t, canvas)).copy()
		else:
			arr = frame

		# 換頁交叉淡化：記住上一頁最後一格，新頁前 TRANS_MS 內混合
		if idx != last_idx:
			trans_from, trans_until = last_frame, t + TRANS_MS
			last_idx = idx
		if trans_from is not None and t < trans_until:
			a = ease_move(1 - (trans_until - t) / TRANS_MS)
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
