#!/usr/bin/env python3
"""多元教材工作台：版本化 API、素材庫與單一 CLI 工作佇列。

用法：.venv/bin/python -m workbench.server [--port 8765] [--out video_engine/out/units]
"""
import argparse
from datetime import date
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import math
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from . import formats, uploads, usage
from .jobs import JobQueue, PLAYWRIGHT_PY, PROJECT_PY, run_command
from .library import Library, read_json, safe_path

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = Path(__file__).resolve().parent / "web"
# 配音：gemini（預設，英文照原文唸）或 sovits（本機王老師，免費，需要 :9880）
TTS_MODE = os.environ.get("BOARD_TTS", "gemini")
MAX_BODY = 4 * 1024 * 1024
STORY_ID = re.compile(r"[a-z][a-z0-9_-]{0,31}")
LANGUAGES = ("Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "C", "Ruby", "Go",
	"Rust", "Kotlin", "Swift", "PHP", "SQL", "Dart", "Scala", "Lua", "Perl", "R")


class APIError(Exception):
	def __init__(self, status, message, advice="請檢查輸入後再試", code=None):
		super().__init__(message)
		self.status = status
		self.code = code or {400: "bad_request", 404: "not_found", 409: "conflict", 413: "too_large"}.get(status, "unknown")
		self.advice = advice

	def payload(self):
		return {"error": {"code": self.code, "reason": str(self), "advice": self.advice}}


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
		self.uploads = uploads.Uploads(self.out.parent / "uploads")
		self.command_runner = command_runner or run_command
		self.tts_checker = tts_checker or tts_health
		self.tts_available = self._tts_ready()
		self.job_queue = JobQueue(self.library, self._run_command, formats, tts_mode=self.tts_mode, on_success=self._job_done)
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
		return usage.unit_spent(self._unit_dir(identifier))

	def _plan(self, identifier):
		self._unit_path(identifier, "plan.json")
		plan = self.library.plan(identifier)
		if plan is None:
			raise APIError(409, "請先分析教材")
		source = read_json(self._unit_path(identifier, "plan.source.json"))
		if source is not None:
			from workbench.material import validate_provenance
			try:
				validate_provenance(source, self.library.material(identifier))
			except (ValueError, OSError, TypeError) as exc:
				raise APIError(409, "分析結果與教材來源版本不一致", code="material_version") from exc
		stories = plan.get("stories", [])
		ids = [s.get("id") for s in stories]
		reserved = {fmt["id"] for fmt in formats.public()["formats"]} | {"analysis", "ingest"}
		if (not ids or any(not isinstance(s, str) or not STORY_ID.fullmatch(s) or s in reserved for s in ids)
			or len(set(ids)) != len(ids)):
			raise APIError(500, "教材規劃的段落代號不正確")
		return plan

	def create_unit(self, payload):
		markdown, title, source_ref = payload.get("markdown"), payload.get("title"), payload.get("source_ref")
		source_kind = payload.get("source_kind", "md")
		if source_kind not in ("md", "txt"):
			raise APIError(400, "文字來源類型必須是 MD 或 TXT")
		if not isinstance(markdown, str) or not markdown.strip():
			raise APIError(400, "請提供教材 Markdown 內容")
		if title is not None and not isinstance(title, str):
			raise APIError(400, "教材標題必須是文字")
		if source_ref is not None and not isinstance(source_ref, dict):
			raise APIError(400, "來源參照必須是物件")
		with self.lock:
			try:
				identifier, created = self.library.create_unit(markdown, title, source_ref, source_kind)
			except ValueError:
				raise APIError(404, "找不到檔案")
			return {"unit_id": identifier, "created": created}

	def _unit_jobs(self, identifier):
		return [self.job_queue.get(jid) for jid, job in self.job_queue.jobs.items() if job["unit_id"] == identifier]

	def _targets(self, job, item):
		if "kind" in job:
			return job["kind"] == "highlight" if item == "highlight" else (
				job["kind"] == "stories" and item in job.get("stories", []))
		return job["item"] == item

	def _item(self, view, item, rows):
		module = formats.get_format(formats.item_format(view.plan, item))
		jobs = [job for job in self._unit_jobs(view.id) if self._targets(job, item)]
		latest = jobs[-1] if jobs else None
		active = next((job for job in reversed(jobs) if job["state"] in ("queued", "running")), None)
		# 舊批次可能在別點失敗，已完成或沿用的影片仍可讀取。
		status_job = next((job for job in reversed(jobs) if "kind" not in job or job["state"] == "done"
			or item in job.get("completed", []) or job.get("target", item) == item), None)
		done = module.is_done(view, item)
		status = "done" if done else "none"
		if status_job and status_job["state"] == "failed":
			status = "failed"
			if "kind" in status_job and item in status_job.get("completed", []):
				status = "done" if done else "none"
		if active:
			status = active["state"]
		files = module.outputs(view, item) if status == "done" else {}
		for relative in files.values():
			self._unit_path(view.id, relative)
		timeline = read_json(self._unit_path(view.id, f"{item}/timeline.json"), {}) if status == "done" else {}
		duration = timeline.get("duration", timeline.get("total"))
		if type(duration) not in (int, float) or not math.isfinite(duration):
			duration = None
		source_path = f"{item}/source.json" if module.FORMAT["id"] in ("slides", "mindmap") else f"{item}.scene.source.json"
		product_source = read_json(self._unit_path(view.id, source_path)) if status == "done" else None
		costs = [row["usd"] for row in rows if row["item"] == item]
		return {"item": item, "format": module.FORMAT["id"], "label": usage.item_label(item, view.plan),
			"status": status, "estimate_usd": 0.0 if status == "done" else module.estimate_usd(view, item),
			"cost_usd": round(sum(costs), 8) if costs and not any(row.get("cost_unknown") for row in rows if row["item"] == item) else None, "duration": duration, "files": files,
			"source_version": product_source.get("content_version") if isinstance(product_source, dict) else None,
			"source_ids": product_source.get("source_ids", []) if isinstance(product_source, dict) else [],
			"job_id": latest["job_id"] if latest else None, "warnings": latest["warnings"] if latest else []}

	def _analysis(self, plan):
		if plan is None:
			return None
		point_keys = ("id", "question", "also_asks", "title", "sec", "objectives", "screens", "show")
		points = []
		for story in plan["stories"]:
			point = {key: story.get(key, [] if key in ("also_asks", "objectives", "screens") else "") for key in point_keys}
			points.append(point)
		highlight = plan.get("highlight") or {}
		return {"unit_title": plan.get("unit_title", ""),
			"scope": {key: plan.get("scope", {}).get(key, []) for key in ("covers", "not_covers")},
			"points": points, "glossary": plan.get("glossary", []),
			"highlight": {"points": highlight.get("stories", []), "total_sec": highlight.get("total_sec", 0), "why": highlight.get("why", "")}}

	def get_unit(self, identifier):
		with self.lock:
			self._unit_dir(identifier)
			meta = self.library.meta(identifier)
			self._unit_path(identifier, "plan.json")
			plan = self.library.plan(identifier)
			if plan is not None:
				plan = self._plan(identifier)
			view = formats.UnitView(identifier, self._unit_dir(identifier), plan, self.tts_mode)
			rows = usage.read_unit(view.dir)
			items = [story["id"] for story in plan["stories"]] + ["highlight", "mindmap", "slides"] if plan else []
			return {"unit_id": identifier, "title": meta["title"],
				"normalization_attention": self._normalization_attention(identifier),
				"unknown_calls": sum(bool(row.get("cost_unknown")) for row in rows),
				"source_ref": meta.get("source_ref") if isinstance(meta.get("source_ref"), dict) else None,
				"spent_usd": self._spent_usd(identifier), "analysis": self._analysis(plan),
				"items": [self._item(view, item, rows) for item in items]}

	def list_units(self):
		with self.lock:
			units = []
			for uid in self.library.unit_ids():
				detail = self.get_unit(uid)
				products = {"video": 0, "highlight": False, "mindmap": False, "slides": False}
				for item in detail["items"]:
					if item["status"] == "done":
						if item["format"] == "video":
							products["video"] += 1
						else:
							products[item["format"]] = True
				units.append({key: detail[key] for key in ("unit_id", "title", "spent_usd", "source_ref", "unknown_calls")})
				units[-1].update(created_at=self.library.meta(uid)["created_at"], analyzed=detail["analysis"] is not None,
					points=len(detail["analysis"]["points"]) if detail["analysis"] else 0, products=products)
			return units

	def ask(self, payload):
		question = payload.get("question")
		if not isinstance(question, str) or not question.strip():
			raise APIError(400, "請輸入學生問題")
		identifier = payload.get("unit_id")
		detail = self.get_unit(identifier)
		plan = self._plan(identifier)
		items = {item["item"]: item for item in detail["items"]}
		def video(item):
			path = items[item]["files"].get("video")
			return f"/media/{identifier}/{path}" if path else None
		highlight = plan.get("highlight") or {}
		score = match_score(question, highlight)
		if highlight and (score >= 0.18 or any(word in question for word in ("重點", "整個單元", "整個單位", "全單元"))):
			return {"kind": "highlight", "story": None, "score": score,
				"reason": "這個問題適合觀看單元重點片", "video": video("highlight")}
		best = max(plan["stories"], key=lambda story: match_score(question, story))
		score = match_score(question, best)
		if score >= 0.18:
			return {"kind": "story", "story": best["id"], "score": score,
				"reason": "問題對應這段問題故事", "video": video(best["id"])}
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
			raise APIError(409, "工作佇列已停止")

	def review_material(self, identifier, payload):
		from workbench.material import confirm_review
		if payload.get("confirmed") is not True:
			raise APIError(400, "請先對照原檔確認內容")
		with self.lock:
			self._unit_dir(identifier)
			try:
				data = confirm_review(self.library, identifier, payload.get("content_version"))
			except (ValueError, OSError, TypeError) as exc:
				raise APIError(409, "教材版本已改變，請重新核對", code="material_version") from exc
			return {"unit_id": identifier, "content_version": data["content_version"], "reviewed": True}

	def get_material(self, identifier):
		self._unit_dir(identifier)
		return {**self.library.material(identifier),
			"markdown": self._unit_path(identifier, "material.md").read_bytes().decode("utf-8")}

	def _normalization_attention(self, identifier):
		from workbench.material import review_confirmed
		try:
			data = self.library.material(identifier)
			if review_confirmed(data):
				return None
			if data.get("review", {}).get("reviewed_content_version"):
				return "教材來源已變更，請重新核對。"
		except (ValueError, OSError, TypeError):
			pass
		review = read_json(self._unit_path(identifier, "normalization.json"))
		if isinstance(review, dict) and review.get("requires_review"):
			return review.get("attention") or "整理內容有待核對項目，請先對照原稿。"
		# 舊單元可能只有 Markdown，仍須保留既有疑點的阻擋效果。
		if "\n待核對：\n" in self._unit_path(identifier, "material.md").read_text(encoding="utf-8"):
			return "整理內容有待核對項目，請先對照原稿。"
		return None

	def _check_material(self, identifier):
		attention = self._normalization_attention(identifier)
		if attention:
			raise APIError(409, attention, "請核對原始教材，將修正後內容以「貼上文字」建立新教材。", code="normalization_review")
		try:
			material = self.library.material(identifier)
		except (ValueError, OSError, TypeError) as exc:
			raise APIError(409, "教材來源或版本不一致", "請重新加入原始教材。", code="material_version") from exc
		if material.get("review", {}).get("required"):
			raise APIError(409, "教材內容需要核對", "請對照原檔修正後建立新教材。", code="normalization_review")

	def enqueue_analyze(self, identifier):
		with self.lock:
			self._unit_dir(identifier)
			self._check_material(identifier)
			if self._active_job(identifier, "analysis"):
				raise APIError(409, "這份教材正在分析")
			if self._unit_path(identifier, "plan.json").is_file():
				return {"job_id": None, "analyzed": True}
			self._check_queue()
			view = formats.UnitView(identifier, self._unit_dir(identifier), None, self.tts_mode)
			return {"job_id": self.job_queue.enqueue_stage(identifier, "analysis", formats.stages.analysis_commands(view))}

	def enqueue_generate(self, identifier, payload):
		with self.lock:
			self._check_material(identifier)
			plan = self._plan(identifier)
			requested = payload.get("items")
			if not isinstance(requested, list) or any(not isinstance(item, str) for item in requested):
				raise APIError(400, "請提供成品代號清單")
			for item in requested:
				try:
					formats.item_format(plan, item)
				except KeyError:
					raise APIError(400, "成品代號不存在或形式尚未實作")
			points = list(dict.fromkeys(item for item in requested if formats.item_format(plan, item) == "video"))
			items = points + [item for item in ("highlight", "mindmap", "slides") if item in requested]
			detail = {item["item"]: item for item in self.get_unit(identifier)["items"]}
			self._check_queue()
			return {"job_ids": [self.job_queue.enqueue(identifier, item) for item in items
				if detail[item]["status"] != "done" and not self._active_job(identifier, item)]}

	def enqueue_renarrate(self, identifier, item, payload):
		with self.lock:
			self._check_material(identifier)
			plan = self._plan(identifier)
			try:
				fid = formats.item_format(plan, item)
			except KeyError:
				raise APIError(400, "找不到可重配的成品")
			if fid not in ("video", "highlight"):
				raise APIError(400, "這個形式沒有配音")
			scene = self._unit_path(identifier, f"{item}.scene.json")
			if not scene.is_file():
				raise APIError(409, "請先生成分鏡")
			beats = payload.get("beats")
			count = sum(len(part["beats"]) for part in read_json(scene)["scenes"])
			if not isinstance(beats, list) or not beats or any(type(beat) is not int or not 1 <= beat <= count for beat in beats):
				raise APIError(400, "請提供講稿範圍內的句號（從 1 起）")
			if self._active_job(identifier, item):
				raise APIError(409, "這個成品正在製作")
			self._check_queue()
			view = formats.UnitView(identifier, self._unit_dir(identifier), plan, self.tts_mode)
			commands = formats.video.render_commands(view, item, scene)
			commands[0].argv.extend(["--redo", ",".join(str(beat) for beat in dict.fromkeys(beats))])
			return {"job_id": self.job_queue.enqueue_commands(identifier, item, commands)}

	def upload(self, content_type, body):
		try:
			return self.uploads.create(content_type, body)
		except uploads.TooLarge as exc:
			raise APIError(413, str(exc), "拆小再上傳")
		except ValueError as exc:
			raise APIError(400, str(exc))

	def enqueue_normalize(self, identifier):
		with self.lock:
			try:
				directory = self.uploads.directory(identifier)
			except KeyError:
				raise APIError(404, "找不到上傳草稿")
			commands = formats.stages.ingest_commands(directory, self.library.root)
			if self._active_ingest(commands[0].argv):
				raise APIError(409, "這份教材正在整理")
			self._check_queue()
			return {"job_id": self.job_queue.enqueue_stage(None, "ingest", commands)}

	def _active_ingest(self, argv):
		return any(job["format"] == "ingest" and job["state"] in ("queued", "running") and
			(job.get("_commands") or [{}])[0].get("argv") == argv for job in self.job_queue.jobs.values())

	def retry(self, identifier):
		with self.lock:
			job = self.get_job(identifier)
			if job["unit_id"] and job["format"] != "ingest":
				self._check_material(job["unit_id"])
				if job["format"] != "analysis":
					self._plan(job["unit_id"])
			if job["format"] == "ingest":
				commands = self.job_queue.jobs[identifier].get("_commands")
				if commands and self._active_ingest(commands[0]["argv"]):
					raise APIError(409, "這份教材正在整理")
			if job["unit_id"] and self._active_job(job["unit_id"], job["item"]):
				raise APIError(409, "這個成品已經在排隊或製作")
			self._check_queue()
			try:
				return {"job_id": self.job_queue.retry(identifier)}
			except ValueError as exc:
				raise APIError(409, str(exc))

	def get_usage(self):
		with self.lock:
			return usage.summarize([(uid, self.library.meta(uid)["title"], self.library.plan(uid),
				usage.read_unit(self._unit_dir(uid))) for uid in self.library.unit_ids()], date.today())

	def _job_done(self, job):
		if job["unit_id"] is not None:
			self.library.write_manifest(job["unit_id"], self.get_unit(job["unit_id"])["items"])

	def manifest(self, identifier):
		with self.lock:
			path = self._unit_path(identifier, "manifest.json")
			if path.is_file():
				return read_json(path)
			return self.library.write_manifest(identifier, self.get_unit(identifier)["items"])


