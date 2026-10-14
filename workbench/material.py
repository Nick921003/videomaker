"""共用教材契約；文字來源保持原樣，定位以原文行號為準。"""
import hashlib


SCHEMA_VERSION = 1


def plaintext_material(markdown: str, kind: str) -> dict:
	if kind not in ('md', 'txt'):
		raise ValueError('文字契約只接受 md 或 txt 原文')
	version = hashlib.sha256(markdown.encode('utf-8')).hexdigest()
	return {
		'schema_version': SCHEMA_VERSION,
		'content_version': version,
		'sources': [{
			'id': version, 'sha256': version, 'kind': kind,
			'path': 'material.md',
		}],
		'sections': [{
			'id': 'text-1', 'source_id': version,
			'locator': {'line_start': 1, 'line_end': max(1, len(markdown.splitlines()))},
			'text': markdown,
		}],
		'review': {'required': False, 'uncertainties': []},
	}


def attach_source(library, uid, raw_path, kind, extracted, pages):
	"""同正文多來源合併；原檔獨立保存，頁資料已由整理器核對。"""
	from pathlib import Path
	from workbench.source_document import KINDS, source_blocks
	if kind not in KINDS:
		raise ValueError("來源格式不支援")
	from workbench.library import read_json, write_json
	payload = Path(raw_path).read_bytes()
	digest = hashlib.sha256(payload).hexdigest()
	markdown = library.path(uid, 'material.md').read_bytes().decode('utf-8')
	version = hashlib.sha256(markdown.encode('utf-8')).hexdigest()
	data = read_json(library.path(uid, 'material.json')) or {
		'schema_version': SCHEMA_VERSION, 'content_version': version,
		'sources': [], 'sections': [], 'review': {'required': False, 'uncertainties': []},
	}
	if data['content_version'] != version:
		raise ValueError('教材正文版本與共同資料不一致')
	if any(source['id'] == digest for source in data['sources']):
		return data
	filename = Path(raw_path).name
	relative = f'sources/{digest}/original.{kind}'
	original = library.path(uid, relative)
	original.parent.mkdir(parents=True, exist_ok=True)
	original.write_bytes(payload)
	extracted_path = f'sources/{digest}/extracted.md'
	library.path(uid, extracted_path).write_text(extracted, encoding='utf-8')
	blocks = source_blocks(extracted, kind)
	for index, block in enumerate(blocks, 1):
		block['id'] = f'{digest}-b{index}'
	data.pop('derived_from_legacy', None)
	data['sources'].append({'id': digest, 'sha256': digest, 'kind': kind,
		'name': filename, 'path': relative, 'extracted_path': extracted_path,
		'blocks': blocks})
	for page in pages:
		section = dict(page)
		locator_key = 'page' if kind == 'pdf' else 'slide' if kind == 'pptx' else None
		section['source_block_ids'] = [block['id'] for block in blocks
			if locator_key is None or block['locator'].get(locator_key) == page['page']]
		section.update(id=f'{digest}-{page["page"]}', source_id=digest, locator={('page' if kind == 'pdf' else 'slide' if kind == 'pptx' else 'extracted_part'): page['page']})
		data['sections'].append(section)
		doubts = page['uncertainties']
		data['review']['uncertainties'].extend(doubts)
		data['review']['required'] = data['review']['required'] or bool(doubts)
	write_json(library.path(uid, 'material.json'), data)
	return data


