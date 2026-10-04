"""教材用量的相容讀取、品項標籤與費用彙總。"""
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path

from .library import safe_path


_LABELS = {
	"highlight": "重點片", "mindmap": "心智圖", "slides": "簡報",
	"analysis": "教材分析", "ingest": "教材整理", "video": "影片（未標點）",
}
_CALL_FIELDS = ("at", "step", "model", "in", "out", "usd")


def _text(value, default=""):
	return value if isinstance(value, str) and value else default


def _read_rows(path, item=None, step=None):
	rows = []
	try:
		with path.open(encoding="utf-8") as handle:
			modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
			for line in handle:
				try:
					value = json.loads(line)
				except ValueError:
					# 子行程可能仍在寫入最後一列，下一次讀取再補上。
					continue
				if not isinstance(value, dict):
					continue
				usd = value.get("usd", 0.0)
				if type(usd) not in (int, float) or not math.isfinite(usd):
					continue
				stage = _text(value.get("stage"))
				entry = {
					"at": _text(value.get("at"), modified),
					"item": item or _text(value.get("item"), "analysis" if stage == "plan" else "video"),
					"step": step or _text(value.get("step"), {"plan": "plan", "scene": "storyboard"}.get(stage, "")),
					"model": _text(value.get("model"), "unknown"), "usd": usd,
				}
				for key in ("in", "out"):
					count = value.get(key)
					entry[key] = count if type(count) is int and count >= 0 else 0
				entry.update({key: count for key, count in value.items() if key.startswith("cache_")})
				rows.append(entry)
	except FileNotFoundError:
		pass
	return rows


def read_unit(unit_dir) -> list[dict]:
	directory = Path(unit_dir).resolve()
	rows = _read_rows(safe_path(directory, "usage.jsonl"))
	for path in sorted(directory.glob("*/voice/tts_usage.jsonl")):
		relative = path.relative_to(directory)
		rows.extend(_read_rows(safe_path(directory, relative), item=relative.parts[0], step="narrate"))
	return rows


def item_label(item, plan) -> str:
	for number, story in enumerate((plan or {}).get("stories", []), 1):
		if story["id"] == item:
			return f"第 {number} 點影片：{story['title']}"
	return _LABELS.get(item, item)


def _timestamp(at):
	try:
		value = datetime.fromisoformat(at.replace("Z", "+00:00"))
	except ValueError:
		return datetime.min.replace(tzinfo=timezone.utc)
	# 舊紀錄沒有時區，排序時視為 UTC；今日費用沿用紀錄日期。
	return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def summarize(units: list[tuple[str, str, dict | None, list[dict]]], today: date) -> dict:
	totals = {"today": 0.0, "all": 0.0, "by_model": {}}
	result = {"totals": totals, "units": []}
	for uid, title, plan, rows in units:
		items = {}
		for row in rows:
			item = row["item"]
			group = items.setdefault(item, {"item": item, "label": item_label(item, plan), "usd": 0.0, "calls": []})
			group["calls"].append({key: row[key] for key in _CALL_FIELDS})
			group["usd"] += row["usd"]
			totals["all"] += row["usd"]
			if _timestamp(row["at"]).date() == today:
				totals["today"] += row["usd"]
			model = row["model"]
			totals["by_model"][model] = totals["by_model"].get(model, 0.0) + row["usd"]
		for group in items.values():
			group["usd"] = round(group["usd"], 8)
			group["calls"].sort(key=lambda call: _timestamp(call["at"]), reverse=True)
		result["units"].append({"unit_id": uid, "title": title, "usd": round(sum(row["usd"] for row in rows), 8),
			"items": list(items.values())})
	totals["today"], totals["all"] = round(totals["today"], 8), round(totals["all"], 8)
	totals["by_model"] = {model: round(usd, 8) for model, usd in totals["by_model"].items()}
	return result


def unit_spent(unit_dir) -> float:
	return round(sum(row["usd"] for row in read_unit(unit_dir)), 6)
