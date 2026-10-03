import copy
import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image


def board_fixture(code=False):
	objects = [{"id": "state", "kind": "cells", "label": "持續狀態", "values": ["0", "1", "2"]},
		{"id": "note", "kind": "text", "label": "原因", "values": ["累積保留"]}]
	if code:
		objects.append({"id": "code", "kind": "code", "label": "程式", "values": ["int sum = 0;", "sum += 1;", "sum += 2;"]})
	scenes = []
	for i in range(3):
		focus = "code" if code and i else "state"
		scenes.append({"id": f"s{i}", "title": f"步驟 {i}", "source_quote": "狀態持續累積。", "steps": [{
			"id": f"b{i}", "speech": "我們觀察這個狀態，接著繼續保留它的變化。", "caption": f"累積狀態 {i}",
			"focus": focus, "visible": [o["id"] for o in objects], "updates": ([{"target": "state", "values": [str(i + 1), "1", "2"]}] if i < 2 else []), "code_line": i if focus == "code" else -1}]})
	return {"contract_version": "1.0", "title": "累積狀態", "objects": objects, "scenes": scenes}


def timeline_fixture(board):
	return {"duration": 3.6, "steps": [{"scene_id": scene["id"], "step_id": scene["steps"][0]["id"], "start": i * 1.2, "end": i * 1.2 + 1} for i, scene in enumerate(board["scenes"])]}


class PaperRendererTests(unittest.TestCase):
	def renderer(self):
		self.assertTrue((Path(__file__).resolve().parents[1] / "video_engine/paper_renderer.py").is_file(), "paper renderer 尚未實作")
		from video_engine import paper_renderer
		return paper_renderer

	def test_cross_scene_state_retained_and_code_line(self):
		r = self.renderer()
		board = board_fixture(True)
		state = r._state_at(board, timeline_fixture(board), 2.8)
		self.assertEqual(state["values"]["state"], ["2", "1", "2"])
		self.assertEqual(state["step"]["code_line"], 2)
		self.assertEqual(board["objects"][0]["values"][0], "0")

	def test_preview_geometry_measured_inside_panels_and_deterministic(self):
		r = self.renderer()
		board = board_fixture(True)
		with tempfile.TemporaryDirectory() as d:
			layout = r.render_previews(board, Path(d))
			first = (Path(d) / "slide_01_full.png").read_bytes()
			r.render_previews(board, Path(d))
			self.assertEqual(first, (Path(d) / "slide_01_full.png").read_bytes())
			self.assertEqual([s["slide_id"] for s in layout["slides"]], ["s0", "s1", "s2"])
			self.assertEqual(json.loads((Path(d) / "layout.json").read_text()), layout)
			for obj in layout["objects"]:
				panel = obj["panel"]
				for box in obj["elements"].values():
					self.assertGreaterEqual(box["x"], panel["x"])
					self.assertGreaterEqual(box["y"], panel["y"])
					self.assertLessEqual(box["x"] + box["w"], panel["x"] + panel["w"])
					self.assertLessEqual(box["y"] + box["h"], panel["y"] + panel["h"])

	def test_seek_order_and_code_highlight_are_observable(self):
		r = self.renderer()
		board = board_fixture(True)
		tl = timeline_fixture(board)
		a = r.frame_at(board, tl, 2.8, size=(960, 540))
		r.frame_at(board, tl, .3)
		self.assertEqual(a.tobytes(), r.frame_at(board, tl, 2.8, size=(960, 540)).tobytes())
		other = copy.deepcopy(board)
		other["scenes"][2]["steps"][0]["code_line"] = 0
		self.assertNotEqual(a.tobytes(), r.frame_at(other, tl, 2.8, size=(960, 540)).tobytes())

	def test_audio_actual_durations_and_srt(self):
		r = self.renderer()
		board = board_fixture()
		with tempfile.TemporaryDirectory() as d:
			wavs = {}
			for i in range(3):
				p = Path(d) / f"b{i}.wav"
				with wave.open(str(p), "wb") as w:
					w.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
					w.writeframes(b"\0\0" * (800 * (i + 1)))
				wavs[f"b{i}"] = p
			tl = r.compile_paper_audio(board, wavs, Path(d))
			for i, step in enumerate(tl["steps"]):
				self.assertAlmostEqual(step["end"] - step["start"], .1 * (i + 1))
				self.assertEqual(step["scene_id"], f"s{i}")
			with wave.open(str(Path(d) / "master.wav")) as w:
				self.assertAlmostEqual(w.getnframes() / w.getframerate(), tl["duration"])
			self.assertIn("我們觀察這個狀態，接著繼續保留它的變化。", (Path(d) / "subtitles.srt").read_text())
			self.assertNotIn("累積狀態 2", (Path(d) / "subtitles.srt").read_text())

	def test_cancel_and_existing_output_not_overwritten(self):
		r = self.renderer()
		with tempfile.TemporaryDirectory() as d:
			p = Path(d) / "video.mp4"
			p.write_bytes(b"keep")
			with self.assertRaises(FileExistsError):
				r.render_paper_video(board_fixture(), timeline_fixture(board_fixture()), Path(d) / "master.wav", p)
			self.assertEqual(p.read_bytes(), b"keep")
			cancel = threading.Event()
			cancel.set()
			with self.assertRaises(RuntimeError):
				r.render_paper_video(board_fixture(), timeline_fixture(board_fixture()), Path(d) / "master.wav", Path(d) / "cancel.mp4", cancel)
			self.assertFalse((Path(d) / "cancel.mp4").exists())


