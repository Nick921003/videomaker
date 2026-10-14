"""只表達試片的 C 字串狀態；尾端資料不參與讀取。"""


def output_at(cells, count):
	result = []
	for cell in cells[:count]:
		if cell == "\0":
			break
		result.append(cell)
	return "".join(result)


def validate_beats(beats):
	expected = ["setup", "copy"] + ["scan"] * 5 + ["stop", "summary", "question"]
	if [beat.get("phase") for beat in beats] != expected:
		raise ValueError("分鏡 phase 順序不符合連續讀取")
	for index, beat in enumerate(beats[2:7]):
		if beat.get("index") != index or beat.get("output_after") != output_at(list("Alice") + ["\0"], index+1):
			raise ValueError(f"scan 狀態錯誤：{index}")
	stop = beats[7]
	if stop.get("index") != 5 or stop.get("output_after") != "Alice":
		raise ValueError("stop 必須在 NUL，輸出保持 Alice")
