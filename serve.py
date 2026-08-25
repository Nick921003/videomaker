#!/usr/bin/env python3
"""現場 Demo 用的本機服務：丟檔案 → 看八階段跑 → 確認講稿 → 拿 MP4。

只管 HTTP 與 job 狀態機，不含任何影片邏輯——所有影片知識留在 video_engine 裡。
同時只跑一個 job：LLM、TTS、CPU 都是單一資源，併發沒有意義。

用法：.venv/bin/python serve.py [埠號，預設 8899]
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_engine"))

from ingest import SUPPORTED
from jobstate import REVIEW_SEC, Job
from run import next_free, resolve_material
from script_gate import read_segments, revalidate, write_segments

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, ".venv/bin/python")
RUN = os.path.join(HERE, "video_engine/run.py")
MATERIALS = os.path.join(HERE, "video_engine/materials")
OUT = os.path.join(HERE, "video_engine/out")
WEB = os.path.join(HERE, "web")
MAX_UPLOAD = 5 * 1024 * 1024
TTS_URL = os.environ.get("TTS_API_URL", "http://127.0.0.1:9880")

_lock = threading.Lock()
_job = None          # 同時只有一個
_job_id = 0


def allowed(name):
	return os.path.splitext(name)[1].lower() in SUPPORTED


def safe_name(name):
	"""只留檔名，丟掉任何路徑元素"""
	return os.path.basename(name.replace("\\", "/"))


def tts_ready(url=TTS_URL, timeout=3.0):
	"""GPT-SoVITS 沒開是現場最常見的翻車點，收件前先探。
	404 也算活著——只要 TCP 通、HTTP 有回應就行"""
	try:
		with urllib.request.urlopen(url, timeout=timeout):
			return True
	except urllib.error.HTTPError:
		return True
	except Exception:
		return False


def _guard(job, fn, *args):
	"""執行緒裡炸掉的話，狀態要留下痕跡。

	沒有這層的話，job 會永遠停在 running，之後每個上傳都吃 409——
	現場等於整台停擺，而且畫面上看不出發生了什麼事。
	"""
	try:
		fn(*args)
	except Exception as e:
		job.status = "failed"
		job.error = f"{type(e).__name__}: {e}"


def real_runner(material, sec):
	"""把 run.py --json-events 的 stderr 逐行轉成事件流"""
	def runner(stage_from, stage_to):
		args = [PY, RUN, material, "--from", stage_from, "--until", stage_to, "--json-events"]
		if sec:
			args += ["--sec", str(sec)]
		p = subprocess.Popen(args, stdout=subprocess.DEVNULL,
			stderr=subprocess.PIPE, text=True, bufsize=1)
		saw_fail = False
		for line in p.stderr:
			line = line.strip()
			if not line.startswith("{"):
				continue
			try:
				ev = json.loads(line)
			except json.JSONDecodeError:
				continue      # 底層套件的警告訊息也可能以 { 開頭，不能讓它炸掉整條 runner
			saw_fail = saw_fail or ev.get("event") == "stage_fail"
			yield ev
		p.wait()
		# run.py 若是被 SyntaxError、MemoryError 這類炸掉的，根本來不及印事件。
		# 沒有這一條的話 job 會永遠停在 running，前端進度條卡死
		if p.returncode != 0 and not saw_fail:
			yield {"event": "stage_fail", "stage": stage_to, "code": p.returncode}
	return runner


class Handler(BaseHTTPRequestHandler):
	def _send(self, code, body=b"", ctype="application/json"):
		self.send_response(code)
		self.send_header("Content-Type", ctype)
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def _json(self, code, obj):
		self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

	def do_GET(self):
		if self.path == "/":
			with open(os.path.join(WEB, "index.html"), "rb") as f:
				html = f.read()
			return self._send(200, html, "text/html; charset=utf-8")
		if self.path.endswith("/events"):
			return self._events()
		if self.path.endswith("/script"):
			# 只有進審稿階段才有 actions_path，早打會拿 None 去開檔案
			if not _job or _job.status != "awaiting_review":
				return self._json(409, {"error": "現在不在審稿階段"})
			return self._json(200, {"segments": read_segments(_job.actions_path),
				"deadline": _job.review_deadline})
		if self.path.endswith("/video"):
			if not _job or _job.status != "done":
				return self._json(404, {"error": "影片還沒好"})
			with open(_job.video_path, "rb") as f:
				data = f.read()
			return self._send(200, data, "video/mp4")
		self._json(404, {"error": "找不到"})

	def _events(self):
		"""SSE：把 job 的事件與進度推給前端"""
		self.send_response(200)
		self.send_header("Content-Type", "text/event-stream")
		self.send_header("Cache-Control", "no-cache")
		self.end_headers()
		seen, last_state = 0, None
		while True:
			if not _job:
				break
			try:
				while seen < len(_job.events):
					ev = dict(_job.events[seen])
					ev.update(status=_job.status, pct=_job.pct)
					self._push(ev)
					seen += 1
				if _job.status in ("done", "failed", "awaiting_review"):
					state = {"event": "state", "status": _job.status, "pct": _job.pct,
						"stage": _job.stage, "error": _job.error,
						"deadline": _job.review_deadline}
					# 只在真的變了才推。審稿那 60 秒狀態不會動，
					# 無條件推的話會在倒數期間送出 150 個一模一樣的封包
					if state != last_state:
						self._push(state)
						last_state = state
					if _job.status != "awaiting_review":
						break
			except (BrokenPipeError, ConnectionResetError, OSError):
				break     # 瀏覽器關掉或重整，安靜收工，不要噴 traceback
			threading.Event().wait(0.4)

	def _push(self, obj):
		self.wfile.write(f"data: {json.dumps(obj, ensure_ascii=False)}\n\n".encode())
		self.wfile.flush()

	def do_POST(self):
		global _job, _job_id
		if self.path == "/jobs":
			return self._create()
		if self.path.endswith("/approve"):
			return self._approve()
		self._json(404, {"error": "找不到"})

	def _create(self):
		global _job, _job_id
		with _lock:
			if _job and _job.status in ("queued", "running", "awaiting_review"):
				return self._json(409, {"error": "已經有一個工作在跑，等它跑完"})
			if not tts_ready():
				return self._json(503, {"error": f"語音服務 {TTS_URL} 沒有回應，先把 GPT-SoVITS 開起來"})
			length = int(self.headers.get("Content-Length", 0))
			if length > MAX_UPLOAD:
				return self._json(413, {"error": "檔案超過 5 MB"})
			name, blob, sec = parse_multipart(self.rfile.read(length),
				self.headers.get("Content-Type", ""))
			name = safe_name(name)
			if not allowed(name):
				return self._json(400, {"error": f"不支援 {name}，只吃 {'、'.join(SUPPORTED)}"})
			os.makedirs(MATERIALS, exist_ok=True)
			# 原始檔也要走「同名加序號」，跟 resolve_material 一致。
			# 若這裡覆寫、那裡加序號，deck.pptx 被蓋掉但抽出來的變成 deck_2.md，
			# lesson_id 跟著變成 deck_2，materials/ 與 examples/ 留下一堆孤兒
			raw = next_free(os.path.join(MATERIALS, name))
			with open(raw, "wb") as f:
				f.write(blob)
			# 收件當下就落地成 .md，之後兩段 run.py 一律只傳這個路徑。
			# 若兩段都傳 .pptx，第二段會因為 deck.md 已存在而產生 deck_2.md，
			# 然後去找不存在的 examples/deck_2.lesson.json 直接崩潰
			try:
				md = resolve_material(raw, MATERIALS)
			except ValueError as e:
				return self._json(400, {"error": str(e)})
			_job_id += 1
			_job = Job(md, OUT, sec, real_runner(md, sec))
			threading.Thread(target=_guard, args=(_job, _start_job, _job), daemon=True).start()
		self._json(201, {"job_id": _job_id})

	def _approve(self):
		length = int(self.headers.get("Content-Length", 0))
		payload = json.loads(self.rfile.read(length) or b"{}")
		segs = payload.get("segments") or []
		# 這裡刻意不看 review_expired()。倒數由計時器負責推進，claim() 誰搶到算誰的。
		# 舊版在這裡判逾時，網路延遲一秒就把人改好的稿靜默丟掉
		if not _job or not _job.claim():
			return self._json(409, {"error": "倒數已到，已用原稿繼續合成"})
		# claim 成功＝狀態已是 running，計時器不會再插手。
		# 重驗要開 subprocess（約 0.3 秒），不放在 _lock 裡
		notice = None
		if segs:
			shutil.copy(_job.actions_path, _job.actions_backup)   # 每次都重新備份
			write_segments(_job.actions_path, segs)
			try:
				errs = revalidate(_job.lesson_path, _job.actions_path, _job.sec)
			except RuntimeError as e:
				# 驗證器本身炸了。不能當成「通過」放行——那正是這個閘存在的理由
				shutil.copy(_job.actions_backup, _job.actions_path)
				errs = [f"驗證器沒跑起來：{e}"]
			if errs:
				# 一律還原。壞稿絕不能進 TTS——這是驗證閘存在的理由
				shutil.copy(_job.actions_backup, _job.actions_path)
				if not _job.retried:
					_job.retried = True
					_job.status = "awaiting_review"      # 放回審稿，重開一輪倒數
					_job.review_deadline = _job.clock() + REVIEW_SEC
					threading.Thread(target=_review_timer, args=(_job,), daemon=True).start()
					return self._json(400, {"errors": errs,
						"deadline": _job.review_deadline})
				notice = "講稿兩次都沒通過驗證，已改用原稿繼續"
		_job.notice = notice
		threading.Thread(target=_guard, args=(_job, _job.resume), daemon=True).start()
		self._json(200, {"ok": True, "notice": notice})


def _start_job(job):
	job.start()
	if job.status == "awaiting_review":
		threading.Thread(target=_review_timer, args=(job,), daemon=True).start()


def _review_timer(job):
	"""後端自己的倒數。瀏覽器關掉、網路斷了、人走開了，job 都不能永遠卡在
	awaiting_review——那會讓之後每一個上傳都吃 409，現場等於整台停擺。

	絕對不可以在這裡同步呼叫 resume()：它會跑滿語音合成與影格渲染（90 秒以上）。
	若那時還握著 _lock，期間所有 POST 都會卡在鎖後面動彈不得，服務形同當機。
	claim() 已經原子地把狀態翻成 running，計時器不必也不該再持 _lock。
	"""
	while job.status == "awaiting_review":
		if job.review_expired():
			if job.claim():
				job.notice = "倒數結束，沒有人反對，已用原稿繼續"
				threading.Thread(target=_guard, args=(job, job.resume), daemon=True).start()
			return
		time.sleep(0.5)


def parse_multipart(body, ctype):
	"""只解析我們自己前端送的兩個欄位：file 與 sec。
	不用 cgi 模組——Python 3.13 已經移除它。

	去尾必須精確切掉那兩個 CRLF 位元組，不能用 rstrip(b"\r\n-")：
	.pptx 是二進位 zip，結尾本來就可能有 0x0D／0x0A／0x2D，
	rstrip 會把檔案結構吃掉，解壓時炸 BadZipFile。
	"""
	boundary = ctype.split("boundary=")[-1].strip().strip('"').encode()
	name, blob, sec = "", b"", None
	for part in body.split(b"--" + boundary):
		if b"\r\n\r\n" not in part:
			continue
		head, data = part.split(b"\r\n\r\n", 1)
		if data.endswith(b"\r\n"):     # 每個 part 結尾固定是一組 CRLF，只砍這兩個位元組
			data = data[:-2]
		h = head.decode("utf-8", "replace")
		if 'name="file"' in h:
			name = h.split('filename="')[1].split('"')[0]
			blob = data
		elif 'name="sec"' in h:
			sec = data.decode().strip() or None
	return name, blob, sec


def make_server(port):
	return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
	port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
	print(f"開好了：http://127.0.0.1:{port}")
	make_server(port).serve_forever()
