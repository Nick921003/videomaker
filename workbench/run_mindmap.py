"""單元教材 → 概念心智圖與 SVG。"""
from functools import partial
import os
from pathlib import Path
import sys


if __package__ in (None, ""):
	sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("VIDEO_ENGINE_LLM", "google:gemini-3.8-flash")

from studio.mindmap import MindmapError, build_mindmap, render_mindmap_svg
from video_engine.usage import UsageLedger
from workbench._runner import arguments, captured, failure, guard_budget, marker
from workbench.library import safe_path, write_json


def main(argv, complete_json=None) -> int:
	args = arguments(argv, "生成概念心智圖", "unit_dir")
	os.environ.setdefault("VIDEO_ENGINE_LLM", "google:gemini-3.8-flash")
	directory = Path(args.unit_dir).resolve()
	ledger = UsageLedger()
	try:
		material = safe_path(directory, "material.md").read_text(encoding="utf-8")
		if complete_json is None:
			from video_engine.llm import complete_json as complete
			complete_json = partial(complete, stage="mindmap")
		def cj(system, user, schema):
			guard_budget(directory, args.budget_usd, "mindmap", system, user, schema)
			result = captured(ledger, directory, "mindmap", "generate", complete_json, system, user, schema)
			marker("step", "validate")
			return result
		marker("step", "generate")
		mindmap = build_mindmap(material, "整理這份教材的概念與關係", cj)
		marker("step", "render")
		svg = render_mindmap_svg(mindmap, material)
		write_json(safe_path(directory, "mindmap/mindmap.json"), mindmap)
		safe_path(directory, "mindmap/mindmap.svg").write_bytes(svg)
		return 0
	except Exception as exc:
		return failure(exc, MindmapError)


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
