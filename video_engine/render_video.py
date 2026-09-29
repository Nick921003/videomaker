#!/usr/bin/env python3
"""影片渲染：依 timeline.json 逐格合成畫面，接上音軌後由 FFmpeg 封裝。

用法：.venv/bin/python video_engine/render_video.py <lesson.json> [輸出目錄]

效果全部由時間軸驅動，這支程式不認識任何投影片內容，也不含任何座標常數。

效果語彙：
  語意焦點　程式碼用側軌、文字用底線、圖示用圈選；同一目標的 spotlight/laser 共用形狀
  程式碼走讀　非目標行淡化，目標行保持原色並沿用焦點側軌
  左移淡入　reveal 從左側平移進場
  場景過場　前頁先退至主題底面，新頁再進場，不疊字
  鏡頭推近　只在有相機動作時重取樣
  退場淡出　所有強調效果收尾都淡掉
  依序進場　同時觸發的多個 reveal 由上到下錯開
"""
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw
from scipy.io import wavfile

from layout import CODE_BOX, CONTENT_BOX, HEADER_BOX, rect
from motion import (CAMERA_MS, DIM_IN_MS, EXIT_RATIO, FOCUS_IN_MS, INTRO_SUB_DELAY_MS,
	INTRO_SUB_MS, INTRO_TITLE_MS, INTRO_TOTAL_MS, TRANS_MS)

REVEAL_SHIFT = 30     # 左移淡入的位移；再大就是動作疲勞，再小就看不出方向
REVEAL_OVERSHOOT = 0.05   # 落位過衝，紙感材質上限（教學內容偏穩重，不用彈性材質的 15–25%）
CAM_OVERSHOOT = 0.02      # 鏡頭推近的過衝，像真的攝影機推到定位再回穩


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
ease_move = _bezier(0.2, 0, 0, 1)          # 畫面內位移：鏡頭


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
	with open(path, encoding="utf-8") as stream:
		return json.load(stream)


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


def apply_intro(frame, full, intro, t, card_rgb):
	"""首張 hook 的字從上方進場；僅移動實測 ink box，完成後保留原像素。"""
	elapsed = t - intro["start_ms"]
	if elapsed < 0 or elapsed >= INTRO_TOTAL_MS:
		return frame
	for key in ("title", "subtitle"):
		b = intro.get(key)
		if not b:
			continue
		x, y, w, h = (int(b[k]) for k in ("x", "y", "w", "h"))
		if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
			continue
		frame[y:y + h, x:x + w] = card_rgb
	for key, delay, duration, rise in (("title", 0, INTRO_TITLE_MS, 16),
			("subtitle", INTRO_SUB_DELAY_MS, INTRO_SUB_MS, 10)):
		b = intro.get(key)
		if not b:
			continue
		x, y, w, h = (int(b[k]) for k in ("x", "y", "w", "h"))
		if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > frame.shape[1] or y + h > frame.shape[0]:
			continue
		p = max(0.0, min(1.0, (elapsed - delay) / duration))
		a = ease_enter(p)
		if a <= 0:
			continue
		shift = min(rise, max(0, y - HEADER_BOX[1]))
		dy = y - round(shift * (1 - a))
		patch = full[y:y + h, x:x + w].astype(np.float32)
		dst = frame[dy:dy + h, x:x + w].astype(np.float32)
		frame[dy:dy + h, x:x + w] = (dst * (1 - a) + patch * a).astype(np.uint8)
	return frame


def apply_focus_mark(frame, eff, t, col):
	"""以框外同款側軌標示焦點；任何字形像素都不參與混色。"""
	if t < eff["start_ms"]:
		return frame
	b = eff["box"]
	p = ease_enter(min(1.0, (t - eff["start_ms"]) / FOCUS_IN_MS))
	out = exit_alpha(t, eff["end_ms"], FOCUS_IN_MS)
	if p <= 0 or out <= 0:
		return frame
	H, W = frame.shape[:2]
	y0, y1 = max(0, b["y"]), min(H, b["y"] + b["h"])
	if y1 <= y0:
		return frame
	left = b["x"] >= 16
	x0 = b["x"] - 14 if left else b["x"] + b["w"] + 8
	if x0 < 0 or x0 + 6 > W:
		return frame
	end = min(y1, y0 + max(1, round((y1 - y0) * p)))
	c = np.array(col, dtype=np.float32)
	blend(frame, y0, end, x0, x0 + 6, c, out)
	if p > 0.8:
		cap = round(10 * (p - 0.8) / 0.2)
		if left:
			xa, xb = x0, min(b["x"], x0 + 6 + cap)
		else:
			xa, xb = max(b["x"] + b["w"], x0 - cap), x0 + 6
		blend(frame, y0, min(y0 + 5, y1), xa, xb, c, out)
		blend(frame, max(y0, y1 - 5), y1, xa, xb, c, out)
	return frame


