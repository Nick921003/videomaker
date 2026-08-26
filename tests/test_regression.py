import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv/bin/python")
COMPILE = os.path.join(ROOT, "video_engine/compile_timeline.py")
EXAMPLES = os.path.join(ROOT, "video_engine/examples")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "regression")

SUMMARY_RE = re.compile(r"總長 [\d.]+ 秒，\d+ 個場景")


class TestRegression(unittest.TestCase):
	"""compile_timeline.py 的回歸檢查：兩個委交的固定案例要編譯乾淨、無警告無錯誤。

	輸入來自 tests/fixtures/regression/，路徑已洗過；compile_timeline 不開
	這些檔案，只把字串抄進時間軸。

	原本的檢查是 shell 一行指令 `... | grep -E "WARN|ERROR"; echo $?`——$? 抓到
	的是 grep 的退出碼，不是 compile_timeline.py 的；而且只 pipe 了 stdout。
	compile_timeline.py 真的崩潰時 stdout 是空的、traceback 印在 stderr，grep
	在空字串裡找不到 WARN/ERROR 就回傳 1，那個檢查反而會報「零診斷，正確」。
	崩掉的檢查和通過的檢查完全無法區分。這裡換成真的會失敗的 unittest：
	先斷言退出碼，再斷言有編譯摘要，最後才斷言沒有 WARN/ERROR 診斷。
	"""

	def _run(self, lesson_json, actions_json, lesson_id_for_layout):
		"""對指定教材跑 compile_timeline.py，回傳 CompletedProcess。

		layout.json／durations.json 從 tests/fixtures/regression/<lesson_id_for_layout>/
		複製到暫存目錄再餵給 compile_timeline.py，不寫進受版控的輸出目錄。
		"""
		src = os.path.join(FIXTURES, lesson_id_for_layout)
		with tempfile.TemporaryDirectory() as tmp:
			shutil.copy(os.path.join(src, "layout.json"), tmp)
			shutil.copy(os.path.join(src, "durations.json"), tmp)
			return subprocess.run([PY, COMPILE, lesson_json, actions_json, tmp],
				capture_output=True, text=True, timeout=60)

	def _assert_clean(self, lesson_id):
		lesson = os.path.join(EXAMPLES, f"{lesson_id}.lesson.json")
		actions = os.path.join(EXAMPLES, f"{lesson_id}.actions.json")
		r = self._run(lesson, actions, lesson_id)
		# 先斷言退出碼：崩潰要在這裡就現形，stderr 放進失敗訊息才看得到原因
		self.assertEqual(r.returncode, 0,
			f"compile_timeline.py 對 {lesson_id} 崩潰（退出碼 {r.returncode}）：\n{r.stderr}")
		self.assertRegex(r.stdout, SUMMARY_RE,
			f"stdout 沒有場景編譯摘要：\n{r.stdout}")
		for line in r.stdout.splitlines():
			stripped = line.strip()
			self.assertFalse(stripped.startswith("WARN") or stripped.startswith("ERROR"),
				f"{lesson_id} 出現診斷：{line}")

	def test_c_struct_編譯無診斷(self):
		self._assert_clean("c_struct")

	def test_c_string_編譯無診斷(self):
		self._assert_clean("c_string")


if __name__ == "__main__":
	unittest.main()
