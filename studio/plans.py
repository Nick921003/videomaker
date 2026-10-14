"""只保存由 server 驗證過的計畫。"""

from copy import deepcopy
from dataclasses import dataclass
import threading
import uuid

from studio.contracts import assert_canonical_plan


@dataclass(frozen=True)
class PlanRecord:
	plan_id: str
	plan: dict
	instruction: str = ""


class PlanStore:
	MAX_PLANS = 100

	def __init__(self):
		self._items = {}
		self._lock = threading.Lock()

	def save_canonical(self, plan, instruction=""):
		assert_canonical_plan(plan)
		record = PlanRecord(uuid.uuid4().hex, deepcopy(plan), instruction)
		with self._lock:
			self._items[record.plan_id] = (deepcopy(record.plan), record.instruction)
			while len(self._items) > self.MAX_PLANS:
				self._items.pop(next(iter(self._items)))
		return PlanRecord(record.plan_id, deepcopy(record.plan), record.instruction)

	def get(self, plan_id):
		with self._lock:
			item = deepcopy(self._items.get(plan_id))
		return PlanRecord(plan_id, item[0], item[1]) if item else None
