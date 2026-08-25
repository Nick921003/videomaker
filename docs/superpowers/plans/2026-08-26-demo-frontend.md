# 現場 Demo 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一個本機工具：丟一份 `.md` 或 `.pptx`，看著八階段跑，中途確認或修改講稿，拿到 MP4。

**Architecture:** 瀏覽器單頁 HTML ↔ `serve.py`（stdlib `http.server`）↔ subprocess 呼叫既有 `run.py`。服務層只管 HTTP 與 job 狀態機，不含任何影片邏輯；所有影片知識留在既有引擎裡。審稿閘插在 `validate` 之後、`synth` 之前，因此改講稿的代價是零。

**Tech Stack:** Python 3.10 stdlib（`http.server`、`zipfile`、`xml.etree`、`unittest`）、既有 `video_engine/*`、單一 HTML 檔（無建置、無 CDN）。

**Spec:** `docs/superpowers/specs/2026-08-26-demo-frontend-design.md`

## Global Constraints

- 縮排一律 **Tab（4 格）**。註解用**中文**，密度跟隨專案既有慣例（引擎目前是「每個函式一句 docstring 說明為什麼」，不逐行註解）。
- **零新增執行期依賴。** 服務層、`.pptx` 解析、測試全部走 stdlib。
- **偏離 spec（需審查者裁決）**：spec 第「元件與職責」節寫 `.pptx` 用 `python-pptx`。本計畫改用 stdlib `zipfile` + `xml.etree`。理由：`.pptx` 是 OOXML zip，抽文字只需撈 `<a:t>` 節點，約 30 行；引入套件違反專案「依賴很省」的既有調性。代價：`python-pptx` 對表格、群組圖形、SmartArt 的處理較完整，stdlib 版只保證抽得到一般文字框與備忘稿。若審查者認為代價過高，改回 `python-pptx` 只影響 Task 1。
- **測試用 stdlib `unittest`**，不引 pytest（專案 venv 無 pytest，無 `pyproject.toml`）。測試放 `tests/`，用 `.venv/bin/python -m unittest` 跑。
- 前端色票**只能**用以下值，禁用純白 `#FFFFFF` 與純黑 `#000000`：

  | 用途 | 色票 |
  | :--- | :--- |
  | 頁面底色 | `#F4EDE2` |
  | 卡片／面板 | `#FBF7F0`，邊框 `#DFD2BF` |
  | 主要文字 | `#3B322A` |
  | 次要文字 | `#4B4238` |
  | 強調／進行中 | `#B85C38` |
  | 已完成 | `#A0673F` |
  | 講稿編輯區 | 底 `#EFE6D8`，邊 `#DCCDB6` |
  | 倒數警示 | 底 `#F2D9A0`，字 `#B85C38` |

- 前端不引入任何外部字型、CSS 框架、CDN 資源。單一 HTML 檔，離線可跑。不做深色模式。
- 階段權重（總和 100）：`lesson` 25、`slides` 1、`actions` 19、`validate` 1、`storyboard` 0、`synth` 30、`timeline` 0、`video` 24。
- 每個 Task 結束都 commit。commit message 用中文、Conventional Commits 格式。

---

### Task 1: `ingest.py` — 教材檔案抽成純文字

**Files:**
- Create: `video_engine/ingest.py`
- Create: `tests/__init__.py`（空檔）
- Create: `tests/test_ingest.py`
- Create: `tests/fixtures/make_pptx.py`（產測試用的最小 `.pptx`）

**Interfaces:**
- Produces: `extract_text(path: str) -> str`。丟 `.md`／`.txt` 回原文；丟 `.pptx` 回組好的 markdown 文字。副檔名不支援時丟 `ValueError`；`.pptx` 抽不到任何文字時丟 `ValueError`。
- Produces: `SUPPORTED = (".md", ".txt", ".pptx")`，供 Task 6 的白名單使用。

- [ ] **Step 1: 寫產生測試 fixture 的小工具**

`.pptx` 是 OOXML zip，用 stdlib 就能組一份最小的出來，不需要真的簡報檔。

建立 `tests/fixtures/make_pptx.py`：

```python
#!/usr/bin/env python3
"""產生測試用的最小 .pptx。

.pptx 是 OOXML：一個 zip，投影片文字在 ppt/slides/slideN.xml 的 <a:t> 節點，
備忘稿在 ppt/notesSlides/notesSlideN.xml。測試只需要這兩種檔案存在且格式正確，
不需要 PowerPoint 開得起來的完整簡報。
"""
import zipfile

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _slide_xml(paragraphs):
	body = "".join(
		f'<a:p><a:r><a:t>{p}</a:t></a:r></a:p>' for p in paragraphs
	)
	return (f'<?xml version="1.0" encoding="UTF-8"?>'
		f'<p:sld xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>'
		f'<p:sp><p:txBody>{body}</p:txBody></p:sp>'
		f'</p:spTree></p:cSld></p:sld>')


def make(path, slides, notes=None):
	"""slides 是 [[段落, 段落], ...]；notes 是 {投影片編號(1起): 備忘稿文字}"""
	notes = notes or {}
	with zipfile.ZipFile(path, "w") as z:
		z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
		for i, paras in enumerate(slides, start=1):
			z.writestr(f"ppt/slides/slide{i}.xml", _slide_xml(paras))
		for i, text in notes.items():
			z.writestr(f"ppt/notesSlides/notesSlide{i}.xml", _slide_xml([text]))


if __name__ == "__main__":
	make("sample.pptx", [["標題", "重點一"]], {1: "這裡是備忘稿"})
```

- [ ] **Step 2: 寫失敗的測試**

建立 `tests/__init__.py`（空檔）與 `tests/test_ingest.py`：

