"""重用 Claude 口語稿與原分鏡，製作無 TTS 的字幕試排。"""
from copy import deepcopy
import json
from pathlib import Path
import re

import render_pilot

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "video_engine/out/state_change_pilot_20261001"
OUT = ROOT / "video_engine/out/state_change_natural_20261001"

SECTIONS = [
	{"id": "s1", "start": 0, "end": 7, "caption": "容量和長度，是兩回事",
		"speech": "這個陣列有三十二格，為什麼字串長度卻只有五？因為陣列的容量，和放進去的字串長度，是兩回事。"},
	{"id": "s2", "start": 7, "end": 16, "caption": "結束字元，標記字串的終點",
		"speech": "把 Alice 放進去時，除了五個字母，還會一起放入一個結束字元。它就像句點，告訴程式：字串到這裡結束。"},
	{"id": "s3", "start": 16, "end": 31, "caption": "從開頭讀，遇到結束字元就停",
		"speech": "輸出字串時，程式從開頭往後讀，把讀到的字母接起來。遇到結束字元就停，所以印出來的是 Alice，而不會把整個陣列都印出來。"},
	{"id": "s4", "start": 31, "end": 44, "caption": "長度不含結束字元，容量要留一格",
		"speech": "所以這裡的容量是三十二，字串長度是五。結束字元不算在長度裡，但仍然占一格；要存五個字母，至少得準備六格。"},
]

# 字幕按意思分句，同一短句可以承接多個視覺動作。
CUES = [
	(0, 3.8, "這個陣列有三十二格，為什麼字串長度卻只有五？"),
	(3.8, 7, "因為陣列的容量，和放進去的字串長度，是兩回事。"),
	(7, 11.7, "把 Alice 放進去時，除了五個字母，還會一起放入一個結束字元。"),
	(11.7, 16, "它就像句點，告訴程式：字串到這裡結束。"),
	(16, 19.2, "輸出字串時，程式從開頭往後讀，"),
	(19.2, 25, "把讀到的字母接起來。"),
	(25, 27.8, "遇到結束字元就停，"),
	(27.8, 31, "所以印出來的是 Alice，而不會把整個陣列都印出來。"),
	(31, 35.5, "所以這裡的容量是三十二，字串長度是五。"),
	(35.5, 39.8, "結束字元不算在長度裡，但仍然占一格；"),
	(39.8, 44, "要存五個字母，至少得準備六格。"),
]


def build():
	board = json.loads((OLD / "storyboard.json").read_text())
	segments = []
	for i, original in enumerate(board["beats"][:9]):
		beat = deepcopy(original)
		if i == 0:
			section, start, end = SECTIONS[0], 0, 7
		elif i == 1:
			section, start, end = SECTIONS[1], 7, 16
		elif i < 7:
			section = SECTIONS[2]
			start = (16000+(i-2)*1800)/1000
			end = (16000+(i-1)*1800)/1000
		else:
			section = SECTIONS[2] if i == 7 else SECTIONS[3]
			start, end = (25, 31) if i == 7 else (31, 44)
		beat.update(start=start, end=end, speech_end=end, speech=section["speech"],
			caption=section["caption"], narration_id=section["id"], action_time=start+.1,
			append_time=start+1.15, flight_start=start+.5)
		if i == 1:
			beat["copy_times"] = [8.8+j*.55 for j in range(6)]
		if i == 7:
			beat["stop_time"] = 25.65
		segments.append(beat)
	assert all(not re.search(r"第[零一二三四五六七八九\d]+格|游標|輸出又多", s["speech"]) for s in SECTIONS)
	assert {s["narration_id"] for s in segments if s["phase"] == "scan"} == {"s3"}
	for i, segment in enumerate(segments[2:7]):
		assert segment["index"] == i and segment["output_after"] == "Alice"[:i+1]
	assert segments[7]["index"] == 5 and segments[7]["output_after"] == "Alice"
	assert all(a["end"] == b["start"] for a, b in zip(segments, segments[1:]))
	data = {"duration": 44, "fps": 24, "canvas": [1280, 720], "silent": True,
		"continuous_narrative": True, "segments": segments,
		"subtitle_cues": [dict(start=start, end=end, text=text) for start, end, text in CUES],
		"timing_note": "無聲字幕試排，時間供預覽；未生成TTS，未宣稱語音同步。"}
	(OUT / "pilot_timeline.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
	(OUT / "narrative_edited.json").write_text(json.dumps({"sections": SECTIONS,
		"provenance": "重用已完成的Claude Opus 5.5口語稿，Codex進行問句開場與措辭編輯；不是新的Claude回應。"}, ensure_ascii=False, indent=2))
	def stamp(value):
		ms = round(value*1000)
		return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
	srt = "\n\n".join(f"{i}\n{stamp(start)} --> {stamp(end)}\n{text}" for i, (start, end, text) in enumerate(CUES, 1))+"\n"
	(OUT / "subtitles.srt").write_text(srt)
	text = "# 字串教學短片：字幕修訂稿\n\n" + "\n\n".join(s["speech"] for s in SECTIONS)
	text += "\n\n這輪沒有生成TTS；字幕時間為無聲預覽試排。Claude原稿及本機編輯稿分開保存。\n"
	(OUT / "SCRIPT.md").write_text(text)
	return data


if __name__ == "__main__":
	build()
	render_pilot.OUT = OUT
	render_pilot.render()
