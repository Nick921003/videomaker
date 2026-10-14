"""獨立試片的模型呼叫與原始證據；每階段僅呼叫一次，不自動重試。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from video_engine import llm
from studio.material_normalizer import normalize_material
from state_model import validate_beats

OUT = ROOT / "video_engine/out/state_change_pilot_20261001"
SOURCE = ROOT / "video_engine/materials/c_string.md"


def save(name, data):
	with (OUT / name).open("x", encoding="utf-8") as handle:
		handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def normalize():
	from google import genai
	from google.genai import types
	model = os.environ.get("STUDIO_INGEST_MODEL", "gemini-3.8-flash")
	def runner(system, user, pdf):
		assert pdf is None
		save("gemini_request.json", {"model": model, "system": system, "user": user})
		start = time.monotonic()
		client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
		response = client.models.generate_content(model=model, contents=user,
			config=types.GenerateContentConfig(system_instruction=system,
				max_output_tokens=llm.output_limit("ingest"), response_mime_type="application/json",
				automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
		save("gemini_response.json", response.model_dump(mode="json", exclude_none=True))
		meta = response.usage_metadata
		usage = {"provider": "google", "model": model,
			"response_model": response.model_version,
			"input_tokens": meta.prompt_token_count,
			"output_tokens": meta.candidates_token_count,
			"thought_tokens": meta.thoughts_token_count,
			"total_tokens": meta.total_token_count,
			"seconds": round(time.monotonic() - start, 3), "calls": 1}
		save("gemini_usage.json", usage)
		return llm._first_json(response.text), usage
	record = SimpleNamespace(material_path=str(SOURCE), original_name=SOURCE.name, raw_path=str(SOURCE))
	cleaned, usage = normalize_material(record, runner=runner)
	(OUT / "normalized.md").write_text(cleaned, encoding="utf-8")
	save("source_manifest.json", {"path": str(SOURCE.relative_to(ROOT)),
		"sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
		"normalized_sha256": hashlib.sha256(cleaned.encode()).hexdigest(),
		"usage": usage, "existing_normalization_reused": False})
	print(json.dumps(usage, ensure_ascii=False))


def storyboard():
	import anthropic
	provider, model = llm.target("lesson")
	if provider != "anthropic":
		raise RuntimeError("目前 lesson 設定不是 Anthropic；必須先告知使用者，不能假稱 Claude。")
	system = "你是繁體中文教學動畫分鏡設計師。只回傳 JSON，不執行工具。讀教材並以連續物件的狀態變化解釋概念。"
	lines = "\n".join(f"L{i}: {line}" for i, line in enumerate(SOURCE.read_text().splitlines(), 1))
	user = f"""製作學生看得懂的 30–60 秒 C 字串試片。以下是原文與 Gemini 整理稿。
使用同一個 name[32] 陣列、讀取游標及輸出面板，統一風格，不要求學生寫重點或分鏡。
以 char name[32]; strcpy(name, "Alice"); 為範例。printf("%s", name) 是從原教材 printf 簡化的衍生示範。
不能宣稱真實標準函式一定逐位元組實作；動畫是概念示意。strcpy 複製包含 NUL，尾部索引6..31保持未知。
原文幾個說法需要修正：未終止字串可能導致未定義行為，不保證亂碼；陣列不能以 = 重新指定；位址比較不是永遠不相等。本片聚焦正確範例，不擴張這些錯誤。
規格：JSON 頂層 title, learning_goal, initial_state, final_state, style_rules, beats。
beats 每段含 id, phase, speech, caption, student_sees, before, after, cause, source_lines (原文行號整數陣列), source_quote。
phase 依序 setup, copy, scan (五段), stop, summary, question，共10段。
scan 五段另附 index 0..4 和 output_after 分別 A, Al, Ali, Alic, Alice。
每段 scan 旁白須先講對應字母／逐格前進，再說輸出形成；學生看見游標移到這一格，字元從陣列流到輸出，輸出累積，已輸出字元數加一。
stop index=5 output_after=Alice，讀到 \\0 就停止，不印出終止符、不讀未知尾端。不能同時假稱在做 strlen；掃描面板計數叫「已輸出字元」。
setup 是32格未初始化；copy 顯示 A l i c e \\0，只畫前六格，另明示6..31仍未知。
summary 才顯示 strlen(name)=5、sizeof name=32、至少需要6格；旁白分清容量、長度和終止符。
question 提一個易回答的回想題並給答案，例如終止符是否算在長度中，不能讀取未初始化資料。
中文 speech 全片約200–260字，每段8–50字。scan 每段至少8個中文字，以利TTS；英文單字 Alice 在 speech 寫「愛麗絲」，字母可用英文字母但保留中文上下文。
caption 每段<=24字。所有源據精確對回原文；衍生示意在student_sees明示。可由實測TTS長度排程，不編造毫秒時間。

