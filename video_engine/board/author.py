#!/usr/bin/env python3
"""教材 md → 單元規劃 → 小節 scene.json（Opus 5.5），含預算上限與驗證閘修正迴圈。

用法：
  .venv/bin/python video_engine/board/author.py plan  <教材.md> <輸出目錄> [--budget-usd 2]
  .venv/bin/python video_engine/board/author.py scene <教材.md> <輸出目錄> <小節id> [--budget-usd 2]

輸出目錄：plan.json、<id>.scene.json、<id>.report.json、usage.jsonl（每次呼叫的 tokens 與估價）。
預算是整個輸出目錄累計的：每次呼叫前先用免費的 count_tokens 量輸入，加上輸出上限算最壞情況，超過就不呼叫。
"""
import argparse
import copy
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import compile as BC
from build import build

# 分工（使用者原始設計）：整理教材用便宜的長文模型，分鏡需要教學與畫面判斷，用強模型
DEFAULT_MODEL = {"plan": "google:gemini-3.8-flash", "scene": "anthropic:claude-opus-5-5"}
# USD／百萬 tokens（2026-10 牌價）；Anthropic 快取寫入以 5 分鐘快取計，Gemini 思考 tokens 以輸出計價
PRICE = {
	"claude-opus-5-5": {"in": 4.0, "out": 20.0, "cache_read": 0.20, "cache_write": 5.0},
	"claude-sonnet-5-5": {"in": 2.0, "out": 10.0, "cache_read": 0.20, "cache_write": 2.5},
	"gemini-3.8-flash": {"in": 0.75, "out": 3.75, "cache_read": 0.075, "cache_write": 0.75},
}
MAX_TOKENS = {"plan": 16000, "scene": 12000}
MAX_REPAIRS = 2
SAY_MAX = 40
ENGLISH_OK = {"Windows"}  # 與 narrate.py 一致：實測唸得清楚的英文字
CHARS_PER_SEC = 5.2
PLAYWRIGHT_PY = os.path.expanduser("~/.local/share/pipx/venvs/webwright/bin/python")
SPELLED = re.compile(r"(?<![A-Za-z])(?:[A-Za-z] ){1,}[A-Za-z](?![A-Za-z])|(?<![A-Za-z])[A-Z]{2,6}(?![A-Za-z])")


class BudgetExceeded(RuntimeError):
	pass


class Budget:
	def __init__(self, path, cap):
		self.path, self.cap = path, cap

	def spent(self):
		if not os.path.exists(self.path):
			return 0.0
		with open(self.path, encoding="utf-8") as f:
			return sum(json.loads(line)["usd"] for line in f if line.strip())

	def guard(self, model, input_tokens, max_tokens):
		p = PRICE[model]
		worst = (input_tokens * max(p["in"], p["cache_write"]) + max_tokens * p["out"]) / 1e6
		if self.spent() + worst > self.cap:
			raise BudgetExceeded(f"已花 US${self.spent():.3f}，本次最壞 US${worst:.3f}，會超過上限 US${self.cap:.2f}")

	def record(self, stage, model, usage):
		p = PRICE[model]
		usd = (usage["in"] * p["in"] + usage["out"] * p["out"] + usage["cache_read"] * p["cache_read"]
			+ usage["cache_write"] * p["cache_write"]) / 1e6
		with open(self.path, "a", encoding="utf-8") as f:
			f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": stage, "model": model, **usage, "usd": round(usd, 5)}) + "\n")
		return usd


def first_json(text):
	start = text.find("{")
	while start >= 0:
		depth = 0
		for i in range(start, len(text)):
			depth += {"{": 1, "}": -1}.get(text[i], 0)
			if depth == 0:
				try:
					return json.loads(text[start:i + 1])
				except json.JSONDecodeError:
					break
		start = text.find("{", start + 1)
	raise ValueError(f"回應裡找不到 JSON：{text[:200]}")


def call_anthropic(budget, stage, model, system, messages, light=False):
	import anthropic
	client = anthropic.Anthropic()
	sys_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
	# 第一則（教材）也進快取：重寫時同樣的前綴只收快取讀取價
	messages = [{"role": m["role"], "content": [{"type": "text", "text": m["content"], **({"cache_control": {"type": "ephemeral"}} if i == 0 else {})}]}
		for i, m in enumerate(messages)]
	count = client.messages.count_tokens(model=model, system=sys_blocks, messages=messages, thinking={"type": "adaptive"})
	budget.guard(model, count.input_tokens, MAX_TOKENS[stage])
	resp = client.messages.create(model=model, max_tokens=MAX_TOKENS[stage], system=sys_blocks, messages=messages,
		thinking={"type": "adaptive"}, output_config={"effort": "low" if light else "medium"})
	u = resp.usage
	usage = {"in": u.input_tokens, "out": u.output_tokens, "cache_read": u.cache_read_input_tokens or 0,
		"cache_write": u.cache_creation_input_tokens or 0}
	text = next((b.text for b in resp.content if b.type == "text"), "")
	return text, usage, resp.stop_reason == "max_tokens"


