"""抽取只信任片段代號；不合格時帶原因重試，三次都不過就停，不放寬。"""
import json
import unittest

from studio import key_points as K
from studio.teaching_plan import source_excerpts
from tests.fixtures.key_points import model_output, sample_key_points
from tests.fixtures.teaching_quality import MATERIAL


def by_excerpt_ids(output):
	"""把 fixture 的原文引用換成片段 id，模擬模型只回傳代號。"""
	excerpts = source_excerpts(MATERIAL)
	def ref(quote):
		normalized = ' '.join(quote.split())
		return next(item['id'] for item in excerpts if normalized in ' '.join(item['text'].split()))
	for objective in output['objectives']:
		objective['sources'] = [ref(quote) for quote in objective['sources']]
	for point in output['points']:
		point['sources'] = [ref(quote) for quote in point['sources']]
	return output


class TestBuildKeyPoints(unittest.TestCase):
	def test_structure_detection(self):
		self.assertEqual(K.structure_of(MATERIAL, ['md']), 'material')
		self.assertEqual(K.structure_of(MATERIAL, ['pdf']), 'inferred')
		self.assertEqual(K.structure_of(MATERIAL, ['md', 'pdf']), 'inferred')
		self.assertEqual(K.structure_of(MATERIAL, ['normalized_markdown']), 'inferred')
		self.assertEqual(K.structure_of('# 標題\n\n只有內容。', ['md']), 'inferred')
		self.assertEqual(K.structure_of(MATERIAL, []), 'inferred')

	def test_schema_only_allows_excerpt_ids_and_has_no_presentation_fields(self):
		excerpts = source_excerpts(MATERIAL)
		schema = K.model_schema(excerpts)
		ids = [item['id'] for item in excerpts]
		point = schema['properties']['points']['items']['properties']
		self.assertEqual(point['sources']['items']['enum'], ids)
		self.assertEqual(schema['properties']['objectives']['items']['properties']['sources']['items']['enum'], ids)
		self.assertEqual(set(point), {'id', 'title', 'question', 'type', 'objectives', 'explanation',
			'example', 'misconceptions', 'parent_id', 'sources'})

	def test_model_ids_are_restored_to_exact_text(self):
		calls = []
		def complete(system, user, schema):
			calls.append(json.loads(user))
			return by_excerpt_ids(model_output()), {}
		value = K.build_key_points(MATERIAL, complete, source_kinds=['md'])
		self.assertEqual(len(calls), 1)
		self.assertEqual(calls[0]['structure'], 'material')
		refs = {item['id']: item['text'] for item in source_excerpts(MATERIAL)}
		raw = by_excerpt_ids(model_output())
		self.assertEqual(value['points'][0]['sources'], [refs[i] for i in raw['points'][0]['sources']])
		self.assertEqual(value['status'], 'ready')
		self.assertIsNone(value['points'][0]['parent_id'])
		self.assertIsNone(value['points'][1]['example'])
		self.assertEqual(K.problems(value, MATERIAL), [])

	def test_inferred_material_starts_as_needs_review(self):
		value = K.build_key_points(MATERIAL, lambda *_: (model_output(), {}), source_kinds=['pdf'])
		self.assertEqual((value['structure'], value['status']), ('inferred', 'needs_review'))
		self.assertTrue(all(item['inferred'] for item in value['objectives']))

	def test_retry_feeds_back_problems_then_succeeds(self):
		requests, rejected = [], []
		def complete(system, user, schema):
			requests.append(json.loads(user))
			output = model_output()
			if len(requests) == 1:
				output['points'][0]['explanation'] = '長' * 151
			return output, {}
		value = K.build_key_points(MATERIAL, complete, source_kinds=['md'],
			on_rejected=lambda candidate, found: rejected.append(found))
		self.assertEqual(len(requests), 2)
		self.assertEqual(requests[0]['previous_problems'], [])
		self.assertTrue(any('超過 150 字' in item for item in requests[1]['previous_problems']))
		self.assertEqual(len(rejected), 1)
		self.assertEqual(value['points'][0]['explanation'], sample_key_points()['points'][0]['explanation'])

	def test_three_failures_stop_without_relaxing(self):
		calls = []
		def complete(system, user, schema):
			calls.append(1)
			output = model_output(); output['points'][0]['question'] = '迴圈是什麼？'
			return output, {}
		with self.assertRaises(K.KeyPointsError) as caught:
			K.build_key_points(MATERIAL, complete, source_kinds=['md'])
		self.assertEqual(len(calls), K.MAX_ATTEMPTS)
		self.assertTrue(any('泛問' in item for item in caught.exception.problems))

	def test_service_error_keeps_cause_for_busy_detection(self):
		def complete(system, user, schema):
			raise RuntimeError('429 RESOURCE_EXHAUSTED')
		with self.assertRaises(K.KeyPointsError) as caught:
			K.build_key_points(MATERIAL, complete, source_kinds=['md'])
		self.assertIn('429', str(caught.exception.__cause__))

	def test_note_is_sent_to_model(self):
		seen = []
		def complete(system, user, schema):
			seen.append(json.loads(user)['note'])
			return model_output(), {}
		K.build_key_points(MATERIAL, complete, source_kinds=['md'], note='重點放在差一錯誤')
		self.assertEqual(seen, ['重點放在差一錯誤'])

	def test_oversized_material_is_refused_before_calling_model(self):
		with self.assertRaises(K.KeyPointsError):
			K.build_key_points('字' * 30001, lambda *_: self.fail('不得呼叫模型'), source_kinds=['md'])


if __name__ == '__main__':
	unittest.main()
