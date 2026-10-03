"""用既有 Whisper 核對 A+C 旁白；時間皆相對各段 WAV，不呼叫外部服務。"""
import argparse
import json
import time
import wave
from dataclasses import asdict
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video_engine/out/state_change_ac_20261001"
ANCHORS = {
	"s1": ["因為"],
	"s2": ["五個字母", "結束字元", "它就像"],
	"s3": ["程式從開頭", "接起來", "遇到結束字元", "就停", "所以印出來", "而不會"],
	"s4": ["結束字元不算", "但仍然", "要存", "至少"],
}
CANDIDATES = {
	("s1", "因為"): [("因为", "simplified_script_variant")],
	("s2", "它就像"): [("她就將", "possible_phonetic_or_ASR_substitution")],
	("s3", "程式從開頭"): [("從開頭", "partial_phrase; ASR omitted 程式")],
	("s3", "遇到結束字元"): [("遇到結束結緣", "possible_phonetic_or_ASR_substitution")],
	("s4", "結束字元不算"): [("結束的次元不算", "possible_phonetic_or_ASR_substitution")],
}
REVIEWS = {
	"s1": "容量32、長度5與兩者不同均辨識到；還什么/自串屬ASR疑似誤辨識，不能據此認定TTS文字錯誤。",
	"s2": "五字母、一起放入結束字元、句點與字串終點均辨識到；把/當及它就像/她就將有ASR差異。",
	"s3": "從開頭讀、字母接起來、結束時停、輸出愛麗絲及不印全部均辨識到；程式漏詞與結緣/正念需保留不確定性。",
	"s4": "容量32、長度5、不計結束字元但占一格、五字母至少六格均辨識到；計算/字串及的次元/字元有ASR差異。",
}


def match_anchor(words, text):
	chars = []
	for index, word in enumerate(words):
		chars.extend((char, index) for char in word["word"] if char.isalnum())
	joined = "".join(char for char, _ in chars)
	position = joined.find(text)
	if position < 0:
		return {"text": text, "status": "not_found", "candidates": []}
	first = chars[position][1]
	last = chars[position + len(text) - 1][1]
	return {
		"text": text, "status": "literal_match", "matched_text": text,
		"start": words[first]["start"], "end": words[last]["end"],
		"word_indices": [first, last],
		"timing_note": "Whisper 詞級邊界；多字詞中的字不能再視為精確字級邊界。",
	}


def reviewed_anchor(section_id, words, text):
	match = match_anchor(words, text)
	if match["status"] == "literal_match":
		return match
	for candidate, basis in CANDIDATES.get((section_id, text), []):
		found = match_anchor(words, candidate)
		if found["status"] == "literal_match":
			found["basis"] = basis
			found["status"] = "candidate_only"
			match["candidates"].append(found)
	return match


def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--reuse-asr", action="store_true", help="Refresh notes from existing ASR without inference")
	args = parser.parse_args()
	started = time.monotonic()
	model = None if args.reuse_asr else WhisperModel("large-v3", device="cpu", compute_type="int8",
		cpu_threads=8, local_files_only=True)
	usage = json.loads((OUT / "tts_usage.json").read_text())
	result = {
		"model": "cached faster-whisper-large-v3", "device": "cpu", "compute_type": "int8",
		"cpu_threads": 8, "local_files_only": True, "language": "zh",
		"mode": "per-WAV local seconds; original ASR text retained", "segments": [],
	}
	if args.reuse_asr:
		result = json.loads((OUT / "asr.json").read_text())
	recheck_path = OUT / "asr_vocabulary_recheck.json"
	recheck = json.loads(recheck_path.read_text()) if recheck_path.exists() else None
	notes = {
		"time_basis": "Each section's WAV starts at 0 seconds; no full-film offsets applied.",
		"method": "Original Whisper output; punctuation ignored for literal anchor search only.",
		"limitations": "ASR is evidence for content and approximate timing, not human listening or forced alignment.",
		"sections": [],
	}
	for record in usage:
		path = OUT / record["file"]
		with wave.open(str(path)) as wav:
			duration = wav.getnframes() / wav.getframerate()
		if args.reuse_asr:
			data_segments = [segment for segment in result["segments"] if segment["beat_id"] == record["id"]]
		else:
			segments, info = model.transcribe(str(path), language="zh", word_timestamps=True,
				beam_size=5, vad_filter=False, condition_on_previous_text=False)
			data_segments = [asdict(segment) for segment in segments]
		words, texts = [], []
		for data in data_segments:
			data["beat_id"] = record["id"]
			data["file"] = record["file"]
			if not args.reuse_asr:
				result["segments"].append(data)
			words.extend(data["words"])
			texts.append(data["text"])
			print(record["id"], data["start"], data["end"], data["text"], flush=True)
		notes["sections"].append({
			"id": record["id"], "file": record["file"], "duration": duration,
			"speech": record["speech"], "tts_text": record["tts_text"],
			"asr_text": "".join(texts),
			"content_review": {
				"method": "Compare full original ASR text with ledger speech and tts_text.",
				"assessment": REVIEWS[record["id"]],
				"confirmed_tts_content_defect": False,
				"human_listening_verified": False,
				"status": "ASR semantic evidence; no TTS defect established",
			},
			"anchors": [reviewed_anchor(record["id"], words, anchor)
				for anchor in ANCHORS[record["id"]]],
		})
		if record["id"] == "s3":
			notes["sections"][-1]["stop_moment"] = match_anchor(words, "停")
		if recheck:
			secondary = [segment for segment in recheck["segments"] if segment["beat_id"] == record["id"]]
			secondary_words = [word for segment in secondary for word in segment["words"]]
			notes["sections"][-1]["vocabulary_recheck"] = {
				"file": recheck_path.name, "initial_prompt": recheck["initial_prompt"],
				"asr_text": "".join(segment["text"] for segment in secondary),
				"anchors": [reviewed_anchor(record["id"], secondary_words, anchor)
					for anchor in ANCHORS[record["id"]]],
				"caution": "詞彙提示可影響辨識，不能替代人耳，也未改寫首輪ASR。",
			}
		if not args.reuse_asr:
			(OUT / "asr.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
		(OUT / "asr_alignment_notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2))
	if not args.reuse_asr:
		result["seconds"] = round(time.monotonic() - started, 3)
		(OUT / "asr.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()
