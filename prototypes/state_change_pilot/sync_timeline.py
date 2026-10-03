"""以實測 ASR 詞時間排程輸出與停止；缺少錨點就明確停止。"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video_engine/out/state_change_pilot_20261001"


def word_key(value):
	value = value.translate(str.maketrans({"读": "讀", "输": "輸", "结": "結", "长": "長", "个": "個", "1": "一"}))
	return re.sub(r"[^\w\u4e00-\u9fff]", "", value)


def locate(words, needle):
	keys, times = "", []
	for word in words:
		key = word_key(word["word"])
		keys += key
		times.extend([(word["start"], word["end"])]*len(key))
	index = keys.find(needle)
	if index < 0:
		raise ValueError(f"ASR 缺少同步錨點 {needle}")
	return times[index][0], times[index+len(needle)-1][1]


if __name__ == "__main__":
	d = json.loads((OUT / "pilot_timeline.json").read_text())
	a = json.loads((OUT / "asr.json").read_text())
	all_words = [word for segment in a["segments"] for word in segment["words"]]
	records = []
	for s in d["segments"]:
		words = [word for word in all_words if s["start"]-.08 <= word["start"] < s["speech_end"]]
		if s["phase"] == "scan":
			anchor = "多一個字母" if "多一個字母" in s["speech"] else "輸出"
			start, end = locate(words, anchor)
			s["append_time"] = end
			read_start, read_end = locate(words, "讀到")
			s["flight_start"] = read_end
			records.append({"id": s["id"], "anchor": anchor, "asr_start": start,
				"asr_end": end, "visual_time": end, "flight_start": read_end,
				"error_against_anchor_end": 0.0})
		elif s["phase"] == "stop":
			start, end = locate(words, "停止")
			s["stop_time"] = start
			records.append({"id": s["id"], "anchor": "停止", "asr_start": start,
				"asr_end": end, "visual_time": start, "error_against_anchor_start": 0.0})
		elif s["phase"] == "copy":
			start, end = locate(words, "字元")
			copy_start = s["start"] + min(1.6, (end-s["start"])*.5)
			s["copy_times"] = [copy_start + (end-copy_start)*i/5 for i in range(6)]
		elif s["phase"] == "question":
			start, end = locate(words, "不算")
			s["answer_time"] = start
		duration = s["speech_end"]-s["start"]
		assert duration > 0
	d["sync_precision"] = "本機 ASR 詞時間作錨點；24fps 量化誤差 <=41.7ms，不代表 ASR 本身具有逐音素精度。"
	(OUT / "pilot_timeline.json").write_text(json.dumps(d, ensure_ascii=False, indent=2))
	(OUT / "sync_checks.json").write_text(json.dumps({"anchors": records,
		"frame_quantization_ms": 1000/24, "method": d["sync_precision"]}, ensure_ascii=False, indent=2))
	print(json.dumps(records, ensure_ascii=False, indent=2))
