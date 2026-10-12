"""引用由模型選片段代號，由程式恢復原文；不模糊比對或放寬來源閘。"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio import teaching_plan
from tests.fixtures.teaching_quality import MATERIAL, sample_plan
from workbench.library import Library, read_json
from workbench.teaching import get_plan


class TestTeachingReferences(unittest.TestCase):
    def test_common_teaching_plan_does_not_depend_on_a_pptx_renderer(self):
        with patch('studio.pptx_export.export_pptx', side_effect=ValueError('簡報文字過長')):
            plan = teaching_plan.build_plan(MATERIAL, lambda *_: (sample_plan(), {}))
        self.assertEqual(plan['units'][2]['visual']['states'][-1]['output'], '15')
        teaching_plan.plan_deck(plan); teaching_plan.plan_mindmap(plan)

    def test_model_selects_excerpt_ids_and_adapters_receive_exact_source_text(self):
        selected = {}
        def complete(system, user, schema):
            request = json.loads(user)
            excerpts = request['source_excerpts']
            refs = {item['id']: item['text'] for item in excerpts}
            self.assertTrue(all(text in MATERIAL for text in refs.values()))
            self.assertEqual(schema['properties']['content_version']['const'], request['content_version'])
            fields = schema['properties']['units']['items']['properties']
            self.assertEqual(fields['source_quotes']['items']['enum'], list(refs))
            self.assertEqual(fields['relation_quote']['enum'], list(refs))
            self.assertEqual(fields['details']['items']['properties']['source_quote']['enum'], list(refs))
            plan = sample_plan(); plan['contract_version'] = '1.1'
            def reference(quote):
                normalized = ' '.join(quote.split())
                return next(id for id, text in refs.items() if normalized in ' '.join(text.split()))
            for unit in plan['units']:
                unit.update(concept_label=unit['id'], parent_id='root', relation='主題',
                            relation_quote=reference(unit['source_quotes'][0]))
                unit['source_quotes'] = [reference(q) for q in unit['source_quotes']]
                for detail in unit['details']: detail['source_quote'] = reference(detail['source_quote'])
            selected.update(plan=deepcopy(plan), refs=refs)
            return plan, {}
        plan = teaching_plan.build_plan(MATERIAL, complete)
        self.assertNotIn(plan['units'][0]['explanation'], MATERIAL)
        self.assertEqual(plan['units'][0]['explanation'], selected['plan']['units'][0]['explanation'])
        for raw, unit in zip(selected['plan']['units'], plan['units']):
            self.assertEqual(unit['source_quotes'], [selected['refs'][id] for id in raw['source_quotes']])
            self.assertEqual(unit['relation_quote'], selected['refs'][raw['relation_quote']])
        teaching_plan.plan_deck(plan); teaching_plan.plan_mindmap(plan)
        self.assertEqual(teaching_plan.SCHEMA['properties']['content_version'], {'type':'string'})

    def test_catalog_is_bounded_contiguous_and_keeps_unicode_code_and_end_of_source(self):
        material = '前文\n\n```c\nprintf("%.2f V\\n", voltage);\n```\n\n' + '資料' * 1100 + '\n結尾μV'
        excerpts = teaching_plan.source_excerpts(material)
        self.assertEqual(excerpts, teaching_plan.source_excerpts(material))
        self.assertEqual(len({row['id'] for row in excerpts}), len(excerpts))
        self.assertTrue(all(0 < len(row['text']) <= 900 and row['text'] in material for row in excerpts))
        self.assertTrue(any('結尾μV' in row['text'] for row in excerpts))
        self.assertTrue(any('printf("%.2f V\\n", voltage);' in row['text'] for row in excerpts))

    def test_unknown_references_and_rewritten_quotes_still_fail_and_keep_drafts(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = Library(Path(tmp)); uid, _ = library.create_unit(MATERIAL)
            directory = library.unit_dir(uid)
            good = get_plan(directory, lambda *_: (sample_plan(), {}), configuration='good')
            for quote in ('src_does_not_exist', '把一至一百相加，不能手寫一百行。'):
                bad = sample_plan(); bad['units'][0]['source_quotes'] = [quote]
                with self.assertRaisesRegex(ValueError, '引文'):
                    get_plan(directory, lambda *_: (bad, {}), configuration='bad')
                self.assertEqual(read_json(directory/'teaching_plan.json'), good)
            drafts = list((directory/'teaching_plan_attempts').glob('*.json'))
            self.assertEqual(len(drafts), 2)
            self.assertEqual({read_json(p)['candidate']['units'][0]['source_quotes'][0] for p in drafts},
                             {'src_does_not_exist', '把一至一百相加，不能手寫一百行。'})
            self.assertTrue(all(read_json(p)['source_excerpts'] for p in drafts))
            self.assertTrue(all('units[0].source_quotes[0]' in read_json(p)['error'] for p in drafts))


if __name__ == '__main__': unittest.main()
