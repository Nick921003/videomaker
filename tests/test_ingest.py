import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))
sys.path.insert(0, os.path.join(ROOT, "tests/fixtures"))

import make_pptx
from ingest import SUPPORTED, extract_text, lesson_id_for


class TestExtractText(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp()

	def path(self, name):
		return os.path.join(self.dir, name)

	def test_md_原文照回(self):
		p = self.path("a.md")
		open(p, "w", encoding="utf-8").write("# 標題\n\n內文一行")
		self.assertEqual(extract_text(p), "# 標題\n\n內文一行")

	def test_txt_原文照回(self):
		p = self.path("a.txt")
		open(p, "w", encoding="utf-8").write("純文字")
		self.assertEqual(extract_text(p), "純文字")

	def test_pptx_每頁都在且照播放順序(self):
		p = self.path("a.pptx")
		make_pptx.make(p, [(f"第{i}頁標題", [f"第{i}頁內容"]) for i in range(1, 6)])
		out = extract_text(p)
		for i in range(1, 6):
			self.assertIn(f"第{i}頁標題", out)
		self.assertLess(out.index("第1頁標題"), out.index("第5頁標題"))

	def test_標題不會重複出現在內文列(self):
		# slide.shapes 每次迭代都給新的 proxy 物件，用 `is` 比對會失效，
		# 標題會同時被當成標題和內文各印一次
		p = self.path("a.pptx")
		make_pptx.make(p, [("唯一標題", ["內容"])])
		self.assertEqual(extract_text(p).count("唯一標題"), 1)

	def test_備忘稿要掛在正確的頁_不是照檔名編號(self):
		# 這是本 Task 最重要的一則。只有第 2、4 頁有備忘稿時，
		# 檔案裡是 notesSlide1.xml（屬於 slide2）與 notesSlide2.xml（屬於 slide4）。
		# 照檔名編號對應會把第 2 頁的備忘稿掛到第 1 頁。
		p = self.path("a.pptx")
		make_pptx.make(p,
			[(f"第{i}頁標題", [f"第{i}頁內容"]) for i in range(1, 6)],
			{2: "這句屬於第二頁", 4: "這句屬於第四頁"})
		out = extract_text(p)
		pages = out.split("## 第 ")
		self.assertNotIn("備忘稿", pages[1])
		self.assertIn("這句屬於第二頁", pages[2])
		self.assertNotIn("備忘稿", pages[3])
		self.assertIn("這句屬於第四頁", pages[4])
		self.assertNotIn("備忘稿", pages[5])

	def test_全是圖沒有文字要丟錯(self):
		p = self.path("a.pptx")
		make_pptx.make_blank(p)
		with self.assertRaises(ValueError):
			extract_text(p)

	def test_不支援的副檔名要丟錯(self):
		p = self.path("a.pdf")
		open(p, "w", encoding="utf-8").write("x")
		with self.assertRaises(ValueError):
			extract_text(p)

	def test_SUPPORTED_是白名單來源(self):
		self.assertEqual(SUPPORTED, (".md", ".txt", ".pptx"))


class TestLessonId(unittest.TestCase):
	def test_英數檔名維持既有行為(self):
		self.assertEqual(lesson_id_for("/x/c_string.md"), "c_string")
		self.assertEqual(lesson_id_for("/x/C-Struct Combo.pptx"), "c_struct_combo")

	def test_中文檔名不會全部壓成底線互撞(self):
		a = lesson_id_for("/x/測試教材.pptx")
		b = lesson_id_for("/x/另一份教材.pptx")
		self.assertNotEqual(a, b)
		self.assertRegex(a, r"^[a-z0-9_]+$")


if __name__ == "__main__":
	unittest.main()
