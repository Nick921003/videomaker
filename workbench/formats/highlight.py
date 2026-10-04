from . import BOARD_DIR, Command, UnitView, _existing_outputs, _nonempty
from .video import scene_commands, render_commands


FORMAT = {
	"id": "highlight",
	"name": "重點片",
	"scope": "unit",
	"status": "available",
	"preview": "video",
	"steps": [
		{
			"id": "scenes",
			"name": "補齊段落分鏡",
			"model": "google:gemini-3.8-flash",
			"cost": "每段約 US$0.02–0.04",
			"detail": "補齊建議重點片中缺少的分鏡，已有分鏡直接沿用。",
			"paid": True
		},
		{
			"id": "compose",
			"name": "串接重點片",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "把三至五段分鏡串起來；目錄過場由程式產生，不呼叫模型。"
		},
		{
			"id": "narrate",
			"name": "配音",
			"model": "google:gemini-3.8-flash-tts（Charon 聲音）",
			"cost": "5 分鐘約 US$0.09",
			"detail": "每句一次 Gemini TTS，台灣華語口音；英文（sum、printf、VS Code）照原文唸，程式符號（<=、-o）依詞彙表唸中文。faster-whisper 拼音級漏字檢查，漏了就重配。可改回本機 GPT-SoVITS（免費，narrate.py --tts sovits）。",
			"paid": True
		},
		{
			"id": "render",
			"name": "出片",
			"model": "本機",
			"cost": "免費",
			"detail": "依配音實測時間編譯，建立 Canvas 播放器，通過 Playwright 量測檢查後截圖，使用 ffmpeg 編碼為影片。",
			"paid": False
		}
	],
	"planned_note": None
}


def estimate_usd(unit: UnitView, item: str) -> float:
	highlight = unit.plan["highlight"]
	missing = sum(not (unit.dir / f"{story}.scene.json").is_file() for story in highlight["stories"])
	return 0.03 * missing + highlight["total_sec"] * 0.0003


def commands(unit: UnitView, item: str) -> list[Command]:
	result = []
	for story in unit.plan["highlight"]["stories"]:
		result.extend(scene_commands(unit, story, step="scenes"))
	scene = unit.dir / "highlight.scene.json"
	result.append(Command("compose", [str(BOARD_DIR / "compose.py"), str(unit.dir / "plan.json"),
		str(unit.dir), str(scene)]))
	return result + render_commands(unit, "highlight", scene)


def outputs(unit: UnitView, item: str) -> dict[str, str]:
	return _existing_outputs(unit, {"video": "highlight/video.mp4"})


def is_done(unit: UnitView, item: str) -> bool:
	return _nonempty(unit.dir / "highlight/video.mp4")
