import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import serve


class TestServeHelpers(unittest.TestCase):
	def test_TTS_探測_連不上要回_False(self):
		self.assertFalse(serve.tts_ready("http://127.0.0.1:1", timeout=0.5))

	def test_副檔名白名單來自_ingest(self):
		self.assertTrue(serve.allowed("a.md"))
		self.assertTrue(serve.allowed("a.pptx"))
		self.assertFalse(serve.allowed("a.pdf"))
		self.assertFalse(serve.allowed("a.md.exe"))

	def test_檔名清理_去掉路徑元素(self):
		self.assertEqual(serve.safe_name("../../etc/passwd.md"), "passwd.md")
		self.assertEqual(serve.safe_name("a b/c.pptx"), "c.pptx")


class TestMultipart(unittest.TestCase):
	def _body(self, blob, boundary=b"XBOUND"):
		return (b"--" + boundary + b"\r\n"
			b'Content-Disposition: form-data; name="file"; filename="a.pptx"\r\n'
			b"Content-Type: application/octet-stream\r\n\r\n"
			+ blob + b"\r\n--" + boundary + b"--\r\n")

	def test_二進位內容一個位元組都不能少(self):
		# .pptx 是 zip，結尾本來就可能有 0x0D / 0x0A / 0x2D。
		# 舊版用 rstrip(b"\r\n-") 去尾會把這些真實資料吃掉，解壓時炸 BadZipFile
		blob = bytes([0x50, 0x4B, 0x05, 0x06]) + b"\x00" * 8 + b"\r\n--\r\n-"
		name, got, sec = serve.parse_multipart(
			self._body(blob), "multipart/form-data; boundary=XBOUND")
		self.assertEqual(name, "a.pptx")
		self.assertEqual(got, blob)

	def test_真的_pptx_過一輪還解得開(self):
		import sys as _s
		_s.path.insert(0, os.path.join(ROOT, "tests/fixtures"))
		import zipfile
		import make_pptx
		src = os.path.join(ROOT, "tests/fixtures/_mp_check.pptx")
		make_pptx.make(src, [("標題", ["內容"])])
		with open(src, "rb") as f:
			blob = f.read()
		_, got, _ = serve.parse_multipart(
			self._body(blob), "multipart/form-data; boundary=XBOUND")
		self.assertEqual(got, blob)
		dst = os.path.join(ROOT, "tests/fixtures/_mp_out.pptx")
		with open(dst, "wb") as f:
			f.write(got)
		zipfile.ZipFile(dst).testzip()      # 解不開會丟例外
		os.remove(src)
		os.remove(dst)


class TestReviewTimer(unittest.TestCase):
	def setUp(self):
		self.now = [1000.0]

	def _job(self):
		from jobstate import Job

		def runner(a, b):
			yield {"event": "stage_start", "stage": a}
			yield {"event": "stage_end", "stage": a, "sec": 0.1}

		return Job("m.md", "/tmp/out", 110, runner, clock=lambda: self.now[0])

	def test_計時器搶走之後_使用者送出要拿到明確錯誤而不是被靜默丟棄(self):
		j = self._job()
		j.start()
		self.now[0] = 1061.0
		self.assertTrue(j.claim())           # 計時器搶到
		self.assertFalse(j.claim())          # 使用者這時才送出，必須被擋下
		self.assertNotEqual(j.status, "awaiting_review")

	def test_計時器不可在持鎖狀態下同步跑管線(self):
		# _review_timer 若同步呼叫 resume()，會跑滿 90 秒的語音合成與影格渲染。
		# 期間握著 _lock 的話，所有進來的 POST 全部卡死，服務形同當機
		import inspect
		src = inspect.getsource(serve._review_timer)
		self.assertIn("threading.Thread", src)
		self.assertNotIn("with _lock", src)


if __name__ == "__main__":
	unittest.main()
