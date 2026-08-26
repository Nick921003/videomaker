#!/usr/bin/env python3
"""從本機真的跑過的產出，抽出回歸測試需要的兩份 JSON 並洗掉絕對路徑。

用法：.venv/bin/python tests/fixtures/regression/make_fixtures.py

只有在 compile_timeline.py 的輸入契約改變時才需要重跑。
洗路徑是必要的：原檔裡的 png / wav 是絕對路徑，含產生者的家目錄。
compile_timeline 只把這些字串抄進時間軸、從不開啟，所以換成佔位字串
不影響任何行為。
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
OUT = os.path.join(ROOT, "video_engine", "out")
PLACEHOLDER = "FIXTURE"


def scrub(obj):
	"""把任何絕對路徑換成佔位字串，其餘原封不動。

	原本只洗 ROOT（本專案根目錄）這一種前綴不夠：durations.json 的 wav 欄位是
	synth.py 執行當下累積的快取，某次 synth.py 曾被指到別的專案目錄下執行
	（真實發生過，不是假設——c_struct/durations.json 裡有 16 筆 wav 路徑
	是 /home/<user>/projects/GPT-SoVITS/video_engine/out/... ，來自語音模型
	所在的另一個專案），那筆快取的絕對路徑前綴就不是 ROOT，逃過只認 ROOT
	的洗法，把使用者家目錄原樣留在委交的 fixture 裡。這裡改成不管前綴是
	什麼，只要是絕對路徑就洗：找得到 video_engine/ 這個地標就留它之後的
	部分（還能看出是哪個階段的產出，方便除錯），找不到就只留檔名。
	"""
	if isinstance(obj, dict):
		return {k: scrub(v) for k, v in obj.items()}
	if isinstance(obj, list):
		return [scrub(v) for v in obj]
	if isinstance(obj, str) and obj.startswith("/"):
		marker = "video_engine/"
		idx = obj.find(marker)
		tail = obj[idx:] if idx != -1 else os.path.basename(obj)
		return f"{PLACEHOLDER}/{tail}"
	return obj


def main():
	for lesson_id in ("c_struct", "c_string"):
		src = os.path.join(OUT, lesson_id)
		dst = os.path.join(HERE, lesson_id)
		os.makedirs(dst, exist_ok=True)
		for name in ("layout.json", "durations.json"):
			with open(os.path.join(src, name), encoding="utf-8") as f:
				data = json.load(f)
			with open(os.path.join(dst, name), "w", encoding="utf-8") as f:
				json.dump(scrub(data), f, ensure_ascii=False, indent="\t")
		print(f"寫好 {dst}")


if __name__ == "__main__":
	main()
