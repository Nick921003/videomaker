"""兩個 runner 共用一次抽取；推論結果未確認時停在待確認，不產出成品。"""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from tests.fixtures.key_points import model_output
from tests.fixtures.teaching_quality import MATERIAL
from workbench import formats, run_mindmap, run_slides
from workbench.formats import UnitView
from workbench.jobs import parse_marker
from workbench.library import Library, read_json, write_json


class TestKeyPointsRunners(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.library = Library(Path(self.temp.name))
		uid, _ = self.library.create_unit(MATERIAL)
		self.directory = self.library.unit_dir(uid)
		self.calls = 0

	def complete(self, system, user, schema):
		self.calls += 1
		return model_output(), {}

	def run_runner(self, module):
		output = StringIO()
		with contextlib.redirect_stdout(output):
			status = module.main([str(self.directory), '--quality', 'keypoints'], self.complete)
		return status, [parse_marker(line) for line in output.getvalue().splitlines()]

	def test_one_extraction_feeds_both_outputs(self):
		self.assertEqual(self.run_runner(run_slides)[0], 0)
		self.assertEqual(self.run_runner(run_mindmap)[0], 0)
		self.assertEqual(self.calls, 1)
		deck = read_json(self.directory / 'slides/deck.json')
		self.assertEqual(deck['contract_version'], '1.3')
		self.assertTrue((self.directory / 'slides/deck.pptx').stat().st_size > 0)
		self.assertEqual(read_json(self.directory / 'mindmap/mindmap.json')['contract_version'], '1.2')
		self.assertIn(b'data-handout-page="2"', (self.directory / 'mindmap/mindmap.svg').read_bytes())

	def test_inferred_material_stops_at_review(self):
		path = self.directory / 'material.json'
		data = read_json(path); data['sources'][0]['kind'] = 'pdf'; write_json(path, data)
		status, markers = self.run_runner(run_slides)
		self.assertEqual(status, 1)
		self.assertIn('key_points_review', json.dumps(markers, ensure_ascii=False))
		self.assertFalse((self.directory / 'slides/deck.pptx').exists())
		self.assertTrue((self.directory / 'key_points.json').exists())

	def test_formats_default_to_keypoints(self):
		view = UnitView('x', self.directory, None)
		for module in (formats.slides, formats.mindmap):
			argv = module.commands(view, module.FORMAT['id'])[0].argv
			self.assertEqual(argv[argv.index('--quality') + 1], 'keypoints')

	def test_reextract_makes_existing_products_not_done(self):
		from workbench.key_points import request_reextract
		self.assertEqual(self.run_runner(run_slides)[0], 0)
		self.assertEqual(self.run_runner(run_mindmap)[0], 0)
		view = UnitView('x', self.directory, None)
		self.assertTrue(formats.slides.is_done(view, 'slides'))
		self.assertTrue(formats.mindmap.is_done(view, 'mindmap'))
		record = read_json(self.directory / 'slides/source.json')
		self.assertEqual(len(record['key_points_digest']), 64)
		request_reextract(self.directory, '')
		self.assertFalse(formats.slides.is_done(view, 'slides'))
		self.assertFalse(formats.mindmap.is_done(view, 'mindmap'))


if __name__ == '__main__':
	unittest.main()
