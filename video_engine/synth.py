#!/usr/bin/env python3
"""語音合成 + 自動驗收重試（閘二）。

用法：.venv/bin/python video_engine/synth.py <lesson.json> <actions.json> [輸出目錄]

每段 speech 合成後檢查：異常靜音、長度是否落在預期區間。不合格就重跑，
最多三次，仍不合格取最好的一次並記在報告裡。已合成過的段落會跳過（比對文字雜湊）。
"""
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.request

import numpy as np
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm  # 借它的 .env 讀取

llm.load_env()
# 聲音模型在另一個專案（GPT-SoVITS），這裡只認得 HTTP 端點與參考音訊路徑
API_URL = os.environ.get("TTS_API_URL", "http://127.0.0.1:9880/tts")
REF_AUDIO = os.environ.get("TTS_REF_AUDIO", "")
REF_TEXT = os.environ.get("TTS_REF_TEXT", "")
if not REF_AUDIO or not os.path.exists(REF_AUDIO):
	raise SystemExit(f"找不到參考音訊，請在 .env 設 TTS_REF_AUDIO（目前：{REF_AUDIO or '未設定'}）")

MAX_SINGLE_CHARS = 70  # 這個長度以內整句一次送（cut0），上下文完整最自然
MIN_FRAG_CHARS = 12    # 真的要切時，片段不得短於這個字數；孤立片段會讓 AR 失控
MIN_PEAK = 0.15        # 峰值低於這個等於整段是雜音
SIL_FLOOR = 0.015      # 絕對靜音門檻。只用相對門檻的話，低電平雜訊會被當成有聲音
FRAG_GAP_MS = 120
MAX_TRIES = 3
MAX_GAP_SEC = 1.5          # 句中空白超過這個就是卡住
CHARS_PER_SEC = 6.35       # 實測王老師 3.0 語速中位數（18 段，範圍 4.2–8.3）
LEN_TOLERANCE = (0.55, 1.9)  # 實測比值落在 0.66–1.31，這個區間有餘裕又抓得到失控
PAD_START, PAD_END = 0.15, 0.25


def safe_fragments(text):
	"""自己斷句：切在標點，但太短或沒有中文的片段一律併進前一段。

	只有超長講稿才會走到這裡。API 的 cut5 會在「、」硬切，把「 float ，」變成
	孤立片段送進 AR 模型，實測產生 8.4 秒、峰值 0.02 的雜音，所以片段一律補足長度。
	"""
	parts = re.findall(r"[^，。！？、；：,.!?;]+[，。！？、；：,.!?;]?", text)
	parts = [p.strip() for p in parts if p.strip()]
	merged = []
	for p in parts:
		cjk = len(re.findall(r"[\u4e00-\u9fff]", p))
		too_short = len(p) < MIN_FRAG_CHARS or cjk == 0
		if merged and too_short:
			merged[-1] += p
		else:
			merged.append(p)
	# 最後一段太短也往前併
	if len(merged) > 1 and len(merged[-1]) < MIN_FRAG_CHARS:
		merged[-2] += merged.pop()
	return merged


def tts(text, speed):
	payload = {
		"text": text,
		"text_lang": "zh",
		"ref_audio_path": REF_AUDIO,
		"prompt_text": REF_TEXT,
		"prompt_lang": "zh",
		"top_k": 5,
		"top_p": 0.6,
		"temperature": 0.28,
		"speed_factor": speed,
		"text_split_method": "cut0",
		"fragment_interval": 0.12,
		"media_type": "wav",
	}
	req = urllib.request.Request(
		API_URL, data=json.dumps(payload).encode("utf-8"),
		headers={"Content-Type": "application/json"},
	)
	with urllib.request.urlopen(req, timeout=300) as resp:
		return wavfile.read(io.BytesIO(resp.read()))


