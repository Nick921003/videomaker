"""以指定音訊時間重繪 A+C Canvas，匯出含旁白的 1080p MP4。"""
import argparse
import asyncio
import base64
import json
import math
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen

import websockets


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video_engine/out/state_change_ac_20261001"
FPS = 24


class CDP:
	def __init__(self, socket):
		self.socket = socket
		self.sequence = 0

	async def call(self, method, params=None):
		self.sequence += 1
		request_id = self.sequence
		await self.socket.send(json.dumps({"id": request_id, "method": method, "params": params or {}}))
		while True:
			message = json.loads(await self.socket.recv())
			if message.get("id") == request_id:
				if "error" in message:
					raise RuntimeError(message["error"])
				return message.get("result", {})

	async def evaluate(self, expression):
		result = await self.call("Runtime.evaluate", {
			"expression": expression, "returnByValue": True, "awaitPromise": True,
		})
		if "exceptionDetails" in result:
			raise RuntimeError(result["exceptionDetails"])
		return result["result"].get("value")


def endpoint(cdp_url, path, method="GET", parse_json=True):
	with urlopen(Request(cdp_url.rstrip("/") + path, method=method), timeout=10) as response:
		body = response.read()
		return json.loads(body) if parse_json else body.decode("utf-8")


async def export(out, cdp_url):
	timeline = json.loads((out / "movie_timeline.json").read_text(encoding="utf-8"))
	duration = float(timeline["duration"])
	if not math.isfinite(duration) or duration <= 0:
		raise ValueError("movie_timeline.json 的 duration 必須為正數")
	html = (out / "movie.html").resolve()
	audio = out / "master.wav"
	if not html.is_file() or not audio.is_file():
		raise FileNotFoundError("需要 movie.html 與 master.wav")
	video = out / "c_string_ac.mp4"
	partial = out / "c_string_ac.part.mp4"
	if video.exists() or partial.exists():
		raise FileExistsError("輸出已存在；請先保留既有產物並選擇新的輸出目錄")
	target = endpoint(cdp_url, "/json/new?about:blank", "PUT")
	frames = math.ceil(duration * FPS)
	started = time.monotonic()
	process = None
	try:
		async with websockets.connect(target["webSocketDebuggerUrl"], max_size=16 * 1024 * 1024) as socket:
			cdp = CDP(socket)
			await cdp.call("Page.enable")
			await cdp.call("Runtime.enable")
			await cdp.call("Page.navigate", {"url": html.as_uri()})
			for attempt in range(200):
				ready = await cdp.evaluate("typeof window.renderMovie === 'function' && document.readyState === 'complete'")
				if ready:
					break
				await asyncio.sleep(0.05)
			else:
				raise RuntimeError("movie.html 未提供 window.renderMovie")
			await cdp.evaluate("document.fonts.ready.then(() => true)")
			size = await cdp.evaluate("""(() => {
				const canvas = window.sourceCanvas || document.getElementById('sourceCanvas');
				if (!canvas) throw new Error('找不到 sourceCanvas');
				canvas.width = 1920;
				canvas.height = 1080;
				const ctx = canvas.getContext('2d');
				const original = ctx.setTransform.bind(ctx);
				// 保留 1280×720 的世界座標，直接以高解析度重繪向量與文字。
				ctx.setTransform = function(a, b, c, d, e, f) {
					if (typeof a === 'object') {
						return original(a.a * 1.5, a.b * 1.5, a.c * 1.5, a.d * 1.5, a.e * 1.5, a.f * 1.5);
					}
					return original(a * 1.5, b * 1.5, c * 1.5, d * 1.5, e * 1.5, f * 1.5);
				};
				window.__exportCanvas = canvas;
				return [canvas.width, canvas.height];
			})()""")
			if size != [1920, 1080]:
				raise RuntimeError(f"Canvas 尺寸錯誤：{size}")
			command = [
				"ffmpeg", "-hide_banner", "-n", "-f", "image2pipe", "-vcodec", "mjpeg",
				"-framerate", str(FPS), "-i", "pipe:0", "-i", str(audio),
				"-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "fast",
				"-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
				"-movflags", "+faststart", "-shortest", "-t", str(duration), str(partial),
			]
			with (out / "export_ffmpeg.log").open("w", encoding="utf-8") as log:
				process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=log)
				try:
					for frame in range(frames):
						t = frame / FPS
						data_url = await cdp.evaluate(
							f"window.renderMovie({t!r}); window.__exportCanvas.toDataURL('image/jpeg', 0.95)"
						)
						if not isinstance(data_url, str) or not data_url.startswith("data:image/jpeg;base64,"):
							raise RuntimeError(f"第 {frame} 格無 JPEG")
						process.stdin.write(base64.b64decode(data_url.split(",", 1)[1], validate=True))
						if (frame + 1) % 120 == 0 or frame + 1 == frames:
							print(f"frames {frame + 1}/{frames}; audio {t:.2f}/{duration:.2f}s; elapsed {time.monotonic() - started:.1f}s", flush=True)
					process.stdin.close()
					status = process.wait()
					if status:
						raise RuntimeError(f"FFmpeg exit {status}；詳見 export_ffmpeg.log")
				finally:
					if process.poll() is None:
						process.terminate()
						process.wait()
		partial.rename(video)
		print(f"exported {video}; {frames} frames; {duration:.3f}s", flush=True)
	finally:
		endpoint(cdp_url, "/json/close/" + target["id"], parse_json=False)


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--out", type=Path, default=OUT)
	parser.add_argument("--cdp", default="http://127.0.0.1:9334")
	args = parser.parse_args()
	asyncio.run(export(args.out.resolve(), args.cdp))


if __name__ == "__main__":
	main()