```python
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video_engine"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures"))

import make_pptx
from ingest import SUPPORTED, extract_text


class TestExtractText(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp()

	def path(self, name):
		return os.path.join(self.dir, name)

	def test_md_原文照回(self):
		p = self.path("a.md")
		open(p, "w", encoding="utf-8").write("# 標題\n\n內文一行")
		self.assertEqual(extract_text(p), "# 標題\n\n內文一行")

	def test_txt_原文照回(self):
		p = self.path("a.txt")
		open(p, "w", encoding="utf-8").write("純文字")
		self.assertEqual(extract_text(p), "純文字")

	def test_pptx_每頁文字都要在且照頁序(self):
		p = self.path("a.pptx")
		make_pptx.make(p, [["第一頁標題", "第一頁重點"], ["第二頁標題"]])
		out = extract_text(p)
		self.assertIn("第一頁標題", out)
		self.assertIn("第一頁重點", out)
		self.assertIn("第二頁標題", out)
		self.assertLess(out.index("第一頁標題"), out.index("第二頁標題"))

	def test_pptx_備忘稿要抽出來(self):
		p = self.path("a.pptx")
		make_pptx.make(p, [["標題"]], {1: "這句只在備忘稿裡"})
		self.assertIn("這句只在備忘稿裡", extract_text(p))

	def test_pptx_投影片超過九頁要照數字排序不是字串排序(self):
		p = self.path("a.pptx")
		make_pptx.make(p, [[f"第{i}頁"] for i in range(1, 12)])
		out = extract_text(p)
		self.assertLess(out.index("第9頁"), out.index("第10頁"))

	def test_pptx_全是圖沒有文字要丟錯(self):
		p = self.path("a.pptx")
		make_pptx.make(p, [[]])
		with self.assertRaises(ValueError):
			extract_text(p)

	def test_不支援的副檔名要丟錯(self):
		p = self.path("a.pdf")
		open(p, "w", encoding="utf-8").write("x")
		with self.assertRaises(ValueError):
			extract_text(p)

	def test_SUPPORTED_是白名單來源(self):
		self.assertEqual(SUPPORTED, (".md", ".txt", ".pptx"))


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 3: 跑測試確認失敗**

Run: `.venv/bin/python -m unittest tests.test_ingest -v`
Expected: FAIL，錯誤是 `ModuleNotFoundError: No module named 'ingest'`

- [ ] **Step 4: 寫實作**

建立 `video_engine/ingest.py`：

```python
#!/usr/bin/env python3
"""教材檔案 → 純文字。

引擎的輸入契約其實是「一段純文字」——generate_lesson.py 只做 open().read()，
沒有任何 markdown 解析。所以支援新格式就是在最前面多一道抽取，
後面七個階段一行都不用改。
"""
import os
import re
import zipfile
from xml.etree import ElementTree as ET

SUPPORTED = (".md", ".txt", ".pptx")

# OOXML 的 drawingml 命名空間，投影片上所有文字都在這底下的 <a:t>
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_SLIDE_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
_NOTES_RE = re.compile(r"^ppt/notesSlides/notesSlide(\d+)\.xml$")


def _paragraphs(xml_bytes):
	"""一個 <a:p> 是一段。同段裡可能被切成多個 <a:t>（換字型就會斷），要接回去"""
	root = ET.fromstring(xml_bytes)
	out = []
	for para in root.iter(_A + "p"):
		text = "".join(t.text or "" for t in para.iter(_A + "t")).strip()
		if text:
			out.append(text)
	return out


def _pptx_text(path):
	"""每頁第一段當標題，其餘當內容，備忘稿另外標出來。
	備忘稿常常是老師真正想講的話，比投影片上的關鍵字有用"""
	with zipfile.ZipFile(path) as z:
		names = z.namelist()
		slides = sorted(
			((int(m.group(1)), n) for n in names for m in [_SLIDE_RE.match(n)] if m))
		notes = {int(m.group(1)): n for n in names for m in [_NOTES_RE.match(n)] if m}
		blocks = []
		for num, name in slides:
			paras = _paragraphs(z.read(name))
			if not paras:
				continue
			lines = [f"## 第 {num} 頁：{paras[0]}"]
			lines += [f"- {p}" for p in paras[1:]]
			if num in notes:
				said = _paragraphs(z.read(notes[num]))
				if said:
					lines.append("備忘稿：" + " ".join(said))
			blocks.append("\n".join(lines))
	if not blocks:
		raise ValueError("這份簡報沒有文字層，抽不出任何內容")
	return "\n\n".join(blocks)


def extract_text(path):
	"""教材檔案 → 純文字。副檔名不支援或抽不到內容時丟 ValueError"""
	ext = os.path.splitext(path)[1].lower()
	if ext not in SUPPORTED:
		raise ValueError(f"不支援的格式 {ext}，只吃 {'、'.join(SUPPORTED)}")
	if ext == ".pptx":
		return _pptx_text(path)
	return open(path, encoding="utf-8").read()
```

- [ ] **Step 5: 跑測試確認通過**

Run: `.venv/bin/python -m unittest tests.test_ingest -v`
Expected: `Ran 8 tests` 全部 OK

- [ ] **Step 6: Commit**

```bash
git add video_engine/ingest.py tests/
git commit -m "feat(ingest): 教材檔案抽成純文字，支援 pptx

pptx 走 stdlib zipfile + xml.etree 撈 <a:t>，不引 python-pptx——
引擎的輸入契約本來就是純文字，抽取只需要 30 行。備忘稿一起抽出來，
那常常是老師真正想講的話。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: `run.py` 接上 ingest 與檔案落地

**Files:**
- Modify: `video_engine/run.py:33-52`（`main()` 開頭取得 material 到算出 lesson_id 那段）
- Test: `tests/test_run_material.py`

**Interfaces:**
- Consumes: Task 1 的 `extract_text`、`SUPPORTED`
- Produces: `resolve_material(path: str, materials_dir: str) -> str`，回傳實際要餵給管線的 `.md` 路徑。`.md` 直接原路徑回傳；其他格式抽成文字後落地成 `<stem>.md`，同名加序號不覆寫。

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_run_material.py`：

```python
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "video_engine"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures"))

import make_pptx
from run import resolve_material


