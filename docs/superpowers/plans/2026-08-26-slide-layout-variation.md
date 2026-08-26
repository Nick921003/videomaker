# 投影片版型多樣化 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓投影片的幾何版位隨內容型態變化，消除連續五頁長得一樣的單調感，且完全不動配色、內容結構與動畫層。

**Architecture:** 新增純函式模組 `video_engine/layout.py` 負責「這一頁的哪塊區域給誰」，`render_slides.py` 退回單純的「把東西畫進被指定的區域」。幾何算式因此可以不畫圖就測。四種版型（`stack` / `split` / `stage` / `code`）由內容組成確定性推導。

**Tech Stack:** Python 3.10、Pillow、fontTools。不新增任何第三方依賴。

**Spec:** `docs/superpowers/specs/2026-08-26-slide-layout-variation-design.md`（先讀它的第 5 節「不變量」與第 6 節「明確不做」）

## Global Constraints

- 縮排一律 **Tab（4 格）**。註解用**中文**，密度跟隨檔案既有慣例（本專案註解稀疏但實在，只寫「為什麼」不寫「做什麼」）。
- **`themes/warm.json` 一個位元組都不准改。** 繪製器不得寫死任何顏色，顏色一律從 `th[...]` 取。
- **不准改** `video_engine/schema/lesson.schema.json`、`video_engine/prompts/*`、`compile_timeline.py`、`render_video.py`、`validate.py`。
- **不准新增第三方依賴。**
- **`HEADER_BOX` 與 `CONTENT_BOX` 的外框在所有版型中逐像素相同。** 換頁是 420ms 交叉淡化，外框一變就會在淡化中互相穿插。
- **`base` 與 `full` 兩張圖的版位必須完全相同。** `hidden` 元素只畫在 `full`，但**版位計算一律含 hidden**。
- **所有可定址代號都必須出現在 `layout.json` 的 boxes**：元素 id 本身、`{id}:L{n}`、`{id}:i{n}`、`{id}:l{n}`、`{id}:r{n}`、`{id}:caption`。
- **決定性**：同一份 lesson 重跑兩次，PNG 逐位元組相同。不得引入隨機或時間相依。
- **不得把 `slide.note` 畫上畫面**——schema 明定它不顯示。
- 範例碼是**起點不是定稿**。與專案既有慣例衝突時以慣例為準，並在報告裡說明改了什麼。但**不准擅自改測試的斷言或名稱**——那會遮蔽計畫本身的洞；發現斷言有問題就回報。

## 回歸基準（每個 Task 都要用）

改動前，五份教材共 44 張 PNG 的正規化 md5 為 **`bf7997d90b8fd8b6863eb43178f9c28f`**。重建方式：

```bash
D=$(mktemp -d); for f in c_loop c_string c_struct c_struct_combo c_struct_v3; do \
  .venv/bin/python video_engine/render_slides.py video_engine/examples/$f.lesson.json $D/$f >/dev/null; done; \
  find $D -name '*.png' | sort | xargs md5sum | sed "s|$D|X|" | md5sum
```

Task 1 與 Task 2 **必須**維持這個雜湊不變（純重構）。Task 3 起版位會刻意改變，屆時改用「同一份教材連跑兩次逐位元組相同」驗決定性。

---

## File Structure

| 檔案 | 責任 |
| --- | --- |
| `video_engine/layout.py`（新增） | 純幾何。畫布常數、版型選擇、區域切分、容量與降級、程式碼行距字級。**不 import PIL、不碰檔案。** |
| `video_engine/render_slides.py`（修改） | 只負責繪製與量測。所有座標問 `layout.py` 拿。 |
| `tests/test_layout.py`（新增） | 純函式測試：版型選擇、區域切分、容量降級、鏡像、程式碼行距。 |
| `tests/test_render_slides.py`（修改） | 繪製層的不變量：量測框完整、框在區域內、hidden 不影響版位、決定性。 |

---

### Task 1: 把幾何常數搬進 `layout.py`

**Files:**
- Create: `video_engine/layout.py`
- Modify: `video_engine/render_slides.py`（第 17-31 行的常數區、第 86-93 行的 `code_metrics`）
- Modify: `tests/test_render_slides.py`（`import` 來源改成 `layout`）

