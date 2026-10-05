"""教材單元的識別、資料與安全路徑。"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re


_UNIT_ID = re.compile(r"[a-f0-9]{12}")


def unit_id(markdown: str) -> str:
	return hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:12]


def read_json(path, default=None):
	try:
		with Path(path).open(encoding="utf-8") as handle:
			return json.load(handle)
	except FileNotFoundError:
		return default


def write_json(path, value):
	path = Path(path)
	path.parent.mkdir(parents=True, exist_ok=True)
	temporary = path.with_suffix(".tmp")
	with temporary.open("w", encoding="utf-8") as handle:
		json.dump(value, handle, ensure_ascii=False, indent="\t", allow_nan=False)
	os.replace(temporary, path)


def safe_path(root, relative) -> Path:
	root = Path(root).resolve()
	path = (root / relative).resolve()
	path.relative_to(root)
	return path


class Library:
	def __init__(self, root: Path):
		self.root = Path(root).resolve()
		self.root.mkdir(parents=True, exist_ok=True)

	def create_unit(self, markdown, title=None, source_ref=None, source_kind="md") -> tuple[str, bool]:
		identifier = unit_id(markdown)
		directory = safe_path(self.root, identifier)
		meta = safe_path(directory, "meta.json")
		if meta.is_file():
			return identifier, False
		if not title or not title.strip():
			title = next((line.lstrip("# ").strip() for line in markdown.splitlines() if line.strip()), "未命名教材")
		directory.mkdir(parents=True, exist_ok=True)
		safe_path(directory, "material.md").write_text(markdown, encoding="utf-8")
		write_json(meta, {"title": title.strip()[:200],
			"created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
			"source_ref": source_ref, "source_kind": source_kind})
		return identifier, True

	def exists(self, uid) -> bool:
		try:
			self.unit_dir(uid)
		except KeyError:
			return False
		return True

	def unit_dir(self, uid) -> Path:
		if not isinstance(uid, str) or not _UNIT_ID.fullmatch(uid):
			raise KeyError(uid)
		try:
			directory = safe_path(self.root, uid)
			if directory.is_dir() and safe_path(directory, "meta.json").is_file():
				return directory
		except ValueError:
			pass
		raise KeyError(uid)

	def unit_ids(self) -> list[str]:
		def created_at(uid):
			try:
				meta = self.meta(uid)
			except (KeyError, OSError, ValueError, RecursionError):
				return ""
			value = meta.get("created_at") if isinstance(meta, dict) else None
			return value if isinstance(value, str) else ""

		identifiers = [entry.name for entry in sorted(self.root.iterdir()) if self.exists(entry.name)]
		return sorted(identifiers, key=created_at, reverse=True)

	def meta(self, uid) -> dict:
		return read_json(self.path(uid, "meta.json"))

	def plan(self, uid) -> dict | None:
		return read_json(self.path(uid, "plan.json"))

	def path(self, uid, relative) -> Path:
		return safe_path(self.unit_dir(uid), relative)

	def write_manifest(self, uid, items) -> dict:
		meta = self.meta(uid)
		products = []
		for item in items:
			if item["status"] != "done":
				continue
			files = item["files"]
			created = max((self.path(uid, relative).stat().st_mtime for relative in files.values()), default=None)
			products.append({key: item[key] for key in ("item", "format", "label", "files", "duration", "cost_usd")})
			products[-1].update(embed_url=f"/embed/{uid}/{item['item']}",
				created_at=datetime.fromtimestamp(created, timezone.utc).isoformat() if created is not None else meta["created_at"])
		manifest = {"unit_id": uid, "title": meta["title"],
			"source_ref": meta.get("source_ref") if isinstance(meta.get("source_ref"), dict) else None, "products": products}
		write_json(self.path(uid, "manifest.json"), manifest)
		return manifest
