#!/usr/bin/env python3
"""編排驗證閘：檢查 actions.json 是否能安全出片。

用法：python3 video_engine/validate.py <lesson.json> <actions.json> [目標秒數]
回傳碼 0 = 通過，1 = 有錯誤（ERROR）。WARN 不擋，只提醒。
"""
import json
import re
import sys

REF_RE = re.compile(r"^([a-z0-9_]+)(?::(?:L(\d+)(?:-L(\d+))?|[a-z]+\d*))?$")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
CAPS_RE = re.compile(r"\b[A-Z]{2,}\b")
GLUE_RE = re.compile(r"[一-鿿][A-Za-z]|[A-Za-z][一-鿿]")

# 刻意要逐字母唸的縮寫，不列為警告
SPELL_OUT = {"AI", "API", "AST", "DKT", "GPU", "CPU", "IDE", "UI", "TTS", "LLM",
	"CNN", "RNN", "GRU", "NLP", "PDF", "HTML", "CSS", "SQL", "IO"}
CHARS_PER_SEC = 5.5   # 含換氣與段間停頓的實測值（525 字 → 95 秒）
# 這些直接唸出來 TTS 會出事，講稿要用口語說法
RAW_FUNCS = re.compile(r"\b(strcpy|strlen|strcmp|printf|scanf|malloc|free|sizeof|fopen|fclose)\b", re.I)
MAX_CAMERA = 2

MIN_ACTIONS = 3
MIN_SPEECH = 2
MIN_CODE_FOCUS = 4


def load_lesson(path):
	"""建索引：元素 id、程式碼行數、hidden 元素"""
	doc = json.load(open(path, encoding="utf-8"))
	slides = {}
	for s in doc["slides"]:
		ids, code_len, hidden, parts = set(), {}, set(), {}
		for e in s["elements"]:
			ids.add(e["id"])
			if e["type"] == "code":
				code_len[e["id"]] = len(e["lines"])
			if e["type"] == "figure":
				n = len(e.get("items", [])) or max(
					len(e.get("left", {}).get("items", [])), len(e.get("right", {}).get("items", [])))
				parts.setdefault(e["id"], n)
			if e.get("hidden"):
				hidden.add(e["id"])
		slides[s["id"]] = {"ids": ids, "code_len": code_len, "hidden": hidden, "parts": parts}
	return slides


def check_ref(ref, idx):
	m = REF_RE.match(ref)
	if not m:
		return None, f"target 格式錯誤：{ref}"
	base, a, b = m.group(1), m.group(2), m.group(3)
	if base not in idx["ids"]:
		return None, f"target 指向不存在的元素：{ref}"
	if ":" in ref and a is None:
		if base not in idx.get("parts", {}):
			return None, f"只有 figure 才有部件引用：{ref}"
		return base, None
	if a is not None:
		if base not in idx["code_len"]:
			return None, f"對非程式碼元素使用行號：{ref}"
		hi = int(b) if b else int(a)
		if int(a) < 1 or hi > idx["code_len"][base] or hi < int(a):
			return None, f"行號越界或反向：{ref}（該元素共 {idx['code_len'][base]} 行）"
	return base, None