**Interfaces:**
- Produces：`layout.W`、`layout.H`、`layout.HEADER_BOX`、`layout.CONTENT_BOX`、`layout.CODE_BOX`、`layout.TITLE_Y`、`layout.SUB_Y`、`layout.BULLET_Y0`、`layout.BULLET_STEP`、`layout.CENTER_X`、`layout.BULLET_MAX_W`、`layout.CODE_X`、`layout.CODE_Y0`、`layout.CODE_STEP`、`layout.CODE_SIZE`、`layout.FIG_MAX_W`、`layout.FIG_ROW_H`、`layout.FIG_GAP`、`layout.FIG_CAPTION_H`、`layout.code_metrics(n)`、`layout.rect(x0,y0,x1,y1)`
- 這是純搬移，**行為零改變**。

- [ ] **Step 1：建立 `video_engine/layout.py`**

```python
#!/usr/bin/env python3
"""投影片幾何：這一頁的哪塊區域給誰。

刻意是純函式——不 import PIL、不碰檔案、不畫任何東西。
所以版型選擇、容量計算與降級邏輯都能不產圖就測。
繪製與量測留在 render_slides.py。
"""

W, H = 1920, 1080

HEADER_BOX = (80, 60, 1840, 200)
CONTENT_BOX = (80, 240, 1840, 980)
CODE_BOX = (130, 280, 1790, 940)

TITLE_Y, SUB_Y = 80, 148
BULLET_Y0, BULLET_STEP = 310, 120
CENTER_X = W // 2
BULLET_MAX_W = 1650
CODE_X, CODE_Y0, CODE_STEP = 170, 310, 42
CODE_SIZE = 28

FIG_MAX_W = 1560
FIG_ROW_H = 104
FIG_GAP = 26
FIG_CAPTION_H = 46


def rect(x0, y0, x1, y1):
	"""(x0,y0,x1,y1) → 跟 layout.json 的框同一種形狀，免得兩種座標慣例混用"""
	return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}


def code_metrics(n):
	"""依行數決定行距與字級，保證 n 行一定關得進 CODE_BOX。

	prompt 允許 8–16 行，但固定 42px 行距在 15 行就剛好貼齊底線、16 行溢出 42px——
	差一行就爆版。15 行以內回傳原本的 42／28，既有教材的輸出逐像素不變
	"""
	step = min(CODE_STEP, (CODE_BOX[3] - CODE_Y0) // max(1, n))
	return step, max(12, min(CODE_SIZE, round(step * CODE_SIZE / CODE_STEP)))
```

- [ ] **Step 2：`render_slides.py` 改成匯入，刪掉自己那份**

刪除 `render_slides.py` 第 20-31 行之間的 `W, H`／`HEADER_BOX`／`CONTENT_BOX`／`CODE_BOX`／`TITLE_Y, SUB_Y`／`BULLET_Y0, BULLET_STEP`／`CENTER_X`／`BULLET_MAX_W`／`CODE_X, CODE_Y0, CODE_STEP`／`CODE_SIZE` 這些賦值，以及 `FIG_MAX_W`／`FIG_ROW_H`／`FIG_GAP`／`FIG_CAPTION_H` 四行、還有整個 `code_metrics` 函式。`THEME_DIR` 與 `DEFAULT_THEME` **留在原地**（那是主題不是幾何）。

在 `from fontTools.ttLib import TTFont` 之後加：

```python
from layout import (
	BULLET_MAX_W, BULLET_STEP, BULLET_Y0, CENTER_X, CODE_BOX, CODE_X, CODE_Y0,
	CONTENT_BOX, FIG_CAPTION_H, FIG_GAP, FIG_MAX_W, FIG_ROW_H, H, HEADER_BOX,
	SUB_Y, TITLE_Y, W, code_metrics,
)
```

`CODE_STEP` 與 `CODE_SIZE` 現在只有 `code_metrics` 用得到，`render_slides.py` 不需要匯入。若 grep 發現還有別處用到就一併加進匯入清單。

- [ ] **Step 3：`tests/test_render_slides.py` 改匯入來源**

