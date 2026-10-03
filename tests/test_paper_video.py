from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from studio.paper_video import PaperVideoJob
from studio.paper_video_facade import PaperVideoJobFacade
from studio.video_facade import FacadeError
from tests.test_paper_contract import WATER_SOURCE, water_board
from video_engine.ingest import lesson_id_for


def previews(board, out):
	layout = {'slides': [{'slide_id': scene['id']} for scene in board['scenes']]}
	Path(out, 'layout.json').write_text(json.dumps(layout))
	for n in range(len(board['scenes'])): Path(out, f'slide_{n+1:02d}_full.png').write_bytes(b'png')
	return layout


def pcm(speech):
	sr = 16000
	data = (np.sin(np.arange(int(sr * len(speech) / 6.35)) * 2 * np.pi * 200 / sr) * 16000).astype(np.int16)
	return sr, data


class Releases:
	def __init__(self): self.calls = []
	def release_path(self, path): self.calls.append(path)
	def release(self, owner): self.calls.append(owner)


class PaperVideoTests(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.addCleanup(self.tmp.cleanup)
		self.root = Path(self.tmp.name)
		self.source = self.root / 'studio_job_test.txt'
		self.source.write_text(WATER_SOURCE)
		self.calls = []
		def complete(*args):
			self.calls.append(args)
			return water_board(), {'provider': 'google', 'model': 'gemini-3.8-flash', 'in': 10, 'out': 20}
		self.job = PaperVideoJob(self.source, self.root / 'out', 60, complete, synthesizer=pcm,
			renderer=lambda board, timeline, audio, path, cancelled: Path(path).write_bytes(b'video'))
		self.preview_patch = patch('studio.paper_video.render_previews', previews)
		self.preview_patch.start()
		self.addCleanup(self.preview_patch.stop)
		self.store, self.slot = Releases(), Releases()
		self.facade = PaperVideoJobFacade(self.job, 'job1', 'plan1', {'original_name': 'water.txt', 'revision': 1},
			self.source, self.store, self.slot, 'owner1')
		self.job.completion_check = self.facade.completion_check
		self.addCleanup(self.facade.close)

	def test_start_private_paths_usage_review_and_preview(self):
		self.facade.start()
		self.assertEqual(self.job.status, 'awaiting_review')
		reserved = self.root / 'out' / lesson_id_for(self.source)
		self.assertEqual(Path(self.job.board_path).parent, reserved)
		self.assertEqual(Path(self.job.video_path), reserved / f'{lesson_id_for(self.source)}.mp4')
		self.assertEqual(len(self.calls), 1)
		self.assertEqual(self.facade.snapshot()['capability_id'], 'video.paper_preview.v1')
		self.assertEqual(self.job.usage.summary()['total_tokens'], 30)
		review = self.facade.get_review()
		self.assertEqual(review['segments'][0]['slide_id'], 's1')
		self.assertEqual(review['segments'][0]['idx'], 0)
		self.assertTrue(Path(self.facade.slide_path('s1')).is_file())
		self.assertEqual(len(self.store.calls), 0)

	def test_review_validates_all_ids_before_atomic_speech_edit(self):
		self.facade.start()
		original = Path(self.job.board_path).read_bytes()
		segments = self.facade.get_review()['segments']
		for corrupt in ['duplicate', 'missing', 'idx', 'too_long', 'field']:
			bad = deepcopy(segments)
			if corrupt == 'duplicate': bad[1] = deepcopy(bad[0])
			elif corrupt == 'missing': bad.pop()
			elif corrupt == 'idx': bad[0]['idx'] = False
			elif corrupt == 'too_long': bad[0]['text'] = '水' * 161
			else: bad[0]['focus'] = 'other'
			with self.assertRaises(FacadeError): self.facade.submit_review(bad)
			self.assertEqual(self.job.status, 'awaiting_review')
			self.assertEqual(Path(self.job.board_path).read_bytes(), original)
		segments[0]['text'] = '請仔細觀察水在受熱之後，如何轉變成水氣。'
		with patch.object(self.facade, '_resume_async'):
			self.assertTrue(self.facade.submit_review(segments)['ok'])
		updated = json.loads(Path(self.job.board_path).read_text())
		expected = water_board(); expected['scenes'][0]['steps'][0]['speech'] = segments[0]['text']
		self.assertEqual(updated, expected)
		self.assertEqual(len(self.calls), 1)
		with self.assertRaises(FacadeError): self.facade.submit_review([])

	def test_resume_audio_renderer_artifact_and_release_once(self):
		self.facade.start()
		self.assertTrue(self.job.claim())
		def compile_audio(board, wavs, out):
			self.assertEqual(set(wavs), {'b1', 'b2', 'b3'})
			self.assertTrue(all(Path(path).is_file() for path in wavs.values()))
			Path(out, 'master.wav').write_bytes(b'audio')
			return {'steps': [], 'duration': 10}
		with patch('studio.paper_video.compile_paper_audio', compile_audio): self.facade._run_resume()
		self.assertEqual(self.job.status, 'done')
		self.assertEqual(self.job.pct, 100)
		self.assertEqual(self.facade.artifacts()[0]['capability_id'], 'video.paper_preview.v1')
		self.facade.snapshot(); self.facade.close()
		self.assertEqual(len(self.store.calls), 1)
		self.assertEqual(len(self.slot.calls), 1)

	def test_callback_pcm_retains_pair_interface_and_has_no_fragment_claim(self):
		self.facade.start()
		wavs = self.job._synthesize()
		self.assertEqual(set(wavs), {'b1', 'b2', 'b3'})
		self.assertTrue((self.job.reserved_dir / 'speech_fragments.json').is_file(), '缺少實測片段紀錄')
		self.assertEqual(json.loads((self.job.reserved_dir / 'speech_fragments.json').read_text()), {})

	def test_default_tts_records_clean_pcm_boundaries_and_bounded_complete_text(self):
		from scipy.io import wavfile
		self.facade.start()
		speech = '水' * 160
		self.job.board['scenes'][0]['steps'][0]['speech'] = speech
		self.job.synthesizer = None
		requests = []
		def tts(text, speed):
			requests.append(text)
			return pcm(text)
		def clean(data, sr):
			return np.concatenate([np.zeros(80, dtype=np.int16), data, np.zeros(160, dtype=np.int16)])
		synth = SimpleNamespace(MAX_SINGLE_CHARS=70, MIN_FRAG_CHARS=12, MAX_TRIES=1, tts=tts,
			safe_fragments=lambda text: [text], trim_and_pad=clean,
			analyse=lambda sr, data: (len(data) / sr, len(data) / sr, 0, 0),
			verdict=lambda *args: (True, ''), FRAG_GAP_MS=120)
		with patch('studio.paper_video._load_synth', return_value=synth): wavs = self.job._synthesize()
		self.assertTrue(all(len(text) <= 70 for text in requests), '單次 TTS 文字超出70字')
		self.assertTrue((self.job.reserved_dir / 'speech_fragments.json').is_file(), '缺少實測片段紀錄')
		metadata = json.loads((self.job.reserved_dir / 'speech_fragments.json').read_text())
		self.assertEqual(set(metadata), {'b1', 'b2', 'b3'})
		fragments = metadata['b1']
		self.assertEqual(''.join(f['text'] for f in fragments), speech)
		self.assertEqual(len(fragments), 3)
		self.assertTrue(all(12 <= len(f['text']) <= 70 for f in fragments))
		self.assertTrue(all(len(text) <= 70 for text in requests))
		sr, data = wavfile.read(wavs['b1'])
		expected, cursor = [], 0
		for i, fragment in enumerate(fragments):
			if i:
				gap = np.zeros(int(sr * .12), dtype=np.int16)
				expected.append(gap)
				cursor += len(gap)
			self.assertEqual(fragment['start'], cursor / sr)
			piece = clean(pcm(fragment['text'])[1], sr)
			expected.append(piece)
			cursor += len(piece)
			self.assertEqual(fragment['end'], cursor / sr)
		self.assertEqual(fragments[-1]['end'], len(data) / sr)
		self.assertTrue(np.array_equal(data, np.concatenate(expected)))

	def test_default_tts_preserves_repeated_punctuation_and_avoids_short_tail(self):
		self.facade.start()
		self.job.synthesizer = None
		speech = '水' * 57 + '，？！' + '受熱' * 6
		self.job.board['scenes'][0]['steps'][0]['speech'] = speech
		synth = SimpleNamespace(MAX_SINGLE_CHARS=70, MIN_FRAG_CHARS=12, MAX_TRIES=1, tts=lambda text, speed: pcm(text),
			safe_fragments=lambda text: [text.replace('？！', '')], trim_and_pad=lambda data, sr: data,
			analyse=lambda sr, data: (len(data) / sr, len(data) / sr, 0, 0),
			verdict=lambda *args: (True, ''), FRAG_GAP_MS=120)
		with patch('studio.paper_video._load_synth', return_value=synth): self.job._synthesize()
		self.assertTrue((self.job.reserved_dir / 'speech_fragments.json').is_file(), '缺少實測片段紀錄')
		fragments = json.loads((self.job.reserved_dir / 'speech_fragments.json').read_text())['b1']
		self.assertEqual(''.join(f['text'] for f in fragments), speech)
		self.assertTrue(all(12 <= len(f['text']) <= 70 for f in fragments))

	def test_default_tts_rejects_non_cjk_fragment_before_any_request(self):
		from studio.paper_video import _speech_fragments
		speech = '中' * 65 + '，' + 'A' * 94
		with self.assertRaisesRegex(RuntimeError, '自然中文'): _speech_fragments(speech, 70, 12)
		requests = []
		synth = SimpleNamespace(MAX_SINGLE_CHARS=70, MIN_FRAG_CHARS=12, MAX_TRIES=1,
			tts=lambda text, speed: (requests.append(text) or pcm(text)), trim_and_pad=lambda data, sr: data,
			analyse=lambda sr, data: (len(data) / sr, len(data) / sr, 0, 0),
			verdict=lambda *args: (True, ''), FRAG_GAP_MS=120)
		with self.assertRaisesRegex(RuntimeError, '自然中文'): self.job._default_speech(synth, speech)
		self.assertEqual(requests, [])

	def test_default_tts_preflights_all_steps_before_first_request(self):
		self.facade.start()
		self.job.synthesizer = None
		self.job.board['scenes'][-1]['steps'][0]['speech'] = '中' * 65 + '，' + 'A' * 94
		requests = []
		synth = SimpleNamespace(MAX_SINGLE_CHARS=70, MIN_FRAG_CHARS=12, MAX_TRIES=1,
			tts=lambda text, speed: (requests.append(text) or pcm(text)), trim_and_pad=lambda data, sr: data,
			analyse=lambda sr, data: (len(data) / sr, len(data) / sr, 0, 0),
			verdict=lambda *args: (True, ''), FRAG_GAP_MS=120)
		with patch('studio.paper_video._load_synth', return_value=synth), self.assertRaisesRegex(RuntimeError, '自然中文'):
			self.job._synthesize()
		self.assertEqual(requests, [])

	def test_invalid_pcm_and_silence_fail_without_rendering(self):
		for synthesizer in [lambda _: (16000, np.zeros(32000, dtype=np.int16)),
			lambda _: (16000, np.ones((10, 2), dtype=np.int16)), lambda _: (True, np.ones(10, dtype=np.int16)),
			lambda _: (16000, np.ones(10, dtype=np.float32))]:
			with self.subTest(synthesizer=synthesizer):
				job = PaperVideoJob(self.source, self.root / 'invalid', 60, self.job.complete_json,
					synthesizer=synthesizer, renderer=lambda *args: self.fail('must not render'))
				job.start(); job.claim(); job.resume()
				self.assertEqual(job.status, 'failed')
				self.assertTrue(job.worker_done.is_set())

	def test_close_queued_awaiting_review_and_claimed_prevents_tts(self):
		for state in ['queued', 'awaiting_review', 'claimed']:
			job = PaperVideoJob(self.source, self.root / state, 60, self.job.complete_json,
				synthesizer=lambda _: self.fail('TTS after close'))
			if state != 'queued': job.start()
			if state == 'claimed': job.claim()
			job.close()
			job.start() if state == 'queued' else job.resume()
			self.assertEqual(job.status, 'failed')
			self.assertTrue(job.worker_done.is_set())

	def test_close_during_llm_and_tts_defers_release_and_stops_next_stage(self):
		for stage in ['lesson', 'synth']:
			job = PaperVideoJob(self.source, self.root / stage, 60, self.job.complete_json,
				synthesizer=pcm, renderer=lambda *args: self.fail('render after close'))
			store, slot = Releases(), Releases()
			facade = PaperVideoJobFacade(job, 'blocked', 'plan1', {'original_name': 'water.txt', 'revision': 1},
				self.source, store, slot, 'blocked-owner')
			self.addCleanup(facade.close)
			entered, leave = threading.Event(), threading.Event()
			def blocking_complete(*args):
				entered.set(); leave.wait(5)
				return water_board(), {}
			def blocking_synth(speech):
				entered.set(); leave.wait(5)
				return pcm(speech)
			job.complete_json = blocking_complete if stage == 'lesson' else job.complete_json
			job.synthesizer = blocking_synth
			if stage == 'synth': facade.start(); job.claim()
			worker = threading.Thread(target=facade.start if stage == 'lesson' else facade._run_resume)
			worker.start(); self.assertTrue(entered.wait(2))
			facade.close()
			self.assertFalse(job.worker_done.is_set())
			self.assertEqual(store.calls, [])
			leave.set(); worker.join(5)
			self.assertEqual(job.status, 'failed')
			self.assertEqual(len(store.calls), 1)
			self.assertEqual(len(slot.calls), 1)

	def test_bad_board_preserves_usage_and_single_callback(self):
		self.job.complete_json = lambda *args: ({}, {'in': 10, 'out': 5})
		self.facade.start()
		self.assertEqual(self.job.status, 'failed')
		self.assertEqual(self.job.usage.summary()['total_tokens'], 15)
		self.assertTrue(Path(self.job.usage_path).is_file())

	def test_lazy_tts_systemexit_is_terminal(self):
		self.job.synthesizer = None
		self.facade.start(); self.job.claim()
		with patch('studio.paper_video._load_synth', side_effect=SystemExit('missing ref')):
			self.facade._run_resume()
		self.assertEqual(self.job.status, 'failed')
		self.assertEqual(len(self.slot.calls), 1)

	def test_default_synth_cancel_prevents_fragment_retry(self):
		self.job.synthesizer = None
		self.facade.start(); self.job.claim()
		requests = []
		def tts(text, speed):
			requests.append(text)
			self.job.close()
			return 16000, np.zeros(32000, dtype=np.int16)
		synth = SimpleNamespace(MAX_SINGLE_CHARS=70, MAX_TRIES=3, tts=tts,
			safe_fragments=lambda speech: [speech], trim_and_pad=lambda data, sr: data,
			analyse=lambda sr, data: (2, 0, 2, 2), verdict=lambda *args: (False, 'silent'), FRAG_GAP_MS=120)
		def synth_one(text, speed, path):
			for _ in range(3): tts(text, speed)
			return {}, False
		synth.synth_one = synth_one
		with patch('studio.paper_video._load_synth', return_value=synth): self.facade._run_resume()
		self.assertEqual(self.job.status, 'failed')
		self.assertEqual(len(requests), 1)

	def test_missing_renderer_output_cannot_complete(self):
		self.job.renderer = lambda *args: None
		self.job.completion_check = None
		self.job.start(); self.job.claim()
		with patch('studio.paper_video.compile_paper_audio', return_value={}): self.job.resume()
		self.assertEqual(self.job.status, 'failed')

	def test_real_previews_and_audio_timeline_integrate_without_services(self):
		from video_engine.paper_renderer import render_previews
		with patch('studio.paper_video.render_previews', render_previews): self.facade.start()
		self.assertEqual(self.job.status, 'awaiting_review')
		self.assertTrue(Path(self.facade.slide_path('s1')).read_bytes().startswith(b'\x89PNG'))
		self.job.claim(); self.facade._run_resume()
		self.assertEqual(self.job.status, 'done')
		timeline = json.loads((self.job.reserved_dir / 'timeline.json').read_text())
		self.assertEqual([step['step_id'] for step in timeline['steps']], ['b1', 'b2', 'b3'])
		self.assertGreater(timeline['duration'], 0)
		self.assertTrue((self.job.reserved_dir / 'master.wav').is_file())

	def test_review_is_published_only_after_usage_write_and_worker_handoff(self):
		from studio.paper_video import _write_json
		entered, release = threading.Event(), threading.Event()
		def blocked_usage(path, value):
			if str(path) == self.job.usage_path:
				entered.set()
				if not release.wait(5): raise RuntimeError('test usage write was not released')
			return _write_json(path, value)
		with patch('studio.paper_video._write_json', side_effect=blocked_usage):
			worker = threading.Thread(target=self.facade.start)
			worker.start()
			try:
				self.assertTrue(entered.wait(2))
				self.assertEqual(self.job.status, 'running')
				self.assertFalse(self.job.worker_done.is_set())
				self.assertFalse(self.job.claim())
				with self.assertRaises(FacadeError): self.facade.get_review()
				with self.assertRaises(FacadeError): self.facade.submit_review([])
			finally:
				release.set()
				worker.join(5)
		self.assertEqual(self.job.status, 'awaiting_review')
		self.assertTrue(self.job.worker_done.is_set())
		with patch.object(self.facade, '_resume_async', side_effect=self.facade._run_resume):
			self.assertTrue(self.facade.submit_review([])['ok'])
		self.assertEqual(self.job.status, 'done')

	def test_snapshot_reports_actual_duration_against_requested_range(self):
		self.job.duration_range={'min_seconds':180,'max_seconds':300}
		self.job.sec=240
		self.facade.start()
		self.assertTrue(self.job.claim())
		with patch('studio.paper_video.compile_paper_audio',return_value={'duration':200,'steps':[]}):
			self.facade._run_resume()
		metrics=self.facade.snapshot()['production_metrics']
		self.assertEqual(metrics['actual_duration_seconds'],200)
		self.assertEqual(metrics['duration_range'],self.job.duration_range)
		self.assertTrue(metrics['within_requested_range'])
		self.assertGreaterEqual(metrics['processing_seconds'],0)
		self.assertIn('lesson',metrics['stage_seconds'])

	def test_failed_generation_persists_elapsed_metrics(self):
		def failed(*args):raise RuntimeError('offline API failure')
		self.job.complete_json=failed
		self.facade.start()
		self.assertEqual(self.job.status,'failed')
		path=self.job.reserved_dir/'production_metrics.json'
		self.assertTrue(path.is_file())
		self.assertIn('lesson',json.loads(path.read_text())['stage_seconds'])
