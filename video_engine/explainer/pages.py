#!/usr/bin/env python3
"""story 的分頁、句間空檔與先畫後講；不需要 GPU，草稿片和 f5_story.py 共用同一套規則。

用法：
  (cd video_engine/explainer/chalk && python3 tools/story.py <story 資料夾> --dry)
  python3 video_engine/explainer/pages.py <story 資料夾>

只接受 story.draft == true：沒配音的骨架照 pages.json／screens.json／holds.json／leads.json 分頁、
留換頁時間、套 lead／hold，寫回 story.json（仍是草稿，旁白無聲）。真正配音照舊走 f5_story.py（在 Colab）。
骨架第一次讀到時另存成 story.dry.json，之後一律從它重建，重跑不會越疊越歪。
"""
import bisect
import json
import os
import shutil
import sys

# 粉筆頁換粉筆頁：板擦擦掉（講完 0.1＋擦 1.5＋0.2 後開口）。使用者 2026-10-25：擦 0.9 秒像趕火車
ERASE_GAP = 1.8
# 其餘換頁直線平移：講完 0.2 出發＋平移 0.9＋到位 0.1。黑板 index.html 的 ERASE_AT／ERASE_DUR／LEAVE／PAN／SETTLE 配合這裡
TRAVEL_GAP = 1.2
# 進電腦畫面：講完 0.2 出發＋平移 0.9＋畫螢幕框與推近 1.4
SCREEN_GAP = 2.5
# 複習頁的旁白（recap.json 的 say）：頁出現後稍等再講，講完留時間看圖
RECAP_LEAD = 0.6
RECAP_TAIL = 2.5


def remap(knots):
	"""骨架時間 → 實際時間：句界之間線性內插，範圍外平移"""
	xs = [a for a, _ in knots]
	ys = [b for _, b in knots]

	def f(t):
		if t <= xs[0]:
			return ys[0] + (t - xs[0])
		if t >= xs[-1]:
			return ys[-1] + (t - xs[-1])
		j = bisect.bisect_right(xs, t) - 1
		return ys[j] + (t - xs[j]) * (ys[j + 1] - ys[j]) / (xs[j + 1] - xs[j])
	return f


def chapter_of(s, line):
	"""和黑板 index.html 同一套歸章規則（骨架時間）"""
	for k, c in enumerate(s["chapters"]):
		if c["start"] - 0.05 <= line["start"] < c["end"]:
			return k
	return max([k for k, c in enumerate(s["chapters"]) if c["start"] <= line["start"] + 0.3] or [0])


def make_pages(s, story_dir):
	"""回傳 (pages, screens)；檔案不合規就明確失敗，不猜"""
	end_line = (s.get("end") or {}).get("line")
	body = [L["i"] for L in s["lines"] if L["i"] != end_line]
	chap = {L["i"]: chapter_of(s, L) for L in s["lines"]}
	sp = os.path.join(story_dir, "screens.json")
	screens = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else []
	for sc in screens:
		if len({chap[i] for i in sc["lines"]}) > 1:
			raise SystemExit(f"screens.json 的 {sc['lines']} 跨章了，一段電腦畫面只能在同一章裡")
	on_screen = {i for sc in screens for i in sc["lines"]}
	path = os.path.join(story_dir, "pages.json")
	if os.path.exists(path):
		pages = json.load(open(path, encoding="utf-8"))
		groups = sorted(pages + [sc["lines"] for sc in screens], key=lambda g: body.index(g[0]) if g[0] in body else -1)
		if [i for g in groups for i in g] != body:
			raise SystemExit(f"pages.json＋screens.json 要依序涵蓋每一句正文（{body}），不多不少、不重疊")
		for pg in pages:
			if len({chap[i] for i in pg}) > 1:
				raise SystemExit(f"pages.json 的 {pg} 跨章了，一頁只能放同一章的句子")
		return pages, screens
	pages, cur, cur_k = [], [], None
	for i in body:
		if i in on_screen:
			if cur:
				pages.append(cur)
			cur, cur_k = [], None
			continue
		if cur and (chap[i] != cur_k or len(cur) == 2):
			pages.append(cur)
			cur = []
		cur.append(i)
		cur_k = chap[i]
	return (pages + [cur] if cur else pages), screens


def load_pauses(story_dir, name):
	"""holds.json／leads.json → {句號: 秒數}；負數會讓句子疊在一起，明確失敗"""
	path = os.path.join(story_dir, name)
	if not os.path.exists(path):
		return {}
	holds = {int(k): float(v) for k, v in json.load(open(path, encoding="utf-8")).items()}
	bad = [k for k, v in holds.items() if v < 0]
	if bad:
		raise SystemExit(f"{name} 的 {bad} 是負數，只能多停不能少停")
	return holds


