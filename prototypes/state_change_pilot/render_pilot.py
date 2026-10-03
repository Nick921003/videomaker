"""狀態動畫試片；沿用主題與 TTS helper，不接入正式八階段流程。"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.io import wavfile

from state_model import validate_beats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video_engine"))
from render_slides import load_theme, FONT_FACES
from render_video import ease_move

OUT = ROOT / "video_engine/out/state_change_pilot_20261001"
W, H, FPS = 1280, 720, 24
THEME = load_theme("explainer")
FONTS = {}


def font(size, bold=False, mono=False):
	key = (size, bold, mono)
	if key not in FONTS:
		path, index = FONT_FACES["mono-tc" if mono else "bold-tc" if bold else "regular-tc"]
		FONTS[key] = ImageFont.truetype(path, size, index=index)
	return FONTS[key]


def save(name, data):
	(OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def synthesize():
	import synth
	# 本機 GPU 呼叫也只先做一次；品質不合格時停止供診斷。
	synth.MAX_TRIES = 1
	board = json.loads((OUT / "storyboard.json").read_text())
	validate_beats(board["beats"])
	assert json.loads((OUT / "storyboard_validation.json").read_text())["valid"]
	audio_dir = OUT / "audio"
	audio_dir.mkdir(exist_ok=True)
	records = []
	for beat in board["beats"]:
		text = beat["speech"]
		digest = hashlib.sha256(text.encode()).hexdigest()[:12]
		path = audio_dir / f"{beat['id']}_{digest}.wav"
		meta_path = path.with_suffix(".json")
		if path.exists() and meta_path.exists():
			record = json.loads(meta_path.read_text())
		else:
			metrics, ok = synth.synth_one(text, 0.95, str(path))
			record = {"id": beat["id"], "text": text, "file": str(path.relative_to(OUT)),
				"speed_factor": 0.95, "quality_ok": ok, "metrics": metrics, "calls": metrics["frags"],
				"service": "local GPT-SoVITS Wang 3.0", "llm_tokens": None}
			meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
		print(beat["id"], record["metrics"], "ok=", record["quality_ok"], flush=True)
		if not record["quality_ok"]:
			raise RuntimeError("TTS 未通過現有品質檢查；已保存音訊，先診斷，不自動重試。")
		records.append(record)
	save("tts_usage.json", records)


def timeline():
	board = json.loads((OUT / "storyboard.json").read_text())
	validate_beats(board["beats"])
	usage = json.loads((OUT / "tts_usage.json").read_text())
	pieces, segments, cursor, sr = [], [], 0, None
	for beat, record in zip(board["beats"], usage):
		rate, samples = wavfile.read(OUT / record["file"])
		assert sr is None or rate == sr
		sr = rate
		assert samples.ndim == 1
		duration = len(samples) / sr
		segment = dict(beat, start=cursor / sr, speech_end=(cursor + len(samples)) / sr,
			end=(cursor + len(samples) + int(sr * 0.24)) / sr,
			action_time=cursor / sr + 0.15,
			append_time=cursor / sr + min(1.1, duration * 0.4))
		if record.get("attempt") == 3:
			segment["claude_original_speech"] = beat["speech"]
			segment["speech"] = record["tts_text"]
		segments.append(segment)
		pieces += [samples, np.zeros(int(sr * 0.24), dtype=samples.dtype)]
		cursor += len(samples) + int(sr * 0.24)
	master = np.concatenate(pieces)
	wavfile.write(OUT / "master.wav", sr, master)
	data = {"fps": FPS, "canvas": [W, H], "duration": len(master) / sr,
		"audio_sample_rate": sr, "segments": segments,
		"sync_precision": "句子起點；append 尚待 ASR 語句定位驗證"}
	save("pilot_timeline.json", data)
	print("duration", data["duration"], flush=True)
	return data


def frame_at(t, data):
	segments = data["segments"]
	k = next((i for i, segment in enumerate(segments) if t < segment["end"]), len(segments)-1)
	s = segments[k]
	phase, local = s["phase"], t - s["start"]
	duration = s["speech_end"] - s["start"]
	image = Image.new("RGB", (W, H), THEME["canvas"]["bg"])
	d = ImageDraw.Draw(image)
	ink = THEME["text"]["title"]
	muted = THEME["text"]["subtitle"]
	accent = THEME["effects"]["focus"]
	green = THEME["figure"]["heading"]
	def text(x, y, value, size=26, color=ink, bold=False, mono=False):
		f = font(size, bold, mono)
		box = d.textbbox((x, y), value, font=f)
		if box[2] > W-36 or box[3] > H-12 or box[0] < 0 or box[1] < 0:
			raise ValueError(f"文字越界：{value}")
		d.text((x, y), value, font=f, fill=color)
	text(72, 25, "字串讀到哪裡才停？", 42, bold=True)
	text(972, 45, "C 字串 / 狀態走讀", 21, muted)
	d.line((72, 98, 1208, 98), fill=THEME["card"]["edge"], width=2)
	caption = s["caption"]
	if phase == "scan" and not data.get("continuous_narrative") and t < s["append_time"]:
		caption = f"游標在 [{s['index']}]：讀取 {'Alice'[s['index']]}"
	if phase == "question" and t < s.get("answer_time", s["start"]+duration*.48):
		caption = "小問題：\\0 算進長度嗎？"
	if phase == "stop" and not data.get("continuous_narrative") and t < s.get("stop_time", s["start"]):
		caption = "游標在 [5]：讀到 \\0"
	text(72, 120, caption, 30, green, True)
	code = {"setup": "char name[32];", "copy": 'strcpy(name, "Alice");',
		"scan": 'printf("%s", name);', "stop": 'printf("%s", name);',
		"summary": "strlen(name) == 5;   sizeof name == 32;",
		"question": "strlen(name) == 5;"}[phase]
	if phase == "question" and t < s.get("answer_time", s["start"]+duration*.48):
		code = "strlen(name)"
	d.rounded_rectangle((72, 177, 1208, 240), radius=16, fill=THEME["code"]["bg"])
	text(98, 188, code, 28, THEME["code"]["normal"], mono=True)
	if phase in ("scan", "stop"):
		text(1010, 194, "簡化示範", 20, THEME["code"]["keyword"])
	text(72, 251, "name", 21, bold=True, mono=True)
	text(1002, 269, "容量：32 格", 24, green, True)
	cell_x, step, y, cell_w, cell_h = 72, 112, 327, 96, 88
	copied = 0 if phase == "setup" else 6
	if phase == "copy":
		copied = sum(t >= time for time in s["copy_times"]) if "copy_times" in s else min(6, max(0, int((local - 0.25) / max(0.2, duration * 0.09)) + 1))
	chars = list("Alice") + ["\\0"]
	for i in range(6):
		x = cell_x + i * step
		focus = phase in ("scan", "stop") and s["index"] == i
		fill = THEME["figure"]["fill"] if i < copied else THEME["figure"]["alt"]
		d.rounded_rectangle((x, y, x+cell_w, y+cell_h), radius=13, fill=fill,
			outline=accent if focus else THEME["figure"]["edge"], width=4 if focus else 2)
		text(x+23, y+12, chars[i] if i < copied else "?", 39, green if i == 5 and i < copied else ink, mono=True)
		text(x+39, y+cell_h+7, str(i), 21, muted, mono=True)
	d.rounded_rectangle((777, y, 1208, y+cell_h), radius=13,
		fill=THEME["figure"]["alt"], outline=THEME["figure"]["edge"], width=2)
	text(810, y+14, "…  其餘 26 格：?", 27, muted)
	text(810, y+48, "索引 6–31：尚未初始化", 21, muted)
	if phase in ("scan", "stop", "summary", "question"):
		index = s.get("index", 5)
		previous = max(0, index-1)
		progress = ease_move(min(1, max(0, (t-s["action_time"])/0.42)))
		cx = cell_x + cell_w/2 + step*(previous+(index-previous)*progress)
		cy = 301
		# 同一個讀取游標：移動、指向當前格，在 NUL 停住。
		d.rounded_rectangle((cx-30, cy-23, cx+30, cy+4), radius=12, fill=accent)
		for eye_x in (cx-10, cx+10):
			d.ellipse((eye_x-3, cy-14, eye_x+3, cy-8), fill=THEME["figure"]["heading_text"])
		d.polygon([(cx-9, cy+6), (cx+9, cy+6), (cx, cy+19)], fill=accent)
		if phase in ("summary", "question") or (phase == "stop" and t >= s.get("stop_time", s["start"])):
			text(754, 292, "遇到 \\0 → 停止", 23, accent, True)
	text(72, 452, "概念示意：不代表標準函式的實際實作方式", 17, muted)
	count = 0
	if phase == "scan":
		count = s["index"] + (1 if t >= s["append_time"] else 0)
	elif phase in ("stop", "summary", "question"):
		count = 5
	d.rounded_rectangle((72, 479, 848, 584), radius=16, fill=THEME["code"]["bg"])
	text(93, 489, "輸出", 20, THEME["code"]["keyword"])
	text(193, 498, "Alice"[:count] + ("▏" if phase == "scan" else ""), 46, THEME["code"]["normal"], mono=True)
	if phase not in ("setup", "copy"):
		text(889, 486, "已輸出字元", 23, muted)
		text(975, 519, str(count), 36, green, True)
	flight_start = s.get("flight_start", s["action_time"])
	if phase == "scan" and flight_start <= t < s["append_time"]:
		p = min(1, (t-flight_start) / max(0.01, s["append_time"]-flight_start))
		x0 = cell_x + s["index"]*step + 32
		x1 = 193 + s["index"]*font(46, mono=True).getlength("A")
		text(x0+(x1-x0)*p, 392+104*p, "Alice"[s["index"]], 32, accent, True, True)
	if phase == "summary":
		for x, label in [(72, "容量：32 格"), (420, "長度：5"), (768, "至少需要：6 格")]:
			d.rounded_rectangle((x, 600, x+310, 637), radius=10, fill=THEME["figure"]["fill"])
			text(x+16, 601, label, 23, green, True)
		d.line((72, 320, 616, 320), fill=green, width=3)
		d.line((72, 324, 728, 324), fill=accent, width=2)
	elif phase == "question":
		answer_time = s.get("answer_time", s["start"] + duration*0.48)
		text(72, 600, "\\0 算進長度嗎？" if t < answer_time else "不算。長度是 5，但 \\0 仍占一格容量。", 26, green, True)
		d.ellipse((624, 324, 731, 418), outline=accent, width=3)
	# 旁白字幕獨立於核心教學圖示；長句依字寬換行。
	words, rows = "", []
	subtitle = s["speech"]
	for cue in data.get("subtitle_cues", []):
		if cue["start"] <= t < cue["end"]:
			subtitle = cue["text"]
			break
	for ch in subtitle:
		if font(24).getlength(words+ch) > 1110:
			rows.append(words)
			words = ch
		else:
			words += ch
	rows.append(words)
	if len(rows) > 2:
		raise ValueError("旁白字幕超過兩行")
	for j, row in enumerate(rows):
		text(72, 644+j*30, row, 24)
	d.rectangle((72, 706, 1208, 710), fill=THEME["card"]["edge"])
	d.rectangle((72, 706, 72+1136*min(1, t/data["duration"]), 710), fill=accent)
	return image


def render():
	data = json.loads((OUT / "pilot_timeline.json").read_text()) if (OUT / "pilot_timeline.json").exists() else timeline()
	if not 30 <= data["duration"] <= 60:
		raise RuntimeError("實測片長不在30–60秒；需先診斷節奏。")
	frames = math.ceil(data["duration"]*FPS)
	command = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
		"-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0"]
	if not data.get("silent"):
		command += ["-i", str(OUT/"master.wav")]
	command += [
		"-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p",
		"-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(OUT/"state_change_pilot.mp4")]
	process = subprocess.Popen(command, stdin=subprocess.PIPE)
	try:
		for i in range(frames):
			process.stdin.write(frame_at(i/FPS, data).tobytes())
			if i % (FPS*5) == 0:
				print(f"render {i/FPS:.0f}s / {data['duration']:.2f}s", flush=True)
	finally:
		process.stdin.close()
	if process.wait() != 0:
		raise RuntimeError("FFmpeg failed")
	for s in data["segments"]:
		frame_at((s["speech_end"]+s["start"])/2, data).save(OUT / f"preview_{s['id']}.png")
	print("render complete", flush=True)


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("stage", choices=["synth", "timeline", "render"])
	args = parser.parse_args()
	{"synth": synthesize, "timeline": timeline, "render": render}[args.stage]()