def analyse(sr, data):
	"""回傳 (全長, 實際講話時間, 最長空白, 空白總和)"""
	x = (data[:, 0] if data.ndim > 1 else data).astype(np.float32) / 32768.0
	n = sr // 50
	frames = x[: len(x) // n * n].reshape(-1, n)
	energy = np.sqrt((frames ** 2).mean(1))
	# 相對門檻抓一般停頓，絕對門檻抓 AR 失控產生的低電平雜訊
	sil = (energy < energy.max() * 0.02) | (energy < SIL_FLOOR)
	voiced = float((~sil).sum() * 0.02)

	gaps, i = [], 0
	while i < len(sil):
		if sil[i]:
			j = i
			while j < len(sil) and sil[j]:
				j += 1
			if (j - i) * 0.02 > 0.4:
				gaps.append(round((j - i) * 0.02, 2))
			i = j
		else:
			i += 1
	return len(x) / sr, voiced, (max(gaps) if gaps else 0.0), sum(gaps)


def trim_and_pad(data, sr):
	"""切掉頭尾的靜音與低電平雜訊。用逐框 RMS，不能用單一取樣點振幅——
	雜訊的瞬間振幅可以到 0.07，但整框 RMS 只有 0.005。"""
	mono = data[:, 0] if data.ndim > 1 else data
	f = mono.astype(np.float32) / 32768.0
	n = sr // 50
	frames = f[: len(f) // n * n].reshape(-1, n)
	rms = np.sqrt((frames ** 2).mean(1))
	active = np.where(rms > SIL_FLOOR)[0]
	if len(active) == 0:
		return data
	s = max(0, active[0] * n - int(sr * 0.03))
	e = min(len(data), (active[-1] + 1) * n + int(sr * 0.03))
	lead = np.zeros(int(sr * PAD_START), dtype=data.dtype)
	tail = np.zeros(int(sr * PAD_END), dtype=data.dtype)
	return np.concatenate([lead, data[s:e], tail])


def verdict(text, total, voiced, max_gap, peak):
	"""合格與否，附上原因"""
	expect = len(text) / CHARS_PER_SEC
	ratio = voiced / expect if expect else 0
	if peak < MIN_PEAK:
		return False, f"整段近乎無聲（峰值 {peak:.2f}），AR 失控"
	if max_gap > MAX_GAP_SEC:
		return False, f"句中空白 {max_gap:.1f}s"
	if not LEN_TOLERANCE[0] <= ratio <= LEN_TOLERANCE[1]:
		return False, f"長度異常（講話 {voiced:.1f}s，預估 {expect:.1f}s）"
	return True, "合格"


def synth_fragment(text, speed):
	"""單一片段：不合格就只重跑這一段，不必整句重來"""
	best = None
	for attempt in range(1, MAX_TRIES + 1):
		sr, raw = tts(text, speed)
		clean = trim_and_pad(raw, sr)
		total, voiced, max_gap, _ = analyse(sr, clean)
		peak = float(np.abs((clean[:, 0] if clean.ndim > 1 else clean).astype(np.float32) / 32768.0).max())
		ok, why = verdict(text, total, voiced, max_gap, peak)
		rec = {"sr": sr, "data": clean, "total": total, "voiced": voiced,
			"max_gap": max_gap, "peak": peak, "tries": attempt, "why": why}
		if best is None or (peak >= MIN_PEAK and max_gap < best["max_gap"]):
			best = rec
		if ok:
			return rec, True
		print(f"      片段第 {attempt} 次不合格：{why}，重跑")
	return best, False


def synth_one(text, speed, out_wav):
	"""夠短就整句一次送；太長才切，且切點保證每段都有中文上下文"""
	frags = [text] if len(text) <= MAX_SINGLE_CHARS else safe_fragments(text)
	pieces, sr, tries, worst_gap, all_ok = [], None, 1, 0.0, True
	for f in frags:
		rec, ok = synth_fragment(f, speed)
		sr = rec["sr"]
		pieces.append(rec["data"])
		tries = max(tries, rec["tries"])
		worst_gap = max(worst_gap, rec["max_gap"])
		all_ok = all_ok and ok
	gap = np.zeros(int(sr * FRAG_GAP_MS / 1000), dtype=pieces[0].dtype)
	joined = pieces[0]
	for p in pieces[1:]:
		joined = np.concatenate([joined, gap, p])
	wavfile.write(out_wav, sr, joined)
	total = len(joined) / sr
	_, voiced, max_gap, _ = analyse(sr, joined)
	return {"total": total, "voiced": voiced, "max_gap": max(worst_gap, max_gap),
		"tries": tries, "frags": len(frags)}, all_ok


def main():
	if len(sys.argv) < 3:
		print(__doc__)
		return 2
	lesson = json.load(open(sys.argv[1], encoding="utf-8"))
	actions = json.load(open(sys.argv[2], encoding="utf-8"))
	out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
		os.path.dirname(os.path.abspath(__file__)), "out", lesson["lesson_id"]
	)
	audio_dir = os.path.join(out_dir, "audio")
	os.makedirs(audio_dir, exist_ok=True)

	default_speed = lesson.get("voice", {}).get("speed_factor", 0.95)
	dur_path = os.path.join(out_dir, "durations.json")
	cache = json.load(open(dur_path, encoding="utf-8")) if os.path.exists(dur_path) else {}

	jobs = []
	for slide in actions["slides"]:
		for i, a in enumerate(slide["actions"]):
			if a["type"] == "speech":
				jobs.append((slide["slide_id"], i, a["text"], a.get("speed_factor", default_speed)))

	print(f"共 {len(jobs)} 段語音")
	failed, t0 = [], time.time()
	for n, (sid, idx, text, speed) in enumerate(jobs, start=1):
		key = f"{sid}#{idx}"
		digest = hashlib.sha1(f"{text}|{speed}".encode("utf-8")).hexdigest()[:12]
		wav = os.path.join(audio_dir, f"{sid}_{idx:02d}_{digest}.wav")
		hit = cache.get(key, {})
		if hit.get("digest") == digest and hit.get("accepted") and os.path.exists(wav):
			print(f"[{n}/{len(jobs)}] {key} 已存在，跳過")
			continue

		print(f"[{n}/{len(jobs)}] {key} {text[:24]}…")
		rec, ok = synth_one(text, speed, wav)
		if not ok:
			failed.append(key)
		cache[key] = {
			"digest": digest,
			"text": text,
			"wav": wav,
			"duration": round(rec["total"], 3),
			"voiced": round(rec["voiced"], 3),
			"max_gap": round(rec["max_gap"], 2),
			"tries": rec["tries"],
			"accepted": ok,
		}
		print(f"    {rec['total']:.1f}s（{rec['frags']} 片段，講話 {rec['voiced']:.1f}s，最長空白 {rec['max_gap']:.2f}s，最多 {rec['tries']} 次）")
		json.dump(cache, open(dur_path, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")

	total = sum(v["duration"] for v in cache.values())
	print(f"\n完成，耗時 {time.time() - t0:.0f} 秒")
	print(f"語音總長 {total:.1f} 秒（不含頁面停頓）")
	if failed:
		print(f"重試三次仍不合格：{failed}（已採用最佳的一次）")
	print(f"時長表：{dur_path}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
