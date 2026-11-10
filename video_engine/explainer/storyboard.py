#!/usr/bin/env python3
"""分鏡表 storyboard.json → story 資料夾的 script.md、pages.json、screens.json、leads.json、holds.json、keys.json、recap.json。

用法：
  python3 video_engine/explainer/storyboard.py <story 資料夾>

分鏡表是唯一手寫（或由 LLM 產生）的檔案：每頁定模板（center／two-col／screen）與主角配角，
每句寫旁白、黑板上的關鍵詞（key，字幕改成 .srt 另給，黑板只留關鍵詞）、開口前先畫什麼（draw）、講的時候點名什麼（point）。其餘檔案一律由它產生，不要手改。
draw／point 不進 script.md，是給寫 beats.js 的人（或 AGY）看的規格。
電腦畫面頁可以另寫 screen（元件描述，格式同手帳 scene.json 的物件）與每句的 do（動作），
會經手帳編譯器驗證後寫進 screens.json，黑板轉接照它畫，不用寫程式。
每頁的 spine 是「這頁要讓學生懂的一句話」：交審先看 review.md 的骨架順序，再看逐句（使用者 2026-10-26：
逐句讀都通順，順序的毛病只有連著看骨架才看得出來）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "board"))
import compile as BC  # noqa: E402

TEMPLATES = ("center", "two-col", "screen")
BOARD_TYPES = ("icon", "note")  # 黑板已有粉筆皮膚的元件；其他型別不准悄悄換成別的畫法
CENTER_MAX, COL_MAX = 3, 2
KEEP = ("act", "target", "obj", "args", "n", "cue")


def action_dur(a):
	"""動作時長照編譯器排出來的 t1−t0；until 類沒有固定長度，填 None 讓黑板端換算。
	逐項動作（per）的長度取決於真實的句長視窗，假時間軸算不準，維持取區間中點（舊基準）。"""
	spec = a["spec"]
	if spec.get("span") == "until":
		return None
	if "per" in spec:
		return (a["n"] or 1) * sum(spec["per"]) / 2
	d = a["t1"] - a["t0"]
	if "dur" in spec and abs(d - spec["dur"]) < 1e-6:
		return spec["dur"]  # 沒被句尾壓縮就是 catalog 原值，避免浮點雜訊
	return round(d, 6)


def action_out(a, first):
	"""編譯後的動作 → 分鏡檔格式；until_beat 是頁內序號、until_t 是假時間軸算的，換成全片句號"""
	args = {k: v for k, v in a["args"].items() if k not in ("until_beat", "until_t")}
	if "until_beat" in a["args"]:
		args["until_line"] = first + a["args"]["until_beat"]
	return {k: (args if k == "args" else a[k]) for k in KEEP} | {"dur": action_dur(a), "blocks": a["blocks"]}


def screen_actions(pg, first):
	"""電腦畫面頁的元件描述交給手帳的編譯器驗證（型別、欄位、錨點、cue 在不在旁白裡），
	回傳 (補齊預設的元件物件, {句號: [動作]})。黑板沒有逐句的實測時間，dur 給黑板轉接自己照 cue 排。"""
	obj = dict(pg["screen"])
	obj.setdefault("type", "vscode")
	doc = {"version": 1, "objects": [obj, {"id": "cursor", "type": "cursor"}],
		"scenes": [{"id": "screen", "layout": {"stack": [obj["id"]]}, "beats": [{"say": ln["say"], "do": ln.get("do", [])} for ln in pg["lines"]]}]}
	c = BC.Compiler(doc, None, BC.load_catalog())
	c.run()
	do = {}
	for a in c.actions:
		spec = a["spec"]
		do.setdefault(str(first + a["beat"]), []).append(action_out(a, first))
	return c.objects[obj["id"]], do


def board_layout(pg):
	"""置中／雙欄頁的版面文法；超過就是教材寫太滿，明確報錯"""
	objs = pg["objects"]
	# dir: row＝置中頁的物件左右並排（預設由上往下）；雙欄頁本身就是左右兩欄，不再開橫排
	if pg.get("dir") is not None and (pg["dir"] != "row" or pg["template"] != "center"):
		raise ValueError("dir 只能在置中頁寫 row（這頁是 %s、dir=%r）" % (pg["template"], pg["dir"]))
	for o in objs:
		if o.get("type") not in BOARD_TYPES:
			raise ValueError("黑板還沒有 %s 的粉筆皮膚（%s）：目前只有 %s" % (o.get("type"), o.get("id"), "、".join(BOARD_TYPES)))
	ids = [o["id"] for o in objs]
	if pg["template"] == "center":
		if len(objs) > CENTER_MAX:
			raise ValueError("置中頁最多 %d 個物件，這頁有 %d 個：%s" % (CENTER_MAX, len(objs), ids))
		return {"row" if pg.get("dir") == "row" else "stack": ids}
	cols = {"left": [], "right": []}
	for o in objs:
		if o.get("col") not in cols:
			raise ValueError("雙欄頁的物件 %s 要寫 col: left 或 right" % o["id"])
		cols[o["col"]].append(o["id"])
	for side, got in cols.items():
		if len(got) > COL_MAX:
			raise ValueError("雙欄頁每欄最多 %d 個物件，%s 欄有 %d 個：%s" % (COL_MAX, side, len(got), got))
	return {"row": [{"stack": cols["left"]}, {"stack": cols["right"]}]}


def board_actions(pg, first):
	"""置中／雙欄頁的物件與每句的 do 交給手帳編譯器驗證，回傳 (補齊預設的物件, {句號: [動作]})"""
	layout = board_layout(pg)
	cols = {o["id"]: o.get("col") for o in pg["objects"]}
	objs = [{k: v for k, v in o.items() if k != "col"} for o in pg["objects"]]
	doc = {"version": 1, "objects": objs, "scenes": [{"id": "board", "layout": layout, "beats": [{"say": ln["say"], "do": ln.get("do", [])} for ln in pg["lines"]]}]}
	c = BC.Compiler(doc, None, BC.load_catalog())
	c.run()
	firsts = {}
	do = {}
	for a in c.actions:
		firsts.setdefault(a["obj"], a)
		do.setdefault(str(first + a["beat"]), []).append(action_out(a, first))
	for o in pg["objects"]:
		if o["type"] == "note" and o["id"] in firsts and firsts[o["id"]]["act"] not in ("write", "show"):
			raise ValueError("%s（note）的第一個動作是 %s：文字要先 write 或 show" % (o["id"], firsts[o["id"]]["act"]))
	out = []
	for o in pg["objects"]:
		x = c.objects[o["id"]]
		out.append(x | {"col": cols[o["id"]]} if cols[o["id"]] else x)
	return out, do


def build(sb):
	"""回傳 {檔名: 內容字串}；句號從 1 起算，結語句接在最後。"""
	md = ["---", "title: " + sb["title"], "subtitle: " + sb["subtitle"], "---", ""]
	pages, screens, boards, leads, holds, keys = [], [], [], {}, {}, {}
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
				scr = {"lines": nums, "kind": pg.get("kind", "vscode")}
				if pg.get("screen"):
					scr["screen"], scr["do"] = screen_actions(pg, nums[0])
				screens.append(scr)
			else:
				pages.append(nums)
				if pg.get("objects") is not None:
					objs, do = board_actions(pg, nums[0])
					boards.append({"lines": nums, "template": pg["template"], "objects": objs, "do": do} | ({"dir": pg["dir"]} if pg.get("dir") else {}))
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
	extra = {"objects.json": dump(boards)} if boards else {}
	return extra | {
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