class PaperMotionTests(unittest.TestCase):
	renderer = PaperRendererTests.renderer
	def test_gap_keeps_previous_step_and_line_when_code_is_visible(self):
		r = self.renderer()
		board = board_fixture(True)
		board["scenes"][2]["steps"][0]["focus"] = "state"
		board["scenes"][2]["steps"][0]["code_line"] = -1
		state = r._state_at(board, timeline_fixture(board), 2.8)
		self.assertEqual(state["code_lines"]["code"], 1)
		gap = r._state_at(board, timeline_fixture(board), 2.3)
		self.assertEqual(gap["step"]["id"], "b1")
		board["scenes"][2]["steps"][0]["visible"].remove("code")
		self.assertNotIn("code", r._state_at(board, timeline_fixture(board), 2.8)["code_lines"])

	def test_multi_cell_changes_animate_within_speech_and_camera_is_continuous(self):
		r = self.renderer()
		board = board_fixture()
		board["scenes"][1]["steps"][0]["updates"] = [{"target": "state", "values": ["4", "5", "6"]}]
		tl = timeline_fixture(board)
		frames = [r.frame_at(board, tl, t, size=(960, 540)).tobytes() for t in [1.22, 1.38, 1.6, 1.9]]
		self.assertEqual(len(set(frames)), 4)
		layout = r.layout_board(board)
		left = r._camera_at(board, tl, layout, 1.2 - .00001)
		right = r._camera_at(board, tl, layout, 1.2 + .00001)
		self.assertLess(max(abs(a - b) for a, b in zip(left, right)), .02)

	def test_invalid_timeline_rejected(self):
		r = self.renderer()
		board = board_fixture()
		tl = timeline_fixture(board)
		tl["steps"][1]["start"] = .2
		with self.assertRaises(ValueError):
			r.frame_at(board, tl, .4)
		tl = timeline_fixture(board)
		tl["duration"] = float("nan")
		with self.assertRaises(ValueError):
			r.frame_at(board, tl, .4)

