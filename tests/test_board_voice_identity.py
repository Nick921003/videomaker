import copy
import hashlib
import io
import json
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

from tests.test_board_narrate import load
from workbench.library import write_json


def fake_voice(text, wav, *args):
	with wave.open(str(wav), "wb") as handle:
		handle.setnchannels(1)
		handle.setsampwidth(2)
		handle.setframerate(24000)
		handle.writeframes(hashlib.sha256(text.encode()).digest() * 750)
	return {}, True, {"usd": 0.001}


class TestVoiceIdentity(unittest.TestCase):
	def setUp(self):
		self.temporary = tempfile.TemporaryDirectory()
		self.addCleanup(self.temporary.cleanup)
		self.directory = Path(self.temporary.name)
		self.scene = self.directory / "scene.json"
		self.voice = self.directory / "voice"
		self.narrate = load("narrate")
		self.compiler = load("compile")
		stack = ExitStack()
		self.addCleanup(stack.close)
		self.doc = {"version": 1, "objects": [], "scenes": [{"id": "s", "beats": [
			{"say": "第一句", "spoken": "第一個句子", "do": []}, {"say": "第二句", "do": []}]}]}
		self.tts = stack.enter_context(patch.object(self.narrate.gemini_tts, "synth_gemini", side_effect=fake_voice))
		self.asr = stack.enter_context(patch.object(self.narrate, "asr_check", side_effect=lambda jobs, out: {
			job["wav"]: {"ok": True, "problems": [], "missing": [], "heard": job["text"]} for job in jobs}))
		stack.enter_context(patch("llm.load_env"))

	def generate(self, *extra):
		write_json(self.scene, self.doc)
		with redirect_stdout(io.StringIO()), patch.object(self.narrate.sys, "argv", [
			"narrate.py", str(self.scene), str(self.voice), "--english", "off", *extra]):
			self.narrate.main()
		return json.loads((self.voice / "narration.json").read_text())

	def compile(self):
		write_json(self.scene, self.doc)
		output, errors = self.directory / "timeline.json", io.StringIO()
		with redirect_stdout(io.StringIO()), redirect_stderr(errors), patch.object(self.compiler.sys, "argv", [
			"compile.py", str(self.scene), str(output), "--timing", str(self.voice / "timing.json")]):
			self.compiler.main()
		return json.loads(output.read_text()), errors.getvalue()

	def test_insert_and_reorder_reuse_audio_and_asr(self):
		before = self.generate()["beats"]
		self.tts.reset_mock()
		self.asr.reset_mock()
		self.doc["scenes"][0]["beats"] = [self.doc["scenes"][0]["beats"][1], {"say": "插入句", "do": []}, self.doc["scenes"][0]["beats"][0]]
		after = self.generate()["beats"]
		self.assertEqual([call.args[0] for call in self.tts.call_args_list], ["插入句"])
		self.assertEqual(self.asr.call_args.args[0][0]["text"], "插入句")
		self.assertEqual(after[0]["wav"], before[1]["wav"])
		self.assertEqual(after[2]["wav"], before[0]["wav"])
		self.assertEqual(after[2]["asr"], before[0]["asr"])
		self.assertEqual(after[0]["wav"], after[0]["digest"] + ".wav")

	def test_replaced_cached_audio_is_rejected_before_resigning(self):
		records = self.generate()["beats"]
		identity_before = (self.voice / "timing.identity.json").read_bytes()
		fake_voice("完全不同內容", self.voice / "audio" / records[0]["wav"])
		self.tts.reset_mock()
		self.asr.reset_mock()
		with self.assertRaisesRegex(ValueError, "快取|digest|音檔"):
			self.generate()
		self.tts.assert_not_called()
		self.asr.assert_not_called()
		self.assertEqual((self.voice / "timing.identity.json").read_bytes(), identity_before)
		with self.assertRaisesRegex(ValueError, "音檔|digest"):
			self.compile()

	def test_legacy_without_audio_hash_rechecks_asr_before_binding(self):
		report = self.generate()
		for record in report["beats"]:
			for key in ("audio_sha256", "voice_digest", "speech_digest", "wav_format"):
				record.pop(key, None)
		report.pop("cache", None)
		write_json(self.voice / "narration.json", report)
		(self.voice / "timing.identity.json").unlink()
		self.tts.reset_mock()
		self.asr.reset_mock()
		self.generate()
		self.tts.assert_not_called()
		self.assertEqual(self.asr.call_count, 1)
		self.assertEqual(len(self.asr.call_args.args[0]), 2)

	def test_readded_deleted_sentence_reuses_historical_audio_and_asr(self):
		before = self.generate()["beats"]
		original = copy.deepcopy(self.doc["scenes"][0]["beats"])
		self.doc["scenes"][0]["beats"] = [original[1]]
		self.generate()
		self.generate()
		self.doc["scenes"][0]["beats"] = original
		self.tts.reset_mock()
		self.asr.reset_mock()
		after = self.generate()["beats"]
		self.tts.assert_not_called()
		self.asr.assert_not_called()
		self.assertEqual(after[0]["wav"], before[0]["wav"])
		self.assertEqual(after[0]["asr"], before[0]["asr"])

	def test_cache_text_voice_and_wav_format_metadata_are_verified(self):
		report = self.generate()
		for field, value in (("text", "完全不同內容"), ("voice_digest", "0" * 64), ("wav_format", {})):
			with self.subTest(field=field):
				changed = copy.deepcopy(report)
				changed["beats"][0][field] = value
				write_json(self.voice / "narration.json", changed)
				self.tts.reset_mock()
				with self.assertRaisesRegex(ValueError, "快取|身份|格式"):
					self.generate()
				self.tts.assert_not_called()

	def test_audio_hash_without_voice_binding_requires_fresh_asr(self):
		report = self.generate()
		for record in report["beats"]:
			record.pop("voice_digest", None)
			record.pop("speech_digest", None)
		report.pop("cache", None)
		write_json(self.voice / "narration.json", report)
		(self.voice / "timing.identity.json").unlink()
		self.asr.reset_mock()
		self.generate()
		self.assertEqual(self.asr.call_count, 1)

	def test_prior_sidecar_binds_old_report_without_metadata(self):
		report = self.generate()
		for record in report["beats"]:
			for key in ("audio_sha256", "voice_digest", "speech_digest", "wav_format"):
				record.pop(key, None)
		report.pop("cache", None)
		write_json(self.voice / "narration.json", report)
		self.tts.reset_mock()
		self.asr.reset_mock()
		self.generate()
		self.tts.assert_not_called()
		self.asr.assert_not_called()

	def test_historical_audio_corruption_is_rejected_after_sentence_returns(self):
		records = self.generate()["beats"]
		original = copy.deepcopy(self.doc["scenes"][0]["beats"])
		self.doc["scenes"][0]["beats"] = [original[1]]
		self.generate()
		fake_voice("完全不同內容", self.voice / "audio" / records[0]["wav"])
		self.doc["scenes"][0]["beats"] = original
		with self.assertRaisesRegex(ValueError, "快取|digest"):
			self.generate()

	def test_audio_change_during_asr_is_rejected_before_identity_output(self):
		def replacing_asr(jobs, out):
			for job in jobs:
				fake_voice("完全不同內容", job["wav"])
			return {job["wav"]: {"ok": True, "problems": [], "missing": [], "heard": job["text"]} for job in jobs}
		self.asr.side_effect = replacing_asr
		with self.assertRaisesRegex(ValueError, "ASR.*改變"):
			self.generate()
		self.assertFalse((self.voice / "timing.identity.json").exists())

	def test_legacy_indexed_audio_and_asr_are_preserved_after_move(self):
		report = self.generate()
		for index, beat in enumerate(report["beats"]):
			old, new = self.voice / "audio" / beat["wav"], f"{index:02d}_{beat['digest']}.wav"
			old.rename(old.with_name(new))
			beat["wav"] = new
		write_json(self.voice / "narration.json", report)
		self.doc["scenes"][0]["beats"].reverse()
		self.tts.reset_mock()
		self.asr.reset_mock()
		after = self.generate()["beats"]
		self.tts.assert_not_called()
		self.asr.assert_not_called()
		self.assertTrue((self.voice / "audio" / report["beats"][0]["wav"]).exists())
		self.assertEqual(after[0]["asr"], report["beats"][1]["asr"])

	def test_voice_configuration_change_invalidates_audio(self):
		before = self.generate()["beats"]
		self.tts.reset_mock()
		after = self.generate("--voice", "Kore")["beats"]
		self.assertEqual(self.tts.call_count, 2)
		self.assertNotEqual(before[0]["wav"], after[0]["wav"])

	def test_duplicate_sentences_share_one_synthesis(self):
		self.doc["scenes"][0]["beats"] *= 2
		records = self.generate()["beats"]
		self.assertEqual(self.tts.call_count, 2)
		self.assertEqual(records[0]["wav"], records[2]["wav"])

	def test_identity_sidecar_and_verified_cli_preserve_timing_list(self):
		self.generate()
		self.assertIsInstance(json.loads((self.voice / "timing.json").read_text()), list)
		self.assertTrue((self.voice / "timing.identity.json").exists())
		tl, errors = self.compile()
		self.assertEqual(tl["timing_identity"]["status"], "verified")
		self.assertNotIn("legacy", errors)
		self.assertEqual(tl["timing_identity"].get("speech_status"), "passed")

	def test_failed_asr_retries_and_returns_needs_review_without_hard_failure(self):
		self.asr.side_effect = lambda jobs, out: {job["wav"]: {
			"ok": False, "problems": ["漏念"], "missing": ["句子"], "heard": ""} for job in jobs}
		output = io.StringIO()
		write_json(self.scene, self.doc)
		with redirect_stdout(output), patch.object(self.narrate.sys, "argv", [
			"narrate.py", str(self.scene), str(self.voice), "--english", "off"]):
			self.narrate.main()
		self.assertEqual(self.tts.call_count, 2 * self.narrate.MAX_ROUNDS)
		self.assertEqual(self.asr.call_count, self.narrate.MAX_ROUNDS)
		self.assertIn("@warn tts_missing", output.getvalue())
		identity = json.loads((self.voice / "timing.identity.json").read_text())
		self.assertTrue(all(beat.get("speech_checked") is True and beat.get("ok") is False for beat in identity["beats"]))
		tl, errors = self.compile()
		self.assertEqual(tl["timing_identity"]["status"], "verified")
		self.assertEqual(tl["timing_identity"].get("speech_status"), "needs_review")
		self.assertIn("needs_review", errors)

	def test_sidecar_cannot_claim_speech_passed_against_failed_asr_record(self):
		self.generate()
		path = self.voice / "narration.json"
		report = json.loads(path.read_text())
		report["beats"][0]["asr"]["ok"] = False
		report["beats"][0]["ok"] = False
		write_json(path, report)
		with self.assertRaisesRegex(ValueError, "驗收"):
			self.compile()

	def test_missing_speech_fields_or_report_is_needs_review(self):
		self.generate()
		path = self.voice / "timing.identity.json"
		identity = json.loads(path.read_text())
		for beat in identity["beats"]:
			beat.pop("speech_checked", None)
			beat.pop("ok", None)
		write_json(path, identity)
		self.assertEqual(self.compile()[0]["timing_identity"].get("speech_status"), "needs_review")
		self.generate()
		(self.voice / "narration.json").unlink()
		self.assertEqual(self.compile()[0]["timing_identity"].get("speech_status"), "needs_review")

	def test_unknown_asr_is_needs_review_and_forged_ok_is_rejected(self):
		self.generate()
		path = self.voice / "narration.json"
		report = json.loads(path.read_text())
		report["beats"][0].pop("asr")
		report["beats"][0]["ok"] = False
		write_json(path, report)
		identity_path = self.voice / "timing.identity.json"
		identity = json.loads(identity_path.read_text())
		identity["beats"][0].update(speech_checked=False, ok=False)
		write_json(identity_path, identity)
		self.assertEqual(self.compile()[0]["timing_identity"].get("speech_status"), "needs_review")
		identity["beats"][0].update(speech_checked=True, ok=True)
		write_json(identity_path, identity)
		with self.assertRaisesRegex(ValueError, "驗收"):
			self.compile()

	def test_narration_speech_record_must_bind_current_audio_identity(self):
		self.generate()
		path = self.voice / "narration.json"
		report = json.loads(path.read_text())
		report["beats"][0]["audio_sha256"] = "0" * 64
		write_json(path, report)
		with self.assertRaisesRegex(ValueError, "驗收|身份"):
			self.compile()

	def test_glossary_reading_keeps_original_spoken_and_actual_text(self):
		self.doc["scenes"][0]["beats"][0].update(say="判斷 i <= 三", spoken="判斷變數小於等於三")
		plan = self.directory / "plan.json"
		write_json(plan, {"glossary": [{"term": "<=", "say_as": "小於等於"}]})
		self.generate("--english", str(plan))
		identity = json.loads((self.voice / "timing.identity.json").read_text())
		self.assertEqual(identity["beats"][0]["spoken"], "判斷變數小於等於三")
		self.assertEqual(identity["beats"][0]["text"], "判斷 i 小於等於 三")
		self.assertEqual(self.compile()[0]["timing_identity"]["status"], "verified")

	def test_actual_text_or_voice_identity_change_is_rejected(self):
		self.generate()
		path = self.voice / "timing.identity.json"
		original = json.loads(path.read_text())
		for field in ("text", "voice_digest"):
			with self.subTest(field=field):
				identity = copy.deepcopy(original)
				if field == "text":
					identity["beats"][0][field] = "不同實際發音"
				else:
					identity[field] = "0" * 64
				write_json(path, identity)
				with self.assertRaisesRegex(ValueError, "身份|旁白"):
					self.compile()

	def test_legacy_missing_asr_is_checked_without_tts(self):
		report = self.generate()
		for record in report["beats"]:
			record.pop("asr")
		write_json(self.voice / "narration.json", report)
		self.tts.reset_mock()
		self.asr.reset_mock()
		self.generate()
		self.tts.assert_not_called()
		self.assertEqual(len(self.asr.call_args.args[0]), 2)

	def test_same_count_changed_say_or_spoken_is_rejected(self):
		self.generate()
		original = copy.deepcopy(self.doc)
		for key in ("say", "spoken"):
			with self.subTest(key=key):
				self.doc = copy.deepcopy(original)
				self.doc["scenes"][0]["beats"][0][key] = "完全不同內容"
				with self.assertRaisesRegex(ValueError, "身份|旁白"):
					self.compile()

	def test_beat_reorder_is_rejected(self):
		self.generate()
		self.doc["scenes"][0]["beats"].reverse()
		with self.assertRaisesRegex(ValueError, "身份|旁白"):
			self.compile()

	def test_replaced_sentence_audio_or_master_is_rejected(self):
		records = self.generate()["beats"]
		for path in (self.voice / "audio" / records[0]["wav"], self.voice / "master.wav"):
			with self.subTest(path=path.name):
				original = path.read_bytes()
				path.write_bytes(original + b"changed")
				with self.assertRaisesRegex(ValueError, "digest|音檔"):
					self.compile()
				path.write_bytes(original)

	def test_modified_span_or_audio_location_is_rejected(self):
		self.generate()
		path = self.voice / "timing.json"
		timing = json.loads(path.read_text())
		timing[0]["t0"] += 0.01
		write_json(path, timing)
		with self.assertRaisesRegex(ValueError, "身份|起訖"):
			self.compile()
		self.generate()
		audio = next((self.voice / "audio").glob("*.wav"))
		audio.rename(audio.with_suffix(".moved"))
		with self.assertRaisesRegex(ValueError, "音檔"):
			self.compile()

	def test_legacy_timing_without_identity_is_explicit(self):
		self.generate()
		path = self.voice / "timing.identity.json"
		if path.exists():
			path.unlink()
		tl, errors = self.compile()
		self.assertEqual(tl["timing_identity"]["status"], "legacy")
		self.assertIn("legacy", errors)
