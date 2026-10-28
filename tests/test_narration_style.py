import glob
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine", "board"))

import author


class NarrationStyleTest(unittest.TestCase):
	def test_every_prompt_placeholder_is_filled_by_author(self):
		# 佔位字串沒被替換就會原樣送進模型，旁白規則等於沒給
		system = open(os.path.join(ROOT, "video_engine/board/prompts/scene.system.md"), encoding="utf-8").read()
		author = open(os.path.join(ROOT, "video_engine/board/author.py"), encoding="utf-8").read()
		for name in re.findall(r"\{\{(\w+)\}\}", system):
			self.assertIn('"{{%s}}"' % name, author)

	def test_shared_style_has_taiwanese_rules_and_examples(self):
		style = open(os.path.join(ROOT, "video_engine/prompts/narration_style_tw.md"), encoding="utf-8").read()
		self.assertIn("台灣老師的講法", style)
		self.assertIn("→", style)

	def test_banned_particle_is_rejected_by_the_gate(self):
		# 提示裡寫「不要用」不保證模型照做，驗證閘才是真的擋得住的那一關
		doc = {"scenes": [{"id": "a", "beats": [{"say": "這一格要記得從零開始算喔。"}]}]}
		hits = [p for p in author.narration_problems(doc, 60) if "喔" in p]
		self.assertTrue(hits, "旁白出現「喔」時驗證閘沒回報")
		clean = {"scenes": [{"id": "a", "beats": [{"say": "這一格要記得從零開始算。"}]}]}
		self.assertFalse([p for p in author.narration_problems(clean, 60) if "喔" in p])

	def test_absolute_claims_are_rejected_by_the_gate(self):
		doc = {"scenes": [{"id": "a", "beats": [{"say": "這樣寫絕對不會出錯。"}]}]}
		hits = [p for p in author.ai_tone_problems(doc) if "絕對" in p]
		self.assertTrue(hits, "旁白把話講絕對時驗證閘沒回報")
		# 講程式行為的事實不該被擋，不然閘會被當成雜訊
		fact = {"scenes": [{"id": "a", "beats": [{"say": "條件永遠成立，迴圈就停不下來。"}]}]}
		self.assertFalse(author.ai_tone_problems(fact))

	def test_checked_in_narration_has_no_banned_particle(self):
		files = glob.glob(os.path.join(ROOT, "video_engine/examples/*.actions.json"))
		files += glob.glob(os.path.join(ROOT, "video_engine/board/examples/*.scene.json"))
		files += glob.glob(os.path.join(ROOT, "docs/experiments/*/video/*/script.md"))
		self.assertTrue(files)
		for path in files:
			with self.subTest(path=os.path.relpath(path, ROOT)):
				self.assertNotIn("喔", open(path, encoding="utf-8").read())


if __name__ == "__main__":
	unittest.main()
