"""單元頁取得重點清單狀態、確認、重抽；待確認時 API 直接拒絕製作。"""
from pathlib import Path
import http.client
import json
import tempfile
import threading
import unittest

from tests.fixtures.key_points import model_output
from tests.fixtures.teaching_quality import MATERIAL
from tests.test_workbench_server import FakeRunner
from workbench import key_points as W
from workbench import server as BS
from workbench.library import read_json, write_json


class TestKeyPointsServer(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.runner = FakeRunner()
		self.studio = BS.Studio(Path(self.temp.name) / 'units', command_runner=self.runner, tts_mode='gemini')
		self.addCleanup(self.studio.close)
		self.addCleanup(self.runner.release.set)
		self.uid, _ = self.studio.library.create_unit(MATERIAL)
		self.directory = self.studio.library.unit_dir(self.uid)

	def extract(self, kind='md'):
		path = self.directory / 'material.json'
		data = read_json(path); data['sources'][0]['kind'] = kind; write_json(path, data)
		W.get_key_points(self.directory, lambda *_: (model_output(), {}), require_ready=False)

	def test_missing_then_ready(self):
		self.assertEqual(self.studio.get_key_points(self.uid)['status'], 'missing')
		self.extract()
		value = self.studio.get_key_points(self.uid)
		self.assertEqual((value['unit_id'], value['status'], value['structure']), (self.uid, 'ready', 'material'))

	def test_confirm_and_reextract(self):
		self.extract('pdf')
		digest = self.studio.get_key_points(self.uid)['digest']
		with self.assertRaises(BS.APIError) as caught:
			self.studio.review_key_points(self.uid, {'action': 'confirm', 'digest': '0' * 64})
		self.assertEqual(caught.exception.status, 409)
		self.assertEqual(self.studio.review_key_points(self.uid, {'action': 'confirm', 'digest': digest})['status'], 'ready')
		self.assertEqual(self.studio.review_key_points(self.uid, {'action': 'reextract', 'note': '重點放在差一錯誤'})['status'], 'missing')
		with self.assertRaises(BS.APIError) as caught:
			self.studio.review_key_points(self.uid, {'action': 'delete'})
		self.assertEqual(caught.exception.status, 400)

	def test_generation_blocked_while_needs_review(self):
		self.extract('pdf')
		with self.assertRaises(BS.APIError) as caught:
			self.studio.enqueue_generate(self.uid, {'items': ['slides']})
		self.assertEqual((caught.exception.status, caught.exception.code), (409, 'key_points_review'))
		with self.assertRaises(BS.APIError) as caught:
			self.studio.enqueue_generate(self.uid, {'items': ['mindmap']})
		self.assertEqual(caught.exception.code, 'key_points_review')

	def test_http_routes(self):
		server = BS.StudioHTTPServer(('127.0.0.1', 0), self.studio, web_dir=Path(self.temp.name))
		thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
		thread.start()
		def stop():
			server.shutdown(); server.server_close(); thread.join(2)
		self.addCleanup(stop)
		def call(method, payload=None):
			connection = http.client.HTTPConnection(*server.server_address, timeout=3)
			try:
				body = json.dumps(payload).encode() if payload is not None else None
				connection.request(method, f'/api/v1/units/{self.uid}/key-points', body=body,
					headers={'Content-Type': 'application/json'} if body else {})
				response = connection.getresponse()
				return response.status, json.loads(response.read())
			finally:
				connection.close()
		self.extract('pdf')
		status, value = call('GET')
		self.assertEqual((status, value['unit_id'], value['status']), (200, self.uid, 'needs_review'))
		self.assertEqual(call('POST', {'action': 'confirm', 'digest': '0' * 64})[0], 409)
		status, value = call('POST', {'action': 'confirm', 'digest': value['digest']})
		self.assertEqual((status, value['status']), (200, 'ready'))


if __name__ == '__main__':
	unittest.main()
