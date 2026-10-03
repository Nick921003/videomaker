"""獨立紙上動畫工作：語意審稿後才合成語音。"""

from copy import deepcopy
import json
import os
from pathlib import Path
import re
import threading
import time

import numpy as np
from scipy.io import wavfile

from jobstate import Job, REVIEW_SEC
from video_engine.ingest import lesson_id_for
from video_engine.paper_contract import PaperError, build_paper_board, canonical_board
from video_engine.usage import capture_call


def render_previews(board, out_dir):
	from video_engine.paper_renderer import render_previews as render
	return render(board, out_dir)


def compile_paper_audio(board, wavs, out_dir):
	from video_engine.paper_renderer import compile_paper_audio as compile_audio
	return compile_audio(board, wavs, out_dir)


def _load_synth():
	try:
		from video_engine import synth
	except SystemExit as exc:
		raise RuntimeError('本機 TTS 參考音訊設定不完整') from exc
	return synth


def _write_json(path, value):
	path = Path(path)
	partial = path.with_name(path.name + '.partial')
	try:
		partial.write_text(json.dumps(value, ensure_ascii=False, indent='\t'), encoding='utf-8')
		os.replace(partial, path)
	finally:
		if partial.exists(): partial.unlink()


def _validate_pcm(speech, sr, data):
	if type(sr) is not int or not 8000 <= sr <= 192000 or not isinstance(data, np.ndarray) or data.dtype != np.int16 or data.ndim != 1 or len(data) < sr // 50:
		raise RuntimeError('TTS 必須回傳有效 sample rate 與非空 int16 單聲道 PCM')
	# 注入音訊仍沿既有 synth 的峰值、RMS、空白與語速品質閘。
	x = data.astype(np.float32) / 32768.0
	n = sr // 50
	energy = np.sqrt((x[:len(x) // n * n].reshape(-1, n) ** 2).mean(1))
	peak = float(np.abs(x).max())
	silent = (energy < energy.max() * .02) | (energy < .015)
	voiced = float((~silent).sum() * .02)
	longest, current = 0, 0
	for silence in silent:
		current = current + 1 if silence else 0
		longest = max(longest, current)
	ratio = voiced / (len(speech) / 6.35)
	if peak < .15 or longest * .02 > 1.5 or not .55 <= ratio <= 1.9:
		raise RuntimeError('TTS 音訊未通過峰值、空白或旁白長度品質閘')


def _speech_fragments(speech, maximum, minimum):
	# 保留所有標點，並預留最短尾段；既有 safe_fragments 不限制無標點長句。
	fragments = []
	while len(speech) > maximum:
		limit = min(maximum, len(speech) - minimum)
		ends = [i + 1 for i, ch in enumerate(speech[:limit]) if ch in '，。！？、；：,.!?;' and i + 1 >= minimum]
		cut = ends[-1] if ends else limit
		fragments.append(speech[:cut])
		speech = speech[cut:]
	if speech: fragments.append(speech)
	if any(len(fragment) < minimum or not re.search(r'[\u4e00-\u9fff]', fragment) for fragment in fragments):
		raise RuntimeError('旁白無法安全分段；請改寫為自然中文，避免獨立英文或過短片段')
	return fragments


class PaperVideoJob(Job):
	def __init__(self, material_path, out_dir, sec, complete_json, instruction='', synthesizer=None, renderer=None, duration_range=None):
		super().__init__(material_path, out_dir, sec, runner=None)
		self.complete_json = complete_json
		self.instruction = instruction
		self.duration_range = deepcopy(duration_range)
		self.synthesizer = synthesizer
		self.renderer = renderer
		stem = lesson_id_for(material_path)
		self.reserved_dir = Path(out_dir) / stem
		self.board_path = str(self.reserved_dir / 'board.json')
		self.usage_path = str(self.reserved_dir / 'usage.json')
		self.layout_path = str(self.reserved_dir / 'layout.json')
		self.video_path = str(self.reserved_dir / f'{stem}.mp4')
		self.board = None
		self.material = None
		self.cancelled = threading.Event()
		self.worker_done = threading.Event()
		self.worker_done.set()
		self.stage_seconds = {}
		self.actual_duration_seconds = None
		self._work_lock = threading.RLock()
		self._worker_active = False

	def _check_cancelled(self):
		if self.cancelled.is_set(): raise RuntimeError('紙上動畫工作已取消')

	def production_metrics(self):
		bounds, actual = self.duration_range, self.actual_duration_seconds
		return {'stage_seconds':dict(self.stage_seconds), 'processing_seconds':sum(self.stage_seconds.values()),
			'actual_duration_seconds':actual, 'duration_range':deepcopy(bounds),
			'within_requested_range':bounds['min_seconds'] <= actual <= bounds['max_seconds'] if bounds and actual is not None else None}

	def _begin(self, expected):
		with self._work_lock:
			if self.cancelled.is_set():
				self.status = 'failed'
				self.error = '紙上動畫工作已取消'
				return False
			if self.status != expected or self._worker_active:
				raise RuntimeError('紙上動畫工作狀態不允許執行')
			self._worker_active = True
			self.worker_done.clear()
			self.status = 'running'
			return True

	def _finish_worker(self, awaiting_review=False):
		with self._work_lock:
			if self.cancelled.is_set():
				self.status = 'failed'
				self.error = '紙上動畫工作已取消'
			self._worker_active = False
			self.worker_done.set()
			# 審稿是下一個 worker 的入口，必須等 usage 落盤與前一個 worker 交接完成。
			if awaiting_review and self.status == 'running':
				self.review_deadline = self.clock() + REVIEW_SEC
				self.status = 'awaiting_review'

	def _stage(self, name, function):
		self._check_cancelled()
		self.stage = name
		self.events.append({'event': 'stage_start', 'stage': name})
		started = time.monotonic()
		try:
			result = function()
		finally:
			self.stage_seconds[name] = self.stage_seconds.get(name, 0) + time.monotonic() - started
		self._check_cancelled()
		self.done_stages.add(name)
		self.events.append({'event': 'stage_end', 'stage': name})
		return result

	def _fail(self, exc):
		self.error = str(exc)
		self.status = 'failed'
		self.events.append({'event': 'stage_fail', 'stage': self.stage, 'tail': str(exc)})

	def start(self):
		if not self._begin('queued'): return
		ready_for_review = False
		try:
			self.reserved_dir.mkdir(parents=True, exist_ok=True)
			self.material = Path(self.material_path).read_text(encoding='utf-8')
			def generate():
				complete = lambda *args: capture_call(self.usage, 'lesson', self.complete_json, *args)
				return build_paper_board(self.material, self.instruction, self.sec, complete, self.duration_range)
			self.board = self._stage('lesson', generate)
			_write_json(self.board_path, self.board)
			self._stage('slides', lambda: render_previews(self.board, self.reserved_dir))
			self._stage('actions', lambda: None)
			self._stage('validate', lambda: canonical_board(self.board, self.material))
			self._stage('storyboard', lambda: None)
			self._check_cancelled()
			ready_for_review = True
		except (Exception, SystemExit) as exc:
			self._fail(exc)
		finally:
			try:
				if self.reserved_dir.is_dir():
					_write_json(self.usage_path, self.usage.summary())
					_write_json(self.reserved_dir / 'production_metrics.json', self.production_metrics())
			except (Exception, SystemExit) as exc:
				self._fail(exc)
			self._finish_worker(awaiting_review=ready_for_review)

	def claim(self):
		with self._work_lock:
			if self.cancelled.is_set(): return False
			return super().claim()

	def review_segments(self):
		with self._work_lock:
			return [{'slide_id': scene['id'], 'idx': index, 'text': step['speech']}
				for scene in self.board['scenes'] for index, step in enumerate(scene['steps'])]

	def submit_review(self, segments):
		with self._work_lock:
			if self.status != 'awaiting_review' or self.cancelled.is_set():
				raise RuntimeError('講稿審核已由另一個請求處理')
			if not isinstance(segments, list): raise PaperError('講稿格式不正確')
			board = deepcopy(self.board)
			if segments:
				expected = {(scene['id'], index): step for scene in board['scenes'] for index, step in enumerate(scene['steps'])}
				seen = set()
				for segment in segments:
					if not isinstance(segment, dict) or set(segment) != {'slide_id', 'idx', 'text'} or not isinstance(segment['slide_id'], str) or type(segment['idx']) is not int:
						raise PaperError('講稿 ID 或欄位不合法')
					key = (segment['slide_id'], segment['idx'])
					if key not in expected or key in seen: raise PaperError('講稿 ID 不存在或重複')
					seen.add(key)
					expected[key]['speech'] = segment['text']
				if seen != set(expected): raise PaperError('講稿必須包含所有段落')
				board = canonical_board(board, self.material)
				_write_json(self.board_path, board)
				self.board = board
			if not self.claim(): raise RuntimeError('講稿審核已由另一個請求處理')

	def _synthesize(self):
		wavs, fragments = {}, {}
		audio_dir = self.reserved_dir / 'audio'
		audio_dir.mkdir(exist_ok=True)
		synth = None
		if self.synthesizer is None:
			self._check_cancelled()
			synth = _load_synth()
			# 整份講稿先檢查，避免後段不安全時已耗用前段的 TTS。
			for scene in self.board['scenes']:
				for step in scene['steps']:
					_speech_fragments(step['speech'], synth.MAX_SINGLE_CHARS, getattr(synth, 'MIN_FRAG_CHARS', 12))
		for scene in self.board['scenes']:
			for step in scene['steps']:
				self._check_cancelled()
				path = audio_dir / f"{step['id']}.wav"
				if self.synthesizer is not None:
					sr, data = self.synthesizer(step['speech'])
					self._check_cancelled()
					_validate_pcm(step['speech'], sr, data)
					wavfile.write(path, sr, data)
				else:
					self._check_cancelled()
					fragments[step['id']] = []
					sr, data = self._default_speech(synth, step['speech'], fragments[step['id']])
					self._check_cancelled()
					_validate_pcm(step['speech'], sr, data)
					wavfile.write(path, sr, data)
				wavs[step['id']] = path
		_write_json(self.reserved_dir / 'speech_fragments.json', fragments)
		return wavs

	def _default_speech(self, synth, speech, fragment_records=None):
		fragments = _speech_fragments(speech, synth.MAX_SINGLE_CHARS, getattr(synth, 'MIN_FRAG_CHARS', 12))
		pieces, sample_rate = [], None
		for fragment in fragments:
			accepted = False
			for _ in range(synth.MAX_TRIES):
				# synth_one 內部會重試；在每次請求外另設取消閘，避免 close 後再呼叫 TTS。
				self._check_cancelled()
				sr, raw = synth.tts(fragment, .95)
				self._check_cancelled()
				if type(sr) is not int or not 8000 <= sr <= 192000 or not isinstance(raw, np.ndarray) or raw.dtype != np.int16 or raw.ndim != 1 or len(raw) < sr // 50:
					raise RuntimeError('本機 TTS 回傳無效 PCM')
				clean = synth.trim_and_pad(raw, sr)
				total, voiced, gap, _ = synth.analyse(sr, clean)
				peak = float(np.abs(clean.astype(np.float32) / 32768.0).max())
				accepted, _ = synth.verdict(fragment, total, voiced, gap, peak)
				if accepted: break
			if not accepted: raise RuntimeError('本機 TTS 音訊未通過品質閘')
			if sample_rate is not None and sample_rate != sr: raise RuntimeError('TTS 段落取樣率不一致')
			sample_rate = sr
			pieces.append(clean)
		gap = np.zeros(int(sample_rate * synth.FRAG_GAP_MS / 1000), dtype=np.int16)
		joined, cursor = [], 0
		for fragment, piece in zip(fragments, pieces):
			if joined:
				joined.append(gap)
				cursor += len(gap)
			start = cursor / sample_rate
			joined.append(piece)
			cursor += len(piece)
			if fragment_records is not None:
				fragment_records.append({'text': fragment, 'start': start, 'end': cursor / sample_rate})
		return sample_rate, np.concatenate(joined)

	def resume(self):
		if not self._begin('running'): return
		try:
			wavs = self._stage('synth', self._synthesize)
			timeline = self._stage('timeline', lambda: compile_paper_audio(self.board, wavs, self.reserved_dir))
			self.actual_duration_seconds = timeline['duration']
			def render():
				renderer = self.renderer
				if renderer is None:
					from video_engine.paper_renderer import render_paper_video
					renderer = render_paper_video
				return renderer(self.board, timeline, self.reserved_dir / 'master.wav', Path(self.video_path), self.cancelled)
			self._stage('video', render)
			if not Path(self.video_path).is_file() or Path(self.video_path).stat().st_size <= 0:
				raise RuntimeError('影片檔案缺失或為空')
			if self.completion_check is not None:
				problem = self.completion_check(self)
				if problem: raise RuntimeError(problem)
			self._check_cancelled()
			self.status = 'done'
			self.stage = None
		except (Exception, SystemExit) as exc:
			self._fail(exc)
		finally:
			try:
				_write_json(self.reserved_dir / 'production_metrics.json', self.production_metrics())
			except OSError:
				pass
			self._finish_worker()

	def close(self):
		with self._work_lock:
			self.cancelled.set()
			if not self._worker_active and self.status not in ('done', 'failed'):
				self.status = 'failed'
				self.error = '紙上動畫工作已取消'
				self.worker_done.set()
