"""單元教材 → 線上簡報與可編輯 PPTX。"""
from functools import partial
import os
from pathlib import Path
import sys


if __package__ in (None, ""):
	sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("VIDEO_ENGINE_LLM", "google:gemini-3.8-flash")

from studio.deck_builder import build_deck
from studio.deck_contracts import DeckError
from studio.pptx_export import export_pptx
from video_engine.usage import UsageLedger
from workbench._runner import arguments, captured, failure, guard_budget, marker
from workbench.library import safe_path, write_json
from workbench.material import generation_material, source_context, provenance


def main(argv, complete_json=None) -> int:
	args = arguments(argv, "生成教學簡報", "unit_dir")
	os.environ.setdefault("VIDEO_ENGINE_LLM", "google:gemini-3.8-flash")
	directory = Path(args.unit_dir).resolve()
	ledger = UsageLedger()
	try:
		try:
			material, source_data = generation_material(directory)
		except (ValueError, OSError) as exc:
			raise DeckError(str(exc)) from exc
		if complete_json is None:
			from video_engine.llm import complete_json as complete
			complete_json = partial(complete, stage="deck")
		def cj(system, user, schema):
			guard_budget(directory, args.budget_usd, "deck", system, user, schema)
			result = captured(ledger, directory, "slides", "generate", complete_json, system, user, schema)
			marker("step", "validate")
			return result
		marker("step", "generate")
		deck = build_deck(material, "把這份教材做成線上簡報", cj, source_context=source_context(source_data))
		marker("step", "export")
		pptx = export_pptx(deck)
		write_json(safe_path(directory, "slides/deck.json"), deck)
		safe_path(directory, "slides/deck.pptx").write_bytes(pptx)
		write_json(safe_path(directory, "slides/source.json"), provenance(source_data))
		return 0
	except Exception as exc:
		return failure(exc, DeckError)


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