class TestResolveMaterial(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp()
		self.materials = os.path.join(self.dir, "materials")
		os.makedirs(self.materials)

	def test_md_原路徑回傳不落地(self):
		p = os.path.join(self.dir, "a.md")
		open(p, "w", encoding="utf-8").write("內容")
		self.assertEqual(resolve_material(p, self.materials), p)
		self.assertEqual(os.listdir(self.materials), [])

	def test_pptx_落地成同名_md(self):
		p = os.path.join(self.dir, "deck.pptx")
		make_pptx.make(p, [["標題", "重點"]])
		out = resolve_material(p, self.materials)
		self.assertEqual(out, os.path.join(self.materials, "deck.md"))
		self.assertIn("標題", open(out, encoding="utf-8").read())

	def test_同名不覆寫要加序號(self):
		open(os.path.join(self.materials, "deck.md"), "w", encoding="utf-8").write("舊的")
		p = os.path.join(self.dir, "deck.pptx")
		make_pptx.make(p, [["新的"]])
		out = resolve_material(p, self.materials)
		self.assertEqual(out, os.path.join(self.materials, "deck_2.md"))
		self.assertEqual(open(os.path.join(self.materials, "deck.md"), encoding="utf-8").read(), "舊的")


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/python -m unittest tests.test_run_material -v`
Expected: FAIL，`ImportError: cannot import name 'resolve_material'`

- [ ] **Step 3: 寫實作**

在 `video_engine/run.py` 的 `run()` 函式**之後**、`main()` 之前插入：

```python
def resolve_material(path, materials_dir):
	"""非 .md 的來源先抽成純文字落地，手上才有引擎實際讀到的東西可以對照。
	同名不覆寫——產出可以重生，教材不行"""
	if os.path.splitext(path)[1].lower() == ".md":
		return path
	text = ingest.extract_text(path)
	stem = os.path.splitext(os.path.basename(path))[0]
	out = os.path.join(materials_dir, f"{stem}.md")
	n = 2
	while os.path.exists(out):
		out = os.path.join(materials_dir, f"{stem}_{n}.md")
		n += 1
	os.makedirs(materials_dir, exist_ok=True)
	open(out, "w", encoding="utf-8").write(text)
	return out
```

在 `run.py` 檔案頂端的 import 區塊加入（放在 `import time` 之後）：

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest
```

在 `main()` 中，把這一行：

```python
	material = sys.argv[1]
```

改成：

```python
	material = resolve_material(sys.argv[1], os.path.join(HERE, "materials"))
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/python -m unittest tests.test_run_material -v`
Expected: `Ran 3 tests` 全部 OK

- [ ] **Step 5: 回歸——既有 .md 路徑不能壞**

Run: `.venv/bin/python video_engine/run.py video_engine/materials/c_string.md --until slides`
Expected: 跑完 `階段 3　投影片繪製與量測`，無錯誤退出

- [ ] **Step 6: Commit**

```bash
git add video_engine/run.py tests/test_run_material.py
git commit -m "feat(run): 教材走 ingest，非 md 抽成文字後落地

同名加序號不覆寫：產出可以重生，教材不行。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: `run.py --json-events` 機器可讀進度

**Files:**
- Modify: `video_engine/run.py`（`run()` 函式與 `main()` 的旗標解析）
- Test: `tests/test_run_events.py`

**Interfaces:**
- Produces: 帶 `--json-events` 時，每階段起訖各印一行 JSON 到 **stderr**。人看的中文輸出走 stdout，完全不變。
  - 起：`{"event": "stage_start", "stage": "lesson"}`
  - 訖：`{"event": "stage_end", "stage": "lesson", "sec": 41.2}`
  - 失敗：`{"event": "stage_fail", "stage": "synth", "code": 1}`

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_run_events.py`：

```python
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv/bin/python")


class TestJsonEvents(unittest.TestCase):
	def test_帶旗標時_stderr_是每行一則_JSON(self):
		# 只跑到 slides，不呼叫 LLM：lesson 階段用既有的 examples 當快取跳過
		r = subprocess.run(
			[PY, os.path.join(ROOT, "video_engine/run.py"),
				os.path.join(ROOT, "video_engine/materials/c_string.md"),
				"--from", "slides", "--until", "slides", "--json-events"],
			capture_output=True, text=True)
		self.assertEqual(r.returncode, 0, r.stderr)
		events = [json.loads(l) for l in r.stderr.splitlines() if l.startswith("{")]
		kinds = [(e["event"], e["stage"]) for e in events]
		self.assertIn(("stage_start", "slides"), kinds)
		self.assertIn(("stage_end", "slides"), kinds)
		end = next(e for e in events if e["event"] == "stage_end")
		self.assertIsInstance(end["sec"], float)

	def test_不帶旗標時_stderr_沒有_JSON(self):
		r = subprocess.run(
			[PY, os.path.join(ROOT, "video_engine/run.py"),
				os.path.join(ROOT, "video_engine/materials/c_string.md"),
				"--from", "slides", "--until", "slides"],
			capture_output=True, text=True)
		self.assertEqual(r.returncode, 0, r.stderr)
		self.assertNotIn('{"event"', r.stderr)


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/python -m unittest tests.test_run_events -v`
Expected: 第一個測試 FAIL（stderr 沒有 JSON），第二個 PASS

- [ ] **Step 3: 寫實作**

在 `run.py` 頂端 import 區塊加 `import json`。

把 `run()` 函式改成（`STAGES` 定義之後）：

```python
JSON_EVENTS = False


def event(**kw):
	"""機器可讀的進度事件走 stderr，人看的中文輸出走 stdout，兩邊互不干擾"""
	if JSON_EVENTS:
		print(json.dumps(kw, ensure_ascii=False), file=sys.stderr, flush=True)


def run(script, args, label, interpreter=None, stage=None):
	t0 = time.time()
	print(f"\n\033[1m▶ {label}\033[0m")
	event(event="stage_start", stage=stage)
	r = subprocess.run([interpreter or PY, os.path.join(HERE, script)] + args)
	if r.returncode != 0:
		event(event="stage_fail", stage=stage, code=r.returncode)
		raise SystemExit(f"\n{label} 失敗（回傳碼 {r.returncode}），停在這裡")
	sec = time.time() - t0
	event(event="stage_end", stage=stage, sec=round(sec, 1))
	print(f"  ── {sec:.0f} 秒")
```

在 `main()` 的旗標解析區（`sec = opt("--sec")` 之後）加：

```python
	global JSON_EVENTS
	JSON_EVENTS = "--json-events" in argv
```

把 `main()` 裡八個 `run(...)` 呼叫各補上 `stage=` 參數。例如：

```python
	if want("lesson"):
		run("generate_lesson.py", [material, lesson], "階段 2　教材結構化（LLM）", LLM_PY, stage="lesson")
	if want("slides"):
		run("render_slides.py", [lesson, out_dir], "階段 3　投影片繪製與量測", stage="slides")
	if want("actions"):
		run("generate_actions.py", [lesson, actions] + (["--sec", sec] if sec else []),
			"階段 4　動作編排（LLM，內含驗證閘）", LLM_PY, stage="actions")
	if want("validate"):
		run("validate.py", [lesson, actions] + ([sec] if sec else []), "階段 4.5　編排驗證", stage="validate")
	if want("storyboard"):
		run("storyboard.py", [lesson, actions, out_dir], "階段 5　審稿分鏡表", stage="storyboard")
	if want("synth"):
		run("synth.py", [lesson, actions, out_dir], "階段 5.5　語音合成與驗收重試", stage="synth")
	if want("timeline"):
		run("compile_timeline.py", [lesson, actions, out_dir], "階段 6　時間軸編譯", stage="timeline")
	if want("video"):
		run("render_video.py", [lesson, out_dir], "階段 7　影格渲染與封裝", stage="video")
```

**注意**：上面 `storyboard` 與 `synth` 的順序與標籤已經是 Task 4 要的結果，這一步一起寫掉，Task 4 只負責改 `STAGES` 常數與驗證。

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/python -m unittest tests.test_run_events -v`
Expected: `Ran 2 tests` 全部 OK

- [ ] **Step 5: Commit**

```bash
git add video_engine/run.py tests/test_run_events.py
git commit -m "feat(run): 新增 --json-events 機器可讀進度

事件走 stderr，人看的中文輸出走 stdout 不變。比正則抓中文可靠。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: 審稿閘前移——`storyboard` 排到 `synth` 之前

**Files:**
- Modify: `video_engine/run.py`（`STAGES` 常數與 docstring）
- Modify: `README.md`（「審稿建議停在 storyboard」那句的相依說明）

**Interfaces:**
- Produces: `STAGES` 順序變成 `["lesson", "slides", "actions", "validate", "storyboard", "synth", "timeline", "video"]`

**為什麼可以前移**：`storyboard.py:46` 是 `json.load(...) if os.path.exists(dur_path) else {}`。音檔時長只影響分鏡表上的秒數欄位，沒有它照樣產得出來。前移之後，改講稿不必重跑 TTS。

- [ ] **Step 1: 改 STAGES 常數**

把 `video_engine/run.py` 的：

```python
STAGES = ["lesson", "slides", "actions", "validate", "synth", "storyboard", "timeline", "video"]
```

改成：

```python
# storyboard 排在 synth 前面：分鏡表不需要音檔（storyboard.py 的 durations.json 是選用的），
# 前移之後改講稿不必重跑 TTS，代價從 51 秒降到零
STAGES = ["lesson", "slides", "actions", "validate", "storyboard", "synth", "timeline", "video"]
```

- [ ] **Step 2: 改 docstring**

把 `run.py` docstring 的：

```
階段：lesson → slides → actions → validate → synth → storyboard → timeline → video
審稿建議停在 storyboard，確認講稿沒問題再往下跑，因為改講稿只要重生那一段。
```

改成：

```
階段：lesson → slides → actions → validate → storyboard → synth → timeline → video
審稿停在 storyboard——它排在語音合成前面，這時候改講稿不用重跑 TTS。
```

- [ ] **Step 3: 驗證分鏡表在沒有音檔時產得出來**

```bash
rm -rf /tmp/sb_test && mkdir -p /tmp/sb_test
cp video_engine/out/c_string/layout.json /tmp/sb_test/
.venv/bin/python video_engine/storyboard.py \
  video_engine/examples/c_string.lesson.json \
  video_engine/examples/c_string.actions.json /tmp/sb_test
```

Expected: 退出碼 0，`/tmp/sb_test/storyboard.html` 存在

- [ ] **Step 4: 回歸——完整管線順序正確**

Run: `.venv/bin/python video_engine/run.py video_engine/materials/c_string.md --from slides --until storyboard`
Expected: 依序印出 `階段 3`、`階段 4`、`階段 4.5`、`階段 5　審稿分鏡表`，不出現語音合成

- [ ] **Step 5: 更新 README**

把 `README.md` 中「架構全貌見…」段落**前面**的目錄樹裡這兩行：

```
├── synth.py            語音合成 + 驗收重試
├── storyboard.py       出片前的審稿分鏡表
```

改成：

```
├── storyboard.py       審稿分鏡表（排在語音合成前，改稿不用重跑 TTS）
├── synth.py            語音合成 + 驗收重試
```

- [ ] **Step 6: Commit**

```bash
git add video_engine/run.py README.md
git commit -m "refactor(run): 分鏡表前移到語音合成之前

storyboard.py 的 durations.json 本來就是選用的，分鏡表不需要音檔。
前移之後改講稿的代價從重跑 TTS 51 秒降到零。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Job 狀態機（純邏輯，不碰 HTTP）

**Files:**
- Create: `jobstate.py`（專案根目錄）
- Test: `tests/test_jobstate.py`

**Interfaces:**
- Produces: `class Job(material_path, out_dir, sec, runner, clock=time.time)`
  - `runner(stage_from, stage_to) -> Iterator[dict]`：可注入。真跑時是 subprocess 讀 `--json-events`；測試時是假的。
  - `Job.status` → `"queued" | "running" | "awaiting_review" | "done" | "failed"`
  - `Job.stage` → 目前階段名或 `None`
  - `Job.pct` → 0–100 整數
  - `Job.events` → `list[dict]`，累積的事件
  - `Job.start()` → 跑到 `awaiting_review` 為止
  - `Job.approve(segments)` → 續跑到 `done`。`segments` 為空陣列代表未修改
  - `Job.review_deadline` → 進入 `awaiting_review` 時的截止時間戳（`clock() + 60`）
  - `Job.review_expired()` → `bool`
- Produces: `STAGE_WEIGHT` dict，總和 100

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_jobstate.py`：

```python
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jobstate import STAGE_WEIGHT, Job


def fake_runner(stages):
	"""照給定的階段清單吐 stage_start / stage_end，模擬 run.py --json-events"""
	def runner(stage_from, stage_to):
		lo, hi = stages.index(stage_from), stages.index(stage_to)
		for s in stages[lo:hi + 1]:
			yield {"event": "stage_start", "stage": s}
			yield {"event": "stage_end", "stage": s, "sec": 1.0}
	return runner


def failing_runner(fail_at):
	def runner(stage_from, stage_to):
		yield {"event": "stage_start", "stage": fail_at}
		yield {"event": "stage_fail", "stage": fail_at, "code": 1}
	return runner


ALL = ["lesson", "slides", "actions", "validate", "storyboard", "synth", "timeline", "video"]


class TestJob(unittest.TestCase):
	def test_權重總和是100(self):
		self.assertEqual(sum(STAGE_WEIGHT.values()), 100)

	def test_start_跑到審稿閘就停(self):
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		j.start()
		self.assertEqual(j.status, "awaiting_review")
		self.assertEqual(j.stage, "storyboard")

	def test_審稿閘之後才跑語音合成(self):
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		j.start()
		self.assertNotIn("synth", [e["stage"] for e in j.events])
		j.approve([])
		self.assertIn("synth", [e["stage"] for e in j.events])
		self.assertEqual(j.status, "done")
		self.assertEqual(j.pct, 100)

	def test_進度只算已完成階段的權重(self):
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		j.start()
		# lesson 25 + slides 1 + actions 19 + validate 1 + storyboard 0
		self.assertEqual(j.pct, 46)

	def test_階段失敗就轉_failed(self):
		j = Job("m.md", "/tmp/out", 110, failing_runner("lesson"))
		j.start()
		self.assertEqual(j.status, "failed")
		self.assertEqual(j.stage, "lesson")

	def test_審稿倒數60秒(self):
		now = [1000.0]
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL), clock=lambda: now[0])
		j.start()
		self.assertEqual(j.review_deadline, 1060.0)
		self.assertFalse(j.review_expired())
		now[0] = 1061.0
		self.assertTrue(j.review_expired())

	def test_未進審稿閘不可以_approve(self):
		j = Job("m.md", "/tmp/out", 110, fake_runner(ALL))
		with self.assertRaises(RuntimeError):
			j.approve([])


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/python -m unittest tests.test_jobstate -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'jobstate'`

- [ ] **Step 3: 寫實作**

建立 `jobstate.py`：

```python
#!/usr/bin/env python3
"""Job 狀態機：只管「跑到哪、剩多少、下一步是什麼」，不碰 HTTP、不碰影片。

runner 是注入的，所以這支可以完全離線測試——不用真的跑三分鐘的管線。
"""
import time

# 權重照實測配（c_string.md：810 字 → 5 頁 98 秒影片，總計 167 秒）。
# 等寬八格會騙人，會卡在第一格不動半分鐘
STAGE_WEIGHT = {
	"lesson": 25, "slides": 1, "actions": 19, "validate": 1,
	"storyboard": 0, "synth": 30, "timeline": 0, "video": 24,
}
REVIEW_SEC = 60          # 審稿閘倒數，首次現場實測後再調
BEFORE_REVIEW = ("lesson", "storyboard")
AFTER_REVIEW = ("synth", "video")


class Job:
	def __init__(self, material_path, out_dir, sec, runner, clock=time.time):
		self.material_path = material_path
		self.out_dir = out_dir
		self.sec = sec
		self.runner = runner
		self.clock = clock
		self.status = "queued"
		self.stage = None
		self.events = []
		self.done_stages = set()
		self.review_deadline = None
		self.error = None

	@property
	def pct(self):
		return sum(STAGE_WEIGHT.get(s, 0) for s in self.done_stages)

	def _pump(self, stage_from, stage_to):
		"""跑一段階段區間，把事件收進來。回傳是否成功"""
		for ev in self.runner(stage_from, stage_to):
			self.events.append(ev)
			self.stage = ev.get("stage")
			if ev["event"] == "stage_end":
				self.done_stages.add(ev["stage"])
			elif ev["event"] == "stage_fail":
				self.status = "failed"
				self.error = f"{ev['stage']} 失敗（回傳碼 {ev.get('code')}）"
				return False
		return True

	def start(self):
		self.status = "running"
		if not self._pump(*BEFORE_REVIEW):
			return
		self.status = "awaiting_review"
		self.review_deadline = self.clock() + REVIEW_SEC

	def review_expired(self):
		return self.review_deadline is not None and self.clock() > self.review_deadline

	def approve(self, segments):
		"""segments 為空代表沒改。回寫與重驗由呼叫端在進來之前做完"""
		if self.status != "awaiting_review":
			raise RuntimeError(f"目前是 {self.status}，不能核可")
		self.status = "running"
		if not self._pump(*AFTER_REVIEW):
			return
		self.status = "done"
		self.stage = None
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/python -m unittest tests.test_jobstate -v`
Expected: `Ran 7 tests` 全部 OK

- [ ] **Step 5: Commit**

```bash
git add jobstate.py tests/test_jobstate.py
git commit -m "feat(serve): job 狀態機，runner 可注入

runner 注入所以能離線測試，不用真的跑三分鐘管線。進度權重照實測配，
等寬八格會卡在第一格不動半分鐘。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: 講稿抽取、回寫與重驗

**Files:**
- Create: `script_gate.py`（專案根目錄）
- Test: `tests/test_script_gate.py`

**Interfaces:**
- Consumes: `video_engine/validate.py`（以 subprocess 呼叫）
- Produces:
  - `read_segments(actions_path) -> list[dict]`，每則 `{"slide_id": str, "idx": int, "text": str}`。`idx` 是該投影片 `actions` 陣列中的索引。
  - `write_segments(actions_path, segments) -> None`
  - `revalidate(lesson_path, actions_path, sec) -> list[str]`，回傳 ERROR 訊息清單；通過時是空陣列

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_script_gate.py`：

```python
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from script_gate import read_segments, revalidate, write_segments

LESSON = os.path.join(ROOT, "video_engine/examples/c_string.lesson.json")
ACTIONS = os.path.join(ROOT, "video_engine/examples/c_string.actions.json")


class TestScriptGate(unittest.TestCase):
	def setUp(self):
		self.dir = tempfile.mkdtemp()
		self.actions = os.path.join(self.dir, "a.json")
		shutil.copy(ACTIONS, self.actions)

	def test_抽出所有_speech_段落(self):
		segs = read_segments(self.actions)
		self.assertTrue(len(segs) >= 10)
		self.assertTrue(all(set(s) == {"slide_id", "idx", "text"} for s in segs))
		raw = json.load(open(ACTIONS, encoding="utf-8"))
		total = sum(1 for s in raw["slides"] for a in s["actions"] if a["type"] == "speech")
		self.assertEqual(len(segs), total)

	def test_回寫後文字有變且其他欄位不動(self):
		segs = read_segments(self.actions)
		segs[0]["text"] = "改過的講稿內容"
		write_segments(self.actions, segs)
		self.assertEqual(read_segments(self.actions)[0]["text"], "改過的講稿內容")
		before = json.load(open(ACTIONS, encoding="utf-8"))
		after = json.load(open(self.actions, encoding="utf-8"))
		self.assertEqual(len(before["slides"]), len(after["slides"]))
		for b, a in zip(before["slides"], after["slides"]):
			self.assertEqual(len(b["actions"]), len(a["actions"]))
			self.assertEqual([x["type"] for x in b["actions"]], [x["type"] for x in a["actions"]])

	def test_原稿重驗要通過(self):
		self.assertEqual(revalidate(LESSON, self.actions, None), [])

	def test_改成唸函式名要被擋(self):
		segs = read_segments(self.actions)
		segs[0]["text"] = "我們用 strcpy 把字串複製過去"
		write_segments(self.actions, segs)
		errs = revalidate(LESSON, self.actions, None)
		self.assertTrue(any("strcpy" in e for e in errs), errs)


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/python -m unittest tests.test_script_gate -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'script_gate'`

- [ ] **Step 3: 寫實作**

建立 `script_gate.py`：

```python
#!/usr/bin/env python3
"""審稿閘：把 actions.json 的講稿抽出來給人改，改完寫回去並重跑驗證閘。

重跑驗證是硬需求。現場很容易改出唸函式名、全大寫縮寫這類 TTS 會出事的稿，
驗證閘本來就擋這些——回寫後不重跑等於把閘關掉。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, ".venv/bin/python")
VALIDATE = os.path.join(HERE, "video_engine/validate.py")


def read_segments(actions_path):
	doc = json.load(open(actions_path, encoding="utf-8"))
	return [
		{"slide_id": s["slide_id"], "idx": i, "text": a["text"]}
		for s in doc["slides"]
		for i, a in enumerate(s["actions"])
		if a["type"] == "speech"
	]


def write_segments(actions_path, segments):
	"""只動 speech 的 text，動作結構完全不碰——編排是閘驗過的，人只改字"""
	doc = json.load(open(actions_path, encoding="utf-8"))
	by_slide = {s["slide_id"]: s for s in doc["slides"]}
	for seg in segments:
		slide = by_slide.get(seg["slide_id"])
		if not slide:
			continue
		i = seg["idx"]
		if 0 <= i < len(slide["actions"]) and slide["actions"][i]["type"] == "speech":
			slide["actions"][i]["text"] = seg["text"]
	json.dump(doc, open(actions_path, "w", encoding="utf-8"),
		ensure_ascii=False, indent="\t")


def revalidate(lesson_path, actions_path, sec):
	"""回傳 ERROR 訊息清單，通過時是空陣列。WARN 不擋"""
	args = [PY, VALIDATE, lesson_path, actions_path]
	if sec:
		args.append(str(sec))
	r = subprocess.run(args, capture_output=True, text=True)
	return [l[len("ERROR "):].strip()
		for l in r.stdout.splitlines() if l.startswith("ERROR ")]
```

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/python -m unittest tests.test_script_gate -v`
Expected: `Ran 4 tests` 全部 OK

- [ ] **Step 5: Commit**

```bash
git add script_gate.py tests/test_script_gate.py
git commit -m "feat(serve): 講稿抽取、回寫與重驗

只動 speech 的 text，動作結構不碰——編排是閘驗過的，人只改字。
回寫後一定重跑驗證閘，不然現場改出唸函式名的稿 TTS 會爆。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: `serve.py` HTTP 層

**Files:**
- Create: `serve.py`（專案根目錄）
- Test: `tests/test_serve.py`

**Interfaces:**
- Consumes: Task 5 的 `Job`、`STAGE_WEIGHT`；Task 6 的 `read_segments`／`write_segments`／`revalidate`；Task 1 的 `SUPPORTED`
- Produces:
  - `tts_ready(url: str, timeout: float = 3.0) -> bool`
  - `real_runner(material, out_dir, sec)` — 回傳符合 `Job.runner` 契約的函式，內部 subprocess 呼叫 `run.py --json-events`
  - `make_server(port: int) -> HTTPServer`
  - 端點如 spec「HTTP 介面契約」節

- [ ] **Step 1: 寫失敗的測試**

建立 `tests/test_serve.py`（只測不需要真跑管線的部分）：

```python
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import serve


class TestServeHelpers(unittest.TestCase):
	def test_TTS_探測_連不上要回_False(self):
		self.assertFalse(serve.tts_ready("http://127.0.0.1:1", timeout=0.5))

	def test_副檔名白名單來自_ingest(self):
		self.assertTrue(serve.allowed("a.md"))
		self.assertTrue(serve.allowed("a.pptx"))
		self.assertFalse(serve.allowed("a.pdf"))
		self.assertFalse(serve.allowed("a.md.exe"))

	def test_檔名清理_去掉路徑元素(self):
		self.assertEqual(serve.safe_name("../../etc/passwd.md"), "passwd.md")
		self.assertEqual(serve.safe_name("a b/c.pptx"), "c.pptx")


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `.venv/bin/python -m unittest tests.test_serve -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'serve'`

- [ ] **Step 3: 寫實作**

建立 `serve.py`：

```python
#!/usr/bin/env python3
"""現場 Demo 用的本機服務：丟檔案 → 看八階段跑 → 確認講稿 → 拿 MP4。

只管 HTTP 與 job 狀態機，不含任何影片邏輯——所有影片知識留在 video_engine 裡。
同時只跑一個 job：LLM、TTS、CPU 都是單一資源，併發沒有意義。

用法：.venv/bin/python serve.py [埠號，預設 8899]
"""
import json
import os
import subprocess
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "video_engine"))

