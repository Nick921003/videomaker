import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv/bin/python")
COMPILE = os.path.join(ROOT, "video_engine/compile_timeline.py")
EXAMPLES = os.path.join(ROOT, "video_engine/examples")

import sys
sys.path.insert(0, os.path.join(ROOT, "video_engine"))
from compile_timeline import calc_camera_scale, check_figure_subitems, compile_slide
from render_video import apply_spotlight, apply_camera


class TestSpotlight(unittest.TestCase):
	"""聚光燈壓暗、鏡頭推近節制規則、示意圖子項目診斷測試"""

	def test_calc_camera_scale_節制規則(self):
		canvas = {"width": 1920, "height": 1080}
		# 1. 大於等於 8% 的目標不推近
		large_box = {"x": 100, "y": 100, "w": 600, "h": 350}  # area = 210,000 > 165,888 (8%)
		share, scale = calc_camera_scale(large_box, canvas)
		self.assertGreaterEqual(share, 0.08)
		self.assertIsNone(scale, "目標佔比 >= 8% 應該不推近")

		# 2. 小於 8% 的目標依面積反向放大，上限 1.4
		small_box = {"x": 100, "y": 100, "w": 100, "h": 50}  # area = 5,000 (0.24%)
		share_small, scale_small = calc_camera_scale(small_box, canvas)
		self.assertLess(share_small, 0.08)
		self.assertAlmostEqual(scale_small, 1.4, places=2)

		# 3. 中等尺寸目標 (如 4%)
		mid_box = {"x": 100, "y": 100, "w": 850, "h": 98}  # area = 83,300 (~4.0%)
		share_mid, scale_mid = calc_camera_scale(mid_box, canvas)
		self.assertLess(share_mid, 0.08)
		self.assertLess(scale_mid, 1.4)
		self.assertGreater(scale_mid, 1.0)
		self.assertGreater(scale_small, scale_mid, "目標越小推近倍率應越高")

	def test_apply_spotlight_壓暗外圍並保留目標亮度(self):
		# 建立一張全白 (255, 255, 255) 畫布 200x200
		frame = np.full((200, 200, 3), 255, dtype=np.uint8)
		box = {"x": 50, "y": 50, "w": 60, "h": 40}
		eff = {
			"type": "spotlight",
			"start_ms": 1000,
			"end_ms": 5000,
			"box": box,
			"dim": 0.62
		}
		dim_rgb = (42, 35, 28)

		# 在 t = 2000 (聚光燈進行中)
		# 簽章改了：保留區由呼叫端指定（實際上是整張程式碼卡），
		# 不再是效果自己的框——壓暗只用在程式講解，卡內哪幾行由 apply_code_focus 管
		res = apply_spotlight(frame.copy(), eff, 2000, dim_rgb, box)

		# 框外像素 (如 (10, 10)) 應顯著壓暗
		out_pixel = res[10, 10]
		self.assertLess(np.mean(out_pixel), 200, "框外像素應被壓暗")

		# 框內像素 (如 (60, 60)) 應保持原亮度（並疊加螢光筆暖色）
		in_pixel = res[60, 60]
		self.assertGreater(np.mean(in_pixel), 200, "框內像素應維持高亮度")

	def test_B5_診斷_示意圖整體指向(self):
		boxes = {
			"fig1": {"x": 100, "y": 100, "w": 400, "h": 300},
			"fig1:i1": {"x": 110, "y": 110, "w": 100, "h": 50},
			"fig1:i2": {"x": 220, "y": 110, "w": 100, "h": 50},
			"fig2": {"x": 100, "y": 500, "w": 400, "h": 300},
			"fig2:l1": {"x": 110, "y": 510, "w": 180, "h": 40},
			"fig2:r1": {"x": 300, "y": 510, "w": 180, "h": 40},
			"single_item": {"x": 100, "y": 900, "w": 200, "h": 40}
		}

		# 1. spotlight 指向有子項目的 fig1 -> 應有 WARN 且列出子代號
		diags = []
		check_figure_subitems(boxes, "spotlight", "fig1", "p1", diags)
		self.assertEqual(len(diags), 1)
		self.assertEqual(diags[0]["level"], "warn")
		self.assertIn("fig1:i1", diags[0]["msg"])
		self.assertIn("fig1:i2", diags[0]["msg"])

		# 2. laser 指向有子項目的 fig2 -> 應有 WARN
		diags = []
		check_figure_subitems(boxes, "laser", "fig2", "p1", diags)
		self.assertEqual(len(diags), 1)
		self.assertEqual(diags[0]["level"], "warn")
		self.assertIn("fig2:l1", diags[0]["msg"])
		self.assertIn("fig2:r1", diags[0]["msg"])

		# 3. reveal 與 camera 指向 fig1 -> 不應報 WARN
		diags = []
		check_figure_subitems(boxes, "reveal", "fig1", "p1", diags)
		check_figure_subitems(boxes, "camera", "fig1", "p1", diags)
		self.assertEqual(len(diags), 0, "reveal 與 camera 指向示意圖整體是合法的")

		# 4. spotlight 指向無子項目的元素 -> 不應報 WARN
		diags = []
		check_figure_subitems(boxes, "spotlight", "single_item", "p1", diags)
		self.assertEqual(len(diags), 0)

	def test_鏡頭平滑過渡銜接(self):
		canvas = {"width": 1920, "height": 1080}
		box1 = {"x": 100, "y": 100, "w": 200, "h": 100}
		box2 = {"x": 800, "y": 500, "w": 300, "h": 150}

		# 連續鏡頭動作
		cam1 = {"start_ms": 1000, "end_ms": 3000, "box": box1, "scale": 1.3, "ms": 600, "from_box": None, "from_scale": 1.0}
		cam2 = {"start_ms": 3000, "end_ms": 5000, "box": box2, "scale": 1.25, "ms": 600, "from_box": box1, "from_scale": 1.3}

		img = Image.new("RGB", (1920, 1080), (200, 200, 200))
		# 在 t = 3000 時，cam2 剛開始，畫面應平滑銜接 cam1 結束時的狀態（中心在 box1，scale 1.3）
		res_end_cam1 = apply_camera(img, cam1, 2999, canvas)
		res_start_cam2 = apply_camera(img, cam2, 3000, canvas)
		diff = np.max(np.abs(np.array(res_end_cam1).astype(int) - np.array(res_start_cam2).astype(int)))
		self.assertEqual(diff, 0, "連續聚光燈切換時鏡頭不得瞬移或跳回全景")