該檔目前 `import render_slides as R` 後用 `R.CODE_STEP` 等。改成同時匯入：

```python
import layout as L
import render_slides as R
```

並把測試裡的 `R.code_metrics`、`R.CODE_STEP`、`R.CODE_SIZE`、`R.CODE_Y0`、`R.CODE_BOX` 全部改成 `L.` 前綴。`R.main()` 維持不變。

- [ ] **Step 4：跑測試**

Run: `.venv/bin/python -m unittest discover -s tests -t . -v`
Expected: 71 passed, 1 skipped, 0 failed。

- [ ] **Step 5：驗證逐像素不變（這一步是本 Task 的重點）**

跑上方「回歸基準」那段指令。
Expected: 輸出 `bf7997d90b8fd8b6863eb43178f9c28f`。**不是這個雜湊就是搬移過程改到了東西，回報 FAILED，不准把預期值改成跟輸出一致。**

- [ ] **Step 6：Commit**

```bash
git add video_engine/layout.py video_engine/render_slides.py tests/test_render_slides.py
git commit -m "refactor: 幾何常數搬進 layout.py"
```

---

### Task 2: `regions_for()` — 用區域取代寫死座標

**Files:**
- Modify: `video_engine/layout.py`
- Modify: `video_engine/render_slides.py`（`render_slide()` 與 `draw_figure()`）
- Create: `tests/test_layout.py`

**Interfaces:**
- Consumes：Task 1 的常數與 `rect()`
- Produces：`layout.regions_for(slide, index) -> dict`。鍵值固定為：

```python
{
	"variant": "stack",            # 版型名稱
	"text": {...},                 # 條列與 callout 的可用區域（rect）
	"text_align": "center",        # "center" 或 "left"
	"figure": {...} 或 None,       # figure 的可用區域
	"code": {...} 或 None,         # 程式碼的可用區域
}
```
`title`／`subtitle` **不在裡面**——它們永遠畫在 `HEADER_BOX`，那是換頁的錨點（見 spec 3.1）。

本 Task 只實作 `stack`，也就是把現況原樣搬進區域框架，**輸出仍須逐像素不變**。

- [ ] **Step 1：先寫失敗的測試**

新增 `tests/test_layout.py`：

```python
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))

import layout as L


def slide(*types, kind=None, n_bullets=0, hidden=()):
	"""照 lesson.schema 的形狀捏一頁，只帶版型會用到的欄位"""
	els = [{"id": "p1_title", "type": "title", "text": "t"},
		{"id": "p1_sub", "type": "subtitle", "text": "s"}]
	for i in range(n_bullets):
		els.append({"id": f"p1_b{i}", "type": "bullet", "text": "x",
			"hidden": i in hidden})
	for t in types:
		if t == "figure":
			els.append({"id": "p1_fig", "type": "figure", "kind": kind or "boxes",
				"items": ["a", "b"]})
		elif t == "code":
			els.append({"id": "p1_code", "type": "code", "lang": "c",
				"lines": ["int a;"] * 10})
	return {"id": "p1", "elements": els}


class TestRegionsStack(unittest.TestCase):
	def test_文字區域關在內容卡裡(self):
		r = L.regions_for(slide("figure", n_bullets=3), 0)
		t = r["text"]
		self.assertGreaterEqual(t["x"], L.CONTENT_BOX[0])
		self.assertGreaterEqual(t["y"], L.CONTENT_BOX[1])
		self.assertLessEqual(t["x"] + t["w"], L.CONTENT_BOX[2])
		self.assertLessEqual(t["y"] + t["h"], L.CONTENT_BOX[3])

	def test_hidden_不影響版位(self):
		# base 與 full 是同一份版位算出來的。這裡若不同，浮現時裁出來的就是錯位畫面
		a = L.regions_for(slide("figure", n_bullets=3), 0)
		b = L.regions_for(slide("figure", n_bullets=3, hidden=(1, 2)), 0)
		self.assertEqual(a, b)

	def test_沒有程式碼的頁面_code_區域是_None(self):
		self.assertIsNone(L.regions_for(slide("figure", n_bullets=3), 0)["code"])

	def test_有程式碼的頁面_code_區域等於_CODE_BOX(self):
		r = L.regions_for(slide("code"), 0)
		self.assertEqual(r["code"], L.rect(*L.CODE_BOX))


if __name__ == "__main__":
	unittest.main()
```

