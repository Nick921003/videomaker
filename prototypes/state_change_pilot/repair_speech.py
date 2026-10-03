"""保留 Claude 旁白原文，僅對 TTS 加入英文字母發音提示。"""
import hashlib
import argparse
import json
from pathlib import Path
import re
import sys
import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video_engine"))
import synth

OUT = ROOT / "video_engine/out/state_change_pilot_20261001"
PRONUNCIATION = {"A": "欸", "l": "欸爾", "i": "哎", "c": "西", "e": "衣",
	"Al": "欸、欸爾", "Ali": "欸、欸爾、哎", "Alic": "欸、欸爾、哎、西"}


def tighten_pauses(path, record):
	# 只壓短語句內已確認的靜音；原始 WAV 留存，不裁切有聲部分。
	sr, data = wavfile.read(path)
	n = sr // 50
	x = data.astype(np.float32) / 32768
	rms = np.sqrt((x[:len(x)//n*n].reshape(-1, n)**2).mean(1))
	silent = (rms < synth.SIL_FLOOR) | (rms < rms.max()*.02)
	pieces, last, i, removed = [], 0, 0, 0
	while i < len(silent):
		if not silent[i]:
			i += 1
			continue
		j = i
		while j < len(silent) and silent[j]:
			j += 1
		if i > 0 and j < len(silent) and (j-i)*.02 > .5:
			keep = int(sr*.32)
			pieces.append(data[last:i*n+keep//2])
			last = j*n-keep//2
			removed += (j-i)*n-keep
		i = j
	pieces.append(data[last:])
	clean = np.concatenate(pieces)
	output = path.with_name(path.stem+"_tight.wav")
	wavfile.write(output, sr, clean)
	total, voiced, gap, _ = synth.analyse(sr, clean)
	peak = float(np.abs(clean.astype(np.float32)/32768).max())
	ok, why = synth.verdict(record["tts_text"], total, voiced, gap, peak)
	return dict(record, raw_file=record["file"], file=str(output.relative_to(OUT)),
		raw_quality_ok=record["quality_ok"], quality_ok=ok, raw_metrics=record["metrics"],
		metrics=dict(record["metrics"], total=total, voiced=voiced, max_gap=gap, peak=peak),
		pause_edit={"removed_seconds": removed/sr, "inner_pause_cap_seconds": .32, "verdict": why})


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--mode", choices=["phonetic", "chinese"], default="phonetic")
	args = parser.parse_args()
	backup = OUT / "tts_usage_first_pass.json"
	if not backup.exists():
		with backup.open("x") as handle:
			handle.write((OUT / "tts_usage.json").read_text())
	board = json.loads((OUT / "storyboard.json").read_text())
	first = json.loads(backup.read_text())
	previous = json.loads((OUT / "tts_usage.json").read_text())
	if args.mode == "chinese" and not (OUT / "tts_usage_phonetic_pass.json").exists():
		with (OUT / "tts_usage_phonetic_pass.json").open("x") as handle:
			handle.write(json.dumps(previous, ensure_ascii=False, indent=2))
	current = []
	synth.MAX_TRIES = 1
	for beat, original in zip(board["beats"], first):
		if beat["phase"] != "scan":
			current.append(original)
			continue
		text = re.sub(r"\b(?:Alic|Ali|Al|A|l|i|c|e)\b",
			lambda match: PRONUNCIATION[match.group()], beat["speech"])
		if args.mode == "chinese":
			text = re.sub(r"讀到 [A-Za-z]+", "讀到這個字母", beat["speech"])
			text = re.sub(r"畫面先出現 A", "畫面先出現一個字母", text)
			text = re.sub(r"輸出(?:變成|累積成) [A-Za-z]+", "輸出又多一個字母", text)
		digest = hashlib.sha256(text.encode()).hexdigest()[:12]
		path = OUT / "audio" / f"{beat['id']}_{args.mode}_{digest}.wav"
		meta = path.with_suffix(".json")
		if path.exists() and meta.exists():
			record = json.loads(meta.read_text())
		else:
			metrics, ok = synth.synth_one(text, 1.0, str(path))
			record = dict(original, file=str(path.relative_to(OUT)), tts_text=text,
				speed_factor=1.0, quality_ok=ok, metrics=metrics, calls=metrics["frags"],
				pronunciation_note="發音提示" if args.mode == "phonetic" else "本機旁白修訂：以中文指涉畫面字母，避免英文字母發音混淆；Claude原稿保留",
				attempt=2 if args.mode == "phonetic" else 3, authorization="使用者要求重做字母旁白並驗證")
			with meta.open("x") as handle:
				handle.write(json.dumps(record, ensure_ascii=False, indent=2))
		record = tighten_pauses(path, record)
		print(beat["id"], repr(text), record["metrics"], "pause_edit=", record["pause_edit"], flush=True)
		if not record["quality_ok"]:
			raise RuntimeError("修正音檔未通過品質检查；先診斷，不自動重試。")
		current.append(record)
	(OUT / "tts_usage.json").write_text(json.dumps(current, ensure_ascii=False, indent=2))
	repairs = [rec for rec in current if rec.get("attempt") in (2, 3)]
	if args.mode == "chinese":
		repairs += [rec for rec in json.loads((OUT / "tts_usage_phonetic_pass.json").read_text()) if rec.get("attempt") == 2]
	(OUT / "tts_call_ledger.json").write_text(json.dumps({"first_pass": first,
		"authorized_repairs": repairs,
		"total_local_tts_calls": sum(rec["calls"] for rec in first) + sum(rec["calls"] for rec in repairs),
		"external_llm_tokens": 0}, ensure_ascii=False, indent=2))
