"""保存既有樣片並建立配音身份；不呼叫模型或 TTS。"""
import argparse
import copy
import hashlib
import json
import pathlib
import shutil
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "video_engine/board"))
from compile import compile_scene, load_catalog
from build import build


def digest(path):
	return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
	return json.loads(path.read_text())


def save(path, value):
	path.write_text(json.dumps(value, ensure_ascii=False, indent="\t") + "\n")


def pcm(path):
	with wave.open(str(path)) as wav:
		return wav.getparams(), wav.readframes(wav.getnframes())


def validate_identity(scene, binding, audio, timing):
	texts = [b.get("spoken") or b["say"] for s in scene["scenes"] for b in s["beats"]]
	if texts != binding["spoken"]:
		raise ValueError("講稿身份不符，拒絕使用舊 timing")
	if digest(audio) != binding["audio_sha256"]:
		raise ValueError("音檔身份不符，拒絕使用舊 timing")
	if digest(timing) != binding["timing_sha256"]:
		raise ValueError("timing 身份不符")


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--source", default="/tmp/videomaker-step1-preview-20261008/units/ecdc0848e6bb")
	args = ap.parse_args()
	source = pathlib.Path(args.source)
	out = HERE / "out"
	out.mkdir(exist_ok=True)
	voice = source / "q2/voice"
	original = load(source / "q2.scene.json")
	narration = load(voice / "narration.json")
	beats = [b for s in original["scenes"] for b in s["beats"]]
	assert len(beats) == len(narration["beats"]) == 12
	assert all(b["say"] == r["text"] for b, r in zip(beats, narration["beats"]))
	params, master = pcm(voice / "master.wav")
	assert params.nchannels == 1 and params.sampwidth == 2
	sr = params.framerate
	pieces = [bytes(int(sr * .4) * 2)]
	prev_scene, start = 0, .4
	rows = []
	for i, rec in enumerate(narration["beats"]):
		p, data = pcm(voice / "audio" / rec["wav"])
		assert (p.nchannels, p.sampwidth, p.framerate) == (1, 2, sr)
		if i:
			gap = int(sr * (.35 + (.6 if rec["scene"] != prev_scene else 0)))
			pieces.append(bytes(gap * 2))
			start += gap / sr
		pieces.append(data)
		rows.append({"index": i, "text": rec["text"], "wav": rec["wav"], "audio_sha256": digest(voice / "audio" / rec["wav"]), "start": start, "duration": p.nframes / sr, "asr": rec.get("asr")})
		start += p.nframes / sr
		prev_scene = rec["scene"]
	assert b"".join(pieces) == master, "保存 master 與逐句 WAV 無法逐樣本重建"
	shutil.copyfile(source / "q2.scene.json", out / "original.scene.json")
	shutil.copyfile(voice / "master.wav", out / "audio.wav")
	shutil.copyfile(voice / "timing.json", out / "timing.json")
	shutil.copyfile(source / "q2/video.mp4", out / "A-original.mp4")
	shutil.copytree(source / "q2/player", out / "A-player", dirs_exist_ok=True)
	(out / "saved-voice").mkdir(exist_ok=True)
	for name in ["narration.json", "timing.json"]:
		shutil.copyfile(voice / name, out / "saved-voice" / name)
	shutil.copytree(voice / "audio", out / "saved-voice/audio", dirs_exist_ok=True, ignore=shutil.ignore_patterns("raw"))
	reconciled = copy.deepcopy(original)
	for b, rec in zip([b for s in reconciled["scenes"] for b in s["beats"]], narration["beats"]):
		b["spoken"] = rec["text"]
	binding = {"version": 1, "origin": "saved Gemini narration, renderer fixture; no generation in this run", "spoken": [r["text"] for r in narration["beats"]], "voice": {"tts": narration["tts"], "speed": narration["speed"], "model": "gemini-3.8-flash-tts", "voice_name": "unknown in saved metadata; not inferred"}, "audio_sha256": digest(out / "audio.wav"), "timing_sha256": digest(out / "timing.json"), "master_pcm_rebuilt_byte_identical": True, "scene_spoken_mismatches": [i for i, (b, r) in enumerate(zip(beats, narration["beats"])) if b.get("spoken") != r["text"]], "beats": rows}
	validate_identity(reconciled, binding, out / "audio.wav", out / "timing.json")
	save(out / "identity.json", binding)
	save(out / "reconciled.scene.json", reconciled)
	# 只在實測句界演出；不把中文字位置比例當作詞級時間。
	upgraded = copy.deepcopy(reconciled)
	upgraded["corner_note"] = "固定 fixture · 保存配音"
	for scene in upgraded["scenes"]:
		for beat in scene["beats"]:
			for action in beat["do"]:
				action.pop("cue", None)
				if action is not beat["do"][0]:
					action["with"] = "prev"
	upgraded["objects"].append({"id": "sum_output", "type": "output", "label": "計算結果"})
	upgraded["scenes"][1]["beats"][1]["do"].append({"act": "show", "target": "sum_output", "with": "prev"})
	upgraded["scenes"][1]["beats"][1]["do"].append({"act": "set", "target": "sum_output", "text": "1 + 2 + 3 + 4 + 5 = 15", "with": "prev"})
	upgraded["scenes"][1]["beats"][1]["layout"] = {"stack": [{"row": ["code_sum", "vars_sum"]}, "sum_output"]}
	upgraded["scenes"][1]["beats"][0]["do"] = [a for a in upgraded["scenes"][1]["beats"][0]["do"] if a["act"] != "set"]
	wrong_code = copy.deepcopy(next(o for o in upgraded["objects"] if o["id"] == "code_arr"))
	wrong_code["id"] = "wrong_code_arr"
	wrong_code["caption"] = "錯誤示範：把 < 改成 <="
	wrong_code["lines"][1] = wrong_code["lines"][1].replace("i < 5", "i <= 5")
	upgraded["objects"].append(wrong_code)
	bad_beat = upgraded["scenes"][2]["beats"][2]
	bad_beat["do"] = [{"act": "circle", "target": "wrong_code_arr:L2"}, {"act": "stop", "target": "arr_cells", "index": 4, "note": "索引 5 不存在！", "with": "prev"}]
	fix_beat = upgraded["scenes"][2]["beats"][3]
	array_scene = upgraded["scenes"][2]
	array_scene["beats"] = array_scene["beats"][:2]
	upgraded["scenes"][3:3] = [
		{"id":"array_error","title":"誤用 <= 5，會讓索引走到不存在的一格","label":"錯誤示範","keep":["arr_cells"],"layout":{"stack":["wrong_code_arr","arr_cells"]},"beats":[bad_beat]},
		{"id":"array_fix","title":"最後有效索引是四：條件恢復 < 5","label":"修正邊界","keep":["arr_cells"],"layout":{"stack":["code_arr","arr_cells"]},"beats":[fix_beat]},
	]
	upgraded["objects"] = [o for o in upgraded["objects"] if o["id"] != "rule_note"]
	upgraded["objects"].append({"id": "rule_note", "type": "pipeline", "title": "判斷邊界的順序", "direction": "row", "stages": [{"id": "start", "label": "先看起點"}, {"id": "end", "label": "確認最後值"}, {"id": "rule", "label": "選擇條件"}]})
	upgraded["scenes"][-1]["beats"][-1]["do"] = [{"act": "show", "target": "rule_note"}, {"act": "step", "target": "rule_note:rule", "with": "prev"}]
	save(out / "B-board.scene.json", upgraded)
	validate_identity(upgraded, binding, out / "audio.wav", out / "timing.json")
	# 相同句數但不同講稿／聲音是必要的反向控制。
	bad = copy.deepcopy(upgraded)
	bad["scenes"][0]["beats"][0]["spoken"] = "不同講稿但相同句數"
	try:
		validate_identity(bad, binding, out / "audio.wav", out / "timing.json")
	except ValueError:
		text_rejected = True
	else:
		raise AssertionError("錯誤講稿未被拒絕")
	bad_audio = out / "wrong-audio.control.wav"
	wrong_pcm = bytearray(master)
	first_start = int(rows[0]["start"] * sr) * 2
	first_end = first_start + int(rows[0]["duration"] * sr) * 2
	wrong_pcm[first_start:first_end] = bytes(first_end - first_start)
	with wave.open(str(bad_audio), "wb") as wav:
		wav.setparams(params)
		wav.writeframes(bytes(wrong_pcm))
	try:
		validate_identity(upgraded, binding, bad_audio, out / "timing.json")
	except ValueError:
		audio_rejected = True
	else:
		raise AssertionError("錯誤音檔未被拒絕")
	save(out / "identity-controls.json", {"same_count_different_script_rejected": text_rejected, "different_audio_rejected": audio_rejected, "audio_negative_method":"same duration PCM with first sentence muted"})
	tl = compile_scene(upgraded, load(out / "timing.json"), load_catalog())
	save(out / "B-timeline.json", tl)
	build(tl, str(out / "B-player"), str(out / "audio.wav"))
	patches = {
		"code.js": [("size: 36", "size: 44")],
		"vars.js": [("size: 28", "size: 32"), ("size: 30", "size: 32")],
		"output.js": [("LABEL = {size: 30}", "LABEL = {size: 32}")],
		"cells.js": [("LABEL_H = 50, STOP_H = 50", "LABEL_H = 60, STOP_H = 60"), ("size: 36", "size: 44"), ("size: 34", "size: 44"), ("size: 40", "size: 44")],
	}
	patch_log = []
	for name, changes in patches.items():
		file = out / "B-player/runtime/components" / name
		text = file.read_text()
		for before, after in changes:
			count = text.count(before)
			assert count > 0, f"上游 runtime 已改版，無法適配 {name} {before}"
			text = text.replace(before, after)
			patch_log.append({"file": name, "before": before, "after": after, "count": count})
		file.write_text(text)
	save(out / "B-typography-adaptation.json", patch_log)
	print(json.dumps({"duration": tl["duration"], "identity": "pass", "gaps": tl["gaps"], "warnings": tl["warnings"]}, ensure_ascii=False))


if __name__ == "__main__":
	main()
