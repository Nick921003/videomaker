"""上傳教材 → 抽取、整理並建立單元。"""
import os
from pathlib import Path
import sys
from types import SimpleNamespace


if __package__ in (None, ""):
	sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("VIDEO_ENGINE_LLM", "google:gemini-3.8-flash")

from studio.material_normalizer import NormalizationError, check_normalization_limits, normalize_material
from video_engine.ingest import extract_text
from video_engine.usage import UsageLedger
from workbench._runner import append_usage, arguments, captured, failure, guard_budget, marker
from workbench.library import Library, read_json, safe_path


def main(argv, runner=None) -> int:
	args = arguments(argv, "整理上傳教材", "upload_dir", "units_root")
	os.environ.setdefault("VIDEO_ENGINE_LLM", "google:gemini-3.8-flash")
	directory = Path(args.upload_dir).resolve()
	ledger = UsageLedger()
	try:
		marker("step", "extract")
		metadata = read_json(safe_path(directory, "upload.json"))
		if not isinstance(metadata, dict):
			raise ValueError("上傳資料格式不正確")
		filename, kind, title = (metadata.get(key) for key in ("filename", "kind", "title"))
		if (not isinstance(filename, str) or not filename or Path(filename).name != filename or "\\" in filename or
			kind not in ("pdf", "pptx") or Path(filename).suffix.lower() != "." + kind or
			(title is not None and not isinstance(title, str))):
			raise ValueError("上傳資料格式不正確")
		raw_path = safe_path(directory, filename)
		if raw_path.stat().st_size > 5 * 1024 * 1024:
			raise NormalizationError("教材檔案超過 5 MB")
		extracted = extract_text(str(raw_path))
		check_normalization_limits(extracted, "." + kind)
		extracted_path = safe_path(directory, "extracted.md")
		extracted_path.write_text(extracted, encoding="utf-8")
		record = SimpleNamespace(material_path=str(extracted_path), original_name=filename, raw_path=str(raw_path))
		if runner is None:
			from studio.material_normalizer import complete_ingest_text_json, complete_pdf_json
			def runner(system, user, pdf_bytes):
				if pdf_bytes is not None:
					return complete_pdf_json(system, user, pdf_bytes)
				return complete_ingest_text_json(system, user)
		def complete(system, user, pdf_bytes):
			guard_budget(directory, args.budget_usd, "ingest", system, user,
				provider="google", model=os.environ.get("STUDIO_INGEST_MODEL", "gemini-3.8-flash"))
			return captured(ledger, directory, "ingest", "normalize", runner, system, user, pdf_bytes)
		marker("step", "normalize")
		markdown, _ = normalize_material(record, complete)
		library = Library(Path(args.units_root))
		uid, _ = library.create_unit(markdown, title, source_kind=kind)
		append_usage(library.unit_dir(uid), ledger.summary()["calls"], "ingest", "normalize")
		marker("unit", uid)
		return 0
	except Exception as exc:
		return failure(exc, NormalizationError)


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
