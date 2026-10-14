from . import BOARD_DIR, MODEL, Command, UnitView, _existing_outputs, _nonempty


FORMAT = {
	"id": "video",
	"name": "教學影片",
	"scope": "point",
	"status": "available",
	"preview": "video",
	"steps": [
		{
			"id": "selftest",
			"name": "本機自我檢查",
			"model": "本機",
			"cost": "免費",
			"detail": "每次規劃或分鏡呼叫前先做免費自檢；沿用既有快速模式，範例與測試分鏡必須通過量測閘，已知崩潰時間軸必須能執行。元件有問題就不呼叫模型；相關程式雜湊未變時沿用通過紀錄。規格要求的歷來分鏡全面檢查屬完整模式，現有 CLI 快速自檢會略過歷史輸出，亦未掃描工作室素材庫。",
			"paid": False
		},
		{
			"id": "storyboard",
			"name": "分鏡",
			"model": "google:gemini-3.8-flash",
			"cost": "每段約 US$0.02–0.04",
			"detail": "只產生分鏡資料：元件、動作與旁白，不寫座標與秒數。工作室固定傳入此模型；整個單元預算上限 US$0.50。",
			"paid": True
		},
		{
			"id": "validate",
			"name": "驗證閘",
			"model": "本機",
			"cost": "免費",
			"detail": "檢查編譯、旁白的英文與程式符號、唸法撞名、標註數、必演畫面，以及越界、重疊、字級與決定性。",
			"paid": False
		},
		{
			"id": "repair",
			"name": "修正",
			"model": "google:gemini-3.8-flash",
			"cost": "每次約 US$0.005–0.015",
			"detail": "最多修正兩次；問題可定位時只重寫出問題的場景，無法定位時修正完整分鏡。費用納入同一單元預算。",
			"paid": True
		},
		{
			"id": "narrate",
			"name": "配音",
			"model": "google:gemini-3.8-flash-tts（Charon 聲音）",
			"cost": "5 分鐘約 US$0.09",
			"detail": "每句一次 Gemini TTS，台灣華語口音；英文（sum、printf、VS Code）照原文唸，程式符號（<=、-o）依詞彙表唸中文。faster-whisper 拼音級漏字與重複檢查，未通過就重配，最多三輪。可改回本機 GPT-SoVITS（免費，narrate.py --tts sovits）。",
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
	story = next(story for story in unit.plan["stories"] if story["id"] == item)
	return 0.035 + story["sec"] * 0.0003


def scene_commands(unit: UnitView, item: str, step: str = "storyboard") -> list[Command]:
	if (unit.dir / f"{item}.scene.json").is_file():
		return []
	argv = [str(BOARD_DIR / "author.py"), "scene", str(unit.dir / "material.md"), str(unit.dir), item]
	if (unit.dir / f"{item}.failed.json").is_file():
		argv.append("--resume")
	argv.extend(["--model", MODEL, "--budget-usd", "0.50"])
	return [Command(step,[str(BOARD_DIR.parents[1]/'workbench/run_teaching_plan.py'),str(unit.dir),
		'--budget-usd','0.50']),Command(step, argv)]


def render_commands(unit: UnitView, item: str, scene) -> list[Command]:
	output = unit.dir / item
	voice = output / "voice"
	player = output / "player"
	timeline = output / "timeline.json"
	return [
		Command("narrate", [str(BOARD_DIR / "narrate.py"), str(scene), str(voice), "--tts", unit.tts_mode]),
		Command("render", [str(BOARD_DIR / "compile.py"), str(scene), str(timeline), "--timing",
			str(voice / "timing.json"), "--gaps", str(output / "gaps.jsonl")]),
		Command("render", [str(BOARD_DIR / "build.py"), str(timeline), str(player),
			"--audio", str(voice / "master.wav")]),
		Command("render", [str(BOARD_DIR / "check.py"), str(player)], python="playwright"),
		Command("render", [str(BOARD_DIR / "export.py"), str(player), str(output / "video.mp4")], python="playwright"),
	]


def commands(unit: UnitView, item: str) -> list[Command]:
	return scene_commands(unit, item) + render_commands(unit, item, unit.dir / f"{item}.scene.json")


def outputs(unit: UnitView, item: str) -> dict[str, str]:
	return _existing_outputs(unit, {"video": f"{item}/video.mp4"})


def is_done(unit: UnitView, item: str) -> bool:
	return _nonempty(unit.dir / item / "video.mp4")
