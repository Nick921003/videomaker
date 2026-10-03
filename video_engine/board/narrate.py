#!/usr/bin/env python3
"""scene.json → 配音 master.wav＋timing.json（每句實測起訖）。

用法：.venv/bin/python video_engine/board/narrate.py <scene.json> <輸出目錄> [--speed 0.95]

每句唸 `spoken`（沒有就唸 `say`），以文字雜湊快取：改一句只重合成那一句。
需要 GPT-SoVITS 服務（.env 的 TTS_API_URL）。合成與驗收重試沿用 synth.py。
"""
import argparse
import hashlib
import json
import os
import re
import sys

import numpy as np
from scipy.io import wavfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import synth
from compile import BEAT_GAP, LEAD_IN, SCENE_GAP

# 「G C C」這種空白隔開的字母，或 GCC、PATH 這類全大寫縮寫
SPELLED = re.compile(r"(?<![A-Za-z])(?:[A-Za-z] ){1,}[A-Za-z](?![A-Za-z])|(?<![A-Za-z])[A-Z]{2,6}(?![A-Za-z])")


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("scene")
	ap.add_argument("out_dir")
	ap.add_argument("--speed", type=float, default=0.95)
	ap.add_argument("--allow-spelled", action="store_true", help="確定要唸縮寫時才用")
	args = ap.parse_args()
	with open(args.scene, encoding="utf-8") as f:
		doc = json.load(f)
	audio_dir = os.path.join(args.out_dir, "audio")
	os.makedirs(audio_dir, exist_ok=True)
	report_path = os.path.join(args.out_dir, "narration.json")
	cache = {}
	if os.path.exists(report_path):
		with open(report_path, encoding="utf-8") as f:
			cache = {r["digest"]: r for r in json.load(f)["beats"]}

	beats = [(si, b) for si, s in enumerate(doc["scenes"]) for b in s["beats"]]
	spelled = [(b.get("spoken") or b["say"]) for _, b in beats if SPELLED.search(b.get("spoken") or b["say"])]
	if spelled and not args.allow_spelled:
		# 王老師語料沒有逐字母唸的縮寫，合成出來是氣音，且能量與 ASR 都抓不到（見 memory gptsovits-ar-failure-modes）
		raise SystemExit("講稿含逐字母縮寫，請改中文說法（畫面可保留英文）：\n  " + "\n  ".join(spelled))
	records = []
	for k, (si, b) in enumerate(beats):
		text = b.get("spoken") or b["say"]
		digest = hashlib.sha1(f"{text}|{args.speed}".encode("utf-8")).hexdigest()[:12]
		wav = os.path.join(audio_dir, f"{k:02d}_{digest}.wav")
		hit = cache.get(digest)
		if hit and os.path.exists(wav):
			rec = hit
			print(f"[{k + 1}/{len(beats)}] 快取 {text}")
		else:
			print(f"[{k + 1}/{len(beats)}] 合成 {text}", flush=True)
			info, ok = synth.synth_one(text, args.speed, wav)
			rec = {"digest": digest, "text": text, "ok": ok, **info}
		records.append({**rec, "scene": si, "wav": os.path.basename(wav)})

	# 接成一條：開頭留白、句間停頓、換場多停一點，跟 compile.py 估時的節奏一致
	pieces, timing, t, sr, prev_scene = [], [], 0.0, None, 0
	for k, rec in enumerate(records):
		rate, data = wavfile.read(os.path.join(audio_dir, rec["wav"]))
		if sr is None:
			sr = rate
			pieces.append(np.zeros(int(sr * LEAD_IN), dtype=data.dtype))
			t = LEAD_IN
		elif rate != sr:
			raise SystemExit(f"取樣率不一致：{rec['wav']} {rate} ≠ {sr}")
		else:
			gap = BEAT_GAP + (SCENE_GAP if rec["scene"] != prev_scene else 0)
			pieces.append(np.zeros(int(sr * gap), dtype=data.dtype))
			t += int(sr * gap) / sr
		dur = len(data) / sr
		# synth 在每句前後各墊了靜音，起訖點取實際開口與收尾
		timing.append({"t0": round(t + synth.PAD_START, 3), "t1": round(t + dur - synth.PAD_END, 3)})
		pieces.append(data)
		t += dur
		prev_scene = rec["scene"]
	master = os.path.join(args.out_dir, "master.wav")
	wavfile.write(master, sr, np.concatenate(pieces))
	with open(os.path.join(args.out_dir, "timing.json"), "w", encoding="utf-8") as f:
		json.dump(timing, f, ensure_ascii=False)
	with open(report_path, "w", encoding="utf-8") as f:
		json.dump({"speed": args.speed, "total": round(t, 3), "beats": records}, f, ensure_ascii=False, indent="\t")
	bad = [r["text"] for r in records if not r["ok"]]
	print(f"{master}：{t:.2f}s，{len(records)} 句，{len(bad)} 句未過驗收")
	for text in bad:
		print("  未過：" + text)


if __name__ == "__main__":
	main()
