import copy
import unittest
from PIL import ImageColor
from tests.test_paper_renderer import board_fixture
from video_engine import paper_renderer as r


def long_timeline(board):
	return {"duration": 24.6, "steps": [{"scene_id": s["id"], "step_id": s["steps"][0]["id"], "start": i * 8.2, "end": i * 8.2 + 8} for i, s in enumerate(board["scenes"])]}


class PaperACRendererTests(unittest.TestCase):
	def setUp(self):
		self.assertTrue(hasattr(r, "frame_metadata"), "A+C 畫面尚無可測量的物件運動與 composition metadata")

	def test_local_value_change_stays_inside_its_slot(self):
		for kind in ('text', 'flow', 'cells'):
			board = board_fixture()
			board['objects'][1].update(kind=kind, values=['舊說明'])
			for scene in board['scenes']:
				step = scene['steps'][0]
				step.update(focus='note', visible=['note'], updates=[{'target':'note', 'values':['單行註解']}])
			tl = long_timeline(board)
			for t in (.2, .6, 1.1, 2, 3):
				with self.subTest(kind=kind, time=t):
					image = r.frame_at(board, tl, t)
					meta = r.frame_metadata(board, tl, t)
					self.assertEqual(image.size, (1920, 1080))
					self.assertEqual(meta['flights'], [])
					change = meta['value_changes'][0]
					slot = meta['objects']['note']['slots'][0]
					self.assertFalse('old' in change and 'new' in change)
					for phase in ('old', 'new'):
						if phase not in change: continue
						box = change[phase]['bbox']
						self.assertGreaterEqual(box['x'], slot['x'])
						self.assertGreaterEqual(box['y'], slot['y'])
						self.assertLessEqual(box['x']+box['w'], slot['x']+slot['w'])
						self.assertLessEqual(box['y']+box['h'], slot['y']+slot['h'])

	def test_noncode_has_paper_background_outside_shapes(self):
		board = board_fixture()
		tl = long_timeline(board)
		meta = r.frame_metadata(board, tl, 5)
		image = r.frame_at(board, tl, 5)
		box = meta["objects"]["state"]["panel"]
		# 標籤和格子之間應是紙面，不能是永久大卡片填色。
		p = (round(box["x"] + box["w"] * .8), round(box["y"] + 70))
		self.assertIn(image.getpixel(p), [ImageColor.getrgb(r._theme()["canvas"]["bg"]), ImageColor.getrgb(r._theme()["canvas"]["grid"])])

	def test_transfer_continues_after_first_second_and_is_seekable(self):
		board = board_fixture()
		step = board["scenes"][1]["steps"][0]
		step.update(motion="transfer", source="note")
		step["updates"] = [{"target": "state", "values": ["4", "5", "6"]}]
		tl = long_timeline(board)
		a = r.frame_metadata(board, tl, 9.4)
		b = r.frame_metadata(board, tl, 12)
		self.assertNotEqual(a["flights"], b["flights"])
		self.assertTrue(b["flights"])
		image = r.frame_at(board, tl, 12).tobytes()
		r.frame_at(board, tl, .5)
		self.assertEqual(image, r.frame_at(board, tl, 12).tobytes())

	def test_scan_stops_at_semantic_index(self):
		board = board_fixture()
		board["scenes"][1]["steps"][0].update(motion="scan", focus_index=1)
		tl = long_timeline(board)
		near = r.frame_metadata(board, tl, 14)["scan"]
		late = r.frame_metadata(board, tl, 16)["scan"]
		self.assertEqual(near, late)
		self.assertEqual(late["index"], 1)

	def test_hint_follows_code_step_and_keeps_all_noncode_objects_measured(self):
		board = board_fixture(True)
		board['scenes'][2]['steps'][0].update(focus='state', code_line=-1)
		tl = long_timeline(board)
		a = r.frame_metadata(board, tl, 9.2)
		b = r.frame_metadata(board, tl, 18)
		self.assertEqual(a["code_hint"]["lines"], [0, 1, 2])
		self.assertIsNotNone(r.frame_metadata(board, tl, 14)['code_hint'])
		self.assertIsNone(b["code_hint"])
		self.assertEqual(set(a["objects"]), {"state", "note", "code"})
		for meta in (a, b):
			for oid, geom in meta["objects"].items():
				if oid == "code":
					continue
				for box in geom["elements"].values():
					self.assertGreaterEqual(box["x"], 0)
					self.assertGreaterEqual(box["y"], r.VIEW_TOP)
					self.assertLessEqual(box["x"] + box["w"], r.W)
					self.assertLessEqual(box["y"] + box["h"], r.VIEW_BOTTOM)

	def test_flow_nodes_and_all_subreferences_are_measured(self):
		board = board_fixture()
		board["objects"][0].update(kind="flow", values=["開始", "檢查", "執行", "完成"])
		board["scenes"][0]["steps"][0]["updates"] = []
		board["scenes"][1]["steps"][0]["updates"] = []
		layout = r.layout_board(board)
		obj = layout["objects"][0]
		self.assertEqual(len(obj["slots"]), 4)
		self.assertTrue(all(f"state:i{i}" in obj["elements"] for i in range(4)))
		self.assertIn("compositions", layout)

	def test_explicit_source_index_uses_previous_source_value(self):
		board = board_fixture()
		board["objects"][1]["values"] = ["舊值", "來源乙"]
		step = board["scenes"][1]["steps"][0]
		step.update(motion="transfer", source="note", source_index=1)
		step["updates"] = [{"target": "note", "values": ["新值", "新來源"]}, {"target": "state", "values": ["來源乙", "1", "2"]}]
		meta = r.frame_metadata(board, long_timeline(board), 10)
		flight = next(f for f in meta["flights"] if f["id"] == "state")
		self.assertEqual(flight["value"], "來源乙")
		source = meta["objects"]["note"]["slots"][1]
		self.assertEqual(flight["start"], (source["x"] + source["w"] / 2, source["y"] + source["h"] / 2))
		self.assertGreater(len(flight["path"]), 2)
		self.assertIn("bbox", flight)

	def test_data_step_does_not_restart_retired_code_hint(self):
		board = board_fixture(True)
		step = board["scenes"][2]["steps"][0]
		step.update(focus="state", code_line=-1)
		tl = long_timeline(board)
		self.assertIsNotNone(r.frame_metadata(board, tl, 9)["code_hint"])
		self.assertIsNotNone(r.frame_metadata(board, tl, 14)["code_hint"])
		self.assertIsNone(r.frame_metadata(board, tl, 17.5)["code_hint"])
		self.assertIsNone(r.frame_metadata(board, tl, 19)["code_hint"])

	def test_transition_measurements_cover_dynamic_artifacts(self):
		board = board_fixture(True)
		board["scenes"][2]["steps"][0].update(focus="state", code_line=-1, motion="scan", focus_index=2)
		tl = long_timeline(board)
		for t in (8.2, 8.44, 9, 10.4, 11.88, 12, 16.4, 17, 21.9, 23):
			meta = r.frame_metadata(board, tl, t)
			boxes = [f["bbox"] for f in meta["flights"]] + [a["bbox"] for a in meta["arrows"]]
			if meta["scan"]:
				boxes.append(meta["scan"]["bbox"])
			if meta["code_hint"]:
				boxes.extend(meta["code_hint"]["elements"].values())
			for box in boxes:
				self.assertGreaterEqual(box["x"], 0)
				self.assertGreaterEqual(box["y"], r.VIEW_TOP)
				self.assertLessEqual(box["x"] + box["w"], r.W)
				self.assertLessEqual(box["y"] + box["h"], r.VIEW_BOTTOM)

	def test_long_legal_code_hint_fits_its_measured_panel(self):
		board = board_fixture(True)
		board["objects"][2]["values"] = ["字" * 80] * 8
		board["scenes"][1]["steps"][0]["code_line"] = 4
		hint = r.frame_metadata(board, long_timeline(board), 9)["code_hint"]
		panel = hint["panel"]
		for box in hint["elements"].values():
			self.assertGreaterEqual(box["x"], panel["x"])
			self.assertGreaterEqual(box["y"], panel["y"])
			self.assertLessEqual(box["x"] + box["w"], panel["x"] + panel["w"])
			self.assertLessEqual(box["y"] + box["h"], panel["y"] + panel["h"])

	def test_dense_visible_objects_fail_instead_of_silently_minifying(self):
		board = board_fixture()
		board["objects"] = [{"id": f"obj{i}", "kind": "cells", "label": "完整物件", "values": ["值" * 12] * 8} for i in range(6)]
		for scene in board["scenes"]:
			step = scene["steps"][0]
			step.update(focus="obj0", visible=[o["id"] for o in board["objects"]], updates=[])
		with self.assertRaisesRegex(ValueError, "可讀"):
			r.frame_at(board, long_timeline(board), 5)

	def test_transfer_without_update_still_moves_explicit_source_value(self):
		board = board_fixture()
		step = board["scenes"][1]["steps"][0]
		step.update(motion="transfer", source="note", focus_index=2, updates=[])
		meta = r.frame_metadata(board, long_timeline(board), 10)
		self.assertTrue(meta["flights"])
		self.assertEqual(meta["flights"][0]["index"], 2)
		self.assertEqual(meta["flights"][0]["value"], "累積保留")

	def test_parallel_text_values_have_no_causal_arrows(self):
		board = board_fixture()
		board["objects"][1]["values"] = ["第一項註解", "第二項註解"]
		meta = r.frame_metadata(board, long_timeline(board), 5)
		self.assertEqual(meta["arrows"], [])

	def test_same_values_in_flow_have_explicit_sequence_arrows(self):
		board = board_fixture()
		board["objects"][1].update(kind="flow", values=["第一項註解", "第二項註解"])
		meta = r.frame_metadata(board, long_timeline(board), 5)
		self.assertEqual(len(meta["arrows"]), 1)
		self.assertEqual(meta["arrows"][0]["id"], "note")

	def test_transfer_keeps_entire_long_source_within_viewport(self):
		for value in ("長" * 50, "四字來源"):
			with self.subTest(length=len(value)):
				board = board_fixture()
				board["objects"][1]["values"] = [value]
				step = board["scenes"][1]["steps"][0]
				step.update(motion="transfer", source="note", focus_index=0)
				meta = r.frame_metadata(board, long_timeline(board), 10)
				flight = next(f for f in meta["flights"] if f["id"] == "state")
				self.assertEqual(flight["value"], value)
				box = flight["bbox"]
				self.assertGreaterEqual(box["x"], 0)
				self.assertGreaterEqual(box["y"], r.VIEW_TOP)
				self.assertLessEqual(box["x"] + box["w"], r.W)
				self.assertLessEqual(box["y"] + box["h"], r.VIEW_BOTTOM)

	def test_injected_caption_cue_cannot_replace_full_speech(self):
		board = board_fixture()
		tl = long_timeline(board)
		tl["subtitle_cues"] = [{"step_id": "b0", "start": 0, "end": 8, "text": "摘要", "timing_basis": "measured_step_character_estimate"}]
		with self.assertRaises(ValueError):
			r.frame_at(board, tl, 1)

	def test_one_explicit_transfer_does_not_copy_source_into_every_changed_slot(self):
		for index in (-1, 0):
			with self.subTest(focus_index=index):
				board = board_fixture()
				board["objects"][1]["values"] = ["A"]
				values = ["A", "l", "i", "c", "e", "終點"]
				step = board["scenes"][1]["steps"][0]
				step.update(motion="transfer", source="note", focus_index=index, updates=[{"target": "state", "values": values}])
				meta = r.frame_metadata(board, long_timeline(board), 11.6)
				flights = meta['flights']
				paths = [f for f in flights if f["draw_path"]]
				self.assertEqual(len(paths), 1)
				self.assertEqual(paths[0]["index"], 0)
				self.assertEqual(paths[0]["value"], "A")
				self.assertEqual(len(flights), 1)
				for flight in flights:
					self.assertEqual(flight["value"], values[flight["index"]])
					self.assertEqual(flight["motion"], "transfer")
				self.assertEqual({change['index'] for change in meta['value_changes']}, {1, 2, 3, 4, 5})
				for change in meta['value_changes']:
					self.assertEqual(change['progress'], 1)
					self.assertNotIn('old', change)
					self.assertEqual(change['new']['text'], values[change['index']])

	def scan_output_board(self, include=False, code=False):
		board = board_fixture(code)
		board["objects"][0]["values"] = ["A", "l", "i", "c", "e", "停止"]
		board["objects"][1].update(label="輸出", values=["尚未輸出"])
		for scene in board["scenes"]:
			scene["steps"][0]["updates"] = []
		step = board["scenes"][1]["steps"][0]
		step.update(focus="state", code_line=-1, motion="scan", focus_index=5, scan_output="note", scan_include_stop=include,
			updates=[{"target": "note", "values": ["Alice停止" if include else "Alice"]}])
		if code:
			board["scenes"][0]["steps"][0].update(focus="code", code_line=1)
		return board

	def test_scan_output_builds_prefix_instead_of_full_string_flight(self):
		board = self.scan_output_board()
		tl = long_timeline(board)
		before = r.frame_metadata(board, tl, 8.2)
		middle = r.frame_metadata(board, tl, 10)
		end = r.frame_metadata(board, tl, 14)
		self.assertIn("output_text", before["scan"], "scan 尚未逐格綁定輸出")
		self.assertEqual(before["scan"]["output_text"], "")
		self.assertTrue("Alice".startswith(middle["scan"]["output_text"]))
		self.assertLess(middle["scan"]["count"], 5)
		self.assertTrue(any(f["motion"] == "scan" for f in middle["flights"]))
		self.assertFalse(any(f["value"] == "Alice" for f in middle["flights"]))
		self.assertEqual(end["scan"]["output_text"], "Alice")
		self.assertEqual(end["scan"]["count"], 5)
		self.assertEqual(end["scan"]["index"], 5)

	def test_scan_include_stop_and_multichar_cells_are_preserved(self):
		board = self.scan_output_board(True)
		board["objects"][0]["values"] = ["甲乙", "丙丁", "停止"]
		step = board["scenes"][1]["steps"][0]
		step.update(focus_index=2, updates=[{"target": "note", "values": ["甲乙丙丁停止"]}])
		meta = r.frame_metadata(board, long_timeline(board), 14)
		self.assertEqual(meta["scan"]["output_text"], "甲乙丙丁停止")
		self.assertEqual(meta["scan"]["count"], 3)

	def test_scan_output_geometry_and_seek_with_retired_code_hint(self):
		board = self.scan_output_board(code=True)
		tl = long_timeline(board)
		for t in (8.2, 8.6, 9.2, 10, 11, 12, 14):
			meta = r.frame_metadata(board, tl, t)
			if t < 9.2: self.assertIsNotNone(meta['code_hint'])
			else: self.assertIsNone(meta['code_hint'])
			boxes = [f["bbox"] for f in meta["flights"]] + [meta["scan"]["output_bbox"]]
			for box in boxes:
				self.assertGreaterEqual(box["x"], 0)
				self.assertGreaterEqual(box["y"], r.VIEW_TOP)
				self.assertLessEqual(box["x"] + box["w"], r.W)
				self.assertLessEqual(box["y"] + box["h"], r.VIEW_BOTTOM)
		image = r.frame_at(board, tl, 10).tobytes()
		r.frame_at(board, tl, 14)
		self.assertEqual(image, r.frame_at(board, tl, 10).tobytes())

	def test_short_code_hint_overlaps_next_scan_then_retires_without_restart(self):
		board = self.scan_output_board(code=True)
		board["scenes"][2]["steps"][0].update(focus="state", code_line=-1)
		tl = {"duration": 8, "steps": [
			{"scene_id": "s0", "step_id": "b0", "start": 0, "end": 2},
			{"scene_id": "s1", "step_id": "b1", "start": 2.18, "end": 5.56},
			{"scene_id": "s2", "step_id": "b2", "start": 5.74, "end": 7.8}]}
		meta = r.frame_metadata(board, tl, 2.5)
		self.assertIsNotNone(meta["code_hint"])
		self.assertTrue(any(f["motion"] == "scan" for f in meta["flights"]))
		for box in [f["bbox"] for f in meta["flights"]] + [meta["scan"]["output_bbox"]]:
			self.assertGreaterEqual(box["x"], 0)
			self.assertGreaterEqual(box["y"], r.VIEW_TOP)
			self.assertLessEqual(box["x"] + box["w"], r.W)
			self.assertLessEqual(box["y"] + box["h"], r.VIEW_BOTTOM)
		self.assertIsNone(r.frame_metadata(board, tl, 3.3)["code_hint"])
		self.assertIsNone(r.frame_metadata(board, tl, 6)["code_hint"])

	def test_settled_outline_wobbles_at_12hz_without_moving_glyphs(self):
		board = board_fixture()
		tl = long_timeline(board)
		a = r.frame_at(board, tl, 19)
		b = r.frame_at(board, tl, 19.09)
		self.assertTrue(a.tobytes() != b.tobytes(), "穩態線條尚未隨12Hz tick變化")
		meta = r.frame_metadata(board, tl, 19)
		glyph = meta["objects"]["state"]["elements"]["state:i0"]
		box = tuple(round(v) for v in (glyph["x"], glyph["y"], glyph["x"] + glyph["w"], glyph["y"] + glyph["h"]))
		self.assertEqual(a.crop(box).tobytes(), b.crop(box).tobytes())
		self.assertEqual(r._state_at(board, tl, 19)["values"], r._state_at(board, tl, 19.09)["values"])
		r.frame_at(board, tl, 2)
		self.assertEqual(a.tobytes(), r.frame_at(board, tl, 19).tobytes())

	def test_code_fade_keeps_data_reserved_until_panel_is_gone(self):
		board = self.scan_output_board(code=True)
		board["scenes"][2]["steps"][0].update(focus="state", code_line=-1)
		tl = {"duration": 8, "steps": [
			{"scene_id": "s0", "step_id": "b0", "start": 0, "end": 2},
			{"scene_id": "s1", "step_id": "b1", "start": 2.18, "end": 5.56},
			{"scene_id": "s2", "step_id": "b2", "start": 5.74, "end": 7.8}]}
		meta = r.frame_metadata(board, tl, 2.9)
		hint = meta["code_hint"]
		self.assertIsNotNone(hint)
		self.assertAlmostEqual(hint["opacity"], .5)
		right = hint["panel"]["x"] + hint["panel"]["w"]
		boxes = [box for oid, geom in meta["objects"].items() if oid != "code" for box in geom["elements"].values()]
		boxes += [f["bbox"] for f in meta["flights"]] + [meta["scan"]["bbox"], meta["scan"]["output_bbox"]]
		for box in boxes:
			self.assertGreaterEqual(box["x"], right)
		self.assertEqual(hint["reserve_weight"], 1)
		a = r.frame_metadata(board, tl, 3.2)
		b = r.frame_metadata(board, tl, 3.8)
		self.assertIsNone(a["code_hint"])
		self.assertIsNone(b["code_hint"])
		self.assertEqual(a["code_reserve_weight"], 1)
		self.assertEqual(b["code_reserve_weight"], 0)
		self.assertLess(b["objects"]["state"]["panel"]["x"], a["objects"]["state"]["panel"]["x"])
		image = r.frame_at(board, tl, 2.9).tobytes()
		r.frame_at(board, tl, 3.8)
		self.assertTrue(image == r.frame_at(board, tl, 2.9).tobytes())

	def test_two_code_blocks_with_data_require_explicit_separate_steps(self):
		board = board_fixture(True)
		self.assertTrue(r.layout_board(board)["compositions"])
		board["objects"].append({"id": "other_code", "kind": "code", "label": "另一程式", "values": ["int value = 1;"]})
		for scene in board["scenes"]:
			scene["steps"][0]["visible"].append("other_code")
		with self.assertRaisesRegex(ValueError, "分步"):
			r.layout_board(board)

	def test_scaled_scan_pointer_does_not_overlap_label_or_cell_glyphs(self):
		board = self.scan_output_board(code=True)
		board["objects"][0]["label"] = "同一個 name[32] 陣列（前六格）"
		board["scenes"][2]["steps"][0].update(focus="state", code_line=-1)
		tl = {"duration": 8, "steps": [
			{"scene_id": "s0", "step_id": "b0", "start": 0, "end": 2},
			{"scene_id": "s1", "step_id": "b1", "start": 2.18, "end": 5.56},
			{"scene_id": "s2", "step_id": "b2", "start": 5.74, "end": 7.8}]}
		def overlaps(a, b):
			return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]
		for t in [2.9] + [i / 24 for i in range(53, 134)]:
			meta = r.frame_metadata(board, tl, t)
			pointer = meta["scan"]["bbox"]
			elements = meta["objects"]["state"]["elements"]
			self.assertFalse(overlaps(pointer, elements["state:label"]), f"scan 指針遮住標籤 t={t}")
			for i in range(6):
				self.assertFalse(overlaps(pointer, elements[f"state:i{i}"]), f"scan 箭頭遮住字形 t={t}")


if __name__ == "__main__":
	unittest.main()
