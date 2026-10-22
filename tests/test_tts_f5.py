"""tts_f5 文字前端與切段；不載入模型。需要 f5 環境（~/.venvs/f5tts），缺套件就跳過。"""
import importlib.util
import os
import tempfile
import unittest

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("soundfile", "pypinyin", "numpy"))


@unittest.skipUnless(HAS_DEPS, "需要 f5 環境：~/.venvs/f5tts/bin/python -m unittest tests.test_tts_f5")
class F5NarratorTextTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		import numpy as np
		import soundfile as sf
		from tts_f5 import F5Narrator
		cls.tmp = tempfile.TemporaryDirectory()
		cls.ckpt = os.path.join(cls.tmp.name, "w.safetensors")
		open(cls.ckpt, "wb").close()
		cls.ref = os.path.join(cls.tmp.name, "ref.wav")
		sf.write(cls.ref, np.zeros(int(24000 * 5.7), np.float32), 24000)
		cls.F5Narrator = F5Narrator

	@classmethod
	def tearDownClass(cls):
		cls.tmp.cleanup()

	def narrator(self, **kw):
		return self.F5Narrator(self.ckpt, self.ref, "就是在 scanf 的時候，scanf 的時候你要在變數前面加一個 and。", **kw)

	def test_short_paragraph_is_one_chunk(self):
		# 句與句分開生成會各自收尾降調，能整段送就整段
		text = "甚至程式直接停不下來。最麻煩的是編譯器完全不會報錯，只有跑出來的結果會告訴你。"
		self.assertEqual(self.narrator().chunks(text), [text])

	def test_long_paragraph_splits_within_limit(self):
		v = self.narrator()
		text = "。".join(["第五行是迴圈本身，i 從一開始，只要 i 小於等於五就繼續跑下去"] * 6) + "。"
		chunks = v.chunks(text)
		self.assertGreater(len(chunks), 1)
		self.assertEqual("".join(chunks), text)
		for c in chunks:
			self.assertLessEqual(v.estimate(c), 22.0 - v.ref_sec)

	def test_polyphone_table_applies_after_normalizer(self):
		spoken = self.narrator().spoken("先看第 4 行，長度為 5 的陣列。")
		self.assertIn("第四航", spoken)
		self.assertIn("常度維五", spoken)

	@unittest.skipUnless(importlib.util.find_spec("f5_tts"), "需要 f5_tts")
	def test_pronunciation_table_reaches_f5_pinyin(self):
		from f5_tts.model.utils import convert_char_to_pinyin
		self.narrator(pronunciation={"垃圾": "lè sè"})
		tokens = [t for t in convert_char_to_pinyin(["帶着垃圾值"])[0] if t.strip()]
		self.assertEqual(tokens[2:4], ["le4", "se4"])

	def test_english_lead_picks_en_voice(self):
		from tts_f5 import choose_voice
		voices = {"default": {}, "en_lead": {}}
		for text in ("像 for，就是把三件事寫在同一行。", "while 迴圈會先檢查條件。"):
			self.assertEqual(choose_voice(text, voices), "en_lead", text)
		for text in ("所以如果知道次數，就優先用 for。", "第五行是迴圈本身。"):
			self.assertEqual(choose_voice(text, voices), "default", text)
		# 沒掛英文開頭聲音就退回預設，不能找不到鍵
		self.assertEqual(choose_voice("for 迴圈", {"default": {}}), "default")

	def test_voice_seed_and_reference_follow_choice(self):
		v = self.narrator(voices={"en_lead": (self.ref, "bit 的 and，也就是說。", 4)})
		calls = []
		v._infer = lambda spoken, speed, seed, voice: calls.append((seed, voice["text"])) or __import__("numpy").ones(2400, "float32") * .5
		_, en = v.chunk("像 for，就是把三件事寫在同一行。")
		_, zh = v.chunk("第五行是迴圈本身。")
		self.assertEqual((en["voice"], en["seed"]), ("en_lead", 4))
		self.assertEqual((zh["voice"], zh["seed"]), ("default", 5))
		self.assertIn("bit", calls[0][1])
		self.assertNotEqual(en["digest"], v.chunk("像 for，就是把三件事寫在同一行。", voice="default")[1]["digest"])

	def test_pronunciation_change_changes_cache_key(self):
		# 文字沒變但拼音變了，快取不能沿用舊音檔
		a = self.narrator(pronunciation={"垃圾": "lè sè"})._pron_tag
		b = self.narrator(pronunciation={"垃圾": "lā jī"})._pron_tag
		self.assertNotEqual(a, b)


if __name__ == "__main__":
	unittest.main()
