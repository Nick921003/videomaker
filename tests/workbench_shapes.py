"""新版工作台的共用 JSON 契約；型別鍵表示動態對照表，Enum 型別限制合法值。"""

from enum import Enum


_NUMBER = (int, float)
_SCOPE = Enum("Scope", {value: value for value in ("point", "unit")})
_STATUS = Enum("Status", {value: value for value in ("available", "planned")})
_PREVIEW = Enum("Preview", {value: value for value in ("video", "svg", "deck", "none")})
_ITEM_STATUS = Enum("ItemStatus", {value: value for value in ("none", "queued", "running", "done", "failed")})
_JOB_STATE = Enum("JobState", {value: value for value in ("queued", "running", "done", "failed")})
_STEP_STATE = Enum("StepState", {value: value for value in ("pending", "running", "done", "failed", "skipped")})
_KEY_POINTS_STATUS = Enum("KeyPointsStatus", {value: value for value in ("missing", "needs_review", "ready")})
_KEY_POINTS_STRUCTURE = Enum("KeyPointsStructure", {value: value for value in ("material", "inferred")})
_ASK_KIND = Enum("AskKind", {value: value for value in ("story", "highlight", "out_of_scope", "no_match")})
_SOURCE_REF = (dict, None)
_FILES = {str: str}
_STEP = {"id": str, "name": str, "model": str, "paid": bool, "cost": str, "detail": str}
_FORMAT = {
	"id": str, "name": str, "scope": _SCOPE, "status": _STATUS, "preview": _PREVIEW,
	"steps": [_STEP], "planned_note": ({"order": int, "why": str}, None),
}
_POINT = {
	"id": str, "question": str, "also_asks": [str], "title": str, "sec": _NUMBER,
	"objectives": [int], "screens": [str], "show": str,
}
_PRODUCT = {
	"item": str, "format": str, "label": str, "files": _FILES,
	"duration": (int, float, None), "cost_usd": (int, float, None),
	"embed_url": str, "created_at": str,
}
_CALL = {"at": str, "step": str, "model": str, "in": int, "out": int, "usd": _NUMBER}


SHAPES: dict[str, object] = {
	"formats": {"stages": [_FORMAT], "formats": [_FORMAT]},
	"unit_summary": {
		"unit_id": str, "title": str, "created_at": str, "analyzed": bool, "points": int,
		"products": {"video": int, "highlight": bool, "mindmap": bool, "slides": bool},
		"spent_usd": _NUMBER, "source_ref": _SOURCE_REF,
	},
	"analysis": {
		"unit_title": str, "scope": {"covers": [str], "not_covers": [str]},
		"points": [_POINT], "glossary": [{"term": str, "say_as": str}],
		"highlight": {"points": [str], "total_sec": _NUMBER, "why": str},
	},
	"item": {
		"item": str, "format": str, "label": str, "status": _ITEM_STATUS,
		"estimate_usd": _NUMBER, "cost_usd": (int, float, None),
		"duration": (int, float, None), "files": _FILES, "job_id": (str, None),
		"warnings": [{"code": str, "detail": str}],
	},
	"job_error": {"code": str, "reason": str, "advice": str, "retry": bool},
	"usage": {
		"totals": {"today": _NUMBER, "all": _NUMBER, "by_model": {str: _NUMBER}},
		"units": [{
			"unit_id": str, "title": str, "usd": _NUMBER,
			"items": [{"item": str, "label": str, "usd": _NUMBER, "calls": [_CALL]}],
		}],
	},
	"manifest": {"unit_id": str, "title": str, "source_ref": _SOURCE_REF, "products": [_PRODUCT]},
	"ask": {"kind": _ASK_KIND, "story": (str, None), "score": _NUMBER, "reason": str, "video": (str, None)},
	"api_error": {"error": {"code": str, "reason": str, "advice": str}},
	"key_points": {
		"unit_id": str, "status": _KEY_POINTS_STATUS, "structure": (_KEY_POINTS_STRUCTURE, None),
		"content_version": (str, None), "digest": (str, None), "key_points": (dict, None),
	},
	"upload": {"upload_id": str, "kind": str, "excerpt": str, "pages": (int, None), "chars": int, "estimate_usd": _NUMBER},
}
SHAPES["unit"] = {
	"unit_id": str, "title": str, "source_ref": _SOURCE_REF, "spent_usd": _NUMBER,
	"analysis": (SHAPES["analysis"], None), "items": [SHAPES["item"]],
}
SHAPES["job"] = {
	"job_id": str, "unit_id": (str, None), "item": str, "format": str, "state": _JOB_STATE,
	"steps": [{"id": str, "state": _STEP_STATE}], "current": (str, None),
	"log": [str], "spent_usd": _NUMBER, "error": (SHAPES["job_error"], None),
	"warnings": [{"code": str, "detail": str}],
}
SHAPES["queue"] = {"running": (SHAPES["job"], None), "queued": [SHAPES["job"]]}


def assert_shape(value, shape, path="$"):
	"""檢查必填欄位與型別，失敗時保留第一個錯誤的完整路徑。"""
	if isinstance(shape, tuple):
		first_error = None
		for option in shape:
			try:
				assert_shape(value, type(None) if option is None else option, path)
			except AssertionError as error:
				if first_error is None:
					first_error = error
			else:
				return
		raise first_error
	if isinstance(shape, dict):
		if not isinstance(value, dict):
			raise AssertionError(f"{path}: expected dict, got {type(value).__name__}")
		for key, child in shape.items():
			if isinstance(key, type):
				for actual_key, actual_value in value.items():
					assert_shape(actual_key, key, f"{path}.<key>")
					assert_shape(actual_value, child, f"{path}.{actual_key}")
				continue
			child_path = f"{path}.{key}"
			if key not in value:
				raise AssertionError(f"{child_path}: missing key")
			assert_shape(value[key], child, child_path)
		return
	if isinstance(shape, list):
		if not isinstance(value, list):
			raise AssertionError(f"{path}: expected list, got {type(value).__name__}")
		for index, item in enumerate(value):
			assert_shape(item, shape[0], f"{path}[{index}]")
		return
	if issubclass(shape, Enum):
		try:
			shape(value)
		except (TypeError, ValueError):
			raise AssertionError(f"{path}: expected one of {[member.value for member in shape]}, got {value!r}") from None
		return
	# JSON 的布林值不可因 Python 的繼承關係被當成數字。
	if type(value) is not shape:
		raise AssertionError(f"{path}: expected {shape.__name__}, got {type(value).__name__}")