def apply_semantic_focus(frame, eff, t, col):
	"""依目標語意畫焦點；實測框已含留白，標記不可覆蓋字形。"""
	shape = eff.get("focus_shape", "rail")
	if shape == "rail":
		return apply_focus_mark(frame, eff, t, col)
	if t < eff["start_ms"]:
		return frame
	p = ease_enter(min(1.0, (t - eff["start_ms"]) / FOCUS_IN_MS))
	out = exit_alpha(t, eff["end_ms"], FOCUS_IN_MS)
	if p <= 0 or out <= 0:
		return frame
	b = eff["box"]
	H, W = frame.shape[:2]
	x0, y0 = max(0, b["x"]), max(0, b["y"])
	x1, y1 = min(W, b["x"] + b["w"]), min(H, b["y"] + b["h"])
	if x1 - x0 < 16 or y1 - y0 < 16:
		return frame
	if shape == "underline":
		left, right = x0 + 5, x1 - 5
		end = min(right, left + max(1, round((right - left) * p)))
		blend(frame, max(y0, y1 - 9), min(H, y1 - 3), left, end,
			np.array(col, dtype=np.float32), out)
		return frame
	if shape == "outline":
		mask = Image.new("L", (x1 - x0, y1 - y0), 0)
		ImageDraw.Draw(mask).arc((3, 3, x1 - x0 - 4, y1 - y0 - 4),
			start=-90, end=-90 + round(360 * p), fill=255, width=6)
		alpha = np.asarray(mask, dtype=np.float32)[:, :, None] * (out / 255)
		patch = frame[y0:y1, x0:x1].astype(np.float32)
		frame[y0:y1, x0:x1] = (patch * (1 - alpha)
			+ np.array(col, dtype=np.float32) * alpha).astype(np.uint8)
		return frame
	raise ValueError(f"未知焦點形狀：{shape}")


def apply_code_focus(frame, eff, t, fade_rgb, focus_rgb):
	"""淡化未聚焦程式行，保留目標行原色，並沿用同一種框外聚焦軌。"""
	region = eff.get("region")
	if not region:
		return apply_focus_mark(frame, eff, t, focus_rgb)
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
	return apply_focus_mark(frame, eff, t, focus_rgb)


def spot_style(eff):
	"""只有 code spotlight 需淡化非目標程式行；其餘由目標語意選標記。"""
	return "code" if eff.get("style") == "code" else "focus"


def apply_spotlight(frame, eff, t, dim_rgb, keep_box):
	"""聚光燈：壓暗 keep_box 以外的整頁，框內維持原亮度。

	keep_box 是要保留的區域（程式碼卡），不是效果自己的框——壓暗只用在程式講解，
	框選哪幾行由 apply_code_focus 在卡片內部處理
	"""
	b = keep_box
	p = min(1.0, (t - eff["start_ms"]) / FOCUS_IN_MS)
	out = exit_alpha(t, eff["end_ms"], FOCUS_IN_MS)
	if out <= 0:
		return frame
	keep = frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]].copy()
	fade = np.array(dim_rgb, dtype=np.float32)
	a = eff.get("dim", 0.62) * ease_enter(p) * out
	frame = (frame.astype(np.float32) * (1 - a) + fade * a).astype(np.uint8)
	frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]] = keep
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
	W, H = canvas["width"], canvas["height"]
	raw_p = (t - cam["start_ms"]) / cam["ms"] if cam.get("ms") else 1.0
	p = min(1.0, max(0.0, raw_p))
	ease_p = ease_move(p)

	from_b = cam.get("from_box")
	if from_b is not None:
		from_cx, from_cy = from_b["x"] + from_b["w"] / 2, from_b["y"] + from_b["h"] / 2
	else:
		from_cx, from_cy = W / 2, H / 2
	from_scale = cam.get("from_scale", 1.0)

	to_b = cam.get("box")
	if to_b is not None:
		to_cx, to_cy = to_b["x"] + to_b["w"] / 2, to_b["y"] + to_b["h"] / 2
	else:
		to_cx, to_cy = W / 2, H / 2
	to_scale = cam.get("scale", 1.0)

	cx = from_cx + (to_cx - from_cx) * ease_p
	cy = from_cy + (to_cy - from_cy) * ease_p

	if to_scale > from_scale:
		q = back_out(p, CAM_OVERSHOOT)
		scale = from_scale + (to_scale - from_scale) * q
	else:
		scale = from_scale + (to_scale - from_scale) * ease_p

	return zoom(img, cx, cy, scale, canvas)


