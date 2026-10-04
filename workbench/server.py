#!/usr/bin/env python3
"""獨立影片工作室：教材素材庫、學生提問與單一 CLI 工作佇列。

用法：.venv/bin/python -m workbench.server [--port 8765] [--out video_engine/out/units]
"""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from . import formats
from .jobs import JobQueue, run_command, spent_usd
from .library import Library, read_json, safe_path

ROOT = Path(__file__).resolve().parents[1]
BOARD_DIR = ROOT / "video_engine/board"
STUDIO_DIR = BOARD_DIR / "studio"
PROJECT_PY = ROOT / ".venv/bin/python"
PLAYWRIGHT_PY = Path("~/.local/share/pipx/venvs/webwright/bin/python").expanduser()
MODEL = "google:gemini-3.8-flash"
# 每段預估：分鏡約 US$0.035＋Gemini 配音約 US$0.02（60–75 秒）
ESTIMATE_USD = 0.055
# 配音：gemini（預設，英文照原文唸）或 sovits（本機王老師，免費，需要 :9880）
TTS_MODE = os.environ.get("BOARD_TTS", "gemini")
MAX_BODY = 4 * 1024 * 1024
STORY_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}")
JOB_ID = re.compile(r"[a-f0-9]{32}")
LANGUAGES = ("Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Ruby", "Go",
	"Rust", "Kotlin", "Swift", "PHP", "SQL", "Dart", "Scala", "Lua", "Perl", "R")


class APIError(Exception):
	def __init__(self, status, message):
		super().__init__(message)
		self.status = status


def bigrams(text):
	characters = "".join(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\U00020000-\U0002ebef]", text))
	return {characters[i:i + 2] for i in range(len(characters) - 1)}


def jaccard(left, right):
	a, b = bigrams(left), bigrams(right)
	return len(a & b) / len(a | b) if a or b else 0.0


def match_score(question, entry):
	texts = [entry.get("question", ""), *entry.get("also_asks", []), entry.get("title", "")]
	return max((jaccard(question, text) for text in texts), default=0.0)


def tts_health():
	connection = http.client.HTTPConnection("127.0.0.1", 9880, timeout=3)
	try:
		connection.request("GET", "/tts")
		response = connection.getresponse()
		response.close()
		return True
	except (OSError, http.client.HTTPException):
		return False
	finally:
		connection.close()


