#!/usr/bin/env python3
"""岚叔 explainer 的 story（--dry 骨架）＋F5 逐句配音 → 實測時間的 story.json 與 narration.wav。

用法：
  (cd <lanshu>/explainer && python3 tools/story.py <story 資料夾> --dry)     # 先產骨架
  ~/.venvs/f5tts/bin/python video_engine/explainer/f5_story.py <story 資料夾>

岚叔的 --audio 是從錄音的停頓找句界、逐字時間用權重估；我們的 F5 本來就有每句的實際長度，
所以句界用實測、句間停頓沿用骨架的設計、句內逐字只按比例縮放骨架的估計。
骨架第一次讀到時另存成 story.dry.json，之後一律從它重建，重跑不會越疊越歪。

分頁：story 資料夾有 pages.json（例如 [[1],[2],[3,4]]，結語句不列）就照它分，沒有就每章兩句一頁。
screens.json（例如 [{"lines": [8, 9], "kind": "vscode"}]）列出改在電腦畫面上演的句子，它們不進 pages。
recap.json（{"say": "..."}）給複習頁一句旁白；岚叔的複習頁原本無聲。
seeds.json（例如 {"3": 11}）指定個別句子的 seed：同一句換 seed 停頓與語速差很多，人耳挑過的寫在這裡才重跑得出來。
picks.json 是 f5_pick.py 機器挑的 seed（多 seed＋ASR／句尾音高打分），seeds.json 有寫的句子以 seeds.json 為準。
holds.json（例如 {"15": 1.0}）在該句講完後多停幾秒：操作步驟點下去之後，留時間讓學生看到結果再往下講。
leads.json（例如 {"6": 2.0}）在該句開口前空幾秒給 beats 先把圖畫完（先畫後講，使用者 2026-10-25）；寫進 story.json 該句的 lead，
黑板鏡頭照 start − lead 到位；hold 也寫進 story.json，換頁照 end ＋ hold 才出發。
兩者寫進 story.json 的 pages／screens，黑板照它擺版。粉筆頁換頁用板擦擦掉、其餘直線平移，句間至少留 TRAVEL_GAP；
進出電腦畫面要畫螢幕框再推近，至少留 SCREEN_GAP。同頁句間照骨架，不另加停頓。
"""
import json
import os
import shutil
import sys

import numpy as np
import soundfile as sf
import torch
import torchaudio

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

from synth_f5 import CKPT, EN_REF, EN_REF_TEXT, EN_SEED, REF, REF_TEXT, SEED  # noqa: E402
from tts_f5 import SR, F5Narrator  # noqa: E402

OUT_SR = 48000
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
		return float(np.interp(t, xs, ys))
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