- [ ] **Step 2：跑測試確認它紅**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: FAIL，`AttributeError: module 'layout' has no attribute 'regions_for'`

- [ ] **Step 3：實作 `regions_for()`（只有 `stack`）**

在 `layout.py` 加：

```python
def fig_height(el):
	"""先算高度，才能把整塊內容垂直置中"""
	cap = FIG_CAPTION_H if el.get("caption") else 0
	if el["kind"] == "compare":
		n = max(len(el.get("left", {}).get("items", [])),
			len(el.get("right", {}).get("items", [])))
		return 64 + n * 74 + cap
	return FIG_ROW_H + cap


def regions_for(slide, index):
	"""這一頁的哪塊區域給誰。index 是頁次，供需要鏡像的版型使用。

	title／subtitle 不在回傳值裡——它們永遠畫在 HEADER_BOX，
	那是換頁交叉淡化時唯一不動的錨點
	"""
	els = slide["elements"]
	has_code = any(e["type"] == "code" for e in els)
	# 條列計數不分 hidden：base 與 full 必須算出同一份版位
	n_bullets = sum(1 for e in els if e["type"] in ("bullet", "callout"))
	figs = [e for e in els if e["type"] == "figure"]

	bullets_h = (n_bullets - 1) * BULLET_STEP + 48 if n_bullets else 0
	figs_h = sum(fig_height(f) + 40 for f in figs)
	block_h = bullets_h + figs_h
	top = (CONTENT_BOX[1] + (CONTENT_BOX[3] - CONTENT_BOX[1] - block_h) // 2
		if block_h else BULLET_Y0)

	return {
		"variant": "stack",
		"text": rect(CONTENT_BOX[0], top, CONTENT_BOX[2], top + bullets_h),
		"text_align": "center",
		"figure": rect(CONTENT_BOX[0], top + bullets_h + (40 if bullets_h else 0),
			CONTENT_BOX[2], CONTENT_BOX[3]) if figs else None,
		"code": rect(*CODE_BOX) if has_code else None,
	}
```

`fig_height` 從 `render_slides.py` 搬過來（那是純算式），`render_slides.py` 改成 `from layout import fig_height`。

- [ ] **Step 4：跑測試確認它綠**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: 4 passed

- [ ] **Step 5：`render_slide()` 改成消費區域**

在 `render_slide()` 開頭，把現行第 205-213 行那段 `n_bullets`／`figs`／`bullets_h`／`figs_h`／`block_h`／`bullet_y`／`fig_y` 的計算整段刪掉，換成：

```python
	reg = regions_for(slide, idx - 1)      # idx 從 1 起算，版型用 0 起算的頁次
	bullet_y = reg["text"]["y"]
	fig_y = reg["figure"]["y"] if reg["figure"] else bullet_y
```

`draw_centered` 與 `draw_figure` 這一步**先不動**——它們仍用 `CENTER_X`。目的是把「算版位」與「畫」切開，行為零改變。

- [ ] **Step 6：跑測試 + 逐像素驗證**

Run: `.venv/bin/python -m unittest discover -s tests -t . && ` 接著跑「回歸基準」那段指令
Expected: 全綠，且雜湊仍為 `bf7997d90b8fd8b6863eb43178f9c28f`。**雜湊變了就是重構改到行為，回報 FAILED。**

- [ ] **Step 7：Commit**

```bash
git add video_engine/layout.py video_engine/render_slides.py tests/test_layout.py
git commit -m "refactor: render_slides 改用 regions_for 取得版位"
```

---

### Task 3: `split` 版型 — 左右分欄

**Files:**
- Modify: `video_engine/layout.py`（新增 `pick_variant`，`regions_for` 支援 `split`）
- Modify: `video_engine/render_slides.py`（`draw_centered` 支援靠左、`draw_figure` 接受區域）
- Modify: `tests/test_layout.py`

