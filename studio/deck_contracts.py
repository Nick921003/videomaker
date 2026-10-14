"""線上簡報與 PPTX 共用的封閉 Deck v1 內容契約。"""

from copy import deepcopy
import json
import re


_VERSIONS = ("1.0", "1.1", "1.2", "1.3")
_ROLES = frozenset(("hook", "concept", "example", "pitfall", "summary"))
_LAYOUTS = frozenset(("bullets", "code", "compare", "steps"))
_SLIDE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
_MAX_JSON_BYTES = 64 * 1024


class DeckError(ValueError):
	"""Deck 候選內容不符合封閉契約。"""


def _fields(value, required):
	if not isinstance(value, dict) or set(value) != set(required):
		raise DeckError("簡報欄位不符合契約")


def _text(value, maximum):
	if not isinstance(value, str) or not value.strip() or len(value) > maximum:
		raise DeckError("簡報文字不符合契約")
	if any(ord(character) < 32 and character not in "\n\t" for character in value):
		raise DeckError("簡報文字包含控制字元")
	return value


def _items(value, minimum, maximum, text_maximum=120):
	if not isinstance(value, list) or not minimum <= len(value) <= maximum:
		raise DeckError("簡報清單長度不符合契約")
	for item in value:
		_text(item, text_maximum)


def _block(value, layout):
	if not isinstance(value, dict) or value.get("type") != layout:
		raise DeckError("簡報區塊與版型不符")
	if layout == "bullets":
		_fields(value, ("type", "items"))
		_items(value["items"], 1, 5)
	elif layout == "code":
		_fields(value, ("type", "language", "lines"))
		_text(value["language"], 32)
		_items(value["lines"], 1, 16, 120)
	elif layout == "compare":
		_fields(value, ("type", "left", "right"))
		for side in ("left", "right"):
			_fields(value[side], ("title", "items"))
			_text(value[side]["title"], 60)
			_items(value[side]["items"], 1, 4)
	elif layout == "concept":
		_fields(value, ("type", "center", "items"))
		_text(value["center"], 40)
		if not isinstance(value["items"], list) or not 2 <= len(value["items"]) <= 4:
			raise DeckError("概念圖分支數量不符合契約")
		for item in value["items"]:
			_fields(item, ("title", "text"))
			_text(item["title"], 32)
			_text(item["text"], 80)
	elif layout == "steps":
		_fields(value, ("type", "items"))
		_items(value["items"], 2, 6)
	elif layout == "walkthrough":
		_fields(value, ("type", "language", "lines", "states"))
		_text(value['language'], 32)
		_items(value['lines'], 1, 10, 72)
		states = value['states']
		if not isinstance(states, list) or not 2 <= len(states) <= 8:
			raise DeckError('走讀狀態數量不符合契約')
		for state in states:
			_fields(state, ('label', 'line', 'vars', 'output', 'explanation'))
			if type(state['line']) is not int or not 1 <= state['line'] <= len(value['lines']):
				raise DeckError('走讀程式行不存在')
			for key, maximum in (('label', 24), ('output', 80), ('explanation', 80)):
				_text(state[key], maximum)
			variables = state['vars']
			if not isinstance(variables, list) or not 1 <= len(variables) <= 4:
				raise DeckError('走讀變數數量不符合契約')
			names = set()
			for variable in variables:
				_fields(variable, ('name', 'value'))
				_text(variable['name'], 20);_text(variable['value'], 24)
				if variable['name'] in names:
					raise DeckError('走讀變數名稱重複')
				names.add(variable['name'])
	elif layout == 'pipeline':
		from studio.visual_components import validate_pipeline
		try:
			validate_pipeline(value)
		except ValueError as exc:
			raise DeckError(str(exc)) from exc
	else:
		raise DeckError("不支援的簡報版型")


_HANDOUT_FIELDS = {
	'cover': ('slide_id', 'kind', 'title', 'objectives'),
	'point': ('slide_id', 'kind', 'question', 'title', 'explanation', 'example', 'misconceptions', 'sources'),
	'mistakes': ('slide_id', 'kind', 'items'),
}


