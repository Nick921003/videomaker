from . import ROOT, BOARD_DIR, MODEL, Command, UnitView


INGEST = {
	"id": "ingest",
	"name": "教材整理",
	"scope": "unit",
	"status": "available",
	"preview": "none",
	"steps": [
		{
			"id": "extract",
			"name": "本機抽取",
			"model": "本機",
			"paid": False,
			"cost": "免費",
			"detail": "讀取 PDF 或 PPTX 的文字；上限 5 MB、30 頁、6 萬字。"
		},
		{
			"id": "normalize",
			"name": "教材整理（確認後執行）",
			"model": "google:gemini-3.8-flash",
			"paid": True,
			"cost": "依實際用量計費",
			"detail": "修復換行、閱讀順序與辨識雜訊，逐頁核對引用並保留疑點。"
		}
	],
	"planned_note": None
}


ANALYSIS = {
	"id": "analysis",
	"name": "教材分析",
	"scope": "unit",
	"status": "available",
	"preview": "none",
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
			"id": "plan",
			"name": "教材整理（規劃）",
			"model": "google:gemini-3.8-flash",
			"cost": "約 US$0.015",
			"detail": "整理學生會問的問題故事、建議秒數、詞彙表（含程式符號唸法）、必演畫面與推薦重點片。",
			"paid": True
		}
	],
	"planned_note": None
}


STAGES = [INGEST, ANALYSIS]


def analysis_commands(unit: UnitView) -> list[Command]:
	return [
		Command("selftest", [str(BOARD_DIR / "selftest.py"), "--quick"]),
		Command("plan", [str(BOARD_DIR / "author.py"), "plan", str(unit.dir / "material.md"),
			str(unit.dir), "--model", MODEL, "--budget-usd", "0.50"]),
	]


def ingest_commands(upload_dir, units_root) -> list[Command]:
	return [Command("normalize", [str(ROOT / "workbench/run_normalize.py"), str(upload_dir), str(units_root)])]
