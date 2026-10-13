"""重點清單驗證器：好的要過，每一種壞法都要被擋，且原因要說得出來。"""
from copy import deepcopy
import unittest

from studio.key_points import KeyPointsError, canonical_key_points, problems
from tests.fixtures.key_points import sample_key_points
from tests.fixtures.teaching_quality import MATERIAL


class TestKeyPointsContract(unittest.TestCase):
	def assert_rejected(self, value, fragment):
		found = problems(value, MATERIAL)
		self.assertTrue(any(fragment in item for item in found), found)
		with self.assertRaises(KeyPointsError) as caught:
			canonical_key_points(value, MATERIAL)
		self.assertEqual(caught.exception.problems, found)

	def test_sample_passes_and_is_isolated(self):
		value = sample_key_points()
		self.assertEqual(problems(value, MATERIAL), [])
		result = canonical_key_points(value, MATERIAL)
		result['points'][0]['title'] = '改過'
		self.assertEqual(value['points'][0]['title'], '迴圈三要素')

	def test_inferred_sample_passes_and_may_be_confirmed(self):
		value = sample_key_points('inferred')
		self.assertEqual(problems(value, MATERIAL), [])
		value['status'] = 'ready'
		self.assertEqual(problems(value, MATERIAL), [])

	def test_material_structure_must_be_ready(self):
		value = sample_key_points(); value['status'] = 'needs_review'
		self.assert_rejected(value, 'structure 為 material 時 status 必須是 ready')

	def test_inferred_flag_must_match_structure(self):
		value = sample_key_points(); value['objectives'][0]['inferred'] = True
		self.assert_rejected(value, 'inferred 與 structure 不一致')

	def test_length_limits(self):
		value = sample_key_points(); value['points'][0]['title'] = '一' * 13
		self.assert_rejected(value, 'points[0].title 超過 12 字')
		value = sample_key_points(); value['points'][1]['explanation'] = '一' * 151
		self.assert_rejected(value, 'points[1].explanation 超過 150 字')
		value = sample_key_points(); value['points'][1]['explanation'] = '一' * 150
		self.assertEqual(problems(value, MATERIAL), [])

	def test_generic_questions_are_rejected_but_specific_ones_pass(self):
		for question in ('什麼是迴圈？', '迴圈是什麼？', 'for迴圈是什麼'):
			value = sample_key_points(); value['points'][0]['question'] = question
			self.assert_rejected(value, '是泛問')
		value = sample_key_points(); value['points'][0]['question'] = '這個括號的用處是什麼？'
		self.assertEqual(problems(value, MATERIAL), [])

	def test_every_objective_must_be_covered(self):
		value = sample_key_points()
		for point in value['points']:
			point['objectives'] = ['o1']
		self.assert_rejected(value, '學習目標 o2 沒有任何重點涵蓋')

	def test_unknown_objective_reference(self):
		value = sample_key_points(); value['points'][0]['objectives'] = ['o9']
		self.assert_rejected(value, 'points[0].objectives 指向不存在或重複的學習目標')

	def test_supplementary_point_without_objectives_is_allowed(self):
		value = sample_key_points(); value['points'][1]['objectives'] = []
		self.assertEqual(problems(value, MATERIAL), [])

	def test_quotes_must_exist_verbatim(self):
		value = sample_key_points(); value['points'][0]['sources'] = ['迴圈就是重複做事。']
		self.assert_rejected(value, 'points[0].sources[0] 的引文不在教材原文中')
		value = sample_key_points(); value['objectives'][0]['sources'] = []
		self.assert_rejected(value, 'objectives[0].sources 數量須為 1–2')

	def test_parent_must_be_an_earlier_point(self):
		value = sample_key_points(); value['points'][0]['parent_id'] = 'choose'
		self.assert_rejected(value, 'points[0].parent_id 必須指向排在前面的另一個重點')
		value = sample_key_points(); value['points'][1]['parent_id'] = 'choose'
		self.assert_rejected(value, 'points[1].parent_id 必須指向排在前面的另一個重點')
		value = sample_key_points(); value['points'][1]['parent_id'] = 'nope'
		self.assert_rejected(value, 'points[1].parent_id')

	def test_presentation_fields_are_forbidden(self):
		for field in ('narration', 'layout', 'duration', 'page'):
			value = sample_key_points(); value['points'][0][field] = 'x'
			self.assert_rejected(value, f"不得有 ['{field}']")
		value = sample_key_points(); value['visual'] = {}
		self.assert_rejected(value, "多出 ['visual']")

	def test_reserved_and_duplicate_ids(self):
		for reserved in ('root', 'cover', 'mistakes'):
			value = sample_key_points(); value['points'][2]['id'] = reserved
			self.assert_rejected(value, 'points[2].id 不合法或重複')
		value = sample_key_points(); value['points'][2]['id'] = 'choose'
		self.assert_rejected(value, 'points[2].id 不合法或重複')

	def test_point_count_and_misconception_limits(self):
		value = sample_key_points(); value['points'] = value['points'][:2]
		self.assert_rejected(value, '重點數量須為 3–8')
		value = sample_key_points(); value['points'][0]['misconceptions'] *= 3
		self.assert_rejected(value, 'points[0].misconceptions 最多 2 條')
		value = sample_key_points()
		extra = deepcopy(value['points'][3]); extra['id'] = 'extra'
		value['points'].append(extra)
		for point in value['points']:
			point['misconceptions'] = deepcopy(value['points'][2]['misconceptions']) * 2
		self.assert_rejected(value, '常見錯誤總數最多 8 條')

	def test_example_shape(self):
		value = sample_key_points(); value['points'][0]['example']['language'] = ''
		self.assert_rejected(value, 'points[0].example.language 只在程式例子填寫')
		value = sample_key_points(); value['points'][1]['example'] = {'kind': 'formula', 'content': '1+2', 'language': 'c'}
		self.assert_rejected(value, 'points[1].example.language 只在程式例子填寫')
		value = sample_key_points(); value['points'][0]['example']['content'] = '\n'.join(['x'] * 13)
		self.assert_rejected(value, 'points[0].example.content 超過 12 行')

	def test_version_binding(self):
		value = sample_key_points()
		self.assertTrue(any('content_version' in item for item in problems(value, MATERIAL + '改')))


if __name__ == '__main__':
	unittest.main()
