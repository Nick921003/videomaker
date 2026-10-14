from copy import deepcopy
import json
import unittest

from video_engine.paper_contract import PaperError, canonical_board, build_paper_board


WATER_SOURCE = '水受熱後蒸發成水氣。水氣冷卻凝結成雲。雲中的水落下成雨。'
CODE_SOURCE = '累加每個數字。\nint sum = 0;\nfor (int i = 1; i <= 3; i++) {\n    sum += i;\n}\n印出累加結果。'


def water_board():
	quotes = ['水受熱後蒸發成水氣。', '水氣冷卻凝結成雲。', '雲中的水落下成雨。']
	return {'contract_version': '1.0', 'title': '水循環', 'objects': [
		{'id': 'water', 'kind': 'cells', 'label': '水的狀態', 'values': ['水']}],
		'scenes': [{'id': f's{n}', 'title': '狀態變化', 'source_quote': quote,
			'steps': [{'id': f'b{n}', 'speech': '我們先觀察水的狀態，再一起理解這個變化。',
				'caption': '水的變化', 'focus': 'water', 'visible': ['water'],
				'updates': [{'target': 'water', 'values': [value]}], 'code_line': -1}]}
			for n, (quote, value) in enumerate(zip(quotes, ['水氣', '雲', '雨']), 1)]}


def code_board():
	board = water_board()
	board['title'] = '累加'
	board['objects'] = [{'id': 'program', 'kind': 'code', 'label': '程式',
		'values': ['int sum = 0;', 'for (int i = 1; i <= 3; i++) {', 'sum += i;', '}']}]
	for scene in board['scenes']:
		scene['source_quote'] = '累加每個數字。'
		step = scene['steps'][0]
		step.update(focus='program', visible=['program'], updates=[], code_line=2)
	return board


