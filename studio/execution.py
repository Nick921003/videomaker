"""legacy 與工作台共用的唯一昂貴工作執行權。"""

import threading


class ExecutionSlot:
	def __init__(self):
		self._owner = None
		self._lock = threading.Lock()

	def claim(self, owner):
		if owner is None:
			raise ValueError("execution slot owner 不可為空")
		with self._lock:
			if self._owner is not None:
				return False
			self._owner = owner
			return True

	def release(self, owner):
		with self._lock:
			if self._owner != owner:
				raise RuntimeError("execution slot owner 不符")
			self._owner = None

	def owner(self):
		with self._lock:
			return self._owner
