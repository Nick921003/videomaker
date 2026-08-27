#!/usr/bin/env python3
"""現場 Demo 用的本機服務：丟檔案 → 看八階段跑 → 確認講稿 → 拿 MP4。

只管 HTTP 與 job 狀態機，不含任何影片邏輯——所有影片知識留在 video_engine 裡。
同時只跑一個 job：LLM、TTS、CPU 都是單一資源，併發沒有意義。

用法：.venv/bin/python serve.py [埠號，預設 8899]
"""
import collections
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
CHUNK = 256 * 1024
TTS_URL = os.environ.get("TTS_API_URL", "http://127.0.0.1:9880")

_lock = threading.Lock()
_job = None          # 同時只有一個
_job_id = 0


class BadRange(Exception):
	"""Range 指到檔案外面，得回 416"""


def parse_range(header, size):
	"""解析 Range: bytes=... 回傳閉區間 (start, end)。

	沒帶或格式壞掉回 None（照 RFC 9110 當成整支要）；指到檔案外面丟 BadRange。
	只認第一個區間——瀏覽器拉進度條送的就是單一區間
	"""
	if not header or not header.startswith("bytes="):
		return None
	first, sep, last = header[len("bytes="):].split(",")[0].strip().partition("-")
	if not sep:
		return None
	try:
		if first:
			start, end = int(first), int(last) if last else size - 1
		elif last:
			start, end = max(0, size - int(last)), size - 1      # bytes=-500：最後 500 個位元組
		else:
			return None
	except ValueError:
		return None
	end = min(end, size - 1)
	if start > end or start >= size:
		raise BadRange(header)
	return start, end


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


_children = set()
_children_lock = threading.Lock()


def spawn(args):
	"""開子行程並登記。登記是為了 Ctrl+C 時收得掉——
	執行緒是 daemon 會跟著死，但 Popen 是獨立的 OS 行程不會"""
	p = subprocess.Popen(args, stdout=subprocess.DEVNULL,
		stderr=subprocess.PIPE, text=True, bufsize=1)
	with _children_lock:
		_children.add(p)
	return p


def reap(p):
	"""確保子行程死透並解除登記。可以重複呼叫。

	p.wait() 不會關 p.stderr——那是獨立的檔案物件，process 死了它還開著。
	不在這裡關掉的話，Popen 物件被回收時會噴 ResourceWarning，把測試輸出弄髒
	"""
	if p.poll() is None:
		p.kill()
		p.wait()
	if p.stderr:
		p.stderr.close()
	with _children_lock:
		_children.discard(p)


def kill_children():
	"""收掉所有還活著的子行程，回傳收掉幾個"""
	with _children_lock:
		alive = list(_children)
	for p in alive:
		reap(p)
	return len(alive)


def live_children():
	with _children_lock:
		return set(_children)


def shutdown(srv):
	"""收工：先收子行程再關 socket。

	執行緒是 daemon 會跟著行程死，但 Popen 是獨立的 OS 行程不會——
	不在這裡收掉的話，按了 Ctrl+C 之後管線還在背景跑、還在打 TTS、
	還在寫檔案，而操作者以為已經停了。
	"""
	n = kill_children()
	srv.server_close()
	return n