def check_slide(slide, idx):
	errs, warns = [], []
	acts = slide["actions"]
	sid = slide["slide_id"]

	if len(acts) < MIN_ACTIONS:
		errs.append(f"動作只有 {len(acts)} 個，少於 {MIN_ACTIONS} —— 這會變成 PPT 換頁")
	speeches = [a for a in acts if a["type"] == "speech"]
	if len(speeches) < MIN_SPEECH:
		errs.append(f"speech 只有 {len(speeches)} 段，少於 {MIN_SPEECH}")
	if acts and acts[-1]["type"] != "speech":
		errs.append(f"最後一個動作是 {acts[-1]['type']}，必須是 speech")

	revealed, focused_code, cam_zoomed = set(), 0, False
	for a in acts:
		ref = a.get("target")
		if ref:
			base, err = check_ref(ref, idx)
			if err:
				errs.append(err)
				continue
			if a["type"] == "reveal":
				revealed.add(base)
			if a["type"] in ("spotlight", "laser") and base in idx["code_len"]:
				focused_code += 1
		if a["type"] == "camera":
			if a.get("reset"):
				cam_zoomed = False
			elif a.get("scale", 1.35) > 1:
				cam_zoomed = True
				if not a.get("target"):
					errs.append("camera 推近但沒有 target")

	missing = idx["hidden"] - revealed
	if missing:
		errs.append(f"hidden 元素沒有 reveal，永遠不會出現：{sorted(missing)}")
	if cam_zoomed:
		errs.append("鏡頭推近後沒有 reset，會帶進下一頁")
	if idx["code_len"] and focused_code < MIN_CODE_FOCUS:
		errs.append(f"程式碼頁只有 {focused_code} 個聚焦動作，少於 {MIN_CODE_FOCUS}，走讀不完整")
	if idx["code_len"] and not any(a["type"] == "camera" for a in acts):
		errs.append("程式碼頁沒有鏡頭推近，字太小看不清楚")

	cams = sum(1 for a in acts if a["type"] == "camera" and not a.get("reset"))
	if cams > MAX_CAMERA:
		errs.append(f"鏡頭推近 {cams} 次，超過每頁上限 {MAX_CAMERA}，畫面會一直在動")

	for a in speeches:
		t = a["text"]
		for w in set(RAW_FUNCS.findall(t)):
			errs.append(f"講稿直接唸函式名「{w}」，要改成口語說法（例如 strcpy 講成「字串複製」）")
		if EMOJI_RE.search(t):
			errs.append(f"講稿含 Emoji：{t[:20]}…")
		for w in CAPS_RE.findall(t):
			if w in SPELL_OUT:
				continue
			warns.append(f"「{w}」全大寫，會被逐字母唸。要當單字唸請改成非全大寫")
		for g in GLUE_RE.findall(t):
			warns.append(f"中英黏在一起「{g}」，建議加半形空格")
		if len(t) > 70:
			warns.append(f"單段講稿 {len(t)} 字偏長，建議拆開並插入視覺動作")

	return [f"[{sid}] {e}" for e in errs], [f"[{sid}] {w}" for w in warns]


def main():
	if len(sys.argv) < 3:
		print(__doc__)
		return 2
	target = float(sys.argv[3]) if len(sys.argv) > 3 else None
	slides = load_lesson(sys.argv[1])
	doc = json.load(open(sys.argv[2], encoding="utf-8"))

	errors, warnings, total, chars = [], [], 0, 0
	for slide in doc["slides"]:
		sid = slide["slide_id"]
		if sid not in slides:
			errors.append(f"[{sid}] actions 指向不存在的投影片")
			continue
		e, w = check_slide(slide, slides[sid])
		errors += e
		warnings += w
		total += len(slide["actions"])
		chars += sum(len(a["text"]) for a in slide["actions"] if a["type"] == "speech")

	covered = {s["slide_id"] for s in doc["slides"]}
	for sid in slides:
		if sid not in covered:
			errors.append(f"[{sid}] 這一頁沒有任何動作")

	est = chars / CHARS_PER_SEC
	print(f"投影片 {len(slides)} 頁，動作 {total} 個，平均每頁 {total / max(len(slides), 1):.1f} 個")
	print(f"講稿 {chars} 字，估算片長 {est:.0f} 秒")
	if target and est > target:
		warnings.append(f"[全片] 估算 {est:.0f} 秒，超過目標 {target} 秒，需刪減講稿約 {int((est - target) * CHARS_PER_SEC)} 字")
	for w in warnings:
		print(f"WARN  {w}")
	for e in errors:
		print(f"ERROR {e}")
	print("通過" if not errors else f"未通過（{len(errors)} 個錯誤）")
	return 1 if errors else 0


if __name__ == "__main__":
	sys.exit(main())
