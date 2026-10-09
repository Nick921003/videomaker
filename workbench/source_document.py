"""有界的確定性文件抽取，不執行公式或外部連結。"""
import csv
import io
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET
import zipfile

from video_engine.ingest import extract_text

KINDS = ('pdf', 'pptx', 'md', 'txt', 'csv', 'docx', 'xlsx', 'png', 'jpg', 'jpeg')
MAX_XML = 8 * 1024 * 1024
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
	's': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
	'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def _xml(archive, name):
	data = archive.read(name)
	if len(data) > MAX_XML or b'<!DOCTYPE' in data.replace(b'\x00', b'').upper() or b'<!ENTITY' in data.replace(b'\x00', b'').upper():
		raise ValueError('文件 XML 超出限制或含不支援的實體')
	return ET.fromstring(data)


def _archive(path):
	archive = zipfile.ZipFile(path)
	members = archive.infolist()
	if (len(members) > 2000 or sum(m.file_size for m in members) > 50 * 1024 * 1024
		or len({m.filename for m in members}) != len(members)):
		archive.close()
		raise ValueError('文件解壓資料超過限制或包含重複項目')
	return archive


def _word_text(block):
	parts = []
	for element in block.iter():
		if element.tag == '{' + NS['w'] + '}t':
			parts.append(element.text or '')
		elif element.tag == '{' + NS['w'] + '}tab':
			parts.append('\t')
		elif element.tag in ('{' + NS['w'] + '}br', '{' + NS['w'] + '}cr'):
			parts.append('\n')
	return ''.join(parts)


def _word_blocks(body):
	for block in body:
		if block.tag == '{' + NS['w'] + '}sdt':
			content = block.find('w:sdtContent', NS)
			if content is not None:
				yield from _word_blocks(content)
		else:
			yield block


def _docx(archive):
	root = _xml(archive, 'word/document.xml')
	body = root.find('w:body', NS)
	if body is None:
		raise ValueError('DOCX 缺少本文')
	lines = []
	blocks = list(_word_blocks(body))
	for index, block in enumerate(blocks, 1):
		if block.tag == '{' + NS['w'] + '}p':
			text = _word_text(block)
			lines.append(f'段落 {index}：{text}')
		elif block.tag == '{' + NS['w'] + '}tbl':
			for row_index, row in enumerate(block.findall('w:tr', NS), 1):
				cells = ['\n'.join(_word_text(p) for p in cell.findall('w:p', NS)) for cell in row.findall('w:tc', NS)]
				lines.append(f'表格 {index} 列 {row_index}：' + repr(cells))
	if (root.findall('.//w:drawing', NS) or root.findall('.//w:object', NS)
		or any(e.tag.endswith('}oMath') for e in root.iter())
		or any(e.tag not in ('{' + NS['w'] + '}p', '{' + NS['w'] + '}tbl', '{' + NS['w'] + '}sectPr') for e in blocks)
		or any(name.startswith(('word/header', 'word/footer', 'word/footnotes', 'word/endnotes')) for name in archive.namelist())):
		lines.extend(['待核對：', '- 文件含圖片、公式或附加內容，請另附 PDF 核對。'])
	return '\n'.join(lines)


def _xlsx(archive):
	book = _xml(archive, 'xl/workbook.xml')
	rels = _xml(archive, 'xl/_rels/workbook.xml.rels')
	targets = {r.get('Id'): r.get('Target') for r in rels if r.get('TargetMode') != 'External'}
	strings = []
	if 'xl/sharedStrings.xml' in archive.namelist():
		strings = [''.join(e.text or '' for e in item.findall('.//s:t', NS))
			for item in _xml(archive, 'xl/sharedStrings.xml').findall('s:si', NS)]
	lines = []
	for sheet in book.findall('s:sheets/s:sheet', NS):
		target = targets.get(sheet.get('{' + NS['r'] + '}id'))
		if not target:
			raise ValueError('XLSX 工作表來源缺失或為外部連結')
		path = target.lstrip('/') if target.startswith('/') else str(PurePosixPath('xl') / target)
		if '..' in PurePosixPath(path).parts or '\\' in path:
			raise ValueError('XLSX 工作表路徑不正確')
		root = _xml(archive, path)
		lines.append('工作表：' + sheet.get('name', ''))
		lines.append('數值原樣保存；未解讀日期格式或重算公式。')
		for cell in root.findall('s:sheetData/s:row/s:c', NS):
			value = cell.findtext('s:v', default='', namespaces=NS)
			if cell.get('t') == 's' and value:
				index = int(value)
				if index < 0:
					raise ValueError('XLSX 字串索引不正確')
				value = strings[index]
			elif cell.get('t') == 'inlineStr':
				value = ''.join(e.text or '' for e in cell.findall('.//s:t', NS))
			formula = cell.findtext('s:f', namespaces=NS)
			line = f'{cell.get("r", "?")}：{value!r}'
			if cell.get('t') in ('b', 'e'):
				line += '；型別=' + ('布林' if cell.get('t') == 'b' else '公式錯誤')
			if formula is not None:
				line += f'；公式={formula!r}；以上為儲存快取，未重算'
			lines.append(line)
		if root.find('s:drawing', NS) is not None:
			lines.extend(['待核對：', '- 工作表含圖表或圖片，請另附 PDF 核對視覺內容。'])
	return '\n'.join(lines)