def recap_start(mapped, last_end):
	"""結語講完像換頁一樣平移到複習頁；黑板在複習頁開始後 0.55 秒到位（出發 0.2＋平移 0.9＝1.1）"""
	return max(mapped, last_end + TRAVEL_GAP - 0.65)


def recap_window(start, end, voice_sec):
	"""複習頁旁白的起點與（必要時拉長的）複習頁結尾"""
	at = start + RECAP_LEAD
	return at, max(end, at + voice_sec + RECAP_TAIL)


def gap_after(prev_i, cur_i, where, base):
	"""where：句號 → ("p", 頁序) 或 ("s", 螢幕段序)；結語句不在 where 裡，視為換頁"""
	a, b = where.get(prev_i), where.get(cur_i)
	if a == b and a is not None:
		return base
	if (a and a[0] == "s") or (b and b[0] == "s"):
		return max(base, SCREEN_GAP)
	if a and b:
		return max(base, ERASE_GAP)
	return max(base, TRAVEL_GAP)


def apply_leads(s, story_dir, seconds=None, starts=None):
	"""照分頁、換頁空檔、hold／lead 重排句界，就地改 s 並回傳。

	seconds 是每句實際講多久（f5_story 給實測值）；None 表示草稿，沿用骨架估計的長度。
	starts 給了就依序填入每句未四捨五入的起點，f5_story 用它把音檔貼進總軌。
	"""
	pages, screens = make_pages(s, story_dir)
	where = {i: ("p", n) for n, pg in enumerate(pages) for i in pg}
	where.update({i: ("s", k) for k, sc in enumerate(screens) for i in sc["lines"]})
	holds, leads = load_pauses(story_dir, "holds.json"), load_pauses(story_dir, "leads.json")
	if seconds is None:
		seconds = [L["end"] - L["start"] for L in s["lines"]]
	# 句間停頓要在改寫任何句界之前取，否則讀到的是上一句的實測結尾，每句都會落回骨架時間而互相蓋掉
	gaps = [0.0] + [b["start"] - a["end"] for a, b in zip(s["lines"], s["lines"][1:])]
	knots = []
	t = s["lines"][0]["start"]
	prev_end = None
	for k, line in enumerate(s["lines"]):
		if k:
			t = prev_end + gap_after(s["lines"][k - 1]["i"], line["i"], where, gaps[k]) \
				+ holds.get(s["lines"][k - 1]["i"], 0.0)
		t += leads.get(line["i"], 0.0)
		line["lead"], line["hold"] = leads.get(line["i"], 0.0), holds.get(line["i"], 0.0)
		start, end = t, t + seconds[k]
		a, b = line["start"], line["end"]
		line["words"] = [[w, round(start + (wt - a) * (end - start) / (b - a), 3)] for w, wt in line["words"]]
		knots += [(a, start), (b, end)]
		line["start"], line["end"] = round(start, 3), round(end, 3)
		prev_end = end
		if starts is not None:
			starts.append(start)

	f = remap(knots)
	for ch in s["chapters"]:
		ch["start"], ch["end"] = round(f(ch["start"]), 3), round(f(ch["end"]), 3)
	if s.get("end"):
		s["end"]["start"] = round(f(s["end"]["start"]), 3)
	if s.get("recap"):
		length = s["recap"]["end"] - s["recap"]["start"]
		s["recap"]["start"] = round(recap_start(f(s["recap"]["start"]), s["lines"][-1]["end"]), 3)
		s["recap"]["end"] = round(s["recap"]["start"] + length, 3)
	s["duration"] = round(max(s["recap"]["end"] if s.get("recap") else 0, f(s["duration"])), 3)
	s["pages"] = pages
	s["screens"] = screens
	return s


def main():
	if len(sys.argv) != 2:
		print(__doc__)
		return 2
	story_dir = sys.argv[1]
	path = os.path.join(story_dir, "story.json")
	dry_path = os.path.join(story_dir, "story.dry.json")
	current = json.load(open(path, encoding="utf-8"))
	if not current.get("draft"):
		raise SystemExit("story.json 已經配過音，pages.py 只處理草稿；重排配音版請跑 f5_story.py")
	# 還沒排過的草稿才是骨架；排過的再存一次就會越疊越歪
	if not current.get("paged"):
		shutil.copy(path, dry_path)
	s = apply_leads(json.load(open(dry_path, encoding="utf-8")), story_dir)
	s["paged"] = True
	json.dump(s, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
	print(f"story.json（草稿）：{s['duration']:.1f}s，{len(s['pages'])} 頁、{len(s['screens'])} 段電腦畫面")
	return 0


if __name__ == "__main__":
	sys.exit(main())
