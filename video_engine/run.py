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
import re
import subprocess
import sys
import time

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


def main():
	if len(sys.argv) < 2:
		print(__doc__)
		return 2
	material = sys.argv[1]
	argv = sys.argv[2:]

	def opt(name, default=None):
		return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default

	start = STAGES.index(opt("--from", "lesson"))
	stop = STAGES.index(opt("--until", "video"))
	sec = opt("--sec")

	lesson_id = re.sub(r"[^a-z0-9_]", "_", os.path.splitext(os.path.basename(material))[0].lower())
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
