"""封閉的規劃請求與生成計畫契約。"""

from copy import deepcopy
import re

from studio.catalog import get_capability


_VERSION = "1.0"
_REF = re.compile(r"^material:[A-Za-z0-9_-]+$")
_REVISION = re.compile(r"^sha256:[0-9a-f]{64}$")
_STEP_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class ContractError(ValueError):
	"""輸入不符合封閉契約。"""


def _fields(value, required, optional=()):
	if not isinstance(value, dict) or not set(required) <= set(value) or set(value) - set(required) - set(optional):
		raise ContractError("欄位不符合契約")


def _text(value, maximum, allow_empty=False):
	if not isinstance(value, str) or len(value) > maximum or (not allow_empty and not value.strip()):
		raise ContractError("文字欄位不符合契約")
	return value


def _source(value):
	_fields(value, ("kind", "ref", "revision"))
	if value["kind"] != "upload" or not isinstance(value["ref"], str) or not _REF.fullmatch(value["ref"]):
		raise ContractError("教材來源不符合契約")
	if not isinstance(value["revision"], str) or not _REVISION.fullmatch(value["revision"]):
		raise ContractError("教材版本不符合契約")
	return deepcopy(value)


def duration_range(value):
	_fields(value, ("min_seconds", "max_seconds"))
	low, high = value["min_seconds"], value["max_seconds"]
	if type(low) is not int or type(high) is not int or not 30 <= low <= high <= 600:
		raise ContractError("期望片長需為30到600秒，最短不可大於最長")
	return deepcopy(value)


def normalize_plan_request(value):
	_fields(value, ("contract_version", "instruction", "source"), ("duration_range",))
	if value["contract_version"] != _VERSION:
		raise ContractError("不支援的契約版本")
	instruction = _text(value["instruction"], 2000).strip()
	result = {"contract_version": _VERSION, "instruction": instruction, "source": _source(value["source"])}
	if "duration_range" in value:
		result["duration_range"] = duration_range(value["duration_range"])
	return result


def _messages(items, maximum):
	if not isinstance(items, list) or len(items) > 20:
		raise ContractError("訊息清單不符合契約")
	return [_text(item, maximum) for item in items]


def _questions(items):
	if not isinstance(items, list) or len(items) > 10:
		raise ContractError("釐清問題不符合契約")
	for item in items:
		_fields(item, ("code", "message"))
		_text(item["code"], 64)
		_text(item["message"], 300)
	return deepcopy(items)


def _options(value, definitions):
	required = {name for name, rule in definitions.items() if not rule.get("optional")}
	if not isinstance(value, dict) or not required <= set(value) or set(value) - set(definitions):
		raise ContractError("能力選項不符合契約")
	for name, rule in definitions.items():
		if name not in value:
			continue
		item = value[name]
		if rule["type"] == "integer":
			if not isinstance(item, int) or isinstance(item, bool) or not rule["minimum"] <= item <= rule["maximum"]:
				raise ContractError("數值選項超出範圍")
		elif rule["type"] == "string":
			if not isinstance(item, str) or item not in rule["enum"]:
				raise ContractError("文字選項不在允許範圍")
		elif rule["type"] == "object" and name == "duration_range":
			duration_range(item)
			if not item["min_seconds"] <= value["duration_seconds"] <= item["max_seconds"]:
				raise ContractError("目標片長不在期望範圍內")
		else:
			raise ContractError("未知選項型別")
	return deepcopy(value)


def _step(value, canonical):
	required = {"step_id", "action", "capability_id", "options", "requires"}
	if canonical:
		required |= {"template_id", "review_gate"}
	_fields(value, required)
	if not isinstance(value["step_id"], str) or not _STEP_ID.fullmatch(value["step_id"]):
		raise ContractError("步驟 ID 不符合契約")
	if value["action"] != "artifact.generate" or value["requires"] != []:
		raise ContractError("目前只接受單一無相依生成步驟")
	if not isinstance(value["capability_id"], str):
		raise ContractError("能力 ID 不符合契約")
	capability = get_capability(value["capability_id"])
	if not capability or capability["availability"] != "available":
		raise ContractError("能力目前不可執行")
	options = _options(value["options"], capability["options"])
	if canonical and (value["template_id"] != capability["template_id"] or
		value["review_gate"] != capability["review_gate"]):
		raise ContractError("模板或審核閘不符合目錄")
	result = {"step_id": value["step_id"], "action": value["action"],
		"capability_id": value["capability_id"], "options": options, "requires": []}
	if canonical:
		result["template_id"] = capability["template_id"]
		result["review_gate"] = capability["review_gate"]
	return result


def _plan(value, canonical):
	_fields(value, ("contract_version", "status", "summary", "source", "questions", "warnings", "steps"))
	if value["contract_version"] != _VERSION:
		raise ContractError("不支援的契約版本")
	if value["status"] not in ("ready", "needs_clarification"):
		raise ContractError("未知的計畫狀態")
	result = {"contract_version": _VERSION, "status": value["status"],
		"summary": _text(value["summary"], 500), "source": _source(value["source"]),
		"questions": _questions(value["questions"]), "warnings": _messages(value["warnings"], 300)}
	steps = value["steps"]
	if not isinstance(steps, list):
		raise ContractError("步驟清單不符合契約")
	if value["status"] == "needs_clarification":
		if not result["questions"] or steps:
			raise ContractError("待釐清計畫必須有問題且不可執行")
		result["steps"] = []
	else:
		if result["questions"] or len(steps) != 1:
			raise ContractError("可執行計畫必須恰有一個生成步驟")
		result["steps"] = [_step(steps[0], canonical)]
	return result


def canonicalize_plan(value):
	result = _plan(value, False)
	for step in result["steps"]:
		capability = get_capability(step["capability_id"])
		step["template_id"] = capability["template_id"]
		step["review_gate"] = capability["review_gate"]
	return result


def assert_canonical_plan(value):
	_plan(value, True)


def generation_plan_schema(capability_ids):
	"""給結構化 AI 的 draft schema；保留欄位由 server 補入。"""
	step = {"type": "object", "additionalProperties": False,
		"required": ["step_id", "action", "capability_id", "options", "requires"],
		"properties": {
			"step_id": {"type": "string"},
			"action": {"const": "artifact.generate"},
			"capability_id": {"type": "string", "enum": sorted(capability_ids)},
			"options": {"type": "object"},
			"requires": {"type": "array", "maxItems": 0},
		}}
	return {"type": "object", "additionalProperties": False,
		"required": ["contract_version", "status", "summary", "source", "questions", "warnings", "steps"],
		"properties": {
			"contract_version": {"const": _VERSION},
			"status": {"enum": ["ready", "needs_clarification"]},
			"summary": {"type": "string"},
			"source": {"type": "object"},
			"questions": {"type": "array"},
			"warnings": {"type": "array"},
			"steps": {"type": "array", "items": step},
		}}
