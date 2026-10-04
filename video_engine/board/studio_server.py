#!/usr/bin/env python3
"""獨立影片工作室：教材素材庫、學生提問與單一 CLI 工作佇列。

用法：.venv/bin/python video_engine/board/studio_server.py [--port 8765] [--out video_engine/out/units]
"""
import argparse
import copy
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit
import uuid

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STUDIO_DIR = HERE / "studio"
PROJECT_PY = ROOT / ".venv/bin/python"
PLAYWRIGHT_PY = Path("~/.local/share/pipx/venvs/webwright/bin/python").expanduser()
MODEL = "google:gemini-3.8-flash"
# 每段預估：分鏡約 US$0.035＋Gemini 配音約 US$0.02（60–75 秒）
ESTIMATE_USD = 0.055
# 配音：gemini（預設，英文照原文唸）或 sovits（本機王老師，免費，需要 :9880）
TTS_MODE = os.environ.get("BOARD_TTS", "gemini")
MAX_BODY = 4 * 1024 * 1024
UNIT_ID = re.compile(r"[a-f0-9]{12}")
STORY_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}")
JOB_ID = re.compile(r"[a-f0-9]{32}")
LANGUAGES = ("Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Ruby", "Go",
	"Rust", "Kotlin", "Swift", "PHP", "SQL", "Dart", "Scala", "Lua", "Perl", "R")


class APIError(Exception):
	def __init__(self, status, message):
		super().__init__(message)
		self.status = status


def unit_id(markdown):
	return hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:12]


def read_json(path, default=None):
	try:
		with path.open(encoding="utf-8") as handle:
			return json.load(handle)
	except FileNotFoundError:
		return default


def write_json(path, value):
	path.parent.mkdir(parents=True, exist_ok=True)
	temporary = path.with_suffix(".tmp")
	with temporary.open("w", encoding="utf-8") as handle:
		json.dump(value, handle, ensure_ascii=False, indent="\t", allow_nan=False)
	os.replace(temporary, path)


def safe_path(root, relative):
	root = root.resolve()
	path = (root / relative).resolve()
	try:
		path.relative_to(root)
	except ValueError:
		raise APIError(404, "找不到檔案")
	return path


def spent_usd(directory):
	"""規劃＋分鏡（usage.jsonl）加上各段 Gemini 配音（*/voice/tts_usage.jsonl）。"""
	return round(_sum_usd(directory / "usage.jsonl") + sum(_sum_usd(p) for p in Path(directory).glob("**/tts_usage.jsonl")), 6)


def _sum_usd(path):
	total = 0.0
	try:
		with Path(path).open(encoding="utf-8") as handle:
			for line in handle:
				try:
					value = json.loads(line).get("usd")
					if type(value) in (int, float) and math.isfinite(value):
						total += value
				except (ValueError, AttributeError):
					# 子行程可能正寫到最後一行，下一次輪詢再讀。
					continue
	except FileNotFoundError:
		pass
	return round(total, 8)


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


def run_command(command, log):
	environment = dict(os.environ, PYTHONUNBUFFERED="1")
	with subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1) as process:
		for line in process.stdout:
			log(line.rstrip("\r\n"))
		return process.wait()


