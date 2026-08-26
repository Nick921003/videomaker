import io
import json
import os
import sys
import threading
import time
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import serve


def _rm(path):
	"""清掉測試落地的暫存檔，檔案已經不在（例如上一步就砍過）也不算錯"""
	try:
		os.remove(path)
	except FileNotFoundError:
		pass


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
		self.addCleanup(_rm, src)      # 斷言失敗也要清，不能等到最後才砍
		with open(src, "rb") as f:
			blob = f.read()
		_, got, _ = serve.parse_multipart(
			self._body(blob), "multipart/form-data; boundary=XBOUND")
		self.assertEqual(got, blob)
		dst = os.path.join(ROOT, "tests/fixtures/_mp_out.pptx")
		with open(dst, "wb") as f:
			f.write(got)
		self.addCleanup(_rm, dst)
		zipfile.ZipFile(dst).testzip()      # 解不開會丟例外


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
		# 舊版本這裡是比對 _review_timer 原始碼字串（找 "threading.Thread"、
		# 找不到 "with _lock"）。兩邊都只是子字串比對，連出現在註解或
		# docstring 裡都算數——已經炸過一次假陽性；而且一個「有開執行緒、
		# 但同時又同步呼叫 resume()」的版本一樣會通過。改成行為測試：
		# 用一個會卡住的假 runner 模擬 90 秒的語音合成／影格渲染，把
		# _review_timer 丟到背景執行緒跑，趁 resume() 卡住的當下去搶
		# serve._lock——搶得到才代表計時器沒有在持鎖狀態下同步呼叫
		# resume()，不然現場所有 POST 都會卡死在鎖後面
		block = threading.Event()
		entered_after_review = threading.Event()

		def runner(stage_from, stage_to):
			yield {"event": "stage_start", "stage": stage_from}
			if stage_from != "lesson":     # AFTER_REVIEW（synth→video）：卡住模擬長時間工作
				entered_after_review.set()
				block.wait(5)
			yield {"event": "stage_end", "stage": stage_from, "sec": 0.1}

		j = self._job()
		j.runner = runner
		j.start()
		self.assertEqual(j.status, "awaiting_review")
		self.now[0] = j.review_deadline + 1     # 讓倒數視為已過期

		t = threading.Thread(target=serve._review_timer, args=(j,), daemon=True)
		t.start()
		try:
			self.assertTrue(entered_after_review.wait(2), "resume() 應該已經在背景開始跑")
			got = serve._lock.acquire(blocking=False)
			try:
				self.assertTrue(got, "計時器持有 _lock 的話，這裡就搶不到——服務會整台卡死")
			finally:
				if got:
					serve._lock.release()
		finally:
			block.set()      # 一定要放行，不然背景執行緒會卡到逾時才收工
			t.join(5)
			deadline = time.time() + 3
			while j.status not in ("done", "failed") and time.time() < deadline:
				time.sleep(0.01)


class TestGuard(unittest.TestCase):
	def test_背景執行緒炸掉要轉_failed_不能永遠卡在_running(self):
		# 模擬 subprocess.Popen 炸 FileNotFoundError 之類的情境：
		# runner 一被呼叫就炸，_pump 連第一個事件都收不到
		from jobstate import Job

		def exploding_runner(stage_from, stage_to):
			raise RuntimeError("模擬 runner 炸掉")

		job = Job("m.md", "/tmp/out", None, exploding_runner, clock=lambda: 1000.0)
		serve._guard(job, job.start)
		self.assertEqual(job.status, "failed")
		self.assertTrue(job.error)


class TestStageFailTail(unittest.TestCase):
	def test_stage_fail帶tail要接進job_error(self):
		# real_runner 把 sub-stage 沒被吞掉的 stderr（過期金鑰、額度用盡、
		# TTS 拒接的 traceback）收進 tail，掛在 stage_fail 事件上。
		# _pump 要把它接進 job.error，前端才看得到，不然「階段 X 失敗」
		# 這句話對現場操作者沒有任何資訊量——三種原因看起來一模一樣
		from jobstate import Job

		def failing_runner_with_tail(stage_from, stage_to):
			yield {"event": "stage_start", "stage": stage_from}
			yield {"event": "stage_fail", "stage": stage_from, "code": 1,
				"tail": ["Traceback (most recent call last):",
					"FileNotFoundError: video_engine/materials/x.md"]}

		job = Job("m.md", "/tmp/out", None, failing_runner_with_tail, clock=lambda: 1000.0)
		job.start()
		self.assertEqual(job.status, "failed")
		self.assertIn("FileNotFoundError", job.error)
		self.assertIn("video_engine/materials/x.md", job.error)