class Studio:
	def __init__(self, out, command_runner=None, tts_checker=None, tts_mode=None):
		self.tts_mode = tts_mode or TTS_MODE
		self.library = Library(out)
		self.out = self.library.root
		self.command_runner = command_runner or run_command
		self.tts_checker = tts_checker or tts_health
		self.tts_available = self._tts_ready()
		self.job_queue = JobQueue(self.library, self._run_command, formats, tts_mode=self.tts_mode)
		self.lock = self.job_queue.lock

	def close(self):
		self.job_queue.close()

	def _run_command(self, argv, on_line):
		cli = Path(argv[1]).name
		if cli == "narrate.py":
			self.tts_available = self._tts_ready()
			if not self.tts_available:
				raise RuntimeError("配音伺服器沒開（:9880）")
			Path(argv[3]).mkdir(parents=True, exist_ok=True)
		code = self.command_runner(argv, on_line)
		if code:
			label = {"check.py": "驗證", "export.py": "出片", "selftest.py": "本機自我檢查"}.get(cli, cli)
			on_line(f"{label}失敗（結束碼 {code}），請查看工作紀錄")
		elif cli == "author.py":
			path = Path(argv[4]) / ("plan.json" if argv[2] == "plan" else f"{argv[5]}.scene.json")
			if not path.is_file():
				raise RuntimeError("生成程序沒有產生預期的規劃或分鏡檔案")
		elif cli == "export.py":
			path = Path(argv[3])
			if not path.is_file() or not path.stat().st_size:
				raise RuntimeError("出片程序沒有產生影片")
		return code

	def _tts_ready(self):
		if self.tts_mode != "sovits":
			return True
		try:
			return bool(self.tts_checker())
		except OSError:
			return False

	def _unit_dir(self, identifier):
		try:
			return self.library.unit_dir(identifier)
		except KeyError:
			raise APIError(404, "找不到教材")

	def _unit_path(self, identifier, relative):
		try:
			return self.library.path(identifier, relative)
		except KeyError:
			raise APIError(404, "找不到教材")
		except ValueError:
			raise APIError(404, "找不到檔案")

	def _spent_usd(self, identifier):
		return spent_usd(self._unit_dir(identifier), lambda relative: self._unit_path(identifier, relative))

	def _plan(self, identifier):
		self._unit_path(identifier, "plan.json")
		plan = self.library.plan(identifier)
		if plan is None:
			raise APIError(409, "請先規劃教材")
		stories = plan.get("stories", [])
		ids = [s.get("id") for s in stories]
		if (not ids or any(not isinstance(s, str) or not STORY_ID.fullmatch(s) or s == "highlight" for s in ids)
			or len(set(ids)) != len(ids)):
			raise APIError(500, "教材規劃的段落代號不正確")
		return plan

	def create_unit(self, payload):
		markdown, title = payload.get("markdown"), payload.get("title")
		if not isinstance(markdown, str) or not markdown.strip():
			raise APIError(400, "請提供教材 Markdown 內容")
		if title is not None and not isinstance(title, str):
			raise APIError(400, "教材標題必須是文字")
		with self.lock:
			try:
				identifier, created = self.library.create_unit(markdown, title)
			except ValueError:
				raise APIError(404, "找不到檔案")
			return {"unit_id": identifier, "created": created}

	def _unit_jobs(self, identifier):
		return [self.job_queue.get(jid) for jid, job in self.job_queue.jobs.items() if job["unit_id"] == identifier]

	def _targets(self, job, story):
		if "kind" in job:
			return job["kind"] == "highlight" if story == "highlight" else (
				job["kind"] == "stories" and story in job.get("stories", []))
		return job["item"] == story

	def _video_ready(self, identifier, story):
		video = self._unit_path(identifier, f"{story}/video.mp4")
		if not video.is_file() or video.stat().st_size == 0:
			return False
		for job in reversed(self._unit_jobs(identifier)):
			if not self._targets(job, story):
				continue
			if job["state"] == "done" or story in job.get("completed", []):
				return True
			if job["state"] == "failed" and ("kind" not in job or job.get("target", story) == story):
				return False
			if job["state"] == "running" and ("kind" not in job or job.get("target") == story):
				return False
		return True

	def _artifact(self, identifier, story):
		jobs = [j for j in self._unit_jobs(identifier) if self._targets(j, story)]
		active = next((j for j in jobs if j["state"] == "running"), None)
		active = active or next((j for j in jobs if j["state"] == "queued"), None)
		ready = self._video_ready(identifier, story)
		status = "done" if ready else active["state"] if active else "failed" if jobs and jobs[-1]["state"] == "failed" else "none"
		if active and active["state"] == "running":
			status, ready = "running", False
		duration = None
		if ready:
			report = read_json(self._unit_path(identifier, f"{story}/video.export.json"), {})
			timeline = read_json(self._unit_path(identifier, f"{story}/timeline.json"), {})
			duration = report.get("duration", timeline.get("duration"))
		costs = [j["costs"][story] if "kind" in j else j["spent_usd"] for j in self._unit_jobs(identifier)
			if ("kind" in j and story in j.get("costs", {})) or ("kind" not in j and self._targets(j, story))]
		return {"status": status, "video": f"/media/{identifier}/{story}/video.mp4" if ready else None,
			"duration": duration, "cost_usd": round(sum(costs), 8) if costs else None,
			"estimate_usd": 0.0 if ready or self._unit_path(identifier, f"{story}.scene.json").is_file() else ESTIMATE_USD}

	def get_unit(self, identifier):
		with self.lock:
			self._unit_dir(identifier)
			meta = self.library.meta(identifier)
			self._unit_path(identifier, "plan.json")
			plan = self.library.plan(identifier)
			if plan is not None:
				plan = self._plan(identifier)
				for story in plan["stories"]:
					story.setdefault("also_asks", [])
					story.setdefault("screens", [])
					story.update(self._artifact(identifier, story["id"]))
				highlight = plan.get("highlight")
				if highlight is not None:
					highlight.update(self._artifact(identifier, "highlight"))
					selected = set(highlight.get("stories", []))
					highlight["estimate_usd"] = 0.0 if highlight["video"] else round(sum(
						s["estimate_usd"] for s in plan["stories"] if s["id"] in selected), 8)
			return {"unit_id": identifier, "title": meta["title"], "planned": plan is not None,
				"spent_usd": self._spent_usd(identifier), "plan": plan,
				"jobs": [j["job_id"] for j in self._unit_jobs(identifier)]}

	def list_units(self):
		with self.lock:
			units = []
			for identifier in self.library.unit_ids():
				detail = self.get_unit(identifier)
				meta = self.library.meta(identifier)
				plan = detail["plan"] or {}
				artifacts = [*plan.get("stories", []), plan.get("highlight") or {}]
				units.append({key: detail[key] for key in ("unit_id", "title", "planned", "spent_usd")})
				units[-1].update(created_at=meta["created_at"], videos=sum(bool(s.get("video")) for s in artifacts))
			return sorted(units, key=lambda unit: unit["created_at"], reverse=True)

	def ask(self, payload):
		question = payload.get("question")
		if not isinstance(question, str) or not question.strip():
			raise APIError(400, "請輸入學生問題")
		identifier = payload.get("unit_id")
		detail = self.get_unit(identifier)
		plan = detail["plan"]
		if plan is None:
			raise APIError(409, "請先規劃教材")
		highlight = plan.get("highlight") or {}
		score = match_score(question, highlight)
		if highlight and (score >= 0.18 or any(word in question for word in ("重點", "整個單元", "整個單位", "全單元"))):
			return {"kind": "highlight", "story": None, "score": score,
				"reason": "這個問題適合觀看單元重點片", "video": highlight["video"]}
		best = max(plan["stories"], key=lambda story: match_score(question, story))
		score = match_score(question, best)
		if score >= 0.18:
			return {"kind": "story", "story": best["id"], "score": score,
				"reason": "問題對應這段問題故事", "video": best["video"]}
		scope_score = max((jaccard(question, text) for text in plan.get("scope", {}).get("not_covers", [])), default=0.0)
		material = self._unit_path(identifier, "material.md").read_text(encoding="utf-8")
		for language in LANGUAGES:
			pattern = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(language) + r"(?![A-Za-z0-9_])", re.I)
			if pattern.search(question) and not pattern.search(material):
				return {"kind": "out_of_scope", "story": None, "score": scope_score,
					"reason": "這份教材沒有教這個", "video": None}
		if scope_score >= 0.15:
			return {"kind": "out_of_scope", "story": None, "score": scope_score,
				"reason": "這份教材沒有教這個", "video": None}
		return {"kind": "no_match", "story": None, "score": score,
			"reason": "素材庫尚未找到對應的問題故事", "video": None}

	def get_job(self, identifier):
		try:
			return self.job_queue.get(identifier)
		except KeyError:
			raise APIError(404, "找不到工作")

	def _active_job(self, identifier, item):
		return next((job["job_id"] for job in self._unit_jobs(identifier)
			if job["item"] == item and job["state"] in ("queued", "running")), None)

	def _check_queue(self):
		if self.job_queue.stopping.is_set():
			raise APIError(503, "伺服器正在停止")

	def enqueue_plan(self, identifier):
		with self.lock:
			if self._unit_path(identifier, "plan.json").is_file():
				return {"job_id": None, "planned": True}
			self._check_queue()
			jid = self._active_job(identifier, "analysis")
			if jid is None:
				view = formats.UnitView(identifier, self._unit_dir(identifier), None, self.tts_mode)
				jid = self.job_queue.enqueue_stage(identifier, "analysis", formats.stages.analysis_commands(view))
			return {"job_id": jid}

	def enqueue_videos(self, identifier, payload):
		with self.lock:
			self._unit_dir(identifier)
			plan = self._plan(identifier)
			if set(payload) == {"highlight"} and payload["highlight"] is True:
				stories = plan.get("highlight", {}).get("stories", [])
				known = {story["id"] for story in plan["stories"]}
				if not stories or any(story not in known for story in stories):
					raise APIError(409, "教材規劃沒有可生成的重點片")
				items = ["highlight"]
			elif set(payload) == {"stories"} and isinstance(payload["stories"], list) and payload["stories"]:
				known = {story["id"] for story in plan["stories"]}
				if any(not isinstance(story, str) or story not in known for story in payload["stories"]):
					raise APIError(400, "請選擇教材規劃中的段落")
				items = list(dict.fromkeys(payload["stories"]))
			else:
				raise APIError(400, "請提供段落清單或重點片選項")
			items = [item for item in items if not self._video_ready(identifier, item)]
			if not items:
				return {"job_id": None}
			self._check_queue()
			jids = [self._active_job(identifier, item) or self.job_queue.enqueue(identifier, item) for item in items]
			return {"job_id": jids[0], "job_ids": jids}