if __name__ == "__main__":
	unittest.main()


class TestCameraOnlyForCode(unittest.TestCase):
	"""推近只配程式區塊，而且程式碼的每個聚光燈都要配到自己那一行。

	實測過兩種壞法：圖與條列也配推近時，幾乎每一格都在做 LANCZOS 縮放，
	渲染時間從 95 秒變成 400 秒而畫面看不出好處；讓 LLM 的顯式 camera
	優先時，會在聚光燈亮起的同時把鏡頭往後拉（scale 1.4 → 1.3），
	剪輯上讀起來是「燈壞了」不是「看這裡」
	"""

	def _compile(self):
		import subprocess, tempfile, shutil, os, json
		root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
		shutil.copy(os.path.join(root, "video_engine/out/demo3/durations.json"), d)
		py = os.path.join(root, ".venv/bin/python")
		les = os.path.join(root, "video_engine/examples/demo3.lesson.json")
		act = os.path.join(root, "video_engine/examples/demo3.actions.json")
		subprocess.run([py, os.path.join(root, "video_engine/render_slides.py"), les, d],
			capture_output=True, check=True)
		subprocess.run([py, os.path.join(root, "video_engine/compile_timeline.py"), les, act, d],
			capture_output=True, check=True)
		with open(os.path.join(d, "timeline.json"), encoding="utf-8") as f:
			return json.load(f)

	def test_只有程式碼頁有鏡頭(self):
		for sc in self._compile()["scenes"]:
			codes = [e for e in sc["effects"]
				if e["type"] == "spotlight" and e.get("style") == "code"]
			if codes:
				self.assertEqual(len(sc["camera"]), len(codes),
					f"{sc['slide_id']} 的程式碼聚光燈沒有一對一配到推近")
			else:
				self.assertEqual(sc["camera"], [],
					f"{sc['slide_id']} 沒有程式碼卻配了推近")

	def test_每個推近都指到自己那一行(self):
		for sc in self._compile()["scenes"]:
			spots = [e["target"] for e in sc["effects"]
				if e["type"] == "spotlight" and e.get("style") == "code"]
			for c in sc["camera"]:
				self.assertIn(c.get("target"), spots,
					f"{sc['slide_id']} 有推近指到 {c.get('target')!r}，"
					"不是任何聚光燈的目標——鏡頭會在強調時跑去別的地方")
				self.assertIsNotNone(c.get("box"), "推近沒有目標框，等於拉遠")
