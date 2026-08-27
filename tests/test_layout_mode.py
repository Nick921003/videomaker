import io
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import layout as L
import render_slides
import serve


def make_slide(*types, kind=None, n_bullets=0, hidden=(), n_items=2):
	"""產生測試用的 slide 結構"""
	els = [
		{"id": "p1_title", "type": "title", "text": "測試標題"},
		{"id": "p1_sub", "type": "subtitle", "text": "測試副標"},
	]
	for i in range(n_bullets):
		els.append({
			"id": f"p1_b{i+1}", "type": "bullet", "text": f"條列項目 {i+1}",
			"hidden": i in hidden,
		})
	for t in types:
		if t == "figure":
			k = kind or "boxes"
			if k == "compare":
				els.append({
					"id": "p1_fig", "type": "figure", "kind": "compare",
					"left": {"title": "左側", "items": [f"左{j+1}" for j in range(n_items)]},
					"right": {"title": "右側", "items": [f"右{j+1}" for j in range(n_items)]},
				})
			else:
				els.append({
					"id": "p1_fig", "type": "figure", "kind": k,
					"items": [f"項目{j+1}" for j in range(n_items)],
				})
		elif t == "code":
			els.append({
				"id": "p1_code", "type": "code", "lang": "c",
				"lines": ["int x = 0;", "return x;"],
			})
		elif t == "image":
			els.append({
				"id": "p1_img", "type": "image", "src": "tests/fixtures/sample.png",
			})
	return {"id": "p1", "elements": els}


class TestPickVariantMode(unittest.TestCase):
	"""測試 pick_variant 在不同 mode 下的版型選擇邏輯"""

	def test_預設值模式為_auto(self):
		"""不傳 mode 時預設走 auto 模式：compare 走 stage，boxes 走 split"""
		compare_slide = make_slide("figure", kind="compare", n_bullets=2)
		boxes_slide = make_slide("figure", kind="boxes", n_bullets=2)
		self.assertEqual(L.pick_variant(compare_slide), "stage")
		self.assertEqual(L.pick_variant(compare_slide, mode="auto"), "stage")
		self.assertEqual(L.pick_variant(boxes_slide), "split")
		self.assertEqual(L.pick_variant(boxes_slide, mode="auto"), "split")

	def test_未知模式值拋出_ValueError(self):
		"""未知的 mode 必須明確拋出 ValueError，嚴禁靜默退回 auto"""
		sl = make_slide("figure", kind="compare", n_bullets=2)
		with self.assertRaises(ValueError):
			L.pick_variant(sl, mode="invalid_mode")
		with self.assertRaises(ValueError):
			L.pick_variant(sl, mode="")
		with self.assertRaises(ValueError):
			L.pick_variant(sl, mode=None)

	def test_未知模式值在_regions_for拋出_ValueError(self):
		"""regions_for 遇到未知的 mode 亦必須拋出 ValueError"""
		sl = make_slide("figure", kind="compare", n_bullets=2)
		with self.assertRaises(ValueError):
			L.regions_for(sl, 0, mode="random_bad")

	def test_split模式下單張compare圖走split(self):
		"""split 模式下，單張 compare 圖改走 split（auto 下為 stage）"""
		compare_slide = make_slide("figure", kind="compare", n_bullets=2)
		self.assertEqual(L.pick_variant(compare_slide, mode="split"), "split")
		self.assertEqual(L.pick_variant(compare_slide, mode="auto"), "stage")

	def test_split模式下單張boxes與steps圖維持split(self):
		"""split 模式下，單張 boxes 與 steps 維持 split"""
		boxes_slide = make_slide("figure", kind="boxes", n_bullets=2)
		steps_slide = make_slide("figure", kind="steps", n_bullets=2)
		self.assertEqual(L.pick_variant(boxes_slide, mode="split"), "split")
		self.assertEqual(L.pick_variant(steps_slide, mode="split"), "split")

	def test_center模式下一律為stack(self):
		"""center 模式下，除了 code 以外所有頁面一律走 stack"""
		compare_slide = make_slide("figure", kind="compare", n_bullets=2)
		boxes_slide = make_slide("figure", kind="boxes", n_bullets=2)
		steps_slide = make_slide("figure", kind="steps", n_bullets=2)
		text_only = make_slide(n_bullets=3)
		self.assertEqual(L.pick_variant(compare_slide, mode="center"), "stack")
		self.assertEqual(L.pick_variant(boxes_slide, mode="center"), "stack")
		self.assertEqual(L.pick_variant(steps_slide, mode="center"), "stack")
		self.assertEqual(L.pick_variant(text_only, mode="center"), "stack")

	def test_所有模式下code頁皆維持code(self):
		"""包含程式碼的頁面在 auto / split / center 下皆必須維持 code"""
		code_slide = make_slide("code", "figure", kind="compare", n_bullets=1)
		self.assertEqual(L.pick_variant(code_slide, mode="auto"), "code")
		self.assertEqual(L.pick_variant(code_slide, mode="split"), "code")
		self.assertEqual(L.pick_variant(code_slide, mode="center"), "code")

	def test_所有模式下多圖與image皆維持stack(self):
		"""含 image 或多張圖的頁面在所有模式下皆退回 stack"""
		img_slide = make_slide("image", "figure", n_bullets=1)
		two_figs = make_slide("figure", "figure", n_bullets=1)
		for mode in ("auto", "split", "center"):
			self.assertEqual(L.pick_variant(img_slide, mode=mode), "stack")
			self.assertEqual(L.pick_variant(two_figs, mode=mode), "stack")


