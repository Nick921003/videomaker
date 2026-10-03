"""合成 A+C 四段完整旁白；每段至多呼叫一次並保留原始音檔。"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "video_engine"))
import synth

OUT = ROOT / "video_engine/out/state_change_ac_20261001"
SOURCE = ROOT / "video_engine/out/state_change_natural_20261001/narrative_edited.json"
USAGE = OUT / "tts_usage.json"


def metrics(sr, data, text):
	total, voiced, max_gap, gap_total = synth.analyse(sr, data)
	peak = float(np.abs(data.astype(np.float32) / 32768).max())
	ok, reason = synth.verdict(text, total, voiced, max_gap, peak)
	return {
		"total": total, "totalseconds": total, "sample_rate": sr,
		"peak": peak, "voiced": voiced, "max_gap": max_gap,
		"gap_total": gap_total, "quality_ok": ok, "verdict": reason,
	}


def save(records):
	USAGE.write_text(json.dumps(records, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")


def shorten_abnormal_pauses(record):
	if record.get("quality_ok") or record.get("status") != "complete" or record.get("max_gap", 0) <= synth.MAX_GAP_SEC:
		return
	path = OUT / record["file"]
	sr, data = wavfile.read(path)
	n = sr // 50
	x = data.astype(np.float32) / 32768
	rms = np.sqrt((x[:len(x) // n * n].reshape(-1, n) ** 2).mean(1))
	silent = (rms < synth.SIL_FLOOR) | (rms < rms.max() * .02)
	pieces, last, index, removed = [], 0, 0, 0
	while index < len(silent):
		if not silent[index]:
			index += 1
			continue
		end = index
		while end < len(silent) and silent[end]:
			end += 1
		# 保留正常句讀；只有超過既有品質門檻的內部空白才缩短。
		if index > 0 and end < len(silent) and (end - index) * .02 > synth.MAX_GAP_SEC:
			keep = int(sr * .5)
			pieces.append(data[last:index * n + keep // 2])
			last = end * n - keep // 2
			removed += (end - index) * n - keep
		index = end
	if not removed:
		return
	pieces.append(data[last:])
	clean = np.concatenate(pieces)
	output = path.with_name(path.stem + "_pause_clean.wav")
	wavfile.write(output, sr, clean)
	info = metrics(sr, clean, record["tts_text"])
	record["pre_pause_file"] = record["file"]
	record["pre_pause_metrics"] = record["metrics"]
	record["file"] = str(output.relative_to(OUT))
	record.update(info)
	record["metrics"] = info
	record["pause_edit"] = {
		"removed_seconds": removed / sr, "minimum_pause_seconds": synth.MAX_GAP_SEC,
		"inner_pause_cap_seconds": .5, "tts_calls": 0,
	}
	print(record["id"], "確定性縮短異常空白", json.dumps(info, ensure_ascii=False), flush=True)


def main():
	synth.MAX_TRIES = 1
	(OUT / "audio").mkdir(parents=True, exist_ok=True)
	sections = json.loads(SOURCE.read_text(encoding="utf-8"))["sections"]
	records = json.loads(USAGE.read_text(encoding="utf-8")) if USAGE.exists() else []
	for section in sections:
		sid = section["id"]
		text = section["speech"].replace("Alice", "愛麗絲")
		previous = next((rec for rec in records if rec["id"] == sid), None)
		if previous:
			if previous["speech"] != section["speech"] or previous["tts_text"] != text:
				raise RuntimeError(f"{sid} 已有呼叫紀錄，原文變動須先確認，不能自動重新合成")
			print(sid, "已有呼叫紀錄；跳過", flush=True)
			continue
		digest = hashlib.sha256(text.encode()).hexdigest()[:12]
		raw_path = OUT / "audio" / f"{sid}_{digest}_raw.wav"
		clean_path = OUT / "audio" / f"{sid}_{digest}.wav"
		record = {
			"id": sid, "speech": section["speech"], "tts_text": text,
			"speed_factor": 1.0, "calls": 1, "max_tries": 1,
			"frags": 1, "text_split_method": "cut0", "status": "requested",
			"authorization": "使用者要求 A+C 完整 MP4 含本機 TTS；每段一次",
			"file": str(clean_path.relative_to(OUT)),
			"raw_file": str(raw_path.relative_to(OUT)),
		}
		records.append(record)
		# 請求送出前記帳；中途失敗不會因重跑程式而產生額外呼叫。
		save(records)
		try:
			sr, raw = synth.tts(text, 1.0)
			wavfile.write(raw_path, sr, raw)
			record["raw_metrics"] = metrics(sr, raw, text)
			save(records)
			clean = synth.trim_and_pad(raw, sr)
			wavfile.write(clean_path, sr, clean)
			info = metrics(sr, clean, text)
			record.update(info)
			record["metrics"] = info
			record["status"] = "complete"
			record["processing"] = "僅移除頭尾靜音後補 0.15s/0.25s；內部句讀保留"
			save(records)
			print(sid, json.dumps(info, ensure_ascii=False), flush=True)
		except Exception as error:
			record.update(status="failed", error=str(error), quality_ok=False)
			save(records)
			raise
	for record in records:
		shorten_abnormal_pauses(record)
		save(records)
	return 0 if len(records) == 4 and all(rec.get("quality_ok") for rec in records) else 1


if __name__ == "__main__":
	sys.exit(main())
