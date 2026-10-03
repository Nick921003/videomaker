#!/usr/bin/env python3
"""教材 md → 單元規劃 → 小節 scene.json（Opus 5.5），含預算上限與驗證閘修正迴圈。

用法：
  .venv/bin/python video_engine/board/author.py plan  <教材.md> <輸出目錄> [--budget-usd 2]
  .venv/bin/python video_engine/board/author.py scene <教材.md> <輸出目錄> <小節id> [--budget-usd 2]

輸出目錄：plan.json、<id>.scene.json、<id>.report.json、usage.jsonl（每次呼叫的 tokens 與估價）。
預算是整個輸出目錄累計的：每次呼叫前先用免費的 count_tokens 量輸入，加上輸出上限算最壞情況，超過就不呼叫。
"""
import argparse
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


def call_anthropic(budget, stage, model, system, messages):
	import anthropic
	client = anthropic.Anthropic()
	sys_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
	count = client.messages.count_tokens(model=model, system=sys_blocks, messages=messages, thinking={"type": "adaptive"})
	budget.guard(model, count.input_tokens, MAX_TOKENS[stage])
	resp = client.messages.create(model=model, max_tokens=MAX_TOKENS[stage], system=sys_blocks, messages=messages,
		thinking={"type": "adaptive"}, output_config={"effort": "medium"})
	u = resp.usage
	usage = {"in": u.input_tokens, "out": u.output_tokens, "cache_read": u.cache_read_input_tokens or 0,
		"cache_write": u.cache_creation_input_tokens or 0}
	text = next((b.text for b in resp.content if b.type == "text"), "")
	return text, usage, resp.stop_reason == "max_tokens"


def call_google(budget, stage, model, system, messages):
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


def call(budget, stage, system, messages, target):
	provider, model = target.split(":", 1)
	text, usage, truncated = (call_google if provider == "google" else call_anthropic)(budget, stage, model, system, messages)
	usd = budget.record(stage, model, usage)
	print(f"  {stage}［{model}］：輸入 {usage['in']}＋快取讀 {usage['cache_read']}＋快取寫 {usage['cache_write']}，輸出 {usage['out']}，US${usd:.4f}（累計 US${budget.spent():.4f}）", flush=True)
	if truncated:
		raise RuntimeError(f"{stage} 輸出達到上限 {MAX_TOKENS[stage]}")
	return text


def converse(budget, stage, system, user, validate, failed_path=None, target=None):
	target = target or DEFAULT_MODEL[stage]
	"""呼叫 → 驗證 → 有問題就把問題清單丟回去，只修那些，最多 MAX_REPAIRS 次。"""
	messages = [{"role": "user", "content": user}]
	for attempt in range(MAX_REPAIRS + 1):
		text = call(budget, stage, system, messages, target)
		try:
			data = first_json(text)
			problems = validate(data)
		except ValueError as e:
			data, problems = None, [str(e)]
		if not problems:
			return data, attempt
		print(f"  第 {attempt + 1} 次未過驗證閘：", *problems[:8], sep="\n    ", flush=True)
		messages += [{"role": "assistant", "content": text},
			{"role": "user", "content": "驗證閘回報以下問題，只修這些，其餘維持不變，輸出完整修正後的 JSON：\n- " + "\n- ".join(problems[:20])}]
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


def plan_problems(plan, md):
	problems = []
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
	return problems


def do_plan(md_path, out_dir, budget, target=None):
	with open(md_path, encoding="utf-8") as f:
		md = f.read()
	with open(os.path.join(HERE, "prompts", "plan.system.md"), encoding="utf-8") as f:
		system = f.read()
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


def apply_glossary(doc, glossary):
	"""依單元詞彙表把旁白裡的英文術語換成中文唸法，寫進 spoken。程式處理，不花 tokens；換不掉的才交給閘退件。"""
	terms = sorted((g for g in glossary if g.get("term") and g.get("say_as")), key=lambda g: -len(g["term"]))
	for scene in doc.get("scenes", []):
		for b in scene.get("beats", []):
			text = b.get("spoken") or b.get("say", "")
			for g in terms:
				for term in re.split(r"\s*/\s*", g["term"]):
					if re.search(r"[A-Za-z]", term):
						text = re.sub(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", g["say_as"], text, flags=re.I)
			text = re.sub(r"(?<![A-Za-z])[A-Za-z](?![A-Za-z])", lambda m: LETTERS[m.group(0).upper()], text)
			if text != (b.get("spoken") or b.get("say", "")):
				b["spoken"] = text
	return doc


def narration_problems(doc, target):
	problems, chars = [], 0
	for scene in doc.get("scenes", []):
		for b in scene.get("beats", []):
			say = b.get("say", "")
			chars += len(re.sub(r"\s", "", say))
			if len(say) > SAY_MAX:
				problems.append(f"say 超過 {SAY_MAX} 字，請拆句：{say}")
			spoken = b.get("spoken") or say
			hit = spelled(spoken)
			words = [w for w in re.findall(r"[A-Za-z]+", spoken) if w not in ENGLISH_OK]
			if hit:
				problems.append(f"旁白含逐字母縮寫 {hit}（TTS 會變氣音），請加 spoken 改中文說法：{say}")
			elif words:
				problems.append(f"旁白夾英文單字 {words}（TTS 會唸糊並吃掉後面的字），請加 spoken 改中文說法：{say}")
	est = chars / CHARS_PER_SEC
	if not 40 <= est <= 90 or abs(est - target) > target * .35:
		problems.append(f"旁白 {chars} 字約 {est:.0f} 秒，目標 {target} 秒（約 {round(target * CHARS_PER_SEC)} 字），請增刪內容")
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


def scene_problems(doc, target, catalog):
	try:
		tl = BC.compile_scene(doc, None, catalog)
	except (ValueError, KeyError, TypeError) as e:
		return [f"編譯失敗：{e}"]
	problems = [f"用了不存在的元件或動作 {g['wanted']}，請改用目錄內的" for g in tl["gaps"]]
	problems += [f"編譯警告：{w}" for w in tl["warnings"]]
	problems += narration_problems(doc, target)
	return problems or measure_problems(tl)


def do_scene(md_path, out_dir, seg_id, budget, target=None):
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
	with open(os.path.join(HERE, "examples", "c_string.scene.json"), encoding="utf-8") as f:
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
		"全單元統一用語：" + "；".join(f"{g['term']} 唸作「{g['say_as']}」" for g in plan.get("glossary", [])),
		"", "# 教材段落", excerpt,
	])
	print(f"分鏡：{seg_id} {seg['title']}（{seg['sec']}s）", flush=True)
	glossary = plan.get("glossary", [])
	doc, repairs = converse(budget, "scene", system, user, lambda d: scene_problems(apply_glossary(d, glossary), seg["sec"], catalog),
		failed_path=os.path.join(out_dir, f"{seg_id}.failed.json"), target=target)
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
			do_scene(args.md, args.out_dir, args.segment, budget, args.model)
	except BudgetExceeded as e:
		sys.exit(f"預算上限：{e}")
	print(f"累計花費 US${budget.spent():.4f}／上限 US${budget.cap:.2f}")


if __name__ == "__main__":
	main()
