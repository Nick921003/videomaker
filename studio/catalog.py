"""工作台可用能力與版本化模板的唯一目錄。"""

from copy import deepcopy

from video_engine.layout import LAYOUT_MODES


CAPABILITIES = [
	{
		"id": "video.micro_lesson.v1",
		"template_id": "video.micro_lesson.default.v1",
		"kind": "video",
		"label": "微課程影片",
		"description": "帶旁白、字幕與程式碼導讀的短影片",
		"availability": "available",
		"cost_tier": "high",
		"review_gate": "script",
		"options": {
			"duration_seconds": {"type": "integer", "minimum": 30, "maximum": 600, "default": 110},
			"layout": {"type": "string", "enum": list(LAYOUT_MODES), "default": "auto"},
		},
	},
	{
		"id": "slides.lesson_deck.v1",
		"template_id": "slides.lesson_deck.default.v1",
		"kind": "slides", "label": "線上簡報",
		"description": "逐頁預覽並核可，之後下載可編輯 PPTX",
		"availability": "available", "cost_tier": "medium", "review_gate": "content", "options": {},
	},
	{
		"id": "pptx.editable_deck.v1",
		"template_id": "pptx.editable_deck.default.v1",
		"kind": "pptx", "label": "可編輯 PPTX",
		"description": "請先製作線上簡報，核可後即可下載可編輯 PPTX",
		"availability": "planned", "cost_tier": "medium", "review_gate": "content", "options": {},
	},
	{
		"id": "comic.misconception_story.v1",
		"template_id": "comic.misconception_story.default.v1",
		"kind": "comic", "label": "迷思澄清漫畫",
		"description": "用情境與概念衝突說明常見迷思",
		"availability": "planned", "cost_tier": "high", "review_gate": "content", "options": {},
	},
	{
		"id": "mindmap.concept_overview.v1",
		"template_id": "mindmap.concept_overview.default.v1",
		"kind": "mindmap", "label": "概念心智圖",
		"description": "整理概念全貌、層次與複習重點",
		"availability": "available", "cost_tier": "medium", "review_gate": "content", "options": {},
	},
	{
		"id": "audio.teacher_student.v1",
		"template_id": "audio.teacher_student.default.v1",
		"kind": "audio", "label": "師生對話音訊",
		"description": "以問答與錯誤示範輔助聆聽學習",
		"availability": "planned", "cost_tier": "high", "review_gate": "script", "options": {},
	},
	{
		"id": "text.immersive_lesson.v1",
		"template_id": "text.immersive_lesson.default.v1",
		"kind": "text", "label": "互動圖文教材",
		"description": "分段閱讀並穿插理解提問",
		"availability": "planned", "cost_tier": "medium", "review_gate": "content", "options": {},
	},
	{
		"id": "interactive.worked_example.v1",
		"template_id": "interactive.worked_example.default.v1",
		"kind": "interactive", "label": "引導式範例",
		"description": "按步驟練習與檢查除錯思路",
		"availability": "planned", "cost_tier": "medium", "review_gate": "content", "options": {},
	},
]


PAPER_CAPABILITY = {
	"id": "video.paper_preview.v1", "template_id": "video.paper_preview.paper.v1",
	"kind": "video", "label": "紙上連續動畫（A＋C）",
	"description": "測試新教材的持續狀態、跟隨鏡頭與程式走讀",
	"availability": "available", "cost_tier": "high", "review_gate": "script",
	"experimental": True,
	"options": {"duration_seconds": {"type": "integer", "minimum": 30, "maximum": 600, "default": 110},
		"duration_range": {"type": "object", "optional": True}},
}


def capability_index(include_experiments=False):
	items = CAPABILITIES + ([PAPER_CAPABILITY] if include_experiments else [])
	return {item["id"]: deepcopy(item) for item in items}


def capability_ids():
	return set(capability_index())


def get_capability(capability_id):
	return capability_index(True).get(capability_id)


def public_catalog(include_experiments=False):
	return [{key: deepcopy(value) for key, value in item.items() if key != "handler"}
		for item in capability_index(include_experiments).values()]