def call_google(budget, stage, model, system, messages, light=False):
	from google import genai
	from google.genai import types
	client = genai.Client()
	contents = [types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part(text=m["content"])]) for m in messages]
	count = client.models.count_tokens(model=model, contents=[types.Content(role="user", parts=[types.Part(text=system)])] + contents)
	budget.guard(model, count.total_tokens, MAX_TOKENS[stage])
	resp = client.models.generate_content(model=model, contents=contents, config=types.GenerateContentConfig(
		system_instruction=system, max_output_tokens=MAX_TOKENS[stage], response_mime_type="application/json"))
	u = resp.usage_metadata
	cached = u.cached_content_token_count or 0
	usage = {"in": (u.prompt_token_count or 0) - cached, "out": (u.candidates_token_count or 0) + (u.thoughts_token_count or 0),
		"cache_read": cached, "cache_write": 0}
	finish = resp.candidates[0].finish_reason if resp.candidates else None
	return resp.text or "", usage, str(finish).endswith("MAX_TOKENS")


def call(budget, stage, system, messages, target, light=False):
	provider, model = target.split(":", 1)
	text, usage, truncated = (call_google if provider == "google" else call_anthropic)(budget, stage, model, system, messages, light)
	usd = budget.record(stage, model, usage)
	print(f"  {stage}［{model}］：輸入 {usage['in']}＋快取讀 {usage['cache_read']}＋快取寫 {usage['cache_write']}，輸出 {usage['out']}，US${usd:.4f}（累計 US${budget.spent():.4f}）", flush=True)
	if truncated:
		raise RuntimeError(f"{stage} 輸出達到上限 {MAX_TOKENS[stage]}")
	return text


PATCH_ASK = ("驗證閘回報的問題只出在場景 {ids}。只輸出要改的部分，格式："
	'{{"scenes": [修正後的完整場景], "objects": [新增或修改的物件]}}；沒改的場景與物件不要輸出。'
	"一場太擠可以拆成兩場：新場景給新的 id，放在原場景後面一起輸出。問題：")
FULL_ASK = "驗證閘回報以下問題，只修這些，其餘維持不變，輸出完整修正後的 JSON："


def problem_scenes(doc, problems):
	"""每個問題對到哪些場景（訊息裡的「場景 id」或該場的旁白原句）；有一個對不到就回 None，改回整份重寫。"""
	ids = set()
	for p in problems:
		# 「場景 id」（量測閘）、「id/beatN」（編譯錯誤與缺口）、或該場的旁白原句
		hit = {s["id"] for s in doc.get("scenes", [])
			if f"場景 {s['id']} " in p or f"{s['id']}/beat" in p or any(b.get("say") and b["say"] in p for b in s.get("beats", []))}
		if not hit:
			return None
		ids |= hit
	return ids


def merge_patch(doc, patch):
	"""把只含修正場景／物件的片段併回原分鏡；場景照 id 換掉，物件照 id 換掉或新增。"""
	if not isinstance(patch, dict) or not isinstance(patch.get("scenes", []), list) or not isinstance(patch.get("objects", []), list):
		raise ValueError("修正片段格式不對：要 {\"scenes\": [...], \"objects\": [...]}")
	out = copy.deepcopy(doc)
	cursor = None
	for s in patch.get("scenes", []):
		if not isinstance(s, dict) or not isinstance(s.get("id"), str):
			raise ValueError("修正片段的場景缺 id")
		ids = [x["id"] for x in out["scenes"]]
		if s["id"] in ids:
			cursor = ids.index(s["id"])
			out["scenes"][cursor] = s
		else:
			# 新場景（例：太擠被要求拆成兩場）：接在前一個修正的場景後面，沒有就接在最後
			cursor = len(out["scenes"]) if cursor is None else cursor + 1
			out["scenes"].insert(cursor, s)
	objs = {o["id"]: i for i, o in enumerate(out["objects"])}
	for o in patch.get("objects", []):
		if not isinstance(o, dict) or "id" not in o:
			raise ValueError("修正片段的物件缺 id")
		if o["id"] in objs:
			out["objects"][objs[o["id"]]] = o
		else:
			out["objects"].append(o)
	return out


