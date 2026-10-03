"""以現有分鏡、四段WAV與本機ASR建立有聲影片時間軸；不呼叫LLM/TTS。"""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import re

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video_engine/out/state_change_ac_20261001"
SCENES = ROOT / "video_engine/out/state_change_scenes_20261001"
NATURAL = ROOT / "video_engine/out/state_change_natural_20261001"


class LogicParser(HTMLParser):
	def __init__(self):
		super().__init__()
		self.active = False
		self.logic = ""
	def handle_starttag(self, tag, attrs):
		self.active = tag == "script" and dict(attrs).get("id") == "animation-logic"
	def handle_endtag(self, tag):
		if tag == "script":
			self.active = False
	def handle_data(self, data):
		if self.active:
			self.logic += data


def load(path):
	return json.loads(path.read_text())


def build():
	usage = load(OUT / "tts_usage.json")
	pieces, sections, sr, cursor = [], [], 32000, 0
	def silence(seconds):
		nonlocal cursor
		piece = np.zeros(round(seconds*sr), dtype=np.int16)
		pieces.append(piece)
		cursor += len(piece)
	silence(.35)
	for index, record in enumerate(usage):
		rate, data = wavfile.read(OUT / record["file"])
		assert rate == sr and data.ndim == 1 and record["quality_ok"]
		sections.append({"id": record["id"], "start": cursor/sr,
			"end": (cursor+len(data))/sr, "speech": record["speech"], "file": record["file"]})
		pieces.append(data)
		cursor += len(data)
		if index < 3:
			silence(2.1 if index == 1 else .65)
	silence(1.25)
	master = np.concatenate(pieces)
	wavfile.write(OUT / "master.wav", sr, master)
	starts = {s["id"]: s["start"] for s in sections}
	ends = {s["id"]: s["end"] for s in sections}
	# 經本機ASR量到的各段局部語句錨點；保留原始辨識及匹配限制。
	anchors = [
		(0, 0), (starts["s1"], .3), (starts["s1"]+3.94, 3.8), (ends["s1"], 6.999),
		(starts["s2"]-.35, 7), (starts["s2"], 7.7),
		(starts["s2"]+1.54, 8.8), (starts["s2"]+4.14, 12.05),
		(starts["s2"]+4.82, 12.7), (ends["s2"], 15.8),
		(ends["s2"]+.75, 17.45), (starts["s3"], 17.5),
		(starts["s3"]+1.06, 19.0), (starts["s3"]+3.90, 25.56),
		(starts["s3"]+4.04, 25.60), (starts["s3"]+5.14, 25.65), (starts["s3"]+5.32, 26.07),
		(starts["s3"]+5.56, 27.8), (starts["s3"]+7.26, 28.5), (ends["s3"], 30.65),
		(starts["s4"]-.35, 31), (starts["s4"], 32.2),
		(starts["s4"]+3.56, 35.5), (starts["s4"]+5.42, 37.5),
		(starts["s4"]+6.96, 39.8), (ends["s4"], 43.6), (cursor/sr, 43.999),
	]
	assert all(a[0]<b[0] and a[1]<=b[1] for a,b in zip(anchors, anchors[1:]))
	def real_at(visual):
		for a,b in zip(anchors,anchors[1:]):
			if a[1]<=visual<=b[1]:
				return a[0]+(b[0]-a[0])*(visual-a[1])/(b[1]-a[1])
		return cursor/sr
	cues = load(NATURAL / "pilot_timeline.json")["subtitle_cues"]
	# 字幕依語句分段，非每個動畫事件一段旁白。
	boundaries = [0, starts["s1"]+3.94, starts["s2"], starts["s2"]+4.82,
		starts["s3"], starts["s3"]+2.18, starts["s3"]+4.04, starts["s3"]+5.56,
		starts["s4"], starts["s4"]+3.56, starts["s4"]+6.96, cursor/sr]
	assert len(boundaries) == len(cues)+1 and all(a<b for a,b in zip(boundaries,boundaries[1:]))
	subtitles = [{"start": boundaries[i], "end": boundaries[i+1], "text": c["text"]} for i,c in enumerate(cues)]
	timeline = {"duration": cursor/sr, "sections": sections,
		"anchors": [{"real": r, "visual": v} for r,v in anchors], "subtitle_cues": subtitles,
		"ending": "comparison hold; empty overview removed", "audio_sample_rate": sr,
		"new_llm_tokens": 0, "new_tts_calls_this_resume": 0, "tts_calls_original": 4,
		"alignment_note": "ASR句子/詞時間同步；遇到結束字元為同音候選，停止的停字5.32s可核對。"}
	(OUT / "movie_timeline.json").write_text(json.dumps(timeline,ensure_ascii=False,indent=2))
	board = deepcopy(load(SCENES / "scenes.json"))
	for scene in board["scenes"]:
		scene["cameras"] = [c for c in scene["cameras"] if c["focus"] != "overview"]
	data = {"board": board, "cues": cues, "tokens": load(SCENES / "token_summary.json")}
	parser = LogicParser()
	parser.feed(Path(__file__).with_name("scene_samples.html").read_text())
	assert parser.logic and "function render(t)" in parser.logic
	def encoded(value):
		return json.dumps(value,ensure_ascii=False).replace("<","\\u003c")
	markup = '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>A＋C 字串教學影片</title><style>body{margin:0;background:#ece6da;color:#302b27;font-family:"Microsoft JhengHei",sans-serif}main{max-width:1200px;margin:auto;padding:12px}canvas{display:block;width:100%;height:auto}nav{display:flex;gap:12px;align-items:center;margin-top:12px}button{padding:8px 20px;cursor:pointer}input{flex:1}#legacy{display:none}</style><main><canvas id="canvas" width="1280" height="720"></canvas><audio id="narration" src="master.wav" preload="auto"></audio><nav><button id="movie-play">播放</button><input id="movie-seek" type="range" min="0" step="0.01" aria-label="播放進度"><span id="movie-clock"></span></nav></main><div id="legacy"><input id="seek"><button id="play"></button><select id="speed"></select><div id="tabs"></div><span id="clock"></span><p id="style-note"></p><p id="usage-note"></p><p id="accessible-caption"></p></div>'''
	markup += '<script id="lesson-data" type="application/json">'+encoded(data)+'</script>'
	markup += '<script id="movie-data" type="application/json">'+encoded(timeline)+'</script>'
	markup += '<script>'+parser.logic+'</script><script>'+Path(__file__).with_name("ac_movie_overrides.js").read_text()+'</script></html>'
	(OUT / "movie.html").write_text(markup)
	def stamp(value):
		ms=round(value*1000)
		return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"
	(OUT / "subtitles.srt").write_text("\n\n".join(f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}" for i,c in enumerate(subtitles,1))+"\n")
	print(json.dumps({"duration":timeline["duration"], "sections":sections},ensure_ascii=False,indent=2))


if __name__ == "__main__":
	build()
