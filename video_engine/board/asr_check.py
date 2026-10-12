#!/usr/bin/env python3
"""配音內容檢查：本機語音辨識 → 拼音 → 跟講稿逐音節比對，抓漏念與重複念。

用法（需 GPT-SoVITS venv：faster-whisper＋pypinyin，videomaker 不新增依賴）：
  ~/projects/GPT-SoVITS/.venv/bin/python video_engine/board/asr_check.py <jobs.json> <結果.json>

jobs.json：[{"wav": 路徑, "text": 送去合成的文字}]。比拼音而不比字，同音字誤辨（變數→電數）不算錯，
差很多的替換與不見的音節才算漏念。判定：連續漏 ≥ 2 個音節、或句尾音節不見、或漏念比例 > 25%。
"""
import json
import os
import re
import sys

MODEL = os.environ.get("ASR_MODEL", "large-v3")
DROP_RUN = 2
DROP_RATIO = 0.25
CHECK_VERSION = 2
REPEAT_MIN = 6


DIGITS = dict(zip("0123456789", "零一二三四五六七八九"))


def comparison_text(text):
	# 英文與識別字的數字不保證唸成中文；保留講稿已替換的符號唸法與中文。
	text = re.sub(r"[A-Za-z_][A-Za-z0-9_]*(?:[.+:/-][A-Za-z0-9_]+)*", "", text)
	return "".join(re.findall(r"[\u4e00-\u9fff]", "".join(DIGITS.get(c, c) for c in text)))


def syllables(text):
	"""每個中文音節拆成（聲母, 韻母）；英文與程式識別字不參與判定。"""
	from pypinyin import Style, pinyin
	han = comparison_text(text)
	ini = [p[0] for p in pinyin(han, style=Style.INITIALS, strict=True)]
	fin = [p[0] for p in pinyin(han, style=Style.FINALS, strict=True)]
	return list(zip(ini, fin))


def edit(a, b):
	d = list(range(len(b) + 1))
	for i, ca in enumerate(a, 1):
		prev, d[0] = d[0], i
		for j, cb in enumerate(b, 1):
			prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
	return d[-1]


def similar(x, y):
	"""辨識器聽成近音字不算漏念：韻母相同，或聲母相同且韻母只差一個音素。"""
	return x[1] == y[1] or (x[0] == y[0] and edit(x[1], y[1]) <= 1)


def align(ref, hyp):
	"""回傳 ref 每個音節的狀態：ok／sub（差很多的替換）／del（不見了）。"""
	n, m = len(ref), len(hyp)
	cost = lambda i, j: 0 if similar(ref[i], hyp[j]) else 1
	d = [[0] * (m + 1) for _ in range(n + 1)]
	for i in range(n + 1):
		d[i][0] = i
	for j in range(m + 1):
		d[0][j] = j
	for i in range(1, n + 1):
		for j in range(1, m + 1):
			d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost(i - 1, j - 1))
	state, i, j = ["ok"] * n, n, m
	while i > 0:
		if j > 0 and d[i][j] == d[i - 1][j - 1] + cost(i - 1, j - 1):
			state[i - 1] = "ok" if cost(i - 1, j - 1) == 0 else "sub"
			i, j = i - 1, j - 1
		elif d[i][j] == d[i - 1][j] + 1:
			state[i - 1] = "del"
			i -= 1
		else:
			j -= 1
	return state


def judge(text, heard):
	ref, hyp = syllables(text), syllables(heard)
	state = align(ref, hyp)
	miss = [s != "ok" for s in state]
	runs, run = [], 0
	for k, mk in enumerate(miss + [False]):
		if mk:
			run += 1
		elif run:
			runs.append((k - run, run))
			run = 0
	chars = comparison_text(text)
	missing = ["".join(chars[s:s + n]) for s, n in runs]
	problems = []
	if any(n >= DROP_RUN for _, n in runs):
		problems.append("連續漏念")
	# 句尾只認「不見了」：句尾被聽成別的字多半是收音含糊，不是沒唸
	if state and state[-1] == "del":
		problems.append("句尾漏念")
	if ref and sum(miss) / len(ref) > DROP_RATIO:
		problems.append("漏念比例過高")
	if repeated_speech(ref, hyp):
		problems.append("重複念")
	return {"ok": not problems, "problems": problems, "missing": missing, "heard": heard, "version": CHECK_VERSION}


def repeated_speech(ref, hyp):
	"""至少多出六音節，且原稿中的連續片語出現次數超出原稿；稿內刻意重複仍允許。"""
	if len(hyp) - len(ref) < REPEAT_MIN:
		return False
	def count(sequence, phrase):
		found, index = 0, 0
		while index <= len(sequence) - len(phrase):
			if sequence[index:index + len(phrase)] == phrase:
				found += 1
				index += len(phrase)
			else:
				index += 1
		return found
	for start in range(len(ref) - REPEAT_MIN + 1):
		phrase = ref[start:start + REPEAT_MIN]
		if count(hyp, phrase) > count(ref, phrase):
			return True
	return False


def main():
	jobs_path, out_path = sys.argv[1], sys.argv[2]
	with open(jobs_path, encoding="utf-8") as f:
		jobs = json.load(f)
	from faster_whisper import WhisperModel
	# CPU int8：GPU 留給 TTS 服務
	model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=8)
	results = []
	for job in jobs:
		segs, _ = model.transcribe(job["wav"], language="zh", beam_size=5, vad_filter=False,
			condition_on_previous_text=False, temperature=0)
		heard = "".join(s.text for s in segs)
		results.append({**job, **judge(job["text"], heard)})
	with open(out_path, "w", encoding="utf-8") as f:
		json.dump(results, f, ensure_ascii=False, indent="\t")


if __name__ == "__main__":
	main()
