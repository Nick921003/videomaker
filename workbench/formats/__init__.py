"""成品格式的公開描述與執行契約。"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
BOARD_DIR = ROOT / "video_engine/board"
MODEL = "google:gemini-3.8-flash"


@dataclass
class UnitView:
	id: str
	dir: Path
	plan: dict | None
	tts_mode: str = "gemini"


@dataclass
class Command:
	step: str
	argv: list[str]
	python: str = "project"


class FormatError(Exception):
	pass


def _validate_description(fmt: dict):
	if not isinstance(fmt, dict):
		raise FormatError("格式描述必須是 dict")
	for key in ("id", "name", "scope", "status", "preview"):
		if type(fmt.get(key)) is not str:
			raise FormatError(f"格式缺少文字欄位：{key}")
	for key, choices in (("scope", ("point", "unit")), ("status", ("available", "planned")),
		("preview", ("video", "svg", "deck", "none"))):
		if fmt[key] not in choices:
			raise FormatError(f"{fmt['id']} 的 {key} 不合法")
	if not isinstance(fmt.get("steps"), list):
		raise FormatError(f"{fmt['id']} 缺少 steps 清單")
	seen = set()
	for step in fmt["steps"]:
		if not isinstance(step, dict):
			raise FormatError(f"{fmt['id']} 的步驟必須是 dict")
		for key in ("id", "name", "model", "paid", "cost", "detail"):
			if type(step.get(key)) is not (bool if key == "paid" else str):
				raise FormatError(f"{fmt['id']} 的步驟欄位不合法：{key}")
		if step["id"] in seen:
			raise FormatError(f"{fmt['id']} 的 step id 重複：{step['id']}")
		seen.add(step["id"])


def validate(fmt: dict, module=None) -> None:
	_validate_description(fmt)
	if fmt["status"] == "planned":
		if "commands" in fmt or (module is not None and hasattr(module, "commands")):
			raise FormatError(f"{fmt['id']} 尚未實作，不得有 commands")
		if fmt["steps"]:
			raise FormatError(f"{fmt['id']} 尚未實作，steps 必須為空")
		note = fmt.get("planned_note")
		if (not isinstance(note, dict) or type(note.get("order")) is not int
			or type(note.get("why")) is not str):
			raise FormatError(f"{fmt['id']} 缺少合法的 planned_note")
	else:
		for name in ("estimate_usd", "commands", "outputs", "is_done"):
			if not callable(getattr(module, name, None)):
				raise FormatError(f"{fmt['id']} 缺少可執行的 {name}")


def list_formats() -> list[ModuleType]:
	return list(_FORMATS.values())


def get_format(fid: str) -> ModuleType:
	return _FORMATS[fid]


def public() -> dict:
	keys = ("id", "name", "scope", "status", "preview", "steps", "planned_note")
	def description(fmt):
		return {key: deepcopy(fmt[key]) for key in keys}
	return {
		"stages": [description(stage) for stage in stages.STAGES],
		"formats": [description(module.FORMAT) for module in list_formats()]
			+ [description(fmt) for fmt in planned.PLANNED],
	}


def item_format(plan: dict | None, item: str) -> str:
	if item in ("highlight", "mindmap", "slides"):
		return item
	if any(story["id"] == item for story in (plan or {}).get("stories", [])):
		return "video"
	raise KeyError(item)


def _existing_outputs(unit: UnitView, files: dict[str, str]) -> dict[str, str]:
	return {key: relative for key, relative in files.items() if (unit.dir / relative).is_file()}


def _nonempty(path: Path) -> bool:
	return path.is_file() and path.stat().st_size > 0


# 先定義共用型別，避免格式模組匯入時形成循環。
from . import stages, video, highlight, mindmap, slides, planned

_AVAILABLE = (video, highlight, mindmap, slides)
for _module in _AVAILABLE:
	validate(_module.FORMAT, _module)
for _fmt in planned.PLANNED:
	validate(_fmt)
for _stage in stages.STAGES:
	_validate_description(_stage)
_FORMATS = {module.FORMAT["id"]: module for module in _AVAILABLE}
