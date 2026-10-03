#!/usr/bin/env python3
"""教材檔案 → 純文字。

引擎的輸入契約其實是「一段純文字」——generate_lesson.py 只做 open().read()，
沒有任何 markdown 解析。所以支援新格式就是在最前面多一道抽取，
後面七個階段一行都不用改。
"""
import hashlib
import os
import re
import subprocess
import tempfile
import zipfile

SUPPORTED = (".md", ".txt", ".pptx", ".pdf")
MAX_PPTX_MEMBERS = 2000
MAX_PPTX_UNCOMPRESSED = 50 * 1024 * 1024
MAX_PPTX_SLIDES = 500
MAX_NORMALIZED_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 100


def lesson_id_for(path):
	"""教材路徑 → lesson_id。run.py 與服務層共用這一份，各算一次遲早走鐘"""
	stem = os.path.splitext(os.path.basename(path))[0].lower()
	slug = re.sub(r"[^a-z0-9_]", "_", stem).strip("_")
	# 中文檔名會被整串壓成底線，不同檔案全部撞在同一個 id 上。
	# 退化時改用原檔名的雜湊，至少能區分
	if not slug.replace("_", ""):
		return "material_" + hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8]
	return slug


def _pptx_text(path):
	"""每頁抓標題、內文與備忘稿。

	投影片順序、備忘稿歸屬都交給 python-pptx——這兩件事在檔案裡都隔了
	一層 rels 間接，照檔名編號硬對會張冠李戴。備忘稿常常是老師真正想講的話，
	比投影片上的關鍵字有用。
	"""
	# python-pptx 載入前先看 ZIP 中央目錄，避免展開炸彈。
	try:
		with zipfile.ZipFile(path) as archive:
			members = archive.infolist()
			if len(members) > MAX_PPTX_MEMBERS or sum(item.file_size for item in members) > MAX_PPTX_UNCOMPRESSED:
				raise ValueError("簡報檔案展開後過大")
	except zipfile.BadZipFile as exc:
		raise ValueError("簡報檔案無法讀取") from exc
	from pptx import Presentation
	from pptx.enum.shapes import MSO_SHAPE_TYPE

	slides = Presentation(path).slides
	if len(slides) > MAX_PPTX_SLIDES:
		raise ValueError("簡報頁數超過上限")
	blocks = []
	for num, slide in enumerate(slides, start=1):
		title = slide.shapes.title
		# 用 shape_id 比對，不能用 is：slide.shapes 每次迭代都給新的 proxy 物件
		title_id = title.shape_id if title is not None else None
		head = title.text.strip() if title is not None and title.has_text_frame else ""
		lines = []
		for shape in slide.shapes:
			if shape.shape_id == title_id or not shape.has_text_frame:
				continue
			for para in shape.text_frame.paragraphs:
				text = "".join(r.text for r in para.runs).strip()
				if text:
					lines.append(text)
		visual = any(shape.shape_type == MSO_SHAPE_TYPE.PICTURE or shape.has_chart or shape.has_table
			for shape in slide.shapes)
		if not (head or lines or visual):
			continue
		block = [f"## 第 {num} 頁：{head}" if head else f"## 第 {num} 頁"]
		if visual and not (head or lines):
			block.append("[本頁只有圖片或圖表，需要圖片辨識]")
		block += [f"- {line}" for line in lines]
		if slide.has_notes_slide:
			said = slide.notes_slide.notes_text_frame.text.strip()
			if said:
				block.append("備忘稿：" + " ".join(said.split()))
		blocks.append("\n".join(block))
	if not blocks:
		raise ValueError("這份簡報沒有文字層，抽不出任何內容")
	return "\n\n".join(blocks)


def _pdf_text(path):
    """以 PDF 原生文字層逐頁抽取；掃描頁留下視覺辨識標記。"""
    with open(path, "rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError("PDF 檔案格式不正確")
    try:
        info = subprocess.run(["pdfinfo", path], capture_output=True, text=True,
                              timeout=15, check=True).stdout
        match = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
        if not match:
            raise ValueError("無法判讀 PDF 頁數")
        pages = int(match.group(1))
        if pages < 1 or pages > MAX_PDF_PAGES:
            raise ValueError("PDF 頁數超過上限")
        with tempfile.TemporaryFile() as output:
            subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", path, "-"],
                           stdout=output, stderr=subprocess.PIPE, timeout=30, check=True)
            output.seek(0)
            data = output.read(MAX_NORMALIZED_BYTES + 1)
            if len(data) > MAX_NORMALIZED_BYTES:
                raise ValueError("教材文字超過 2 MB")
            text = data.decode("utf-8")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, UnicodeError, OSError) as exc:
        raise ValueError("PDF 文字無法抽取") from exc
    parts = text.split("\f")
    if parts and not parts[-1].strip():
        parts.pop()
    blocks = []
    for number in range(1, pages + 1):
        page_text = parts[number - 1].strip() if number <= len(parts) else ""
        blocks.append(f"## 第 {number} 頁\n" +
                      (page_text if page_text else "[本頁沒有可抽取的文字，需要圖片辨識]"))
    return "\n\n".join(blocks)


def extract_text(path):
	"""教材檔案 → 純文字。副檔名不支援或抽不到內容時丟 ValueError"""
	ext = os.path.splitext(path)[1].lower()
	if ext not in SUPPORTED:
		raise ValueError(f"不支援的格式 {ext}，只吃 {'、'.join(SUPPORTED)}")
	if ext == ".pptx":
		text = _pptx_text(path)
	elif ext == ".pdf":
		text = _pdf_text(path)
	else:
		try:
			with open(path, encoding="utf-8") as f:
				text = f.read()
		except UnicodeDecodeError as exc:
			raise ValueError("教材文字不是 UTF-8") from exc
	text = text.replace("\r\n", "\n").replace("\r", "\n")
	if not text.strip():
		raise ValueError("教材沒有可用文字")
	if len(text.encode("utf-8")) > MAX_NORMALIZED_BYTES:
		raise ValueError("教材文字超過 2 MB")
	return text
