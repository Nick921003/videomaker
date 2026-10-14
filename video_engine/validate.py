#!/usr/bin/env python3
"""編排驗證閘：檢查 actions.json 是否能安全出片。

用法：python3 video_engine/validate.py <lesson.json> <actions.json> [目標秒數] [--audience beginner|general|advanced]
回傳碼 0 = 通過，1 = 有錯誤（ERROR）。WARN 不擋，只提醒。
"""
import argparse
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
MAINLAND_TERMS = {
	"大坑": "地雷／陷阱",
	"踩坑": "踩雷",
	"避坑": "避開陷阱",
	"走讀": "導讀／一行一行看",
	"代碼": "程式碼",
	"內存": "記憶體",
	"數組": "陣列",
	"指針": "指標",
	"字符串": "字串",
	"字符": "字元",
	"默認": "預設",
	"優化": "最佳化",
}
MAX_CAMERA = 2
BLOCKING = {"speech", "pause"}
# 節奏閘：一段語音配一個視覺重點。同時動太多處，觀眾來不及看，畫面就顯得吵
MAX_BEATS = 2          # 兩段語音之間的強調動作，超過提醒
HARD_BEATS = 4         # 超過即為錯誤
MAX_REVEAL_BURST = 5   # 一次連續帶出的 hidden 元素上限（錯開後仍看得清的數量）

# 依觀眾程度調整的編輯提醒；不是版面容量或 TTS 速度的硬上限。
PACING_PROFILES = {
	"beginner": {"display_chars": 115, "speech_chars": 60},
	"general": {"display_chars": 140, "speech_chars": 70},
	"advanced": {"display_chars": 180, "speech_chars": 90},
}
LINE_RE = re.compile(r"第\s*(\d+|[一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九])\s*行")
CHINESE_DIGITS = {c: i for i, c in enumerate("一二三四五六七八九", 1)}

MIN_ACTIONS = 3
MIN_SPEECH = 2
MIN_CODE_FOCUS = 4


def display_text(element):
	"""圖內標籤也是觀眾同時要讀的字；程式碼另由走讀動作承擔。"""
	if element["type"] == "code":
		return ""
	parts = [element.get("text", ""), element.get("caption", "")]
	parts.extend(element.get("items", []))
	for side in ("left", "right"):
		block = element.get(side, {})
		parts.append(block.get("title", ""))
		parts.extend(block.get("items", []))
	return "".join(parts)


def load_lesson(path):
	"""建索引：元素 id、程式碼行數、hidden 元素與畫面字量。"""
	with open(path, encoding="utf-8") as f:
		doc = json.load(f)
	slides = {}
	for s in doc["slides"]:
		ids, code_len, hidden, parts = set(), {}, set(), {}
		display_chars = 0
		for e in s["elements"]:
			ids.add(e["id"])
			display_chars += len(display_text(e))
			if e["type"] == "code":
				code_len[e["id"]] = len(e["lines"])
			if e["type"] == "figure":
				n = len(e.get("items", [])) or max(
					len(e.get("left", {}).get("items", [])), len(e.get("right", {}).get("items", [])))
				parts.setdefault(e["id"], n)
			if e.get("hidden"):
				hidden.add(e["id"])
		slides[s["id"]] = {"ids": ids, "code_len": code_len, "hidden": hidden,
			"parts": parts, "display_chars": display_chars}
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


def line_number(raw):
	if raw.isdigit():
		return int(raw)
	if "十" in raw:
		left, right = raw.split("十", 1)
		return (CHINESE_DIGITS[left] if left else 1) * 10 + (CHINESE_DIGITS[right] if right else 0)
	return CHINESE_DIGITS[raw]


def spoken_lines(text):
	"""只擷取明說的行號；不推測講稿語意。"""
	matches = list(LINE_RE.finditer(text))
	lines = set()
	for i, match in enumerate(matches):
		n = line_number(match.group(1))
		if i and re.fullmatch(r"\s*(?:到|至|～|~|－|-)\s*", text[matches[i - 1].end():match.start()]):
			prev = line_number(matches[i - 1].group(1))
			lines.update(range(min(prev, n), max(prev, n) + 1))
		else:
			lines.add(n)
	return lines