**Interfaces:**
- Consumes：Task 2 的 `regions_for` 回傳結構
- Produces：`layout.pick_variant(slide) -> str`（`"stack"` / `"split"` / `"stage"` / `"code"`）

**版型規則**：`figure.kind in ("boxes", "steps")` → `split`。內容卡切成左右兩欄，中間 60px 溝，兩側各留 40px 內距。左右由頁次奇偶鏡像（偶數頁文字在左、奇數頁文字在右）。文字欄改**靠左對齊**。

- [ ] **Step 1：先寫失敗的測試**

加進 `tests/test_layout.py`：

```python
class TestPickVariant(unittest.TestCase):
	def test_有程式碼一律走_code(self):
		self.assertEqual(L.pick_variant(slide("code")), "code")

	def test_compare_走_stage(self):
		self.assertEqual(L.pick_variant(slide("figure", kind="compare", n_bullets=3)), "stage")

	def test_boxes_與_steps_走_split(self):
		for k in ("boxes", "steps"):
			self.assertEqual(L.pick_variant(slide("figure", kind=k, n_bullets=3)), "split", k)

	def test_純文字頁走_stack(self):
		self.assertEqual(L.pick_variant(slide(n_bullets=3)), "stack")


class TestRegionsSplit(unittest.TestCase):
	def _r(self, index):
		return L.regions_for(slide("figure", kind="boxes", n_bullets=3), index)

	def test_文字與圖不重疊(self):
		for index in (0, 1):
			r = self._r(index)
			t, f = r["text"], r["figure"]
			self.assertTrue(t["x"] + t["w"] <= f["x"] or f["x"] + f["w"] <= t["x"],
				f"第 {index} 頁的文字欄與圖欄重疊了")

	def test_兩欄都關在內容卡裡(self):
		r = self._r(0)
		for key in ("text", "figure"):
			b = r[key]
			self.assertGreaterEqual(b["x"], L.CONTENT_BOX[0], key)
			self.assertLessEqual(b["x"] + b["w"], L.CONTENT_BOX[2], key)

	def test_奇偶頁鏡像(self):
		# 同一堂課出現兩頁同 kind 的 figure 時，純內容驅動會讓它們長得一樣
		self.assertLess(self._r(0)["text"]["x"], self._r(1)["text"]["x"])

	def test_文字欄靠左對齊(self):
		self.assertEqual(self._r(0)["text_align"], "left")

	def test_hidden_不影響版位(self):
		a = L.regions_for(slide("figure", kind="boxes", n_bullets=3), 0)
		b = L.regions_for(slide("figure", kind="boxes", n_bullets=3, hidden=(1, 2)), 0)
		self.assertEqual(a, b)
```

- [ ] **Step 2：跑測試確認它紅**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: FAIL（`pick_variant` 不存在）

- [ ] **Step 3：實作 `pick_variant` 與 `split` 區域**

```python
COL_GAP = 60
COL_PAD = 40


def pick_variant(slide):
	"""版型由內容組成推導，不由教材指定，也不隨機。

	一堂課的序列固定是 compare → boxes → code → steps，四種內容配四種幾何，
	同一堂課內自然就不重複——不需要靠頁次輪替製造變化
	"""
	els = slide["elements"]
	if any(e["type"] == "code" for e in els):
		return "code"
	fig = next((e for e in els if e["type"] == "figure"), None)
	if fig is None:
		return "stack"
	return "stage" if fig["kind"] == "compare" else "split"
```

`regions_for` 依 `pick_variant` 分流。`split` 的切法：

```python
	x0, y0, x1, y1 = CONTENT_BOX
	half = (x1 - x0 - COL_GAP) // 2
	left = rect(x0 + COL_PAD, y0 + COL_PAD, x0 + half - COL_PAD, y1 - COL_PAD)
	right = rect(x0 + half + COL_GAP + COL_PAD, y0 + COL_PAD, x1 - COL_PAD, y1 - COL_PAD)
	text_left = index % 2 == 0          # 偶數頁文字在左
	return {
		"variant": "split",
		"text": left if text_left else right,
		"text_align": "left",
		"figure": right if text_left else left,
		"code": None,
	}
```