class TestRegionsMode(unittest.TestCase):
	"""測試 regions_for 幾何分配在不同 mode 與容量守門下的表現"""

	def test_regions_for預設值模式為_auto(self):
		"""regions_for(slide, index) 二參數呼叫保持現有行為"""
		compare_slide = make_slide("figure", kind="compare", n_bullets=2)
		r_default = L.regions_for(compare_slide, 0)
		r_auto = L.regions_for(compare_slide, 0, mode="auto")
		self.assertEqual(r_default["variant"], "stage")
		self.assertEqual(r_default, r_auto)

	def test_regions_for_split模式下compare圖分配雙欄幾何(self):
		"""split 模式下 compare 成功分配 split 欄位幾何（左/右分欄）"""
		compare_slide = make_slide("figure", kind="compare", n_bullets=2)
		r = L.regions_for(compare_slide, 0, mode="split")
		self.assertEqual(r["variant"], "split")
		self.assertEqual(r["text_align"], "left")
		# 偶數頁 index 0 文字在左，圖在右
		self.assertLess(r["text"]["x"], r["figure"]["x"])
		# 圖寬度約為半欄 810px
		self.assertEqual(r["figure"]["w"], (L.CONTENT_BOX[2] - L.CONTENT_BOX[0] - 2 * L.COL_PAD - L.COL_GAP) // 2)

	def test_regions_for_split模式容量守門降級(self):
		"""split 模式下若圖高度在窄欄放不下（例如 5 項 steps 直排 760px > 660px），自動降級回 stack"""
		tall_steps_slide = make_slide("figure", kind="steps", n_bullets=2, n_items=5)
		r = L.regions_for(tall_steps_slide, 0, mode="split")
		self.assertEqual(r["variant"], "stack")
		self.assertEqual(r["text_align"], "center")

	def test_regions_for_center模式一律為stack幾何(self):
		"""center 模式下分配 stack 幾何（全幅置中）"""
		boxes_slide = make_slide("figure", kind="boxes", n_bullets=2)
		r = L.regions_for(boxes_slide, 0, mode="center")
		self.assertEqual(r["variant"], "stack")
		self.assertEqual(r["text_align"], "center")
		self.assertEqual(r["figure"]["x"], L.CONTENT_BOX[0])
		self.assertEqual(r["figure"]["w"], L.CONTENT_BOX[2] - L.CONTENT_BOX[0])


class TestServeAndPipelineIntegration(unittest.TestCase):
	"""測試 serve.py 與 run.py 鏈路的參數傳遞與相容性"""

	def test_parse_multipart解析layout欄位且相容三元組解包(self):
		"""parse_multipart 能解析 layout 欄位，同時維持 3-tuple 解包相容性"""
		boundary = b"BOUNDARY123"
		body = (
			b"--" + boundary + b"\r\n"
			b'Content-Disposition: form-data; name="file"; filename="test.pptx"\r\n'
			b"Content-Type: application/octet-stream\r\n\r\n"
			b"fake_content\r\n"
			b"--" + boundary + b"\r\n"
			b'Content-Disposition: form-data; name="sec"\r\n\r\n'
			b"120\r\n"
			b"--" + boundary + b"\r\n"
			b'Content-Disposition: form-data; name="layout"\r\n\r\n'
			b"split\r\n"
			b"--" + boundary + b"--\r\n"
		)
		# 舊呼叫端以 3-tuple 解包
		name, blob, sec = serve.parse_multipart(body, "multipart/form-data; boundary=BOUNDARY123")
		self.assertEqual(name, "test.pptx")
		self.assertEqual(blob, b"fake_content")
		self.assertEqual(sec, "120")

		# 新欄位屬性存取
		res = serve.parse_multipart(body, "multipart/form-data; boundary=BOUNDARY123")
		self.assertEqual(res.layout, "split")
		self.assertEqual(res.name, "test.pptx")
		self.assertEqual(res.blob, b"fake_content")
		self.assertEqual(res.sec, "120")

	def test_real_runner傳遞layout參數至子行程(self):
		"""real_runner 在有指定 layout 時，將 --layout 帶入 subprocess 參數"""
		runner_fn = serve.real_runner("test.md", 120, layout="split")
		with patch("serve.spawn") as mock_spawn:
			mock_proc = MagicMock()
			mock_proc.stderr = io.StringIO("")
			mock_proc.poll.return_value = 0
			mock_proc.returncode = 0
			mock_spawn.return_value = mock_proc

			# 呼叫 generator
			list(runner_fn("slides", "slides"))
			self.assertTrue(mock_spawn.called)
			cmd_args = mock_spawn.call_args[0][0]
			self.assertIn("--layout", cmd_args)
			layout_idx = cmd_args.index("--layout")
			self.assertEqual(cmd_args[layout_idx + 1], "split")
			self.assertIn("--sec", cmd_args)


class TestRandomModeAndSeed(unittest.TestCase):
	"""測試第四種模式 random 與 seed 參數的行為與管線整合"""

	def test_LAYOUT_MODES包含random(self):
		"""LAYOUT_MODES 包含 auto, split, center, random 四種模式"""
		self.assertEqual(L.LAYOUT_MODES, ("auto", "split", "center", "random"))

	def test_random模式下code頁必定為code(self):
		"""包含程式碼的頁面在 random 模式下不論 seed 為何皆維持 code"""
		code_slide = make_slide("code", "figure", kind="compare", n_bullets=1)
		for s in (0, 1, 42, 100, 2026):
			self.assertEqual(L.pick_variant(code_slide, mode="random", seed=s), "code")

	def test_random模式下純文字多圖與image必定為stack(self):
		"""純文字、多張圖、有 image 的頁面在 random 模式下無候選，一律回傳 stack"""
		text_slide = make_slide(n_bullets=3)
		img_slide = make_slide("image", "figure", n_bullets=1)
		two_figs = make_slide("figure", "figure", n_bullets=1)
		for s in (0, 1, 42, 100, 2026):
			self.assertEqual(L.pick_variant(text_slide, mode="random", seed=s), "stack")
			self.assertEqual(L.pick_variant(img_slide, mode="random", seed=s), "stack")
			self.assertEqual(L.pick_variant(two_figs, mode="random", seed=s), "stack")

	def test_random模式單張圖在候選集抽樣且具決定性(self):
		"""單張圖在 random 模式下只在 (split, stage, stack) 抽樣，且同 seed 產出相同結果"""
		fig_slide = make_slide("figure", kind="boxes", n_bullets=2)
		allowed_variants = {"split", "stage", "stack"}
		observed = set()
		for s in range(50):
			v = L.pick_variant(fig_slide, mode="random", seed=s)
			self.assertIn(v, allowed_variants)
			observed.add(v)
			# 決定性：同 seed 再次呼叫必同結果
			self.assertEqual(L.pick_variant(fig_slide, mode="random", seed=s), v)
		# 50 個種子應足以涵蓋 3 種候選
		self.assertEqual(observed, allowed_variants)

	def test_FNV1a純算術混合演算法(self):
		"""測試 _roll 輔助函式之 FNV-1a 混合計算與可重現性"""
		h1 = L._roll(0, "p1")
		h2 = L._roll(0, "p1")
		h3 = L._roll(1, "p1")
		h4 = L._roll(0, "p2")
		self.assertEqual(h1, h2)
		self.assertNotEqual(h1, h3)
		self.assertNotEqual(h1, h4)
		self.assertIsInstance(h1, int)
		self.assertGreaterEqual(h1, 0)
		self.assertLessEqual(h1, 0xFFFFFFFF)

	def test_regions_for_random模式容量守門降級(self):
		"""random 模式下若抽中 split 但圖高度在窄欄放不下，容量守門仍降級回 stack"""
		tall_steps_slide = make_slide("figure", kind="steps", n_bullets=2, n_items=5)
		# 找到讓 pick_variant 抽中 split 的種子
		split_seed = None
		for s in range(20):
			if L.pick_variant(tall_steps_slide, mode="random", seed=s) == "split":
				split_seed = s
				break
		self.assertIsNotNone(split_seed)
		# regions_for 應自動降級為 stack
		r = L.regions_for(tall_steps_slide, 0, mode="random", seed=split_seed)
		self.assertEqual(r["variant"], "stack")
		self.assertEqual(r["text_align"], "center")

	def test_parse_multipart解析seed欄位(self):
		"""parse_multipart 能正確解析 seed 欄位並掛在 MultipartResult 上"""
		boundary = b"BOUNDARY456"
		body = (
			b"--" + boundary + b"\r\n"
			b'Content-Disposition: form-data; name="file"; filename="demo.md"\r\n'
			b"Content-Type: text/markdown\r\n\r\n"
			b"# Hello\r\n"
			b"--" + boundary + b"\r\n"
			b'Content-Disposition: form-data; name="sec"\r\n\r\n'
			b"60\r\n"
			b"--" + boundary + b"\r\n"
			b'Content-Disposition: form-data; name="layout"\r\n\r\n'
			b"random\r\n"
			b"--" + boundary + b"\r\n"
			b'Content-Disposition: form-data; name="seed"\r\n\r\n'
			b"42\r\n"
			b"--" + boundary + b"--\r\n"
		)
		res = serve.parse_multipart(body, "multipart/form-data; boundary=BOUNDARY456")
		self.assertEqual(res.name, "demo.md")
		self.assertEqual(res.sec, "60")
		self.assertEqual(res.layout, "random")
		self.assertEqual(res.seed, "42")
		# 3-tuple 解包相容
		name, blob, sec = res
		self.assertEqual(name, "demo.md")
		self.assertEqual(sec, "60")

	def test_real_runner傳遞seed參數(self):
		"""real_runner 在有指定 seed 時，將 --seed 帶入 subprocess 參數"""
		runner_fn = serve.real_runner("test.md", 120, layout="random", seed=42)
		with patch("serve.spawn") as mock_spawn:
			mock_proc = MagicMock()
			mock_proc.stderr = io.StringIO("")
			mock_proc.poll.return_value = 0
			mock_proc.returncode = 0
			mock_spawn.return_value = mock_proc

			list(runner_fn("slides", "slides"))
			self.assertTrue(mock_spawn.called)
			cmd_args = mock_spawn.call_args[0][0]
			self.assertIn("--layout", cmd_args)
			self.assertEqual(cmd_args[cmd_args.index("--layout") + 1], "random")
			self.assertIn("--seed", cmd_args)
			self.assertEqual(cmd_args[cmd_args.index("--seed") + 1], "42")

	def test_layout_py維持零import與零內建hash(self):
		"""video_engine/layout.py 必須維持零 import、零 from、且無內建 hash( 呼叫"""
		layout_file = os.path.join(ROOT, "video_engine", "layout.py")
		with open(layout_file, encoding="utf-8") as f:
			content = f.read()
		lines = content.splitlines()
		import_lines = [l for l in lines if l.startswith("import ") or l.startswith("from ")]
		self.assertEqual(len(import_lines), 0, f"layout.py 不得有 import: {import_lines}")
		self.assertNotIn("hash(", content, "layout.py 不得呼叫內建 hash()")


if __name__ == "__main__":
	unittest.main()

