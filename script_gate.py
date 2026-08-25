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
	"""回傳 ERROR 訊息清單，通過時是空陣列。WARN 不擋

	validate.py 若在印任何東西之前就崩掉（例如 lesson_path 打錯、
	load_lesson 丟例外），stdout 會是空的，一行 ERROR 都撿不到——
	若照舊回傳空陣列，呼叫端會把「驗證器沒跑起來」誤判成「驗證通過」，
	等於把這個模組存在的理由（擋住會搞壞 TTS 的講稿）靜默關掉。
	exit code 沒辦法拿來分辨：找到錯誤時 exit 1，未捕捉的例外也是 exit 1。
	改用輸出本身當存活信號——validate.py 只要真的跑到最後，不管通過
	或未通過都會印出含「通過」的結尾行，用它判斷驗證器是否跑完。
	"""
	args = [PY, VALIDATE, lesson_path, actions_path]
	if sec:
		args.append(str(sec))
	r = subprocess.run(args, capture_output=True, text=True)
	if "通過" not in r.stdout:
		stderr_tail = "\n".join(r.stderr.strip().splitlines()[-5:])
		raise RuntimeError(
			f"validate.py 沒有正常跑完就結束了（exit code {r.returncode}），"
			f"stdout 裡沒有「通過」字樣，可能是崩潰而不是驗證失敗。\n"
			f"stderr 最後幾行：\n{stderr_tail}"
		)
	return [l[len("ERROR "):].strip()
		for l in r.stdout.splitlines() if l.startswith("ERROR ")]
