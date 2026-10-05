"""單一子行程佇列、stdout 協定與工作復原。"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import uuid

from . import formats
from .library import read_json, safe_path, write_json


ROOT = Path(__file__).resolve().parents[1]
PROJECT_PY = ROOT / ".venv/bin/python"
PLAYWRIGHT_PY = Path("~/.local/share/pipx/venvs/webwright/bin/python").expanduser()
MODEL = "google:gemini-3.8-flash"
_JOB_ID = re.compile(r"[a-f0-9]{32}")
_BUSY = re.compile(r"429|503|UNAVAILABLE|RESOURCE_EXHAUSTED|[Tt]ime ?out|timed out")
_FIELDS = ("job_id", "unit_id", "item", "format", "state", "steps", "current", "log", "spent_usd", "error", "warnings")

ERRORS = {
	"gemini_busy": {"reason": "Gemini 暫時忙碌或連線中斷", "advice": "等 1–2 分鐘再按「重試」", "retry": True},
	"repair_exhausted": {"reason": "分鏡還有問題（{detail}）", "advice": "重試會從失敗草稿接著修，約 US$0.01", "retry": True},
	"quote_mismatch": {"reason": "AI 引用的句子在教材裡找不到", "advice": "重試，約 US$0.005", "retry": True},
	"tts_missing": {"reason": "{detail}配音一直漏字", "advice": "重試；仍失敗就改寫那一句", "retry": True},
	"budget": {"reason": "這份教材已花到上限 US$0.50", "advice": "少選幾點或提高上限", "retry": False},
	"selftest": {"reason": "元件檢查沒過，為了不浪費錢沒有呼叫 AI", "advice": "回報開發者", "retry": False},
	"too_large": {"reason": "超過 5 MB／30 頁／6 萬字", "advice": "拆小再上傳", "retry": False},
	"interrupted": {"reason": "伺服器重啟，工作中斷", "advice": "重試", "retry": True},
	"unknown": {"reason": "{detail}", "advice": "重試或回報", "retry": True},
}


def parse_marker(line):
	parts = line.rstrip("\r\n").split(maxsplit=2)
	if len(parts) == 2 and parts[0] in ("@step", "@unit"):
		return parts[0][1:], parts[1]
	if len(parts) >= 2 and parts[0] == "@error":
		return "error", parts[1], parts[2] if len(parts) == 3 else ""
	return None


def classify(code, detail, log_tail):
	lines = log_tail.splitlines() if isinstance(log_tail, str) else list(log_tail)
	if not code and _BUSY.search("\n".join(lines)):
		code = "gemini_busy"
	if code not in ERRORS:
		code = "unknown"
	if code == "unknown":
		detail = "\n".join(lines[-3:]) or detail or "（無工作紀錄）"
	elif code == "tts_missing" and not detail:
		detail = "第 X 句"
	return {"code": code, **ERRORS[code], "reason": ERRORS[code]["reason"].format(detail=detail)}


class StepTracker:
	def __init__(self, step_ids):
		self._states = dict.fromkeys(step_ids, "pending")
		self.current = None

	def enter(self, sid):
		if sid not in self._states:
			return
		if self.current is not None:
			self._states[self.current] = "done"
		for step in self._states:
			if step == sid:
				break
			if self._states[step] == "pending":
				self._states[step] = "skipped"
		self._states[sid] = "running"
		self.current = sid

	def finish(self, ok):
		if self.current is not None:
			self._states[self.current] = "done" if ok else "failed"
		if ok:
			self._states = {sid: "skipped" if state == "pending" else state for sid, state in self._states.items()}
			self.current = None

	def states(self):
		return [{"id": sid, "state": state} for sid, state in self._states.items()]


def run_command(argv, on_line):
	environment = dict(os.environ, PYTHONUNBUFFERED="1", VIDEO_ENGINE_LLM=MODEL)
	with subprocess.Popen(argv, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1) as process:
		for line in process.stdout:
			on_line(line.rstrip("\r\n"))
		return process.wait()


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
					# 寫入中的最後一列留待下一次輪詢。
					continue
	except FileNotFoundError:
		pass
	return round(total, 8)


def spent_usd(directory, path_resolver=None):
	directory = Path(directory)
	resolve = path_resolver or (lambda relative: safe_path(directory, relative))
	return round(_sum_usd(resolve("usage.jsonl")) + sum(_sum_usd(resolve(path.relative_to(directory)))
		for path in directory.glob("**/tts_usage.jsonl")), 6)


def _valid_job(job):
	if any(key not in job for key in _FIELDS):
		return False
	if any(type(job[key]) is not str for key in ("job_id", "item", "format")):
		return False
	if job["unit_id"] is not None and type(job["unit_id"]) is not str:
		return False
	if job["current"] is not None and type(job["current"]) is not str:
		return False
	if type(job["spent_usd"]) not in (int, float) or not math.isfinite(job["spent_usd"]):
		return False
	if not isinstance(job["log"], list) or any(type(line) is not str for line in job["log"]):
		return False
	if not isinstance(job["steps"], list) or any(not isinstance(step, dict)
		or type(step.get("id")) is not str or step.get("state") not in ("pending", "running", "done", "failed", "skipped")
		for step in job["steps"]):
		return False
	error = job["error"]
	return error is None or (isinstance(error, dict) and type(error.get("retry")) is bool
		and all(type(error.get(key)) is str for key in ("code", "reason", "advice")))


class JobQueue:
	def __init__(self, library, runner=None, formats_mod=None, tts_mode="gemini"):
		self.library = library
		self.runner = runner or run_command
		self.formats = formats_mod or formats
		self.tts_mode = tts_mode
		self.lock = threading.RLock()
		self.jobs = {}
		self.pending = queue.Queue()
		self.stopping = threading.Event()
		self._running = None
		self._restore()
		self.worker = threading.Thread(target=self._work, name="工作佇列", daemon=True)
		self.worker.start()

	def _view(self, uid):
		return formats.UnitView(uid, self.library.unit_dir(uid), self.library.plan(uid), self.tts_mode)

	def enqueue(self, uid, item):
		view = self._view(uid)
		fid = self.formats.item_format(view.plan, item)
		module = self.formats.get_format(fid)
		return self._enqueue(uid, item, fid, module.FORMAT["steps"])

	def enqueue_stage(self, uid_or_None, stage_id, commands):
		stage = next((stage for stage in self.formats.stages.STAGES if stage["id"] == stage_id), None)
		if stage is None:
			raise KeyError(stage_id)
		if uid_or_None is not None:
			self.library.unit_dir(uid_or_None)
		stored = [{"step": cmd.step, "argv": list(map(str, cmd.argv)), "python": cmd.python} for cmd in commands]
		return self._enqueue(uid_or_None, stage_id, stage_id, stage["steps"], stored)

	def _enqueue(self, uid, item, fid, steps, commands=None):
		with self.lock:
			if self.stopping.is_set():
				raise ValueError("工作佇列已停止")
			jid = uuid.uuid4().hex
			job = {"job_id": jid, "unit_id": uid, "item": item, "format": fid, "state": "queued",
				"steps": StepTracker(step["id"] for step in steps).states(), "current": None,
				"log": [], "spent_usd": 0.0, "error": None, "warnings": [], "created_at": datetime.now(timezone.utc).isoformat(),
				"_global": uid is None, "_commands": commands}
			self._save(job)
			self.jobs[jid] = job
			self.pending.put(jid)
			return jid

	def _path(self, job):
		relative = f"jobs/{job['job_id']}.json"
		if job.get("_global"):
			return safe_path(self.library.root.parent, relative)
		return self.library.path(job["unit_id"], relative)

	def _save(self, job):
		if job["state"] == "running" and "_before" in job:
			job["spent_usd"] = self._spent(job)
		write_json(self._path(job), job)

	def _usage(self, uid):
		if uid is None:
			return 0.0
		return spent_usd(self.library.unit_dir(uid), lambda relative: self.library.path(uid, relative))

	def _spent(self, job):
		return round(self._usage(job["unit_id"]) - job.get("_before", 0.0), 6)

	def _public(self, job):
		result = deepcopy({key: job[key] for key in _FIELDS})
		if "kind" in job:
			result.update(deepcopy({key: job[key] for key in ("kind", "stories", "completed", "target", "costs") if key in job}))
		if job["state"] == "running":
			result["spent_usd"] = self._spent(job)
		return result

	def get(self, job_id):
		with self.lock:
			return self._public(self.jobs[job_id])

	def queue(self):
		with self.lock:
			return {"running": self._public(self.jobs[self._running]) if self._running else None,
				"queued": [self._public(job) for job in self.jobs.values() if job["state"] == "queued"]}

	def retry(self, job_id):
		with self.lock:
			job = self.jobs[job_id]
			if job["state"] != "failed" or not (job["error"] or {}).get("retry"):
				raise ValueError("這個工作無法重試")
			if job["format"] in ("analysis", "ingest"):
				commands = job.get("_commands")
				if commands is None and job["format"] == "analysis":
					return self.enqueue_stage(job["unit_id"], "analysis", self.formats.stages.analysis_commands(self._view(job["unit_id"])))
				if commands is None:
					raise ValueError("工作缺少原始執行指令")
				return self.enqueue_stage(None if job.get("_global") else job["unit_id"], job["format"],
					[formats.Command(**cmd) for cmd in commands])
			return self.enqueue(job["unit_id"], job["item"])

	def _restore(self):
		paths = []
		for uid in self.library.unit_ids():
			try:
				paths.extend((uid, path) for path in self.library.path(uid, "jobs").glob("*.json"))
			except (OSError, ValueError):
				continue
		paths.extend((None, path) for path in safe_path(self.library.root.parent, "jobs").glob("*.json"))
		for uid, path in paths:
			if not _JOB_ID.fullmatch(path.stem):
				continue
			try:
				path = self.library.path(uid, f"jobs/{path.name}") if uid else safe_path(self.library.root.parent, f"jobs/{path.name}")
				job = read_json(path)
				if (not isinstance(job, dict) or job.get("job_id") != path.stem
					or (uid is not None and job.get("unit_id") != uid)
					or job.get("state") not in ("queued", "running", "done", "failed")):
					continue
				# B1 的舊工作仍可查詢；重新執行一律走格式登錄表。
				if "item" not in job:
					kind = job.get("kind")
					if kind not in ("plan", "stories", "highlight"):
						continue
					fid = "analysis" if kind == "plan" else "video" if kind == "stories" else "highlight"
					item = "analysis" if kind == "plan" else "highlight" if kind == "highlight" else job.get("target") or next(iter(job.get("stories", [])), "")
					steps = self.formats.stages.ANALYSIS["steps"] if fid == "analysis" else self.formats.get_format(fid).FORMAT["steps"]
					job.update(item=item, format=fid, steps=StepTracker(step["id"] for step in steps).states(), current=None)
					if isinstance(job.get("error"), str):
						job["error"] = classify(None, "", [job["error"]])
				job.setdefault("spent_usd", 0.0)
				job.setdefault("error", None)
				job.setdefault("warnings", [])
				job.setdefault("log", [])
				if not _valid_job(job):
					continue
				job["_global"] = uid is None
				job["log"] = job["log"][-40:]
				if job["state"] in ("queued", "running"):
					if job["state"] == "running" and "_before" in job:
						job["spent_usd"] = self._spent(job)
					job.update(state="failed", error=classify("interrupted", "", job["log"]))
					for step in job["steps"]:
						if step["state"] == "running":
							step["state"] = "failed"
					self._save(job)
				self.jobs[job["job_id"]] = job
			except (KeyError, TypeError, OSError, ValueError, RecursionError):
				continue
		self.jobs = dict(sorted(self.jobs.items(), key=lambda entry:
			entry[1].get("created_at", "") if type(entry[1].get("created_at", "")) is str else ""))

	def _execute(self, job, tracker):
		commands = job.get("_commands")
		if commands is not None:
			commands = [formats.Command(**cmd) for cmd in commands]
		else:
			commands = self.formats.get_format(job["format"]).commands(self._view(job["unit_id"]), job["item"])
		def on_line(line):
			with self.lock:
				line = line.rstrip("\r\n")
				job["log"] = [*job["log"], line][-40:]
				marker = parse_marker(line)
				if marker:
					if marker[0] == "step":
						tracker.enter(marker[1])
					elif marker[0] == "error":
						job["_error"] = marker[1:]
						job["error"] = classify(*marker[1:], job["log"])
					elif marker[0] == "unit":
						self.library.unit_dir(marker[1])
						if job["unit_id"] is None:
							job["_before"] = job.get("_before_units", {}).get(marker[1], 0.0)
						job["unit_id"] = marker[1]
				job.update(steps=tracker.states(), current=tracker.current)
				self._save(job)
		for cmd in commands:
			with self.lock:
				tracker.enter(cmd.step)
				job.update(steps=tracker.states(), current=tracker.current)
				self._save(job)
			self._check_paths(job, cmd)
			python = PLAYWRIGHT_PY if cmd.python == "playwright" else PROJECT_PY
			code = self.runner([str(python), *map(str, cmd.argv)], on_line)
			if code != 0 or job.get("_error"):
				with self.lock:
					job["error"] = classify(*job.get("_error", (None, "")), job["log"])
				return False
		return True

	def _check_paths(self, job, cmd):
		uid = job["unit_id"]
		directory = self.library.unit_dir(uid) if uid is not None else self.library.root
		for arg in cmd.argv:
			try:
				relative = Path(arg).relative_to(directory)
			except ValueError:
				continue
			if uid is None:
				safe_path(directory, relative)
			else:
				self.library.path(uid, relative)
		if Path(cmd.argv[0]).name == "author.py" and job["unit_id"] is not None:
			files = ["plan.json", "usage.jsonl"]
			if cmd.argv[1] == "scene":
				files.extend(f"{cmd.argv[4]}.{suffix}.json" for suffix in ("scene", "failed", "report"))
			for relative in files:
				self.library.path(job["unit_id"], relative)

	def _work(self):
		while True:
			jid = self.pending.get()
			try:
				if jid is None or self.stopping.is_set():
					return
				job = self.jobs[jid]
				tracker = StepTracker(step["id"] for step in job["steps"])
				ok = False
				try:
					with self.lock:
						self._running = jid
						job.update(state="running", _before=self._usage(job["unit_id"]))
						if job["unit_id"] is None:
							job["_before_units"] = {uid: self._usage(uid) for uid in self.library.unit_ids()}
						self._save(job)
					ok = self._execute(job, tracker)
				except Exception as error:
					with self.lock:
						job["log"] = [*job["log"], str(error)][-40:]
						job["error"] = classify(*job.get("_error", (None, "")), job["log"])
				finally:
					with self.lock:
						tracker.finish(ok)
						job.update(state="done" if ok else "failed", steps=tracker.states(), current=tracker.current)
						try:
							job["spent_usd"] = self._spent(job)
							self._save(job)
						finally:
							self._running = None
			finally:
				self.pending.task_done()

	def close(self):
		with self.lock:
			if not self.stopping.is_set():
				self.stopping.set()
				self.pending.put(None)
		self.worker.join(timeout=3)
