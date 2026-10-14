"""重點清單的快取、鎖與待確認狀態；同教材版本與同一次重抽要求只抽取一次。"""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import uuid

from studio.key_points import SYSTEM, KeyPointsError, build_key_points, canonical_key_points
from workbench.artifacts import publish
from workbench.library import read_json, safe_path, write_json
from workbench.material import generation_material, provenance, source_context


class KeyPointsPending(ValueError):
	"""推論出的重點清單尚未確認，不得製作成品。"""


def _digest(value):
	return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _request(directory):
	value = read_json(safe_path(directory, 'key_points.request.json'), {})
	if not isinstance(value, dict):
		return {'note': None, 'nonce': None}
	note = value.get('note')
	return {'note': note if isinstance(note, str) and note.strip() else None,
		'nonce': value.get('nonce') if isinstance(value.get('nonce'), str) else None}


def _sources(data):
	# 來源種類決定結構是教材寫的還是推論的；正文相同但來源變了也要重抽。
	return sorted([source['id'], source['kind']] for source in data['sources'])


def _cache_key(data, configuration, request):
	return hashlib.sha256(json.dumps({'content_version': data['content_version'], 'sources': _sources(data),
		'configuration': configuration, 'system': SYSTEM, 'request': request},
		sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _publish(directory, value, meta):
	meta = {key: item for key, item in meta.items() if key != 'digest'}
	publish(directory, {'key_points.json': json.dumps(value, ensure_ascii=False, allow_nan=False).encode(),
		'key_points.source.json': json.dumps({**meta, 'digest': _digest(value)}, ensure_ascii=False).encode()})


def current(directory):
	"""只回傳仍對應目前教材、目前重抽要求且未被竄改的清單。"""
	directory = Path(directory)
	material, data = generation_material(directory)
	value = read_json(safe_path(directory, 'key_points.json'))
	meta = read_json(safe_path(directory, 'key_points.source.json'), {})
	if (not isinstance(value, dict) or not isinstance(meta, dict) or meta.get('digest') != _digest(value)
		or meta.get('request') != _request(directory) or meta.get('sources') != _sources(data)
		or value.get('content_version') != data['content_version']):
		return None
	return canonical_key_points(value, material)


def digest_of(value):
	return _digest(value)


def product_is_current(directory, relative):
	"""成品必須來自目前這份重點清單；重抽、改版或換來源後，舊成品不算完成。"""
	try:
		value = current(directory)
		record = read_json(safe_path(Path(directory), relative), {})
	except (ValueError, OSError):
		return False
	return (value is not None and value['status'] == 'ready' and isinstance(record, dict)
		and record.get('key_points_digest') == _digest(value))


def get_key_points(directory, complete_json, *, configuration='default', require_ready=True):
	directory = Path(directory)
	generation_material(directory)
	with safe_path(directory, '.key_points.lock').open('a') as lock:
		fcntl.flock(lock, fcntl.LOCK_EX)
		material, data = generation_material(directory)
		request = _request(directory)
		key = _cache_key(data, configuration, request)
		meta = read_json(safe_path(directory, 'key_points.source.json'), {})
		cached = read_json(safe_path(directory, 'key_points.json'))
		if isinstance(meta, dict) and meta.get('cache_key') == key and cached is not None:
			if meta.get('digest') != _digest(cached):
				raise KeyPointsError(['重點清單快取身份不一致'])
			value = canonical_key_points(cached, material)
		else:
			def rejected(candidate, found):
				try:
					write_json(safe_path(directory, f'key_points_attempts/{uuid.uuid4().hex}.json'),
						{'candidate': candidate, 'problems': found,
							'content_version': data['content_version'], 'configuration': configuration})
				except (OSError, TypeError, ValueError):
					pass  # 診斷寫入失敗不得蓋過原本的抽取結果。
			value = build_key_points(material, complete_json,
				source_kinds=[source['kind'] for source in data['sources']],
				source_context=source_context(data), note=request['note'], on_rejected=rejected)
			_, latest = generation_material(directory)
			if latest['content_version'] != data['content_version']:
				raise KeyPointsError(['抽取期間教材版本已改變'])
			_publish(directory, value, {**provenance(data), 'cache_key': key, 'request': request,
				'sources': _sources(data)})
	if require_ready and value['status'] != 'ready':
		raise KeyPointsPending('重點清單是 AI 推論的，請先在單元頁確認')
	return value


def confirm(directory, digest):
	"""綁定畫面上看到的那一份清單（digest），不是教材版本；重抽後舊畫面不能批准新清單。"""
	directory = Path(directory)
	with safe_path(directory, '.key_points.lock').open('a') as lock:
		fcntl.flock(lock, fcntl.LOCK_EX)
		value = current(directory)
		if value is None or _digest(value) != digest:
			raise ValueError('重點清單已改變，請重新讀取')
		if value['status'] != 'ready':
			value['status'] = 'ready'
			meta = read_json(safe_path(directory, 'key_points.source.json'), {})
			_publish(directory, value, {**meta, 'confirmed_at': datetime.now(timezone.utc).isoformat(timespec='seconds')})
		return value


def request_reextract(directory, note):
	if not isinstance(note, str) or len(note.strip()) > 200:
		raise ValueError('修正意見最多 200 字')
	# nonce 讓沒有附意見的重抽也能讓快取失效。
	write_json(safe_path(Path(directory), 'key_points.request.json'),
		{'note': note.strip() or None, 'nonce': uuid.uuid4().hex,
			'requested_at': datetime.now(timezone.utc).isoformat(timespec='seconds')})


def summary(directory):
	try:
		value = current(directory)
	except (ValueError, OSError):
		value = None
	if value is None:
		return {'status': 'missing', 'structure': None, 'content_version': None, 'digest': None, 'key_points': None}
	return {'status': value['status'], 'structure': value['structure'],
		'content_version': value['content_version'], 'digest': _digest(value), 'key_points': value}
