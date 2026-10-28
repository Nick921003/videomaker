#!/usr/bin/env python3
"""scene.json → 配音 master.wav＋timing.json（每句實測起訖），F5-TTS 王老師聲音。

用法：~/.venvs/f5tts/bin/python video_engine/board/narrate_f5.py <scene.json> <輸出目錄>

narrate.py 的 F5 版：每句唸 `spoken`（沒有就唸 `say`），句間停頓與 compile.py 估時一致，
產出的 timing.json 可直接餵 compile.py --timing。參考音、seed 沿用 synth_f5.py 的設定
（英文開頭的句子自動換參考音）。不產 timing.identity.json，所以 compile 會標成待審：
F5 的成品一律要人耳聽過。
"""
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from compile import BEAT_GAP, LEAD_IN, SCENE_GAP  # noqa: E402
from synth_f5 import CKPT, EN_REF, EN_REF_TEXT, EN_SEED, REF, REF_TEXT, SEED  # noqa: E402
from tts_f5 import SR, F5Narrator  # noqa: E402


def main():
	if len(sys.argv) != 3:
		print(__doc__)
		return 2
	scene = json.load(open(sys.argv[1], encoding="utf-8"))
	out_dir = sys.argv[2]
	os.makedirs(out_dir, exist_ok=True)
	voices = {"en_lead": (EN_REF, EN_REF_TEXT, EN_SEED)} if EN_REF.exists() else {}
	voice = F5Narrator(CKPT, REF, REF_TEXT, seed=SEED, voices=voices, cache_dir=os.path.join(out_dir, "f5_chunks"))

	pieces, timing, beats = [np.zeros(int(SR * LEAD_IN), np.float32)], [], []
	t, prev_scene = LEAD_IN, None
	for si, sc in enumerate(scene["scenes"]):
		for bi, beat in enumerate(sc["beats"]):
			text = beat.get("spoken") or beat["say"]
			if prev_scene is not None:
				gap = BEAT_GAP + (SCENE_GAP if si != prev_scene else 0)
				pieces.append(np.zeros(int(SR * gap), np.float32))
				t += int(SR * gap) / SR
			audio, recs = voice.speak(text, pad=(0, 0))
			dur = len(audio) / SR
			timing.append({"t0": round(t, 3), "t1": round(t + dur, 3)})
			beats.append({"scene": si, "i": bi, "text": text, "chunks": recs})
			pieces.append(audio)
			t += dur
			prev_scene = si
			warn = "；".join(w for r in recs for w in r["warnings"])
			print(f"[{si}/{bi}] {dur:.1f}s {'／'.join(r['voice'] for r in recs)} {text[:20]}{'　⚠ ' + warn if warn else ''}", flush=True)

	sf.write(os.path.join(out_dir, "master.wav"), np.concatenate(pieces), SR, subtype="PCM_16")
	json.dump(timing, open(os.path.join(out_dir, "timing.json"), "w", encoding="utf-8"), ensure_ascii=False)
	json.dump(beats, open(os.path.join(out_dir, "narration.json"), "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
	print(f"master.wav {t:.1f}s，{len(timing)} 句。成品要人耳聽過才算數。")
	return 0


if __name__ == "__main__":
	sys.exit(main())