def _canonical_handout(value):
	"""講義版：封面在前、常見錯誤整理只能在最後，中間 3–8 個重點頁。"""
	slides = value['slides']
	if not isinstance(slides, list) or not 4 <= len(slides) <= 10:
		raise DeckError('講義頁數不符合契約')
	seen = set()
	for index, slide in enumerate(slides):
		kind = slide.get('kind') if isinstance(slide, dict) else None
		if (kind not in _HANDOUT_FIELDS or (kind == 'cover') != (index == 0)
			or (kind == 'mistakes' and index != len(slides) - 1)):
			raise DeckError('講義頁面種類或順序不符合契約')
		_fields(slide, _HANDOUT_FIELDS[kind])
		if not isinstance(slide['slide_id'], str) or not _SLIDE_ID.fullmatch(slide['slide_id']) or slide['slide_id'] in seen:
			raise DeckError('簡報頁面 ID 不符合契約')
		seen.add(slide['slide_id'])
		if kind == 'cover':
			_text(slide['title'], 160)
			_items(slide['objectives'], 1, 6, 80)
		elif kind == 'point':
			_text(slide['question'], 60)
			_text(slide['title'], 12)
			_text(slide['explanation'], 150)
			example = slide['example']
			if example is not None:
				_fields(example, ('kind', 'content', 'language'))
				if example['kind'] not in ('code', 'formula', 'text') or not isinstance(example['language'], str):
					raise DeckError('講義例子不符合契約')
				_text(example['content'], 400)
			mistakes = slide['misconceptions']
			if not isinstance(mistakes, list) or len(mistakes) > 2:
				raise DeckError('講義常見錯誤數量不符合契約')
			for mistake in mistakes:
				_fields(mistake, ('wrong', 'why', 'correct'))
				for key in ('wrong', 'why', 'correct'):
					_text(mistake[key], 80)
			_items(slide['sources'], 1, 4, 1000)
		else:
			items = slide['items']
			if not isinstance(items, list) or not 1 <= len(items) <= 8:
				raise DeckError('常見錯誤整理數量不符合契約')
			for item in items:
				_fields(item, ('point_title', 'wrong', 'why', 'correct'))
				_text(item['point_title'], 12)
				for key in ('wrong', 'why', 'correct'):
					_text(item[key], 80)
	if not 3 <= sum(slide['kind'] == 'point' for slide in slides) <= 8:
		raise DeckError('講義重點頁數不符合契約')


def canonical_deck(value):
	"""驗證模型 Deck 並回傳與原輸入隔離的資料。"""
	_fields(value, ("contract_version", "title", "slides"))
	if value["contract_version"] not in _VERSIONS:
		raise DeckError("不支援的簡報版本")
	_text(value["title"], 160)
	if value["contract_version"] == "1.3":
		_canonical_handout(value)
		try:
			encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
		except (TypeError, ValueError, UnicodeError) as exc:
			raise DeckError("簡報內容無法序列化") from exc
		if len(encoded) > _MAX_JSON_BYTES:
			raise DeckError("簡報內容超過大小上限")
		return deepcopy(value)
	slides = value["slides"]
	if not isinstance(slides, list) or not 3 <= len(slides) <= 12:
		raise DeckError("簡報頁數不符合契約")
	seen = set()
	self_study = value["contract_version"] != "1.0"
	professional = value['contract_version'] == '1.2'
	for slide in slides:
		fields = ("slide_id", "role", "title", "layout", "blocks", "speaker_notes", "source_quote")
		_fields(slide, fields + (("takeaway",) if self_study else ()) +
			(('question', 'explanation', 'source_quotes', 'selection_reason') if professional else ()))
		slide_id = slide["slide_id"]
		if not isinstance(slide_id, str) or not _SLIDE_ID.fullmatch(slide_id) or slide_id in seen:
			raise DeckError("簡報頁面 ID 不符合契約")
		seen.add(slide_id)
		if (not isinstance(slide["role"], str) or slide["role"] not in _ROLES or
			not isinstance(slide["layout"], str) or
			slide["layout"] not in (_LAYOUTS | {"concept", "walkthrough", "pipeline"} if professional else _LAYOUTS | {"concept"} if self_study else _LAYOUTS)):
			raise DeckError("簡報頁面種類或版型不符合契約")
		_text(slide["title"], 120)
		_text(slide["speaker_notes"], 2000)
		_text(slide["source_quote"], 1000 if professional else 500)
		if self_study:
			_text(slide["takeaway"], 120)
		if professional:
			_text(slide['question'], 80)
			_text(slide['explanation'], 200)
			_text(slide['selection_reason'], 160)
			_items(slide['source_quotes'], 1, 8, 1000)
			if slide['source_quote'] != slide['source_quotes'][0]:
				raise DeckError('簡報主要引用與逐項來源不一致')
		blocks = slide["blocks"]
		if not isinstance(blocks, list) or len(blocks) != 1:
			raise DeckError("每頁必須有一個主區塊")
		_block(blocks[0], slide["layout"])
	try:
		encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
	except (TypeError, ValueError, UnicodeError) as exc:
		raise DeckError("簡報內容無法序列化") from exc
	if len(encoded) > _MAX_JSON_BYTES:
		raise DeckError("簡報內容超過大小上限")
	return deepcopy(value)
