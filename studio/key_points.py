"""與形式無關的重點清單：只記學什麼、為什麼、出處，不帶任何畫面或旁白。"""
from copy import deepcopy
import hashlib
import json
import re


CONTRACT_VERSION = '1.0'
TYPES = ('concept', 'process', 'compare', 'mistake', 'code_trace', 'data')
EXAMPLE_KINDS = ('code', 'formula', 'text')
LIMITS = {'title': 12, 'question': 60, 'explanation': 150, 'objective': 80,
	'misconception': 80, 'example_chars': 400, 'example_lines': 12}
RESERVED_IDS = ('root', 'cover', 'mistakes')
_ID = re.compile(r'[a-z][a-z0-9_]{0,23}')
# 只擋「X 是什麼」這類短泛問；「這個括號的用處是什麼？」帶了具體對象，要放行。
_GENERIC = (re.compile(r'^什麼是'), re.compile(r'^[^，,的]{1,10}是什麼[？?]?$'))
_TOP = ('contract_version', 'content_version', 'title', 'structure', 'status', 'objectives', 'points')
_OBJECTIVE = ('id', 'text', 'inferred', 'sources')
_POINT = ('id', 'title', 'question', 'type', 'objectives', 'explanation', 'example',
	'misconceptions', 'parent_id', 'sources')


class KeyPointsError(ValueError):
	def __init__(self, problems):
		self.problems = list(problems)
		super().__init__('重點清單不合格：' + '；'.join(self.problems))


def _normalized(text):
	return re.sub(r'\s+', ' ', text).strip()