原文：
{lines}

Gemini 整理稿：
{(OUT / 'normalized.md').read_text()}
"""
	save("claude_request.json", {"model": model, "system": system, "user": user,
		"max_tokens": 12000, "effort": "medium", "automatic_retries": 0,
		"budget_authorization": "使用者 2026-10-01 明確授權此原型重試並提高至12000"})
	start = time.monotonic()
	client = anthropic.Anthropic(max_retries=0, timeout=180)
	response = client.messages.create(model=model, system=system,
		messages=[{"role": "user", "content": user}], max_tokens=12000,
		thinking={"type": "adaptive"}, output_config={"effort": "medium"})
	save("claude_response.json", response.model_dump(mode="json", exclude_none=True))
	usage = response.usage.model_dump(mode="json", exclude_none=True)
	save("claude_usage.json", {"provider": "anthropic", "requested_model": model,
		"response_model": response.model, "usage": usage,
		"seconds": round(time.monotonic() - start, 3), "calls": 1,
		"thought_tokens": usage.get("output_tokens_details", {}).get("thinking_tokens"),
		"thought_accounting": "思考量已包含於output_tokens，不重複加總"})
	if response.stop_reason != "end_turn":
		raise RuntimeError(f"Claude stop_reason={response.stop_reason}；需診斷，不自動重試。")
	text = "\n".join(block.text for block in response.content if block.type == "text")
	data = llm._first_json(text)
	save("storyboard.json", data)
	validate_beats(data["beats"])
	for beat in data["beats"]:
		if not all(key in beat for key in ("speech", "caption", "student_sees", "before", "after", "cause", "source_lines", "source_quote")):
			raise ValueError("分鏡缺少必要的來源或狀態欄位")
		if len(beat["caption"]) > 24 or not 8 <= len(beat["speech"]) <= 60:
			raise ValueError("分鏡字幕或旁白長度超出規格")
		original_lines = SOURCE.read_text().splitlines()
		if not beat["source_lines"] or any(type(n) is not int or not 1 <= n <= len(original_lines) for n in beat["source_lines"]):
			raise ValueError("教材來源行號不存在")
		excerpt = "\n".join(original_lines[n-1] for n in beat["source_lines"])
		from studio.material_normalizer import _source_quote
		if _source_quote(excerpt, beat["source_quote"]) is None:
			raise ValueError(f"分鏡 {beat['id']} 引文無法對回來源行")
	save("storyboard_validation.json", {"valid": True, "state_checks": True, "source_quote_checks": True})
	print(json.dumps({"response_model": response.model, "usage": usage,
		"beats": len(data["beats"]), "speech_chars": sum(len(b["speech"]) for b in data["beats"])}, ensure_ascii=False))


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("stage", choices=["normalize", "storyboard"])
	parser.add_argument("--output-dir", type=Path)
	args = parser.parse_args()
	if args.output_dir:
		OUT = args.output_dir.resolve()
	OUT.mkdir(parents=True, exist_ok=True)
	llm.load_env()
	prefix = "gemini" if args.stage == "normalize" else "claude"
	if (OUT / f"{prefix}_request.json").exists():
		raise SystemExit("已有呼叫證據，拒絕重跑或覆寫；先取得額外重試授權。")
	try:
		{"normalize": normalize, "storyboard": storyboard}[args.stage]()
	except Exception as exc:
		save(f"{args.stage}_failure.json", {"type": type(exc).__name__,
			"message": str(exc)[:500], "automatic_retries": 0})
		print(f"{args.stage} failed: {type(exc).__name__}; see saved diagnostic")
		raise SystemExit(1)
