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
			"name": "重點清單抽取",
			"model": "google:gemini-3.8-flash",
			"paid": True,
			"cost": "試跑後填入",
			"detail": "每份教材抽取一次重點清單（3–8 個重點），講義與心智圖共用；推論出的結構需先確認。"
		},
		{
			"id": "validate",
			"name": "重點清單檢查",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "學習目標都有涵蓋、出處逐字在教材裡、字數上限、不得有泛問。"
		},
		{
			"id": "export",
			"name": "轉成講義並匯出",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "一頁一個重點，匯出可編輯 PPTX；這一步不再呼叫模型。"
		}
	],
	"planned_note": None
}


def estimate_usd(unit: UnitView, item: str) -> float:
	return 0.01


def commands(unit: UnitView, item: str) -> list[Command]:
	return [Command("generate", [str(ROOT / "workbench/run_slides.py"), str(unit.dir), "--quality", "keypoints", "--budget-usd", "0.50"])]


def outputs(unit: UnitView, item: str) -> dict[str, str]:
	return _existing_outputs(unit, {"deck": "slides/deck.json", "pptx": "slides/deck.pptx"})


def is_done(unit: UnitView, item: str) -> bool:
	from workbench.key_points import product_is_current
	return _nonempty(unit.dir / "slides/deck.pptx") and product_is_current(unit.dir, "slides/source.json")