def read_material(directory):
	"""驗證共同契約與原檔；舊資料只讀 fallback，不推測原始來源。"""
	from pathlib import Path, PurePosixPath
	import re
	from workbench.library import read_json, safe_path
	directory = Path(directory)
	markdown = safe_path(directory, 'material.md').read_bytes().decode('utf-8')
	data = read_json(safe_path(directory, 'material.json'))
	if data is None:
		data = plaintext_material(markdown, 'md')
		data['derived_from_legacy'] = True
		data['sources'][0]['kind'] = 'normalized_markdown'
		return markdown, data
	if (not isinstance(data, dict) or type(data.get('schema_version')) is not int
		or data['schema_version'] != SCHEMA_VERSION
		or data.get('content_version') != hashlib.sha256(markdown.encode('utf-8')).hexdigest()):
		raise ValueError('教材正文版本或共同資料契約不一致')
	sources, sections, review = (data.get(key) for key in ('sources', 'sections', 'review'))
	if (not isinstance(sources, list) or not sources or not isinstance(sections, list) or not sections
		or not isinstance(review, dict) or type(review.get('required')) is not bool):
		raise ValueError('共同教材資料缺少來源或核對狀態')
	identifiers = set()
	for source in sources:
		if not isinstance(source, dict) or not re.fullmatch('[a-f0-9]{64}', str(source.get('id', ''))):
			raise ValueError('來源識別碼不正確')
		if source['id'] in identifiers or source.get('sha256') != source['id']:
			raise ValueError('來源識別碼重複或雜湊不一致')
		identifiers.add(source['id'])
		for key in ('path', 'extracted_path'):
			if key not in source and key == 'extracted_path':
				continue
			path = source.get(key)
			if (not isinstance(path, str) or not path or '\\' in path
				or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts):
				raise ValueError('來源路徑不正確')
			resolved = safe_path(directory, path)
			if not resolved.is_file() or resolved.stat().st_size > 5 * 1024 * 1024:
				raise ValueError('來源檔案缺失或超出限制')
			if key == 'path' and hashlib.sha256(resolved.read_bytes()).hexdigest() != source['id']:
				raise ValueError('來源原檔與保存版本不一致')
	for section in sections:
		if (not isinstance(section, dict) or section.get('source_id') not in identifiers
			or not isinstance(section.get('locator'), dict)):
			raise ValueError('教材節點來源或定位不正確')
	return markdown, data


def review_confirmed(data):
	review = data.get('review', {})
	return (review.get('required') is False
		and review.get('reviewed_content_version') == data.get('content_version')
		and review.get('reviewed_source_ids') == sorted(source['id'] for source in data['sources']))


def confirm_review(library, uid, content_version):
	from datetime import datetime, timezone
	from workbench.library import write_json
	data = library.material(uid)
	if content_version != data['content_version']:
		raise ValueError('核對版本已改變，請重新讀取教材')
	data['review'].update(required=False, reviewed_content_version=content_version,
		reviewed_source_ids=sorted(source['id'] for source in data['sources']),
		reviewed_at=datetime.now(timezone.utc).isoformat(timespec='seconds'), reviewed_by='user')
	write_json(library.path(uid, 'material.json'), data)
	return data


def generation_material(directory):
	from workbench.library import read_json, safe_path
	markdown, data = read_material(directory)
	confirmed = review_confirmed(data)
	review = read_json(safe_path(directory, 'normalization.json'), {})
	if (data['review']['required'] or
		(not confirmed and (data['review'].get('reviewed_content_version')
			or (isinstance(review, dict) and review.get('requires_review'))
			or '\n待核對：\n' in markdown))):
		raise ValueError('教材內容需要先對照原檔核對')
	return markdown, data


def source_context(data):
	"""僅供定位，引用正文仍是 material.md；不混入另一份可引用文字。"""
	if data.get('derived_from_legacy'):
		return None
	return {'content_version': data['content_version'],
		'sources': [{'id': source['id'], 'kind': source['kind']} for source in data['sources']],
		'sections': [{'source_id': section['source_id'], 'locator': section['locator']} for section in data['sections']]}


def provenance(data):
	return {'schema_version': SCHEMA_VERSION, 'content_version': data['content_version'],
		'source_ids': [source['id'] for source in data['sources']],
		'derived_from_legacy': bool(data.get('derived_from_legacy')),
		'review_confirmed': review_confirmed(data)}


def validate_provenance(record, data):
	if (not isinstance(record, dict) or record.get('schema_version') != SCHEMA_VERSION
		or record.get('content_version') != data['content_version']
		or not isinstance(record.get('source_ids'), list)
		or not set(record['source_ids']) <= {source['id'] for source in data['sources']}):
		raise ValueError('成品來源紀錄與教材版本不一致')


def composite_provenance(directory, story_ids):
	from workbench.library import read_json, safe_path
	_, data = generation_material(directory)
	result = provenance(data)
	missing, used = [], set()
	for story in story_ids:
		record = read_json(safe_path(directory, f'{story}.scene.source.json'))
		if record is None:
			missing.append(story)
		else:
			validate_provenance(record, data)
			used.update(record['source_ids'])
	result.update(source_ids=sorted(used), legacy_components=missing,
		requested_content_version=data['content_version'], components=list(story_ids))
	if missing:
		result['content_version'] = None
	return result