class Studio:
	def __init__(self, out, command_runner=None, tts_checker=None, tts_mode=None):
		self.tts_mode = tts_mode or TTS_MODE
		self.out = Path(out).resolve()
		self.out.mkdir(parents=True, exist_ok=True)
		self.command_runner = command_runner or run_command
		self.tts_checker = tts_checker or tts_health
		self.lock = threading.RLock()
		self.jobs = {}
		self.pending = queue.Queue()
		self.stopping = threading.Event()
		self._restore_jobs()
		self.tts_available = self._tts_ready()
		self.worker = threading.Thread(target=self._work, name="影片工作佇列", daemon=True)
		self.worker.start()

	def close(self):
		self.stopping.set()
		self.pending.put(None)
		self.worker.join(timeout=3)

	def _tts_ready(self):
		if self.tts_mode != "sovits":
			return True
		try:
			return bool(self.tts_checker())
		except OSError:
			return False

	def _unit_dir(self, identifier):
		if not isinstance(identifier, str) or not UNIT_ID.fullmatch(identifier):
			raise APIError(404, "找不到教材")
		directory = safe_path(self.out, identifier)
		if not directory.is_dir() or not (directory / "meta.json").is_file():
			raise APIError(404, "找不到教材")
		return directory

	def _plan(self, directory):
		plan = read_json(directory / "plan.json")
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
		identifier = unit_id(markdown)
		with self.lock:
			directory = safe_path(self.out, identifier)
			if (directory / "meta.json").is_file():
				return {"unit_id": identifier, "created": False}
			if not title or not title.strip():
				title = next((line.lstrip("# ").strip() for line in markdown.splitlines() if line.strip()), "未命名教材")
			directory.mkdir(parents=True, exist_ok=True)
			(directory / "material.md").write_text(markdown, encoding="utf-8")
			write_json(directory / "meta.json", {"title": title.strip()[:200],
				"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
			return {"unit_id": identifier, "created": True}

	def _unit_jobs(self, identifier):
		return [job for job in self.jobs.values() if job["unit_id"] == identifier]

	def _targets(self, job, story):
		return job["kind"] == "highlight" if story == "highlight" else (
			job["kind"] == "stories" and story in job.get("stories", []))

	def _video_ready(self, identifier, directory, story):
		video = safe_path(directory, f"{story}/video.mp4")
		if not video.is_file() or video.stat().st_size == 0:
			return False
		for job in reversed(self._unit_jobs(identifier)):
			if not self._targets(job, story):
				continue
			if story in job.get("completed", []) or job["state"] == "done":
				return True
			if job["state"] == "failed" and job.get("target", story) == story:
				return False
			if job["state"] == "running" and job.get("target") == story:
				return False
		return True

	def _artifact(self, identifier, directory, story):
		jobs = [j for j in self._unit_jobs(identifier) if self._targets(j, story)]
		active = next((j for j in jobs if j["state"] == "running"), None)
		active = active or next((j for j in jobs if j["state"] == "queued"), None)
		ready = self._video_ready(identifier, directory, story)
		status = "done" if ready else active["state"] if active else "failed" if jobs and jobs[-1]["state"] == "failed" else "none"
		if active and not ready and active["kind"] == "stories" and active.get("target") != story:
			status = "queued"
		if active and story == active.get("target") and story not in active.get("completed", []):
			status, ready = "running", False
		duration = None
		if ready:
			report = read_json(safe_path(directory, f"{story}/video.export.json"), {})
			timeline = read_json(safe_path(directory, f"{story}/timeline.json"), {})
			duration = report.get("duration", timeline.get("duration"))
		costs = [j["costs"][story] for j in self._unit_jobs(identifier) if story in j.get("costs", {})]
		return {"status": status, "video": f"/media/{identifier}/{story}/video.mp4" if ready else None,
			"duration": duration, "cost_usd": round(sum(costs), 8) if costs else None,
			"estimate_usd": 0.0 if ready or safe_path(directory, f"{story}.scene.json").is_file() else ESTIMATE_USD}

	def get_unit(self, identifier):
		with self.lock:
			directory = self._unit_dir(identifier)
			meta = read_json(directory / "meta.json")
			plan = read_json(directory / "plan.json")
			if plan is not None:
				plan = self._plan(directory)
				for story in plan["stories"]:
					story.setdefault("also_asks", [])
					story.setdefault("screens", [])
					story.update(self._artifact(identifier, directory, story["id"]))
				highlight = plan.get("highlight")
				if highlight is not None:
					highlight.update(self._artifact(identifier, directory, "highlight"))
					selected = set(highlight.get("stories", []))
					highlight["estimate_usd"] = 0.0 if highlight["video"] else round(sum(
						s["estimate_usd"] for s in plan["stories"] if s["id"] in selected), 8)
			return {"unit_id": identifier, "title": meta["title"], "planned": plan is not None,
				"spent_usd": spent_usd(directory), "plan": plan,
				"jobs": [j["job_id"] for j in self._unit_jobs(identifier)]}

	def list_units(self):
		with self.lock:
			units = []
			for entry in sorted(self.out.iterdir()):
				if not UNIT_ID.fullmatch(entry.name) or not (entry / "meta.json").is_file():
					continue
				detail = self.get_unit(entry.name)
				meta = read_json(entry / "meta.json")
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
		material = (self._unit_dir(identifier) / "material.md").read_text(encoding="utf-8")
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

	def _save_job(self, job):
		job["spent_usd"] = spent_usd(self._unit_dir(job["unit_id"]))
		path = safe_path(self.out, f"{job['unit_id']}/jobs/{job['job_id']}.json")
		write_json(path, job)

	def _restore_jobs(self):
		paths = sorted(self.out.glob("*/jobs/*.json"))
		for path in paths:
			identifier = path.parent.parent.name
			if not UNIT_ID.fullmatch(identifier) or not JOB_ID.fullmatch(path.stem):
				continue
			try:
				self._unit_dir(identifier)
				path = safe_path(self.out, str(path.relative_to(self.out)))
				job = read_json(path)
			except (APIError, OSError, ValueError, RecursionError):
				continue
			if (not isinstance(job, dict) or job.get("unit_id") != identifier or job.get("job_id") != path.stem
				or job.get("kind") not in ("plan", "stories", "highlight")
				or job.get("state") not in ("queued", "running", "done", "failed")):
				continue
			self.jobs[job["job_id"]] = job
		self.jobs = dict(sorted(self.jobs.items(), key=lambda item: item[1].get("created_at", "")))
		for job in self.jobs.values():
			if job["state"] not in ("done", "failed"):
				job.update(state="failed", error="伺服器重啟，未完成的工作已停止")
				job["log"] = [*job.get("log", []), job["error"]][-40:]
				self._save_job(job)

	def get_job(self, identifier):
		with self.lock:
			job = self.jobs.get(identifier)
			if job is None:
				raise APIError(404, "找不到工作")
			result = copy.deepcopy(job)
			result["spent_usd"] = spent_usd(self._unit_dir(job["unit_id"]))
			result["log"] = result.get("log", [])[-40:]
			return result

	def enqueue_plan(self, identifier):
		with self.lock:
			directory = self._unit_dir(identifier)
			if (directory / "plan.json").is_file():
				return {"job_id": None, "planned": True}
			return self._enqueue(identifier, "plan", [])

	def enqueue_videos(self, identifier, payload):
		with self.lock:
			directory = self._unit_dir(identifier)
			plan = self._plan(directory)
			if set(payload) == {"highlight"} and payload["highlight"] is True:
				kind = "highlight"
				stories = plan.get("highlight", {}).get("stories", [])
				known = {s["id"] for s in plan["stories"]}
				if not stories or any(s not in known for s in stories):
					raise APIError(409, "教材規劃沒有可生成的重點片")
				if self._video_ready(identifier, directory, "highlight"):
					return {"job_id": None}
			elif set(payload) == {"stories"} and isinstance(payload["stories"], list) and payload["stories"]:
				kind = "stories"
				known = {s["id"] for s in plan["stories"]}
				if any(not isinstance(s, str) or s not in known for s in payload["stories"]):
					raise APIError(400, "請選擇教材規劃中的段落")
				stories = [s for s in dict.fromkeys(payload["stories"]) if not self._video_ready(identifier, directory, s)]
				if not stories:
					return {"job_id": None}
			else:
				raise APIError(400, "請提供段落清單或重點片選項")
			return self._enqueue(identifier, kind, stories)

	def _enqueue(self, identifier, kind, stories):
		if self.stopping.is_set():
			raise APIError(503, "伺服器正在停止")
		for job in self._unit_jobs(identifier):
			if job["kind"] == kind and job.get("stories", []) == stories and job["state"] in ("queued", "running"):
				return {"job_id": job["job_id"]}
		job_id = uuid.uuid4().hex
		job = {"job_id": job_id, "unit_id": identifier, "kind": kind, "state": "queued", "stage": "等待",
			"log": [], "spent_usd": 0.0, "error": None, "stories": list(stories), "completed": [], "costs": {},
			"created_at": datetime.now(timezone.utc).isoformat()}
		self._save_job(job)
		self.jobs[job_id] = job
		self.pending.put(job_id)
		return {"job_id": job_id}

	def _update(self, job, **changes):
		with self.lock:
			job.update(changes)
			self._save_job(job)

	def _log(self, job, line):
		with self.lock:
			job["log"] = [*job["log"], line][-40:]
			self._save_job(job)

	def _step(self, job, stage, cli, args):
		self._update(job, stage=stage)
		python = PLAYWRIGHT_PY if cli in ("check", "export") else PROJECT_PY
		command = [str(python), str(HERE / (cli + ".py")), *map(str, args)]
		code = self.command_runner(command, lambda line: self._log(job, line))
		if code != 0:
			raise RuntimeError(f"{stage}失敗（結束碼 {code}），請查看工作紀錄")

	def _author(self, job, directory, story=None):
		stage = "scene" if story else "plan"
		args = [stage, directory / "material.md", directory]
		if story:
			args.append(story)
		else:
			# author 目前只在分鏡內建自檢，規劃也先過免費閘。
			self._step(job, "本機自我檢查", "selftest", ["--quick"])
		args.extend(["--model", MODEL, "--budget-usd", "0.50"])
		before = spent_usd(directory)
		try:
			self._step(job, f"分鏡 {story}" if story else "規劃", "author", args)
		finally:
			if story:
				with self.lock:
					job["costs"][story] = round(job["costs"].get(story, 0) + spent_usd(directory) - before, 8)
					self._save_job(job)
		path = directory / (f"{story}.scene.json" if story else "plan.json")
		if not path.is_file():
			raise RuntimeError("生成程序沒有產生預期的規劃或分鏡檔案")

	def _scene(self, job, directory, story):
		path = safe_path(directory, f"{story}.scene.json")
		if not path.is_file():
			self._author(job, directory, story)
		return path

	def _render(self, job, directory, story, scene):
		self._update(job, target=story, stage=f"配音 {story}")
		self.tts_available = self._tts_ready()
		if not self.tts_available:
			raise RuntimeError("配音伺服器沒開（:9880）")
		output = safe_path(directory, story)
		output.mkdir(parents=True, exist_ok=True)
		voice, player = output / "voice", output / "player"
		timeline = output / "timeline.json"
		self._step(job, f"配音 {story}", "narrate", [scene, voice, "--tts", self.tts_mode])
		self._step(job, f"編譯 {story}", "compile", [scene, timeline, "--timing", voice / "timing.json", "--gaps", output / "gaps.jsonl"])
		self._step(job, f"播放器 {story}", "build", [timeline, player, "--audio", voice / "master.wav"])
		self._step(job, f"驗證 {story}", "check", [player])
		self._step(job, f"出片 {story}", "export", [player, output / "video.mp4"])
		if not (output / "video.mp4").is_file() or (output / "video.mp4").stat().st_size == 0:
			raise RuntimeError("出片程序沒有產生影片")
		self._update(job, completed=[*job["completed"], story])

	def _execute(self, job):
		directory = self._unit_dir(job["unit_id"])
		if job["kind"] == "plan":
			if not (directory / "plan.json").is_file():
				self._author(job, directory)
			self._plan(directory)
		elif job["kind"] == "stories":
			for story in job["stories"]:
				if self._video_ready(job["unit_id"], directory, story):
					self._update(job, completed=[*job["completed"], story])
					continue
				self._update(job, target=story)
				self._render(job, directory, story, self._scene(job, directory, story))
		else:
			if self._video_ready(job["unit_id"], directory, "highlight"):
				self._update(job, completed=["highlight"])
				return
			for story in job["stories"]:
				self._scene(job, directory, story)
			scene = safe_path(directory, "highlight.scene.json")
			self._step(job, "串接重點片", "compose", [directory / "plan.json", directory, scene])
			self._render(job, directory, "highlight", scene)

	def _work(self):
		while not self.stopping.is_set():
			identifier = self.pending.get()
			try:
				if identifier is None or self.stopping.is_set():
					return
				job = self.jobs[identifier]
				self._update(job, state="running")
				try:
					self._execute(job)
				except Exception as exc:
					message = str(exc) if isinstance(exc, RuntimeError) else "工作執行失敗，請檢查檔案與本機執行環境"
					self._log(job, message)
					self._update(job, state="failed", error=message)
				else:
					self._update(job, state="done", stage="完成")
			finally:
				self.pending.task_done()


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
				return self._file(safe_path(self.server.studio_dir, path[len("/studio/"):]))
			if path.startswith("/media/"):
				parts = path.split("/", 3)
				if len(parts) != 4:
					raise APIError(404, "找不到檔案")
				return self._file(safe_path(studio._unit_dir(parts[2]), parts[3]))
			if path == "/api/pipelines":
				pipelines = read_json(safe_path(self.server.studio_dir, "pipelines.json"))
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