class TestApproveGuard(unittest.TestCase):
	def _fake_handler(self, body=b"{}"):
		"""不經過真的 HTTP 連線，繞過 BaseHTTPRequestHandler 的 socket 初始化。
		_approve 只用到 self.headers／self.rfile／self._json，給假的就夠了"""
		h = serve.Handler.__new__(serve.Handler)
		h.headers = {"Content-Length": str(len(body))}
		h.rfile = io.BytesIO(body)
		h.responses = []
		h._json = lambda code, obj: h.responses.append((code, obj))
		return h

	def test_claim後同步段炸掉要轉failed_不能卡在running(self):
		# claim() 之後、丟執行緒之前那段（回寫講稿、重驗）是同步跑在
		# request handler 裡，沒有 _guard 接住。這裡讓 shutil.copy 因為
		# actions_path 不存在而炸 FileNotFoundError，模擬現場真的會發生的
		# 情境；驗證狀態確實被標成 failed，而不是永遠卡在 claim() 翻好的
		# running——不然之後每個上傳都吃 409，只能重啟服務救
		from jobstate import Job

		def runner(a, b):
			yield {"event": "stage_start", "stage": a}
			yield {"event": "stage_end", "stage": a, "sec": 0.1}

		job = Job("m.md", "/tmp/out", None, runner, clock=lambda: 1000.0)
		job.status = "awaiting_review"
		job.actions_path = "/tmp/videomaker-test-不存在的-actions.json"
		job.actions_backup = job.actions_path + ".orig"

		old_job = serve._job
		serve._job = job
		self.addCleanup(setattr, serve, "_job", old_job)

		body = json.dumps({"segments": [{"slide_id": "s1", "idx": 0, "text": "改過的字"}]}).encode()
		handler = self._fake_handler(body)
		handler._approve()

		self.assertEqual(job.status, "failed")
		self.assertTrue(job.error)
		self.assertEqual(handler.responses[0][0], 500)


class TestDrainBody(unittest.TestCase):
	"""POST /jobs 在 409／503／413 提前回覆之前沒把 body 讀完的話，
	BaseHTTPRequestHandler 預設 HTTP/1.0、回應送出就關連線——receive
	buffer 裡還有沒讀完的資料，對端看到的是 RST 不是正常關閉。瀏覽器
	只會回報「連不上」，蓋掉真正的錯誤訊息（例如 TTS 沒開的 503），
	現場最常見的翻車點反而看不到"""

	def _fake_handler(self, body):
		h = serve.Handler.__new__(serve.Handler)
		h.headers = {"Content-Length": str(len(body)), "Content-Type": "text/plain"}
		h.rfile = io.BytesIO(body)
		h.responses = []
		h._json = lambda code, obj: h.responses.append((code, obj))
		return h

	def test_已有工作在跑_409前body要讀乾淨(self):
		body = b"x" * 2000
		handler = self._fake_handler(body)
		old_job = serve._job
		serve._job = types.SimpleNamespace(status="running")
		self.addCleanup(setattr, serve, "_job", old_job)

		handler._create()

		self.assertEqual(handler.responses[0][0], 409)
		self.assertEqual(handler.rfile.read(), b"", "body 沒讀完的話，收尾關連線會送出 RST")

	def test_檔案過大_413前body也要讀乾淨(self):
		body = b"x" * 2000
		handler = self._fake_handler(body)
		old_job, old_ready, old_max = serve._job, serve.tts_ready, serve.MAX_UPLOAD
		serve._job = None
		serve.tts_ready = lambda *a, **k: True      # 隔開對 TTS_URL 的真實網路呼叫
		serve.MAX_UPLOAD = 10
		self.addCleanup(setattr, serve, "_job", old_job)
		self.addCleanup(setattr, serve, "tts_ready", old_ready)
		self.addCleanup(setattr, serve, "MAX_UPLOAD", old_max)

		handler._create()

		self.assertEqual(handler.responses[0][0], 413)
		self.assertEqual(handler.rfile.read(), b"", "body 沒讀完的話，收尾關連線會送出 RST")


if __name__ == "__main__":
	unittest.main()
