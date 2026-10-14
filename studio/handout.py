"""重點清單 → 講義型簡報；純轉換，不呼叫模型。"""
from copy import deepcopy

from studio.deck_contracts import canonical_deck
from studio.key_points import canonical_key_points


def page_numbers(key_points):
	"""封面是第 1 頁，重點依序從第 2 頁開始；心智圖連回講義用這個頁碼。"""
	return {point['id']: number for number, point in enumerate(key_points['points'], start=2)}


def build_handout(key_points, material):
	value = canonical_key_points(key_points, material)
	slides = [{'slide_id': 'cover', 'kind': 'cover', 'title': value['title'],
		'objectives': [objective['text'] for objective in value['objectives']]}]
	for point in value['points']:
		slides.append({'slide_id': point['id'], 'kind': 'point', 'question': point['question'],
			'title': point['title'], 'explanation': point['explanation'], 'example': deepcopy(point['example']),
			'misconceptions': deepcopy(point['misconceptions']), 'sources': list(point['sources'])})
	items = [{'point_title': point['title'], **mistake} for point in value['points'] for mistake in point['misconceptions']]
	if items:
		slides.append({'slide_id': 'mistakes', 'kind': 'mistakes', 'items': items})
	return canonical_deck({'contract_version': '1.3', 'title': value['title'], 'slides': slides})
