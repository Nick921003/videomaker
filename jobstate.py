#!/usr/bin/env python3
"""Job 狀態機：只管「跑到哪、剩多少、下一步是什麼」，不碰 HTTP、不碰影片。

runner 是注入的，所以這支可以完全離線測試——不用真的跑三分鐘的管線。
"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_engine"))
import ingest

# 權重照實測配（c_string.md：810 字 → 5 頁 98 秒影片，總計 167 秒）。
# 等寬八格會騙人，會卡在第一格不動半分鐘
STAGE_WEIGHT = {
	"lesson": 25, "slides": 1, "actions": 19, "validate": 1,
	"storyboard": 0, "synth": 30, "timeline": 0, "video": 24,
}
REVIEW_SEC = 60          # 審稿閘倒數，首次現場實測後再調
BEFORE_REVIEW = ("lesson", "storyboard")
AFTER_REVIEW = ("synth", "video")


class Job:
	def __init__(self, material_path, out_dir, sec, runner, clock=time.time):
		self.material_path = material_path
		self.out_dir = out_dir
		self.sec = sec
		self.runner = runner
		self.clock = clock
		self.status = "queued"
		self.stage = None
		self.events = []
		self.done_stages = set()
		self.review_deadline = None
		self.error = None
		self._claim_lock = threading.Lock()
		self.actions_path = None
		self.actions_backup = None
		self.lesson_path = None
		self.video_path = None
		self.retried = False
		self.notice = None

	@property
	def pct(self):
		return sum(STAGE_WEIGHT.get(s, 0) for s in self.done_stages)

	def _pump(self, stage_from, stage_to):
		"""跑一段階段區間，把事件收進來。回傳是否成功"""
		for ev in self.runner(stage_from, stage_to):
			self.events.append(ev)
			self.stage = ev.get("stage")
			if ev["event"] == "stage_end":
				self.done_stages.add(ev["stage"])
			elif ev["event"] == "stage_fail":
				self.status = "failed"
				self.error = f"{ev['stage']} 失敗（回傳碼 {ev.get('code')}）"
				return False
		return True

	def start(self):
		self.status = "running"
		if not self._pump(*BEFORE_REVIEW):
			return
		stem = ingest.lesson_id_for(self.material_path)
		base = os.path.dirname(os.path.dirname(os.path.abspath(self.material_path)))
		self.lesson_path = os.path.join(base, "examples", f"{stem}.lesson.json")
		self.actions_path = os.path.join(base, "examples", f"{stem}.actions.json")
		self.actions_backup = self.actions_path + ".orig"
		self.video_path = os.path.join(self.out_dir, stem, f"{stem}.mp4")
		# 上一輪跑剩的 .orig 一定要清掉。留著的話，這一輪若用「檔案已存在就不備份」
		# 的判斷會跳過備份，之後還原會把上一次的舊講稿蓋回來——而且是靜默的
		if os.path.exists(self.actions_backup):
			os.remove(self.actions_backup)
		self.status = "awaiting_review"
		self.review_deadline = self.clock() + REVIEW_SEC

	def review_expired(self):
		return self.review_deadline is not None and self.clock() > self.review_deadline

	def claim(self):
		"""把 awaiting_review 原子地翻成 running，搶到回 True。

		倒數計時器與使用者送出會同時搶這個位子。狀態必須在這裡就翻好，
		不能等到子執行緒進 resume() 才翻——中間那段空窗期，計時器會看到
		狀態還是 awaiting_review 而重複觸發，兩條執行緒同時跑合成與渲染。
		"""
		with self._claim_lock:
			if self.status != "awaiting_review":
				return False
			self.status = "running"
			return True

	def resume(self):
		"""審稿後續跑。呼叫前必須先 claim() 成功"""
		if not self._pump(*AFTER_REVIEW):
			return
		self.status = "done"
		self.stage = None

	def approve(self, segments):
		"""claim + resume 的便利包裝。segments 為空代表沒改，
		回寫與重驗由呼叫端在進來之前做完"""
		if not self.claim():
			raise RuntimeError(f"目前是 {self.status}，不能核可")
		self.resume()
