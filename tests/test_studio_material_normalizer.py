from pathlib import Path
import tempfile
import unittest

from studio.material_normalizer import NormalizationError, normalize_material, _source_quote
from studio.sources import SourceError, SourceStore


class TestMaterialNormalizer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SourceStore(Path(self.tmp.name))
        self.addCleanup(self.store.close)
        self.source = self.store.add_upload('lesson.txt', b'Photosynthesis converts light into energy.\n')
        self.record = self.store.resolve(self.source['ref'], self.source['revision'])

    def good_runner(self, system, request, pdf_bytes):
        self.assertIsNone(pdf_bytes)
        self.assertIn('Photosynthesis', request)
        return {'title':'Photosynthesis', 'pages':[{'page':1,
            'clean_text':'Photosynthesis converts light into energy.',
            'verified_quotes':['Photosynthesis converts light into energy.'],
            'visual_notes':[], 'uncertainties':[]}]}, {'model':'gemini-3.8-flash'}

    def test_normalizes_once_and_preserves_extracted_source(self):
        calls = []
        def normalizer(record):
            calls.append(record)
            return normalize_material(record, self.good_runner)
        updated = self.store.normalize(self.source['ref'], self.source['revision'], normalizer)
        self.assertEqual(updated['normalization_status'], 'complete')
        self.assertNotEqual(updated['revision'], self.source['revision'])
        self.assertEqual(updated['normalization_model'], 'gemini-3.8-flash')
        record = self.store.resolve(updated['ref'], updated['revision'])
        self.assertIn('Photosynthesis', Path(record.material_path).read_text())
        self.assertEqual(Path(record.extracted_path).read_text(), 'Photosynthesis converts light into energy.\n')
        self.assertEqual(self.store.normalize(updated['ref'], updated['revision'], normalizer), updated)
        self.assertEqual(self.store.normalize(self.source['ref'], self.source['revision'], normalizer), updated)
        self.assertEqual(len(calls), 1)

    def test_accepts_quote_when_pdf_style_line_breaks_differ(self):
        source = self.store.add_upload('wrapped.txt', '雨水經過濾網\n進入儲水桶。'.encode())
        def runner(system, request, pdf_bytes):
            return {'title':'雨水收集', 'pages':[{'page':1,
                'clean_text':'雨水經過濾網進入儲水桶。',
                'verified_quotes':['雨水經過濾網進入儲水桶。'],
                'visual_notes':[], 'uncertainties':[]}]}, {'model':'gemini-3.8-flash'}
        updated = self.store.normalize(source['ref'], source['revision'],
            lambda record: normalize_material(record, runner))
        self.assertEqual(updated['normalization_status'], 'complete')
        self.assertIn('雨水經過濾網\n  進入儲水桶。', updated['preview_excerpt'])

    def test_source_store_accepts_layout_punctuation_changes(self):
        source = self.store.add_upload('punctuation.md', '第一步：分類，第二步：比較。'.encode())
        def runner(system, request, pdf_bytes):
            return {'title':'比較方法', 'pages':[{'page':1,
                'clean_text':'先分類，再比較。',
                'verified_quotes':['第一步分類第二步比較'],
                'visual_notes':[], 'uncertainties':[]}]}, {'model':'gemini-3.8-flash'}
        updated = self.store.normalize(source['ref'], source['revision'],
            lambda record: normalize_material(record, runner))
        self.assertEqual(updated['normalization_status'], 'complete')
        self.assertIn('第一步：分類，第二步：比較', updated['preview_excerpt'])

    def test_punctuation_reflow_restores_original_evidence(self):
        self.assertEqual(_source_quote('原文：「雨水經過濾網，進入儲水桶。」',
                                       '雨水經過濾網進入儲水桶'),
                         '雨水經過濾網，進入儲水桶')
        self.assertEqual(_source_quote('步驟：先分類、再比較。',
                                       '步驟:先分類,再比較'),
                         '步驟：先分類、再比較')

    def test_punctuation_matching_keeps_numeric_and_code_operators(self):
        self.assertIsNone(_source_quote('數值是 1.5，不是 15。', '數值是 15'))
        self.assertIsNone(_source_quote('比例為 1/2。', '比例為 12'))
        self.assertIsNone(_source_quote('x-y 的值', 'xy 的值'))
        self.assertIsNone(_source_quote('成功率是 50%。', '成功率是 50。'))
        self.assertIsNone(_source_quote('樣本數為 1,000。', '樣本數為 1000'))
        self.assertIsNone(_source_quote('雨水不能飲用。', '雨水能飲用'))

    def test_unmatched_quote_on_short_source_uses_verbatim_source_and_requires_review(self):
        def bad(system, request, pdf_bytes):
            data, usage = self.good_runner(system, request, pdf_bytes)
            data['pages'][0]['verified_quotes'] = ['Fake statement']
            return data, usage
        updated = self.store.normalize(self.source['ref'], self.source['revision'],
            lambda record: normalize_material(record, bad))
        self.assertEqual(updated['normalization_status'], 'complete')
        self.assertTrue(updated['normalization_attention'])
        saved = Path(self.store.resolve(updated['ref'], updated['revision']).material_path).read_text()
        self.assertIn('Photosynthesis converts light into energy.', saved)
        self.assertIn('待核對', saved)
        self.assertNotIn('Fake statement', saved)

    def test_unmatched_quote_on_long_source_still_rejects(self):
        source = self.store.add_upload('long.txt', ('A' * 2100).encode())
        def bad(system, request, pdf_bytes):
            return {'title':'Long', 'pages':[{'page':1, 'clean_text':'Summary',
                'verified_quotes':['Fake statement'], 'visual_notes':[],
                'uncertainties':[]}]}, {}
        with self.assertRaises(SourceError) as context:
            self.store.normalize(source['ref'], source['revision'],
                lambda record: normalize_material(record, bad))
        self.assertEqual(context.exception.code, 'normalization_failed')

    def test_rejects_missing_page(self):
        def bad(system, request, pdf_bytes):
            return {'title':'Missing', 'pages':[]}, {}
        with self.assertRaises(NormalizationError): normalize_material(self.record, bad)


if __name__ == '__main__':
    unittest.main()