def converse(budget, stage, system, user, validate, failed_path=None, target=None, repair_target=None, scenes_of=None, start=None):
	"""呼叫 → 驗證 → 有問題就修，最多 MAX_REPAIRS 次。

	問題都對得到場景時只重寫那幾場（scenes_of），其餘照舊；repair_target 可指定較便宜的模型負責重寫。
	start＝已有的草稿（例如上次失敗存下來的），直接從修正開始，不重寫第一版。
	"""
	target = target or DEFAULT_MODEL[stage]
	repair_target = repair_target or target
	messages = [{"role": "user", "content": user}]
	data, partial, problems = None, False, []
	if start is not None:
		data = start
		problems = validate(data)
		if not problems:
			return data, 0
	for attempt in range(MAX_REPAIRS + 1):
		if data is not None and problems:
			print(f"  第 {attempt} 次未過驗證閘：", *problems[:8], sep="\n    ", flush=True)
			ids = scenes_of(data, problems) if scenes_of else None
			partial = bool(ids)
			ask = (PATCH_ASK.format(ids="、".join(sorted(ids))) if partial else FULL_ASK) + "\n- " + "\n- ".join(problems[:20])
			# 只帶教材＋目前的分鏡＋問題；不帶前幾輪的對話，輸入才不會越修越長
			messages = [messages[0], {"role": "assistant", "content": json.dumps(data, ensure_ascii=False)}, {"role": "user", "content": ask}]
		elif attempt and data is None:
			messages = messages + [{"role": "user", "content": FULL_ASK + "\n- " + "\n- ".join(problems[:20])}]
		repairing = attempt > 0 or start is not None
		text = call(budget, stage, system, messages, repair_target if repairing else target, light=repairing)
		try:
			got = first_json(text)
			data = merge_patch(data, got) if partial else got
			problems = validate(data)
		except ValueError as e:
			problems = [str(e)]
			if data is None:
				messages = messages + [{"role": "assistant", "content": text}]
		if not problems:
			return data, attempt + (1 if start is not None else 0)
	print(f"  最後一次未過驗證閘：", *problems[:8], sep="\n    ", flush=True)
	if data is not None and failed_path:
		with open(failed_path, "w", encoding="utf-8") as f:
			json.dump({"problems": problems, "last": data}, f, ensure_ascii=False, indent="\t")
	raise RuntimeError(f"{stage} 修正 {MAX_REPAIRS} 次仍未通過：{problems[:5]}")


# ── 教材解析（確定性，不靠模型） ──

def clean_title(t):
	return re.sub(r"[*`]", "", t).strip()


def headings(md):
	# 教材的補充段落常包在引用區塊裡（> #### macOS），標題前的 > 也要認得
	return [(len(m.group(1)), clean_title(m.group(2)), m.start()) for m in re.finditer(r"^(?:>\s*)?(#{1,6})\s+(.+?)\s*$", md, re.M)]


def objectives_of(md):
	"""「學習目標」標題下的編號清單。"""
	hs = headings(md)
	for k, (level, title, pos) in enumerate(hs):
		if "學習目標" in title:
			end = hs[k + 1][2] if k + 1 < len(hs) else len(md)
			return [re.sub(r"[*`]", "", m.group(1)).strip() for m in re.finditer(r"^\s*\d+\.\s+(.+)$", md[pos:end], re.M)]
	return []


def section(md, title):
	hs = headings(md)
	for k, (level, t, pos) in enumerate(hs):
		if t == title:
			end = next((p for lv, _, p in hs[k + 1:] if lv <= level), len(md))
			return md[pos:end].strip()
	return None


def spelled(text):
	return SPELLED.findall(text)


# ── 規劃 ──

MAX_STORIES = 10


def stories_of(plan):
	return plan.get("stories") or plan.get("segments") or []


def glossary_problems(plan):
	"""不同用語唸成同一個詞，旁白就分不出在講哪個（例：GCC 與 cc1 都唸「編譯器」）。"""
	by_say = {}
	for g in plan.get("glossary", []):
		by_say.setdefault(g.get("say_as"), []).append(g.get("term"))
	return [f"glossary 的 {terms} 都唸成同一個「{say}」，請改成不同說法（同一個東西就合併成一條，term 用「A / B」）"
		for say, terms in by_say.items() if say and len(terms) > 1]