- [ ] **Step 4：跑測試確認它綠**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: 全 passed

- [ ] **Step 5：`draw_centered` 支援靠左對齊**

`render_slides.py` 的 `draw_centered(targets, measure, text, y, font, color)` 目前寫死 `CENTER_X` 與 `anchor="ma"`。改成多收一個區域參數，靠左時錨在區域左緣、`anchor="la"`：

```python
def draw_text_block(targets, measure, text, y, font, color, region, align):
	"""在指定區域內畫一行文字。align="center" 沿用舊行為（畫布中線 + "ma"），
	"left" 則錨在區域左緣。回傳實測墨水框"""
	if align == "left":
		x, anchor = region["x"], "la"
	else:
		x, anchor = CENTER_X, "ma"
	for d in targets:
		d.text((x, y), text, font=font, fill=color, anchor=anchor)
	return ink_box(measure, (x, y), text, font, anchor=anchor)
```

保留舊的 `draw_centered` 當薄包裝或直接全數改呼叫新函式——擇一，在報告裡說明選了哪個與理由。`title`／`subtitle` 一律走 `align="center"`（它們在 HEADER_BOX，不受版型影響）。

條列的 `fit_font` 寬度上限改用 `region["w"]` 而非寫死的 `BULLET_MAX_W`，`stack` 版型的區域寬度本來就是 `BULLET_MAX_W` 等價值——若不等價會導致 Task 2 的雜湊變動，那時回報而不要自己調整常數。

- [ ] **Step 6：`draw_figure` 接受區域，窄欄改直向**

`draw_figure(targets, measure, el, th, top, guard)` 改成 `draw_figure(targets, measure, el, th, region, guard)`。`boxes`／`steps` 依 `region["w"]` 決定橫排或直排：

- 橫排所需寬度 = `n * min(360, ...) + gap * (n - 1)`；區域寬度容不下時改直排。
- 直排：每格寬 `min(360, region["w"])`、垂直堆疊、`steps` 的箭頭由向右改為向下（三角形頂點改成朝下）。
- 直排的每一格一樣要寫進 `boxes[f"{eid}:i{i}"]`——**代號一個都不能少**。

`compare` 這一步不動（它走 `stage`，Task 4 才處理）。

- [ ] **Step 7：跑全套測試**

Run: `.venv/bin/python -m unittest discover -s tests -t . -v`
Expected: 全綠。**注意：從這一步起 44 張 PNG 的雜湊會改變，這是預期的。**

- [ ] **Step 8：產圖確認沒有溢出**

```bash
.venv/bin/python video_engine/render_slides.py video_engine/examples/c_loop.lesson.json /tmp/t3
```
接著用 `layout.json` 斷言每個 `p*_fig:i*` 的框都落在該頁 figure 區域內（寫成一次性腳本即可，不必進版控）。
Expected: 零筆越界。

- [ ] **Step 9：Commit**

```bash
git add video_engine/layout.py video_engine/render_slides.py tests/test_layout.py
git commit -m "feat: split 版型與窄欄直向 figure"
```

---

### Task 4: `stage` 與 `code` 版型

**Files:**
- Modify: `video_engine/layout.py`
- Modify: `video_engine/render_slides.py`
- Modify: `tests/test_layout.py`

**Interfaces:**
- Consumes：Task 3 的 `pick_variant`
- Produces：`regions_for` 支援 `"stage"` 與 `"code"`

**`stage`**（`figure.kind == "compare"`）：條列收到內容卡頂部一條帶狀區域（高度依條數，上限為內容卡的 40%），compare 拿下方剩餘的整片寬度。面板寬度由現行 700px 放寬到區域允許的最大值。

**`code`**：`CODE_BOX` 不變（外框是錨點），但程式碼整塊依 `code_metrics` 算出的總高度**垂直置中**於 `CODE_BOX`，消掉 10 行時下方 210px 的死白。

- [ ] **Step 1：先寫失敗的測試**

