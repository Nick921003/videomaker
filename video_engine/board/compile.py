#!/usr/bin/env python3
"""scene.json（內容＋編排）→ timeline.json（絕對秒數）。

用法：compile.py <scene.json> <timeline.json> [--timing timing.json] [--gaps gaps.jsonl]

純標準庫。時間、可見性、版面時段都在這裡決定，瀏覽器端只負責量測與繪製。
規則見 docs/superpowers/specs/2026-10-03-board-runtime-design.md。
"""
import argparse
import copy
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

LEAD_IN = 0.4
SEC_PER_CHAR = 0.24
BEAT_GAP = 0.35
SCENE_GAP = 0.6
TAIL = 1.2
SEQ_MARGIN = 0.15
# 換場鏡頭最早提前多久起跑：太早會在上一句還沒講完時就把畫面拉走
SCENE_LEAD = 0.5
CONTAINERS = ("stack", "row")


def load_catalog(path=None):
	with open(path or os.path.join(HERE, "catalog.json"), encoding="utf-8") as f:
		return json.load(f)


def anchor_parts(target):
	obj_id, _, name = target.partition(":")
	return obj_id, name


def filter_tree(node, keep):
	"""只留 keep 內的葉節點；空容器刪掉，只剩一個容器子節點的容器攤平。"""
	if isinstance(node, str):
		return node if node in keep else None
	(kind, children), = node.items()
	kids = [k for k in (filter_tree(c, keep) for c in children) if k is not None]
	if not kids:
		return None
	if len(kids) == 1 and isinstance(kids[0], dict):
		return kids[0]
	return {kind: kids}


def tree_ids(node):
	if isinstance(node, str):
		return [node]
	(kind, children), = node.items()
	if kind not in CONTAINERS:
		raise ValueError(f"layout 只能用 {CONTAINERS}：{kind}")
	return [i for c in children for i in tree_ids(c)]


