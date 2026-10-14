import contextlib
import io
from pathlib import Path
import zipfile

from PIL import Image

import unittest
from tests import test_workbench_server as fixtures
from workbench.run_normalize import main


def zipped(files):
	output = io.BytesIO()
	with zipfile.ZipFile(output, 'w') as archive:
		for name, data in files.items():
			archive.writestr(name, data)
	return output.getvalue()


class NormalizeRunner(fixtures.FakeRunner):
	def __call__(self, command, log):
		if Path(command[1]).name != 'run_normalize.py':
			return super().__call__(command, log)
		self.commands.append(command)
		def complete(system, request, pdf_bytes):
			raw = request.split('逐頁抽取原文：\n', 1)[1]
			return {'title': '共用教材', 'pages': [{'page': 1, 'clean_text': raw,
				'verified_quotes': [raw] if pdf_bytes is None else [],
				'visual_notes': ['測試圖片'] if pdf_bytes else [], 'uncertainties': []}]}, {}
		output = io.StringIO()
		with contextlib.redirect_stdout(output):
			status = main(command[2:], complete)
		for line in output.getvalue().splitlines():
			log(line)
		return status


class TestMultiFormatIngestion(unittest.TestCase):
	setUp = fixtures.TestStudio.setUp
	stop_http = fixtures.TestStudio.stop_http
	request = fixtures.TestStudio.request
	api = fixtures.TestStudio.api
	upload = fixtures.TestStudio.upload
	wait_job = fixtures.TestStudio.wait_job
	def test_upload_confirm_normalize_source_roundtrip(self):
		runner = NormalizeRunner()
		self.studio.job_queue.runner = runner
		image = io.BytesIO()
		Image.new('RGB', (16, 8), 'white').save(image, format='PNG')
		docx = zipped({'word/document.xml': '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>教材段落</w:t></w:r></w:p></w:body></w:document>'})
		xlsx = zipped({
			'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="教材" r:id="r1"/></sheets></workbook>',
			'xl/_rels/workbook.xml.rels': '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
			'xl/worksheets/sheet1.xml': '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="B2" t="inlineStr"><is><t>001</t></is></c></row></sheetData></worksheet>',
		})
		for name, payload in (('lesson.docx', docx), ('lesson.xlsx', xlsx), ('lesson.csv', '名,值\n甲,001'.encode()), ('lesson.txt', '文字原文\r\n001'.encode()), ('lesson.md', '# 原稿\n001'.encode()), ('lesson.png', image.getvalue())):
			with self.subTest(name=name):
				before = len(runner.commands)
				upload = self.upload(filename=name, data=payload)
				self.assertEqual(len(runner.commands), before)
				job = self.api('POST', f'/api/v1/uploads/{upload["upload_id"]}/normalize')['job_id']
				completed = self.wait_job(job)
				self.assertEqual(completed['state'], 'done', completed)
				uid = completed['unit_id']
				data = self.api('GET', f'/api/v1/units/{uid}/material')
				self.assertEqual(data['sources'][0]['kind'], Path(name).suffix[1:])
				self.assertTrue(data['sources'][0]['blocks'])
				self.assertTrue(data['sections'])
				block_ids = {block['id'] for source in data['sources'] for block in source['blocks']}
				self.assertTrue(set(data['sections'][0]['source_block_ids']) <= block_ids)
				self.assertNotEqual(data['sources'][0]['path'], 'material.md')
				if name.endswith('.xlsx'):
					self.assertIn('001', data['sections'][0]['clean_text'])
				status, _, original = self.request('GET', f'/media/{uid}/{data["sources"][0]["path"]}')
				self.assertEqual((status, original), (200, payload))
