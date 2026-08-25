import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video_engine"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures"))

import make_pptx
from run import next_free, resolve_material


class TestResolveMaterial(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, self.dir)
		self.materials = os.path.join(self.dir, "materials")
		os.makedirs(self.materials)

	def test_md_原路徑回傳不落地(self):
		p = os.path.join(self.dir, "a.md")
		with open(p, "w", encoding="utf-8") as f:
			f.write("內容")
		self.assertEqual(resolve_material(p, self.materials), p)
		self.assertEqual(os.listdir(self.materials), [])

	def test_pptx_落地成同名_md(self):
		p = os.path.join(self.dir, "deck.pptx")
		make_pptx.make(p, [("標題", ["重點"])])
		out = resolve_material(p, self.materials)
		self.assertEqual(out, os.path.join(self.materials, "deck.md"))
		with open(out, encoding="utf-8") as f:
			self.assertIn("標題", f.read())

	def test_md_冪等_連呼叫兩次都回原路徑(self):
		# 服務層會分兩段呼叫 run.py，第二段若又落地一次就會產生 deck_2.md
		# 導致後續找不到 examples/deck.lesson.json
		p = os.path.join(self.dir, "a.md")
		with open(p, "w", encoding="utf-8") as f:
			f.write("內容")
		self.assertEqual(resolve_material(p, self.materials), p)
		self.assertEqual(resolve_material(p, self.materials), p)
		self.assertEqual(os.listdir(self.materials), [])

	def test_同名不覆寫要加序號(self):
		with open(os.path.join(self.materials, "deck.md"), "w", encoding="utf-8") as f:
			f.write("舊的")
		p = os.path.join(self.dir, "deck.pptx")
		make_pptx.make(p, [("新的", ["內容"])])
		out = resolve_material(p, self.materials)
		self.assertEqual(out, os.path.join(self.materials, "deck_2.md"))
		with open(os.path.join(self.materials, "deck.md"), encoding="utf-8") as f:
			self.assertEqual(f.read(), "舊的")

	def test_next_free_連續佔用會往後找(self):
		for name in ("a.md", "a_2.md"):
			with open(os.path.join(self.materials, name), "w", encoding="utf-8") as f:
				f.write("x")
		self.assertEqual(next_free(os.path.join(self.materials, "a.md")),
			os.path.join(self.materials, "a_3.md"))
		self.assertEqual(next_free(os.path.join(self.materials, "b.md")),
			os.path.join(self.materials, "b.md"))


if __name__ == "__main__":
	unittest.main()
