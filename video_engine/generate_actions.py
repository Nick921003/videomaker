#!/usr/bin/env python3
"""階段 4：lesson.json → actions.json（動作編排）。

用法：.venv/bin/python video_engine/generate_actions.py <lesson.json> [輸出路徑]

一頁一次呼叫，產完立刻跑驗證閘；不合格就把錯誤訊息回饋給模型重試，最多三次。
換模型只要改 VIDEO_ENGINE_LLM，見 llm.py。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm
from validate import check_slide, load_lesson

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_TRIES = 3
CHARS_PER_SEC = 5.5   # 含換氣與段間停頓的實測值
DIGEST_SLIDES = 3   # 帶前幾頁講稿給模型，避免重複開場與重複定義

# 給供應商的結構化輸出 schema 刻意放寬：只保證外框與欄位型別，
# 逐型別的細規則（哪個動作要哪些欄位）交給 validate.py，錯了才有具體訊息可回饋
ACTION_SCHEMA = {
	"type": "object",
	"properties": {
		"actions": {
			"type": "array",
			"items": {
				"type": "object",
				"properties": {
					"type": {"enum": ["speech", "spotlight", "laser", "reveal", "camera", "pause"]},
					"text": {"type": "string"},
					"target": {"type": "string"},
					"ms": {"type": "integer"},
					"scale": {"type": "number"},
					"reset": {"type": "boolean"},
				},
				"required": ["type"],
				"additionalProperties": False,
			},
		}
	},
	"required": ["actions"],
	"additionalProperties": False,
}


def normalize(data):
	"""各家回傳形狀不同：prompt 要裸陣列，有結構化輸出的會包成物件，
	包的鍵名也不保證叫 actions。一律挖出那個陣列。"""
	if isinstance(data, list):
		return data
	if isinstance(data, dict):
		if isinstance(data.get("actions"), list):
			return data["actions"]
		for v in data.values():
			if isinstance(v, list) and all(isinstance(x, dict) and "type" in x for x in v):
				return v
		if "type" in data:      # 只回了單一動作
			return [data]
	return []


def elements_table(slide):
	"""給模型看的元素清單。程式碼列出行號，讓它能指定行範圍"""
	rows = []
	for el in slide["elements"]:
		hid = "（進場時隱藏，必須 reveal）" if el.get("hidden") else ""
		if el["type"] == "figure":
			kind = el["kind"]
			rows.append(f"- `{el['id']}`　示意圖（{kind}）{'　' + el['caption'] if el.get('caption') else ''}")
			if kind in ("boxes", "steps"):
				for i, it in enumerate(el.get("items", []), start=1):
					rows.append(f"    `{el['id']}:i{i}`　{it}")
			else:
				for side, tag in (("left", "l"), ("right", "r")):
					blk = el.get(side, {})
					rows.append(f"    {blk.get('title', '')}：")
					for i, it in enumerate(blk.get("items", []), start=1):
						rows.append(f"      `{el['id']}:{tag}{i}`　{it}")
			continue
		if el["type"] == "code":
			rows.append(f"- `{el['id']}`　程式碼（{el['lang']}，共 {len(el['lines'])} 行）")
			for i, line in enumerate(el["lines"], start=1):
				rows.append(f"    L{i}: {line}" if line else f"    L{i}:")
		else:
			rows.append(f"- `{el['id']}`　{el['type']}：{el['text']}　{hid}")
	return "\n".join(rows)


def build_prompts(lesson, slide, index, digest, budget=None):
	system = open(os.path.join(HERE, "prompts/slide_actions.system.md"), encoding="utf-8").read()
	user = open(os.path.join(HERE, "prompts/slide_actions.user.md"), encoding="utf-8").read()
	outline = "\n".join(
		f"{i}. {s['id']}（{s.get('role', '—')}）：" +
		next((e["text"] for e in s["elements"] if e["type"] == "title"), "")
		for i, s in enumerate(lesson["slides"], start=1)
	)
	user = (user
		.replace("{{lesson_title}}", lesson["title"])
		.replace("{{slide_index}}", str(index))
		.replace("{{slide_total}}", str(len(lesson["slides"])))
		.replace("{{slide_role}}", slide.get("role", "—"))
		.replace("{{outline}}", outline)
		.replace("{{elements_table}}", elements_table(slide))
		.replace("{{previous_speech_digest}}", digest or "（這是第一頁）")
		.replace("{{char_budget}}", f"{budget} 字（硬上限，超過即不合格）" if budget else "沒有特別限制，但別讓單頁拖太長")
		.replace("{{slide_note}}", slide.get("note", "（無）")))
	return system, user


def generate_slide(lesson, slide, index, digest, idx_for_check, budget=None):
	"""產一頁的動作，不合格就帶著錯誤訊息重試"""
	system, user = build_prompts(lesson, slide, index, digest, budget)
	feedback = ""
	for attempt in range(1, MAX_TRIES + 1):
		data, meta = llm.complete_json(system, user + feedback, ACTION_SCHEMA, stage="actions")
		actions = normalize(data)
		errs, warns = check_slide({"slide_id": slide["id"], "actions": actions}, idx_for_check)
		chars = sum(len(a["text"]) for a in actions if a["type"] == "speech")
		if budget and chars > budget * 1.15:
			errs.append(f"講稿 {chars} 字，超過本頁上限 {budget} 字，請刪減")
		print(f"    第 {attempt} 次：{len(actions)} 個動作　"
			f"in {meta['in']}／out {meta['out']} tokens")
		for w in warns:
			print(f"      WARN  {w}")
		if not errs:
			return actions, meta
		for e in errs:
			print(f"      ERROR {e}")
		feedback = ("\n\n---\n\n上一次的輸出沒有通過驗證，請修正以下問題後重新輸出完整的動作陣列：\n"
			+ "\n".join(f"- {e}" for e in errs))
	raise SystemExit(f"{slide['id']} 重試 {MAX_TRIES} 次仍不合格，請看上面的錯誤訊息")


def main():
	if len(sys.argv) < 2:
		print(__doc__)
		return 2
	lesson_path = sys.argv[1]
	lesson = json.load(open(lesson_path, encoding="utf-8"))
	out_path = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else lesson_path.replace(".lesson.json", ".actions.json")
	index = load_lesson(lesson_path)
	target_sec = None
	for i, a in enumerate(sys.argv):
		if a == "--sec" and i + 1 < len(sys.argv):
			target_sec = float(sys.argv[i + 1])
	budget = int(target_sec * CHARS_PER_SEC / len(lesson["slides"])) if target_sec else None

	provider, model = llm.target("actions")
	print(f"用 {provider}:{model} 編排 {len(lesson['slides'])} 頁"
		+ (f"，目標 {target_sec:.0f} 秒（每頁 {budget} 字）\n" if budget else "\n"))

	slides, digest_pool, total_in, total_out = [], [], 0, 0
	for i, slide in enumerate(lesson["slides"], start=1):
		print(f"[{i}/{len(lesson['slides'])}] {slide['id']}")
		digest = "\n".join(digest_pool[-DIGEST_SLIDES * 4:])
		actions, meta = generate_slide(lesson, slide, i, digest, index[slide["id"]], budget)
		slides.append({"slide_id": slide["id"], "actions": actions})
		digest_pool += [a["text"] for a in actions if a["type"] == "speech"]
		total_in += meta["in"]
		total_out += meta["out"]

	doc = {"lesson_id": lesson["lesson_id"], "slides": slides}
	json.dump(doc, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent="\t")

	n_act = sum(len(s["actions"]) for s in slides)
	n_sp = sum(1 for s in slides for a in s["actions"] if a["type"] == "speech")
	chars = sum(len(a["text"]) for s in slides for a in s["actions"] if a["type"] == "speech")
	print(f"\n{n_act} 個動作、{n_sp} 段講稿、{chars} 字，估算片長 {chars / 5.5:.0f} 秒")
	print(f"token 用量：in {total_in}／out {total_out}")
	print(f"輸出：{out_path}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
