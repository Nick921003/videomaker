#!/usr/bin/env python3
"""本機自我檢查：不呼叫任何 LLM，把測試分鏡庫、範例與歷來 AI 產出的分鏡全部編譯、建置、過量測閘。

用法：.venv/bin/python video_engine/board/selftest.py [--quick] [--force]

- fixtures/*.scene.json、examples/*.scene.json：必須完整通過量測閘。
- out/check_crashes/*.timeline.json：曾讓量測閘崩潰的時間軸，量測閘必須能跑完（版面問題可以有）。
- out/author_*/ 裡 AI 寫過的分鏡（--quick 略過）：同上，只要求不崩潰、沒有 JS 錯誤。
- 對照 catalog.json 列出測試分鏡庫還沒涵蓋的動作與選填參數（只提醒，不算失敗）。
通過後把 runtime／量測閘／目錄的雜湊記在 out/selftest.ok，沒改過就略過（--force 強制重跑）。
"""
import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build as BB
import compile as BC

OUT = os.path.join(HERE, "..", "out")
STAMP = os.path.join(OUT, "selftest.ok")
PLAYWRIGHT_PY = os.path.expanduser("~/.local/share/pipx/venvs/webwright/bin/python")
# 這些問題代表元件或 runtime 壞了，不是分鏡寫得不好
BROKEN = ("JS 錯誤", "頁面錯誤", "載入失敗", "座標無效", "已註冊元件")


def stamp():
	"""會影響畫面與量測結果的檔案雜湊；任何一個改了就要重跑。"""
	h = hashlib.sha256()
	files = sorted(glob.glob(os.path.join(HERE, "runtime", "**", "*.js"), recursive=True))
	files += sorted(glob.glob(os.path.join(HERE, "presets", "**", "*.json"), recursive=True))
	files += sorted(glob.glob(os.path.join(HERE, "fixtures", "*.json")))
	files += [os.path.join(HERE, n) for n in ("check.py", "compile.py", "build.py", "catalog.json", "selftest.py")]
	for f in files:
		h.update(os.path.relpath(f, HERE).encode())
		with open(f, "rb") as fh:
			h.update(fh.read())
	return h.hexdigest()


def corpus(quick):
	"""回傳 (名稱, 種類, 內容)；種類 strict＝必須全過，history＝只要求不崩潰。"""
	items = []
	for pattern in ("fixtures/*.scene.json", "examples/*.scene.json"):
		for f in sorted(glob.glob(os.path.join(HERE, pattern))):
			items.append((os.path.relpath(f, HERE), "strict", "scene", f))
	for f in sorted(glob.glob(os.path.join(OUT, "check_crashes", "*.timeline.json"))):
		items.append((os.path.relpath(f, OUT), "history", "timeline", f))
	if not quick:
		for f in sorted(glob.glob(os.path.join(OUT, "author_*", "q*.scene.json")) + glob.glob(os.path.join(OUT, "author_*", "q*.failed.json"))):
			items.append((os.path.relpath(f, OUT), "history", "scene", f))
	return items


def run_one(item, catalog):
	name, kind, form, path = item
	with open(path, encoding="utf-8") as f:
		doc = json.load(f)
	if form == "scene":
		try:
			tl = BC.compile_scene(doc, None, catalog)
		except (ValueError, KeyError, TypeError) as e:
			# AI 寫壞的分鏡編譯不過是正常的（所以才會退件）；測試分鏡庫與範例編譯不過就是 bug
			return (name, kind, [f"編譯失敗：{e}"] if kind == "strict" else [], None)
		if kind == "strict" and tl["gaps"]:
			return (name, kind, [f"缺口：{g['wanted']}" for g in tl["gaps"]], None)
	else:
		tl = doc
	with tempfile.TemporaryDirectory() as d:
		BB.build(tl, d)
		r = subprocess.run([PLAYWRIGHT_PY, os.path.join(HERE, "check.py"), d], capture_output=True, text=True)
		report = os.path.join(d, "check.json")
		if not os.path.exists(report):
			last = (r.stderr.strip().splitlines() or ["（無訊息）"])[-1]
			return (name, kind, [f"量測閘崩潰：{last[:300]}"], doc if form == "scene" else None)
		with open(report, encoding="utf-8") as f:
			problems = json.load(f)["problems"]
	if kind == "history":
		problems = [p for p in problems if any(k in p for k in BROKEN)]
	return (name, kind, problems, None)


