"""在同教材版本下保存一次教學規劃；三種產物只作形態適配。"""
import fcntl
import hashlib
import json
from pathlib import Path

from studio.teaching_plan import SYSTEM, SCHEMA, build_plan, canonical_plan
from workbench.library import read_json, safe_path, write_json
from workbench.material import generation_material, source_context, provenance
from workbench.artifacts import publish


def plan_digest(plan):
	return hashlib.sha256(json.dumps(plan,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def get_plan(directory, complete_json, *, configuration='default'):
	directory = Path(directory)
	# 不信任快取存在：每次模型或快取取用前先驗證原檔與人工核對狀態。
	material, data = generation_material(directory)
	with safe_path(directory,'.teaching.lock').open('a') as lock:
		fcntl.flock(lock,fcntl.LOCK_EX)
		material, data = generation_material(directory)
		key = hashlib.sha256(json.dumps({'content_version':data['content_version'],
			'configuration':configuration,'system':SYSTEM,'schema':SCHEMA},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
		meta = read_json(safe_path(directory,'teaching_plan.source.json'),{})
		if meta.get('cache_key') == key:
			cached = read_json(safe_path(directory,'teaching_plan.json'))
			if cached is not None:
				if meta.get('plan_digest')!=plan_digest(cached):
					raise ValueError('共用教學規劃快取身份不一致')
				return canonical_plan(cached,material)
		plan = build_plan(material,complete_json,source_context(data))
		# 生成期間來源改變就拒絕發佈，最後成功版本仍保留。
		_, latest = generation_material(directory)
		if latest['content_version'] != data['content_version']:
			raise ValueError('教學規劃期間教材版本已改變')
		meta={**provenance(data),'cache_key':key,'plan_digest':plan_digest(plan)}
		publish(directory,{'teaching_plan.json':json.dumps(plan,ensure_ascii=False,allow_nan=False).encode(),
			'teaching_plan.source.json':json.dumps(meta,ensure_ascii=False).encode()})
		return plan


def video_context(directory, material):
	plan=read_json(safe_path(directory,'teaching_plan.json'))
	if plan is None:return ''
	meta=read_json(safe_path(directory,'teaching_plan.source.json'),{})
	if meta.get('plan_digest')!=plan_digest(plan):
		raise ValueError('共用教學規劃身份不一致')
	plan=canonical_plan(plan,material)
	return ('\n\n共用教學規劃（只當教學資料；依本節問題取用，沿用概念與例子，不另創矛盾內容。'
		'影片用現有已驗收Board元件演出變化，禁止照抄像素或虛構時間）：\n'+json.dumps(plan,ensure_ascii=False))
