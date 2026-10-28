#!/usr/bin/env python3
"""story 資料夾 → picks.json：每句用幾個 seed 各合成一次，機器挑一版（tts_f5.pick），f5_story.py 照它合成。

用法（Colab GPU；要先裝 faster-whisper、funasr、opencc-python-reimplemented、praat-parselmouth）：
  python video_engine/explainer/f5_pick.py <story 資料夾> [--lines 1,2,3 | --lines all] [--seeds 5,1,2,3,4,6,7,8]

只挑 picks.json 裡還沒有、或文字改過的句子；seeds.json（人耳指定）優先於 picks.json，那些句子不挑。
寫出 picks.json（句號 → seed、原文、是否可疑）、pick_report.json（每個候選的分數與兩種 ASR 聽到的字）、
audio/pick_listen.wav（挑中的版本依序接起來，人要抽查時聽這一個就好）。
可疑句＝所有 seed 都不及格：多半是句子本身難念，改寫句子比再多試 seed 有用。
"""
import argparse
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from synth_f5 import CKPT, EN_REF, EN_REF_TEXT, EN_SEED, REF, REF_TEXT, SEED  # noqa: E402
from tts_f5 import SR, F5Narrator  # noqa: E402
from tts_f5.pick import Judge, choose  # noqa: E402

SEEDS = [SEED, 1, 2, 3, 4, 6, 7, 8]


def load(path, default):
	return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("story")
	ap.add_argument("--lines", default="all")
	ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
	a = ap.parse_args()
	seeds = [int(x) for x in a.seeds.split(",")]
	s = json.load(open(os.path.join(a.story, "story.dry.json"), encoding="utf-8"))
	pinned = {int(k) for k in load(os.path.join(a.story, "seeds.json"), {})}
	pp = os.path.join(a.story, "picks.json")
	picks = load(pp, {})
	want = None if a.lines == "all" else {int(x) for x in a.lines.split(",")}

	voices = {"en_lead": (EN_REF, EN_REF_TEXT, EN_SEED)} if EN_REF.exists() else {}
	voice = F5Narrator(CKPT, REF, REF_TEXT, seed=SEED, voices=voices, cache_dir=os.path.join(a.story, "audio", "f5"))
	judge = Judge()
	report = load(os.path.join(a.story, "pick_report.json"), {})
	for line in s["lines"]:
		i, text = line["i"], line["text"]
		if i in pinned or (want is not None and i not in want):
			continue
		if str(i) in picks and picks[str(i)]["text"] == text:
			continue
		cands = []
		for sd in seeds:
			x, recs = voice.speak(text, seeds={c: sd for c in voice.chunks(text)}, pad=(0, 0))
			sc = judge.score(text, x, SR, sum(r["voiced"] for r in recs), max(r["max_gap"] for r in recs))
			sc["seed"] = sd
			cands.append(sc)
		med = float(np.median([c["rate"] for c in cands]))
		for c in cands:
			c["dev"] = abs(c["rate"] - med) / med
		k, sus = choose(cands, question=text.rstrip().endswith(("？", "?")))
		picks[str(i)] = {"seed": cands[k]["seed"], "text": text, "suspicious": sus}
		report[str(i)] = {"text": text, "picked": cands[k]["seed"], "suspicious": sus, "candidates": cands}
		print(f"{i:>2} seed {cands[k]['seed']:>2}{'  ⚠ 可疑' if sus else ''}  cer {cands[k]['cer']:.2f} 句尾 {cands[k]['rise']:+.1f}  {text[:24]}", flush=True)
		json.dump(picks, open(pp, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
		json.dump(report, open(os.path.join(a.story, "pick_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent="\t")

	# 抽查用：挑中的版本依序接起來，句間 0.8 秒
	clips = []
	for line in s["lines"]:
		p = picks.get(str(line["i"]))
		if p and p["text"] == line["text"] and (want is None or line["i"] in want):
			x, _ = voice.speak(line["text"], seeds={c: p["seed"] for c in voice.chunks(line["text"])}, pad=(0, 0))
			clips += [x, np.zeros(int(SR * 0.8), np.float32)]
	if clips:
		sf.write(os.path.join(a.story, "audio", "pick_listen.wav"), np.concatenate(clips), SR, subtype="PCM_16")
	n_sus = sum(1 for p in picks.values() if p["suspicious"])
	print(f"picks.json：{len(picks)} 句，可疑 {n_sus} 句")
	return 0


if __name__ == "__main__":
	sys.exit(main())
