"""重點清單 → 概念樹；重點底下長出定義，定義底下再分例子與常見錯誤，內容直接是節點。"""
from studio.handout import page_numbers
from studio.key_points import canonical_key_points
from studio.mindmap import canonical_mindmap


def _pitfall(mistake):
	return f"錯：{mistake['wrong']}\n為什麼：{mistake['why']}\n正確：{mistake['correct']}"


def build_concept_tree(key_points, material):
	value = canonical_key_points(key_points, material)
	pages = page_numbers(value)
	nodes = [{'id': 'root', 'label': value['title'], 'kind': 'concept', 'explanation': '',
		'source_quote': '', 'handout_page': None}]
	edges = []
	def add(node_id, parent, label, kind, quote, page=None):
		nodes.append({'id': node_id, 'label': label, 'kind': kind, 'explanation': '',
			'source_quote': quote, 'handout_page': page})
		edges.append({'from': parent, 'to': node_id, 'label': '', 'source_quote': ''})
	for point in value['points']:
		pid, quote = point['id'], point['sources'][0]
		add(pid, point['parent_id'] or 'root', point['title'], 'concept', quote, pages[pid])
		# 定義先加，子重點的邊排在後面，展開時定義永遠是第一個分支。
		meaning = f'{pid}-meaning'
		add(meaning, pid, point['explanation'], 'meaning', quote)
		example = point['example']
		if example is not None and example['kind'] != 'none':
			add(f'{pid}-example-group', meaning, '例子', 'group', quote)
			add(f'{pid}-example', f'{pid}-example-group', example['content'].strip('\n'), 'example', quote)
		if point['misconceptions']:
			add(f'{pid}-pitfall-group', meaning, '常見錯誤', 'group', quote)
			for number, mistake in enumerate(point['misconceptions'], start=1):
				add(f'{pid}-pitfall-{number}', f'{pid}-pitfall-group', _pitfall(mistake), 'pitfall', quote)
	return canonical_mindmap({'contract_version': '1.3', 'title': value['title'], 'layout': 'progressive',
		'root_id': 'root', 'nodes': nodes, 'edges': edges})