from ingest import SUPPORTED
from jobstate import Job
from script_gate import read_segments, revalidate, write_segments

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, ".venv/bin/python")
RUN = os.path.join(HERE, "video_engine/run.py")
MATERIALS = os.path.join(HERE, "video_engine/materials")
OUT = os.path.join(HERE, "video_engine/out")
WEB = os.path.join(HERE, "web")
MAX_UPLOAD = 5 * 1024 * 1024
TTS_URL = os.environ.get("TTS_API_URL", "http://127.0.0.1:9880")

_lock = threading.Lock()
_job = None          # 同時只有一個
_job_id = 0


def allowed(name):
	return os.path.splitext(name)[1].lower() in SUPPORTED


def safe_name(name):
	"""只留檔名，丟掉任何路徑元素"""
	return os.path.basename(name.replace("\\", "/"))


def tts_ready(url=TTS_URL, timeout=3.0):
	"""GPT-SoVITS 沒開是現場最常見的翻車點，收件前先探。
	404 也算活著——只要 TCP 通、HTTP 有回應就行"""
	try:
		urllib.request.urlopen(url, timeout=timeout)
		return True
	except urllib.error.HTTPError:
		return True
	except Exception:
		return False


def real_runner(material, sec):
	"""把 run.py --json-events 的 stderr 逐行轉成事件流"""
	def runner(stage_from, stage_to):
		args = [PY, RUN, material, "--from", stage_from, "--until", stage_to, "--json-events"]
		if sec:
			args += ["--sec", str(sec)]
		p = subprocess.Popen(args, stdout=subprocess.DEVNULL,
			stderr=subprocess.PIPE, text=True, bufsize=1)
		for line in p.stderr:
			line = line.strip()
			if line.startswith("{"):
				yield json.loads(line)
		p.wait()
	return runner