def extract_document(path):
	path = Path(path)
	kind = path.suffix.lower().lstrip('.')
	if kind not in KINDS:
		raise ValueError('教材格式不支援')
	if kind in ('png', 'jpg', 'jpeg'):
		with verified_image(path) as picture:
			return f'圖片：{picture.width} × {picture.height} 像素；內容請核對原圖。'
	if kind in ('pdf', 'pptx'):
		return extract_text(str(path))
	if kind in ('md', 'txt', 'csv'):
		text = path.read_text(encoding='utf-8-sig')
		if '\x00' in text:
			raise ValueError('文字檔包含二進位資料')
		if kind == 'csv':
			try:
				rows = csv.reader(io.StringIO(text), strict=True)
				text = '\n'.join(f'列 {index}：{row!r}' for index, row in enumerate(rows, 1))
			except csv.Error as exc:
				raise ValueError('CSV 格式不正確') from exc
	else:
		try:
			with _archive(path) as archive:
				text = _docx(archive) if kind == 'docx' else _xlsx(archive)
		except (KeyError, IndexError, ET.ParseError, zipfile.BadZipFile) as exc:
			raise ValueError('文件結構不正確，請重新匯出') from exc
	if not text.strip():
		raise ValueError('教材沒有可讀取的文字')
	if len(text) > 60000:
		raise ValueError('教材超過 6 萬字，請先拆分')
	return text


def verified_image(path):
	from PIL import Image, UnidentifiedImageError
	import warnings
	try:
		with warnings.catch_warnings():
			warnings.simplefilter('error', Image.DecompressionBombWarning)
			with Image.open(path) as picture:
				expected = 'PNG' if Path(path).suffix.lower() == '.png' else 'JPEG'
				if picture.format != expected or picture.width * picture.height > 20000000:
					raise ValueError('圖片格式不符或超過 2000 萬像素')
				picture.verify()
			picture = Image.open(path)
			picture.load()
			return picture
	except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
		raise ValueError('圖片無法讀取或尺寸超出限制') from exc


def image_pdf(path):
	from PIL import Image, ImageOps
	with verified_image(path) as picture:
		picture = ImageOps.exif_transpose(picture)
		if picture.mode == 'RGBA' or 'transparency' in picture.info:
			background = Image.new('RGB', picture.size, 'white')
			background.paste(picture.convert('RGBA'), mask=picture.convert('RGBA').getchannel('A'))
			picture = background
		else:
			picture = picture.convert('RGB')
		output = io.BytesIO()
		picture.save(output, format='PDF', resolution=150)
		return output.getvalue()


def source_blocks(extracted, kind):
	"""抽取稿定位；非分頁文件不推算原稿頁碼。"""
	import re
	blocks = []
	page, sheet = None, None
	for number, line in enumerate(extracted.splitlines(), 1):
		locator = {'extracted_line': number}
		if kind in ('pdf', 'pptx'):
			match = re.match(r'^## 第 (\d+) 頁', line)
			if match:
				page = int(match.group(1))
			if page is not None:
				locator = {('page' if kind == 'pdf' else 'slide'): page, 'extracted_line': number}
		elif kind == 'csv':
			match = re.match(r'^列 (\d+)：', line)
			if match:
				locator['row'] = int(match.group(1))
		elif kind == 'docx':
			match = re.match(r'^(段落|表格) (\d+)(?: 列 (\d+))?：', line)
			if match:
				locator['body_block'] = int(match.group(2))
				if match.group(3):
					locator['table_row'] = int(match.group(3))
		elif kind == 'xlsx':
			if line.startswith('工作表：'):
				sheet = line[len('工作表：'):]
			locator['sheet'] = sheet
			match = re.match(r'^([A-Z]+[0-9]+)：', line)
			if match:
				locator['cell'] = match.group(1)
		elif kind in ('png', 'jpg', 'jpeg'):
			locator = {'image': 1}
		else:
			locator = {'line': number}
		blocks.append({'text': line, 'locator': locator})
	return blocks
