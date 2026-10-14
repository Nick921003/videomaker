"""概念樹 1.3：重點底下長出定義，定義底下分例子與常見錯誤；內容直接長在樹上。"""
import hashlib
import json
import unittest
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

from studio.concept_tree import build_concept_tree
from studio.mindmap import MindmapError, canonical_mindmap, render_mindmap_svg
from tests.fixtures.key_points import sample_key_points
from tests.fixtures.teaching_quality import MATERIAL

V12 = Path(__file__).resolve().parent / 'fixtures/concept_tree_v12.json'
V12_MD5 = 'b22cfa52950aaf875b9343d0791b6114'


def children_of(tree):
	result = {node['id']: [] for node in tree['nodes']}
	for edge in tree['edges']:
		result[edge['from']].append(edge['to'])
	return result


class TestConceptTree(unittest.TestCase):
	def test_tree_shape(self):
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		self.assertEqual(tree['contract_version'], '1.3')
		labels = {node['id']: node['label'] for node in tree['nodes']}
		self.assertEqual(labels['root'], 'C 語言迴圈基礎')
		self.assertEqual(labels['three_parts'], '迴圈三要素')
		edges = {(edge['from'], edge['to']) for edge in tree['edges']}
		self.assertIn(('three_parts', 'choose'), edges)
		self.assertIn(('root', 'boundary'), edges)
		self.assertTrue(all(edge['label'] == '' and edge['source_quote'] == '' for edge in tree['edges']))
		pages = {node['id']: node['handout_page'] for node in tree['nodes'] if node['kind'] == 'concept'}
		self.assertEqual(pages, {'root': None, 'three_parts': 2, 'choose': 3, 'boundary': 4, 'infinite': 5})

	def test_detail_is_full_meaning(self):
		points = sample_key_points()
		for explanation in ('一。二！三？四', '沒有句號'):
			points['points'][0]['explanation'] = explanation
			tree = build_concept_tree(points, MATERIAL)
			meaning = next(node for node in tree['nodes'] if node['id'] == 'three_parts-meaning')
			self.assertEqual(meaning['label'], explanation)
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		node = next(node for node in tree['nodes'] if node['id'] == 'three_parts-meaning')
		self.assertEqual(node['label'], '括號裡三段各管一件事：從哪裡開始、什麼時候繼續、每一輪怎麼變。中間那段是「繼續的條件」，成立才會再跑一輪，不是「結束的條件」。')
		self.assertIn(node['source_quote'], MATERIAL)

	def test_svg_is_deterministic_and_carries_pages(self):
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		first, second = render_mindmap_svg(tree, MATERIAL), render_mindmap_svg(tree, MATERIAL)
		self.assertEqual(first, second)
		text = first.decode('utf-8')
		self.assertIn('data-contract-version="1.3"', text)
		self.assertIn('data-node-id="choose" data-node-kind="concept" data-handout-page="3"', text)

	def test_contract_rejects_fabricated_relations_and_bad_pages(self):
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		tree['edges'][0]['label'] = '包含'
		with self.assertRaises(MindmapError):
			canonical_mindmap(tree)
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		tree['nodes'][1]['handout_page'] = 1
		with self.assertRaises(MindmapError):
			canonical_mindmap(tree)
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		tree['nodes'][1]['explanation'] = ''
		tree['nodes'][1]['source_quote'] = ''
		with self.assertRaises(MindmapError):
			canonical_mindmap(tree)


