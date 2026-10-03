import os
import unittest
from unittest.mock import patch

from video_engine import llm


class TestModelOutputBudget(unittest.TestCase):
    def test_stage_caps_are_hard_and_validate_request(self):
        self.assertEqual(llm.output_limit('mindmap'), 4096)
        self.assertEqual(llm.output_limit('paper',999999),16384)
        self.assertEqual(llm.output_limit('deck', 999999), 12288)
        self.assertEqual(llm.output_limit('lesson', 256), 256)
        for bad in (0, -1, True, 2.5, '4096'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                llm.output_limit('lesson', bad)

    def test_opus_defaults_to_medium_and_caps_each_stage(self):
        with patch.dict(os.environ, {'VIDEO_ENGINE_LLM':'anthropic:claude-opus-5-5'}):
            for stage, cap in (('lesson',8192),('deck',12288),('mindmap',4096)):
                with self.subTest(stage=stage), patch.object(llm, '_anthropic', return_value=({'ok':True},{'in':1,'out':1})) as call:
                    llm.complete_json('system','user',max_tokens=100000,stage=stage)
                    self.assertEqual(call.call_args.args[4:], (cap, 'medium'))

    def test_flash_actions_cap_and_explicit_lower_limit(self):
        with patch.dict(os.environ, {'VIDEO_ENGINE_LLM':'google:gemini-3.8-flash'}), \
             patch.object(llm, '_google', return_value=({'ok':True},{'in':1,'out':1})) as call:
            llm.complete_json('system','user',max_tokens=999999,stage='actions')
            self.assertEqual(call.call_args.args[4], 4096)
            llm.complete_json('system','user',max_tokens=500,stage='actions')
            self.assertEqual(call.call_args.args[4], 500)

    def test_ingest_text_is_capped_independently_of_global_override(self):
        with patch.dict(os.environ, {'VIDEO_ENGINE_LLM':'anthropic:claude-opus-5-5',
                                      'STUDIO_INGEST_MODEL':'gemini-3.8-flash'}), \
             patch.object(llm, '_google', return_value=({'ok':True},{'in':1,'out':1})) as call:
            data, usage = llm.complete_ingest_text_json('system','user',max_tokens=999999)
            self.assertEqual(call.call_args.args[0], 'gemini-3.8-flash')
            self.assertEqual(call.call_args.args[4], 16000)
            self.assertEqual(usage['provider'], 'google')


if __name__ == '__main__':
    unittest.main()