def main():
	if len(sys.argv) != 2:
		print(__doc__)
		return 2
	story_dir = sys.argv[1]
	path = os.path.join(story_dir, "story.json")
	dry_path = os.path.join(story_dir, "story.dry.json")
	current = json.load(open(path, encoding="utf-8"))
	if current.get("draft"):
		shutil.copy(path, dry_path)
	if not os.path.exists(dry_path):
		raise SystemExit("找不到骨架：先跑 tools/story.py <story> --dry")
	s = json.load(open(dry_path, encoding="utf-8"))

	voices = {"en_lead": (EN_REF, EN_REF_TEXT, EN_SEED)} if EN_REF.exists() else {}
	voice = F5Narrator(CKPT, REF, REF_TEXT, seed=SEED, voices=voices, cache_dir=os.path.join(story_dir, "audio", "f5"))

	pages, screens = make_pages(s, story_dir)
	where = {i: ("p", n) for n, pg in enumerate(pages) for i in pg}
	where.update({i: ("s", k) for k, sc in enumerate(screens) for i in sc["lines"]})
	# 句間停頓要在改寫任何句界之前取，否則讀到的是上一句的實測結尾，每句都會落回骨架時間而互相蓋掉
	gaps = [0.0] + [b["start"] - a["end"] for a, b in zip(s["lines"], s["lines"][1:])]
	knots, clips, report = [], [], []
	sp = os.path.join(story_dir, "seeds.json")
	holds, leads = load_pauses(story_dir, "holds.json"), load_pauses(story_dir, "leads.json")
	# 機器挑的（f5_pick.py）先放，人耳指定的 seeds.json 蓋過它；句子改過字的挑選結果不算
	pk = os.path.join(story_dir, "picks.json")
	picks = json.load(open(pk, encoding="utf-8")) if os.path.exists(pk) else {}
	text_of = {L["i"]: L["text"] for L in s["lines"]}
	line_seed = {int(k): v["seed"] for k, v in picks.items() if text_of.get(int(k)) == v["text"]}
	if os.path.exists(sp):
		line_seed.update({int(k): v for k, v in json.load(open(sp, encoding="utf-8")).items()})
	t = s["lines"][0]["start"]
	for k, line in enumerate(s["lines"]):
		if k:
			t = clips[-1][0] + len(clips[-1][1]) / SR + gap_after(s["lines"][k - 1]["i"], line["i"], where, gaps[k]) \
				+ holds.get(s["lines"][k - 1]["i"], 0.0)
		t += leads.get(line["i"], 0.0)
		line["lead"], line["hold"] = leads.get(line["i"], 0.0), holds.get(line["i"], 0.0)
		seeds = {c: line_seed[line["i"]] for c in voice.chunks(line["text"])} if line["i"] in line_seed else None
		audio, recs = voice.speak(line["text"], seeds=seeds, pad=(0, 0))
		start, end = t, t + len(audio) / SR
		a, b = line["start"], line["end"]
		line["words"] = [[w, round(start + (wt - a) * (end - start) / (b - a), 3)] for w, wt in line["words"]]
		knots += [(a, start), (b, end)]
		line["start"], line["end"] = round(start, 3), round(end, 3)
		clips.append((start, audio))
		report.append({"i": line["i"], "text": line["text"], "seconds": round(end - start, 2),
			"voice": [r["voice"] for r in recs], "spoken": [r["spoken"] for r in recs],
			"warnings": [w for r in recs for w in r["warnings"]]})
		print(f"{line['i']:>2} {end - start:4.1f}s {'／'.join(r['voice'] for r in recs)} {line['text'][:22]}", flush=True)

	f = remap(knots)
	for ch in s["chapters"]:
		ch["start"], ch["end"] = round(f(ch["start"]), 3), round(f(ch["end"]), 3)
	if s.get("end"):
		s["end"]["start"] = round(f(s["end"]["start"]), 3)
	if s.get("recap"):
		length = s["recap"]["end"] - s["recap"]["start"]
		s["recap"]["start"] = round(recap_start(f(s["recap"]["start"]), s["lines"][-1]["end"]), 3)
		s["recap"]["end"] = round(s["recap"]["start"] + length, 3)
	rp = os.path.join(story_dir, "recap.json")
	if s.get("recap") and os.path.exists(rp):
		say = json.load(open(rp, encoding="utf-8"))["say"]
		audio, recs = voice.speak(say, pad=(0, 0))
		at, s["recap"]["end"] = recap_window(s["recap"]["start"], s["recap"]["end"], len(audio) / SR)
		s["recap"]["end"] = round(s["recap"]["end"], 3)
		s["recap"]["say"] = {"text": say, "start": round(at, 3), "end": round(at + len(audio) / SR, 3)}
		clips.append((at, audio))
		print(f"複習頁 {len(audio) / SR:4.1f}s {say[:22]}", flush=True)
	s["duration"] = round(max(s["recap"]["end"] if s.get("recap") else 0, f(s["duration"])), 3)
	s["pages"] = pages
	s["screens"] = screens
	s["draft"] = False
	s["timing"] = "f5: 句界實測，句內逐字依骨架估計等比縮放"
	s["voice"] = "F5-TTS 王老師 v4"

	master = np.zeros(int(round(s["duration"] * SR)) + SR, np.float32)
	for start, audio in clips:
		i = int(round(start * SR))
		master[i:i + len(audio)] = audio[: max(0, len(master) - i)]
	master = master[: int(round(s["duration"] * SR))]
	up = torchaudio.functional.resample(torch.from_numpy(master), SR, OUT_SR).numpy()
	out_wav = os.path.join(story_dir, s["narration"])
	os.makedirs(os.path.dirname(out_wav), exist_ok=True)
	sf.write(out_wav, up, OUT_SR, subtype="PCM_16")
	json.dump(s, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
	json.dump(report, open(os.path.join(story_dir, "f5_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent="\t")
	print(f"story.json：{s['duration']:.1f}s，{len(s['lines'])} 句；{out_wav}。成品要人耳聽過才算數。")
	return 0


if __name__ == "__main__":
	sys.exit(main())
