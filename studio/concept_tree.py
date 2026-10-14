"""重點清單 → 概念樹心智圖；節點只放短詞，說明收在點開後。"""
import re

from studio.handout import page_numbers
from studio.key_points import canonical_key_points
from studio.mindmap import canonical_mindmap


def first_sentences(text, count=2):
	parts = re.findall(r'[^。！？!?]+[。！？!?]?', text)
	return ''.join(parts[:count]).strip()


def build_concept_tree(key_points, material):
	value = canonical_key_points(key_points, material)
	pages = page_numbers(value)
	nodes = [{'id': 'root', 'label': value['title'], 'kind': 'concept', 'explanation': '',
		'source_quote': '', 'handout_page': None}]
	edges = []
	for point in value['points']:
		nodes.append({'id': point['id'], 'label': point['title'], 'kind': 'concept',
			'explanation': first_sentences(point['explanation']), 'source_quote': point['sources'][0],
			'handout_page': pages[point['id']]})
		edges.append({'from': point['parent_id'] or 'root', 'to': point['id'], 'label': '', 'source_quote': ''})
	return canonical_mindmap({'contract_version': '1.2', 'title': value['title'], 'layout': 'progressive',
		'root_id': 'root', 'nodes': nodes, 'edges': edges})