class TestConceptTree13(unittest.TestCase):
	def setUp(self):
		self.points = sample_key_points()
		self.assertTrue(any(p['example'] and p['example']['kind'] == 'code' for p in self.points['points']))
		self.assertTrue(any(p['misconceptions'] for p in self.points['points']))
		self.tree = build_concept_tree(self.points, MATERIAL)
		self.nodes = {node['id']: node for node in self.tree['nodes']}
		self.children = children_of(self.tree)

	def test_point_grows_meaning_first_then_child_points(self):
		self.assertEqual(self.tree['contract_version'], '1.3')
		self.assertEqual(self.children['three_parts'][0], 'three_parts-meaning')
		self.assertEqual(self.children['three_parts'][1:], ['choose'])
		meaning = self.nodes['three_parts-meaning']
		self.assertEqual(meaning['kind'], 'meaning')
		point = next(p for p in self.points['points'] if p['id'] == 'three_parts')
		self.assertEqual(meaning['label'], point['explanation'])

	def test_meaning_splits_into_example_then_pitfalls(self):
		for point in self.points['points']:
			pid, kids = point['id'], self.children[f"{point['id']}-meaning"]
			expected = []
			if point['example'] is not None and point['example']['kind'] != 'none':
				expected.append(f'{pid}-example-group')
				self.assertEqual(self.nodes[f'{pid}-example-group']['label'], '例子')
				self.assertEqual(self.children[f'{pid}-example-group'], [f'{pid}-example'])
				self.assertEqual(self.nodes[f'{pid}-example']['label'], point['example']['content'].strip('\n'))
			if point['misconceptions']:
				expected.append(f'{pid}-pitfall-group')
				self.assertEqual(self.nodes[f'{pid}-pitfall-group']['label'], '常見錯誤')
				self.assertEqual(self.children[f'{pid}-pitfall-group'],
					[f'{pid}-pitfall-{n}' for n in range(1, len(point['misconceptions']) + 1)])
				first = point['misconceptions'][0]
				self.assertEqual(self.nodes[f'{pid}-pitfall-1']['label'],
					f"錯：{first['wrong']}\n為什麼：{first['why']}\n正確：{first['correct']}")
			self.assertEqual(kids, expected, pid)

	def test_missing_example_or_pitfalls_grow_nothing(self):
		points = sample_key_points()
		points['points'][0]['example'] = None
		points['points'][0]['misconceptions'] = []
		tree = build_concept_tree(points, MATERIAL)
		pid = points['points'][0]['id']
		self.assertEqual(children_of(tree)[f'{pid}-meaning'], [])
		ids = {node['id'] for node in tree['nodes']}
		self.assertNotIn(f'{pid}-example-group', ids)
		self.assertNotIn(f'{pid}-pitfall-group', ids)

	def test_quotes_pages_and_explanations(self):
		for node in self.tree['nodes']:
			self.assertEqual(node['explanation'], '')
			if node['id'] == 'root':
				self.assertIsNone(node['handout_page'])
				continue
			self.assertIn(node['source_quote'], MATERIAL)
			if node['kind'] == 'concept':
				self.assertIsInstance(node['handout_page'], int)
			else:
				self.assertIsNone(node['handout_page'])

	def test_contract_rejects_bad_13_nodes(self):
		bad = deepcopy(self.tree); bad['nodes'][1]['handout_page'] = None
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		bad = deepcopy(self.tree); next(n for n in bad['nodes'] if n['kind'] == 'meaning')['handout_page'] = 2
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		bad = deepcopy(self.tree); next(n for n in bad['nodes'] if n['kind'] == 'group')['label'] = '一' * 9
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		bad = deepcopy(self.tree); next(n for n in bad['nodes'] if n['kind'] == 'meaning')['explanation'] = '多的'
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		bad = deepcopy(self.tree); bad['edges'][0]['label'] = '包含'
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		v12 = json.loads(V12.read_text(encoding='utf-8'))
		next(n for n in v12['nodes'] if n['id'] != 'root')['kind'] = 'group'
		with self.assertRaises(MindmapError): canonical_mindmap(v12)

	def test_svg_is_deterministic_inside_canvas_without_overlap(self):
		first = render_mindmap_svg(self.tree, MATERIAL)
		self.assertEqual(first, render_mindmap_svg(self.tree, MATERIAL))
		text = first.decode('utf-8')
		self.assertIn('data-contract-version="1.3"', text)
		self.assertIn('data-node-id="three_parts-example" data-node-kind="example"', text)
		self.assertIn('Noto Sans Mono CJK TC', text)
		root = ET.fromstring(first)
		ns = '{http://www.w3.org/2000/svg}'
		width, height = float(root.get('width')), float(root.get('height'))
		cards = {card.get('data-node-id'): card for card in root.findall(f'{ns}g')}
		boxes = [tuple(float(card.find(f'{ns}rect').get(key)) for key in ('x', 'y', 'width', 'height'))
			for card in cards.values()]
		self.assertEqual(len(boxes), len(self.tree['nodes']))
		for x, y, w, h in boxes:
			self.assertTrue(0 <= x and 0 <= y and x + w <= width and y + h <= height)
		for i, (x1, y1, w1, h1) in enumerate(boxes):
			for x2, y2, w2, h2 in boxes[i + 1:]:
				self.assertFalse(x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1)
		for node in self.tree['nodes']:
			if node['kind'] == 'example':
				lines = node['label'].count('\n') + 1
				self.assertGreaterEqual(len(cards[node['id']].findall(f'{ns}text')), lines)

	def test_code_and_group_svg_attributes(self):
		points = sample_key_points()
		points['points'][0]['example']['content'] = 'for (i = 0;\n\n     i < 5; i++)\n}'
		root = ET.fromstring(render_mindmap_svg(build_concept_tree(points, MATERIAL), MATERIAL))
		ns = '{http://www.w3.org/2000/svg}'
		card = root.find(f'{ns}g[@data-node-id="three_parts-example"]')
		lines = card.findall(f'{ns}text')
		self.assertEqual([line.text or '' for line in lines], ['for (i = 0;', '', '     i < 5; i++)', '}'])
		for line in lines:
			self.assertEqual(line.get('font-family'), 'Noto Sans Mono CJK TC,monospace')
			self.assertEqual(line.get('font-size'), '18')
			self.assertEqual(line.get('{http://www.w3.org/XML/1998/namespace}space'), 'preserve')
		self.assertEqual([float(line.get('y')) - float(lines[0].get('y')) for line in lines], [0, 24, 48, 72])
		for card in root.findall(f'{ns}g[@data-node-kind="group"]'):
			rect = card.find(f'{ns}rect')
			self.assertEqual((rect.get('height'), rect.get('rx'), rect.get('fill')), ('48', '24', '#fffaf2'))

	def test_contract_limits_and_empty_fields(self):
		for kind, maximum in (('concept', 24), ('meaning', 150), ('group', 8), ('example', 400), ('pitfall', 260)):
			for length in (maximum, maximum + 1):
				bad = deepcopy(self.tree)
				next(n for n in bad['nodes'] if n['kind'] == kind and n['id'] != 'root')['label'] = '字' * length
				with self.subTest(kind=kind, length=length):
					if length == maximum: self.assertEqual(canonical_mindmap(bad), bad)
					else:
						with self.assertRaises(MindmapError): canonical_mindmap(bad)
		for index, key, value in ((0, 'label', '字' * 121), (0, 'source_quote', '原文'),
			(0, 'explanation', '多的'), (1, 'source_quote', ''), (1, 'source_quote', '字' * 1001),
			(1, 'handout_page', True), (1, 'handout_page', 1), (1, 'handout_page', 2.0),
			(1, 'kind', 'usage')):
			bad = deepcopy(self.tree); bad['nodes'][index][key] = value
			with self.subTest(index=index, key=key, value=value), self.assertRaises(MindmapError):
				canonical_mindmap(bad)
		for node in self.tree['nodes']:
			bad = deepcopy(self.tree)
			next(n for n in bad['nodes'] if n['id'] == node['id'])['explanation'] = None
			with self.subTest(node=node['id']), self.assertRaises(MindmapError): canonical_mindmap(bad)

	def test_long_point_ids_remain_unique_with_derived_suffixes(self):
		points = sample_key_points()
		pid = 'a' * 24
		points['points'][0]['id'] = pid
		points['points'][1]['parent_id'] = pid
		tree = build_concept_tree(points, MATERIAL)
		ids = [node['id'] for node in tree['nodes']]
		self.assertEqual(len(ids), len(set(ids)))
		self.assertIn(f'{pid}-example-group', ids)
		self.assertIn(f'{pid}-pitfall-group', ids)
		self.assertIn(f'data-node-id="{pid}-example-group"', render_mindmap_svg(tree, MATERIAL).decode())

	def test_v12_svg_bytes_unchanged(self):
		v12 = json.loads(V12.read_text(encoding='utf-8'))
		self.assertEqual(hashlib.md5(render_mindmap_svg(v12, MATERIAL)).hexdigest(), V12_MD5)


if __name__ == '__main__':
	unittest.main()
