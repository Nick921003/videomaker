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
OUT = os.path.join(ROOT, "video_engine/out")

SUMMARY_RE = re.compile(r"總長 [\d.]+ 秒，\d+ 個場景")


def _missing_input(lesson_id):
	"""回傳這個 lesson_id 缺的第一個必要檔案路徑，都在的話回傳 None。

	layout.json／durations.json 不在版控裡（.gitignore 排除整個
	video_engine/out/），乾淨的 clone 上一定沒有，只能靠本機真的跑過一次
	管線（synth 階段量測語音長度）才會生出來——不是可以簡單補的 fixture。
	缺了就該讓測試明確 SKIP，而不是留給 shutil.copy 炸出一個看起來像
	程式錯誤、其實只是「還沒在這台機器跑過管線」的 FileNotFoundError
	"""
	lesson = os.path.join(EXAMPLES, f"{lesson_id}.lesson.json")
	actions = os.path.join(EXAMPLES, f"{lesson_id}.actions.json")
	layout = os.path.join(OUT, lesson_id, "layout.json")
	durations = os.path.join(OUT, lesson_id, "durations.json")
	for path in (lesson, actions, layout, durations):
		if not os.path.exists(path):
			return path
	return None


_MISSING_C_STRUCT = _missing_input("c_struct")
_MISSING_C_STRING = _missing_input("c_string")


class TestRegression(unittest.TestCase):
	"""compile_timeline.py 的回歸檢查：兩個委交的固定案例要編譯乾淨、無警告無錯誤。

	原本的檢查是 shell 一行指令 `... | grep -E "WARN|ERROR"; echo $?`——$? 抓到
	的是 grep 的退出碼，不是 compile_timeline.py 的；而且只 pipe 了 stdout。
	compile_timeline.py 真的崩潰時 stdout 是空的、traceback 印在 stderr，grep
	在空字串裡找不到 WARN/ERROR 就回傳 1，那個檢查反而會報「零診斷，正確」。
	崩掉的檢查和通過的檢查完全無法區分。這裡換成真的會失敗的 unittest：
	先斷言退出碼，再斷言有編譯摘要，最後才斷言沒有 WARN/ERROR 診斷。
	"""

	def _run(self, lesson_json, actions_json, lesson_id_for_layout):
		"""對指定教材跑 compile_timeline.py，回傳 CompletedProcess。

		layout.json／durations.json 從既有的 video_engine/out/<lesson_id_for_layout>/
		複製到暫存目錄再餵給 compile_timeline.py，不寫進受版控的輸出目錄。
		"""
		src_out = os.path.join(OUT, lesson_id_for_layout)
		with tempfile.TemporaryDirectory() as tmp:
			shutil.copy(os.path.join(src_out, "layout.json"), tmp)
			shutil.copy(os.path.join(src_out, "durations.json"), tmp)
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

	@unittest.skipUnless(_MISSING_C_STRUCT is None,
		f"缺 {_MISSING_C_STRUCT}——這是跑過一次本機管線（含 synth 語音合成）才會產生的檔案")
	def test_c_struct_編譯無診斷(self):
		self._assert_clean("c_struct")

	@unittest.skipUnless(_MISSING_C_STRING is None,
		f"缺 {_MISSING_C_STRING}——這是跑過一次本機管線（含 synth 語音合成）才會產生的檔案")
	def test_c_string_編譯無診斷(self):
		self._assert_clean("c_string")


if __name__ == "__main__":
	unittest.main()
