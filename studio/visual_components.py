"""跨教材形式的有界視覺資料；沿用 Board pipeline 的 stage 欄位。"""
from copy import deepcopy
import re


_ID = re.compile(r'^[a-z][a-z0-9_-]{0,31}$')
PIPELINE_SCHEMA = {'type': 'object', 'additionalProperties': False,
	'required': ['type', 'stages'], 'properties': {
		'type': {'const': 'pipeline'}, 'stages': {'type': 'array', 'items': {
			'type': 'object', 'additionalProperties': False,
			'required': ['id', 'label', 'note'], 'properties': {
				'id': {'type': 'string'}, 'label': {'type': 'string'}, 'note': {'type': 'string'}}}}}}


def validate_pipeline(block):
	if not isinstance(block, dict) or set(block) != {'type', 'stages'} or block['type'] != 'pipeline':
		raise ValueError('流程元件欄位不符合契約')
	stages = block['stages']
	if not isinstance(stages, list) or not 2 <= len(stages) <= 5:
		raise ValueError('流程階段數量須為 2–5')
	ids = set()
	for stage in stages:
		if not isinstance(stage, dict) or set(stage) != {'id', 'label', 'note'}:
			raise ValueError('流程階段欄位不符合契約')
		id = stage['id']
		if not isinstance(id, str) or not _ID.fullmatch(id) or id in ids:
			raise ValueError('流程階段代號不符或重複')
		ids.add(id)
		for name, maximum in (('label', 32), ('note', 80)):
			text = stage[name]
			if (not isinstance(text, str) or not text.strip() or len(text) > maximum or
				any(ord(c) < 32 and c not in '\n\t' for c in text)):
				raise ValueError('流程階段文字超出容量或含控制字元')
	return deepcopy(block)


def pipeline_object(block, object_id):
	"""產生 Board 可用的物件資料，不匯入其執行器或新增動畫動作。"""
	if not isinstance(object_id, str) or not _ID.fullmatch(object_id):
		raise ValueError('流程物件代號不符合契約')
	return {'id': object_id, 'type': 'pipeline', 'stages': validate_pipeline(block)['stages']}
