"""匯出嵐叔 v3-notebook 樣片為 MP4。"""
import json
import math
import pathlib
import subprocess
import time
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "out"
FPS = 24
DURATION = 13.42

def main():
	started = time.time()
	video = OUT / "C-lanshu_notebook.mp4"
	frames = math.ceil(FPS * DURATION)
	
	with sync_playwright() as p:
		browser = p.chromium.launch()
		page = browser.new_page(viewport={"width": 1920, "height": 1080})
		page.goto((HERE / "lanshu_notebook.html").as_uri())
		page.wait_for_timeout(1000)
		
		encoder = subprocess.Popen([
			"ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
			"-f", "image2pipe", "-vcodec", "png", "-r", str(FPS), "-i", "pipe:0",
			"-i", str(OUT / "candidate-audio.wav"),
			"-map", "0:v:0", "-map", "1:a:0",
			"-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
			"-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
			str(video)
		], stdin=subprocess.PIPE)
		
		for k in range(frames):
			t = k / FPS
			page.evaluate(f"() => {{ if (window.__timelines && window.__timelines.main) window.__timelines.main.time({t}); }}")
			encoder.stdin.write(page.screenshot(type="png"))
		
		encoder.stdin.close()
		assert encoder.wait() == 0
		browser.close()
	
	probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-show_format", "-of", "json", str(video)], check=True, capture_output=True, text=True).stdout)
	v = next(s for s in probe["streams"] if s["codec_type"] == "video")
	assert int(v["nb_read_frames"]) == frames
	decode = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-i", str(video), "-f", "null", "-"], capture_output=True, text=True)
	assert decode.returncode == 0
	
	print(f"Lanshu notebook video exported: {video} ({frames} frames, {round(time.time() - started, 1)}s)")

if __name__ == "__main__":
	main()
