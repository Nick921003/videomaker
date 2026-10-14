from . import ROOT, Command, UnitView, _existing_outputs, _nonempty


FORMAT = {
	"id": "mindmap",
	"name": "概念心智圖",
	"scope": "unit",
	"status": "available",
	"preview": "svg",
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
			"id": "render",
			"name": "繪製 SVG",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "節點只放短詞，點開看說明與出處，並連回講義頁；這一步不再呼叫模型。"
		}
	],
	"planned_note": None
}


def estimate_usd(unit: UnitView, item: str) -> float:
	return 0.01


def commands(unit: UnitView, item: str) -> list[Command]:
	return [Command("generate", [str(ROOT / "workbench/run_mindmap.py"), str(unit.dir), "--quality", "keypoints", "--budget-usd", "0.50"])]


def outputs(unit: UnitView, item: str) -> dict[str, str]:
	return _existing_outputs(unit, {"svg": "mindmap/mindmap.svg"})


def is_done(unit: UnitView, item: str) -> bool:
	from workbench.key_points import product_is_current
	return _nonempty(unit.dir / "mindmap/mindmap.svg") and product_is_current(unit.dir, "mindmap/source.json")