def real_runner(material, sec, layout=None, seed=None):
	"""把 run.py --json-events 的 stderr 逐行轉成事件流。

	非 JSON 的那些行不是雜訊——sub-stage（validate.py 之類）的 traceback
	跟 run.py 自己印的 JSON 事件走同一條繼承來的 stderr。舊版整段丟掉的話，
	operator 只看得到「階段 X 失敗」，過期金鑰、額度用盡、TTS 拒接長得一模一樣。
	留最後 20 行掛在 stage_fail 事件上，跟著 job.error 一起送到前端
	"""
	def runner(stage_from, stage_to):
		args = [PY, RUN, material, "--from", stage_from, "--until", stage_to, "--json-events"]
		if sec:
			args += ["--sec", str(sec)]
		if layout:
			args += ["--layout", str(layout)]
		if seed is not None:
			args += ["--seed", str(seed)]
		p = spawn(args)
		saw_fail = False
		tail = collections.deque(maxlen=20)
		try:
			for line in p.stderr:
				line = line.strip()
				if not line.startswith("{"):
					if line:
						tail.append(line)
					continue
				try:
					ev = json.loads(line)
				except json.JSONDecodeError:
					if line:
						tail.append(line)      # 底層套件的警告訊息也可能以 { 開頭，不能讓它炸掉整條 runner
					continue
				if ev.get("event") == "stage_fail":
					saw_fail = True
					ev["tail"] = list(tail)
				yield ev
			p.wait()
			# run.py 若是被 SyntaxError、MemoryError 這類炸掉的，根本來不及印事件。
			# 沒有這一條的話 job 會永遠停在 running，前端進度條卡死
			if p.returncode != 0 and not saw_fail:
				yield {"event": "stage_fail", "stage": stage_to, "code": p.returncode, "tail": list(tail)}
		finally:
			# generator 被丟棄時 Python 會在 yield 處丟 GeneratorExit，
			# finally 照樣執行——子行程就是靠這裡收掉的
			reap(p)
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
		path, _, query = self.path.partition("?")
		if path == "/":
			with open(os.path.join(WEB, "index.html"), "rb") as f:
				html = f.read()
			return self._send(200, html, "text/html; charset=utf-8")
		if path.endswith("/events"):
			return self._events()
		if path.endswith("/script"):
			# 只有進審稿階段才有 actions_path，早打會拿 None 去開檔案
			if not _job or _job.status != "awaiting_review":
				return self._json(409, {"error": "現在不在審稿階段"})
			return self._json(200, {"segments": read_segments(_job.actions_path),
				"deadline": _job.review_deadline})
		if "/slide/" in path:
			return self._slide(path.rsplit("/slide/", 1)[1])
		if path.endswith("/video"):
			if not _job or _job.status != "done":
				return self._json(404, {"error": "影片還沒好"})
			return self._video(_job.video_path, "dl=1" in query)
		self._json(404, {"error": "找不到"})

	def _slide(self, slide_id):
		"""把該頁已繪製的投影片端出去。

		審稿的人看不到頁面長什麼樣就只能盲改稿——投影片在 slides 階段就畫好了，
		那一階段排在審稿閘之前，所以進審稿畫面時圖一定在
		"""
		if not _job or not _job.layout_path or not os.path.exists(_job.layout_path):
			return self._json(404, {"error": "投影片還沒繪製"})
		with open(_job.layout_path, encoding="utf-8") as f:
			ids = [s["slide_id"] for s in json.load(f)["slides"]]
		if slide_id not in ids:
			return self._json(404, {"error": f"沒有這一頁：{slide_id}"})
		# 檔名照 render_slides 的生成規則自己算，不採用 layout.json 存的絕對路徑：
		# 那是產生當下那台機器的路徑，搬過目錄或換一台機器就指到不存在的檔案。
		# 自己算也順便杜絕了 slide_id 夾路徑元素的可能
		png = os.path.join(os.path.dirname(_job.layout_path),
			f"slide_{ids.index(slide_id) + 1:02d}_full.png")
		if not os.path.exists(png):
			return self._json(404, {"error": "投影片圖不見了"})
		with open(png, "rb") as f:
			return self._send(200, f.read(), "image/png")

	def _video(self, path, as_download):
		"""帶 Range 的影片回應。

		瀏覽器的 <video> 只要沒收到 Accept-Ranges: bytes 就直接停用拖曳進度條——
		舊版整支檔案一次回 200，所以片子放得出來、但進度條點不動。
		拖曳時瀏覽器會大量中止請求，寫到一半斷線是正常現象，不能噴 traceback
		"""
		size = os.path.getsize(path)
		try:
			rng = parse_range(self.headers.get("Range"), size)
		except BadRange:
			self.send_response(416)
			self.send_header("Content-Range", f"bytes */{size}")
			self.send_header("Content-Length", "0")
			self.end_headers()
			return
		start, end = rng if rng else (0, size - 1)
		self.send_response(206 if rng else 200)
		self.send_header("Content-Type", "video/mp4")
		self.send_header("Accept-Ranges", "bytes")
		self.send_header("Content-Length", str(end - start + 1))
		if rng:
			self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
		# inline 也要給 filename：<a download> 沒帶檔名時瀏覽器拿網址最後一段命名，
		# 會存成沒有副檔名的 "video"
		self.send_header("Content-Disposition",
			f'{"attachment" if as_download else "inline"}; filename="{os.path.basename(path)}"')
		self.end_headers()
		remain = end - start + 1
		try:
			with open(path, "rb") as f:
				f.seek(start)
				while remain > 0:
					chunk = f.read(min(CHUNK, remain))
					if not chunk:
						break
					self.wfile.write(chunk)
					remain -= len(chunk)
		except (BrokenPipeError, ConnectionResetError, OSError):
			pass      # 拖曳進度條就是不斷中止舊請求，安靜收工

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
		length = int(self.headers.get("Content-Length", 0))
		# 409／503／413 都要在回覆前把整個 body 讀乾淨。BaseHTTPRequestHandler
		# 預設 HTTP/1.0，回應送出後就關連線；receive buffer 裡還有沒讀完的資料的話，
		# 對端看到的是 RST 不是正常關閉——瀏覽器只會回報「連不上」，
		# 蓋掉真正的錯誤訊息（例如 TTS 沒開的 503），現場最常見的翻車點反而看不到
		body = self.rfile.read(length)
		with _lock:
			if _job and _job.status in ("queued", "running", "awaiting_review"):
				return self._json(409, {"error": "已經有一個工作在跑，等它跑完"})
			if not tts_ready():
				return self._json(503, {"error": f"語音服務 {TTS_URL} 沒有回應，先把 GPT-SoVITS 開起來"})
			if length > MAX_UPLOAD:
				return self._json(413, {"error": "檔案超過 5 MB"})
			mp = parse_multipart(body, self.headers.get("Content-Type", ""))
			name, blob, sec, layout, seed = mp.name, mp.blob, mp.sec, mp.layout, mp.seed
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
			_job = Job(md, OUT, sec, real_runner(md, sec, layout, seed))
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
		try:
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
		except Exception as e:
			# claim() 已經把狀態翻成 running，但這一段是同步跑在 request handler
			# 裡、沒有 _guard 接住。shutil.copy 找不到 actions_path、revalidate
			# 裡的 subprocess.run 直譯器路徑錯了炸 FileNotFoundError（只有
			# RuntimeError 會被上面接住）都會走到這裡。不接住的話狀態永遠停在
			# running，之後每個上傳都吃 409，現場只能重啟服務——跟 _guard 保護
			# 背景執行緒是同一個理由，只是這段沒有經過 _guard
			_job.status = "failed"
			_job.error = f"{type(e).__name__}: {e}"
			return self._json(500, {"error": f"核可流程失敗：{_job.error}"})
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


