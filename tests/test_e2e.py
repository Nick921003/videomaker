import os
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv/bin/python")
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

from ingest import lesson_id_for


def _remove_file(path):
	"""容錯移除：檔案不存在就跳過，讓 cleanup 不因為前一步沒跑到而炸開"""
	try:
		os.remove(path)
	except FileNotFoundError:
		pass


def _remove_dir(path):
	"""容錯移除輸出目錄：不存在就跳過"""
	shutil.rmtree(path, ignore_errors=True)


def _mp4_duration(path):
	"""用 ffprobe 讀影片時長（秒），只看檔案大小測不出「渲染出一支空殼」"""
	r = subprocess.run(
		["ffprobe", "-v", "error", "-show_entries", "format=duration",
			"-of", "default=noprint_wrappers=1:nokey=1", path],
		capture_output=True, text=True,
	)
	if r.returncode != 0:
		raise RuntimeError(f"ffprobe 失敗（回傳碼 {r.returncode}）：{r.stderr}")
	return float(r.stdout.strip())


@unittest.skipUnless(os.environ.get("E2E") == "1", "設 E2E=1 才跑，會真的呼叫 LLM 與 TTS")
class TestEndToEnd(unittest.TestCase):
	def test_pptx_進去_mp4_出來(self):
		sys.path.insert(0, os.path.join(ROOT, "tests/fixtures"))
		import make_pptx

		# lesson_id 不能自己硬寫。lesson_id_for 會把頭尾底線剝掉，
		# _e2e_deck 算出來是 e2e_deck——照檔名硬寫路徑會找不到產出，
		# 明明管線跑成功了測試卻紅。用管線同一個函式算才不會脫鉤
		deck = os.path.join(ROOT, "video_engine/materials/_e2e_deck.pptx")
		landed_md = os.path.join(ROOT, "video_engine/materials/_e2e_deck.md")
		lesson_id = lesson_id_for(deck)
		out_dir = os.path.join(ROOT, "video_engine/out", lesson_id)
		# 建檔前先掛 cleanup：斷言中途失敗也不會留下孤兒檔
		self.addCleanup(_remove_file, deck)
		self.addCleanup(_remove_file, landed_md)
		self.addCleanup(_remove_dir, out_dir)

		make_pptx.make(deck, [
			("C 語言的布林值", ["C89 沒有 bool 型態", "非零即真，零為假"]),
			("實務寫法", ["用 int 代替", "或 include stdbool.h"]),
		], {1: "重點是初學者常以為 C 有 bool，其實 C89 沒有。"})
		r = subprocess.run([PY, os.path.join(ROOT, "video_engine/run.py"), deck, "--sec", "60"],
			capture_output=True, text=True, timeout=900)
		self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
		mp4 = os.path.join(out_dir, lesson_id + ".mp4")
		self.assertTrue(os.path.exists(mp4))
		self.assertGreater(os.path.getsize(mp4), 100_000)
		self.assertGreater(_mp4_duration(mp4), 0)


if __name__ == "__main__":
	unittest.main()
