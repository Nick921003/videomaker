"""完整旁白字幕；實測片段內仍以字量估排，不宣稱逐詞對齊。"""

import math
import re


def _compact(text):
	return re.sub(r'\s+', '', text)


def _number(value):
	return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _chunks(text):
	text = ' '.join(text.split())
	chunks = []
	while len(text) > 36:
		window = text[:36]
		ends = [i + 1 for i, ch in enumerate(window) if ch in '。！？.!?；;' and i >= 11]
		if not ends:
			ends = [i + 1 for i, ch in enumerate(window) if ch in '，、：,: ' and i >= 19]
		cut = ends[-1] if ends else 36
		chunks.append(text[:cut].strip())
		text = text[cut:].strip()
	if text: chunks.append(text)
	return chunks


def _scheduled(step_id, text, start, end, measured_fragment=False):
	parts = _chunks(text)
	weights = [len(_compact(part)) for part in parts]
	weight = sum(weights)
	basis = 'measured_fragment' if measured_fragment else 'measured_step_character_estimate'
	if measured_fragment and len(parts) > 1: basis = 'measured_fragment_character_estimate'
	cues, used, previous = [], 0, start
	for i, (part, count) in enumerate(zip(parts, weights)):
		used += count
		finish = end if i == len(parts) - 1 else start + (end - start) * used / weight
		cues.append({'step_id': step_id, 'start': previous, 'end': finish, 'text': part, 'timing_basis': basis})
		previous = finish
	return cues


def build_subtitle_cues(board, timeline, fragments=None):
	"""fragments 為 step_id -> [{text,start,end}]；時間是該 step WAV 局部秒數。"""
	steps = [(scene, step) for scene in board['scenes'] for step in scene['steps']]
	entries, duration = timeline.get('steps'), timeline.get('duration')
	if not isinstance(entries, list) or len(entries) != len(steps) or not _number(duration) or duration <= 0:
		raise ValueError('字幕 timeline duration／steps 無效')
	if fragments is None: fragments = {}
	ids = {step['id'] for _, step in steps}
	if not isinstance(fragments, dict) or any(key not in ids for key in fragments):
		raise ValueError('字幕 fragment 的 step ID 不存在或格式無效')
	cues, previous = [], 0
	for (scene, step), entry in zip(steps, entries):
		if not isinstance(entry, dict): raise ValueError('字幕 timeline step 格式無效')
		start, end = entry.get('start'), entry.get('end')
		if not _number(start) or not _number(end) or not previous <= start < end <= duration:
			raise ValueError('字幕 timeline 時間、順序或範圍無效')
		if entry.get('step_id') != step['id'] or entry.get('scene_id') != scene['id']:
			raise ValueError('字幕 timeline ID 不符合 board')
		previous = end
		speech = step.get('speech')
		if not isinstance(speech, str) or not _compact(speech): raise ValueError('字幕 speech 不得為空')
		if step['id'] not in fragments:
			cues.extend(_scheduled(step['id'], speech, start, end))
			continue
		items = fragments[step['id']]
		if not isinstance(items, list) or not items: raise ValueError('字幕 fragment 必須是非空 list')
		local_previous, texts = 0, []
		for item in items:
			if not isinstance(item, dict) or set(item) != {'text', 'start', 'end'}:
				raise ValueError('字幕 fragment 欄位無效')
			text, local_start, local_end = item['text'], item['start'], item['end']
			if not isinstance(text, str) or not _compact(text): raise ValueError('字幕 fragment 文字不得為空')
			if not _number(local_start) or not _number(local_end) or not local_previous <= local_start < local_end:
				raise ValueError('字幕 fragment 時間必須有限、遞增且不重疊')
			# WAV 秒數加減可能有浮點尾差，只容許數值誤差，不接受超出音長。
			if local_start >= end - start or local_end > end - start + 1e-9:
				raise ValueError('字幕 fragment 超出 step 音長')
			local_previous = local_end
			local_end = min(local_end, end - start)
			texts.append(text)
			cues.extend(_scheduled(step['id'], text, start + local_start, min(end, start + local_end), True))
		if _compact(''.join(texts)) != _compact(speech):
			raise ValueError('字幕 fragment 必須完整還原 speech，不能漏字或多字')
	return cues


def validate_subtitle_cues(board, timeline, cues):
	"""驗注入字幕的文字與時間契約，回傳獨立 list；不替錯誤字幕補字。"""
	build_subtitle_cues(board, timeline)
	if not isinstance(cues, list): raise ValueError('字幕 cues 必須是 list')
	steps = {step['id']: step for scene in board['scenes'] for step in scene['steps']}
	entries = {entry['step_id']: entry for entry in timeline['steps']}
	texts, previous = {step_id: [] for step_id in steps}, 0
	bases = ('measured_fragment', 'measured_fragment_character_estimate', 'measured_step_character_estimate')
	for cue in cues:
		if not isinstance(cue, dict) or set(cue) != {'step_id', 'start', 'end', 'text', 'timing_basis'}:
			raise ValueError('字幕 cue 欄位無效')
		step_id, start, end, text = cue['step_id'], cue['start'], cue['end'], cue['text']
		if not isinstance(step_id, str) or step_id not in steps: raise ValueError('字幕 cue 的 step ID 不存在')
		if not _number(start) or not _number(end) or not previous <= start < end:
			raise ValueError('字幕 cue 時間必須有限、遞增且不重疊')
		entry = entries[step_id]
		if not entry['start'] <= start < end <= entry['end']: raise ValueError('字幕 cue 超出所屬 step 音長')
		if not isinstance(text, str) or not _compact(text): raise ValueError('字幕 cue 文字不得為空')
		if cue['timing_basis'] not in bases: raise ValueError('字幕 cue timing_basis 不合法')
		texts[step_id].append(text)
		previous = end
	for step_id, step in steps.items():
		if _compact(''.join(texts[step_id])) != _compact(step['speech']):
			raise ValueError('字幕 cue 必須完整還原所有 speech，不能以 caption 替代或漏字多字')
	return [dict(cue) for cue in cues]


def subtitle_at(cues, t):
	"""決定性查詢；片段或 step 間的空白不延長前一句字幕。"""
	if not _number(t): raise ValueError('字幕時間必須有限')
	for cue in cues:
		if cue['start'] <= t < cue['end']: return cue['text']
	return ''
