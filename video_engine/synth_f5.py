#!/usr/bin/env python3
"""語音合成：F5-TTS 後端（王老師聲音）。

用法：~/.venvs/f5tts/bin/python video_engine/synth_f5.py <lesson.json> <actions.json> [輸出目錄]

只是轉接層：把 actions.json 的 speech 交給 tts_f5.F5Narrator，寫出跟 synth.py
同格式的 durations.json，下游 storyboard／timeline 不必改。畫面在旁白段與段之間對齊，
段內的停頓交給模型。

辨識器量不出念得像不像，成品一律要人耳聽過。念錯的片段在輸出目錄的
f5_reseed.json 指定別的 seed（{"片段原文": 7}），重跑只重生那幾段。
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tts_f5 import SR, F5Narrator  # noqa: E402

# 權重與參考音在雲端硬碟（Colab 上是 /content/drive/MyDrive/論文研究/Analyses/TTS/F5-TTS），一律用環境變數指定，不寫死本機路徑
F5_BASE = Path(os.environ.get("F5_BASE", "F5-TTS"))
CKPT = os.environ.get("F5_CKPT", F5_BASE / "實驗/2026-10-19_參考音挑選/v4_未平滑權重.safetensors")
REF = os.environ.get("F5_REF", F5_BASE / "實驗/2026-10-19_參考音挑選/參考音/T1_王老師_scanf與and_5.7秒.wav")
REF_TEXT = os.environ.get("F5_REF_TEXT", "就是在 scanf 的時候，scanf 的時候你要在變數前面加一個 and。")
SEED = int(os.environ.get("F5_SEED", "5"))
# 英文開頭的句子另用一組（2026-10-22 人耳：老師「bit 的 and」seed 4 最好）
EN_REF = Path(os.environ.get("F5_EN_REF", F5_BASE / "實驗/2026-10-22_英文開頭參考音/參考音/E1_bit的and_seg_030.wav"))
EN_REF_TEXT = os.environ.get("F5_EN_REF_TEXT", "bit 的 and ，也就是說把五跟七都寫成二進位，然後一個 bit 一個 bit 去比。")
EN_SEED = int(os.environ.get("F5_EN_SEED", "4"))


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
	dur_path = os.path.join(out_dir, "durations.json")
	cache = json.load(open(dur_path, encoding="utf-8")) if os.path.exists(dur_path) else {}
	reseed_path = os.path.join(out_dir, "f5_reseed.json")
	seeds = json.load(open(reseed_path, encoding="utf-8")) if os.path.exists(reseed_path) else {}

	voices = {"en_lead": (EN_REF, EN_REF_TEXT, EN_SEED)} if EN_REF.exists() else {}
	if not voices:
		print(f"⚠ 找不到英文開頭參考音 {EN_REF}，英文開頭的句子也會用預設參考音（容易念錯）")
	try:
		voice = F5Narrator(CKPT, REF, REF_TEXT, seed=SEED, voices=voices, cache_dir=os.path.join(audio_dir, "f5_chunks"))
	except FileNotFoundError as e:
		raise SystemExit(f"找不到 {e}（設 F5_BASE 指到 F5-TTS 資料夾，或用 F5_CKPT／F5_REF 個別指定）")

	jobs = [(s["slide_id"], i, a["text"]) for s in actions["slides"]
		for i, a in enumerate(s["actions"]) if a["type"] == "speech"]
	print(f"共 {len(jobs)} 段語音（F5-TTS，預設 seed {SEED}，英文開頭 seed {EN_SEED}）")
	flagged, t0 = [], time.time()
	for n, (sid, idx, text) in enumerate(jobs, start=1):
		key = f"{sid}#{idx}"
		audio, recs = voice.speak(text, seeds=seeds)
		digest = hashlib.sha1("|".join(r["digest"] for r in recs).encode("utf-8")).hexdigest()[:12]
		wav = os.path.join(audio_dir, f"{sid}_{idx:02d}_f5_{digest}.wav")
		if not os.path.exists(wav):
			sf.write(wav, audio, SR, subtype="PCM_16")
		warnings = [f"第 {k + 1} 片段{w}" for k, r in enumerate(recs) for w in r["warnings"]]
		if warnings:
			flagged.append(key)
		cache[key] = {
			"digest": digest,
			"text": text,
			"wav": wav,
			"duration": round(len(audio) / SR, 3),
			"voiced": round(sum(r["voiced"] for r in recs), 3),
			"max_gap": max(r["max_gap"] for r in recs),
			"tries": 1,
			"accepted": not warnings,
			"backend": "f5",
			"chunks": recs,
		}
		print(f"[{n}/{len(jobs)}] {key} {len(audio) / SR:.1f}s（{len(recs)} 片段：{'、'.join(r['voice'] for r in recs)}）{'　⚠ ' + '；'.join(warnings) if warnings else ''}")
		json.dump(cache, open(dur_path, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")

	total = sum(v["duration"] for v in cache.values())
	print(f"\n完成，耗時 {time.time() - t0:.0f} 秒；語音總長 {total:.1f} 秒")
	if flagged:
		print(f"自動檢查有疑慮：{flagged}（換 seed 寫進 {reseed_path}）")
	print(f"時長表：{dur_path}\n成品要人耳聽過才算數。")
	return 0


if __name__ == "__main__":
	sys.exit(main())