def transition_surface(canvas, theme, visual_style="cards"):
	"""換頁用與場景相同的乾淨底面；cards 保留既有框線。"""
	im = Image.new("RGB", (canvas["width"], canvas["height"]), rgb(theme["canvas"]["bg"]))
	if visual_style == "cards":
		draw = ImageDraw.Draw(im)
		for box in (HEADER_BOX, CONTENT_BOX):
			draw.rectangle(box, fill=rgb(theme["card"]["fill"]),
				outline=rgb(theme["card"]["edge"]), width=theme["card"]["width"])
	elif visual_style != "explainer":
		raise ValueError(f"未知視覺模式：{visual_style}")
	return np.asarray(im)


def dip_to_surface(previous, current, surface, progress):
	"""舊頁先退到卡面，新頁再進場，兩頁文字永不同時疊色。"""
	if progress <= 0:
		return previous.copy()
	if progress >= 1:
		return current.copy()
	if progress < 0.5:
		a = 1 - ease_exit(progress * 2)
		source = previous
	elif progress > 0.5:
		a = ease_enter((progress - 0.5) * 2)
		source = current
	else:
		return surface.copy()
	return (surface.astype(np.float32) * (1 - a)
		+ source.astype(np.float32) * a).astype(np.uint8)


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
	fade_rgb = rgb(fx["code_fade"])
	focus_rgb = rgb(fx.get("focus", fx["spotlight_border"]))
	focus_dark_rgb = rgb(fx.get("focus_on_dark", fx.get("focus", fx["spotlight_border"])))
	dim_rgb = rgb(fx["dim"])

	canvas, fps = timeline["canvas"], timeline["fps"]
	W, H = canvas["width"], canvas["height"]
	master_wav = os.path.join(out_dir, "master.wav")
	print("組音軌…")
	build_audio(timeline, master_wav)

	pages = {s["slide_id"]: (
		np.array(Image.open(s["base_png"]).convert("RGB")),
		np.array(Image.open(s["full_png"]).convert("RGB")),
	) for s in timeline["scenes"]}

	surface = None

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
		visual_style = scene.get("visual_style", timeline.get("visual_style", "cards"))
		base, full = pages[scene["slide_id"]]
		frame = base.copy()
		frame = apply_reveals(frame, full, scene, t, W)
		if scene.get("intro"):
			intro_bg = theme["canvas"]["bg"] if visual_style == "explainer" else theme["card"]["fill"]
			frame = apply_intro(frame, full, scene["intro"], t, rgb(intro_bg))

		for eff in active([e for e in scene["effects"] if e["type"] == "spotlight"], t):
			if spot_style(eff) == "code":
				# cards 保留既有程式區域壓暗；全幅場景僅淡化非目標程式行。
				if visual_style == "cards":
					frame = apply_spotlight(frame, eff, t, dim_rgb, rect(*CODE_BOX))
				frame = apply_code_focus(frame, eff, t, fade_rgb, focus_dark_rgb)
			else:
				frame = apply_semantic_focus(frame, eff, t, focus_rgb)

		for eff in active([e for e in scene["effects"] if e["type"] == "laser"], t):
			frame = apply_semantic_focus(frame, eff, t, focus_rgb)

		# 沒有鏡頭動作就完全不進 PIL 重取樣：連續次像素縮放會讓中文字與程式碼發糊
		cams = active(scene["camera"], t)
		if cams:
			arr = np.asarray(apply_camera(Image.fromarray(frame), cams[-1], t, canvas)).copy()
		else:
			arr = frame

		# 換頁先回到乾淨卡面再帶入新頁，避免文字疊影與邊界裁字
		if idx != last_idx:
			trans_from, trans_until = last_frame, t + TRANS_MS
			surface = transition_surface(canvas, theme, visual_style)
			last_idx = idx
		if trans_from is not None and t < trans_until:
			arr = dip_to_surface(trans_from, arr, surface, 1 - (trans_until - t) / TRANS_MS)
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
