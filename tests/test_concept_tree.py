"""概念樹：節點只有短詞；說明與出處收在節點資料裡；不編造關係；輸出決定。"""
import unittest

from studio.concept_tree import build_concept_tree, first_sentences
from studio.mindmap import MindmapError, canonical_mindmap, render_mindmap_svg
from tests.fixtures.key_points import sample_key_points
from tests.fixtures.teaching_quality import MATERIAL


class TestConceptTree(unittest.TestCase):
	def test_tree_shape(self):
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		self.assertEqual(tree['contract_version'], '1.2')
		labels = {node['id']: node['label'] for node in tree['nodes']}
		self.assertEqual(labels['root'], 'C 語言迴圈基礎')
		self.assertEqual(labels['three_parts'], '迴圈三要素')
		edges = {(edge['from'], edge['to']) for edge in tree['edges']}
		self.assertIn(('three_parts', 'choose'), edges)
		self.assertIn(('root', 'boundary'), edges)
		self.assertTrue(all(edge['label'] == '' and edge['source_quote'] == '' for edge in tree['edges']))
		pages = {node['id']: node['handout_page'] for node in tree['nodes']}
		self.assertEqual(pages, {'root': None, 'three_parts': 2, 'choose': 3, 'boundary': 4, 'infinite': 5})

	def test_detail_is_first_two_sentences(self):
		self.assertEqual(first_sentences('一。二！三？四'), '一。二！')
		self.assertEqual(first_sentences('沒有句號'), '沒有句號')
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		node = next(node for node in tree['nodes'] if node['id'] == 'three_parts')
		self.assertEqual(node['explanation'], '括號裡三段各管一件事：從哪裡開始、什麼時候繼續、每一輪怎麼變。中間那段是「繼續的條件」，成立才會再跑一輪，不是「結束的條件」。')
		self.assertIn(node['source_quote'], MATERIAL)

	def test_svg_is_deterministic_and_carries_pages(self):
		tree = build_concept_tree(sample_key_points(), MATERIAL)
		first, second = render_mindmap_svg(tree, MATERIAL), render_mindmap_svg(tree, MATERIAL)
		self.assertEqual(first, second)
		text = first.decode('utf-8')
		self.assertIn('data-contract-version="1.2"', text)
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


if __name__ == '__main__':
	unittest.main()