class PaperBoundaryTests(unittest.TestCase):
	renderer = PaperRendererTests.renderer
	def test_focus_changes_camera_even_when_visible_set_is_same(self):
		r = self.renderer()
		board = board_fixture(True)
		layout = r.layout_board(board)
		a = r._target_camera(board["scenes"][0]["steps"][0], layout)
		b = r._target_camera(board["scenes"][1]["steps"][0], layout)
		self.assertNotEqual(a, b)

	def test_longest_legal_values_remain_within_measured_panels(self):
		r = self.renderer()
		board = board_fixture(True)
		board["objects"][0]["values"] = ["變" * 12] * 8
		board["objects"][1]["values"] = ["說" * 50] * 3
		board["objects"][2]["values"] = ["字" * 80] * 8
		for obj in r.layout_board(board)["objects"]:
			p = obj["panel"]
			for box in obj["elements"].values():
				self.assertGreaterEqual(box["x"], p["x"])
				self.assertGreaterEqual(box["y"], p["y"])
				self.assertLessEqual(box["x"] + box["w"], p["x"] + p["w"])
				self.assertLessEqual(box["y"] + box["h"], p["y"] + p["h"])

	def test_preexisting_partial_is_preserved(self):
		r = self.renderer()
		with tempfile.TemporaryDirectory() as d:
			partial = Path(d) / "video.part.mp4"
			partial.write_bytes(b"existing partial")
			with self.assertRaises(FileExistsError):
				r.render_paper_video(board_fixture(), timeline_fixture(board_fixture()), Path(d) / "master.wav", Path(d) / "video.mp4")
			self.assertEqual(partial.read_bytes(), b"existing partial")

	@unittest.skipUnless(shutil.which("ffmpeg"), "需要 FFmpeg")
	def test_mid_render_cancel_reaps_real_ffmpeg_and_removes_owned_partial(self):
		r = self.renderer()
		board, processes = board_fixture(), []
		real_popen, real_frame = subprocess.Popen, r.frame_at
		cancel = threading.Event()
		def start(*args, **kwargs):
			process = real_popen(*args, **kwargs)
			processes.append(process)
			return process
		def frame(*args, **kwargs):
			image = real_frame(*args, **kwargs)
			cancel.set()
			return image
		with tempfile.TemporaryDirectory() as d:
			audio = Path(d) / "master.wav"
			with wave.open(str(audio), "wb") as w:
				w.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
				w.writeframes(b"\0\0" * 28800)
			with patch.object(r.subprocess, "Popen", side_effect=start), patch.object(r, "frame_at", side_effect=frame):
				with self.assertRaisesRegex(RuntimeError, "cancelled"):
					r.render_paper_video(board, timeline_fixture(board), audio, Path(d) / "cancel.mp4", cancel)
			self.assertEqual(len(processes), 1)
			self.assertIsNotNone(processes[0].poll())
			self.assertFalse((Path(d) / "cancel.mp4").exists())
			self.assertFalse((Path(d) / "cancel.part.mp4").exists())

	def test_cancel_interrupts_blocked_stdin_writer(self):
		r = self.renderer()
		cancel, stopped = threading.Event(), threading.Event()
		class Pipe:
			closed = False
			def write(self, data):
				cancel.set()
				if not stopped.wait(timeout=1):
					raise AssertionError("取消未中斷阻塞 stdin")
				raise BrokenPipeError("terminated")
			def close(self):
				self.closed = True
		class Process:
			stdin = Pipe()
			def poll(self):
				return -15 if stopped.is_set() else None
			def terminate(self):
				stopped.set()
			def kill(self):
				stopped.set()
			def wait(self, timeout=None):
				if not stopped.wait(timeout):
					raise subprocess.TimeoutExpired("ffmpeg", timeout)
				return -15
		with tempfile.TemporaryDirectory() as d, patch.object(r.subprocess, "Popen", return_value=Process()):
			with self.assertRaisesRegex(RuntimeError, "cancelled"):
				r.render_paper_video(board_fixture(), timeline_fixture(board_fixture()), Path(d) / "master.wav", Path(d) / "blocked.mp4", cancel)
		self.assertTrue(stopped.is_set())


if __name__ == "__main__":
	unittest.main()
