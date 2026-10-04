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
			"name": "概念與關係生成",
			"model": "google:gemini-3.8-flash",
			"paid": True,
			"cost": "試跑後填入",
			"detail": "3–12 個概念、父子關係與原文引用"
		},
		{
			"id": "validate",
			"name": "契約與引用驗證",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "樹狀結構、無循環、每個概念與關係的引用確實在教材裡"
		},
		{
			"id": "render",
			"name": "繪製 SVG",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "程式計算樹狀位置與換行，不由模型畫圖"
		}
	],
	"planned_note": None
}


def estimate_usd(unit: UnitView, item: str) -> float:
	return 0.01


def commands(unit: UnitView, item: str) -> list[Command]:
	return [Command("generate", [str(ROOT / "workbench/run_mindmap.py"), str(unit.dir)])]


def outputs(unit: UnitView, item: str) -> dict[str, str]:
	return _existing_outputs(unit, {"svg": "mindmap/mindmap.svg"})


def is_done(unit: UnitView, item: str) -> bool:
	return _nonempty(unit.dir / "mindmap/mindmap.svg")