```python
class TestRegionsStage(unittest.TestCase):
	def _r(self):
		return L.regions_for(slide("figure", kind="compare", n_bullets=3), 0)

	def test_文字在上_圖在下_不重疊(self):
		r = self._r()
		t, f = r["text"], r["figure"]
		self.assertLessEqual(t["y"] + t["h"], f["y"], "文字帶與圖區重疊")

	def test_圖區比_split_的欄位寬(self):
		stage = self._r()["figure"]["w"]
		split = L.regions_for(slide("figure", kind="boxes", n_bullets=3), 0)["figure"]["w"]
		self.assertGreater(stage, split, "compare 走 stage 的理由就是它需要寬度")

	def test_文字帶不超過內容卡四成高(self):
		r = self._r()
		self.assertLessEqual(r["text"]["h"], (L.CONTENT_BOX[3] - L.CONTENT_BOX[1]) * 0.4)


class TestRegionsCode(unittest.TestCase):
	def test_程式碼整塊垂直置中(self):
		r = L.regions_for(slide("code"), 0)          # 10 行
		step, _ = L.code_metrics(10)
		top = L.code_top(10)
		above = top - L.CODE_BOX[1]
		below = L.CODE_BOX[3] - (top + 10 * step)
		self.assertLessEqual(abs(above - below), 2, "上下留白差超過 2px 就不算置中")

	def test_置中後仍不溢出(self):
		for n in range(1, 41):
			step, _ = L.code_metrics(n)
			top = L.code_top(n)
			self.assertGreaterEqual(top, L.CODE_BOX[1], f"{n} 行")
			self.assertLessEqual(top + n * step, L.CODE_BOX[3], f"{n} 行")
```

- [ ] **Step 2：跑測試確認它紅**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: FAIL（`code_top` 不存在、`stage` 未實作）

- [ ] **Step 3：實作**

```python
def code_top(n):
	"""程式碼整塊在 CODE_BOX 內垂直置中的起始 y。

	舊版固定從 CODE_Y0 開始，10 行的話下方留 210px 死白
	"""
	step, _ = code_metrics(n)
	return CODE_BOX[1] + max(0, (CODE_BOX[3] - CODE_BOX[1] - n * step) // 2)
```

`stage` 的切法：文字帶高度 `min(bullets_h, (y1 - y0) * 0.4)`，圖區為其下方剩餘部分，左右各留 `COL_PAD`。

`render_slides.py` 的程式碼繪製把起始 y 由 `CODE_Y0` 改成 `code_top(len(lines))`；`draw_figure` 的 `compare` 分支面板寬度由寫死的 700 改成 `(region["w"] - mid) // 2`，字級隨寬度用 `fit_font` 調整。

- [ ] **Step 4：跑測試確認它綠**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: 全 passed

- [ ] **Step 5：跑全套 + 產圖**

Run: `.venv/bin/python -m unittest discover -s tests -t .`
接著對五份教材各產一次圖，確認沒有例外。
Expected: 全綠、五份都成功。

- [ ] **Step 6：Commit**

```bash
git add video_engine/layout.py video_engine/render_slides.py tests/test_layout.py
git commit -m "feat: stage 版型與程式碼垂直置中"
```

---

### Task 5: 容量降級與全語料不變量

**Files:**
- Modify: `video_engine/layout.py`
- Modify: `tests/test_layout.py`
- Modify: `tests/test_render_slides.py`

**Interfaces:**
- Consumes：Task 3、4 的全部版型
- Produces：`regions_for` 在容量不足時自動降級為 `stack`

**降級規則**：`split` 的文字欄若容不下條列（`(n-1) * BULLET_STEP + 48 > 欄高`，且把 `BULLET_STEP` 壓到下限 `BULLET_STEP_MIN = 80` 仍容不下），改回 `stack`。降級是設計的一部分，不是失敗。

- [ ] **Step 1：先寫失敗的測試**

