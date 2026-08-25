#!/usr/bin/env python3
"""審稿閘：把 actions.json 的講稿抽出來給人改，改完寫回去並重跑驗證閘。

重跑驗證是硬需求。現場很容易改出唸函式名、全大寫縮寫這類 TTS 會出事的稿，
驗證閘本來就擋這些——回寫後不重跑等於把閘關掉。
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, ".venv/bin/python")
VALIDATE = os.path.join(HERE, "video_engine/validate.py")


def read_segments(actions_path):
	with open(actions_path, encoding="utf-8") as f:
		doc = json.load(f)
	return [
		{"slide_id": s["slide_id"], "idx": i, "text": a["text"]}
		for s in doc["slides"]
		for i, a in enumerate(s["actions"])
		if a["type"] == "speech"
	]


def write_segments(actions_path, segments):
	"""只動 speech 的 text，動作結構完全不碰——編排是閘驗過的，人只改字"""
	with open(actions_path, encoding="utf-8") as f:
		doc = json.load(f)
	by_slide = {s["slide_id"]: s for s in doc["slides"]}
	for seg in segments:
		slide = by_slide.get(seg["slide_id"])
		if not slide:
			continue
		i = seg["idx"]
		if 0 <= i < len(slide["actions"]) and slide["actions"][i]["type"] == "speech":
			slide["actions"][i]["text"] = seg["text"]
	with open(actions_path, "w", encoding="utf-8") as f:
		json.dump(doc, f, ensure_ascii=False, indent="\t")


def revalidate(lesson_path, actions_path, sec):
	"""回傳 ERROR 訊息清單，通過時是空陣列。WARN 不擋"""
	args = [PY, VALIDATE, lesson_path, actions_path]
	if sec:
		args.append(str(sec))
	r = subprocess.run(args, capture_output=True, text=True)
	return [l[len("ERROR "):].strip()
		for l in r.stdout.splitlines() if l.startswith("ERROR ")]