```

實作 `Handler(BaseHTTPRequestHandler)`，路由如下（同一檔案續寫）：

```python
class Handler(BaseHTTPRequestHandler):
	def _send(self, code, body=b"", ctype="application/json"):
		self.send_response(code)
		self.send_header("Content-Type", ctype)
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def _json(self, code, obj):
		self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

	def do_GET(self):
		if self.path == "/":
			html = open(os.path.join(WEB, "index.html"), "rb").read()
			return self._send(200, html, "text/html; charset=utf-8")
		if self.path.endswith("/events"):
			return self._events()
		if self.path.endswith("/script"):
			if not _job:
				return self._json(404, {"error": "沒有進行中的工作"})
			return self._json(200, {"segments": read_segments(_job.actions_path),
				"deadline": _job.review_deadline})
		if self.path.endswith("/video"):
			if not _job or _job.status != "done":
				return self._json(404, {"error": "影片還沒好"})
			data = open(_job.video_path, "rb").read()
			return self._send(200, data, "video/mp4")
		self._json(404, {"error": "找不到"})

	def _events(self):
		"""SSE：把 job 的事件與進度推給前端"""
		self.send_response(200)
		self.send_header("Content-Type", "text/event-stream")
		self.send_header("Cache-Control", "no-cache")
		self.end_headers()
		seen = 0
		while True:
			if not _job:
				break
			while seen < len(_job.events):
				ev = dict(_job.events[seen])
				ev.update(status=_job.status, pct=_job.pct)
				self.wfile.write(f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode())
				self.wfile.flush()
				seen += 1
			if _job.status in ("done", "failed", "awaiting_review"):
				tail = {"event": "state", "status": _job.status, "pct": _job.pct,
					"stage": _job.stage, "error": _job.error,
					"deadline": _job.review_deadline}
				self.wfile.write(f"data: {json.dumps(tail, ensure_ascii=False)}\n\n".encode())
				self.wfile.flush()
				if _job.status != "awaiting_review":
					break
			threading.Event().wait(0.4)
