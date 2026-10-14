"""Board 關鍵畫面、實測字級、字形、解碼與音畫端點報告。"""
import hashlib
import json
import pathlib
import subprocess
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "out"
sys.path.insert(0, str(ROOT / "video_engine/board"))
from check import sample_times


def main():
	timeline = json.loads((OUT / "B-timeline.json").read_text())
	records, baseline_fonts = [], []
	key_times = {"opening":2,"transition-1-before":13.6,"transition-1-after":15.5,"code-focus":24.5,"output":26.5,"transition-2-before":29.1,"transition-2-after":31.2,"boundary-error":43,"summary":61,"ending":67.3,"tail":69.6}
	with sync_playwright() as p:
		browser = p.chromium.launch()
		page = browser.new_page(viewport={"width":1920,"height":1080})
		page.goto((OUT / "B-player/player.html").as_uri() + "?export")
		page.wait_for_function("window.boardReady")
		for t in sample_times(timeline):
			info = page.evaluate("t=>board.seek(t)", t)
			for b in info["boxes"]:
				if b["role"] in ("text","label") and b["alpha"] >= .99 and info["alpha"].get(b["owner"],0) >= .99 and b["owner"] in info["members"] and not info["moving"] and info["camera"]["settled"]:
					font = b["h"] / 1.24
					records.append({"time":t,"owner":b["owner"],"text":b.get("value"),"role":b["role"],"font_px":round(font,2)})
		for name,t in key_times.items():
			info = page.evaluate("t=>board.seek(t)",t)
			page.locator("#board").screenshot(path=str(OUT / f"B-{name}.png"))
			(OUT / f"B-{name}.frame.json").write_text(json.dumps(info,ensure_ascii=False,indent="\t"))
		page.goto((OUT / "A-player/player.html").as_uri() + "?export")
		page.wait_for_function("window.boardReady")
		baseline_timeline = page.evaluate("window.BOARD_DATA.timeline")
		for t in sample_times(baseline_timeline):
			info = page.evaluate("t=>board.seek(t)", t)
			for b in info["boxes"]:
				if b["role"] in ("text","label") and b["alpha"] >= .99 and info["alpha"].get(b["owner"],0) >= .99 and b["owner"] in info["members"] and not info["moving"] and info["camera"]["settled"]:
					baseline_fonts.append(b["h"] / 1.24)
		page.evaluate("board.seek(26.5)")
		page.locator("#board").screenshot(path=str(OUT / "A-code-focus.png"))
		browser.close()
	font_path = pathlib.Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
	# 使用 repo 已安裝的 fontTools，驗證實際本機繁體字體所有 fixture 字元。
	font_report = subprocess.run([str(ROOT / '.venv/bin/python'),'-c', 'from fontTools.ttLib import TTCollection;import sys,json;f=TTCollection(sys.argv[1]);c=f.fonts[3].getBestCmap();t=open(sys.argv[2]).read();print(json.dumps(sorted(set(ch for ch in t if ord(ch)>32 and ord(ch) not in c)),ensure_ascii=False))',str(font_path),str(OUT / 'B-board.scene.json')],capture_output=True,text=True,check=True)
	missing=json.loads(font_report.stdout)
	assert missing == [], missing
	min_font=min(r['font_px'] for r in records)
	report={"samples":len(sample_times(timeline)),"A_min_still_core_font_px":round(min(baseline_fonts),2),"min_still_core_font_px":min_font,"under_28px":[r for r in records if r['font_px']<28],"subtitle_font_px":40,"local_font":{"path":str(font_path),"sha256":hashlib.sha256(font_path.read_bytes()).hexdigest(),"missing_glyphs":missing},"scene_endpoints":[s['t_enter'] for s in timeline['scenes']],"last_narration_end":timeline['beats'][-1]['t1'],"visual_duration":timeline['duration'],"sentence_boundary_actions":True,"word_level_alignment":"not measured, no word precision claim","key_frames":key_times,"font_records":records}
	(OUT / 'B-measurements.json').write_text(json.dumps(report,ensure_ascii=False,indent="\t")+'\n')
	print(json.dumps({k:v for k,v in report.items() if k not in ('font_records','under_28px')},ensure_ascii=False))
	print('under_28px:',len(report['under_28px']))


if __name__ == '__main__':
	main()
