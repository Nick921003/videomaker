import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from video_engine import llm


class TestUsage(unittest.TestCase):
	def test_gemini_thinking_and_claude_thinking_are_counted_once(self):
		from video_engine.usage import normalize_usage
		google = normalize_usage('google', 'gemini-3.8-flash', {'in':779, 'out':805, 'thinking':513})
		self.assertEqual(google['total_tokens'], 2097)
		self.assertEqual(google['output_tokens'], 1318)
		self.assertAlmostEqual(google['estimated_cost_usd'], .00552675)
		claude = normalize_usage('anthropic', 'claude-opus-5-5', {'in':1423, 'out':2372, 'thinking':1866})
		self.assertEqual(claude['total_tokens'], 3795)
		self.assertAlmostEqual(claude['estimated_cost_usd'], .053132)

	def test_cache_costs_and_expiring_google_introductory_rate(self):
		from datetime import date
		from video_engine.usage import normalize_usage
		entry = normalize_usage('anthropic', 'claude-opus-5-5', {'in':100, 'out':200,
			'cache_read':300, 'cache_creation':400, 'cache_creation_1h':100})
		self.assertEqual(entry['input_tokens'], 800)
		self.assertEqual(entry['total_tokens'], 1000)
		self.assertAlmostEqual(entry['estimated_cost_usd'], .00676)
		entry = normalize_usage('google', 'gemini-3.8-flash', {'in':100, 'out':200, 'cache_read':50}, on=date(2027,1,1))
		self.assertEqual(entry['total_tokens'], 300)
		self.assertAlmostEqual(entry['estimated_cost_usd'], .0015825)

	def test_missing_usage_and_unknown_model_are_not_free(self):
		from video_engine.usage import UsageLedger, capture_call
		ledger = UsageLedger()
		self.assertIsNone(ledger.summary()['total_tokens'])
		capture_call(ledger, 'deck', lambda: ({}, {'provider':'custom', 'model':'unknown', 'in':10, 'out':20}))
		self.assertEqual(ledger.summary()['total_tokens'], 30)
		self.assertIsNone(ledger.summary()['estimated_cost_usd'])
		with self.assertRaises(RuntimeError):
			capture_call(ledger, 'deck', lambda: (_ for _ in ()).throw(RuntimeError('secret')))
		self.assertFalse(ledger.summary()['complete'])
		self.assertNotIn('secret', json.dumps(ledger.summary()))

	def test_missing_sdk_usage_still_emits_unknown_call_and_unknown_components(self):
		from io import StringIO
		from video_engine.usage import UsageLedger, capture_call
		response = SimpleNamespace(stop_reason='end_turn', model='claude-opus-5-5', usage=None,
			content=[SimpleNamespace(type='text',text='{}')])
		client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_:response))
		output=StringIO()
		with patch('anthropic.Anthropic',return_value=client), patch('sys.stderr',output), \
			patch.dict(os.environ, {'VIDEO_ENGINE_USAGE_EVENTS':'1'}):
			llm._anthropic('claude-opus-5-5','s','u',None,100,'medium')
		self.assertFalse(json.loads(output.getvalue())['usage']['reported'])
		ledger = UsageLedger()
		capture_call(ledger,'deck',lambda:({},{}))
		self.assertIsNone(ledger.summary()['input_tokens'])
		self.assertIsNone(ledger.summary()['output_tokens'])

	def test_provider_total_survives_missing_breakdown(self):
		from video_engine.usage import normalize_usage, UsageLedger
		entry=normalize_usage('google','gemini-3.8-flash',{'total':100})
		ledger=UsageLedger()
		ledger.add(entry,'ingest')
		self.assertEqual(ledger.summary()['total_tokens'],100)
		self.assertIsNone(ledger.summary()['estimated_cost_usd'])

	def test_google_total_supplies_output_when_thinking_breakdown_is_absent(self):
		from video_engine.usage import normalize_usage
		entry=normalize_usage('google','gemini-3.8-flash',{'in':779,'out':805,'total':2097})
		self.assertEqual(entry['output_tokens'],1318)
		self.assertIsNone(entry['thinking_tokens'])
		self.assertAlmostEqual(entry['estimated_cost_usd'],.00552675)

	def test_isolated_ledgers_and_fallback_are_not_double_counted(self):
		from video_engine.usage import UsageLedger, capture_call, report_usage
		one, two = UsageLedger(), UsageLedger()
		def complete():
			report_usage('anthropic', 'claude-opus-5-5', {'in':10, 'out':20})
			return {}, {'provider':'anthropic', 'model':'claude-opus-5-5', 'in':10, 'out':20}
		capture_call(one, 'deck', complete)
		capture_call(two, 'mindmap', lambda: ({}, {'in':1,'out':2}))
		self.assertEqual(one.summary()['call_count'], 1)
		self.assertEqual(one.summary()['total_tokens'], 30)
		self.assertEqual(two.summary()['total_tokens'], 3)

	def test_claude_truncation_and_invalid_json_keep_usage(self):
		from video_engine.usage import UsageLedger, capture_call
		for stop, value in [('max_tokens',''), ('end_turn','bad json')]:
			with self.subTest(stop=stop):
				response = SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type='text',text=value)],
					usage=SimpleNamespace(input_tokens=11,output_tokens=22))
				client = SimpleNamespace(messages=SimpleNamespace(create=lambda **_:response))
				ledger = UsageLedger()
				with patch('anthropic.Anthropic',return_value=client), self.assertRaises((RuntimeError,ValueError)):
					capture_call(ledger, 'deck', llm._anthropic, 'claude-opus-5-5','s','u',None,100,'medium')
				self.assertEqual(ledger.summary()['total_tokens'],33)
				self.assertEqual(ledger.summary()['call_count'],1)

	def test_usage_event_contains_only_safe_usage(self):
		from io import StringIO
		from video_engine.usage import report_usage
		output = StringIO()
		with patch.dict(os.environ, {'VIDEO_ENGINE_USAGE_EVENTS':'1','VIDEO_ENGINE_USAGE_STAGE':'actions'}), patch('sys.stderr',output):
			report_usage('google','gemini-3.8-flash',{'in':2,'out':3,'thinking':4,'prompt':'secret'})
		event=json.loads(output.getvalue())
		self.assertEqual(event['event'],'usage')
		self.assertEqual(event['usage']['total_tokens'],9)
		self.assertNotIn('secret',output.getvalue())

	def test_google_real_adapter_captures_thinking_before_invalid_json(self):
		from video_engine.usage import UsageLedger, capture_call
		response = SimpleNamespace(text='invalid', model_version='gemini-3.8-flash',
			usage_metadata=SimpleNamespace(prompt_token_count=779,candidates_token_count=805,
				thoughts_token_count=513,total_token_count=2097))
		client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_:response))
		ledger = UsageLedger()
		with patch.dict(os.environ, {'GOOGLE_API_KEY':'fake'}), patch('google.genai.Client',return_value=client):
			with self.assertRaises(ValueError):
				capture_call(ledger,'ingest',llm._google,'gemini-3.8-flash','s','u',None,100,'high')
		self.assertEqual(ledger.summary()['total_tokens'],2097)
		self.assertEqual(ledger.summary()['call_count'],1)

	def test_video_usage_reaches_server_through_real_subprocess(self):
		from pathlib import Path
		import tempfile
		import serve
		from jobstate import Job
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			stage = root/'fake_stage.py'
			stage.write_text("from video_engine.usage import report_usage\n"
				"report_usage('google','gemini-3.8-flash',{'in':10,'out':20,'thinking':3})\n"
				"report_usage('google','gemini-3.8-flash',{'in':1,'out':2,'thinking':3})\n")
			runner = root/'runner.py'
			runner.write_text("from video_engine import run\n"
				"run.JSON_EVENTS=True\n"
				f"run.HERE={str(root)!r}\n"
				"run.run('fake_stage.py',[],'offline',stage='actions')\n")
			with patch.dict(os.environ, {'PYTHONPATH':str(Path(serve.HERE))}), patch.object(serve,'RUN',str(runner)):
				job=Job(str(root/'material.md'),str(root/'out'),60,serve.real_runner(str(root/'material.md'),60))
				self.assertTrue(job._pump('actions','actions'))
			self.assertEqual(job.usage.summary()['total_tokens'],39)
			self.assertEqual(job.usage.summary()['call_count'],2)
			self.assertEqual([event['event'] for event in job.events],['stage_start','stage_end'])
