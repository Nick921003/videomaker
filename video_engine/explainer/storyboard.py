#!/usr/bin/env python3
"""分鏡表 storyboard.json → story 資料夾的 script.md、pages.json、screens.json、leads.json、holds.json、keys.json、recap.json。

用法：
  python3 video_engine/explainer/storyboard.py <story 資料夾>

分鏡表是唯一手寫（或由 LLM 產生）的檔案：每頁定模板（center／two-col／screen）與主角配角，
每句寫旁白、黑板上的關鍵詞（key，字幕改成 .srt 另給，黑板只留關鍵詞）、開口前先畫什麼（draw）、講的時候點名什麼（point）。其餘檔案一律由它產生，不要手改。
draw／point 不進 script.md，是給寫 beats.js 的人（或 AGY）看的規格。
每頁的 spine 是「這頁要讓學生懂的一句話」：交審先看 review.md 的骨架順序，再看逐句（使用者 2026-10-26：
逐句讀都通順，順序的毛病只有連著看骨架才看得出來）。
"""
import json
import os
import sys

TEMPLATES = ("center", "two-col", "screen")


def build(sb):
	"""回傳 {檔名: 內容字串}；句號從 1 起算，結語句接在最後。"""
	md = ["---", "title: " + sb["title"], "subtitle: " + sb["subtitle"], "---", ""]
	pages, screens, leads, holds, keys = [], [], {}, {}, {}
	spine = ["# " + sb["title"] + "：骨架", ""]
	review = []
	n = 0
	for ch in sb["chapters"]:
		md.append("## %s | %s" % (ch["id"], ch["title"]))
		review += ["## " + ch["title"], ""]
		for pg in ch["pages"]:
			if pg["template"] not in TEMPLATES:
				raise ValueError("未知模板 %r（只准 %s）" % (pg["template"], "／".join(TEMPLATES)))
			nums = []
			spine.append("- %s｜%s" % (ch["title"], pg.get("spine", "（沒寫 spine）")))
			review += ["### %s（%s）" % (pg.get("spine", "（沒寫 spine）"), pg["template"]), ""]
			for ln in pg["lines"]:
				n += 1
				nums.append(n)
				md.append(ln["say"])
				review.append("%d. %s%s" % (n, ln["say"], "　〔" + ln["key"] + "〕" if ln.get("key") else ""))
				if ln.get("lead"):
					leads[str(n)] = ln["lead"]
				if ln.get("hold"):
					holds[str(n)] = ln["hold"]
				if ln.get("key"):
					keys[str(n)] = ln["key"]
			if pg["template"] == "screen":
				screens.append({"lines": nums, "kind": pg.get("kind", "vscode")})
			else:
				pages.append(nums)
			review.append("")
		md += ["> " + x for x in ch.get("notes", [])]
		md.append("")
	end = sb["end"]
	md += ["## end", "emphasis: " + end["emphasis"], end["say"], ""]
	review += ["## 結語", "", "%d. %s" % (n + 1, end["say"]), ""]
	rc = sb["recap"]
	md += ["## recap", "center: " + rc["center"], "tagline: " + rc["tagline"], "length: %s" % rc["length"]]
	md += ["- " + x for x in rc["items"]]
	dump = lambda o: json.dumps(o, ensure_ascii=False)
	return {
		"script.md": "\n".join(md) + "\n",
		"pages.json": dump(pages),
		"screens.json": dump(screens),
		"leads.json": dump(leads),
		"holds.json": dump(holds),
		"keys.json": dump(keys),
		"recap.json": dump({"say": rc["say"]}),
		"review.md": "\n".join(spine + ["", "---", ""] + review),
	}


def main(folder):
	with open(os.path.join(folder, "storyboard.json"), encoding="utf-8") as f:
		files = build(json.load(f))
	for name, text in files.items():
		with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
			f.write(text)
	print("寫出 " + "、".join(files))


if __name__ == "__main__":
	main(sys.argv[1])
