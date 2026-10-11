"""影片分鏡前準備共同教學規劃；沿用免費自檢與單元預算。"""
from pathlib import Path
import sys

if __package__ in (None,''):
	sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from studio.deck_contracts import DeckError
from video_engine.usage import UsageLedger
from workbench._runner import arguments, failure, marker, teaching_plan


def main(argv, complete_json=None):
	args=arguments(argv,'準備共同教學規劃','unit_dir')
	try:
		from video_engine.board.author import preflight
		marker('step','selftest');preflight()
		marker('step','storyboard')
		teaching_plan(Path(args.unit_dir),UsageLedger(),args.budget_usd,complete_json)
		return 0
	except Exception as exc:return failure(exc,DeckError)


if __name__=='__main__':sys.exit(main(sys.argv[1:]))
