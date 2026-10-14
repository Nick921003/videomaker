#!/usr/bin/env python3
"""LLM 轉接層：管線裡兩處需要 LLM 的步驟共用，換供應商只改一個設定。

設定（環境變數或專案根目錄的 .env）：
	VIDEO_ENGINE_LLM=anthropic:claude-opus-5-5      預設
	VIDEO_ENGINE_LLM=openai:gpt-5.6-terra
	VIDEO_ENGINE_LLM=google:gemini-3.8-flash
	VIDEO_ENGINE_LLM=openai-compatible:<model>    本機 vLLM／Ollama，另設 LLM_BASE_URL

各家用自家官方 SDK，延遲載入——只有真的選到才需要裝。
"""
import json
import os
import re

try:
	from video_engine.usage import report_usage
except ModuleNotFoundError:
	from usage import report_usage


def _request(provider, model, function, /, **kwargs):
	try:
		return function(**kwargs)
	except Exception:
		report_usage(provider, model, {})
		raise


def _google_usage(response):
	usage = getattr(response, 'usage_metadata', None)
	return {'in':getattr(usage, 'prompt_token_count', None),
		'out':getattr(usage, 'candidates_token_count', None),
		'thinking':getattr(usage, 'thoughts_token_count', None),
		'total':getattr(usage, 'total_token_count', None),
		'cache_read':getattr(usage, 'cached_content_token_count', 0) or 0}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 預設組合：結構化只跑一次、影響整份骨架，用最強的；編排每頁跑一次，用便宜快的
DEFAULT_TARGET = "anthropic:claude-opus-5-5"
DEFAULT_BY_STAGE = {
	"lesson": "anthropic:claude-opus-5-5",
	"actions": "google:gemini-3.8-flash",
	"ingest": "google:gemini-3.8-flash",
}
# 硬上限包含模型思考與可見文字；每次重試也受同一上限約束。
MAX_OUTPUT_BY_STAGE = {
	"lesson": 8192,
	"paper": 16384,
	"actions": 4096,
	"deck": 12288,
	"mindmap": 4096,
	"ingest": 16000,
}
MAX_OUTPUT_DEFAULT = 8192


def output_limit(stage, requested=None):
	cap = MAX_OUTPUT_BY_STAGE.get(stage, MAX_OUTPUT_DEFAULT)
	if requested is None:
		return cap
	if type(requested) is not int or requested < 1:
		raise ValueError("max_tokens 必須是正整數")
	return min(requested, cap)

# 各供應商目前的主力型號，供 --list 顯示與挑選（2026-09 查證）
KNOWN = {
	"anthropic": ["claude-opus-5-5", "claude-sonnet-5", "claude-haiku-4-5"],
	"openai": ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
	"google": ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.1-pro-preview", "gemini-3.5-flash-lite"],
}


def load_env(path=None):
	"""讀專案根目錄的 .env，已存在的環境變數優先，不覆蓋"""
	path = path or os.path.join(BASE_DIR, ".env")
	if not os.path.exists(path):
		return
	with open(path, encoding="utf-8") as handle:
		for line in handle:
			line = line.strip()
			if not line or line.startswith("#") or "=" not in line:
				continue
			k, v = line.split("=", 1)
			k, v = k.strip(), v.strip().strip('"').strip("'")
			os.environ.setdefault(k, v)


def target(stage=None):
	"""VIDEO_ENGINE_LLM 覆蓋一切；沒設就用該階段的預設"""
	load_env()
	spec = os.environ.get("VIDEO_ENGINE_LLM") or DEFAULT_BY_STAGE.get(stage, DEFAULT_TARGET)
	provider, _, model = spec.partition(":")
	if not model:
		raise SystemExit(f"VIDEO_ENGINE_LLM 格式應為 provider:model，收到 {spec!r}")
	return provider, model


def _first_json(text):
	"""從回應裡挖出 JSON。有結構化輸出的供應商不會走到這裡"""
	text = text.strip()
	if text.startswith("```"):
		text = re.sub(r"^```[a-z]*\n|\n```$", "", text).strip()
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		pass
	for a, b in (("{", "}"), ("[", "]")):
		i, j = text.find(a), text.rfind(b)
		if i >= 0 and j > i:
			try:
				return json.loads(text[i:j + 1])
			except json.JSONDecodeError:
				continue
	raise ValueError(f"回應不是合法 JSON：{text[:200]}")


def _anthropic(model, system, user, schema, max_tokens, effort):
	import anthropic

	client = anthropic.Anthropic()
	kwargs = {
		"model": model,
		"max_tokens": max_tokens,
		"system": system,
		"messages": [{"role": "user", "content": user}],
		"thinking": {"type": "adaptive"},
		"output_config": {"effort": effort},
	}
	if schema:
		kwargs["output_config"]["format"] = {"type": "json_schema", "schema": schema}
	resp = _request('anthropic', model, client.messages.create, **kwargs)
	raw_usage = getattr(resp, 'usage', None)
	cache = getattr(raw_usage, 'cache_creation', None)
	usage = {'in':getattr(raw_usage, 'input_tokens', None), 'out':getattr(raw_usage, 'output_tokens', None),
		'thinking':getattr(getattr(raw_usage, 'output_tokens_details', None), 'thinking_tokens', None),
		'cache_read':getattr(raw_usage, 'cache_read_input_tokens', 0) or 0,
		'cache_creation':getattr(raw_usage, 'cache_creation_input_tokens', 0) or 0,
		'cache_creation_1h':getattr(cache, 'ephemeral_1h_input_tokens', 0) or 0}
	report_usage('anthropic', getattr(resp, 'model', None) or model, usage)
	if resp.stop_reason == "refusal":
		raise RuntimeError(f"模型拒絕回應：{getattr(resp.stop_details, 'category', '')}")
	if resp.stop_reason == "max_tokens":
		raise RuntimeError("模型輸出達到 token 上限，請縮短教材或調整格式")
	text = next((b.text for b in resp.content if b.type == "text"), "")
	return _first_json(text), usage


