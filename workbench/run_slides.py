"""單元教材 → 線上簡報與可編輯 PPTX。"""
from functools import partial
import json
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
from workbench._runner import arguments, captured, failure, guard_budget, marker, teaching_plan, assert_current_source, key_points
from workbench.library import safe_path, write_json
from workbench.material import generation_material, source_context, provenance
from workbench.artifacts import publish


def main(argv, complete_json=None) -> int:
	args = arguments(argv, "生成教學簡報", "unit_dir", quality=True)
	os.environ.setdefault("VIDEO_ENGINE_LLM", "google:gemini-3.8-flash")
	directory = Path(args.unit_dir).resolve()
	ledger = UsageLedger()
	try:
		try:
			material, source_data = generation_material(directory)
		except (ValueError, OSError) as exc:
			raise DeckError(str(exc)) from exc
		if complete_json is None and args.quality=='legacy':
			from video_engine.llm import complete_json as complete
			complete_json = partial(complete, stage="deck")
		def cj(system, user, schema):
			guard_budget(directory, args.budget_usd, "deck", system, user, schema)
			result = captured(ledger, directory, "slides", "generate", complete_json, system, user, schema)
			marker("step", "validate")
			return result
		marker("step", "generate")
		record=provenance(source_data)
		if args.quality=='keypoints':
			from studio.handout import build_handout
			from studio.key_points import KeyPointsError
			from workbench.key_points import digest_of
			try:
				points=key_points(directory,ledger,args.budget_usd,complete_json)
				deck=build_handout(points,material)
			except KeyPointsError as exc:
				raise DeckError(str(exc)) from exc
			# 記下成品來自哪一份清單；重抽後 is_done 才會判定舊成品過期。
			record['key_points_digest']=digest_of(points)
			marker('step','validate')
		elif args.quality=='professional':
			from studio.teaching_plan import plan_deck
			deck=plan_deck(teaching_plan(directory,ledger,args.budget_usd,complete_json))
			marker('step','validate')
		else:
			deck = build_deck(material, "把這份教材做成線上簡報", cj, source_context=source_context(source_data))
		marker("step", "export")
		pptx = export_pptx(deck)
		try:assert_current_source(directory,source_data)
		except ValueError as exc:raise DeckError(str(exc)) from exc
		publish(directory,{'slides/deck.json':json.dumps(deck,ensure_ascii=False,allow_nan=False).encode(),
			'slides/deck.pptx':pptx,'slides/source.json':json.dumps(record,ensure_ascii=False).encode()})
		return 0
	except Exception as exc:
		return failure(exc, DeckError)


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
