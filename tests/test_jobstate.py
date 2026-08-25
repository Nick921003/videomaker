import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobstate import STAGE_WEIGHT, Job


def fake_runner(stages):
	"""照給定的階段清單吐 stage_start / stage_end，模擬 run.py --json-events"""
	def runner(stage_from, stage_to):
		lo, hi = stages.index(stage_from), stages.index(stage_to)
		for s in stages[lo:hi + 1]:
			yield {"event": "stage_start", "stage": s}
			yield {"event": "stage_end", "stage": s, "sec": 1.0}
	return runner


def failing_runner(fail_at):
	def runner(stage_from, stage_to):
		yield {"event": "stage_start", "stage": fail_at}
		yield {"event": "stage_fail", "stage": fail_at, "code": 1}
	return runner


ALL = ["lesson", "slides", "actions", "validate", "storyboard", "synth", "timeline", "video"]


class TestJob(unittest.TestCase):
	def test_權重總和是100(self):
		self.assertEqual(sum(STAGE_WEIGHT.values()), 100)

	def test_start_跑到審稿閘就停(self):
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		j.start()
		self.assertEqual(j.status, "awaiting_review")
		self.assertEqual(j.stage, "storyboard")

	def test_審稿閘之後才跑語音合成(self):
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		j.start()
		self.assertNotIn("synth", [e["stage"] for e in j.events])
		j.approve([])
		self.assertIn("synth", [e["stage"] for e in j.events])
		self.assertEqual(j.status, "done")
		self.assertEqual(j.pct, 100)

	def test_進度只算已完成階段的權重(self):
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		j.start()
		# lesson 25 + slides 1 + actions 19 + validate 1 + storyboard 0
		self.assertEqual(j.pct, 46)

	def test_階段失敗就轉_failed(self):
		j = Job("m.md", "/tmp/out", 110, failing_runner("lesson"))
		j.start()
		self.assertEqual(j.status, "failed")
		self.assertEqual(j.stage, "lesson")

	def test_審稿倒數60秒(self):
		now = [1000.0]
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL), clock=lambda: now[0])
		j.start()
		self.assertEqual(j.review_deadline, 1060.0)
		self.assertFalse(j.review_expired())
		now[0] = 1061.0
		self.assertTrue(j.review_expired())

	def test_未進審稿閘不可以_approve(self):
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		with self.assertRaises(RuntimeError):
			j.approve([])

	def test_claim_只有一個搶得到(self):
		# 倒數計時器與使用者送出會同時搶。兩邊都成功的話，
		# 會有兩條執行緒同時跑語音合成與渲染，檔案互相蓋掉
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		j.start()
		self.assertTrue(j.claim())
		self.assertFalse(j.claim())
		self.assertEqual(j.status, "running")

	def test_claim_成功後狀態立刻是_running_不等執行緒(self):
		# 狀態必須在 claim() 回來的當下就翻好。若等到子執行緒裡才翻，
		# 中間那段空窗期計時器會看到還是 awaiting_review 而重複觸發
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		j.start()
		j.claim()
		self.assertNotEqual(j.status, "awaiting_review")

	def test_claim_多執行緒同時搶只有一個贏(self):
		# 順序呼叫兩次的測試把 _claim_lock 拿掉仍全綠，代表沒迴歸保護。
		# 用 Barrier 讓 8 條執行緒同一瞬間進 claim() 才能測到，防止鎖失效
		for _ in range(50):
			j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
			j.start()
			barrier = threading.Barrier(8)
			results = []

			def worker():
				barrier.wait()  # 同步所有執行緒
				results.append(j.claim())

			threads = [threading.Thread(target=worker) for _ in range(8)]
			for t in threads:
				t.start()
			for t in threads:
				t.join()

			# 恰好一個搶到
			self.assertEqual(sum(results), 1)
			# 狀態確實翻了
			self.assertEqual(j.status, "running")


if __name__ == "__main__":
	unittest.main()
