#!/usr/bin/env python3
"""審稿分鏡表：出片前給人看的一頁 HTML。

用法：.venv/bin/python video_engine/storyboard.py <lesson.json> <actions.json> [輸出目錄]

每頁一張投影片圖，右邊列出該頁的動作序列與講稿。已合成的段落會標出實際秒數
與驗收狀態，還沒合成的顯示估算值。看完直接改 actions.json 的講稿即可。
"""
import base64
import io
import json
import os
import sys

from PIL import Image

CHARS_PER_SEC = 6.35
LABEL = {"speech": "講稿", "spotlight": "聚光", "laser": "指點",
	"reveal": "浮現", "camera": "鏡頭", "pause": "留白"}


def thumb(path, width=760):
	"""縮圖轉 base64，單一 HTML 檔可直接寄給別人看"""
	im = Image.open(path).convert("RGB")
	im.thumbnail((width, width))
	buf = io.BytesIO()
	im.save(buf, "JPEG", quality=82)
	return base64.b64encode(buf.getvalue()).decode()


def esc(s):
	return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def main():
	if len(sys.argv) < 3:
		print(__doc__)
		return 2
	lesson = json.load(open(sys.argv[1], encoding="utf-8"))
	actions = json.load(open(sys.argv[2], encoding="utf-8"))
	out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
		os.path.dirname(os.path.abspath(__file__)), "out", lesson["lesson_id"]
	)
	layout = json.load(open(os.path.join(out_dir, "layout.json"), encoding="utf-8"))
	dur_path = os.path.join(out_dir, "durations.json")
	durations = json.load(open(dur_path, encoding="utf-8")) if os.path.exists(dur_path) else {}
	pages = {s["slide_id"]: s for s in layout["slides"]}

	rows, total, synthed = [], 0.0, 0
	for slide in actions["slides"]:
		sid = slide["slide_id"]
		page = pages[sid]
		items, page_sec = [], 0.0
		for i, a in enumerate(slide["actions"]):
			kind = a["type"]
			if kind == "speech":
				rec = durations.get(f"{sid}#{i}")
				if rec:
					synthed += 1
					sec = rec["duration"]
					ok = rec.get("accepted", True)
					mark = f'<span class="ok">{sec:.1f}s</span>' if ok else \
						f'<span class="bad">{sec:.1f}s 未通過</span>'
					gap = rec.get("max_gap", 0)
					if gap > 0.8:
						mark += f' <span class="warn">空白 {gap:.1f}s</span>'
				else:
					sec = len(a["text"]) / CHARS_PER_SEC
					mark = f'<span class="est">約 {sec:.1f}s（未合成）</span>'
				page_sec += sec
				items.append(f'<div class="act sp"><span class="k">講稿</span>'
					f'<span class="tx">{esc(a["text"])}</span>{mark}</div>')
			elif kind == "pause":
				page_sec += a.get("ms", 300) / 1000
				items.append(f'<div class="act"><span class="k">留白</span>'
					f'<span class="tx dim">{a.get("ms", 300)} ms</span></div>')
			else:
				tgt = a.get("target") or ("回全景" if a.get("reset") else "")
				extra = f'　×{a["scale"]}' if kind == "camera" and a.get("scale") else ""
				items.append(f'<div class="act"><span class="k">{LABEL.get(kind, kind)}</span>'
					f'<span class="tx dim">{esc(tgt)}{extra}</span></div>')
		total += page_sec
		rows.append(f"""<section>
	<div class="shot"><img src="data:image/jpeg;base64,{thumb(page["png_full"])}" alt="{sid}"></div>
	<div class="script">
		<h2>{sid}　<span class="sec">{page_sec:.1f} 秒</span></h2>
		{''.join(items)}
	</div>
</section>""")

	speech_n = sum(1 for s in actions["slides"] for a in s["actions"] if a["type"] == "speech")
	html = f"""<title>{lesson['title']}　審稿分鏡</title>
<style>
	:root {{ --bg:#F4EDE2; --card:#FBF7F0; --ink:#3B322A; --soft:#8A7A68;
		--rule:#DFD2BF; --accent:#B85C38; --ok:#2C7F52; --warn:#B8862F; }}
	body {{ background:var(--bg); color:var(--ink); margin:0; padding:32px;
		font-family:"Noto Sans TC","PingFang TC",system-ui,sans-serif; line-height:1.7; }}
	header {{ max-width:1180px; margin:0 auto 28px; border-bottom:2px solid var(--ink); padding-bottom:14px; }}
	h1 {{ margin:0 0 6px; font-size:30px; }}
	.meta {{ color:var(--soft); font-size:14px; }}
	section {{ max-width:1180px; margin:0 auto 22px; background:var(--card); border:1px solid var(--rule);
		border-radius:6px; padding:18px; display:grid; grid-template-columns:minmax(280px,42%) 1fr; gap:22px; }}
	@media (max-width:900px) {{ section {{ grid-template-columns:1fr; }} }}
	.shot img {{ width:100%; border:1px solid var(--rule); border-radius:4px; display:block; }}
	h2 {{ margin:0 0 12px; font-size:19px; }}
	.sec {{ color:var(--soft); font-size:14px; font-weight:400; }}
	.act {{ display:flex; gap:10px; align-items:baseline; padding:7px 0; border-bottom:1px dashed var(--rule); }}
	.act:last-child {{ border-bottom:none; }}
	.act.sp {{ background:rgba(242,217,160,.30); margin:0 -8px; padding:9px 8px; border-radius:3px; }}
	.k {{ flex:0 0 42px; font-size:12px; color:var(--accent); letter-spacing:.05em; }}
	.tx {{ flex:1; }}
	.dim {{ color:var(--soft); font-family:ui-monospace,monospace; font-size:13px; }}
	.ok {{ color:var(--ok); font-size:12px; white-space:nowrap; }}
	.bad {{ color:#B03A2E; font-size:12px; font-weight:700; white-space:nowrap; }}
	.warn {{ color:var(--warn); font-size:12px; white-space:nowrap; }}
	.est {{ color:var(--soft); font-size:12px; white-space:nowrap; }}
</style>
<header>
	<h1>{esc(lesson['title'])}</h1>
	<div class="meta">{len(actions['slides'])} 頁　{speech_n} 段講稿（已合成 {synthed}）
		預估全長 {total:.0f} 秒　改講稿只會重生該段，其餘不動</div>
</header>
{''.join(rows)}
"""
	path = os.path.join(out_dir, "storyboard.html")
	open(path, "w", encoding="utf-8").write(html)
	print(f"分鏡表：{path}")
	print(f"{len(actions['slides'])} 頁、{speech_n} 段講稿、預估 {total:.0f} 秒")
	return 0


if __name__ == "__main__":
	sys.exit(main())
