"""把已保存的模型分鏡與字幕嵌入單一HTML；不呼叫模型或TTS。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "video_engine/out/state_change_scenes_20261001"
FIRST = ROOT / "video_engine/out/state_change_pilot_20261001"
NATURAL = ROOT / "video_engine/out/state_change_natural_20261001"


def load(path):
	return json.loads(path.read_text(encoding="utf-8"))


def build():
	current = load(OUT / "claude_usage.json")["usage"]
	narrative = load(NATURAL / "claude_usage.json")["usage"]
	gemini = load(FIRST / "gemini_usage.json")
	current_total = current["input_tokens"] + current["output_tokens"]
	narrative_total = narrative["input_tokens"] + narrative["output_tokens"]
	tokens = {"current_run_new_tokens": current_total,
		"attributed_single_preview_tokens": gemini["total_tokens"] + narrative_total + current_total,
		"experiment_total_tokens": load(NATURAL / "token_usage.json")["total_tokens"] + current_total,
		"new_tts_calls": 0}
	board = load(OUT / "scenes.json")
	assert [scene["template"] for scene in board["scenes"]] == ["hook", "formation", "read_stop", "comparison"]
	assert board["scenes"][0]["start"] == 0 and board["scenes"][-1]["end"] == 44
	assert all(a["end"] == b["start"] for a, b in zip(board["scenes"], board["scenes"][1:]))
	scans = [event for scene in board["scenes"] for event in scene["events"] if event["type"] == "scan"]
	assert [event["index"] for event in scans] == list(range(5))
	assert [event["output_after"] for event in scans] == ["Alice"[:n] for n in range(1, 6)]
	data = {"board": board, "cues": load(NATURAL / "pilot_timeline.json")["subtitle_cues"], "tokens": tokens}
	encoded = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
	template = Path(__file__).with_name("scene_samples.html").read_text(encoding="utf-8")
	assert template.count("__LESSON_DATA__") == 1
	(OUT / "scene_samples.html").write_text(template.replace("__LESSON_DATA__", encoded), encoding="utf-8")
	(OUT / "token_summary.json").write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")
	print(json.dumps(tokens, ensure_ascii=False))


if __name__ == "__main__":
	build()
