import unittest
from studio.catalog import get_capability, public_catalog
from studio.planner import plan_request
from studio.plans import PlanStore
from studio.contracts import ContractError
from tests.test_studio_contracts import SOURCE

class PaperEntryTests(unittest.TestCase):
	def test_shutdown_preserves_active_paper_worker_snapshot_and_output(self):
		from pathlib import Path
		import tempfile
		import threading
		from types import SimpleNamespace
		from unittest.mock import patch
		import serve
		from studio.sources import SourceStore
		with tempfile.TemporaryDirectory() as directory:
			root=Path(directory)
			store=SourceStore(root/'materials')
			source=store.add_upload('source.txt',b'test')
			snapshot=store.snapshot_for_job(source['ref'],source['revision'],'a'*32)
			stem=Path(snapshot).stem.lstrip('.')
			out=root/'out'
			reserved=out/stem
			reserved.mkdir(parents=True)
			marker=reserved/'board.json'
			marker.write_text('preserve')
			facade=SimpleNamespace(job=SimpleNamespace(worker_done=threading.Event()),snapshot_path=snapshot,
				reserved_dir=reserved,close=lambda:None)
			server=SimpleNamespace(server_close=lambda:None)
			with patch.object(serve,'_studio_jobs',{'job':facade}),patch.object(serve,'_source_store',store),patch.object(serve,'OUT',str(out)):
				serve.shutdown(server)
			self.assertTrue(Path(snapshot).is_file())
			self.assertEqual(marker.read_text(),'preserve')
			store.release_path(snapshot)
	def test_experiment_is_hidden_from_normal_catalog_and_closed(self):
		self.assertNotIn('video.paper_preview.v1', [item['id'] for item in public_catalog()])
		cap = get_capability('video.paper_preview.v1')
		self.assertIsNotNone(cap)
		self.assertTrue(cap['experimental'])
		self.assertEqual(set(cap['options']), {'duration_seconds', 'duration_range'})
		self.assertIn('video.paper_preview.v1', [item['id'] for item in public_catalog(True)])

	def test_test_planner_preserves_source_and_records_experimental_capability(self):
		from studio.planner_backends import PaperTestPlannerBackend
		request = {'contract_version':'1.0','instruction':'幫我看懂水循環，做成60秒影片','source':SOURCE}
		record = plan_request(request, PaperTestPlannerBackend(), PlanStore())
		self.assertEqual(record.plan['source'],SOURCE)
		step = record.plan['steps'][0]
		self.assertEqual(step['capability_id'],'video.paper_preview.v1')
		self.assertEqual(step['options'],{'duration_seconds':60})
		self.assertEqual(step['review_gate'],'script')
		with self.assertRaises(ContractError):
			plan_request(dict(request,visual_style='paper'),PaperTestPlannerBackend(),PlanStore())

	def test_duration_range_survives_plan_and_rejects_invalid_bounds(self):
		from studio.planner_backends import PaperTestPlannerBackend, RulePlannerBackend
		request = {'contract_version':'1.0','instruction':'講清楚重點即可','source':SOURCE,
			'duration_range':{'min_seconds':180,'max_seconds':300}}
		record = plan_request(request, PaperTestPlannerBackend(), PlanStore())
		self.assertEqual(record.plan['steps'][0]['options'],
			{'duration_seconds':240,'duration_range':request['duration_range']})
		for bounds in [{'min_seconds':300,'max_seconds':180}, {'min_seconds':True,'max_seconds':300},
			{'min_seconds':29,'max_seconds':300}, {'min_seconds':180,'max_seconds':601},
			{'min_seconds':180,'max_seconds':300,'extra':1}]:
			with self.subTest(bounds=bounds), self.assertRaises(ContractError):
				plan_request(dict(request,duration_range=bounds),PaperTestPlannerBackend(),PlanStore())
		with self.assertRaises(ContractError):
			plan_request(request,RulePlannerBackend(),PlanStore())