class StudioHTTPServer(ThreadingHTTPServer):
	def __init__(self, address, studio, web_dir=WEB_DIR):
		self.studio = studio
		self.web_dir = Path(web_dir).resolve()
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
		self._json(code, APIError(code, "請求格式不正確" if code == 400 else "不支援此請求").payload())

	def _read_body(self, limit):
		try:
			length = int(self.headers.get("Content-Length", "0"))
		except ValueError:
			raise APIError(400, "請求長度不正確")
		if length < 0:
			raise APIError(400, "請求長度不正確")
		if length > limit:
			self.close_connection = True
			raise APIError(413, "教材內容超過大小限制", "拆小再上傳")
		return self.rfile.read(length)

	def _body(self):
		def invalid_constant(value):
			raise ValueError(value)
		try:
			body = self._read_body(MAX_BODY)
			payload = json.loads(body.decode("utf-8"), parse_constant=invalid_constant) if body else {}
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
					return self._json(416, APIError(416, "影片範圍不正確").payload(), {"Content-Range": f"bytes */{size}"})
				first, last = match.groups()
				if first:
					start, end = int(first), min(int(last), size - 1) if last else size - 1
				else:
					start = max(0, size - int(last))
				if start > end or start >= size:
					return self._json(416, APIError(416, "影片範圍不正確").payload(), {"Content-Range": f"bytes */{size}"})
				status = 206
			mime = {".mp4": "video/mp4", ".json": "application/json", ".js": "text/javascript", ".mjs": "text/javascript"}.get(path.suffix.lower())
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
			return safe_path(self.server.web_dir, relative)
		except ValueError:
			raise APIError(404, "找不到檔案")

	def _dispatch(self):
		path = unquote(urlsplit(self.path).path)
		studio = self.server.studio
		if self.command in ("GET", "HEAD"):
			if path == "/":
				query = urlsplit(self.path).query
				self.send_response(302)
				self.send_header("Location", "/web/index.html" + (f"?{query}" if query else ""))
				self.send_header("Content-Length", "0")
				self.end_headers()
				return
			if path.startswith("/web/"):
				return self._file(self._static_path(path[len("/web/"):]))
			if path.startswith("/media/"):
				parts = path.split("/", 3)
				if len(parts) != 4:
					raise APIError(404, "找不到檔案")
				return self._file(studio._unit_path(parts[2], parts[3]))
			match = re.fullmatch(r"/embed/([^/]+)/([^/]+)", path)
			if match:
				uid, item = match.groups()
				studio._unit_dir(uid)
				try:
					formats.item_format(studio.library.plan(uid), item)
				except KeyError:
					raise APIError(404, "找不到成品")
				return self._file(self._static_path("embed.html"))
			if path == "/api/v1/formats":
				return self._json(200, formats.public())
			if path == "/api/v1/units":
				return self._json(200, studio.list_units())
			if path == "/api/v1/queue":
				return self._json(200, studio.job_queue.queue())
			if path == "/api/v1/usage":
				return self._json(200, studio.get_usage())
			match = re.fullmatch(r"/api/v1/units/([^/]+)(/manifest|/material)?", path)
			if match:
				uid, manifest = match.groups()
				studio._unit_dir(uid)
				return self._json(200, studio.get_material(uid) if manifest == "/material" else
					studio.manifest(uid) if manifest else studio.get_unit(uid))
			match = re.fullmatch(r"/api/v1/jobs/([^/]+)", path)
			if match:
				return self._json(200, studio.get_job(match[1]))
		elif self.command == "POST":
			if path == "/api/v1/uploads":
				body = self._read_body(uploads.MAX_BODY)
				return self._json(200, studio.upload(self.headers.get("Content-Type", ""), body))
			if path == "/api/v1/units":
				return self._json(200, studio.create_unit(self._body()))
			if path == "/api/v1/ask":
				return self._json(200, studio.ask(self._body()))
			match = re.fullmatch(r"/api/v1/uploads/([^/]+)/normalize", path)
			if match:
				self._body()
				return self._json(200, studio.enqueue_normalize(match[1]))
			match = re.fullmatch(r"/api/v1/units/([^/]+)/(analyze|generate|review)", path)
			if match:
				uid, action = match.groups()
				payload = self._body()
				return self._json(200, studio.review_material(uid, payload) if action == "review" else
					studio.enqueue_analyze(uid) if action == "analyze" else studio.enqueue_generate(uid, payload))
			match = re.fullmatch(r"/api/v1/units/([^/]+)/items/([^/]+)/renarrate", path)
			if match:
				return self._json(200, studio.enqueue_renarrate(*match.groups(), self._body()))
			match = re.fullmatch(r"/api/v1/jobs/([^/]+)/retry", path)
			if match:
				self._body()
				return self._json(200, studio.retry(match[1]))
		raise APIError(404, "找不到此入口")

	def _handle(self):
		try:
			self._dispatch()
		except APIError as exc:
			self._json(exc.status, exc.payload())
		except (BrokenPipeError, ConnectionResetError):
			pass
		except (OSError, ValueError, TypeError, KeyError, AttributeError):
			self._json(500, APIError(500, "無法讀取工作台資料", "請檢查檔案與本機環境").payload())

	do_GET = _handle
	do_POST = _handle
	do_HEAD = _handle


def main():
	parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	parser.add_argument("--port", type=int, default=8765)
	parser.add_argument("--out", default=str(ROOT / "video_engine/out/units"))
	parser.add_argument("--web-dir", default=str(WEB_DIR))
	args = parser.parse_args()
	studio = Studio(args.out)
	try:
		server = StudioHTTPServer(("127.0.0.1", args.port), studio, web_dir=args.web_dir)
		try:
			print(f"多元教材工作台：http://127.0.0.1:{args.port}（素材庫：{studio.out}）", flush=True)
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
