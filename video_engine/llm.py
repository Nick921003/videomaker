#!/usr/bin/env python3
"""LLM 轉接層：管線裡兩處需要 LLM 的步驟共用，換供應商只改一個設定。

設定（環境變數或專案根目錄的 .env）：
	VIDEO_ENGINE_LLM=anthropic:claude-opus-5      預設
	VIDEO_ENGINE_LLM=openai:gpt-5.6-terra
	VIDEO_ENGINE_LLM=google:gemini-3.7-flash
	VIDEO_ENGINE_LLM=openai-compatible:<model>    本機 vLLM／Ollama，另設 LLM_BASE_URL

各家用自家官方 SDK，延遲載入——只有真的選到才需要裝。
"""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 預設組合：結構化只跑一次、影響整份骨架，用最強的；編排每頁跑一次，用便宜快的
DEFAULT_TARGET = "anthropic:claude-opus-5"
DEFAULT_BY_STAGE = {
	"lesson": "anthropic:claude-opus-5",
	"actions": "google:gemini-3.7-flash",
}

# 各供應商目前的主力型號，供 --list 顯示與挑選（2026-08 查證）
KNOWN = {
	"anthropic": ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"],
	"openai": ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
	"google": ["gemini-3.7-flash", "gemini-3.1-pro-preview", "gemini-3.5-flash-lite"],
}


def load_env(path=None):
	"""讀專案根目錄的 .env，已存在的環境變數優先，不覆蓋"""
	path = path or os.path.join(BASE_DIR, ".env")
	if not os.path.exists(path):
		return
	for line in open(path, encoding="utf-8"):
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
	resp = client.messages.create(**kwargs)
	if resp.stop_reason == "refusal":
		raise RuntimeError(f"模型拒絕回應：{getattr(resp.stop_details, 'category', '')}")
	text = next((b.text for b in resp.content if b.type == "text"), "")
	usage = {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}
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
	resp = client.chat.completions.create(**kwargs)
	text = resp.choices[0].message.content or ""
	usage = {"in": resp.usage.prompt_tokens, "out": resp.usage.completion_tokens}
	return _first_json(text), usage


def _google(model, system, user, schema, max_tokens, effort):
	from google import genai
	from google.genai import types

	client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
	cfg = types.GenerateContentConfig(
		system_instruction=system,
		max_output_tokens=max_tokens,
		response_mime_type="application/json",
		# 我們不用函式呼叫，關掉才不會每次都印警告
		automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
	)
	resp = client.models.generate_content(model=model, contents=user, config=cfg)
	usage = {"in": resp.usage_metadata.prompt_token_count,
		"out": resp.usage_metadata.candidates_token_count}
	return _first_json(resp.text), usage


def complete_json(system, user, schema=None, max_tokens=16000, effort="high", stage=None):
	"""要一份 JSON 回來。回傳 (資料, {供應商, 型號, token 用量})"""
	provider, model = target(stage)
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
