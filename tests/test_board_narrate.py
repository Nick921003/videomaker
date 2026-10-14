from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

from workbench.library import write_json


BOARD = Path(__file__).resolve().parents[1] / "video_engine/board"


def load(name):
	spec = importlib.util.spec_from_file_location("b6_test_" + name, BOARD / (name + ".py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def fake_pinyin(text, style, strict):
	return [[character if style == "initial" else character * 3] for character in text]


PINYIN = SimpleNamespace(Style=SimpleNamespace(INITIALS="initial", FINALS="final"), pinyin=fake_pinyin)


class TestASRComparison(unittest.TestCase):
	def test_repeated_sentence_is_rejected_but_scripted_repetition_is_allowed(self):
		checker = load("asr_check")
		text = "先手算預期結果，再輸入測試值，最後比對答案。"
		with patch.dict(sys.modules, {"pypinyin": PINYIN}):
			self.assertTrue(checker.judge(text, text)["ok"])
			result = checker.judge(text, text + text)
			self.assertFalse(result["ok"])
			self.assertIn("重複念", result["problems"])
			self.assertTrue(checker.judge(text + text, text + text)["ok"])
			self.assertFalse(checker.judge(text, "先手算預期結果，先手算預期結果，再輸入測試值，最後比對答案。")["ok"])

	def test_repeated_tts_is_automatically_resynthesized(self):
		module, checker = load("narrate"), load("asr_check")
		with tempfile.TemporaryDirectory() as temporary:
			directory = Path(temporary)
			scene, voice = directory / "q1.scene.json", directory / "voice"
			text = "先手算預期結果，再輸入測試值，最後比對答案。"
			write_json(scene, {"scenes": [{"beats": [{"say": text}]}]})
			checks = []
			def asr(jobs, out):
				checks.append(jobs)
				return {job["wav"]: checker.judge(text, text * (2 if len(checks) == 1 else 1)) for job in jobs}
			with redirect_stdout(io.StringIO()), patch("llm.load_env"), patch.dict(sys.modules, {"pypinyin": PINYIN}), \
				patch.object(module.sys, "argv", ["narrate.py", str(scene), str(voice), "--english", "off"]), \
				patch.object(module.gemini_tts, "synth_gemini", side_effect=fake_synth) as synth, patch.object(module, "asr_check", side_effect=asr):
				module.main()
			self.assertEqual(synth.call_count, 2)
			record = json.loads((voice / "narration.json").read_text())["beats"][0]
			self.assertTrue(record["ok"])
			self.assertEqual(record["asr"]["heard"], text)

	def test_unresolved_repetition_is_reported_after_bounded_retries(self):
		module, checker = load("narrate"), load("asr_check")
		with tempfile.TemporaryDirectory() as temporary:
			directory = Path(temporary)
			scene, voice = directory / "q1.scene.json", directory / "voice"
			text = "先手算預期結果，再輸入測試值。"
			write_json(scene, {"scenes": [{"beats": [{"say": text}]}]})
			def asr(jobs, out):
				return {job["wav"]: checker.judge(text, text + text) for job in jobs}
			output = io.StringIO()
			with redirect_stdout(output), patch("llm.load_env"), patch.dict(sys.modules, {"pypinyin": PINYIN}), \
				patch.object(module.sys, "argv", ["narrate.py", str(scene), str(voice), "--english", "off"]), \
				patch.object(module.gemini_tts, "synth_gemini", side_effect=fake_synth) as synth, patch.object(module, "asr_check", side_effect=asr):
				module.main()
			self.assertEqual(synth.call_count, module.MAX_ROUNDS)
			self.assertIn("@warn tts_repeat 第 1 句", output.getvalue())
			identity = json.loads((voice / "timing.identity.json").read_text())
			self.assertFalse(identity["beats"][0]["ok"])

	def test_fake_asr_skips_english_code_digits_and_retains_chinese_missing_check(self):
		checker = load("asr_check")
		with patch.dict(sys.modules, {"pypinyin": PINYIN}):
			for text in ("先看 sum23 的結果", "先看 UTF-8 的結果", "先看 cc123 的結果"):
				with self.subTest(text=text):
					self.assertTrue(checker.judge(text, "先看的結果")["ok"])
			self.assertFalse(checker.judge("先看畫面的結果", "先看的結果")["ok"])
			self.assertEqual(checker.judge("先看 23 的結果", "先看的結果")["missing"], ["二三"])

	def test_narrate_sends_spoken_glossary_reading_to_fake_asr(self):
		module, checker = load("narrate"), load("asr_check")
		with tempfile.TemporaryDirectory() as temporary:
			directory = Path(temporary)
			scene, voice = directory / "q1.scene.json", directory / "voice"
			write_json(scene, {"scenes": [{"beats": [{"say": "先看 sum23 和 <= 的比較", "spoken": "先看加總和小於等於的比較"}]}]})
			write_json(directory / "plan.json", {"glossary": [{"term": "<=", "say_as": "小於等於"}]})
			checked = []
			def asr(jobs, out):
				checked.extend(job["text"] for job in jobs)
				return {job["wav"]: checker.judge(job["text"], "先看和小於等於的比較") for job in jobs}
			output = io.StringIO()
			with redirect_stdout(output), patch.object(module.sys, "argv", ["narrate.py", str(scene), str(voice)]), \
				patch("llm.load_env"), patch.object(module.gemini_tts, "synth_gemini", side_effect=fake_synth) as synth, \
				patch.object(module, "asr_check", side_effect=asr), patch.dict(sys.modules, {"pypinyin": PINYIN}):
				module.main()
			self.assertEqual(checked, ["先看 sum23 和 小於等於 的比較"])
			self.assertEqual(synth.call_count, 1)
			self.assertNotIn("@warn", output.getvalue())


def fake_synth(text, wav, *args):
	with wave.open(str(wav), "wb") as handle:
		handle.setnchannels(1)
		handle.setsampwidth(2)
		handle.setframerate(24000)
		handle.writeframes(b"\0\0" * 12000)
	return {}, True, {"usd": 0.001}


class TestRedo(unittest.TestCase):
	def test_redo_3_5_bypasses_only_selected_cache_entries(self):
		module = load("narrate")
		with tempfile.TemporaryDirectory() as temporary:
			directory = Path(temporary)
			scene, voice = directory / "q1.scene.json", directory / "voice"
			texts = ["第一句", "第二句", "第三句", "第四句", "第五句"]
			write_json(scene, {"scenes": [{"beats": [{"say": text} for text in texts]}]})
			def asr(jobs, out):
				return {job["wav"]: {"ok": True, "problems": [], "missing": [], "heard": job["text"]} for job in jobs}
			with redirect_stdout(io.StringIO()), patch("llm.load_env"), \
				patch.object(module.gemini_tts, "synth_gemini", side_effect=fake_synth) as synth, patch.object(module, "asr_check", side_effect=asr):
				argv = ["narrate.py", str(scene), str(voice), "--english", "off"]
				with patch.object(module.sys, "argv", argv):
					module.main()
				records = json.loads((voice / "narration.json").read_text())["beats"]
				selected = {records[index]["wav"] for index in (2, 4)}
				before = {path.name: path.stat().st_mtime_ns for path in (voice / "audio").glob("*.wav")}
				synth.reset_mock()
				with patch.object(module.sys, "argv", [*argv, "--redo", "3,5"]):
					module.main()
				self.assertEqual([call.args[0] for call in synth.call_args_list], ["第三句", "第五句"])
				for path in (voice / "audio").glob("*.wav"):
					if path.name not in selected:
						self.assertEqual(path.stat().st_mtime_ns, before[path.name])
				self.assertEqual(len(json.loads((voice / "timing.json").read_text())), 5)

	def test_invalid_redo_is_rejected_before_tts(self):
		module = load("narrate")
		with tempfile.TemporaryDirectory() as temporary:
			scene = Path(temporary) / "q1.scene.json"
			write_json(scene, {"scenes": [{"beats": [{"say": "第一句"}]}]})
			for beats in ("0", "-1", "2", "3,", "a"):
				with self.subTest(beats=beats), redirect_stdout(io.StringIO()), patch("llm.load_env"), \
					patch.object(module.sys, "argv", ["narrate.py", str(scene), str(Path(temporary) / "voice"), "--redo", beats]), \
					patch.object(module.gemini_tts, "synth_gemini") as synth, redirect_stderr():
					with self.assertRaises(SystemExit):
						module.main()
					synth.assert_not_called()


def redirect_stderr():
	from contextlib import redirect_stderr as redirect
	return redirect(io.StringIO())


if __name__ == "__main__":
	unittest.main()
