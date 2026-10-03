#!/usr/bin/env python3
"""播放器目錄 → mp4。seek(t) 是純函式，所以影格切段平行渲染、各自編碼後串接。

用法（需 webwright venv 的 Playwright）：
  ~/.local/share/pipx/venvs/webwright/bin/python video_engine/board/export.py <播放器目錄> <輸出.mp4> [--fps 24] [--workers 4]

音訊預設取播放器目錄裡的 audio.*（build.py --audio 放進去的）。
"""
import argparse
import glob
import json
import math
import os
import subprocess
import sys
import tempfile
import time

W, H = 1920, 1080


def render_segment(player_dir, start, end, fps, crf, seg_path):
	from playwright.sync_api import sync_playwright
	enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe", "-vcodec", "png",
		"-r", str(fps), "-i", "pipe:0", "-c:v", "libx264", "-preset", "fast", "-crf", str(crf), "-pix_fmt", "yuv420p", seg_path],
		stdin=subprocess.PIPE)
	try:
		with sync_playwright() as p:
			browser = p.chromium.launch()
			page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
			page.goto("file://" + os.path.join(player_dir, "player.html") + "?export")
			page.wait_for_function("window.boardReady === true", timeout=60000)
			if page.evaluate("window.boardFailed || null"):
				raise RuntimeError(page.evaluate("window.boardFailed"))
			canvas = page.locator("#board")
			for k in range(start, end):
				info = page.evaluate("t => board.seek(t)", k / fps)
				if info["errors"]:
					raise RuntimeError(f"影格 {k}：{info['errors']}")
				enc.stdin.write(canvas.screenshot(type="png"))
			browser.close()
	finally:
		enc.stdin.close()
		if enc.wait() != 0:
			raise RuntimeError(f"ffmpeg 編碼失敗：{seg_path}")


def main():
	ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
	ap.add_argument("player_dir")
	ap.add_argument("out")
	ap.add_argument("--fps", type=int, default=24)
	ap.add_argument("--workers", type=int, default=4)
	ap.add_argument("--crf", type=int, default=18)
	ap.add_argument("--audio")
	ap.add_argument("--segment", nargs=3, type=int, metavar=("START", "END", "INDEX"), help=argparse.SUPPRESS)
	ap.add_argument("--seg-dir", help=argparse.SUPPRESS)
	args = ap.parse_args()
	player_dir = os.path.abspath(args.player_dir)
	if args.segment:
		start, end, idx = args.segment
		render_segment(player_dir, start, end, args.fps, args.crf, os.path.join(args.seg_dir, f"seg{idx:03d}.mp4"))
		return

	with open(os.path.join(player_dir, "board_data.js"), encoding="utf-8") as f:
		data = json.loads(f.read().removeprefix("window.BOARD_DATA = ").rstrip().rstrip(";"))
	duration = data["timeline"]["duration"]
	frames = math.ceil(duration * args.fps)
	audio = args.audio or next(iter(glob.glob(os.path.join(player_dir, "audio.*"))), None)
	workers = max(1, min(args.workers, frames // args.fps or 1))
	bounds = [round(frames * i / workers) for i in range(workers + 1)]
	began = time.time()
	with tempfile.TemporaryDirectory() as seg_dir:
		procs = [subprocess.Popen([sys.executable, os.path.abspath(__file__), player_dir, args.out, "--fps", str(args.fps), "--crf", str(args.crf),
			"--segment", str(bounds[i]), str(bounds[i + 1]), str(i), "--seg-dir", seg_dir]) for i in range(workers)]
		failed = [i for i, p in enumerate(procs) if p.wait() != 0]
		if failed:
			sys.exit(f"第 {failed} 段渲染失敗")
		listing = os.path.join(seg_dir, "list.txt")
		with open(listing, "w") as f:
			f.writelines(f"file '{os.path.join(seg_dir, f'seg{i:03d}.mp4')}'\n" for i in range(workers))
		cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing]
		if audio:
			cmd += ["-i", audio, "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "160k"]
		cmd += ["-c:v", "copy", "-movflags", "+faststart", args.out]
		subprocess.run(cmd, check=True)
	elapsed = time.time() - began
	probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
		"-show_entries", "stream=width,height,nb_read_packets,r_frame_rate", "-of", "json", args.out], capture_output=True, text=True, check=True).stdout)["streams"][0]
	report = {"video": os.path.abspath(args.out), "duration": duration, "fps": args.fps, "frames_expected": frames,
		"frames_encoded": int(probe["nb_read_packets"]), "size": [probe["width"], probe["height"]], "workers": workers,
		"render_seconds": round(elapsed, 1), "audio": audio}
	with open(os.path.splitext(args.out)[0] + ".export.json", "w", encoding="utf-8") as f:
		json.dump(report, f, ensure_ascii=False, indent=1)
	print(json.dumps(report, ensure_ascii=False))
	if report["frames_encoded"] != frames or report["size"] != [W, H]:
		sys.exit("影格數或尺寸不符")


if __name__ == "__main__":
	main()
