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
import subprocess
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
# 中文句中夾英文單字，王老師模型會唸糊並連帶吃掉後面的字（2026-10-04 實測：path 之後的「這份」漏念）
ENGLISH = re.compile(r"[A-Za-z]+")
ENGLISH_OK = {"Windows"}  # 實測唸得清楚的才列入
ASR_PYTHON = os.environ.get("ASR_PYTHON", os.path.expanduser("~/projects/GPT-SoVITS/.venv/bin/python"))
MAX_ROUNDS = 3


def speech_problems(text):
	if SPELLED.search(text):
		return f"逐字母縮寫 {SPELLED.findall(text)}"
	words = [w for w in ENGLISH.findall(text) if w not in ENGLISH_OK]
	return f"夾英文單字 {words}" if words else None


def voice_key(speed):
	"""快取鑰匙含聲音條件：換參考音訊、參考文字、服務或模型，舊音檔就不能沿用。"""
	with open(synth.REF_AUDIO, "rb") as f:
		ref = hashlib.sha1(f.read()).hexdigest()[:12]
	return f"{speed}|{ref}|{synth.REF_TEXT}|{synth.API_URL}|{os.environ.get('TTS_VOICE_ID', '')}"


def synth_keep_raw(text, speed, wav, raw_prefix):
	"""synth_one 會裁掉頭尾低電平；裁切前的原始音訊另存，追查句尾漏字時才分得出是模型還是裁切。"""
	raws, orig = [], synth.trim_and_pad

	def capture(data, sr):
		raws.append((sr, data.copy()))
		return orig(data, sr)
	synth.trim_and_pad = capture
	try:
		info, ok = synth.synth_one(text, speed, wav)
	finally:
		synth.trim_and_pad = orig
	for i, (sr, data) in enumerate(raws):
		wavfile.write(f"{raw_prefix}.raw{i}.wav", sr, data)
	return info, ok


def asr_check(jobs, out_dir):
	"""另一個 venv 跑語音辨識（GPU 留給 TTS），回傳 {wav: 結果}。"""
	jobs_path, res_path = os.path.join(out_dir, "asr_jobs.json"), os.path.join(out_dir, "asr_result.json")
	with open(jobs_path, "w", encoding="utf-8") as f:
		json.dump(jobs, f, ensure_ascii=False)
	subprocess.run([ASR_PYTHON, os.path.join(HERE, "asr_check.py"), jobs_path, res_path], check=True,
		env={**os.environ, "CUDA_VISIBLE_DEVICES": ""})
	with open(res_path, encoding="utf-8") as f:
		return {r["wav"]: r for r in json.load(f)}


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("scene")
	ap.add_argument("out_dir")
	ap.add_argument("--speed", type=float, default=0.95)
	ap.add_argument("--allow-spelled", action="store_true", help="確定要唸縮寫或英文單字時才用")
	args = ap.parse_args()
	with open(args.scene, encoding="utf-8") as f:
		doc = json.load(f)
	audio_dir = os.path.join(args.out_dir, "audio")
	raw_dir = os.path.join(audio_dir, "raw")
	os.makedirs(raw_dir, exist_ok=True)
	report_path = os.path.join(args.out_dir, "narration.json")
	cache = {}
	if os.path.exists(report_path):
		with open(report_path, encoding="utf-8") as f:
			cache = {r["digest"]: r for r in json.load(f)["beats"]}

	beats = [(si, b) for si, s in enumerate(doc["scenes"]) for b in s["beats"]]
	bad = [f"{p}：{b.get('spoken') or b['say']}" for _, b in beats if (p := speech_problems(b.get("spoken") or b["say"]))]
	if bad and not args.allow_spelled:
		# 王老師語料沒有逐字母縮寫、英文單字也極少（見 memory gptsovits-ar-failure-modes）
		raise SystemExit("講稿請改中文說法（畫面可保留英文，旁白寫在 spoken）：\n  " + "\n  ".join(bad))

	key = voice_key(args.speed)
	records, meta, todo, unchecked = [None] * len(beats), {}, [], []
	for k, (si, b) in enumerate(beats):
		text = b.get("spoken") or b["say"]
		digest = hashlib.sha1(f"{text}|{key}".encode("utf-8")).hexdigest()[:12]
		wav = os.path.join(audio_dir, f"{k:02d}_{digest}.wav")
		meta[k] = (si, text, digest, wav)
		hit = cache.get(digest)
		if hit and os.path.exists(wav):
			records[k] = {**hit, "scene": si, "wav": os.path.basename(wav)}
			print(f"[{k + 1}/{len(beats)}] 快取 {text}")
			if not hit.get("asr"):
				unchecked.append(k)
		else:
			todo.append(k)

	# 合成 → 內容檢查 → 沒過的換個隨機種子重合成（服務端每次預設隨機 seed），最多 MAX_ROUNDS 次
	rnd = 0
	while True:
		failed = []
		if unchecked:
			results = asr_check([{"wav": meta[k][3], "text": meta[k][1]} for k in unchecked], args.out_dir)
			for k in unchecked:
				r = results[meta[k][3]]
				records[k]["asr"] = {key2: r[key2] for key2 in ("ok", "problems", "missing", "heard")}
				if not r["ok"]:
					failed.append(k)
					print(f"  內容檢查未過（{'、'.join(r['problems'])}，疑似漏「{'、'.join(r['missing'])}」）：{meta[k][1]}")
		todo = sorted(set(todo) | set(failed))
		if not todo or rnd >= MAX_ROUNDS:
			break
		rnd += 1
		for k in todo:
			si, text, digest, wav = meta[k]
			print(f"[{k + 1}/{len(beats)}] 合成（第 {rnd} 輪）{text}", flush=True)
			info, ok = synth_keep_raw(text, args.speed, wav, os.path.join(raw_dir, f"{k:02d}_{digest}.r{rnd}"))
			records[k] = {"digest": digest, "text": text, "ok": ok, **info, "scene": si, "wav": os.path.basename(wav), "round": rnd}
		unchecked, todo = todo, []
	records = [{**r, "ok": r["ok"] and r.get("asr", {}).get("ok", False)} for r in records]

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
	bad = [r for r in records if not r["ok"]]
	print(f"{master}：{t:.2f}s，{len(records)} 句，{len(bad)} 句未過驗收（音量或內容）")
	for r in bad:
		print(f"  未過：{r['text']}　{r.get('asr', {}).get('problems', '')}")


if __name__ == "__main__":
	main()
