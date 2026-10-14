import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_paper_renderer import board_fixture
from tests.test_paper_ac_renderer import long_timeline
from video_engine import paper_renderer as r
from tests.test_paper_renderer_repair import drawn_text


def flow_board(values):
	board = board_fixture()
	board['objects'][0].update(kind='flow', values=values)
	for scene in board['scenes']:
		scene['steps'][0].update(focus='state', visible=['state'], updates=[], code_line=-1)
	return board


def crosses_interior(a,b,box):
	low, high = 0., 1.
	for axis, dimension in ((0,'x'),(1,'y')):
		minimum = box[dimension] + 2
		maximum = box[dimension] + box['w' if axis==0 else 'h'] - 2
		delta = b[axis] - a[axis]
		if abs(delta) < 1e-9:
			if not minimum < a[axis] < maximum:return False
		else:
			lo, hi = sorted(((minimum-a[axis])/delta,(maximum-a[axis])/delta))
			low, high = max(low,lo), min(high,hi)
			if high <= low:return False
	return high > low


class PaperFlowLayoutTests(unittest.TestCase):
	def test_paths_stay_outside_nodes_during_camera_and_hint_changes(self):
		board=board_fixture(True)
		board['objects'][0].update(kind='flow',values=['這個流程階段需要詳細說明']*8)
		for scene in board['scenes']:
			scene['steps'][0].update(focus='state',visible=['state','code'],updates=[],code_line=-1)
		board['scenes'][0]['steps'][0].update(focus='code',code_line=1)
		timeline=long_timeline(board)
		for at in (.5,5,8.6,9.2,10,13):
			meta=r.frame_metadata(board,timeline,at)
			r.frame_at(board,timeline,at)
			for arrow in meta['arrows']:
				slots=meta['objects'][arrow['id']]['slots']
				for points in (arrow['path'],arrow['head']):
					for a,b in zip(points,points[1:]):
						for slot in slots:self.assertFalse(crosses_interior(a,b,slot),(at,arrow,slot))

	def test_flow_labels_keep_words_and_short_chinese_phrase_together(self):
		board = flow_board(['stdio.h 已載入','編譯','main 起點','printf 輸出','return 0'])
		rows = [text for text,box in drawn_text(board,long_timeline(board),5)]
		self.assertIn('已載入',rows)
		self.assertNotIn('入',rows)
		board = flow_board(['#include']*8)
		rows = [text for text,box in drawn_text(board,long_timeline(board),5)]
		self.assertEqual(rows.count('#include'),8)

	def test_explicit_three_line_label_is_preserved_in_single_column(self):
		board = flow_board(['甲\n乙\n丙'])
		rows = [text for text,box in drawn_text(board,long_timeline(board),5)]
		for text in ('甲','乙','丙'):self.assertIn(text,rows)

	def test_five_short_steps_are_in_order_on_one_row(self):
		board = flow_board(['stdio.h 已載入','編譯','main 起點','printf 輸出','return 0'])
		with tempfile.TemporaryDirectory() as directory:
			r.render_previews(board, directory)
			layout = json.loads((Path(directory)/'layout.json').read_text())
			slots = next(obj for obj in layout['objects'] if obj['id']=='state')['slots']
		self.assertEqual(len({slot['y'] for slot in slots}), 1)
		self.assertTrue(all(a['x']+a['w'] < b['x'] for a,b in zip(slots,slots[1:])))

	def test_actual_wrapped_arrow_head_follows_last_path_segment(self):
		board = flow_board(['這個流程階段需要詳細說明']*8)
		timeline = long_timeline(board)
		meta = r.frame_metadata(board,timeline,5)
		arrow = next(a for a in meta['arrows'] if a['end'][1]>a['start'][1])
		heads=[];original=r._pencil
		def capture(draw,points,progress,color,width=3,phase=0):
			if len(points)==3 and tuple(points[1])==tuple(arrow['end']):heads.append(points)
			return original(draw,points,progress,color,width,phase)
		with patch.object(r,'_pencil',capture):r.frame_at(board,timeline,5)
		self.assertEqual(len(heads),1)
		head=heads[0];path=arrow.get('path',[arrow['start'],arrow['end']])
		shaft=(path[-1][0]-path[-2][0],path[-1][1]-path[-2][1])
		tip=(head[1][0]-(head[0][0]+head[2][0])/2,head[1][1]-(head[0][1]+head[2][1])/2)
		cosine=(shaft[0]*tip[0]+shaft[1]*tip[1])/(math.hypot(*shaft)*math.hypot(*tip))
		self.assertGreater(cosine,.99)