```python
class TestDowngrade(unittest.TestCase):
	def test_條列太多時_split_降級為_stack(self):
		r = L.regions_for(slide("figure", kind="boxes", n_bullets=12), 0)
		self.assertEqual(r["variant"], "stack", "12 條放不進半欄，該降級")

	def test_降級後仍不溢出內容卡(self):
		for n in range(1, 16):
			r = L.regions_for(slide("figure", kind="boxes", n_bullets=n), 0)
			for key in ("text", "figure"):
				b = r[key]
				if not b:
					continue
				self.assertGreaterEqual(b["y"], L.CONTENT_BOX[1], f"{n} 條 {key}")
				self.assertLessEqual(b["y"] + b["h"], L.CONTENT_BOX[3], f"{n} 條 {key}")

	def test_正常條數不會被誤降級(self):
		# 實測語料最多 3 條，這個範圍內必須維持 split
		for n in (2, 3, 4):
			self.assertEqual(L.regions_for(slide("figure", kind="boxes", n_bullets=n), 0)["variant"],
				"split", f"{n} 條")
```

加進 `tests/test_render_slides.py` 的全語料不變量：

```python
class TestCorpusInvariants(unittest.TestCase):
	"""五份現成教材是唯一的真實樣本，每個不變量都要對它們成立"""

	LESSONS = ("c_loop", "c_string", "c_struct", "c_struct_combo", "c_struct_v3")

	def _render(self, name):
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
		src = os.path.join(ROOT, "video_engine/examples", f"{name}.lesson.json")
		old = sys.argv
		sys.argv = ["render_slides.py", src, d]
		try:
			self.assertEqual(R.main(), 0)
		finally:
			sys.argv = old
		with open(os.path.join(d, "layout.json"), encoding="utf-8") as f:
			return json.load(f), d

	def test_每個元素都有量測框(self):
		for name in self.LESSONS:
			lay, _ = self._render(name)
			with open(os.path.join(ROOT, "video_engine/examples", f"{name}.lesson.json"),
					encoding="utf-8") as f:
				lesson = json.load(f)
			for page, sl in zip(lay["slides"], lesson["slides"]):
				for el in sl["elements"]:
					self.assertIn(el["id"], page["boxes"], f"{name} {el['id']} 沒有量測框")
					if el["type"] == "code":
						for i in range(1, len(el["lines"]) + 1):
							self.assertIn(f"{el['id']}:L{i}", page["boxes"], f"{name} 第 {i} 行")

	def test_所有框都在畫布內(self):
		for name in self.LESSONS:
			lay, _ = self._render(name)
			for page in lay["slides"]:
				for key, b in page["boxes"].items():
					self.assertGreaterEqual(b["x"], 0, f"{name} {key}")
					self.assertGreaterEqual(b["y"], 0, f"{name} {key}")
					self.assertLessEqual(b["x"] + b["w"], L.W, f"{name} {key}")
					self.assertLessEqual(b["y"] + b["h"], L.H, f"{name} {key}")

	def test_同一份教材連跑兩次逐位元組相同(self):
		import hashlib
		def digest(name):
			_, d = self._render(name)
			h = hashlib.md5()
			for f in sorted(os.listdir(d)):
				if f.endswith(".png"):
					with open(os.path.join(d, f), "rb") as fh:
						h.update(fh.read())
			return h.hexdigest()
		self.assertEqual(digest("c_loop"), digest("c_loop"), "版型引入了非決定性")
```

- [ ] **Step 2：跑測試確認它紅**

Run: `.venv/bin/python -m unittest tests.test_layout tests.test_render_slides -v`
Expected: 降級那組 FAIL。全語料那組若已經綠，表示前面的 Task 已經守住——在報告裡註明，不要因此刪掉測試。

- [ ] **Step 3：實作降級**

`regions_for` 在回傳 `split` 之前先檢查文字欄容量，不足就 `return` `stack` 的結果。實作成一個小輔助函式，避免 `regions_for` 變成一大坨 if。

- [ ] **Step 4：跑全套測試**

Run: `.venv/bin/python -m unittest discover -s tests -t . -v`
Expected: 全綠。

- [ ] **Step 5：產出前後對照**

對五份教材各產一次圖，與 Task 1 之前的基準版並排存成 `/tmp/layout-compare/`，每頁一組（前／後）。這是給人看的，不進版控。
**不要自行判定視覺好壞**——產出後回報路徑即可。

- [ ] **Step 6：Commit**

```bash
git add video_engine/layout.py tests/test_layout.py tests/test_render_slides.py
git commit -m "feat: 版型容量降級與全語料不變量測試"
```
