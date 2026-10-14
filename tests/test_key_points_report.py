"""對照表：左邊教材段落標題、右邊重點；補充與推論要標出來。"""
import unittest

from tests.fixtures.key_points import sample_key_points
from tests.fixtures.teaching_quality import MATERIAL
from workbench.key_points_report import render_report


class TestKeyPointsReport(unittest.TestCase):
	def test_report_lists_headings_points_and_flags(self):
		value = sample_key_points('inferred')
		value['points'][1]['objectives'] = []
		text = render_report(MATERIAL, value)
		for heading in ('學習目標', '痛點情境', '核心觀念', '為什麼這裡是小於等於', '常見錯誤'):
			self.assertIn(heading, text)
		self.assertIn('| 1 | 迴圈三要素 | for 後面括號裡為什麼用分號隔成三段？ | concept | o1 |', text)
		self.assertIn('補充', text)
		self.assertIn('（推論）', text)
		self.assertIn('needs_review', text)


if __name__ == '__main__':
	unittest.main()