def problems(value, material):
	"""一次列出所有不合格原因，重試時模型才能一併修正。"""
	found = []

	def text(item, maximum, where):
		if not isinstance(item, str) or not item.strip():
			found.append(f'{where} 必須是非空文字')
			return False
		if len(item) > maximum:
			found.append(f'{where} 超過 {maximum} 字（目前 {len(item)} 字）')
			return False
		return True

	def fields(item, names, where):
		if not isinstance(item, dict):
			found.append(f'{where} 必須是物件')
			return False
		extra, missing = sorted(set(item) - set(names)), sorted(set(names) - set(item))
		if extra:
			found.append(f'{where} 欄位不符：不得有 {extra}')
		if missing:
			found.append(f'{where} 欄位不符：缺少 {missing}')
		return not extra and not missing

	if not isinstance(material, str) or not material.strip():
		return ['教材內容為空']
	if not isinstance(value, dict):
		return ['重點清單必須是物件']
	if set(value) != set(_TOP):
		return [f'頂層欄位不符：缺少 {sorted(set(_TOP) - set(value))}，多出 {sorted(set(value) - set(_TOP))}']
	source = _normalized(material)

	def sources(items, minimum, maximum, where):
		if not isinstance(items, list) or not minimum <= len(items) <= maximum:
			found.append(f'{where} 數量須為 {minimum}–{maximum}')
			return
		for index, quote in enumerate(items):
			if not isinstance(quote, str) or not quote.strip() or _normalized(quote) not in source:
				found.append(f'{where}[{index}] 的引文不在教材原文中')

	if value['contract_version'] != CONTRACT_VERSION:
		found.append('contract_version 不支援')
	if value['content_version'] != hashlib.sha256(material.encode('utf-8')).hexdigest():
		found.append('content_version 與教材版本不一致')
	text(value['title'], 120, 'title')
	if value['structure'] not in ('material', 'inferred'):
		found.append('structure 必須是 material 或 inferred')
	if value['status'] not in ('ready', 'needs_review'):
		found.append('status 必須是 ready 或 needs_review')
	elif value['structure'] == 'material' and value['status'] != 'ready':
		found.append('structure 為 material 時 status 必須是 ready')

	objectives, objective_ids = value['objectives'], []
	if not isinstance(objectives, list) or not 1 <= len(objectives) <= 6:
		found.append('學習目標數量須為 1–6')
		objectives = []
	for index, item in enumerate(objectives):
		where = f'objectives[{index}]'
		if not fields(item, _OBJECTIVE, where):
			continue
		if not isinstance(item['id'], str) or not _ID.fullmatch(item['id']) or item['id'] in objective_ids:
			found.append(f'{where}.id 不合法或重複')
		objective_ids.append(item['id'])
		text(item['text'], LIMITS['objective'], f'{where}.text')
		if type(item['inferred']) is not bool:
			found.append(f'{where}.inferred 必須是布林值')
		elif item['inferred'] != (value['structure'] == 'inferred'):
			found.append(f'{where}.inferred 與 structure 不一致')
		sources(item['sources'], 1, 2, f'{where}.sources')

	points, seen, covered, total_mistakes = value['points'], [], set(), 0
	if not isinstance(points, list) or not 3 <= len(points) <= 8:
		found.append('重點數量須為 3–8')
		points = []
	for index, point in enumerate(points):
		where = f'points[{index}]'
		if not fields(point, _POINT, where):
			continue
		pid = point['id']
		if not isinstance(pid, str) or not _ID.fullmatch(pid) or pid in RESERVED_IDS or pid in seen:
			found.append(f'{where}.id 不合法或重複')
		text(point['title'], LIMITS['title'], f'{where}.title')
		if (text(point['question'], LIMITS['question'], f'{where}.question')
			and any(pattern.search(point['question'].strip()) for pattern in _GENERIC)):
			found.append(f'{where}.question 是泛問，必須指向教材裡的具體東西')
		if point['type'] not in TYPES:
			found.append(f'{where}.type 不支援')
		refs = point['objectives']
		if (not isinstance(refs, list) or len(set(map(str, refs))) != len(refs)
			or any(ref not in objective_ids for ref in refs)):
			found.append(f'{where}.objectives 指向不存在或重複的學習目標')
		else:
			covered.update(refs)
		text(point['explanation'], LIMITS['explanation'], f'{where}.explanation')
		example = point['example']
		if example is not None:
			if not fields(example, ('kind', 'content', 'language'), f'{where}.example') or example['kind'] not in EXAMPLE_KINDS:
				found.append(f'{where}.example 格式不符')
			else:
				if not isinstance(example['language'], str) or (example['kind'] == 'code') != bool(example['language'].strip()):
					found.append(f'{where}.example.language 只在程式例子填寫')
				if (text(example['content'], LIMITS['example_chars'], f'{where}.example.content')
					and len(example['content'].strip().splitlines()) > LIMITS['example_lines']):
					found.append(f'{where}.example.content 超過 {LIMITS["example_lines"]} 行')
		mistakes = point['misconceptions']
		if not isinstance(mistakes, list) or len(mistakes) > 2:
			found.append(f'{where}.misconceptions 最多 2 條')
			mistakes = mistakes if isinstance(mistakes, list) else []
		total_mistakes += len(mistakes)
		for mindex, mistake in enumerate(mistakes):
			if fields(mistake, ('wrong', 'why', 'correct'), f'{where}.misconceptions[{mindex}]'):
				for key in ('wrong', 'why', 'correct'):
					text(mistake[key], LIMITS['misconception'], f'{where}.misconceptions[{mindex}].{key}')
		parent = point['parent_id']
		# 上層必須排在前面：同時排除自連、循環與指向不存在的節點。
		if parent is not None and parent not in seen:
			found.append(f'{where}.parent_id 必須指向排在前面的另一個重點')
		sources(point['sources'], 1, 4, f'{where}.sources')
		seen.append(pid)
	if total_mistakes > 8:
		found.append('常見錯誤總數最多 8 條')
	for oid in objective_ids:
		if oid not in covered:
			found.append(f'學習目標 {oid} 沒有任何重點涵蓋')
	if not found and len(json.dumps(value, ensure_ascii=False).encode('utf-8')) > 64 * 1024:
		found.append('重點清單超過大小上限')
	return found


def canonical_key_points(value, material):
	found = problems(value, material)
	if found:
		raise KeyPointsError(found)
	return deepcopy(value)
