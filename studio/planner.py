"""將不可信規劃草稿轉成 server 保存的標準計畫。"""

from studio.catalog import capability_ids, public_catalog
from studio.contracts import ContractError, canonicalize_plan, generation_plan_schema, normalize_plan_request


def plan_request(payload, backend, store):
	request = normalize_plan_request(payload)
	draft = backend.plan(request, public_catalog(), generation_plan_schema(capability_ids()))
	if not isinstance(draft, dict) or draft.get("source") != request["source"]:
		raise ContractError("規劃結果的教材來源不一致")
	plan = canonicalize_plan(draft)
	return store.save_canonical(plan, instruction=request["instruction"])