class Compiler:
	def __init__(self, doc, timing, catalog):
		self.doc = doc
		self.timing = timing
		self.cat = catalog
		self.gaps = []
		self.warnings = []

	# ── 物件 ──

	def normalize_objects(self):
		objects = {}
		for raw in self.doc["objects"]:
			obj = copy.deepcopy(raw)
			oid = obj.get("id")
			if not oid or ":" in oid or oid in objects:
				raise ValueError(f"物件 id 缺漏、含冒號或重複：{oid}")
			spec = self.cat["types"].get(obj.get("type"))
			if spec is None:
				# 元件缺口：學生端不能停，退化成 note
				self.gaps.append({"kind": "type", "object": oid, "wanted": obj.get("type"), "fallback": "note"})
				obj = {"id": oid, "type": self.cat["fallback_type"], "text": raw.get("fallback") or oid, "style": "body", "_fallback_of": raw.get("type")}
				spec = self.cat["types"][obj["type"]]
			for key in spec["req"]:
				if key not in obj:
					raise ValueError(f"{oid}（{obj['type']}）缺必填屬性 {key}")
			objects[oid] = obj
		self.objects = objects
		appends = {}
		for scene in self.doc["scenes"]:
			for beat in scene["beats"]:
				for a in beat.get("do", []):
					if a.get("act") == "append":
						appends[a["target"]] = appends.get(a["target"], 0) + 1
		self.total_appends = appends

	def check_anchor(self, target):
		obj_id, name = anchor_parts(target)
		if obj_id not in self.objects:
			raise ValueError(f"錨點指向未知物件：{target}")
		if not name:
			return obj_id
		obj = self.objects[obj_id]
		for pat in self.cat["types"][obj["type"]]["anchors"]:
			m = re.fullmatch(pat.replace("{n}", r"(\d+)"), name)
			if not m:
				continue
			if m.groups():
				n = int(m.group(1))
				limit = self.anchor_limit(obj, pat)
				if limit is not None and not (limit[0] <= n < limit[1]):
					raise ValueError(f"錨點超出範圍：{target}（允許 {limit[0]}..{limit[1] - 1}）")
			return obj_id
		raise ValueError(f"{obj['type']} 沒有錨點 {name}：{target}")

	def anchor_limit(self, obj, pat):
		t = obj["type"]
		if t == "cells" and pat == "i{n}":
			return (0, obj["count"])
		if t == "code" and pat == "L{n}":
			return (1, len(obj["lines"]) + 1)
		if t == "metrics" and pat == "m{n}":
			return (0, len(obj["items"]))
		if t == "list" and pat == "r{n}":
			return (0, len(obj["rows"]) + self.total_appends.get(obj["id"], 0))
		return None

	# ── beat 時間 ──

	def time_beats(self):
		flat = [(si, bi, b) for si, s in enumerate(self.doc["scenes"]) for bi, b in enumerate(s["beats"])]
		if not flat:
			raise ValueError("沒有任何 beat")
		if self.timing is not None:
			if len(self.timing) != len(flat):
				raise ValueError(f"timing 筆數 {len(self.timing)} ≠ beat 數 {len(flat)}")
			spans = [(float(x["t0"]), float(x["t1"])) for x in self.timing]
			for (a0, a1), (b0, _) in zip(spans, spans[1:]):
				if not a0 < a1 <= b0 + 1e-6:
					raise ValueError("timing 必須遞增且不重疊")
		else:
			spans, t, prev_scene = [], LEAD_IN, 0
			for si, _, b in flat:
				if spans:
					t += BEAT_GAP + (SCENE_GAP if si != prev_scene else 0)
				dur = len(re.sub(r"\s", "", b["say"])) * SEC_PER_CHAR
				spans.append((t, t + dur))
				t += dur
				prev_scene = si
		self.beats = [{"scene": si, "i": bi, "t0": t0, "t1": t1, "say": b["say"], "spoken": b.get("spoken"), "layout": b.get("layout")}
			for (si, bi, b), (t0, t1) in zip(flat, spans)]
		self.duration = round(self.beats[-1]["t1"] + TAIL, 3)

	# ── 動作 ──

	def action_spec(self, act, obj):
		generic = self.cat["generic_actions"]
		if act in generic:
			return generic[act]
		return self.cat["types"][obj["type"]]["actions"].get(act) if obj else None

	def collect_actions(self):
		actions = []
		appended = {}
		for beat in self.beats:
			raw_beat = self.doc["scenes"][beat["scene"]]["beats"][beat["i"]]
			for k, raw in enumerate(raw_beat.get("do", [])):
				act = raw.get("act")
				target = raw.get("target")
				where = f"{self.doc['scenes'][beat['scene']]['id']}/beat{beat['i']}/{act}"
				spec = self.cat["generic_actions"].get(act)
				obj = None
				if not (spec and spec.get("no_target")):
					if not target:
						raise ValueError(f"{where} 缺 target")
					obj = self.objects[self.check_anchor(target)]
					spec = self.action_spec(act, obj)
				if spec is None:
					self.gaps.append({"kind": "action", "object": obj["id"], "wanted": f"{obj.get('_fallback_of') or obj['type']}.{act}", "fallback": "skip"})
					continue
				args = {key: v for key, v in raw.items() if key not in ("act", "target", "cue", "with")}
				for key in spec.get("req", []):
					if key not in args:
						raise ValueError(f"{where} 缺參數 {key}")
				for key in spec.get("anchor_args", []):
					if key in args:
						self.check_anchor(args[key])
				if raw.get("cue") is not None and raw["cue"] not in beat["say"]:
					raise ValueError(f"{where} 的 cue「{raw['cue']}」不在句中：{beat['say']}")
				n = self.seq_count(spec, args, obj, appended, where)
				if act == "append":
					appended[obj["id"]] = appended.get(obj["id"], 0) + 1
				actions.append({
					"scene": beat["scene"], "beat": self.beats.index(beat), "first": k == 0,
					"act": act, "target": target, "obj": obj["id"] if obj else None,
					"cue": raw.get("cue"), "with": raw.get("with"), "args": args, "n": n,
					"spec": spec, "blocks": bool(spec.get("blocks")),
				})
		self.actions = actions

	def seq_count(self, spec, args, obj, appended, where):
		kind = spec.get("seq")
		if kind is None:
			return None
		if kind == "values":
			return len(args["values"])
		if kind == "range":
			lo, hi = args["range"]
			if not 0 <= lo <= hi < obj["count"]:
				raise ValueError(f"{where} range 超出格數：{args['range']}")
			return hi - lo + 1
		if kind == "items":
			if "index" in args:
				if not 0 <= args["index"] < len(obj["items"]):
					raise ValueError(f"{where} index 超出項目數：{args['index']}")
				return 1
			return len(obj["items"])
		if kind == "chars":
			return len(args["text"])
		if kind == "lines":
			return len(args["lines"])
		if kind == "walk":
			rows = len(obj["rows"]) + appended.get(obj["id"], 0)
			found = args.get("found")
			if found is not None and not 0 <= found < rows:
				raise ValueError(f"{where} found 超出列數：{found}")
			return rows if found is None else found + 1
		raise ValueError(f"未知序列種類 {kind}")

	def anchored_start(self, a):
		beat = self.beats[a["beat"]]
		if a["cue"] is not None:
			return beat["t0"] + (beat["t1"] - beat["t0"]) * beat["say"].index(a["cue"]) / len(beat["say"])
		if a["first"]:
			return beat["t0"]
		return None

	def time_actions(self):
		scene_end = {}
		for b in self.beats:
			scene_end[b["scene"]] = b["t1"]
		prev = None
		for idx, a in enumerate(self.actions):
			start = self.anchored_start(a)
			if a["with"] == "prev" and prev is not None and not a["first"]:
				start = prev["t0"]
			elif start is None:
				start = prev["t1"]
			a["t0"] = start
			spec = a["spec"]
			if a["n"] is not None:
				lo, hi = spec["per"]
				window = self.window_end(idx, scene_end[a["scene"]]) - start - SEQ_MARGIN
				dur = min(max(window, a["n"] * lo), a["n"] * hi)
				if window < a["n"] * lo - 1e-6:
					self.warnings.append(f"{self.where(a)} 趕：可用 {max(window, 0):.2f}s，至少需 {a['n'] * lo:.2f}s")
			elif "per_char" in spec:
				text = self.objects[a["obj"]]["text"]
				dur = min(max(len(text) * spec["per_char"], spec["min"]), spec["max"])
			else:
				dur = spec["dur"]
			a["t1"] = start + dur
			prev = a

	def window_end(self, idx, scene_end):
		me = self.actions[idx]
		for later in self.actions[idx + 1:]:
			if later["scene"] != me["scene"]:
				break
			start = self.anchored_start(later)
			if later["blocks"] and start is not None and start >= me["t0"]:
				return start
		return scene_end

	def where(self, a):
		return f"{self.doc['scenes'][a['scene']]['id']}/beat{self.beats[a['beat']]['i']}/{a['act']}"

	# ── 推導內容：scan 讀到的字元、輸出框最大文字 ──

	def derive_content(self):
		values = {oid: list(o.get("values") or [None] * o["count"]) for oid, o in self.objects.items() if o["type"] == "cells"}
		out_text = {}
		out_max = {oid: o.get("text", "") for oid, o in self.objects.items() if o["type"] == "output"}
		for a in sorted(self.actions, key=lambda a: a["t0"]):
			if a["act"] == "fill":
				start = a["args"].get("start", 0)
				for k, v in enumerate(a["args"]["values"]):
					if start + k < len(values[a["obj"]]):
						values[a["obj"]][start + k] = v
			elif a["act"] == "scan":
				lo, hi = a["args"]["range"]
				chars = [values[a["obj"]][i] or "" for i in range(lo, hi + 1)]
				a["args"]["chars"] = chars
				to = a["args"].get("to")
				if to:
					dst = anchor_parts(to)[0]
					out_text[dst] = out_text.get(dst, "") + "".join(chars)
					out_max[dst] = max(out_max.get(dst, ""), out_text[dst], key=len)
			elif a["act"] == "set" and a["obj"] in out_max:
				out_text[a["obj"]] = a["args"]["text"]
				out_max[a["obj"]] = max(out_max[a["obj"]], a["args"]["text"], key=len)
		for oid, text in out_max.items():
			obj = self.objects[oid]
			obj["_max_text"] = max(obj.get("max_text", ""), text, key=len)

	# ── 可見性與版面時段 ──

	def referenced(self, a):
		ids = [a["obj"]] if a["obj"] else []
		for key in a["spec"].get("anchor_args", []):
			if key in a["args"]:
				ids.append(anchor_parts(a["args"][key])[0])
		return ids

	def visibility_and_epochs(self):
		scenes = self.doc["scenes"]
		enters = []
		for si in range(len(scenes)):
			first = next(b for b in self.beats if b["scene"] == si)
			if si == 0:
				enters.append(0.0)
			else:
				prev_last = max(b["t1"] for b in self.beats if b["scene"] == si - 1)
				enters.append(max(prev_last, first["t0"] - SCENE_LEAD))
		self.enters = enters
		# 事件：(時間, 順序, 種類, 資料)
		events = [(t, 0, "scene", si) for si, t in enumerate(enters)]
		for b in self.beats:
			if b["layout"]:
				events.append((b["t0"], 1, "layout", b))
		for a in self.actions:
			if a["act"] == "hide":
				events.append((a["t0"], 3, "hide", a))
			elif a["act"] not in ("wide",):
				for oid in self.referenced(a):
					events.append((a["t0"], 2, "show", (oid, a["scene"])))
		events.sort(key=lambda e: (e[0], e[1]))

		vis = {oid: [] for oid in self.objects}
		on = {}
		home = {}
		scene = 0
		layout = scenes[0].get("layout")
		epochs = []
		for t, _, kind, data in events:
			if kind == "scene":
				scene = data
				layout = scenes[scene].get("layout")
				for oid in scenes[scene].get("keep", []):
					if oid not in self.objects:
						raise ValueError(f"keep 指向未知物件：{oid}")
					home[oid] = scene
			elif kind == "layout":
				layout = data["layout"]
			elif kind == "show":
				oid, s = data
				if oid not in on:
					on[oid] = t
				home[oid] = s
			elif kind == "hide":
				oid = data["obj"]
				if oid in on:
					vis[oid].append([on.pop(oid), data["t1"]])
				else:
					self.warnings.append(f"{self.where(data)} 隱藏了尚未顯示的物件 {oid}")
			members = {oid for oid in on if home.get(oid) == scene}
			spec = layout or {"stack": [o["id"] for o in self.doc["objects"]]}
			declared = tree_ids(spec)
			for oid in declared:
				if oid not in self.objects:
					raise ValueError(f"layout 引用未知物件：{oid}")
			missing = sorted(members - set(declared))
			if missing:
				self.warnings.append(f"{scenes[scene]['id']} 的 layout 沒列到 {missing}，自動接在最後")
				(k, kids), = spec.items()
				spec = {k: kids + missing}
			epoch = {"t": round(t, 4), "scene": scene, "tree": filter_tree(spec, members)}
			if epochs and abs(epochs[-1]["t"] - epoch["t"]) < 1e-6:
				epochs[-1] = epoch
			elif not epochs or epochs[-1]["tree"] != epoch["tree"] or epochs[-1]["scene"] != epoch["scene"]:
				epochs.append(epoch)
		for oid, t0 in on.items():
			vis[oid].append([t0, None])
		self.visibility = vis
		self.epochs = epochs

	# ── 輸出 ──

	def run(self):
		self.normalize_objects()
		for scene in self.doc["scenes"]:
			if scene.get("layout"):
				for oid in tree_ids(scene["layout"]):
					if oid not in self.objects:
						raise ValueError(f"{scene['id']} 的 layout 引用未知物件：{oid}")
		self.time_beats()
		self.collect_actions()
		self.time_actions()
		self.derive_content()
		self.visibility_and_epochs()
		scenes = self.doc["scenes"]
		subtitles = []
		for k, b in enumerate(self.beats):
			end = self.beats[k + 1]["t0"] if k + 1 < len(self.beats) else self.duration
			subtitles.append({"t0": b["t0"], "t1": end, "text": b["say"]})
		camera = [{"t": t, "dur": 1.0, "kind": "scene", "scene": si} for si, t in enumerate(self.enters)]
		for a in self.actions:
			if a["act"] in ("focus", "wide"):
				camera.append({"t": a["t0"], "dur": a["t1"] - a["t0"], "kind": a["act"], "target": a["target"], "scene": a["scene"]})
		camera.sort(key=lambda c: c["t"])
		out_actions = [{key: a[key] for key in ("scene", "beat", "act", "target", "obj", "args", "n", "t0", "t1")} for a in self.actions]
		return {
			"version": 1,
			"title": self.doc.get("title", ""),
			"tag": self.doc.get("tag", ""),
			"corner_note": self.doc.get("corner_note", ""),
			"duration": self.duration,
			"objects": self.objects,
			"scenes": [{"id": s["id"], "title": s.get("title", ""), "label": s.get("label", ""),
				"t_enter": self.enters[si], "t0": next(b["t0"] for b in self.beats if b["scene"] == si)} for si, s in enumerate(scenes)],
			"beats": [{key: b[key] for key in ("scene", "i", "t0", "t1", "say", "spoken")} for b in self.beats],
			"subtitles": subtitles,
			"actions": out_actions,
			"visibility": self.visibility,
			"epochs": self.epochs,
			"camera": camera,
			"gaps": self.gaps,
			"warnings": self.warnings,
		}


def compile_scene(scene, timing, catalog):
	return Compiler(scene, timing, catalog).run()


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("scene")
	ap.add_argument("out")
	ap.add_argument("--timing")
	ap.add_argument("--gaps", default=os.path.join(HERE, "gaps.jsonl"))
	args = ap.parse_args()
	with open(args.scene, encoding="utf-8") as f:
		scene = json.load(f)
	timing = None
	if args.timing:
		with open(args.timing, encoding="utf-8") as f:
			timing = json.load(f)
	tl = compile_scene(scene, timing, load_catalog())
	with open(args.out, "w", encoding="utf-8") as f:
		json.dump(tl, f, ensure_ascii=False, indent=1)
	if tl["gaps"]:
		with open(args.gaps, "a", encoding="utf-8") as f:
			for g in tl["gaps"]:
				f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "title": tl["title"], **g}, ensure_ascii=False) + "\n")
	for w in tl["warnings"]:
		print("警告：" + w, file=sys.stderr)
	print(f"{args.out}：{tl['duration']:.2f}s，{len(tl['actions'])} 個動作，{len(tl['gaps'])} 個缺口，{len(tl['warnings'])} 則警告")


if __name__ == "__main__":
	main()
