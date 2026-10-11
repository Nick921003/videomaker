"""子行程共用的 marker、付費呼叫與安全用量紀錄。"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
import re

from video_engine.usage import capture_call, normalize_usage
from workbench.library import safe_path
from workbench.usage import unit_spent


class BudgetExceeded(RuntimeError):
	pass


def arguments(argv, description, *directories, quality=False):
	parser = argparse.ArgumentParser(description=description)
	for directory in directories:
		parser.add_argument(directory)
	parser.add_argument("--budget-usd", type=float, default=0.50)
	if quality:
		parser.add_argument('--quality',choices=('legacy','professional'),default='legacy')
	args = parser.parse_args(argv)
	if not math.isfinite(args.budget_usd) or args.budget_usd < 0:
		parser.error("--budget-usd 必須是有限的非負數")
	return args


def teaching_plan(directory, ledger, cap, complete_json=None):
	from functools import partial
	from video_engine import llm
	from workbench.teaching import get_plan
	os.environ.setdefault('VIDEO_ENGINE_LLM','google:gemini-3.8-flash')
	provider,model=llm.target('deck')
	complete_json=complete_json or partial(llm.complete_json,stage='deck')
	def complete(system,user,schema):
		guard_budget(directory,cap,'deck',system,user,schema)
		return captured(ledger,directory,'analysis','teaching_plan',complete_json,system,user,schema)
	return get_plan(directory,complete,configuration=f'{provider}:{model}')


def assert_current_source(directory, expected):
	from workbench.material import generation_material
	_,current=generation_material(directory)
	if current['content_version']!=expected['content_version'] or sorted(s['id'] for s in current['sources'])!=sorted(s['id'] for s in expected['sources']):
		raise ValueError('匯出期間教材來源版本已改變，保留上一份成品')


def marker(kind, value, detail=None):
	parts = ["@" + kind, value]
	if detail is not None:
		parts.append(" ".join(str(detail).split()))
	print(" ".join(parts), flush=True)


def append_usage(directory, calls, item, step):
	if not calls:
		return
	path = safe_path(directory, "usage.jsonl")
	with path.open("a", encoding="utf-8") as handle:
		for call in calls:
			row = {**call, "at": datetime.now(timezone.utc).isoformat(), "item": item, "step": step,
				"in": call["input_tokens"] or 0, "out": call["output_tokens"] or 0,
				"usd": call["estimated_cost_usd"]}
			handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def captured(ledger, directory, item, step, function, *args):
	before = ledger.summary()["call_count"]
	try:
		return capture_call(ledger, step, function, *args)
	finally:
		# 引用驗證或 JSON 解析失敗，已付費的呼叫仍需入帳。
		append_usage(directory, ledger.summary()["calls"][before:], item, step)


def guard_budget(directory, cap, stage, system, user, schema=None, *, provider=None, model=None):
	from video_engine import llm
	if provider is None:
		provider, model = llm.target(stage)
	input_tokens = len((system + user + json.dumps(schema, ensure_ascii=False)).encode("utf-8"))
	worst = normalize_usage(provider, model, {"in": input_tokens, "out": llm.output_limit(stage)})["estimated_cost_usd"]
	spent = unit_spent(directory)
	if spent >= cap or (worst is not None and spent + worst > cap):
		raise BudgetExceeded(f"已花 US${spent:.3f}，本次呼叫會超過上限 US${cap:.2f}")


def failure(exc, domain_error):
	chain = []
	current = exc
	while current is not None and current not in chain:
		chain.append(current)
		current = current.__cause__ or current.__context__
	for cause in chain:
		if isinstance(cause, BudgetExceeded):
			marker("error", "budget", str(cause))
			return 1
	if any(re.search(r"429|503|UNAVAILABLE|RESOURCE_EXHAUSTED|[Tt]ime ?out|timed out", str(cause)) for cause in chain):
		marker("error", "gemini_busy", "生成服務暫時忙碌或連線中斷")
		return 1
	if isinstance(exc, domain_error):
		detail = str(exc)
		if re.search(r"引用|引文|原文|來源證據|quote|source evidence", detail, re.IGNORECASE):
			code = "quote_mismatch"
		elif re.search(r"上限|超過|超出|最多接受", detail):
			code = "too_large"
		else:
			code = "unknown"
	else:
		code, detail = "unknown", "工作失敗，請檢查教材與本機檔案"
	marker("error", code, detail)
	return 1