def objects_of(doc):
	"""展開 preset（介面樣板的屬性與 type 寫在 preset 檔裡），物件自己寫的屬性優先。"""
	out = []
	for o in doc.get("objects", []):
		if o.get("preset"):
			path = os.path.join(HERE, "presets", *o["preset"].split(".")) + ".json"
			if os.path.exists(path):
				with open(path, encoding="utf-8") as f:
					o = {**{k: v for k, v in json.load(f).items() if not k.startswith("_")}, **o}
		out.append(o)
	return out


def coverage(catalog, docs):
	"""測試分鏡庫還沒涵蓋的項目：每個動作要用過，每個選填參數要「有給」「省略」各一次，通用標記要打在錨點與整個物件上各一次。"""
	seen = set()
	generic = catalog["generic_actions"]
	for doc in docs:
		objs = objects_of(doc)
		types = {o.get("id"): o.get("type") for o in objs}
		for o in objs:
			for k in catalog["types"].get(o.get("type"), {}).get("opt", []):
				seen.add((o["type"], "prop", k, k in o))
		for s in doc.get("scenes", []):
			for b in s.get("beats", []):
				for a in b.get("do", []):
					target = str(a.get("target") or "")
					typ = types.get(target.split(":")[0])
					act = a.get("act")
					if act in generic:
						owner, spec = "generic", generic[act]
						if typ:
							seen.add((typ, "mark", act, ":" in target))
					else:
						owner, spec = typ, catalog["types"].get(typ, {}).get("actions", {}).get(act)
					if spec is None:
						continue
					seen.add((owner, "act", act, None))
					for k in spec.get("opt", []):
						seen.add((owner, act, k, k in a))
	missing = []
	label = lambda present: "有給" if present else "省略"
	for typ, t in catalog["types"].items():
		for k in t.get("opt", []):
			missing += [f"{typ} 屬性 {k}（{label(p)}）" for p in (True, False) if (typ, "prop", k, p) not in seen]
		for act, spec in t.get("actions", {}).items():
			if (typ, "act", act, None) not in seen:
				missing.append(f"{typ}.{act} 沒用過")
			for k in spec.get("opt", []):
				missing += [f"{typ}.{act} 參數 {k}（{label(p)}）" for p in (True, False) if (typ, act, k, p) not in seen]
		if t.get("floating"):
			continue
		for g in ("circle", "underline", "arrow"):
			named = [True, False] if t.get("anchors") else [False]
			missing += [f"{typ} 上的 {g}（{'錨點' if n else '整個物件'}）" for n in named if (typ, "mark", g, n) not in seen]
	for act, spec in generic.items():
		for k in spec.get("opt", []):
			missing += [f"{act} 參數 {k}（{label(p)}）" for p in (True, False) if ("generic", act, k, p) not in seen]
	return missing


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("--quick", action="store_true", help="略過 out/author_* 的歷史分鏡")
	ap.add_argument("--force", action="store_true", help="就算雜湊沒變也重跑")
	args = ap.parse_args()
	key = stamp()
	if not args.force and os.path.exists(STAMP):
		with open(STAMP, encoding="utf-8") as f:
			if f.read().strip() == key:
				print("自我檢查：runtime／量測閘／目錄沒變，略過")
				return
	catalog = BC.load_catalog()
	items = corpus(args.quick)
	with ThreadPoolExecutor(max_workers=4) as pool:
		results = list(pool.map(lambda it: run_one(it, catalog), items))
	failed = [(n, k, p) for n, k, p, _ in results if p]
	for n, k, p in failed:
		print(f"✗ {n}（{'必須全過' if k == 'strict' else '不准崩潰'}）")
		for m in p[:6]:
			print(f"    {m}")
	fixtures = []
	for f in sorted(glob.glob(os.path.join(HERE, "fixtures", "*.scene.json"))):
		with open(f, encoding="utf-8") as fh:
			fixtures.append(json.load(fh))
	missing = coverage(catalog, fixtures)
	if missing:
		print(f"測試分鏡庫尚未涵蓋 {len(missing)} 項：")
		for m in missing[:40]:
			print(f"    {m}")
	print(f"自我檢查：{len(items)} 份，{'通過' if not failed else f'{len(failed)} 份有問題'}")
	if failed:
		print(f"@error selftest {failed[0][2][0]}", flush=True)
		sys.exit(1)
	os.makedirs(OUT, exist_ok=True)
	with open(STAMP, "w", encoding="utf-8") as f:
		f.write(key)


if __name__ == "__main__":
	main()