class StudioHTTPServer(ThreadingHTTPServer):
	def __init__(self, address, studio, studio_dir=STUDIO_DIR):
		self.studio = studio
		self.studio_dir = Path(studio_dir).resolve()
		super().__init__(address, StudioHandler)


class StudioHandler(BaseHTTPRequestHandler):
	def log_message(self, format, *args):
		pass

	def _json(self, status, value, headers=None):
		body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Content-Length", str(len(body)))
		self.send_header("Cache-Control", "no-store")
		for name, value in (headers or {}).items():
			self.send_header(name, value)
		self.end_headers()
		if self.command != "HEAD":
			self.wfile.write(body)

	def send_error(self, code, message=None, explain=None):
		self._json(code, {"error": "請求格式不正確" if code == 400 else "不支援此請求"})

	def _body(self):
		try:
			length = int(self.headers.get("Content-Length", "0"))
		except ValueError:
			raise APIError(400, "請求長度不正確")
		if length < 0 or length > MAX_BODY:
			self.close_connection = True
			raise APIError(413, "教材內容超過大小限制")
		try:
			payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
		except (ValueError, UnicodeError, RecursionError):
			raise APIError(400, "請提供正確的 JSON 內容")
		if not isinstance(payload, dict):
			raise APIError(400, "JSON 內容必須是物件")
		return payload

	def _file(self, path):
		if not path.is_file():
			raise APIError(404, "找不到檔案")
		with path.open("rb") as handle:
			size = os.fstat(handle.fileno()).st_size
			start, end, status = 0, size - 1, 200
			requested = self.headers.get("Range")
			if requested:
				match = re.fullmatch(r"bytes=(\d*)-(\d*)", requested.strip())
				if not match or not any(match.groups()) or not size:
					return self._json(416, {"error": "影片範圍不正確"}, {"Content-Range": f"bytes */{size}"})
				first, last = match.groups()
				if first:
					start, end = int(first), min(int(last), size - 1) if last else size - 1
				else:
					start = max(0, size - int(last))
				if start > end or start >= size:
					return self._json(416, {"error": "影片範圍不正確"}, {"Content-Range": f"bytes */{size}"})
				status = 206
			mime = {".mp4": "video/mp4", ".json": "application/json", ".js": "text/javascript"}.get(path.suffix.lower())
			mime = mime or mimetypes.guess_type(str(path))[0] or "application/octet-stream"
			if mime.startswith("text/") or mime == "application/json":
				mime += "; charset=utf-8"
			self.send_response(status)
			self.send_header("Content-Type", mime)
			self.send_header("Content-Length", str(max(0, end - start + 1)))
			self.send_header("Accept-Ranges", "bytes")
			self.send_header("X-Content-Type-Options", "nosniff")
			if status == 206:
				self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
			self.end_headers()
			if self.command == "HEAD":
				return
			handle.seek(start)
			remaining = end - start + 1
			while remaining > 0:
				data = handle.read(min(64 * 1024, remaining))
				if not data:
					break
				self.wfile.write(data)
				remaining -= len(data)

	def _static_path(self, relative):
		try:
			return safe_path(self.server.studio_dir, relative)
		except ValueError:
			raise APIError(404, "找不到檔案")

	def _dispatch(self):
		path = unquote(urlsplit(self.path).path)
		studio = self.server.studio
		if self.command in ("GET", "HEAD"):
			if path == "/":
				# 導到 /studio/：頁面裡的 app.js、styles.css、mock/ 都是相對路徑
				query = urlsplit(self.path).query
				self.send_response(302)
				self.send_header("Location", "/studio/index.html" + (f"?{query}" if query else ""))
				self.send_header("Content-Length", "0")
				self.end_headers()
				return
			if path.startswith("/studio/"):
				return self._file(self._static_path(path[len("/studio/"):]))
			if path.startswith("/media/"):
				parts = path.split("/", 3)
				if len(parts) != 4:
					raise APIError(404, "找不到檔案")
				return self._file(studio._unit_path(parts[2], parts[3]))
			if path == "/api/pipelines":
				pipelines = read_json(self._static_path("pipelines.json"))
				if pipelines is None:
					raise APIError(404, "找不到流程說明")
				return self._json(200, pipelines)
			if path == "/api/units":
				return self._json(200, studio.list_units())
			if re.fullmatch(r"/api/units/[^/]+", path):
				return self._json(200, studio.get_unit(path.rsplit("/", 1)[1]))
			if re.fullmatch(r"/api/jobs/[^/]+", path):
				return self._json(200, studio.get_job(path.rsplit("/", 1)[1]))
		elif self.command == "POST":
			payload = self._body()
			if path == "/api/units":
				return self._json(200, studio.create_unit(payload))
			if path == "/api/ask":
				return self._json(200, studio.ask(payload))
			match = re.fullmatch(r"/api/units/([^/]+)/(plan|videos)", path)
			if match:
				identifier, action = match.groups()
				result = studio.enqueue_plan(identifier) if action == "plan" else studio.enqueue_videos(identifier, payload)
				return self._json(200, result)
		raise APIError(404, "找不到此入口")

	def _handle(self):
		try:
			self._dispatch()
		except APIError as exc:
			self._json(exc.status, {"error": str(exc)})
		except (BrokenPipeError, ConnectionResetError):
			pass
		except (OSError, ValueError, TypeError, KeyError, AttributeError):
			self._json(500, {"error": "無法讀取工作室資料，請檢查檔案與本機環境"})

	do_GET = _handle
	do_POST = _handle
	do_HEAD = _handle


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--port", type=int, default=8765)
	parser.add_argument("--out", default=str(ROOT / "video_engine/out/units"))
	args = parser.parse_args()
	studio = Studio(args.out)
	try:
		server = StudioHTTPServer(("127.0.0.1", args.port), studio)
		try:
			print(f"影片工作室：http://127.0.0.1:{args.port}（素材庫：{studio.out}）", flush=True)
			if not studio.tts_available:
				print("配音伺服器沒開（:9880）", flush=True)
			server.serve_forever()
		except KeyboardInterrupt:
			pass
		finally:
			server.server_close()
	finally:
		studio.close()


if __name__ == "__main__":
	main()