def plan_problems(plan, md):
	problems = glossary_problems(plan)
	n = len(objectives_of(md))
	segs = stories_of(plan)
	if len(segs) > MAX_STORIES:
		problems.append(f"整理成 {len(segs)} 支太碎（上限 {MAX_STORIES}），能在同一畫面講完的請合併")
	if not (plan.get("scope") or {}).get("covers"):
		problems.append("缺 scope.covers（教材涵蓋範圍）")
	ids = [s.get("id") for s in segs]
	if len(set(ids)) != len(ids):
		problems.append("小節 id 重複")
	hl = plan.get("highlight") or {}
	picked = hl.get("stories") or []
	unknown = [h for h in picked if h not in [s.get("id") for s in segs]]
	if not 3 <= len(picked) <= 5 or unknown:
		problems.append(f"highlight.stories 要從 stories 挑 3–5 支（目前 {picked}，不存在：{unknown}）")
	if not 120 <= (hl.get("total_sec") or 0) <= 360:
		problems.append(f"highlight.total_sec={hl.get('total_sec')} 不在 120–360 秒")
	covered = {o for s in segs for o in s.get("objectives", [])}
	missing = [k for k in range(1, n + 1) if k not in covered]
	if missing:
		problems.append(f"學習目標 {missing} 沒有任何小節涵蓋（覆蓋閘）")
	titles = {t for _, t, _ in headings(md)}
	for s in segs:
		if not 40 <= s.get("sec", 0) <= 90:
			problems.append(f"{s.get('id')} 的 sec={s.get('sec')} 不在 40–90")
		if not s.get("question"):
			problems.append(f"{s.get('id')} 缺 question（學生口吻的問題）")
		for src in s.get("sources", []):
			if clean_title(src) not in titles:
				problems.append(f"{s.get('id')} 的 sources「{src}」不是教材中的標題（要逐字照抄，不含 #）")
		for dep in s.get("after", []):
			if dep not in ids:
				problems.append(f"{s.get('id')} 的 after 指向不存在的 {dep}")
		bad = unknown_screens(s.get("screens", []))
		if bad:
			problems.append(f"{s.get('id')} 的 screens {bad} 不是內建介面樣板（只能從清單挑）")
	return problems


def do_plan(md_path, out_dir, budget, target=None):
	with open(md_path, encoding="utf-8") as f:
		md = f.read()
	with open(os.path.join(HERE, "prompts", "plan.system.md"), encoding="utf-8") as f:
		system = f.read().replace("{{PRESETS}}", "\n".join(f"- `{n}`：{t}" for n, t in preset_catalog()))
	print(f"規劃：{md_path}（學習目標 {len(objectives_of(md))} 條）", flush=True)
	plan, repairs = converse(budget, "plan", system, md, lambda p: plan_problems(p, md), target=target)
	with open(os.path.join(out_dir, "plan.json"), "w", encoding="utf-8") as f:
		json.dump(plan, f, ensure_ascii=False, indent="\t")
	for s in stories_of(plan):
		print(f"  {s['id']} {s['sec']}s 目標{s['objectives']}：{s.get('question') or s['title']}")
	hl = plan.get("highlight", {})
	print(f"  重點片 {hl.get('stories')} 約 {hl.get('total_sec')}s：{hl.get('why', '')}")
	return plan


# ── 小節分鏡 ──

# 單獨出現的字母照台灣口語唸（C 語言＝西語言）；整個單字或縮寫仍要靠詞彙表或 spoken
LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", ["欸", "逼", "西", "低", "依", "欸付", "基", "欸取", "愛", "傑", "開", "欸樓", "欸姆",
	"恩", "歐", "披", "丘", "阿", "欸斯", "踢", "優", "威", "達布留", "欸克斯", "歪", "立"]))


CODE_EDGE_L, CODE_EDGE_R = r"(?<![A-Za-z0-9\-+./\\_#])", r"(?![A-Za-z0-9\-+./\\_])"
CODE_TOKEN = re.compile(r"[A-Za-z0-9_]*(?:[\-+./\\#][A-Za-z0-9_]+)+|[\-+./\\#][A-Za-z0-9_]+")


