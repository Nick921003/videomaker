import copy
import importlib
from pathlib import Path
import re
import unittest

from tests.test_paper_renderer import board_fixture, timeline_fixture


def compact(text):
	return re.sub(r'\s+', '', text)


class PaperSubtitleTests(unittest.TestCase):
	def helper(self):
		self.assertTrue((Path(__file__).resolve().parents[1] / 'video_engine/paper_subtitles.py').is_file(), '完整旁白字幕尚未實作')
		return importlib.import_module('video_engine.paper_subtitles')

	def test_complete_speech_preserves_punctuation_and_uses_measured_step(self):
		helper = self.helper()
		board = board_fixture()
		speech = '先保留原本的資料，接著沿著路徑移動每一個值。\n請觀察終止符號的位置，讀取到這裡就停止，不要把後面的資料再讀進來！'
		board['scenes'][0]['steps'][0]['speech'] = speech
		cues = helper.build_subtitle_cues(board, timeline_fixture(board))
		first = [c for c in cues if c['step_id'] == 'b0']
		self.assertGreater(len(first), 1)
		self.assertEqual(compact(''.join(c['text'] for c in first)), compact(speech))
		self.assertNotIn(board['scenes'][0]['steps'][0]['caption'], ''.join(c['text'] for c in first))
		self.assertTrue(all(0 < len(c['text']) <= 36 for c in first))
		self.assertTrue(all(c['timing_basis'] == 'measured_step_character_estimate' for c in first))
		self.assertEqual(first[0]['start'], 0)
		self.assertEqual(first[-1]['end'], 1)
		for left, right in zip(first, first[1:]): self.assertEqual(left['end'], right['start'])

	def test_short_natural_sentences_stay_at_punctuation(self):
		helper = self.helper()
		board = board_fixture()
		speech = '第一個值先寫進資料格。接著第二個值沿著路徑移動。最後停在正確的位置。'
		board['scenes'][0]['steps'][0]['speech'] = speech
		cues = [c for c in helper.build_subtitle_cues(board, timeline_fixture(board)) if c['step_id'] == 'b0']
		self.assertTrue(all(c['text'][-1] in '。！？' for c in cues))
		self.assertEqual(compact(''.join(c['text'] for c in cues)), compact(speech))

	def test_fragments_keep_measured_boundaries_and_do_not_fill_gap(self):
		helper = self.helper()
		board = board_fixture()
		speech = board['scenes'][1]['steps'][0]['speech']
		cut = speech.index('，') + 1
		fragments = {'b1': [{'text': speech[:cut], 'start': .02, 'end': .3}, {'text': speech[cut:], 'start': .42, 'end': .98}]}
		cues = helper.build_subtitle_cues(board, timeline_fixture(board), fragments)
		measured = [c for c in cues if c['step_id'] == 'b1']
		self.assertEqual(len(measured), 2)
		self.assertAlmostEqual(measured[0]['start'], 1.22)
		self.assertAlmostEqual(measured[0]['end'], 1.5)
		self.assertAlmostEqual(measured[1]['start'], 1.62)
		self.assertAlmostEqual(measured[1]['end'], 2.18)
		self.assertEqual({c['timing_basis'] for c in measured}, {'measured_fragment'})
		self.assertEqual(helper.subtitle_at(cues, 1.55), '')
		self.assertEqual(helper.subtitle_at(cues, 1.22), speech[:cut])
		self.assertEqual(helper.subtitle_at(cues, 2.2), '')
		self.assertEqual(helper.subtitle_at(cues, -1), '')
		self.assertEqual(helper.subtitle_at(cues, 4), '')
		self.assertTrue(all(c['timing_basis'] == 'measured_step_character_estimate' for c in cues if c['step_id'] != 'b1'))

	def test_long_measured_fragment_splits_only_within_its_boundaries(self):
		helper = self.helper()
		board = board_fixture()
		speech = '資料' * 35 + '，接著停止。'
		board['scenes'][0]['steps'][0]['speech'] = speech
		cues = helper.build_subtitle_cues(board, timeline_fixture(board), {'b0': [{'text': speech, 'start': .1, 'end': .9}]})
		first = [c for c in cues if c['step_id'] == 'b0']
		self.assertGreater(len(first), 2)
		self.assertEqual(first[0]['start'], .1)
		self.assertEqual(first[-1]['end'], .9)
		self.assertEqual(compact(''.join(c['text'] for c in first)), compact(speech))
		self.assertEqual({c['timing_basis'] for c in first}, {'measured_fragment_character_estimate'})

	def test_invalid_fragment_text_times_and_unknown_steps_rejected(self):
		helper = self.helper()
		board = board_fixture()
		speech = board['scenes'][0]['steps'][0]['speech']
		valid = {'text': speech, 'start': 0, 'end': 1}
		invalid = [[], [{'text': speech[:-1], 'start': 0, 'end': 1}], [{'text': speech + '多字', 'start': 0, 'end': 1}],
			[{**valid, 'start': True}], [{**valid, 'start': -.01}], [{**valid, 'end': float('nan')}],
			[{**valid, 'end': float('inf')}], [{**valid, 'end': 1.01}], [{**valid, 'end': 0}],
			[{**valid, 'text': ''}], [{**valid, 'start': '0'}],
			[{'text': speech[:10], 'start': 0, 'end': .6}, {'text': speech[10:], 'start': .5, 'end': 1}]]
		for value in invalid:
			with self.subTest(fragments=value), self.assertRaises(ValueError):
				helper.build_subtitle_cues(board, timeline_fixture(board), {'b0': value})
		with self.assertRaises(ValueError): helper.build_subtitle_cues(board, timeline_fixture(board), {'unknown': [valid]})

	def test_invalid_timeline_and_nonfinite_seek_rejected(self):
		helper = self.helper()
		board = board_fixture()
		for mutate in ['start', 'end', 'duration', 'step_id', 'missing', 'overlap']:
			tl = copy.deepcopy(timeline_fixture(board))
			if mutate == 'start': tl['steps'][0]['start'] = False
			elif mutate == 'end': tl['steps'][0]['end'] = float('nan')
			elif mutate == 'duration': tl['duration'] = -1
			elif mutate == 'step_id': tl['steps'][0]['step_id'] = 'unknown'
			elif mutate == 'missing': tl['steps'].pop()
			else: tl['steps'][1]['start'] = .5
			with self.subTest(mutate=mutate), self.assertRaises(ValueError): helper.build_subtitle_cues(board, tl)
		for t in [float('nan'), float('inf'), True]:
			with self.assertRaises(ValueError): helper.subtitle_at([], t)

	def test_fragment_start_cannot_be_after_audio_even_with_float_tail_tolerance(self):
		helper = self.helper()
		board = board_fixture()
		speech = board['scenes'][0]['steps'][0]['speech']
		with self.assertRaises(ValueError):
			helper.build_subtitle_cues(board, timeline_fixture(board), {'b0': [{'text': speech, 'start': 1 + 1e-10, 'end': 1 + 2e-10}]})

	def validator(self):
		helper = self.helper()
		self.assertTrue(hasattr(helper, 'validate_subtitle_cues'), '注入字幕尚未驗證')
		return helper

	def test_injected_complete_cues_validate_with_all_supported_bases(self):
		helper = self.validator()
		board = board_fixture()
		tl = timeline_fixture(board)
		cues = helper.build_subtitle_cues(board, tl)
		for cue, basis in zip(cues, ['measured_fragment', 'measured_fragment_character_estimate', 'measured_step_character_estimate']):
			cue['timing_basis'] = basis
		before = copy.deepcopy(cues)
		self.assertEqual(helper.validate_subtitle_cues(board, tl, cues), cues)
		self.assertEqual(cues, before)

	def test_injected_invalid_cue_fields_text_and_times_rejected(self):
		helper = self.validator()
		board = board_fixture()
		tl = timeline_fixture(board)
		cues = helper.build_subtitle_cues(board, tl)
		mutations = [('step_id', 'unknown'), ('step_id', []), ('start', False), ('start', float('nan')),
			('end', float('inf')), ('end', -.1), ('end', 1.01), ('start', -.01),
			('text', ''), ('text', ' \n '), ('text', cues[0]['text'][:-1]), ('text', cues[0]['text'] + '多字'),
			('text', board['scenes'][0]['steps'][0]['caption']), ('timing_basis', 'forced_alignment'), ('timing_basis', [])]
		for field, value in mutations:
			bad = copy.deepcopy(cues)
			bad[0][field] = value
			with self.subTest(field=field, value=value), self.assertRaises(ValueError): helper.validate_subtitle_cues(board, tl, bad)
		for bad in [None, {}, [], cues[:-1], list(reversed(cues)), [None] + cues[1:]]:
			with self.subTest(cues=bad), self.assertRaises(ValueError): helper.validate_subtitle_cues(board, tl, bad)

	def test_injected_cues_reject_overlap_within_step_and_invalid_timeline(self):
		helper = self.validator()
		board = board_fixture()
		board['scenes'][0]['steps'][0]['speech'] = '資料' * 35 + '，停止。'
		tl = timeline_fixture(board)
		cues = helper.build_subtitle_cues(board, tl)
		bad = copy.deepcopy(cues)
		bad[1]['start'] = bad[0]['end'] - .01
		with self.assertRaises(ValueError): helper.validate_subtitle_cues(board, tl, bad)
		tl['steps'][0]['end'] = float('nan')
		with self.assertRaises(ValueError): helper.validate_subtitle_cues(board, tl, cues)
