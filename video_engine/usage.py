"""供應商實際用量的安全紀錄；不保存教材、prompt 或憑證。"""

from contextvars import ContextVar
from copy import deepcopy
from datetime import date
import json
import math
import os
import re
import sys
import threading


_sink = ContextVar('video_usage_sink', default=None)
_stage = ContextVar('video_usage_stage', default=None)
PRICING_DATE = '2026-10-02'


def _count(value):
	return value if type(value) is int and value >= 0 else None


def _name(value):
	return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', value) else 'unknown'


def normalize_usage(provider, model, usage, on=None):
	usage = usage if isinstance(usage, dict) else {}
	provider, model = _name(provider), _name(model)
	input_count, output_count = _count(usage.get('in')), _count(usage.get('out'))
	thinking = _count(usage.get('thinking'))
	provider_total = _count(usage.get('total'))
	cache_read = _count(usage.get('cache_read')) or 0
	cache_write = _count(usage.get('cache_creation')) or 0
	cache_hour = min(cache_write, _count(usage.get('cache_creation_1h')) or 0)
	# Gemini未拆報思考時，以供應商合計減輸入取得含思考的輸出。
	inclusive_google_output = (provider == 'google' and provider_total is not None and
		input_count is not None and provider_total >= input_count and (thinking is None or output_count is None))
	if inclusive_google_output:
		output_count = provider_total - input_count
	known = input_count is not None and output_count is not None
	if known:
		if provider == 'google':
			if not inclusive_google_output:
				output_count += thinking or 0
			cache_read = min(cache_read, input_count)
			uncached = input_count - cache_read
		else:
			uncached = input_count
			if provider == 'anthropic':
				input_count += cache_read + cache_write
		cost = None
		if provider == 'anthropic' and model == 'claude-opus-5-5':
			cost = (uncached * 4 + output_count * 20 + cache_read * .20 +
				(cache_write - cache_hour) * 5 + cache_hour * 8) / 1_000_000
		elif provider == 'google' and model == 'gemini-3.8-flash':
			factor = 1 if (on or date.today()) <= date(2026,12,31) else 2
			cost = factor * (uncached * .75 + output_count * 3.75 + cache_read * .075) / 1_000_000
		elif provider == 'google' and model == 'gemini-4-argon':
			# 使用者 2026-10-14 告知與 Opus 5.5 同價；快取讀取比照 Flash 取輸入一成，官方價出來再校正。
			cost = (uncached * 4 + output_count * 20 + cache_read * .4) / 1_000_000
	else:
		cost = None
	total = provider_total if provider_total is not None else input_count + output_count if known else None
	if provider_total is not None and known and provider_total != input_count + output_count:
		cost = None
	return {'provider':provider, 'model':model, 'input_tokens':input_count,
		'output_tokens':output_count, 'thinking_tokens':thinking,
		'cache_read_input_tokens':cache_read, 'cache_creation_input_tokens':cache_write,
		'total_tokens':total,
		'estimated_cost_usd':cost, 'pricing_date':PRICING_DATE, 'reported':total is not None}


class UsageLedger:
	def __init__(self):
		self._calls = []
		self._lock = threading.RLock()

	def add(self, entry, stage=None):
		entry = entry if isinstance(entry, dict) else {}
		input_count, output_count = _count(entry.get('input_tokens')), _count(entry.get('output_tokens'))
		total = _count(entry.get('total_tokens'))
		reported = total is not None
		cost = entry.get('estimated_cost_usd')
		cost = cost if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0 and reported else None
		clean = {'provider':_name(entry.get('provider')), 'model':_name(entry.get('model')),
			'input_tokens':input_count, 'output_tokens':output_count,
			'total_tokens':total,
			'estimated_cost_usd':cost, 'reported':reported,
			'pricing_date':entry.get('pricing_date') if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(entry.get('pricing_date'))) else PRICING_DATE}
		for key in ('thinking_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'):
			clean[key] = _count(entry.get(key))
		with self._lock:
			self._calls.append(dict(clean, stage=_name(stage)))

	@classmethod
	def restore(cls, summary):
		ledger = cls()
		if isinstance(summary, dict) and isinstance(summary.get('calls'), list):
			for call in summary['calls']:
				if isinstance(call, dict):
					ledger.add(call, call.get('stage'))
		return ledger

	def summary(self):
		with self._lock:
			calls = deepcopy(self._calls)
		known = [call for call in calls if call['reported']]
		costs = [call['estimated_cost_usd'] for call in calls]
		def subtotal(key):
			values = [call[key] for call in known if call[key] is not None]
			return sum(values) if values else None
		return {'calls':calls, 'call_count':len(calls),
			'total_tokens':sum(call['total_tokens'] for call in known) if known else None,
			'input_tokens':subtotal('input_tokens'),
			'output_tokens':subtotal('output_tokens'),
			'thinking_tokens':subtotal('thinking_tokens'),
			'complete':bool(calls) and len(known) == len(calls),
			'estimated_cost_usd':sum(costs) if costs and all(cost is not None for cost in costs) else None,
			'currency':'USD', 'pricing_date':PRICING_DATE}


def report_usage(provider, model, usage):
	entry = normalize_usage(provider, model, usage)
	stage = _stage.get() or os.environ.get('VIDEO_ENGINE_USAGE_STAGE')
	sink = _sink.get()
	if sink is not None:
		sink.add(entry, stage)
	elif os.environ.get('VIDEO_ENGINE_USAGE_EVENTS') == '1':
		print(json.dumps({'event':'usage', 'stage':stage, 'usage':entry}, ensure_ascii=False),
			file=sys.stderr, flush=True)
	return usage


def capture_call(ledger, stage, function, *args, **kwargs):
	before = ledger.summary()['call_count']
	sink_token, stage_token = _sink.set(ledger), _stage.set(stage)
	try:
		result = function(*args, **kwargs)
		if ledger.summary()['call_count'] == before:
			meta = result[1] if isinstance(result, tuple) and len(result) == 2 else {}
			meta = meta if isinstance(meta, dict) else {}
			report_usage(meta.get('provider'), meta.get('model'), meta)
		return result
	except Exception:
		if ledger.summary()['call_count'] == before:
			report_usage(None, None, {})
		raise
	finally:
		_sink.reset(sink_token)
		_stage.reset(stage_token)