class MultipartResult(tuple):
	def __new__(cls, name, blob, sec, layout=None, seed=None):
		obj = super().__new__(cls, (name, blob, sec))
		obj.name = name
		obj.blob = blob
		obj.sec = sec
		obj.layout = layout
		obj.seed = seed
		return obj


def parse_multipart(body, ctype):
	"""只解析我們自己前端送的欄位：file、sec、layout 與 seed。
	不用 cgi 模組——Python 3.13 已經移除它。

	去尾必須精確切掉那兩個 CRLF 位元組，不能用 rstrip(b"\r\n-")：
	.pptx 是二進位 zip，結尾本來就可能有 0x0D／0x0A／0x2D，
	rstrip 會把檔案結構吃掉，解壓時炸 BadZipFile。
	"""
	boundary = ctype.split("boundary=")[-1].strip().strip('"').encode()
	name, blob, sec, layout, seed = "", b"", None, None, None
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
		elif 'name="layout"' in h:
			layout = data.decode().strip() or None
		elif 'name="seed"' in h:
			seed = data.decode().strip() or None
	return MultipartResult(name, blob, sec, layout, seed)


def make_server(port):
	return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
	port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
	srv = make_server(port)
	print(f"開好了：http://127.0.0.1:{port}")
	try:
		srv.serve_forever()
	except KeyboardInterrupt:
		print("\n收工中…")
	finally:
		n = shutdown(srv)
		if n:
			print(f"收掉了 {n} 個還在跑的子行程")