```

`do_POST` 處理 `/jobs` 與 `/jobs/{id}/approve`：

```python
	def do_POST(self):
		global _job, _job_id
		if self.path == "/jobs":
			return self._create()
		if self.path.endswith("/approve"):
			return self._approve()
		self._json(404, {"error": "找不到"})

	def _create(self):
		global _job, _job_id
		with _lock:
			if _job and _job.status in ("queued", "running", "awaiting_review"):
				return self._json(409, {"error": "已經有一個工作在跑，等它跑完"})
			if not tts_ready():
				return self._json(503, {"error": f"語音服務 {TTS_URL} 沒有回應，先把 GPT-SoVITS 開起來"})
			length = int(self.headers.get("Content-Length", 0))
			if length > MAX_UPLOAD:
				return self._json(413, {"error": "檔案超過 5 MB"})
			name, blob, sec = parse_multipart(self.rfile.read(length),
				self.headers.get("Content-Type", ""))
			name = safe_name(name)
			if not allowed(name):
				return self._json(400, {"error": f"不支援 {name}，只吃 {'、'.join(SUPPORTED)}"})
			os.makedirs(MATERIALS, exist_ok=True)
			raw = os.path.join(MATERIALS, name)
			open(raw, "wb").write(blob)
			_job_id += 1
			_job = Job(raw, OUT, sec, real_runner(raw, sec))
			_job.actions_path = None      # start() 之後才知道
			threading.Thread(target=_start_job, args=(_job,), daemon=True).start()
		self._json(201, {"job_id": _job_id})

	def _approve(self):
		if not _job or _job.status != "awaiting_review":
			return self._json(409, {"error": "現在不在審稿階段"})
		length = int(self.headers.get("Content-Length", 0))
		payload = json.loads(self.rfile.read(length) or b"{}")
		segs = payload.get("segments") or []
		if segs and not _job.review_expired():
			write_segments(_job.actions_path, segs)
			errs = revalidate(_job.lesson_path, _job.actions_path, _job.sec)
			if errs and not _job.retried:
				_job.retried = True
				_job.review_deadline = _job.clock() + 60
				return self._json(400, {"errors": errs})
		threading.Thread(target=lambda: _job.approve(segs), daemon=True).start()
		self._json(200, {"ok": True})
