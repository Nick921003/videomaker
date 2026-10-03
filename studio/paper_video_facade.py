"""紙上動畫實驗入口；沿用受限產物與投影片路由。"""

import json
from urllib.parse import quote

from studio.video_facade import FacadeError, VideoJobFacade
from video_engine.paper_contract import PaperError


_CAPABILITY = 'video.paper_preview.v1'


class PaperVideoJobFacade(VideoJobFacade):
	def close(self):
		self._stop.set()
		self.job.close()
		self._release_if_terminal()

	def _release_if_terminal(self):
		# 執行中的 LLM/TTS 不可中斷，返回後由 worker 終態負責釋放。
		if self.job.worker_done.is_set(): super()._release_if_terminal()

	def snapshot(self):
		result = super().snapshot()
		result['capability_id'] = _CAPABILITY
		result['production_metrics'] = self.job.production_metrics()
		return result

	def finalize_artifact(self):
		with self._lock:
			super().finalize_artifact()
			self._artifact['capability_id'] = _CAPABILITY
			return self.artifacts()[0]

	def get_review(self):
		with self.job._work_lock:
			if self.job.status != 'awaiting_review':
				raise FacadeError('review_conflict', '現在不在講稿審核階段')
			try:
				with open(self.job.layout_path, encoding='utf-8') as handle: layout = json.load(handle)
				slides = [{'slide_id': item['slide_id'],
					'preview_url': f"/api/studio/jobs/{self.job_id}/slides/{quote(item['slide_id'], safe='')}"}
					for item in layout['slides']]
				return {'segments': self.job.review_segments(), 'deadline': self.job.review_deadline, 'slides': slides}
			except (OSError, ValueError, KeyError, TypeError) as exc:
				raise FacadeError('review_unavailable', '講稿預覽目前無法讀取') from exc

	def submit_review(self, segments):
		try:
			self.job.submit_review(segments)
		except PaperError as exc:
			raise FacadeError('invalid_review', '講稿格式、段落或長度不符合契約') from exc
		except RuntimeError as exc:
			raise FacadeError('review_conflict', '講稿審核已由另一個請求處理') from exc
		except OSError as exc:
			raise FacadeError('review_failed', '講稿儲存失敗，請重試') from exc
		self._resume_async()
		return {'ok': True, 'errors': [], 'deadline': None, 'notice': None}
