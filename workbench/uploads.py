"""只接受一個 PDF／PPTX 檔案的本機上傳草稿。"""
from email import policy
from email.parser import BytesParser
from pathlib import Path
import re
import uuid
from xml.etree import ElementTree
import zipfile

from studio.material_normalizer import MAX_AI_PAGES, NormalizationError, check_normalization_limits
from video_engine.ingest import extract_text
from .library import safe_path, write_json


MAX_FILE = 5 * 1024 * 1024
MAX_BODY = MAX_FILE + 64 * 1024
_UPLOAD_ID = re.compile(r"[a-f0-9]{32}")


class TooLarge(ValueError):
	pass


class Uploads:
	def __init__(self, root):
		self.root = Path(root).resolve()

	def directory(self, identifier):
		if not isinstance(identifier, str) or not _UPLOAD_ID.fullmatch(identifier):
			raise KeyError(identifier)
		try:
			directory = safe_path(self.root, identifier)
			if safe_path(directory, "upload.json").is_file():
				return directory
		except ValueError:
			pass
		raise KeyError(identifier)

	def create(self, content_type, body):
		if len(body) > MAX_BODY:
			raise TooLarge("教材檔案超過 5 MB")
		if "\r" in content_type or "\n" in content_type:
			raise ValueError("上傳格式不正確")
		message = BytesParser(policy=policy.default).parsebytes(
			b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + body)
		if message.get_content_type() != "multipart/form-data" or not message.is_multipart() or message.defects:
			raise ValueError("請以 multipart 上傳一個 file 檔案")
		parts = list(message.iter_parts())
		if len(parts) != 1:
			raise ValueError("請只上傳一個 file 檔案")
		part = parts[0]
		filename = part.get_filename()
		if (part.is_multipart() or part.defects or part.get_content_disposition() != "form-data"
			or part.get_param("name", header="content-disposition") != "file"
			or not filename or Path(filename).name != filename or "\\" in filename or "\0" in filename):
			raise ValueError("上傳檔案名稱或欄位不正確")
		kind = Path(filename).suffix.lower().lstrip(".")
		if kind not in ("pdf", "pptx"):
			raise ValueError("請上傳 PDF 或 PPTX")
		data = part.get_payload(decode=True)
		if not data:
			raise ValueError("教材檔案是空的")
		if len(data) > MAX_FILE:
			raise TooLarge("教材檔案超過 5 MB")
		identifier = uuid.uuid4().hex
		directory = safe_path(self.root, identifier)
		directory.mkdir(parents=True)
		path = safe_path(directory, filename)
		path.write_bytes(data)
		try:
			text = extract_text(str(path))
			pages = check_normalization_limits(text, "." + kind)
			page_count = len(pages)
			if kind == "pptx":
				# 抽取稿略過空白投影片，頁數上限仍須包含它們。
				with zipfile.ZipFile(path) as archive:
					document = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
				page_count = len(document.findall("p:sldIdLst/p:sldId",
					{"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}))
				if page_count > MAX_AI_PAGES:
					raise TooLarge("AI 整理目前最多接受 30 頁，請先拆分教材")
		except NormalizationError as exc:
			if re.search(r"上限|超過|超出|最多接受", str(exc)):
				raise TooLarge(str(exc)) from exc
			raise
		except ValueError as exc:
			if re.search(r"過大|超過|超出|上限", str(exc)):
				raise TooLarge(str(exc)) from exc
			raise
		except (SyntaxError, KeyError, zipfile.BadZipFile) as exc:
			raise ValueError("教材檔案格式不正確，請重新匯出 PDF 或 PPTX") from exc
		write_json(safe_path(directory, "upload.json"), {"filename": filename, "kind": kind, "title": Path(filename).stem})
		safe_path(directory, "extracted.md").write_text(text, encoding="utf-8")
		return {"upload_id": identifier, "kind": kind, "excerpt": text[:400], "pages": page_count,
			"chars": len(text), "estimate_usd": 0.01}
