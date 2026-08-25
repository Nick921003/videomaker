#!/usr/bin/env python3
"""階段 2：教材 → lesson.json（投影片結構化）。

用法：.venv/bin/python video_engine/generate_lesson.py <教材.md> [輸出路徑]

輸出會先自我檢查（id 規則、頁面角色、hidden 比例、程式碼行數），不合格就把錯誤
回饋給模型重試。換模型只要改 VIDEO_ENGINE_LLM，見 llm.py。
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_TRIES = 3
ID_RE = re.compile(r"^[a-z0-9_]+$")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
ROLES = {"hook", "concept", "walkthrough", "pitfall", "summary"}

LESSON_SCHEMA = {
	"type": "object",
	"properties": {
		"lesson_id": {"type": "string"},
		"title": {"type": "string"},
		"slides": {
			"type": "array",
			"items": {
				"type": "object",
				"properties": {
					"id": {"type": "string"},
					"role": {"enum": sorted(ROLES)},
					"note": {"type": "string"},
					"elements": {
						"type": "array",
						"items": {
							"type": "object",
							"properties": {
								"id": {"type": "string"},
								"type": {"enum": ["title", "subtitle", "bullet", "callout", "code", "figure"]},
								"text": {"type": "string"},
								"hidden": {"type": "boolean"},
								"lang": {"type": "string"},
								"lines": {"type": "array", "items": {"type": "string"}},
								"kind": {"enum": ["boxes", "compare", "steps"]},
								"caption": {"type": "string"},
								"items": {"type": "array", "items": {"type": "string"}},
								"left": {"type": "object", "additionalProperties": False, "properties": {
									"title": {"type": "string"},
									"items": {"type": "array", "items": {"type": "string"}}}},
								"right": {"type": "object", "additionalProperties": False, "properties": {
									"title": {"type": "string"},
									"items": {"type": "array", "items": {"type": "string"}}}},
							},
							"required": ["id", "type"],
							"additionalProperties": False,
						},
					},
				},
				"required": ["id", "role", "elements"],
				"additionalProperties": False,
			},
		},
	},
	"required": ["lesson_id", "title", "slides"],
	"additionalProperties": False,
}


def check(lesson):
	"""結構自檢。回傳錯誤清單，空的代表可以進下一步"""
	errs = []
	if not ID_RE.match(lesson.get("lesson_id", "")):
		errs.append("lesson_id 只能用小寫英數與底線")
	slides = lesson.get("slides", [])
	if not 3 <= len(slides) <= 6:
		errs.append(f"共 {len(slides)} 頁，應為 3–6 頁")

	seen = set()
	for s in slides:
		sid = s.get("id", "")
		if not ID_RE.match(sid):
			errs.append(f"頁面 id {sid!r} 只能用小寫英數與底線")
		if s.get("role") not in ROLES:
			errs.append(f"[{sid}] role {s.get('role')!r} 不在允許清單")

		types = [e["type"] for e in s.get("elements", [])]
		if types.count("title") != 1:
			errs.append(f"[{sid}] 必須剛好一個 title")
		has_code = "code" in types
		has_fig = "figure" in types
		if not has_code and not has_fig:
			errs.append(f"[{sid}] 沒有程式碼就必須放一個 figure，純文字頁面太空")
		for fig in [e for e in s["elements"] if e["type"] == "figure"]:
			if fig.get("kind") in ("boxes", "steps"):
				n = len(fig.get("items", []))
				if not 2 <= n <= 5:
					errs.append(f"[{sid}] {fig['id']} 有 {n} 個項目，應為 2–5 個")
				for it in fig.get("items", []):
					if len(it) > 16:
						errs.append(f"[{sid}] {fig['id']} 的「{it}」超過 16 字，方塊放不下")
			elif fig.get("kind") == "compare":
				for side in ("left", "right"):
					n = len(fig.get(side, {}).get("items", []))
					if not 2 <= n <= 4:
						errs.append(f"[{sid}] {fig['id']} 的 {side} 有 {n} 個項目，應為 2–4 個")
		bullets = [e for e in s["elements"] if e["type"] in ("bullet", "callout")]

		if has_code:
			code = next(e for e in s["elements"] if e["type"] == "code")
			n = len(code.get("lines", []))
			if not 4 <= n <= 24:
				errs.append(f"[{sid}] 程式碼 {n} 行，應為 4–24 行")
			if bullets:
				errs.append(f"[{sid}] 走讀頁不要同時放條列")
		elif has_fig and not 0 <= len(bullets) <= 3:
			errs.append(f"[{sid}] 有 figure 時條列最多 3 條，目前 {len(bullets)} 條")
		elif not has_fig and not 2 <= len(bullets) <= 4:
			errs.append(f"[{sid}] 有 {len(bullets)} 條條列，應為 2–4 條")
		elif bullets and sum(1 for b in bullets if b.get("hidden")) != len(bullets) - 1:
			errs.append(f"[{sid}] 除了第一條，其餘條列都要標 hidden")

		for e in s["elements"]:
			eid = e.get("id", "")
			if not ID_RE.match(eid):
				errs.append(f"[{sid}] 元素 id {eid!r} 只能用小寫英數與底線")
			if eid in seen:
				errs.append(f"元素 id {eid!r} 重複")
			seen.add(eid)
			text = e.get("text", "")
			if EMOJI_RE.search(text):
				errs.append(f"[{sid}] {eid} 含 Emoji")
			if e["type"] in ("bullet", "callout") and len(text) > 34:
				errs.append(f"[{sid}] {eid} 有 {len(text)} 字，畫面文字請縮到 28 字內")
			if e["type"] in ("bullet", "callout") and text[:1] in "•-*・":
				errs.append(f"[{sid}] {eid} 不要自己加項目符號")
	return errs


def main():
	if len(sys.argv) < 2:
		print(__doc__)
		return 2
	material_path = sys.argv[1]
	material = open(material_path, encoding="utf-8").read()
	stem = os.path.splitext(os.path.basename(material_path))[0]
	lesson_id = re.sub(r"[^a-z0-9_]", "_", stem.lower())
	out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
		HERE, "examples", f"{lesson_id}.lesson.json")

	system = open(os.path.join(HERE, "prompts/lesson_content.system.md"), encoding="utf-8").read()
	user_tpl = open(os.path.join(HERE, "prompts/lesson_content.user.md"), encoding="utf-8").read()
	user = user_tpl.replace("{{material}}", material).replace("{{lesson_id}}", lesson_id)

	provider, model = llm.target("lesson")
	print(f"用 {provider}:{model} 結構化 {len(material)} 字的教材")

	feedback = ""
	for attempt in range(1, MAX_TRIES + 1):
		lesson, meta = llm.complete_json(system, user + feedback, LESSON_SCHEMA, stage="lesson")
		errs = check(lesson)
		print(f"  第 {attempt} 次：{len(lesson.get('slides', []))} 頁　"
			f"in {meta['in']}／out {meta['out']} tokens")
		if not errs:
			break
		for e in errs:
			print(f"    ERROR {e}")
		feedback = ("\n\n---\n\n上一次的輸出沒通過檢查，修正以下問題後重新輸出完整 JSON：\n"
			+ "\n".join(f"- {e}" for e in errs))
	else:
		raise SystemExit(f"重試 {MAX_TRIES} 次仍不合格")

	lesson.setdefault("voice", {"model": "wang_teacher_v3", "speed_factor": 0.95,
		"text_lang": "zh", "text_split_method": "cut5"})
	json.dump(lesson, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")

	for s in lesson["slides"]:
		kinds = {}
		for e in s["elements"]:
			kinds[e["type"]] = kinds.get(e["type"], 0) + 1
		print(f"  {s['id']}（{s['role']}）　" + "　".join(f"{k}×{v}" for k, v in kinds.items()))
	print(f"輸出：{out_path}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
