"""線上簡報與 PPTX 共用的封閉 Deck v1 內容契約。"""

from copy import deepcopy
import json
import re


_VERSIONS = ("1.0", "1.1")
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
	else:
		raise DeckError("不支援的簡報版型")


def canonical_deck(value):
	"""驗證模型 Deck 並回傳與原輸入隔離的資料。"""
	_fields(value, ("contract_version", "title", "slides"))
	if value["contract_version"] not in _VERSIONS:
		raise DeckError("不支援的簡報版本")
	_text(value["title"], 160)
	slides = value["slides"]
	if not isinstance(slides, list) or not 3 <= len(slides) <= 12:
		raise DeckError("簡報頁數不符合契約")
	seen = set()
	self_study = value["contract_version"] == "1.1"
	for slide in slides:
		fields = ("slide_id", "role", "title", "layout", "blocks", "speaker_notes", "source_quote")
		_fields(slide, fields + (("takeaway",) if self_study else ()))
		slide_id = slide["slide_id"]
		if not isinstance(slide_id, str) or not _SLIDE_ID.fullmatch(slide_id) or slide_id in seen:
			raise DeckError("簡報頁面 ID 不符合契約")
		seen.add(slide_id)
		if (not isinstance(slide["role"], str) or slide["role"] not in _ROLES or
			not isinstance(slide["layout"], str) or
			slide["layout"] not in (_LAYOUTS | {"concept"} if self_study else _LAYOUTS)):
			raise DeckError("簡報頁面種類或版型不符合契約")
		_text(slide["title"], 120)
		_text(slide["speaker_notes"], 2000)
		_text(slide["source_quote"], 500)
		if self_study:
			_text(slide["takeaway"], 120)
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
