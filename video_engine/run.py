#!/usr/bin/env python3
"""一行指令：教材 → MP4。

用法：
	.venv/bin/python video_engine/run.py video_engine/materials/c_struct.md
	.venv/bin/python video_engine/run.py <教材> --sec 120        指定目標片長
	.venv/bin/python video_engine/run.py <教材> --from synth     從某階段續跑
	.venv/bin/python video_engine/run.py <教材> --until storyboard  產完分鏡表就停，等人審稿

階段：lesson → slides → actions → validate → synth → storyboard → timeline → video
審稿建議停在 storyboard，確認講稿沒問題再往下跑，因為改講稿只要重生那一段。
"""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest

HERE = os.path.dirname(os.path.abspath(__file__))
# 本專案不含 torch／gradio，所以 LLM SDK 與繪製依賴共用一個 venv 不會衝突
PY = LLM_PY = os.path.join(os.path.dirname(HERE), ".venv/bin/python")
STAGES = ["lesson", "slides", "actions", "validate", "synth", "storyboard", "timeline", "video"]


def run(script, args, label, interpreter=None):
	t0 = time.time()
	print(f"\n\033[1m▶ {label}\033[0m")
	r = subprocess.run([interpreter or PY, os.path.join(HERE, script)] + args)
	if r.returncode != 0:
		raise SystemExit(f"\n{label} 失敗（回傳碼 {r.returncode}），停在這裡")
	print(f"  ── {time.time() - t0:.0f} 秒")


def next_free(path):
	"""同名不覆寫：deck.md 已存在就給 deck_2.md。

	上傳的原始檔與抽出來的 .md 都走這一條。兩邊命名規則不一致的話，
	原始檔被覆寫、抽出來的卻變成 deck_2.md，lesson_id 跟著變成 deck_2，
	materials/ 與 examples/ 會留下一堆對不上的孤兒檔。
	"""
	if not os.path.exists(path):
		return path
	stem, ext = os.path.splitext(path)
	n = 2
	while os.path.exists(f"{stem}_{n}{ext}"):
		n += 1
	return f"{stem}_{n}{ext}"


def resolve_material(path, materials_dir):
	"""非 .md 的來源先抽成純文字落地，手上才有引擎實際讀到的東西可以對照。
	.md 進來原樣出去（冪等）——服務層會分兩段呼叫，第二段不能又落地一次"""
	if os.path.splitext(path)[1].lower() == ".md":
		return path
	text = ingest.extract_text(path)
	os.makedirs(materials_dir, exist_ok=True)
	stem = os.path.splitext(os.path.basename(path))[0]
	out = next_free(os.path.join(materials_dir, f"{stem}.md"))
	with open(out, "w", encoding="utf-8") as f:
		f.write(text)
	return out


def main():
	if len(sys.argv) < 2:
		print(__doc__)
		return 2
	material = resolve_material(sys.argv[1], os.path.join(HERE, "materials"))
	argv = sys.argv[2:]

	def opt(name, default=None):
		return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default

	start = STAGES.index(opt("--from", "lesson"))
	stop = STAGES.index(opt("--until", "video"))
	sec = opt("--sec")

	lesson_id = ingest.lesson_id_for(material)
	lesson = os.path.join(HERE, "examples", f"{lesson_id}.lesson.json")
	actions = os.path.join(HERE, "examples", f"{lesson_id}.actions.json")
	out_dir = os.path.join(HERE, "out", lesson_id)

	print(f"教材　{material}")
	print(f"課程　{lesson_id}")
	print(f"階段　{STAGES[start]} → {STAGES[stop]}")
	t0 = time.time()

	def want(name):
		i = STAGES.index(name)
		return start <= i <= stop

	if want("lesson"):
		run("generate_lesson.py", [material, lesson], "階段 2　教材結構化（LLM）", LLM_PY)
	if want("slides"):
		run("render_slides.py", [lesson, out_dir], "階段 3　投影片繪製與量測")
	if want("actions"):
		run("generate_actions.py", [lesson, actions] + (["--sec", sec] if sec else []),
			"階段 4　動作編排（LLM，內含驗證閘）", LLM_PY)
	if want("validate"):
		run("validate.py", [lesson, actions] + ([sec] if sec else []), "階段 4.5　編排驗證")
	if want("synth"):
		run("synth.py", [lesson, actions, out_dir], "階段 5　語音合成與驗收重試")
	if want("storyboard"):
		run("storyboard.py", [lesson, actions, out_dir], "階段 5.5　審稿分鏡表")
	if want("timeline"):
		run("compile_timeline.py", [lesson, actions, out_dir], "階段 6　時間軸編譯")
	if want("video"):
		run("render_video.py", [lesson, out_dir], "階段 7　影格渲染與封裝")

	print(f"\n\033[1m全部完成，共 {time.time() - t0:.0f} 秒\033[0m")
	print(f"產出目錄　{out_dir}")
	if want("storyboard"):
		print(f"審稿分鏡　{os.path.join(out_dir, 'storyboard.html')}")
	if want("video"):
		print(f"影片　　　{os.path.join(out_dir, lesson_id + '.mp4')}")
	return 0


if __name__ == "__main__":
	sys.exit(main())