```

`_start_job` 與 `parse_multipart` 補在模組層：

```python
def _start_job(job):
	job.start()


def parse_multipart(body, ctype):
	"""只解析我們自己前端送的兩個欄位：file 與 sec。
	不用 cgi 模組——Python 3.13 已經移除它"""
	boundary = ctype.split("boundary=")[-1].strip().encode()
	name, blob, sec = "", b"", None
	for part in body.split(b"--" + boundary):
		if b"\r\n\r\n" not in part:
			continue
		head, data = part.split(b"\r\n\r\n", 1)
		data = data.rstrip(b"\r\n-")
		h = head.decode("utf-8", "replace")
		if 'name="file"' in h:
			name = h.split('filename="')[1].split('"')[0]
			blob = data
		elif 'name="sec"' in h:
			sec = data.decode().strip() or None
	return name, blob, sec


def make_server(port):
	return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
	port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
	print(f"開好了：http://127.0.0.1:{port}")
	make_server(port).serve_forever()
```

同時要在 `jobstate.Job.__init__` 末尾補三個欄位（Task 5 已建的檔案）：

```python
		self.actions_path = None
		self.lesson_path = None
		self.video_path = None
		self.retried = False
```

並在 `Job.start()` 成功進入 `awaiting_review` 之前，依 `material_path` 算出三個路徑：

```python
		import re
		stem = re.sub(r"[^a-z0-9_]", "_",
			os.path.splitext(os.path.basename(self.material_path))[0].lower())
		base = os.path.dirname(os.path.dirname(os.path.abspath(self.material_path)))
		self.lesson_path = os.path.join(base, "examples", f"{stem}.lesson.json")
		self.actions_path = os.path.join(base, "examples", f"{stem}.actions.json")
		self.video_path = os.path.join(self.out_dir, stem, f"{stem}.mp4")
```

（`jobstate.py` 頂端補 `import os`。）

- [ ] **Step 4: 跑測試確認通過**

Run: `.venv/bin/python -m unittest tests.test_serve -v`
Expected: `Ran 3 tests` 全部 OK

- [ ] **Step 5: 補跑 Task 5 的測試確認沒改壞**

Run: `.venv/bin/python -m unittest tests.test_jobstate -v`
Expected: `Ran 7 tests` 全部 OK

- [ ] **Step 6: Commit**

```bash
git add serve.py jobstate.py tests/test_serve.py
git commit -m "feat(serve): HTTP 層與 SSE 進度串流

收件前先探 GPT-SoVITS——沒開是現場最常見的翻車點，不能等跑到第五階段才炸。
同時只跑一個 job，LLM/TTS/CPU 都是單一資源。multipart 自己解，
不用 cgi 模組（3.13 已移除）。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: `web/index.html` — 前端（委派 AGY）

**Files:**
- Create: `web/index.html`

