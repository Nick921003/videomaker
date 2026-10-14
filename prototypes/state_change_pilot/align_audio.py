"""使用既有本機 Whisper 快取定位旁白，不呼叫外部模型。"""
import json
import argparse
from pathlib import Path
import time
from dataclasses import asdict

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video_engine/out/state_change_pilot_20261001"


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--model", choices=["small", "large-v3"], default="small")
	args = parser.parse_args()
	start = time.monotonic()
	model = WhisperModel(args.model, device="cpu", compute_type="int8", cpu_threads=8,
		local_files_only=True)
	usage = json.loads((OUT / "tts_usage.json").read_text())
	timeline = json.loads((OUT / "pilot_timeline.json").read_text())
	result = {"model": f"cached faster-whisper-{args.model}", "device": "cpu", "language": "zh",
		"mode": "per-beat; WAV 精確邊界，ASR 時間加上實際音訊起點", "segments": []}
	for record, beat in zip(usage, timeline["segments"]):
		segments, info = model.transcribe(str(OUT / record["file"]), language="zh",
			word_timestamps=True, beam_size=5, vad_filter=False, condition_on_previous_text=False)
		for segment in segments:
			data = asdict(segment)
			data["beat_id"] = record["id"]
			data["start"] += beat["start"]
			data["end"] += beat["start"]
			for word in data["words"]:
				word["start"] += beat["start"]
				word["end"] += beat["start"]
			result["segments"].append(data)
			print(record["id"], round(data["start"], 2), round(data["end"], 2), data["text"], flush=True)
	result["seconds"] = round(time.monotonic()-start, 3)
	(OUT / "asr.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