def _openai(model, system, user, schema, max_tokens, effort, base_url=None):
	from openai import OpenAI

	client = OpenAI(base_url=base_url) if base_url else OpenAI()
	kwargs = {
		"model": model,
		"max_completion_tokens": max_tokens,
		"messages": [
			{"role": "system", "content": system},
			{"role": "user", "content": user},
		],
	}
	if schema:
		# json_object 模式禁止頂層陣列，會把陣列拆成單一物件；要用 json_schema 才能指定外框
		kwargs["response_format"] = {
			"type": "json_schema",
			"json_schema": {"name": "output", "schema": schema, "strict": False},
		}
	provider = 'openai-compatible' if base_url else 'openai'
	resp = _request(provider, model, client.chat.completions.create, **kwargs)
	usage = {'in':getattr(resp.usage, 'prompt_tokens', None),
		'out':getattr(resp.usage, 'completion_tokens', None),
		'thinking':getattr(getattr(resp.usage, 'completion_tokens_details', None), 'reasoning_tokens', 0) or 0,
		'cache_read':getattr(getattr(resp.usage, 'prompt_tokens_details', None), 'cached_tokens', 0) or 0}
	report_usage(provider, getattr(resp, 'model', None) or model, usage)
	text = resp.choices[0].message.content or ""
	return _first_json(text), usage


def _google(model, system, user, schema, max_tokens, effort):
	from google import genai
	from google.genai import types

	client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
	cfg = types.GenerateContentConfig(
		system_instruction=system,
		max_output_tokens=max_tokens,
		response_mime_type="application/json",
		response_json_schema=schema,
		# 我們不用函式呼叫，關掉才不會每次都印警告
		automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
	)
	resp = _request('google', model, client.models.generate_content, model=model, contents=user, config=cfg)
	usage = _google_usage(resp)
	report_usage('google', getattr(resp, 'model_version', None) or model, usage)
	return _first_json(resp.text), usage


def complete_ingest_text_json(system, user, max_tokens=None):
    """教材整理固定使用 Gemini；不受影片全域模型覆蓋影響。"""
    load_env()
    model = os.environ.get("STUDIO_INGEST_MODEL", "gemini-3.8-flash")
    data, usage = _google(model, system, user, None, output_limit("ingest", max_tokens), "high")
    return data, {"provider": "google", "model": model, **usage}


def complete_pdf_json(system, user, pdf_bytes, max_tokens=None):
    """讓 Gemini 同時閱讀抽取文字與原 PDF 頁面；只在使用者確認整理後呼叫。"""
    from google import genai
    from google.genai import types

    load_env()
    model = os.environ.get("STUDIO_INGEST_MODEL", "gemini-3.8-flash")
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    cfg = types.GenerateContentConfig(
        system_instruction=system, max_output_tokens=output_limit("ingest", max_tokens),
        response_mime_type="application/json",
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    response = _request('google', model, client.models.generate_content,
        model=model,
        contents=[types.Part.from_text(text=user),
                  types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")],
        config=cfg,
    )
    usage = _google_usage(response)
    report_usage('google', getattr(response, 'model_version', None) or model, usage)
    return _first_json(response.text), {"provider": "google", "model": model, **usage}


def complete_json(system, user, schema=None, max_tokens=None, effort=None, stage=None):
	"""要一份 JSON 回來。回傳 (資料, {供應商, 型號, token 用量})"""
	provider, model = target(stage)
	max_tokens = output_limit(stage, max_tokens)
	effort = effort or ("medium" if model == "claude-opus-5-5" else "high")
	if provider == "anthropic":
		data, usage = _anthropic(model, system, user, schema, max_tokens, effort)
	elif provider == "openai":
		data, usage = _openai(model, system, user, schema, max_tokens, effort)
	elif provider == "openai-compatible":
		data, usage = _openai(model, system, user, schema, max_tokens, effort,
			base_url=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8000/v1"))
	elif provider == "google":
		data, usage = _google(model, system, user, schema, max_tokens, effort)
	else:
		raise SystemExit(f"未知供應商 {provider}，可用：anthropic / openai / google / openai-compatible")
	return data, {"provider": provider, "model": model, **usage}


if __name__ == "__main__":
	load_env()
	forced = os.environ.get("VIDEO_ENGINE_LLM")
	print(f"目前設定：{forced}（環境變數覆蓋）" if forced else "各階段預設：")
	if not forced:
		for st, spec in DEFAULT_BY_STAGE.items():
			print(f"  {st:8s} {spec}")
	for prov, models in KNOWN.items():
		key = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
			"google": "GOOGLE_API_KEY"}[prov]
		mark = "金鑰已設" if os.environ.get(key) else "缺金鑰"
		print(f"  {prov:10s} {mark:8s} {' / '.join(models)}")
