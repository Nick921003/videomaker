import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import ImageDraw
from tests.test_paper_renderer import board_fixture
from tests.test_paper_ac_renderer import long_timeline
from video_engine import paper_renderer as r


def drawn_text(board, timeline, at):
	texts = []
	original = ImageDraw.ImageDraw.text
	def capture(draw, xy, text, *args, **kwargs):
		texts.append((text, draw.textbbox(xy, text, font=kwargs.get('font'), anchor=kwargs.get('anchor'))))
		return original(draw, xy, text, *args, **kwargs)
	with patch.object(ImageDraw.ImageDraw, 'text', capture):
		r.frame_at(board, timeline, at)
	return texts


class PaperRendererRepairTests(unittest.TestCase):
	def change_board(self):
		board = board_fixture()
		board['objects'][1]['values'] = ['舊狀態', '其他資料', '保留資料']
		for scene in board['scenes']:
			scene['steps'][0].update(focus='note', visible=['note'], updates=[], code_line=-1)
		board['scenes'][1]['steps'][0].update(motion='transform', updates=[{'target':'note', 'values':['新狀態', '其他資料', '保留資料']}])
		return board

	def test_local_change_never_draws_old_and_new_together(self):
		board = self.change_board()
		timeline = long_timeline(board)
		for offset in (.02, .10, .18, .25, .4, .6, 2):
			with self.subTest(offset=offset):
				texts = [text for text, box in drawn_text(board, timeline, 8.2+offset)]
				self.assertFalse('舊狀態' in texts and '新狀態' in texts)
		texts = [text for text, box in drawn_text(board, timeline, 8.8)]
		self.assertIn('新狀態', texts)
		self.assertNotIn('舊狀態', texts)

	def test_local_change_arrives_at_its_final_text_position(self):
		board = self.change_board()
		timeline = long_timeline(board)
		arriving = next(box for text, box in drawn_text(board, timeline, 8.55) if text=='新狀態')
		settled = next(box for text, box in drawn_text(board, timeline, 9) if text=='新狀態')
		self.assertEqual(arriving, settled)

	def test_first_visible_update_and_short_step_do_not_hide_new_text(self):
		board = self.change_board()
		board['scenes'][0]['steps'][0]['updates'] = board['scenes'][1]['steps'][0]['updates']
		self.assertIn('新狀態', [text for text, box in drawn_text(board, long_timeline(board), .35)])
		board = self.change_board()
		timeline = {'duration':1.4, 'steps':[{'scene_id':'s0','step_id':'b0','start':0,'end':.3}, {'scene_id':'s1','step_id':'b1','start':.4,'end':.7}, {'scene_id':'s2','step_id':'b2','start':.8,'end':1.2}]}
		self.assertIn('新狀態', [text for text, box in drawn_text(board, timeline, .69)])
		self.assertNotIn('舊狀態', [text for text, box in drawn_text(board, timeline, .69)])

	def test_cells_word_wrap_preserves_all_characters(self):
		font = r._font('body', 40)
		for text in ('#include 無;', 'printf()  next', 'main()\n無;', '超長英文abcdefghijklmnopqrstuv'):
			rows = r._wrap(text, font, 200, True)
			self.assertEqual(''.join(rows), text.replace('\n',''))
			self.assertTrue(all(r.ImageDraw.Draw(r.Image.new('RGB',(1,1))).textlength(row,font=font)<=200 for row in rows))

	def test_cells_keep_program_identifiers_whole_in_actual_rows(self):
		board = board_fixture()
		board['objects'][0]['values'] = ['#include 無;', 'main() 無;', 'printf();', 'return 0;']
		for scene in board['scenes']:
			scene['steps'][0].update(focus='state', visible=['state'], updates=[], code_line=-1)
		with tempfile.TemporaryDirectory() as directory:
			r.render_previews(board, directory)
			layout = json.loads((Path(directory)/'layout.json').read_text())
			obj = next(obj for obj in layout['objects'] if obj['id']=='state')
			for box in obj['elements'].values():
				self.assertGreaterEqual(box['x'], obj['panel']['x'])
				self.assertLessEqual(box['x']+box['w'], obj['panel']['x']+obj['panel']['w'])
				self.assertLessEqual(box['y']+box['h'], obj['panel']['y']+obj['panel']['h'])
		rows = [text for text, box in drawn_text(board, long_timeline(board), 19)]
		for token in ('#include', 'main()', 'printf()', 'return'):
			self.assertTrue(any(token in row for row in rows), (token, rows))

	def test_hint_stays_through_code_explanation_then_retires(self):
		board = board_fixture(True)
		board['scenes'][2]['steps'][0].update(focus='state', code_line=-1)
		timeline = long_timeline(board)
		for at in (9, 12, 15, 16.1):
			self.assertIsNotNone(r.frame_metadata(board, timeline, at)['code_hint'])
		self.assertIsNone(r.frame_metadata(board, timeline, 18)['code_hint'])
		self.assertIsNone(r.frame_metadata(board, timeline, 20)['code_hint'])

	def test_reappearing_object_does_not_travel_from_its_hidden_old_position(self):
		board = board_fixture()
		for scene in board['scenes']: scene['steps'][0]['updates'] = []
		board['scenes'][1]['steps'][0].update(visible=['state'])
		board['scenes'][2]['steps'][0].update(visible=['note'], focus='note')
		timeline = long_timeline(board)
		for at in (16.4, 16.5, 16.8, 17):
			r.frame_at(board, timeline, at)
			box = r.frame_metadata(board, timeline, at)['objects']['note']['panel']
			self.assertGreaterEqual(box['y'], r.VIEW_TOP)
			self.assertLessEqual(box['y']+box['h'], r.VIEW_BOTTOM)