class PaperContractTests(unittest.TestCase):
	def test_valid_domains_and_deepcopy(self):
		for board, source in [(water_board(), WATER_SOURCE), (code_board(), CODE_SOURCE)]:
			result = canonical_board(board, source)
			self.assertEqual(board, result)
			result['objects'][0]['values'][0] = 'changed'
			self.assertNotEqual(board, result)

	def test_closed_structure_references_and_bounds(self):
		def mutate(board, case):
			step = board['scenes'][0]['steps'][0]
			if case == 'field': board['objects'][0]['x'] = 5
			elif case == 'duplicate': board['scenes'][0]['id'] = 'water'
			elif case == 'speech': step['speech'] = '短'
			elif case == 'overflow': board['objects'][0]['values'] = ['字' * 13]
			elif case == 'quote': board['scenes'][0]['source_quote'] = '不存在於教材。'
			elif case == 'focus': step['focus'] = 'missing'
			elif case == 'hidden': step['visible'] = []
			elif case == 'line': step['code_line'] = 0
			elif case == 'boolean': step['code_line'] = False
			elif case == 'updates': step['updates'] *= 2
			elif case == 'steps': board['scenes'][0]['steps'] *= 5
			elif case == 'scenes': board['scenes'] = board['scenes'][:2]
		for case in ['field', 'duplicate', 'speech', 'overflow', 'quote', 'focus', 'hidden', 'line', 'boolean', 'updates', 'steps', 'scenes']:
			with self.subTest(case=case):
				board = water_board()
				mutate(board, case)
				with self.assertRaises(PaperError): canonical_board(board, WATER_SOURCE)

	def test_code_must_match_source_line_and_cannot_be_updated(self):
		for change in ['invented', 'update', 'line']:
			board = code_board()
			if change == 'invented': board['objects'][0]['values'][0] = 'system("fake");'
			elif change == 'update': board['scenes'][0]['steps'][0]['updates'] = [{'target': 'program', 'values': ['int sum = 0;']}]
			else: board['scenes'][0]['steps'][0]['code_line'] = 4
			with self.assertRaises(PaperError): canonical_board(board, CODE_SOURCE)

	def test_builder_calls_once_and_supplies_source_and_semantic_schema(self):
		calls = []
		def complete(system, user, schema):
			calls.append((system, json.loads(user), schema))
			return water_board(), {'in': 10, 'out': 20}
		self.assertEqual(build_paper_board(WATER_SOURCE, '', 60, complete), water_board())
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0][1]['material'], WATER_SOURCE)
		self.assertFalse(calls[0][2]['additionalProperties'])
		def bad(*args):
			calls.append(args)
			return {}, {}
		with self.assertRaises(PaperError): build_paper_board(WATER_SOURCE, '', 60, bad)
		self.assertEqual(len(calls), 2)

	def test_builder_passes_duration_range_to_model(self):
		calls=[]
		def complete(system,user,schema):
			calls.append(json.loads(user))
			return water_board(),{}
		build_paper_board(WATER_SOURCE,'重點清楚',240,complete,
			duration_range={'min_seconds':180,'max_seconds':300})
		self.assertEqual(calls[0]['duration_range'],{'min_seconds':180,'max_seconds':300})

	def test_flow_and_semantic_motion_validate_current_state(self):
		board=water_board()
		board['objects'][0]['kind']='flow'
		board['objects'].append({'id':'source','kind':'cells','label':'來源','values':['水','水氣']})
		first=board['scenes'][0]['steps'][0]
		first.update(motion='transfer',source='source',source_index=1,focus_index=0,visible=['water','source'])
		second=board['scenes'][1]['steps'][0]
		second.update(motion='scan',focus_index=1)
		second['updates']=[{'target':'water','values':['水氣','雲']}]
		self.assertEqual(canonical_board(board,WATER_SOURCE),board)
		for field,value in [('source_index',True),('source_index',2),('source_index',-1),('focus_index',1),('motion','unknown'),('source','missing')]:
			bad=deepcopy(board);bad['scenes'][0]['steps'][0][field]=value
			with self.subTest(field=field,value=value),self.assertRaises(PaperError):canonical_board(bad,WATER_SOURCE)
		bad=deepcopy(board);del bad['scenes'][0]['steps'][0]['source_index']
		with self.assertRaises(PaperError):canonical_board(bad,WATER_SOURCE)
		bad=deepcopy(board);bad['scenes'][2]['steps'][0]['updates']=[];bad['scenes'][2]['steps'][0]['focus_index']=1
		self.assertEqual(canonical_board(bad,WATER_SOURCE),bad)
		bad['scenes'][2]['steps'][0]['focus_index']=2
		with self.assertRaises(PaperError):canonical_board(bad,WATER_SOURCE)

	def test_motion_rejects_code_source_and_source_fields_without_transfer(self):
		board=code_board();step=board['scenes'][0]['steps'][0]
		for change in [{'motion':'transfer','source':'program','source_index':0}, {'source':'program'}, {'source_index':0}]:
			bad=deepcopy(board);bad['scenes'][0]['steps'][0].update(change)
			with self.subTest(change=change),self.assertRaises(PaperError):canonical_board(bad,CODE_SOURCE)

	def test_scan_output_is_an_explicit_visible_prefix_relation(self):
		board=water_board();board['objects'][0]['values']=['A','l','i','c','e','STOP']
		board['objects'].append({'id':'output','kind':'text','label':'輸出','values':['尚未輸出']})
		step=board['scenes'][0]['steps'][0]
		step.update(motion='scan',focus_index=5,scan_output='output',visible=['water','output'],updates=[{'target':'output','values':['Alice']}])
		self.assertEqual(canonical_board(board,WATER_SOURCE),board)
		for change in [{'scan_include_stop':True},{'scan_include_stop':1},{'scan_output':'missing'},{'motion':'reveal'}]:
			bad=deepcopy(board);bad['scenes'][0]['steps'][0].update(change)
			with self.subTest(change=change),self.assertRaises(PaperError):canonical_board(bad,WATER_SOURCE)
		bad=deepcopy(board);bad['scenes'][0]['steps'][0]['scan_include_stop']=True;bad['scenes'][0]['steps'][0]['updates'][0]['values']=['AliceSTOP']
		self.assertEqual(canonical_board(bad,WATER_SOURCE),bad)
