#!/usr/bin/env python3
"""黑板分鏡 storyboard.json → 手帳 scene.json（＋有 story.json 時的 timing.json）：一份分鏡兩種出片。

用法：
  python3 video_engine/explainer/storyboard_to_scene.py <story 資料夾> <輸出資料夾>

一頁變一個 scene，物件、每句的 say／do 照搬；結語句接在最後一個 scene，複習頁變成一個 list。
timing 照 story.json 的實測（或草稿估計）句界；先畫後講的 lead 寫成獨立的 draw 時刻，句子本身的 t0 不提前，
字幕和 cue 仍然對著聲音。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pages import RECAP_LEAD  # noqa: E402


def to_scene(sb):
	"""回傳手帳 scene.json；物件 id 全片唯一，重複就報錯（自動改名會讓 do 的 target 對不上）"""
	objects, scenes, seen = [], [], set()

	def add(o):
		if o["id"] in seen:
			raise ValueError("物件 id 重複：%s（手帳全片共用一組物件，不同頁要取不同名字）" % o["id"])
		seen.add(o["id"])
		objects.append(o)

	for ch in sb["chapters"]:
		for n, pg in enumerate(ch["pages"], 1):
			if pg["template"] == "screen":
				ids = []
				if pg.get("screen"):
					scr = dict(pg["screen"])
					scr.setdefault("type", "vscode")
					add(scr)
					ids = [scr["id"]]
					# 游標是浮動物件，全片一個就夠，各段電腦畫面共用
					if "cursor" not in seen:
						add({"id": "cursor", "type": "cursor"})
				layout = {"stack": ids}
			else:
				objs = pg.get("objects") or []
				for o in objs:
					add({k: v for k, v in o.items() if k != "col"})
				if pg["template"] == "two-col":
					side = lambda c: [o["id"] for o in objs if o.get("col") == c]
					layout = {"row": [{"stack": side("left")}, {"stack": side("right")}]}
				else:
					layout = {"stack": [o["id"] for o in objs]}
			beats = [{"say": ln["say"], "do": ln.get("do", [])} for ln in pg["lines"]]
			scenes.append({"id": "%s_p%d" % (ch["id"], n), "title": ch["title"], "layout": layout, "beats": beats})
	end = sb["end"]
	scenes[-1]["beats"].append({"say": end["say"], "do": end.get("do", [])})
	rc = sb["recap"]
	add({"id": "recap", "type": "list", "rows": rc["items"], "title": rc["center"]})
	scenes.append({"id": "recap", "title": rc["center"], "layout": {"stack": ["recap"]},
		"beats": [{"say": rc["say"], "do": [{"act": "show", "target": "recap"}]}]})
	return {"version": 1, "title": sb["title"], "objects": objects, "scenes": scenes}


def to_timing(story):
	"""story.json → 手帳 timing：每句 {t0, t1, draw}，最後一筆是複習頁旁白。
	draw 夾在上一句講完之後：圖不能搶在上一句還在講的時候畫"""
	out, prev = [], 0.0
	for L in story["lines"]:
		out.append({"t0": L["start"], "t1": L["end"], "draw": round(max(L["start"] - L.get("lead", 0.0), prev), 3)})
		prev = L["end"]
	rc = story.get("recap")
	if rc:
		# 草稿沒有複習頁旁白，照配音版的位置估一段
		say = rc.get("say") or {"start": round(rc["start"] + RECAP_LEAD, 3), "end": rc["end"]}
		out.append({"t0": say["start"], "t1": say["end"]})
	return out


def main():
	if len(sys.argv) != 3:
		print(__doc__)
		return 2
	src, dst = sys.argv[1:]
	sb = json.load(open(os.path.join(src, "storyboard.json"), encoding="utf-8"))
	os.makedirs(dst, exist_ok=True)
	json.dump(to_scene(sb), open(os.path.join(dst, "scene.json"), "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
	written = ["scene.json"]
	sp = os.path.join(src, "story.json")
	if os.path.exists(sp):
		story = json.load(open(sp, encoding="utf-8"))
		json.dump(to_timing(story), open(os.path.join(dst, "timing.json"), "w", encoding="utf-8"), indent="\t")
		written.append("timing.json")
	print("寫出 " + "、".join(written))
	return 0


if __name__ == "__main__":
	sys.exit(main())
