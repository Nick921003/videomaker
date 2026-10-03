import json
import time
import unittest
from unittest.mock import patch
import tests.test_studio_api as helpers
import serve


class PaperHttpTests(unittest.TestCase):
	setUp = helpers.TestStudioHttp.setUp
	request = helpers.TestStudioHttp.request
	session = helpers.TestStudioHttp.session

	def test_new_material_can_generate_review_resume_and_download(self):
		import http.client
		from pathlib import Path
		import numpy as np
		from tests.test_paper_contract import WATER_SOURCE, water_board
		from studio.paper_video import PaperVideoJob
		source=self.store.add_upload('water.txt',WATER_SOURCE.encode())
		headers={'X-Studio-CSRF':self.session(),'Content-Type':'application/json'}
		payload={'contract_version':'1.0','instruction':'做60秒水循環動畫',
			'source':{key:source[key] for key in ('kind','ref','revision')}}
		status, _, planned=self.request('POST','/api/studio/plans?mode=paper-test',json.dumps(payload).encode(),headers)
		def factory(*args,**kwargs):
			kwargs['synthesizer']=lambda speech:(8000,(np.sin(np.arange(32000)*.3)*15000).astype(np.int16))
			kwargs['renderer']=lambda board,tl,audio,video,cancelled:Path(video).write_bytes(b'offline-mp4-fixture')
			return PaperVideoJob(*args,**kwargs)
		with patch.object(serve,'OUT',str(Path(self.tmp.name)/'out')),patch.object(serve,'tts_ready',return_value=True), \
			patch.object(serve,'PaperVideoJob',side_effect=factory),patch.object(serve,'complete_json',
			return_value=(water_board(),{'provider':'anthropic','model':'claude-opus-5-5','in':100,'out':200})):
			status, _, created=self.request('POST','/api/studio/jobs',json.dumps({'plan_id':planned['plan_id']}).encode(),headers)
			self.assertEqual(status,201)
			job_id=created['job_id']
			facade=serve._studio_jobs[job_id]
			self.addCleanup(facade.close)
			path='/api/studio/jobs/'+job_id
			deadline=time.monotonic()+6
			while time.monotonic()<deadline:
				status, _, snapshot=self.request('GET',path)
				if snapshot['status'] in ('awaiting_review','failed'): break
				time.sleep(.01)
			self.assertEqual(snapshot['status'],'awaiting_review',snapshot)
			self.assertEqual(snapshot['usage']['total_tokens'],300)
			self.assertEqual(snapshot['capability_id'],'video.paper_preview.v1')
			status, _, review=self.request('GET',path+'/review')
			self.assertEqual(status,200)
			conn=http.client.HTTPConnection('127.0.0.1',self.port)
			conn.request('GET',review['slides'][0]['preview_url'])
			response=conn.getresponse()
			self.assertEqual(response.status,200)
			self.assertTrue(response.read().startswith(b'\x89PNG'))
			conn.close()
			review['segments'][0]['text']='先觀察水變成水氣，讓我們理解受熱的影響。'
			status, _, result=self.request('POST',path+'/review',json.dumps({'segments':review['segments']}).encode(),headers)
			self.assertTrue(result['ok'])
			deadline=time.monotonic()+6
			while time.monotonic()<deadline:
				status, _, snapshot=self.request('GET',path)
				if snapshot['status'] in ('done','failed'): break
				time.sleep(.01)
			self.assertEqual(snapshot['status'],'done',snapshot)
			artifact=snapshot['artifacts'][0]
			self.assertEqual(artifact['capability_id'],'video.paper_preview.v1')
			conn=http.client.HTTPConnection('127.0.0.1',self.port)
			conn.request('GET',artifact['download']['url'],headers={'Range':'bytes=0-6'})
			response=conn.getresponse()
			self.assertEqual(response.status,206)
			self.assertEqual(response.read(),b'offline')
			conn.close()
			self.assertEqual(facade.job.board['scenes'][0]['steps'][0]['speech'],review['segments'][0]['text'])

	def test_test_page_catalog_and_plan_are_separate(self):
		status, _, data = self.request('GET','/api/studio/catalog')
		self.assertEqual(len(data['capabilities']),8)
		status, _, data = self.request('GET','/api/studio/catalog?experiments=paper')
		self.assertEqual(status,200)
		self.assertIn('video.paper_preview.v1',[item['id'] for item in data['capabilities']])
		self.assertEqual(self.request('GET','/api/studio/catalog?experiments=unknown')[0],400)
		source=self.store.add_upload('water.txt','水受熱後蒸發成水氣。'.encode())
		body=json.dumps({'contract_version':'1.0','instruction':'看懂水循環，做60秒影片',
			'source':{key:source[key] for key in ('kind','ref','revision')}}).encode()
		headers={'X-Studio-CSRF':self.session(),'Content-Type':'application/json'}
		status, _, data=self.request('POST','/api/studio/plans?mode=paper-test',body,headers)
		self.assertEqual(status,201)
		self.assertEqual(data['plan']['steps'][0]['capability_id'],'video.paper_preview.v1')
		with patch.object(serve,'tts_ready',return_value=True), patch.object(serve,'PaperVideoJob') as factory:
			status, _, error=self.request('POST','/api/studio/jobs',json.dumps({'plan_id':data['plan_id'],'visual_style':'paper'}).encode(),headers)
			self.assertEqual(status,400)
			factory.assert_not_called()

	def test_duration_range_http_is_saved_and_rule_rejects_it(self):
		source=self.store.add_upload('range.txt','教材測試'.encode())
		headers={'X-Studio-CSRF':self.session(),'Content-Type':'application/json'}
		payload={'contract_version':'1.0','instruction':'重點講清楚','duration_range':{'min_seconds':180,'max_seconds':300},
			'source':{key:source[key] for key in ('kind','ref','revision')}}
		status,_,data=self.request('POST','/api/studio/plans?mode=paper-test',json.dumps(payload).encode(),headers)
		self.assertEqual(status,201)
		self.assertEqual(data['plan']['steps'][0]['options']['duration_range'],payload['duration_range'])
		self.assertEqual(self.request('POST','/api/studio/plans?mode=rule',json.dumps(payload).encode(),headers)[0],400)
		payload['duration_range']={'min_seconds':300,'max_seconds':180}
		self.assertEqual(self.request('POST','/api/studio/plans?mode=paper-test',json.dumps(payload).encode(),headers)[0],400)
