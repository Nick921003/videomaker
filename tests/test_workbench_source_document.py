from pathlib import Path
import tempfile
import unittest
import zipfile

from workbench.source_document import extract_document


class TestSourceDocument(unittest.TestCase):
	def setUp(self):
		self.temp = tempfile.TemporaryDirectory()
		self.addCleanup(self.temp.cleanup)
		self.root = Path(self.temp.name)

	def archive(self, name, files):
		path = self.root / name
		with zipfile.ZipFile(path, 'w') as archive:
			for key, value in files.items():
				archive.writestr(key, value)
		return path

	def test_csv_preserves_empty_cells_and_numeric_strings(self):
		path = self.root / 'data.csv'
		path.write_text('名稱,數字,空白\n甲,001,\n乙,"a,b",0\n', encoding='utf-8')
		text = extract_document(path)
		self.assertIn("列 2：['甲', '001', '']", text)
		self.assertIn("列 3：['乙', 'a,b', '0']", text)

	def test_docx_retains_body_order_table_and_visual_review(self):
		path = self.archive('lesson.docx', {'word/document.xml': '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>先讀</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>001</w:t></w:r></w:p></w:tc><w:tc/></w:tr></w:tbl><w:p><w:r><w:t>後讀</w:t><w:drawing/></w:r></w:p></w:body></w:document>'''})
		text = extract_document(path)
		self.assertLess(text.index('先讀'), text.index("['001', '']"))
		self.assertLess(text.index("['001', '']"), text.index('後讀'))
		self.assertIn('待核對', text)

	def test_xlsx_follows_workbook_order_and_preserves_formula_cache(self):
		path = self.archive('data.xlsx', {
			'xl/workbook.xml': '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="後表先讀" r:id="r1"/><sheet name="另一表" r:id="r2"/></sheets></workbook>',
			'xl/_rels/workbook.xml.rels': '<Relationships><Relationship Id="r1" Target="worksheets/sheet2.xml"/><Relationship Id="r2" Target="worksheets/sheet1.xml"/></Relationships>',
			'xl/worksheets/sheet2.xml': '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>001</t></is></c><c r="B1"><f>1+2</f><v>3</v></c><c r="C1"/><c r="D1" t="s"/></row></sheetData></worksheet>',
			'xl/worksheets/sheet1.xml': '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1"><v>9</v></c></row></sheetData></worksheet>',
		})
		text = extract_document(path)
		self.assertLess(text.index('後表先讀'), text.index('另一表'))
		self.assertIn("A1：'001'", text)
		self.assertIn("C1：''", text)
		self.assertIn("D1：''", text)
		self.assertIn("公式='1+2'", text)
		self.assertIn('未重算', text)

	def test_rejects_xml_entities_binary_text_and_invalid_utf8(self):
		path = self.archive('bad.docx', {'word/document.xml': '<!DOCTYPE x [<!ENTITY x "bad">]><x/>'})
		with self.assertRaises(ValueError):
			extract_document(path)
		for payload in (b'abc\0def', b'\xff'):
			path = self.root / 'bad.txt'
			path.write_bytes(payload)
			with self.assertRaises(ValueError):
				extract_document(path)

	def test_images_are_verified_and_produce_visual_pdf(self):
		from PIL import Image
		from workbench.source_document import image_pdf
		path = self.root / 'poster.png'
		Image.new('RGBA', (20, 10), (0, 0, 0, 0)).save(path)
		self.assertIn('20 × 10', extract_document(path))
		self.assertTrue(image_pdf(path).startswith(b'%PDF-'))
		for extension in ('jpg', 'jpeg'):
			jpeg = self.root / ('photo.' + extension)
			Image.new('RGB', (20, 10), 'white').save(jpeg, format='JPEG')
			self.assertIn('20 × 10', extract_document(jpeg))
			self.assertTrue(image_pdf(jpeg).startswith(b'%PDF-'))
		path.write_bytes(b'not an image')
		with self.assertRaises(ValueError):
			extract_document(path)

	def test_source_locators_are_not_invented_pages(self):
		from workbench.source_document import source_blocks
		self.assertEqual(source_blocks('列 2：[1]', 'csv')[0]['locator']['row'], 2)
		self.assertEqual(source_blocks('段落 3：文字', 'docx')[0]['locator']['body_block'], 3)
		blocks = source_blocks('工作表：甲\nB7：001', 'xlsx')
		self.assertEqual(blocks[1]['locator'], {'extracted_line': 2, 'sheet': '甲', 'cell': 'B7'})
		self.assertEqual(source_blocks('## 第 4 頁\n文字', 'pptx')[1]['locator']['slide'], 4)

	def test_docx_controls_breaks_and_cell_paragraphs_preserve_separation(self):
		path = self.archive('control.docx', {'word/document.xml': '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:sdt><w:sdtContent><w:p><w:r><w:t>第一行</w:t><w:br/><w:t>第二行</w:t></w:r></w:p></w:sdtContent></w:sdt><w:tbl><w:tr><w:tc><w:p><w:r><w:t>項目</w:t></w:r></w:p><w:p><w:r><w:t>說明</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'})
		text = extract_document(path)
		self.assertIn('第一行\n第二行', text)
		self.assertIn("['項目\\n說明']", text)
