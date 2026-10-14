"""同教材只抽一次；推論結果未確認前擋製作；重抽要求與竄改都會讓快取失效。"""
import json
from pathlib import Path
import tempfile
import unittest

from studio.key_points import KeyPointsError
from tests.fixtures.key_points import model_output
from tests.fixtures.teaching_quality import MATERIAL
from workbench import key_points as W
from workbench.library import Library, read_json, write_json


class TestWorkbenchKeyPoints(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.library = Library(Path(self.temp.name))
		uid, _ = self.library.create_unit(MATERIAL)
		self.directory = self.library.unit_dir(uid)
		self.calls = []

	def complete(self, system, user, schema):
		self.calls.append(json.loads(user))
		return model_output(), {}

	def as_pdf(self):
		path = self.directory / 'material.json'
		data = read_json(path); data['sources'][0]['kind'] = 'pdf'; write_json(path, data)

	def test_cached_per_content_version(self):
		first = W.get_key_points(self.directory, self.complete)
		second = W.get_key_points(self.directory, self.complete)
		self.assertEqual(first, second)
		self.assertEqual(len(self.calls), 1)
		self.assertEqual(W.summary(self.directory)['status'], 'ready')

	def test_inferred_blocks_until_confirmed(self):
		self.as_pdf()
		with self.assertRaises(W.KeyPointsPending):
			W.get_key_points(self.directory, self.complete)
		self.assertEqual(W.summary(self.directory)['status'], 'needs_review')
		digest = W.summary(self.directory)['digest']
		with self.assertRaises(ValueError):
			W.confirm(self.directory, '0' * 64)
		W.confirm(self.directory, digest)
		value = W.get_key_points(self.directory, self.complete)
		self.assertEqual(value['status'], 'ready')
		self.assertEqual(len(self.calls), 1)

	def test_stale_confirm_cannot_approve_a_reextracted_list(self):
		# 同教材版本重抽後，舊畫面帶的 digest 不得批准新清單。
		self.as_pdf()
		W.get_key_points(self.directory, self.complete, require_ready=False)
		stale = W.summary(self.directory)['digest']
		W.request_reextract(self.directory, '')
		def changed(system, user, schema):
			# 固定的假模型兩次輸出相同，digest 也會相同；重抽要真的換了清單才有意義。
			output = model_output(); output['title'] = '重抽後的新標題'
			return output, {}
		W.get_key_points(self.directory, changed, require_ready=False)
		self.assertNotEqual(W.summary(self.directory)['digest'], stale)
		with self.assertRaises(ValueError):
			W.confirm(self.directory, stale)
		self.assertEqual(W.summary(self.directory)['status'], 'needs_review')

	def test_source_kind_change_invalidates_ready_cache(self):
		# 同一份 Markdown 改掛成 PDF 來源，結構變成推論，不能沿用已就緒的快取。
		W.get_key_points(self.directory, self.complete)
		self.as_pdf()
		self.assertIsNone(W.current(self.directory))
		with self.assertRaises(W.KeyPointsPending):
			W.get_key_points(self.directory, self.complete)
		self.assertEqual(len(self.calls), 2)

	def test_products_follow_the_current_list(self):
		W.get_key_points(self.directory, self.complete)
		digest = W.summary(self.directory)['digest']
		write_json(self.directory / 'slides/source.json', {'key_points_digest': digest})
		self.assertTrue(W.product_is_current(self.directory, 'slides/source.json'))
		W.request_reextract(self.directory, '')
		self.assertFalse(W.product_is_current(self.directory, 'slides/source.json'))
		self.assertFalse(W.product_is_current(self.directory, 'mindmap/source.json'))

	def test_reextract_invalidates_and_sends_note(self):
		W.get_key_points(self.directory, self.complete)
		W.request_reextract(self.directory, '重點放在差一錯誤')
		self.assertIsNone(W.current(self.directory))
		self.assertEqual(W.summary(self.directory)['status'], 'missing')
		W.get_key_points(self.directory, self.complete)
		self.assertEqual(len(self.calls), 2)
		self.assertEqual(self.calls[1]['note'], '重點放在差一錯誤')

	def test_reextract_without_note_still_reruns(self):
		W.get_key_points(self.directory, self.complete)
		W.request_reextract(self.directory, '')
		W.get_key_points(self.directory, self.complete)
		self.assertEqual(len(self.calls), 2)
		self.assertIsNone(self.calls[1]['note'])

	def test_reextract_note_length_limit(self):
		with self.assertRaises(ValueError):
			W.request_reextract(self.directory, '字' * 201)

	def test_rejected_candidates_are_kept_for_diagnosis(self):
		def bad(system, user, schema):
			output = model_output(); output['points'][0]['title'] = '超過十二個字的標題一定不合格'
			return output, {}
		with self.assertRaises(KeyPointsError):
			W.get_key_points(self.directory, bad)
		attempts = list((self.directory / 'key_points_attempts').glob('*.json'))
		self.assertEqual(len(attempts), 3)
		self.assertIn('problems', read_json(attempts[0]))
		self.assertIsNone(W.current(self.directory))

	def test_tampered_cache_is_refused(self):
		W.get_key_points(self.directory, self.complete)
		path = self.directory / 'key_points.json'
		value = read_json(path); value['title'] = '被改過'; write_json(path, value)
		with self.assertRaisesRegex(KeyPointsError, '快取身份不一致'):
			W.get_key_points(self.directory, self.complete)
		self.assertIsNone(W.current(self.directory))


if __name__ == '__main__':
	unittest.main()