def code_target_lines(ref, idx):
	m = REF_RE.match(ref or "")
	if not m or m.group(1) not in idx["code_len"] or m.group(2) is None:
		return set()
	lo = int(m.group(2))
	hi = int(m.group(3)) if m.group(3) else lo
	return set(range(lo, hi + 1))


def check_slide(slide, idx, audience_level="general"):
	if audience_level not in PACING_PROFILES:
		raise ValueError(f"未知觀眾程度：{audience_level}")
	profile = PACING_PROFILES[audience_level]
	errs, warns = [], []
	acts = slide["actions"]
	sid = slide["slide_id"]
	if idx.get("display_chars", 0) > profile["display_chars"]:
		warns.append(f"畫面文字 {idx['display_chars']} 字，{audience_level} 建議約 {profile['display_chars']} 字內；請檢查是否能分頁或逐步揭露")

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
			elif a["type"] in ("spotlight", "laser", "camera") and not a.get("reset"):
				if base in idx["hidden"] and base not in revealed:
					errs.append(f"{a['type']} 指向尚未 reveal 的 hidden 元素：{ref}")
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

	beats, burst = 0, 0
	for a in acts:
		if a["type"] in BLOCKING:
			beats, burst = 0, 0
			continue
		if a["type"] == "reveal":
			burst += 1
			if burst == MAX_REVEAL_BURST + 1:
				warns.append(f"一口氣 reveal 超過 {MAX_REVEAL_BURST} 個元素，畫面會整塊蹦出來")
			continue
		burst = 0
		beats += 1
		if beats == HARD_BEATS + 1:
			errs.append(f"兩段語音之間有 {beats} 個強調動作，畫面同時在動太多處")
		elif beats == MAX_BEATS + 1:
			warns.append(f"兩段語音之間有 {beats} 個強調動作，建議一段語音配一個視覺重點")

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
		if len(t) > profile["speech_chars"]:
			warns.append(f"單段講稿 {len(t)} 字偏長（{audience_level} 建議約 {profile['speech_chars']} 字內），建議拆開並插入視覺動作")
		for term, repl in MAINLAND_TERMS.items():
			if term in t:
				warns.append(f"講稿出現非台灣慣用語「{term}」，建議改成「{repl}」")

	beat_code, active_code = set(), set()
	for a in acts:
		kind = a["type"]
		if kind == "speech":
			spoken = spoken_lines(a["text"])
			missing = spoken - (beat_code | active_code)
			if spoken and (beat_code or active_code) and missing:
				warns.append(f"口播行號 {sorted(missing)} 沒有對應程式碼聚焦；請核對此段語音與目標行")
			beat_code = set()
		elif kind == "spotlight":
			active_code = code_target_lines(a.get("target"), idx)
			beat_code.update(active_code)
		elif kind in ("laser", "camera") and not a.get("reset"):
			beat_code.update(code_target_lines(a.get("target"), idx))
		elif kind == "pause":
			beat_code = set()

	return [f"[{sid}] {e}" for e in errs], [f"[{sid}] {w}" for w in warns]


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("lesson", help="lesson.json")
	parser.add_argument("actions", help="actions.json")
	parser.add_argument("target", nargs="?", type=float, help="目標秒數")
	parser.add_argument("--audience", choices=PACING_PROFILES, default="general",
		help="觀眾程度，預設 general")
	args = parser.parse_args()
	target = args.target
	slides = load_lesson(args.lesson)
	with open(args.actions, encoding="utf-8") as f:
		doc = json.load(f)

	errors, warnings, total, chars = [], [], 0, 0
	for slide in doc["slides"]:
		sid = slide["slide_id"]
		if sid not in slides:
			errors.append(f"[{sid}] actions 指向不存在的投影片")
			continue
		e, w = check_slide(slide, slides[sid], audience_level=args.audience)
		errors += e
		warnings += w
		total += len(slide["actions"])
		chars += sum(len(a["text"]) for a in slide["actions"] if a["type"] == "speech")

	covered = {s["slide_id"] for s in doc["slides"]}
	for sid in slides:
		if sid not in covered:
			errors.append(f"[{sid}] 這一頁沒有任何動作")

	est = chars / CHARS_PER_SEC
	print(f"觀眾程度 {args.audience}；投影片 {len(slides)} 頁，動作 {total} 個，平均每頁 {total / max(len(slides), 1):.1f} 個")
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