**Interfaces:**
- Consumes: Task 7 的四個端點
- Produces: 無（終端消費者）

依專案慣例，UI 實作委派 AGY。**Claude 定邊界、AGY 實作、Claude 驗邏輯、視覺交使用者確認。**

- [ ] **Step 1: 派工給 AGY**

用 `mcp__antigravity__discuss_with_antigravity_async_start`，`worker: worker-frontend`，英文 prompt，內容須包含：

- 檔案路徑：`web/index.html`，單一檔案，內嵌 CSS 與 JS
- **硬約束**：只能用 Global Constraints 那張色票表的八個色值；禁止 `#FFFFFF`／`#000000`；禁止任何外部字型、CSS 框架、CDN；不做深色模式；不引 JS 動畫函式庫（流程動畫用 CSS）
- 四個端點的契約（照 spec「HTTP 介面契約」節逐項給）
- 八階段的中文名稱與權重
- 畫面三個狀態：① 上傳（拖放區）② 執行中（流程動畫 + 進度條 + 目前階段）③ 審稿（逐段可編輯的講稿 + 60 秒倒數 + 繼續鈕）④ 完成（下載連結 + `<video>` 預覽）⑤ 失敗（階段名 + 錯誤訊息）
- **倒數畫面必須顯示「倒數歸零就直接繼續，沒有人反對視同確認」這句話**
- 驗收標準：離線可開（斷網不影響版面）、1280×720 與 1920×1080 都不破版、無 console error

- [ ] **Step 2: 收件檢查**

AGY 會幻覺路徑、會把零結果當成功。收到後逐項確認：

```bash
test -f web/index.html && echo "檔案在"
grep -ciE "#FFFFFF|#FFF\b|#000000|#000\b" web/index.html
grep -ciE "https?://|cdn|googleapis|unpkg|jsdelivr" web/index.html
grep -c "沒有人反對視同確認" web/index.html
```

Expected: 檔案存在；前兩個 grep 計數為 **0**；第三個為 **1** 以上

- [ ] **Step 3: 邏輯驗證（Claude 做，不看視覺）**

```bash
.venv/bin/python -c "
import re
h = open('web/index.html', encoding='utf-8').read()
for ep in ('/jobs', '/events', '/script', '/approve', '/video'):
    assert ep in h, ep
assert 'EventSource' in h, '沒有訂閱 SSE'
print('四個端點與 SSE 都接上了')
"
```

Expected: 印出「四個端點與 SSE 都接上了」

- [ ] **Step 4: 視覺交使用者確認**

啟動服務並請使用者開瀏覽器看：

```bash
.venv/bin/python serve.py
```

- [ ] **Step 5: Commit**

```bash
git add web/index.html
git commit -m "feat(web): 現場 Demo 單頁前端

暖色配色沿用 themes/warm.json，投影片與介面同一組色票。
單一 HTML 檔、離線可跑、無 CDN。倒數畫面明講「沒有人反對視同確認」——
不然確認過是假的。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 9: 端到端與回歸

**Files:**
- Create: `tests/test_e2e.py`

**Interfaces:**
- Consumes: 全部

- [ ] **Step 1: 寫端到端測試**

建立 `tests/test_e2e.py`：

```python
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, ".venv/bin/python")


@unittest.skipUnless(os.environ.get("E2E") == "1", "設 E2E=1 才跑，會真的呼叫 LLM 與 TTS")
class TestEndToEnd(unittest.TestCase):
	def test_pptx_進去_mp4_出來(self):
		sys.path.insert(0, os.path.join(ROOT, "tests/fixtures"))
		import make_pptx
		deck = os.path.join(ROOT, "video_engine/materials/_e2e_deck.pptx")
		make_pptx.make(deck, [
			["C 語言的布林值", "C89 沒有 bool 型態", "非零即真，零為假"],
			["實務寫法", "用 int 代替", "或 include stdbool.h"],
		], {1: "重點是初學者常以為 C 有 bool，其實 C89 沒有。"})
		r = subprocess.run([PY, os.path.join(ROOT, "video_engine/run.py"), deck, "--sec", "60"],
			capture_output=True, text=True, timeout=900)
		self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
		mp4 = os.path.join(ROOT, "video_engine/out/_e2e_deck/_e2e_deck.mp4")
		self.assertTrue(os.path.exists(mp4))
		self.assertGreater(os.path.getsize(mp4), 100_000)


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2: 跑端到端（需要 GPT-SoVITS 開著）**

Run: `E2E=1 .venv/bin/python -m unittest tests.test_e2e -v`
Expected: `Ran 1 test` OK，約 3–4 分鐘

- [ ] **Step 3: 跑全部單元測試**

Run: `.venv/bin/python -m unittest discover tests -v`
Expected: 全部 OK，端到端那則顯示 skipped

- [ ] **Step 4: 動態回歸——兩份既有 actions 必須零診斷**

```bash
.venv/bin/python video_engine/compile_timeline.py \
  video_engine/examples/c_struct.lesson.json \
  video_engine/examples/c_struct.actions.json video_engine/out/c_struct_motion \
  | grep -E "WARN|ERROR"; echo "退出碼 $?（1 = 沒有任何診斷，正確）"
```

Expected: `退出碼 1`（grep 找不到東西），即零診斷

- [ ] **Step 5: 清掉端到端產生的檔案並 commit**

```bash
rm -f video_engine/materials/_e2e_deck.pptx video_engine/materials/_e2e_deck.md
rm -rf video_engine/out/_e2e_deck
git add tests/test_e2e.py
git commit -m "test: 端到端 pptx 進去 mp4 出來

預設 skip，設 E2E=1 才跑——會真的呼叫 LLM 與 TTS，約 3-4 分鐘。

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## 自審紀錄

**Spec 覆蓋**：逐節對照——架構（Task 5–7）、元件與職責（Task 1–4、7、8）、檔案落地與命名（Task 2）、HTTP 介面契約（Task 7）、Job 狀態機（Task 5）、審稿閘（Task 6、7、8）、進度權重（Task 5）、視覺規範（Task 8 + Global Constraints）、錯誤處理（Task 7）、測試（Task 1、2、5、6、7、9）。無遺漏。

**已知偏離**：`.pptx` 解析改用 stdlib（見 Global Constraints，待審查者裁決）。

**型別一致性**：`extract_text`／`SUPPORTED`（T1）→ T2、T7 使用；`Job`／`STAGE_WEIGHT`（T5）→ T7 使用；`read_segments`／`write_segments`／`revalidate`（T6）→ T7 使用。Task 7 額外要求 T5 的 `Job` 補四個欄位，已在該步驟寫明。
