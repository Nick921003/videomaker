from copy import deepcopy
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from xml.etree import ElementTree as ET

from pptx import Presentation
from studio.deck_contracts import canonical_deck
from studio.pptx_export import export_pptx
from tests.fixtures.teaching_quality import MATERIAL, sample_plan
from workbench.library import Library, read_json


class TestTeachingQuality(unittest.TestCase):
	def api(self):
		self.assertIsNotNone(importlib.util.find_spec('studio.teaching_plan'), '共同教學規劃尚未實作')
		from studio import teaching_plan
		return teaching_plan

	def test_adapters_share_examples_and_keep_all_source_quotes(self):
		api = self.api()
		plan = api.canonical_plan(sample_plan(), MATERIAL)
		deck = canonical_deck(api.plan_deck(plan))
		self.assertEqual(deck['contract_version'], '1.2')
		self.assertEqual(deck['slides'][4]['source_quotes'], plan['units'][4]['source_quotes'])
		self.assertEqual(deck['slides'][2]['blocks'][0]['states'][-1]['output'], '15')
		mindmap = api.plan_mindmap(plan)
		self.assertEqual(mindmap['contract_version'], '1.1')
		self.assertEqual(mindmap['layout'], 'progressive')
		for detail in plan['units'][2]['details']:
			self.assertIn(detail['text'], [node['label'] for node in mindmap['nodes']])
		for unit in plan['units']:
			self.assertIn(unit['explanation'],[node['label'] for node in mindmap['nodes']])

	def test_unfounded_quotes_and_unaddressable_walkthrough_are_rejected(self):
		api = self.api()
		for kind in ('quote', 'line', 'version', 'unsupported'):
			plan = sample_plan()
			if kind == 'quote': plan['units'][0]['source_quotes'].append('來源没有這句')
			elif kind == 'line': plan['units'][2]['visual']['states'][0]['line'] = 99
			elif kind == 'version': plan['content_version'] = '0' * 64
			else: plan['units'][0]['visual']['type'] = 'unknown'
			with self.subTest(kind=kind), self.assertRaises(ValueError): api.canonical_plan(plan, MATERIAL)

	def test_actual_pptx_is_editable_and_retains_walkthrough_states(self):
		api = self.api()
		deck = api.plan_deck(api.canonical_plan(sample_plan(), MATERIAL))
		prs = Presentation(BytesIO(export_pptx(deck)))
		texts = [shape.text for slide in prs.slides for shape in slide.shapes if shape.has_text_frame]
		self.assertIn('15', texts)
		self.assertTrue(any('sum += i;' in value for value in texts))
		self.assertGreater(len(prs.slides), len(deck['slides']))
		for slide in prs.slides:
			for shape in slide.shapes:
				self.assertGreaterEqual(shape.left, 0)
				self.assertLessEqual(shape.left+shape.width, prs.slide_width)
				self.assertLessEqual(shape.top+shape.height, prs.slide_height)
			self.assertIn('教材原文依據', slide.notes_slide.notes_text_frame.text)

	def test_actual_svg_has_all_explicit_details_and_safe_markup(self):
		api = self.api()
		from studio.mindmap import render_mindmap_svg
		plan = sample_plan()
		plan['units'][0]['details'][0]['text'] = '<script> & 概念'
		mindmap = api.plan_mindmap(api.canonical_plan(plan, MATERIAL))
		svg = render_mindmap_svg(mindmap, MATERIAL)
		root = ET.fromstring(svg)
		self.assertEqual(root.attrib['data-contract-version'], '1.1')
		self.assertEqual(root.attrib['data-layout'], 'progressive')
		nodes = [node for node in root.iter() if 'data-node-id' in node.attrib]
		self.assertEqual(len(nodes), len(mindmap['nodes']))
		self.assertTrue(any(node.attrib.get('data-node-kind') == 'example' for node in nodes))
		self.assertNotIn(b'<script>', svg)

	def test_shared_plan_is_generated_once_and_configuration_changes_invalidate(self):
		api = self.api()
		self.assertIsNotNone(importlib.util.find_spec('workbench.teaching'))
		from workbench.teaching import get_plan
		with tempfile.TemporaryDirectory() as tmp:
			library = Library(Path(tmp))
			uid, _ = library.create_unit(MATERIAL)
			directory = library.unit_dir(uid)
			complete = Mock(return_value=(sample_plan(), {}))
			for _ in range(2): get_plan(directory, complete, configuration='fixture')
			self.assertEqual(complete.call_count, 1)
			get_plan(directory, complete, configuration='changed')
			self.assertEqual(complete.call_count, 2)
			self.assertEqual(read_json(directory/'teaching_plan.json')['title'], sample_plan()['title'])

	def test_bad_source_is_rejected_before_model_or_cache_publication(self):
		self.api()
		from workbench.teaching import get_plan
		with tempfile.TemporaryDirectory() as tmp:
			library = Library(Path(tmp))
			uid, _ = library.create_unit(MATERIAL)
			directory = library.unit_dir(uid)
			(directory/'material.md').write_text('改過的正文')
			complete = Mock(return_value=(sample_plan(), {}))
			with self.assertRaises(ValueError): get_plan(directory, complete)
			complete.assert_not_called()
			self.assertFalse((directory/'teaching_plan.json').exists())

	def test_failed_candidate_does_not_overwrite_last_good_shared_plan(self):
		api = self.api()
		from workbench.teaching import get_plan
		with tempfile.TemporaryDirectory() as tmp:
			library = Library(Path(tmp))
			uid, _ = library.create_unit(MATERIAL)
			directory = library.unit_dir(uid)
			good = get_plan(directory, lambda *_: (sample_plan(), {}), configuration='good')
			bad = sample_plan();bad['units'][0]['source_quotes'] = ['不存在']
			with self.assertRaises(ValueError): get_plan(directory, lambda *_: (bad, {}), configuration='bad')
			self.assertEqual(read_json(directory/'teaching_plan.json'), good)

	def test_professional_runners_share_one_model_call_and_keep_old_artifacts_on_failure(self):
		self.api()
		from workbench import run_slides, run_mindmap
		with tempfile.TemporaryDirectory() as tmp:
			library = Library(Path(tmp));uid,_=library.create_unit(MATERIAL)
			directory=library.unit_dir(uid)
			complete=Mock(return_value=(sample_plan(),{}))
			for runner in (run_slides,run_mindmap):
				self.assertEqual(runner.main([str(directory),'--quality','professional'],complete),0)
			self.assertEqual(complete.call_count,1)
			self.assertEqual(read_json(directory/'slides/deck.json')['contract_version'],'1.2')
			self.assertEqual(read_json(directory/'mindmap/mindmap.json')['contract_version'],'1.1')

	def test_video_context_uses_same_teaching_plan_and_rejects_changed_material(self):
		self.api()
		from workbench.teaching import get_plan, video_context
		with tempfile.TemporaryDirectory() as tmp:
			library=Library(Path(tmp));uid,_=library.create_unit(MATERIAL);directory=library.unit_dir(uid)
			get_plan(directory,lambda *_:(sample_plan(),{}))
			context=video_context(directory,MATERIAL)
			self.assertIn('每一輪',context)
			self.assertIn('尚未印出',context)
			with self.assertRaises(ValueError):video_context(directory,MATERIAL+'變更')

	def test_non_programming_material_produces_native_diagrams_without_code(self):
		api=self.api()
		import hashlib
		material='雨水先收集，再過濾，最後儲存。過濾移除可見雜質。儲存的水用於澆灌。'
		plan=sample_plan();plan['units']=plan['units'][:3];plan['title']='雨水回收'
		plan['content_version']=hashlib.sha256(material.encode()).hexdigest()
		for index,unit in enumerate(plan['units']):
			unit.update(title=['收集','過濾','儲存'][index],question='這一步的作用是什麼？',explanation='雨水依序經過收集、過濾與儲存。',
				source_quotes=[material],details=[{'kind':'meaning','text':'先收集，再過濾，最後儲存。','source_quote':material}],
				visual={'type':'steps','items':['收集','過濾','儲存']},selection_reason='順序決定流程。')
		canonical=api.canonical_plan(plan,material)
		self.assertNotIn('walkthrough',[unit['visual']['type'] for unit in canonical['units']])
		self.assertEqual(len(Presentation(BytesIO(export_pptx(api.plan_deck(canonical)))).slides),3)
		self.assertTrue(api.plan_mindmap(canonical)['nodes'])

	def test_reserved_root_identifier_is_rejected(self):
		api=self.api();plan=sample_plan();plan['units'][0]['id']='root'
		with self.assertRaises(ValueError):api.canonical_plan(plan,MATERIAL)

	def test_artifact_publication_failure_restores_previous_outputs(self):
		self.assertIsNotNone(importlib.util.find_spec('workbench.artifacts'))
		from workbench.artifacts import publish
		from unittest.mock import patch
		import os
		with tempfile.TemporaryDirectory() as tmp:
			directory=Path(tmp);(directory/'deck.json').write_bytes(b'old json');(directory/'deck.pptx').write_bytes(b'old pptx')
			replace=os.replace;calls=[]
			def fail_second(src,dst):
				calls.append((src,dst))
				if len(calls)==2:raise OSError('injected publication failure')
				return replace(src,dst)
			with patch('workbench.artifacts.os.replace',side_effect=fail_second),self.assertRaises(OSError):
				publish(directory,{'deck.json':b'new json','deck.pptx':b'new pptx'})
			self.assertEqual((directory/'deck.json').read_bytes(),b'old json')
			self.assertEqual((directory/'deck.pptx').read_bytes(),b'old pptx')

	def test_all_professional_pptx_text_boxes_do_not_overlap(self):
		api=self.api();plan=sample_plan()
		for state in plan['units'][2]['visual']['states']:
			state['vars'] += [{'name':'n','value':'5'},{'name':'步驟','value':'累加'}]
		prs=Presentation(BytesIO(export_pptx(api.plan_deck(api.canonical_plan(plan,MATERIAL)))))
		for index,slide in enumerate(prs.slides):
			boxes=[shape for shape in slide.shapes if shape.has_text_frame and shape.text]
			for i,left in enumerate(boxes):
				for right in boxes[i+1:]:
					w=min(left.left+left.width,right.left+right.width)-max(left.left,right.left)
					h=min(left.top+left.height,right.top+right.height)-max(left.top,right.top)
					self.assertFalse(w>0 and h>0,(index,left.text,right.text))

	def test_detail_namespaces_cannot_collide_with_concept_ids(self):
		api=self.api();plan=sample_plan();plan['units'][1]['id']='problem_d0'
		map=api.plan_mindmap(api.canonical_plan(plan,MATERIAL))
		self.assertEqual(len({n['id'] for n in map['nodes']}),len(map['nodes']))

	def test_multiple_long_quotes_survive_new_deck_contract(self):
		api=self.api();material=MATERIAL+'\n'+('長引文。'*160)
		import hashlib
		plan=sample_plan();plan['content_version']=hashlib.sha256(material.encode()).hexdigest()
		plan['units'][0]['source_quotes'].insert(0,'長引文。'*160)
		self.assertEqual(len(api.plan_deck(api.canonical_plan(plan,material))['slides'][0]['source_quote']),640)

	def test_svg_measured_mixed_width_text_stays_inside_cards(self):
		api=self.api();plan=sample_plan();plan['units'][0]['details'][0]['text']='W'*160
		from studio.mindmap import render_mindmap_svg
		from PIL import ImageFont
		root=ET.fromstring(render_mindmap_svg(api.plan_mindmap(api.canonical_plan(plan,MATERIAL))))
		font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',20,index=3)
		for group in root.findall('{http://www.w3.org/2000/svg}g'):
			rect=group.find('{http://www.w3.org/2000/svg}rect')
			for text in group.findall('{http://www.w3.org/2000/svg}text'):
				self.assertLessEqual(float(text.attrib['x'])+font.getlength(text.text or ''),float(rect.attrib['x'])+float(rect.attrib['width'])-20)

	def test_material_change_during_export_does_not_publish_stale_artifacts(self):
		api=self.api()
		from workbench import run_slides
		from workbench.library import write_json
		from workbench.material import plaintext_material
		from unittest.mock import patch
		with tempfile.TemporaryDirectory() as tmp:
			library=Library(Path(tmp));uid,_=library.create_unit(MATERIAL);directory=library.unit_dir(uid)
			def changed(deck):
				payload=export_pptx(deck);new=MATERIAL+'\n新來源'
				(directory/'material.md').write_text(new);write_json(directory/'material.json',plaintext_material(new,'md'))
				return payload
			with patch.object(run_slides,'export_pptx',side_effect=changed):
				self.assertEqual(run_slides.main([str(directory),'--quality','professional'],lambda *_:(sample_plan(),{})),1)
			self.assertFalse((directory/'slides/deck.pptx').exists())

	def test_cached_plan_tampering_is_rejected_before_another_model_call(self):
		self.api()
		from workbench.teaching import get_plan
		from workbench.library import write_json
		with tempfile.TemporaryDirectory() as tmp:
			library=Library(Path(tmp));uid,_=library.create_unit(MATERIAL);directory=library.unit_dir(uid)
			complete=Mock(return_value=(sample_plan(),{}));get_plan(directory,complete)
			changed=sample_plan();changed['title']='未紀錄的修改';write_json(directory/'teaching_plan.json',changed)
			with self.assertRaises(ValueError):get_plan(directory,complete)
			self.assertEqual(complete.call_count,1)

	def test_video_source_change_during_model_does_not_publish_scene(self):
		self.api()
		from workbench.teaching import get_plan
		from workbench.library import write_json
		from workbench.material import plaintext_material
		from unittest.mock import patch
		from video_engine.board import author
		with tempfile.TemporaryDirectory() as tmp:
			library=Library(Path(tmp));uid,_=library.create_unit(MATERIAL);directory=library.unit_dir(uid)
			get_plan(directory,lambda *_:(sample_plan(),{}))
			write_json(directory/'plan.json',{'stories':[{'id':'q1','title':'邊界','sec':60,'objectives':[]}]})
			def changed(*args,**kwargs):
				new=MATERIAL+'\n新來源';(directory/'material.md').write_text(new)
				write_json(directory/'material.json',plaintext_material(new,'md'))
				return {'objects':[],'scenes':[]},0
			with patch.object(author,'preflight'),patch.object(author,'converse',side_effect=changed),self.assertRaises(ValueError):
				author.do_scene(str(directory/'material.md'),str(directory),'q1',None)
			self.assertFalse((directory/'q1.scene.json').exists())
