#!/usr/bin/env python3
"""把多支問題故事串成一支單元重點片：各支原封不動，中間插入程式產生的目錄過場（不呼叫 LLM）。

用法：.venv/bin/python video_engine/board/compose.py <plan.json> <scene 所在目錄> <輸出 scene.json> [--stories q1,q2]

預設串 plan.highlight.stories。各支的物件 id 加上 c{n}_ 前綴避免撞名，所有引用一併改寫。
"""
import argparse
import copy
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from author import apply_glossary
from narrate import speech_problems

NUMERALS = "一二三四五六七八九十"
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩"


def prefix_story(doc, p):
	"""物件 id、場景 id、所有指到物件的地方都加前綴；錨點後半（:r2、:envbtn）不動。"""
	ids = {o["id"] for o in doc["objects"]}
	ref = lambda v: p + v if isinstance(v, str) and v.split(":", 1)[0] in ids else v

	def tree(node):
		if isinstance(node, str):
			return ref(node)
		(kind, kids), = node.items()
		return {kind: [tree(k) for k in kids]}
	doc = copy.deepcopy(doc)
	for o in doc["objects"]:
		o["id"] = p + o["id"]
	for s in doc["scenes"]:
		s["id"] = p + s["id"]
		s["keep"] = [ref(k) for k in s.get("keep", [])]
		if s.get("layout"):
			s["layout"] = tree(s["layout"])
		for b in s["beats"]:
			if b.get("layout"):
				b["layout"] = tree(b["layout"])
			b["do"] = [{k: (ref(v) if k not in ("act", "cue", "with", "text", "label", "note") else v) for k, v in a.items()} for a in b.get("do", [])]
	return doc


def spoken_title(text, glossary):
	"""標題套詞彙表唸法；套完還有英文或縮寫就不唸標題。"""
	doc = apply_glossary({"scenes": [{"beats": [{"say": text}]}]}, glossary)
	said = doc["scenes"][0]["beats"][0].get("spoken", text)
	return None if speech_problems(said) else said


def compose(plan, scenes, story_ids):
	stories = {s["id"]: s for s in plan["stories"]}
	glossary = plan.get("glossary", [])
	unit = plan.get("unit_title", "")
	titles = [stories[q]["title"] for q in story_ids]
	toc = {"id": "toc", "type": "list", "title": f"{unit}：{len(titles)} 個重點",
		"rows": [f"{CIRCLED[k]} {t}" for k, t in enumerate(titles)]}
	out = {"version": 1, "title": f"{unit}：重點整理", "tag": scenes[0].get("tag", unit),
		"corner_note": scenes[0].get("corner_note", "概念示意"), "objects": [toc], "scenes": []}

	def transition(k, first=False):
		title = titles[k]
		said = spoken_title(title, glossary)
		beat = {"say": f"第{NUMERALS[k]}個重點：{title}。", "do": [{"act": "circle", "target": f"toc:r{k}", "cue": "重點"}]}
		if said != title:
			beat["spoken"] = f"第{NUMERALS[k]}個重點：{said}。" if said else f"第{NUMERALS[k]}個重點。"
		beats = [beat]
		if first:
			count = "兩" if len(titles) == 2 else NUMERALS[len(titles) - 1]
			beats.insert(0, {"say": f"這支影片用{count}個重點，帶你看懂{unit}。", "do": [{"act": "show", "target": "toc"}]})
		return {"id": f"toc{k}", "title": f"重點{NUMERALS[k]}：{title}", "label": "重點目錄",
			"keep": [] if first else ["toc"], "layout": {"stack": ["toc"]}, "beats": beats}

	for k, doc in enumerate(scenes):
		out["scenes"].append(transition(k, first=k == 0))
		story = prefix_story(doc, f"c{k + 1}_")
		out["objects"] += story["objects"]
		out["scenes"] += story["scenes"]
	out["scenes"].append({"id": "outro", "title": f"{unit}：重點回顧", "label": "重點目錄", "keep": ["toc"],
		"layout": {"stack": ["toc"]}, "beats": [{"say": "卡在哪一個重點，就回頭再看那一段。", "do": [{"act": "underline", "target": "toc:title"}]}]})
	return out


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("plan")
	ap.add_argument("scene_dir")
	ap.add_argument("out")
	ap.add_argument("--stories", help="逗號分隔；預設 plan.highlight.stories")
	args = ap.parse_args()
	with open(args.plan, encoding="utf-8") as f:
		plan = json.load(f)
	ids = args.stories.split(",") if args.stories else plan["highlight"]["stories"]
	scenes = []
	for q in ids:
		with open(os.path.join(args.scene_dir, f"{q}.scene.json"), encoding="utf-8") as f:
			scenes.append(json.load(f))
	doc = compose(plan, scenes, ids)
	with open(args.out, "w", encoding="utf-8") as f:
		json.dump(doc, f, ensure_ascii=False, indent="\t")
	n = sum(len(s["beats"]) for s in doc["scenes"])
	print(f"{args.out}：{len(ids)} 支、{len(doc['scenes'])} 場、{n} 句")


if __name__ == "__main__":
	main()
