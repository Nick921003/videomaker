import os
import subprocess
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import serve


def _sleeper():
	"""開一個會活很久的子行程，用來驗證我們真的收得掉它"""
	return serve.spawn([sys.executable, "-c", "import time; time.sleep(30)"])


class TestChildLifecycle(unittest.TestCase):
	def tearDown(self):
		serve.kill_children()

	def test_spawn_會登記到存活集合(self):
		p = _sleeper()
		self.addCleanup(serve.reap, p)
		self.assertIn(p, serve.live_children())

	def test_reap_收掉子行程且可以重複呼叫(self):
		p = _sleeper()
		serve.reap(p)
		self.assertIsNotNone(p.poll(), "子行程還活著")
		self.assertNotIn(p, serve.live_children())
		serve.reap(p)      # 第二次不可以炸

	def test_kill_children_收掉全部(self):
		a, b = _sleeper(), _sleeper()
		self.assertEqual(serve.kill_children(), 2)
		self.assertIsNotNone(a.poll())
		self.assertIsNotNone(b.poll())
		self.assertEqual(serve.live_children(), set())

	def test_generator_被丟掉時子行程要跟著死(self):
		# real_runner 的事件迴圈一收到 stage_fail 就 return，generator 被丟在
		# yield 上。沒有 finally 的話子行程會在背景把整條管線跑完，
		# 而 job 已經標成 failed、服務會放行下一個 job
		holder = {}

		def gen():
			p = _sleeper()
			holder["p"] = p
			try:
				yield 1
				yield 2
			finally:
				serve.reap(p)

		g = gen()
		next(g)
		self.assertIsNone(holder["p"].poll(), "測試前提：子行程應該還活著")
		g.close()          # 等同 generator 被丟棄
		self.assertIsNotNone(holder["p"].poll(), "generator 收掉了，子行程卻還活著")

	def test_shutdown_會收掉登記中的子行程並關掉_socket(self):
		# 起服務、登記一個活著的子行程、呼叫收尾，子行程必須死透。
		# 用「起服務按 Ctrl+C 再 pgrep 找 run.py」驗不了這件事——
		# 沒送過 job 的話 run.py 根本沒被開過，那種檢查必然通過
		srv = serve.make_server(0)      # 埠號 0＝讓 OS 挑一個沒被佔用的
		self.addCleanup(srv.server_close)      # shutdown 若提早 return，socket 還是要關掉
		p = _sleeper()
		self.assertIsNone(p.poll(), "測試前提：子行程應該活著")
		self.assertEqual(serve.shutdown(srv), 1)
		self.assertIsNotNone(p.poll(), "收尾跑完了，子行程卻還活著")


if __name__ == "__main__":
	unittest.main()
