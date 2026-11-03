#!/usr/bin/env python3
"""岚叔 explainer 的 story（--dry 骨架）＋F5 逐句配音 → 實測時間的 story.json 與 narration.wav。

用法：
  (cd <lanshu>/explainer && python3 tools/story.py <story 資料夾> --dry)     # 先產骨架
  ~/.venvs/f5tts/bin/python video_engine/explainer/f5_story.py <story 資料夾>

岚叔的 --audio 是從錄音的停頓找句界、逐字時間用權重估；我們的 F5 本來就有每句的實際長度，
所以句界用實測、句間停頓沿用骨架的設計、句內逐字只按比例縮放骨架的估計。
骨架第一次讀到時另存成 story.dry.json，之後一律從它重建，重跑不會越疊越歪。

分頁：story 資料夾有 pages.json（例如 [[1],[2],[3,4]]，結語句不列）就照它分，沒有就每章兩句一頁。
screens.json（例如 [{"lines": [8, 9], "kind": "vscode"}]）列出改在電腦畫面上演的句子，它們不進 pages。
recap.json（{"say": "..."}）給複習頁一句旁白；岚叔的複習頁原本無聲。
seeds.json（例如 {"3": 11}）指定個別句子的 seed：同一句換 seed 停頓與語速差很多，人耳挑過的寫在這裡才重跑得出來。
picks.json 是 f5_pick.py 機器挑的 seed（多 seed＋ASR／句尾音高打分），seeds.json 有寫的句子以 seeds.json 為準。
holds.json（例如 {"15": 1.0}）在該句講完後多停幾秒：操作步驟點下去之後，留時間讓學生看到結果再往下講。
leads.json（例如 {"6": 2.0}）在該句開口前空幾秒給 beats 先把圖畫完（先畫後講，使用者 2026-10-25）；寫進 story.json 該句的 lead，
黑板鏡頭照 start − lead 到位；hold 也寫進 story.json，換頁照 end ＋ hold 才出發。
兩者寫進 story.json 的 pages／screens，黑板照它擺版。粉筆頁換頁用板擦擦掉、其餘直線平移，句間至少留 TRAVEL_GAP；
進出電腦畫面要畫螢幕框再推近，至少留 SCREEN_GAP。同頁句間照骨架，不另加停頓。
"""
import json
import os
import shutil
import sys

import numpy as np
import soundfile as sf
import torch
import torchaudio

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from synth_f5 import CKPT, EN_REF, EN_REF_TEXT, EN_SEED, REF, REF_TEXT, SEED  # noqa: E402
from tts_f5 import SR, F5Narrator  # noqa: E402

from pages import (ERASE_GAP, RECAP_LEAD, RECAP_TAIL, SCREEN_GAP, TRAVEL_GAP,  # noqa: E402,F401
	apply_leads, gap_after, load_pauses, make_pages, recap_start, recap_window)

OUT_SR = 48000


def main():
	if len(sys.argv) != 2:
		print(__doc__)
		return 2
	story_dir = sys.argv[1]
	path = os.path.join(story_dir, "story.json")
	dry_path = os.path.join(story_dir, "story.dry.json")
	current = json.load(open(path, encoding="utf-8"))
	# pages.py 排過的草稿不是骨架，骨架已經在 story.dry.json
	if current.get("draft") and not current.get("paged"):
		shutil.copy(path, dry_path)
	if not os.path.exists(dry_path):
		raise SystemExit("找不到骨架：先跑 tools/story.py <story> --dry")
	s = json.load(open(dry_path, encoding="utf-8"))

	voices = {"en_lead": (EN_REF, EN_REF_TEXT, EN_SEED)} if EN_REF.exists() else {}
	voice = F5Narrator(CKPT, REF, REF_TEXT, seed=SEED, voices=voices, cache_dir=os.path.join(story_dir, "audio", "f5"))

	report = []
	sp = os.path.join(story_dir, "seeds.json")
	# 機器挑的（f5_pick.py）先放，人耳指定的 seeds.json 蓋過它；句子改過字的挑選結果不算
	pk = os.path.join(story_dir, "picks.json")
	picks = json.load(open(pk, encoding="utf-8")) if os.path.exists(pk) else {}
	text_of = {L["i"]: L["text"] for L in s["lines"]}
	line_seed = {int(k): v["seed"] for k, v in picks.items() if text_of.get(int(k)) == v["text"]}
	if os.path.exists(sp):
		line_seed.update({int(k): v for k, v in json.load(open(sp, encoding="utf-8")).items()})
	audios = []
	for line in s["lines"]:
		seeds = {c: line_seed[line["i"]] for c in voice.chunks(line["text"])} if line["i"] in line_seed else None
		audio, recs = voice.speak(line["text"], seeds=seeds, pad=(0, 0))
		audios.append(audio)
		report.append({"i": line["i"], "text": line["text"], "seconds": round(len(audio) / SR, 2),
			"voice": [r["voice"] for r in recs], "spoken": [r["spoken"] for r in recs],
			"warnings": [w for r in recs for w in r["warnings"]]})
		print(f"{line['i']:>2} {len(audio) / SR:4.1f}s {'／'.join(r['voice'] for r in recs)} {line['text'][:22]}", flush=True)
	# 句界照實測長度重排；clips 的起點用未四捨五入的值，和 story.json 的 start 差不到 1ms
	starts = []
	apply_leads(s, story_dir, [len(a) / SR for a in audios], starts)
	clips = list(zip(starts, audios))

	rp = os.path.join(story_dir, "recap.json")
	if s.get("recap") and os.path.exists(rp):
		say = json.load(open(rp, encoding="utf-8"))["say"]
		audio, recs = voice.speak(say, pad=(0, 0))
		at, s["recap"]["end"] = recap_window(s["recap"]["start"], s["recap"]["end"], len(audio) / SR)
		s["recap"]["end"] = round(s["recap"]["end"], 3)
		s["recap"]["say"] = {"text": say, "start": round(at, 3), "end": round(at + len(audio) / SR, 3)}
		clips.append((at, audio))
		print(f"複習頁 {len(audio) / SR:4.1f}s {say[:22]}", flush=True)
	if s.get("recap"):
		s["duration"] = max(s["duration"], s["recap"]["end"])
	s.pop("paged", None)
	s["draft"] = False
	s["timing"] = "f5: 句界實測，句內逐字依骨架估計等比縮放"
	s["voice"] = "F5-TTS 王老師 v4"

	master = np.zeros(int(round(s["duration"] * SR)) + SR, np.float32)
	for start, audio in clips:
		i = int(round(start * SR))
		master[i:i + len(audio)] = audio[: max(0, len(master) - i)]
	master = master[: int(round(s["duration"] * SR))]
	up = torchaudio.functional.resample(torch.from_numpy(master), SR, OUT_SR).numpy()
	out_wav = os.path.join(story_dir, s["narration"])
	os.makedirs(os.path.dirname(out_wav), exist_ok=True)
	sf.write(out_wav, up, OUT_SR, subtype="PCM_16")
	json.dump(s, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
	json.dump(report, open(os.path.join(story_dir, "f5_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
	print(f"story.json：{s['duration']:.1f}s，{len(s['lines'])} 句；{out_wav}。成品要人耳聽過才算數。")
	return 0


if __name__ == "__main__":
	sys.exit(main())
