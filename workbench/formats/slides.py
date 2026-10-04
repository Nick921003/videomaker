from . import ROOT, Command, UnitView, _existing_outputs, _nonempty


FORMAT = {
	"id": "slides",
	"name": "教學簡報",
	"scope": "unit",
	"status": "available",
	"preview": "deck",
	"steps": [
		{
			"id": "generate",
			"name": "教學簡報內容生成",
			"model": "google:gemini-3.8-flash",
			"paid": True,
			"cost": "試跑後填入",
			"detail": "3–12 頁；每頁包含版型、可見結論、講者備註與原文引用。"
		},
		{
			"id": "validate",
			"name": "契約與引用驗證",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "驗證簡報契約、每頁原文引用與最低可讀字級。"
		},
		{
			"id": "export",
			"name": "匯出簡報",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "沿用簡報資料提供線上預覽，並匯出可編輯 PPTX。"
		}
	],
	"planned_note": None
}


def estimate_usd(unit: UnitView, item: str) -> float:
	return 0.01


def commands(unit: UnitView, item: str) -> list[Command]:
	return [Command("generate", [str(ROOT / "workbench/run_slides.py"), str(unit.dir)])]


def outputs(unit: UnitView, item: str) -> dict[str, str]:
	return _existing_outputs(unit, {"deck": "slides/deck.json", "pptx": "slides/deck.pptx"})


def is_done(unit: UnitView, item: str) -> bool:
	return _nonempty(unit.dir / "slides/deck.pptx")