def apply_glossary(doc, glossary):
	"""依單元詞彙表把旁白裡的英文術語換成中文唸法，寫進 spoken。程式處理，不花 tokens；換不掉的才交給閘退件。"""
	terms = sorted((g for g in glossary if g.get("term") and g.get("say_as")), key=lambda g: -max(len(t) for t in re.split(r"\s*/\s*", g["term"])))
	for scene in doc.get("scenes", []):
		for b in scene.get("beats", []):
			text = b.get("spoken") or b.get("say", "")
			for g in terms:
				for term in re.split(r"\s*/\s*", g["term"]):
					if re.search(r"[A-Za-z]", term):
						text = re.sub(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", g["say_as"], text, flags=re.I)
					elif term and not re.search(r"[\u4e00-\u9fff]", term):
						# 純符號（<=、+=）照字面換；詞彙表依長度排序，<= 會先於 < 被換掉
						text = text.replace(term, g["say_as"])
			# 只唸真正單獨的字母（C 語言）；貼著符號的（-o、Ctrl+S、hello.o）是程式碼，留給閘退件改講作用
			text = re.sub(CODE_EDGE_L + r"[A-Za-z]" + CODE_EDGE_R, lambda m: LETTERS[m.group(0).upper()], text)
			if text != (b.get("spoken") or b.get("say", "")):
				b["spoken"] = text
	return doc


def restore_terms(doc, glossary, md):
	"""字幕要寫原名：模型有時把唸法（微軟編輯器）直接寫進 say。教材裡沒出現過的唸法是人造的，換回原名（VS Code）；
	「編譯器」這種教材本來就用的一般詞不動。唸法交給 apply_glossary 產生 spoken。"""
	made_up = [g for g in glossary if g.get("say_as") and g["say_as"] not in md and g.get("term")]
	for scene in doc.get("scenes", []):
		for b in scene.get("beats", []):
			for g in made_up:
				if g["say_as"] in b.get("say", ""):
					b["say"] = re.sub(rf"\s*{re.escape(g['say_as'])}\s*", f" {g['term']} ", b["say"]).strip()
					b["say"] = re.sub(r"\s*([，。、；：？！「」（）])\s*", r"\1", b["say"])
				# 模型常寫成「唸法＋原名」（計數迴圈 for），還原後會變「for for」：連續重複的原名合併成一個
				b["say"] = re.sub(rf"({re.escape(g['term'])})(?:\s*\1)+", r"\1", b.get("say", ""), flags=re.I)
	return doc


def tone_down(doc, keep=2):
	"""免費修正：驚嘆號整支片只留前兩個，其餘改句號（驚嘆號一多就很像 AI 在喊口號）。"""
	left = keep
	for scene in doc.get("scenes", []):
		for b in scene.get("beats", []):
			out = []
			for ch in b.get("say", ""):
				if ch in "！!":
					ch = "！" if left > 0 else "。"
					left -= 1
				out.append(ch)
			b["say"] = "".join(out)
			if b.get("spoken"):
				b["spoken"] = re.sub(r"[！!]", "。", b["spoken"]) if "！" not in b["say"] else b["spoken"]
	return doc


def narration_problems(doc, target, glossary=()):
	problems, chars, seen = [], 0, {}
	terms = [g for g in glossary if g.get("term") and g.get("say_as") and re.search(r"[A-Za-z]", g["term"])]
	for scene in doc.get("scenes", []):
		for b in scene.get("beats", []):
			say = b.get("say", "")
			chars += len(re.sub(r"\s", "", say))
			if say and say in seen:
				problems.append(f"旁白重複（場景 {seen[say]} 已經講過），請刪掉或改寫：{say}")
			seen.setdefault(say, scene.get("id"))
			if len(say) > SAY_MAX:
				problems.append(f"say 超過 {SAY_MAX} 字，請拆句：{say}")
			spoken = b.get("spoken") or say
			# 唸法撞名：gcc 換成「編譯器」後跟句子原本的「編譯器」聽起來一樣（例：編譯器呼叫編譯器）
			for g in terms:
				hits = [t for t in re.split(r"\s*/\s*", g["term"]) if re.search(r"(?<![A-Za-z])" + re.escape(t) + r"(?![A-Za-z])", say, re.I)]
				same = [h for h in terms if h is not g and h["say_as"] == g["say_as"] and re.search(re.escape(h["term"]), say, re.I)]
				if hits and (g["say_as"] in say or same):
					problems.append(f"唸法撞名：「{hits[0]}」唸成「{g['say_as']}」後，跟句子裡的「{g['say_as']}」聽起來是同一個東西，請改寫這句：{say}")
			# 唸法跟後面的字重複：for 唸「計數迴圈」，「for 迴圈」就變成「計數迴圈迴圈」
			for g in terms:
				tail = g["say_as"][-2:]
				if len(g["say_as"]) > 2 and re.search(re.escape(g["say_as"]) + r"\s*" + re.escape(tail), spoken):
					problems.append(f"唸法重複：「{g['term']}」唸成「{g['say_as']}」後接著「{tail}」，聽起來是「{g['say_as']}{tail}」，請改寫這句或用 spoken：{say}")
			code = [t for t in CODE_TOKEN.findall(spoken) if re.search(r"[A-Za-z]", t)]
			hit = spelled(spoken)
			words = [w for w in re.findall(r"[A-Za-z]+", spoken) if w not in ENGLISH_OK]
			if code:
				problems.append(f"旁白在唸程式碼或符號 {code}：畫面會顯示，旁白改講它的作用（例：-o → 指定輸出檔名、Ctrl+S → 存檔、hello.c → 原始碼檔），用 spoken 寫：{say}")
			elif hit:
				problems.append(f"旁白含逐字母縮寫 {hit}（TTS 會變氣音），請加 spoken 改中文說法：{say}")
			elif words:
				problems.append(f"旁白夾英文單字 {words}（TTS 會唸糊並吃掉後面的字），請加 spoken 改中文說法：{say}")
	est = chars / CHARS_PER_SEC
	if not 40 <= est <= 90 or abs(est - target) > target * .35:
		problems.append(f"旁白 {chars} 字約 {est:.0f} 秒，目標 {target} 秒（約 {round(target * CHARS_PER_SEC)} 字），請增刪內容")
	return problems


PRESET_DIR = os.path.join(HERE, "presets")


def preset_title(name):
	path = os.path.join(PRESET_DIR, *name.split(".")) + ".json"
	if not os.path.exists(path):
		return None
	with open(path, encoding="utf-8") as f:
		return json.load(f).get("title") or name


def preset_catalog():
	"""內建介面樣板清單（給規劃挑必演畫面用）。"""
	out = []
	for path in sorted(glob.glob(os.path.join(PRESET_DIR, "*", "*.json"))):
		name = ".".join(os.path.relpath(path, PRESET_DIR)[:-5].split(os.sep))
		out.append((name, preset_title(name)))
	return out


def unknown_screens(screens):
	return [n for n in screens if preset_title(n) is None]


def screen_problems(doc, screens):
	"""操作類必演畫面：規劃列出的介面樣板都要出現，而且照順序（漏了步驟，學生就不知道視窗怎麼開）。"""
	if not screens:
		return []
	presets = {o.get("id"): o.get("preset") for o in doc.get("objects", []) if o.get("preset")}
	seen = []
	for scene in doc.get("scenes", []):
		used = set(re.findall(r'"([A-Za-z0-9_]+)(?::[^"]*)?"', json.dumps(scene, ensure_ascii=False)))
		for oid, name in presets.items():
			if oid in used and name not in seen:
				seen.append(name)
	missing = [n for n in screens if n not in seen]
	if missing:
		return [f"漏了必演畫面：{'、'.join(f'{preset_title(n)}（{n}）' for n in missing)}。學生要看到完整路徑，"
			f"請依序演出：{' → '.join(preset_title(n) for n in screens)}（每個畫面一場，用 cursor 點出下一步）"]
	order = [n for n in seen if n in screens]
	if order != list(screens):
		return [f"必演畫面順序不對：現在是 {' → '.join(map(preset_title, order))}，應該是 {' → '.join(map(preset_title, screens))}"]
	return []


CROWDED = ("在全景時字太小", "版面縮到")


def auto_focus(doc, problems):
	"""太擠被判字太小的場景：開場就把鏡頭推近到第一個動作的目標，之後交給 runtime 的鏡頭跟隨（不呼叫 LLM）。
	回傳有沒有改；已經有 focus 的場景不動，免得跟模型自己的鏡頭打架。"""
	changed = False
	for scene in doc.get("scenes", []):
		if not any(f"場景 {scene.get('id')} " in p and any(k in p for k in CROWDED) for p in problems):
			continue
		acts = [a for b in scene.get("beats", []) for a in b.get("do", [])]
		if any(a.get("act") == "focus" for a in acts) or not scene.get("beats"):
			continue
		first = next((a for a in acts if a.get("act") not in ("show", "hide", "wide", "focus") and a.get("target")), None)
		if first is None:
			continue
		for b in scene["beats"]:
			b["do"] = [a for a in b.get("do", []) if a.get("act") != "wide"]
		# 放在第一句的動作最後：物件通常在第一句才 show，太早推近會找不到目標
		scene["beats"][0].setdefault("do", []).append({"act": "focus", "target": first["target"]})
		changed = True
	return changed


MAX_OBJECTS = 2


def layout_ids(node):
	if isinstance(node, str):
		return [node]
	if isinstance(node, dict) and len(node) == 1:
		return [i for k in next(iter(node.values())) for i in layout_ids(k)]
	return []


def crowd_problems(doc):
	"""主體要大、重點要清楚：每場 layout 最多 2 個主要物件（small note 不算）。"""
	small = {o["id"] for o in doc.get("objects", []) if o.get("type") == "note" and o.get("style") == "small"}
	problems = []
	for scene in doc.get("scenes", []):
		ids = []
		for node in [scene.get("layout")] + [b.get("layout") for b in scene.get("beats", [])]:
			ids += [i for i in layout_ids(node) if i not in ids]
		main = [i for i in ids if i not in small]
		if len(main) > MAX_OBJECTS:
			problems.append(f"場景 {scene.get('id')} 同時放了 {len(main)} 個主要物件 {main}，上限 {MAX_OBJECTS}：拆成兩場（用 keep 帶主角過去），每樣才夠大")
	return problems


MAX_MARKS = 3
MARK_ACTS = ("circle", "underline", "arrow", "brace")


def mark_problems(doc):
	"""每場標註上限：標註一多畫面就亂。同一物件的圈會互相取代（新圈出現舊圈淡出），只算一個。"""
	problems = []
	for scene in doc.get("scenes", []):
		n, circled = 0, set()
		for b in scene.get("beats", []):
			for a in b.get("do", []):
				if a.get("act") not in MARK_ACTS:
					continue
				if a["act"] == "circle":
					obj = str(a.get("target", "")).split(":")[0]
					if obj in circled:
						continue
					circled.add(obj)
				n += 1
		if n > MAX_MARKS:
			problems.append(f"場景 {scene.get('id')} 用了 {n} 個標註（圈／底線／箭頭／括號），上限 {MAX_MARKS}：只留最關鍵的，其餘交給旁白")
	return problems


CRASH_DIR = os.path.join(HERE, "..", "out", "check_crashes")


def measure_problems(timeline):
	with tempfile.TemporaryDirectory() as d:
		build(timeline, d)
		r = subprocess.run([PLAYWRIGHT_PY, os.path.join(HERE, "check.py"), d], capture_output=True, text=True)
		if r.returncode == 0:
			return []
		report = os.path.join(d, "check.json")
		if os.path.exists(report):
			with open(report, encoding="utf-8") as f:
				return ["版面：" + p for p in json.load(f)["problems"]][:10]
	# 量測閘本身沒跑完：多半是元件遇到沒處理過的寫法而丟錯，是元件的 bug，存下時間軸供追查
	os.makedirs(CRASH_DIR, exist_ok=True)
	path = os.path.join(CRASH_DIR, time.strftime("%Y%m%d-%H%M%S") + ".timeline.json")
	with open(path, "w", encoding="utf-8") as f:
		json.dump(timeline, f, ensure_ascii=False)
	last = (r.stderr.strip().splitlines() or ["（無訊息）"])[-1]
	print(f"  量測閘執行失敗，時間軸存於 {path}：{last}", flush=True)
	return [f"版面：畫面元件無法處理這份分鏡（{last[:200]}），請改用較單純的寫法"]


def scene_problems(doc, target, catalog, glossary=()):
	try:
		tl = BC.compile_scene(doc, None, catalog)
	except (ValueError, KeyError, TypeError) as e:
		return [f"編譯失敗：{e}"]
	problems = [f"{g['where'] + ' ' if g.get('where') else ''}用了不存在的元件或動作 {g['wanted']}，請改用目錄內的" for g in tl["gaps"]]
	problems += [f"編譯警告：{w}" for w in tl["warnings"]]
	problems += narration_problems(doc, target, glossary)
	problems += mark_problems(doc)
	problems += crowd_problems(doc)
	return problems or measure_problems(tl)


def preflight():
	"""付費前先跑本機自我檢查（不花錢）：元件或量測閘有 bug 就不准呼叫 LLM，免得把元件的錯算到模型頭上。"""
	r = subprocess.run([sys.executable, os.path.join(HERE, "selftest.py"), "--quick"], capture_output=True, text=True)
	print("  " + (r.stdout.strip().splitlines() or ["（無輸出）"])[-1], flush=True)
	if r.returncode:
		sys.exit("本機自我檢查沒過，先修元件再呼叫 AI：\n" + r.stdout[-2000:] + r.stderr[-500:])


def do_scene(md_path, out_dir, seg_id, budget, target=None, repair_target=None, resume=False):
	with open(md_path, encoding="utf-8") as f:
		md = f.read()
	with open(os.path.join(out_dir, "plan.json"), encoding="utf-8") as f:
		plan = json.load(f)
	seg = next(s for s in stories_of(plan) if s["id"] == seg_id)
	catalog = BC.load_catalog()
	with open(os.path.join(HERE, "prompts", "scene.system.md"), encoding="utf-8") as f:
		system = f.read()
	with open(os.path.join(HERE, "prompts", "components.md"), encoding="utf-8") as f:
		system = system.replace("{{COMPONENTS}}", f.read())
	screens = seg.get("screens") or []
	# 操作類附操作範例（從搜尋一路演到驗證），概念類附字串範例；放在系統提示裡走快取
	example = "env_path_howto.scene.json" if screens else "c_string.scene.json"
	with open(os.path.join(HERE, "examples", example), encoding="utf-8") as f:
		system = system.replace("{{EXAMPLE}}", f.read())
	sources = [section(md, clean_title(t)) for t in seg.get("sources", [])]
	excerpt = "\n\n".join(s for s in sources if s) or md
	objectives = objectives_of(md)
	user = "\n".join([
		f"單元：{plan.get('unit_title', '')}",
		f"學生的問題：{seg.get('question', seg['title'])}" + (f"（其他問法：{'；'.join(seg.get('also_asks', []))}）" if seg.get("also_asks") else ""),
		f"本支：{seg['title']}（目標 {seg['sec']} 秒，旁白約 {round(seg['sec'] * CHARS_PER_SEC)} 字）。整支影片就是在回答這個問題。",
		"本節學習目標：" + "；".join(objectives[i - 1] for i in seg["objectives"] if 0 < i <= len(objectives)),
		f"畫面要演出的過程：{seg.get('show', '')}",
		*([f"必演畫面（依序，每個一場，用 cursor 點出下一步；學生要看到視窗怎麼打開）：{' → '.join(f'{preset_title(n)}（preset {n}）' for n in screens)}"] if screens else []),
		"全單元統一用語：" + "；".join(f"{g['term']} 唸作「{g['say_as']}」" for g in plan.get("glossary", [])),
		"", "# 教材段落", excerpt,
	])
	print(f"分鏡：{seg_id} {seg['title']}（{seg['sec']}s）", flush=True)
	preflight()
	glossary = plan.get("glossary", [])
	failed_path = os.path.join(out_dir, f"{seg_id}.failed.json")
	start = None
	if resume and os.path.exists(failed_path):
		with open(failed_path, encoding="utf-8") as f:
			start = json.load(f)["last"]
		print("  從上次失敗的草稿接著修", flush=True)
	def validate(d):
		check = lambda: screen_problems(d, screens) + scene_problems(apply_glossary(restore_terms(tone_down(d), glossary, md), glossary), seg["sec"], catalog, glossary)
		problems = check()
		# 免費修正：太擠的場景自動推近，過了就不用叫模型重寫
		if auto_focus(d, problems):
			print("  自動推近太擠的場景後重新驗證", flush=True)
			problems = check()
		return problems
	doc, repairs = converse(budget, "scene", system, user, validate,
		failed_path=failed_path, target=target, repair_target=repair_target, scenes_of=problem_scenes, start=start)
	path = os.path.join(out_dir, f"{seg_id}.scene.json")
	with open(path, "w", encoding="utf-8") as f:
		json.dump(doc, f, ensure_ascii=False, indent="\t")
	report = {"segment": seg, "repairs": repairs, "bytes_minified": len(json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode())}
	with open(os.path.join(out_dir, f"{seg_id}.report.json"), "w", encoding="utf-8") as f:
		json.dump(report, f, ensure_ascii=False, indent="\t")
	print(f"  → {path}（修正 {repairs} 次，{report['bytes_minified']} bytes）")


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("stage", choices=["plan", "scene"])
	ap.add_argument("md")
	ap.add_argument("out_dir")
	ap.add_argument("segment", nargs="?")
	ap.add_argument("--budget-usd", type=float, default=2.0)
	ap.add_argument("--model", help="覆寫預設模型，例 anthropic:claude-opus-5-5 或 google:gemini-3.8-flash")
	ap.add_argument("--repair-model", help="重寫用的模型（預設同 --model），例 google:gemini-3.8-flash")
	ap.add_argument("--resume", action="store_true", help="scene：從 <segment>.failed.json 的草稿接著修，不重寫第一版")
	args = ap.parse_args()
	os.makedirs(args.out_dir, exist_ok=True)
	sys.path.insert(0, os.path.dirname(HERE))
	import llm
	llm.load_env()
	budget = Budget(os.path.join(args.out_dir, "usage.jsonl"), args.budget_usd)
	try:
		if args.stage == "plan":
			do_plan(args.md, args.out_dir, budget, args.model)
		else:
			do_scene(args.md, args.out_dir, args.segment, budget, args.model, args.repair_model, args.resume)
	except BudgetExceeded as e:
		sys.exit(f"預算上限：{e}")
	print(f"累計花費 US${budget.spent():.4f}／上限 US${budget.cap:.2f}")


if __name__ == "__main__":
	main()
