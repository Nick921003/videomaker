#!/usr/bin/env python3
"""錨點閘：beats.js 引用的旁白字串，逐個對 story 的句子解一次。

用法：python3 tools/anchor_check.py [專案目錄]

api.span(n,"字")／api.at(n,"字"[,k])／api.phrase(n,"字") 都是拿旁白的字面當定位點。
旁白改字之後解不到，runtime 回 null，動作會安靜地不發生——改稿時最容易漏的就是這個。
"""
import json
import os
import re
import sys

ANCHOR = re.compile(r"api\.(span|at|phrase)\(\s*(\d+)\s*,\s*\"([^\"]+)\"(?:\s*,\s*(\d+))?\s*\)")


def problems(beats, lines):
	out = []
	for kind, n, text, nth in {m.groups() for m in ANCHOR.finditer(beats)}:
		i, want = int(n), int(nth or 1)
		if i not in lines:
			out.append(f"api.{kind}({i},\"{text}\")：沒有第 {i} 句")
			continue
		# runtime 比對前會去掉空白（"CodeRunner" 指得到旁白裡的 "Code Runner"），這裡要一樣
		got = re.sub(r"\s", "", lines[i]).count(re.sub(r"\s", "", text))
		if got < want:
			out.append(f"api.{kind}({i},\"{text}\"{', ' + nth if nth else ''})："
				f"第 {i} 句只出現 {got} 次，要第 {want} 次 → {lines[i]}")
	return out


def main():
	root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
	beats = open(os.path.join(root, "beats.js"), encoding="utf-8").read()
	story = open(os.path.join(root, "lib", "story.js"), encoding="utf-8").read()
	data = json.loads(story[story.index("{"): story.rindex("}") + 1])
	lines = {l["i"]: l["text"] for l in data["lines"]}
	bad = problems(beats, lines)
	total = len({m.groups() for m in ANCHOR.finditer(beats)})
	print(f"錨點閘：{total} 個引用，{'全部解得到' if not bad else f'{len(bad)} 個解不到'}")
	for m in bad:
		print("  " + m)
	return 1 if bad else 0


if __name__ == "__main__":
	sys.exit(main())
