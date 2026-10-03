"""可替換的教材意圖規劃器；兩者只產生 draft，不執行。"""

from copy import deepcopy
import re


class PlannerBackendError(RuntimeError):
	def __init__(self, code, safe_message):
		super().__init__(safe_message)
		self.code = code
		self.safe_message = safe_message


class RulePlannerBackend:
	_MEDIA = {
		"video": ("影片", "微課程", "video"),
		"slides": ("簡報", "投影片", "slides"),
		"pptx": ("pptx", "powerpoint"),
		"comic": ("漫畫",),
		"mindmap": ("心智圖",),
		"audio": ("音訊", "師生對話", "podcast"),
		"text": ("圖文教材",),
		"interactive": ("互動教材", "引導式範例"),
	}
	_CAPABILITY = {"video": "video.micro_lesson.v1", "slides": "slides.lesson_deck.v1",
		"pptx": "pptx.editable_deck.v1", "mindmap": "mindmap.concept_overview.v1"}

	def plan(self, request, catalog, schema):
		if 'duration_range' in request:
			from studio.contracts import ContractError
			raise ContractError('期望片長範圍目前僅供紙上動畫測試')
		instruction = request["instruction"].lower()
		media = [kind for kind, names in self._MEDIA.items() if any(name in instruction for name in names)]
		base = {"contract_version": "1.0", "source": deepcopy(request["source"]),
			"summary": "依教材建立學習產物", "questions": [], "warnings": [], "steps": []}
		duration_matches = re.findall(r"(?<!\d)(\d+)\s*秒", instruction)
		available = {item["id"] for item in catalog if item.get("availability") == "available"}
		if len(media) != 1 or len(duration_matches) > 1:
			base.update(status="needs_clarification", questions=[
				{"code": "media", "message": "請指定一種目前可用的教材產物。"}])
			return base
		kind = media[0]
		capability_id = self._CAPABILITY.get(kind)
		if capability_id is None or (kind != "video" and capability_id not in available) or (
			kind == "video" and catalog and capability_id not in available):
			base.update(status="needs_clarification", questions=[
				{"code": "media", "message": "這種教材產物尚未開放，請選擇目前可用的種類。"}])
			return base
		if kind == "video":
			duration = int(duration_matches[0]) if duration_matches else 110
			if duration < 30 or duration > 600:
				base.update(status="needs_clarification", questions=[
					{"code": "duration", "message": "影片長度請設定為 30 到 600 秒。"}])
				return base
			options = {"duration_seconds": duration, "layout": "auto"}
			summary = f"建立一支 {duration} 秒微課程影片"
			step_id = "video-1"
		else:
			options = {}
			summary = {"slides": "建立線上簡報", "mindmap": "建立概念心智圖"}.get(kind, "建立可編輯 PPTX")
			step_id = "mindmap-1" if kind == "mindmap" else "deck-1"
		base.update(status="ready", summary=summary,
			steps=[{"step_id": step_id, "action": "artifact.generate",
				"capability_id": capability_id, "options": options, "requires": []}])
		return base


class PaperTestPlannerBackend:
	"""僅供獨立測試頁使用；不改普通媒體意圖規劃。"""
	def plan(self, request, catalog, schema):
		bounds = request.get('duration_range')
		matches = re.findall(r"(?<!\d)(\d+)\s*秒", request["instruction"])
		base = {"contract_version": "1.0", "source": deepcopy(request["source"]),
			"questions": [], "warnings": ["新影片風格測試；實際片長依旁白音訊，驗收後才納入正式流程。"], "steps": []}
		duration = (bounds['min_seconds'] + bounds['max_seconds']) // 2 if bounds else int(matches[0]) if len(matches) == 1 else 110
		if (not bounds and len(matches) > 1) or not 30 <= duration <= 600:
			return dict(base, status="needs_clarification", summary="請確認測試影片長度",
				questions=[{"code":"duration","message":"請指定一個30到600秒的目標片長。"}])
		options = {'duration_seconds':duration}
		if bounds:
			options['duration_range'] = deepcopy(bounds)
		label = f"期望{bounds['min_seconds']}–{bounds['max_seconds']}秒，重點講清楚優先" if bounds else f"目標{duration}秒"
		return dict(base, status="ready", summary=f"測試紙上連續動畫（A＋C），{label}",
			steps=[{"step_id":"paper-1","action":"artifact.generate","capability_id":"video.paper_preview.v1",
				"options":options,"requires":[]}])


class StructuredAiPlannerBackend:
	def __init__(self, complete_json):
		self._complete_json = complete_json

	def plan(self, request, catalog, schema):
		try:
			raw = self._complete_json("受控教材規劃器", {"request": request, "catalog": catalog}, schema)
		except TimeoutError as exc:
			raise PlannerBackendError("planner_timeout", "AI 規劃服務逾時") from exc
		except Exception as exc:
			raise PlannerBackendError("planner_unavailable", "AI 規劃服務暫時無法使用") from exc
		if not isinstance(raw, dict):
			raise PlannerBackendError("invalid_planner_response", "AI 規劃回應格式錯誤")
		if raw.get("source") != request["source"]:
			raise PlannerBackendError("source_changed", "AI 規劃不得更換教材來源")
		return raw
