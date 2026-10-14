#!/usr/bin/env python3
"""timeline.json → 可直接開啟的播放器目錄（player.html＋runtime＋資料＋音訊）。

用法：build.py <timeline.json> <輸出目錄> [--audio master.wav] [--theme notebook]

輸出目錄自給自足：拷走就能播放，也是 check.py／export.py 的輸入。
"""
import argparse
import json
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(HERE, "runtime")
THEMES = os.path.join(os.path.dirname(HERE), "themes")


def build(timeline, out_dir, audio=None, theme="notebook"):
	with open(os.path.join(THEMES, f"{theme}.json"), encoding="utf-8") as f:
		theme_data = json.load(f)
	with open(os.path.join(HERE, "catalog.json"), encoding="utf-8") as f:
		catalog = json.load(f)
	os.makedirs(out_dir, exist_ok=True)
	dst_runtime = os.path.join(out_dir, "runtime")
	if os.path.exists(dst_runtime):
		shutil.rmtree(dst_runtime)
	shutil.copytree(RUNTIME, dst_runtime, ignore=shutil.ignore_patterns("player.html"))
	comps = sorted(f for f in os.listdir(os.path.join(RUNTIME, "components")) if f.endswith(".js"))
	tags = "\n".join(f'<script src="runtime/components/{c}"></script>' for c in comps)
	with open(os.path.join(RUNTIME, "player.html"), encoding="utf-8") as f:
		page = f.read().replace("<!-- COMPONENTS -->", tags)
	with open(os.path.join(out_dir, "player.html"), "w", encoding="utf-8") as f:
		f.write(page)
	audio_name = None
	if audio:
		audio_name = "audio" + os.path.splitext(audio)[1]
		shutil.copyfile(audio, os.path.join(out_dir, audio_name))
	data = {"timeline": timeline, "theme": theme_data, "catalog": catalog, "audio": audio_name}
	with open(os.path.join(out_dir, "board_data.js"), "w", encoding="utf-8") as f:
		f.write("window.BOARD_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
	return out_dir


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("timeline")
	ap.add_argument("out_dir")
	ap.add_argument("--audio")
	ap.add_argument("--theme", default="notebook")
	args = ap.parse_args()
	with open(args.timeline, encoding="utf-8") as f:
		timeline = json.load(f)
	build(timeline, args.out_dir, args.audio, args.theme)
	print(os.path.join(args.out_dir, "player.html"))


if __name__ == "__main__":
	main()
