"""固定版本外部候選逐格匯出；FFmpeg 失敗、幀數或尺寸不符即失敗。"""
import argparse
import hashlib
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
	ap = argparse.ArgumentParser()
	ap.add_argument('--grammar', choices=['y3_whiteboard','y5_kinetic_type'], nargs='+', default=['y3_whiteboard','y5_kinetic_type'])
	args = ap.parse_args()
	reports = []
	with sync_playwright() as p:
		browser = p.chromium.launch()
		page = browser.new_page(viewport={"width":1920,"height":1080})
		for grammar in args.grammar:
			started = time.time()
			page.goto((HERE / "candidates.html").as_uri() + f"?export&grammar={grammar}")
			page.wait_for_function("window.__ready || window.__failed")
			assert not page.evaluate("window.__failed || null")
			frames = math.ceil(FPS * DURATION)
			video = OUT / f"C-{grammar}.mp4"
			encoder = subprocess.Popen(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","image2pipe","-vcodec","png","-r",str(FPS),"-i","pipe:0","-i",str(OUT / "candidate-audio.wav"),"-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","fast","-crf","18","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k","-movflags","+faststart",str(video)],stdin=subprocess.PIPE)
			samples = []
			for k in range(frames):
				t = k / FPS
				info = page.evaluate("t=>renderFrame(t)", t)
				encoder.stdin.write(page.locator("#c").screenshot(type="png"))
				if k in {0,round(.55*FPS),round(2*FPS),round(7.58*FPS),round(10*FPS),frames-1}:
					samples.append(info)
			encoder.stdin.close()
			assert encoder.wait() == 0
			# 同一時刻先後／倒序 seek 必須得到相同像素。
			page.evaluate("renderFrame(10)")
			one = page.locator("#c").screenshot()
			page.evaluate("renderFrame(2)")
			page.evaluate("renderFrame(10)")
			two = page.locator("#c").screenshot()
			assert one == two
			(OUT / f"{grammar}.png").write_bytes(one)
			probe = json.loads(subprocess.run(["ffprobe","-v","error","-count_frames","-show_streams","-show_format","-of","json",str(video)],check=True,capture_output=True,text=True).stdout)
			v = next(s for s in probe["streams"] if s["codec_type"] == "video")
			assert int(v["nb_read_frames"]) == frames and [v["width"],v["height"]] == [1920,1080]
			decode = subprocess.run(["ffmpeg","-hide_banner","-v","error","-xerror","-i",str(video),"-f","null","-"],capture_output=True,text=True)
			assert decode.returncode == 0 and not decode.stderr
			report = {"grammar":grammar,"duration":float(probe["format"]["duration"]),"frames":frames,"fps":FPS,"width":1920,"height":1080,"audio_stream_present":any(s["codec_type"]=="audio" for s in probe["streams"]),"full_decode":True,"seek_deterministic":True,"png_sha256":hashlib.sha256(one).hexdigest(),"render_seconds":round(time.time()-started,1),"samples":samples}
			(OUT / f"{grammar}.measurements.json").write_text(json.dumps(report,ensure_ascii=False,indent="\t")+"\n")
			reports.append({k:v for k,v in report.items() if k!='samples'})
		browser.close()
	print(json.dumps(reports,ensure_ascii=False))


if __name__ == "__main__":
	main()
