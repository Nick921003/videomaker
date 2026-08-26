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

## 審查後鎖定的幾何數字

2026-08-26 對抗審查抓到三處算錯，已修正。**這些是事實，不要自己重算或調整**：

| 量 | 值 | 說明 |
| --- | --- | --- |
| `CONTENT_BOX` 內寬 | 1760 | `1840 - 80` |
| `BULLET_MAX_W` | 1650 | 與內寬**不等**，左右各有 55px 內距 |
| `CARD_PAD_X` | 55 | `(1760 - 1650) // 2`。`stack` 文字區必須用它，寬度才精確等於 1650 |
| `split` 可用欄寬 | 810 | `(1760 - 2*40 - 60) // 2`。初稿的算式重複扣了內距，中溝會膨脹成 140px |
| `stack` 溢出門檻 | 7 條 | `(7-1)*120+48 = 768 > 740`。6 條還安全 |

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

**Task 對照**：1 常數搬移 → 2 區域框架（`stack`）→ **3A** 版型分流與文字靠左 → **3B** figure 區域化與窄欄直排 → 4 `stage` 與 `code` → 5 全語料不變量。3 拆成 3A／3B 是審查結論：初稿的 Task 3 同時改文字與圖形，一個 reviewer 沒辦法在一輪內看完。

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
BULLET_SIZE = 38
CENTER_X = W // 2
BULLET_MAX_W = 1650
CODE_X, CODE_Y0, CODE_STEP = 170, 310, 42
CODE_SIZE = 28

FIG_MAX_W = 1560
FIG_ROW_H = 104
FIG_GAP = 26
FIG_CAPTION_H = 46


# 文字不貼卡片邊：BULLET_MAX_W 比內容卡內寬窄 110px，左右各 55px。
# 這個內距一直存在，只是以前藏在 fit_font 的寬度上限裡沒有名字
CARD_PAD_X = (CONTENT_BOX[2] - CONTENT_BOX[0] - BULLET_MAX_W) // 2


def bullet_metrics(n):
	"""依條數決定行距與字級，跟 code_metrics 同一個形狀。

	7 條起 (n-1)*120+48 就超過內容卡的 740px 高。prompt 規則 4 只給 2–4 條、
	實測語料最多 3 條，但 schema 沒設上限——沒有這個函式的話，降級回 stack
	之後照樣爆版，只是換個地方爆"""
	avail = CONTENT_BOX[3] - CONTENT_BOX[1] - 48
	step = min(BULLET_STEP, avail // (n - 1)) if n > 1 else BULLET_STEP
	return step, max(16, min(BULLET_SIZE, round(step * BULLET_SIZE / BULLET_STEP)))


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
	BULLET_MAX_W, BULLET_SIZE, BULLET_STEP, BULLET_Y0, CARD_PAD_X, CENTER_X,
	CODE_BOX, CODE_X, CODE_Y0, CONTENT_BOX, FIG_CAPTION_H, FIG_GAP, FIG_MAX_W,
	FIG_ROW_H, H, HEADER_BOX, SUB_Y, TITLE_Y, W, bullet_metrics, code_metrics,
)
```

後續 Task 會再加入 `code_top`、`fig_height`、`pick_variant`、`regions_for`。**每個 Task 自己負責把新用到的名字加進這份清單**——漏加會在跑測試時炸 `NameError`。

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

	def test_stack_文字區寬度必須等於_BULLET_MAX_W(self):
		# 內容卡內寬是 1760，比 BULLET_MAX_W 寬 110px。這裡若用了內寬，
		# Task 3A 把 fit_font 上限改讀區域寬時，文字會突然可以貼到卡片邊
		r = L.regions_for(slide("figure", n_bullets=3), 0)
		self.assertEqual(r["text"]["w"], L.BULLET_MAX_W)

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

	# 這裡刻意用固定的 BULLET_STEP，不用 bullet_metrics。
	# render_slide 的繪製迴圈這一步還是以 BULLET_STEP 遞增，兩邊必須算同一個值，
	# 否則 7 條以上就分歧（738 vs 768），逐像素不變的承諾在那個區間破功。
	# 自適應行距由 Task 3A 在兩處同時換上
	bullets_h = (n_bullets - 1) * BULLET_STEP + 48 if n_bullets else 0
	figs_h = sum(fig_height(f) + 40 for f in figs)
	block_h = bullets_h + figs_h
	top = (CONTENT_BOX[1] + (CONTENT_BOX[3] - CONTENT_BOX[1] - block_h) // 2
		if block_h else BULLET_Y0)

	return {
		"variant": "stack",
		# 左右各留 CARD_PAD_X，寬度才精確等於 BULLET_MAX_W。
		# 直接用 CONTENT_BOX 的內寬會是 1760，比舊的上限寬 110px，文字會貼到卡片邊
		"text": rect(CONTENT_BOX[0] + CARD_PAD_X, top,
			CONTENT_BOX[2] - CARD_PAD_X, top + bullets_h),
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

### Task 3A: `pick_variant` 與 `split` 的文字側

**Files:**
- Modify: `video_engine/layout.py`
- Modify: `video_engine/render_slides.py`（`draw_centered` → `draw_text_block`）
- Modify: `tests/test_layout.py`

**Interfaces:**
- Consumes：Task 2 的 `regions_for` 回傳結構、`bullet_metrics`
- Produces：`layout.pick_variant(slide) -> str`、`regions_for` 支援 `"split"`、`render_slides.draw_text_block(...)`

**本 Task 只動文字側。`draw_figure` 一行都不准改**——圖形側是 Task 3B。`split` 的 figure 這一步會被畫在區域的左上角而不是置中，那是預期的中間狀態，Task 3B 收尾。

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

	def test_多張圖退回_stack(self):
		# split 只切出一塊 figure 區域，兩張圖都從那塊的頂端起畫會完全疊在一起。
		# schema 沒限制每頁一張，只有 prompt 有——擋在這裡才擋得住
		sl = slide("figure", kind="boxes", n_bullets=2)
		sl["elements"].append({"id": "p1_fig2", "type": "figure", "kind": "steps",
			"items": ["a", "b"]})
		self.assertEqual(L.pick_variant(sl), "stack")

	def test_有_image_退回_stack(self):
		# image 是寫死座標貼上去的（render_slides 的 pos = ((W-w)//2, 320)），
		# 不吃區域。放進分欄版型會被條列壓在上面
		sl = slide(n_bullets=2)
		sl["elements"].append({"id": "p1_img", "type": "image", "src": "x.png"})
		self.assertEqual(L.pick_variant(sl), "stack")


class TestRegionsSplit(unittest.TestCase):
	def _r(self, index, n_bullets=3):
		return L.regions_for(slide("figure", kind="boxes", n_bullets=n_bullets), index)

	def test_文字與圖不重疊(self):
		for index in (0, 1):
			r = self._r(index)
			t, f = r["text"], r["figure"]
			self.assertTrue(t["x"] + t["w"] <= f["x"] or f["x"] + f["w"] <= t["x"],
				f"第 {index} 頁的文字欄與圖欄重疊了")

	def test_中溝正好六十像素(self):
		# 初稿的算式在 half 扣掉 COL_GAP 之後又在兩欄內側各扣一次 COL_PAD，
		# 中溝膨脹成 140px、每欄無故少 40px
		r = self._r(0)
		t, f = r["text"], r["figure"]
		gap = f["x"] - (t["x"] + t["w"])
		self.assertEqual(gap, L.COL_GAP)

	def test_欄寬是八一零(self):
		self.assertEqual(self._r(0)["text"]["w"], 810)

	def test_兩欄都關在內容卡裡(self):
		r = self._r(0)
		for key in ("text", "figure"):
			b = r[key]
			self.assertGreaterEqual(b["x"], L.CONTENT_BOX[0], key)
			self.assertLessEqual(b["x"] + b["w"], L.CONTENT_BOX[2], key)

	def test_奇偶頁鏡像(self):
		# 同一堂課出現兩頁同 kind 的 figure 時（c_loop 的 p1 與 p4 都是 compare），
		# 純內容驅動會讓它們長得一樣
		self.assertLess(self._r(0)["text"]["x"], self._r(1)["text"]["x"])

	def test_文字欄靠左對齊(self):
		self.assertEqual(self._r(0)["text_align"], "left")

	def test_條列太多時降級為_stack(self):
		# 降級檢查放這裡而不是留到 Task 5：split 一啟用就需要它，
		# 中間留一個 Task 的防禦空窗沒有道理
		self.assertEqual(self._r(0, n_bullets=12)["variant"], "stack")

	def test_實際會出現的條數不會被誤降級(self):
		# prompt 規則 4 給 2–4 條，實測語料最多 3 條
		for n in (2, 3, 4):
			self.assertEqual(self._r(0, n_bullets=n)["variant"], "split", f"{n} 條")

	def test_hidden_不影響版位(self):
		a = L.regions_for(slide("figure", kind="boxes", n_bullets=3), 0)
		b = L.regions_for(slide("figure", kind="boxes", n_bullets=3, hidden=(1, 2)), 0)
		self.assertEqual(a, b)
```

- [ ] **Step 2：跑測試確認它紅**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: FAIL，`AttributeError: module 'layout' has no attribute 'pick_variant'`

- [ ] **Step 3：實作 `pick_variant`**

```python
COL_GAP = 60
COL_PAD = 40
SPLIT_MAX_BULLETS = 6      # 半欄高 660，(6-1)*120+48 = 648 剛好放得下


def pick_variant(slide):
	"""版型由內容組成推導，不由教材指定，也不隨機。

	一堂課的序列固定是 compare → boxes → code → steps，四種內容配四種幾何，
	同一堂課內自然就不重複——不需要靠頁次輪替製造變化。
	image 與多張圖一律退回 stack：前者是寫死座標貼上去的、不吃區域，
	後者在只切出一塊圖區的版型裡會整個疊在一起
	"""
	els = slide["elements"]
	if any(e["type"] == "code" for e in els):
		return "code"
	if any(e["type"] == "image" for e in els):
		return "stack"
	figs = [e for e in els if e["type"] == "figure"]
	if len(figs) != 1:
		return "stack"
	return "stage" if figs[0]["kind"] == "compare" else "split"
```

- [ ] **Step 4：實作 `split` 的區域切分**

`regions_for` 依 `pick_variant` 分流。`split` 的切法（**注意內距只扣一次**）：

```python
	x0, y0, x1, y1 = CONTENT_BOX
	col_w = (x1 - x0 - 2 * COL_PAD - COL_GAP) // 2
	left = rect(x0 + COL_PAD, y0 + COL_PAD, x0 + COL_PAD + col_w, y1 - COL_PAD)
	right = rect(x0 + COL_PAD + col_w + COL_GAP, y0 + COL_PAD, x1 - COL_PAD, y1 - COL_PAD)
	if n_bullets > SPLIT_MAX_BULLETS:
		return _stack(slide, index)      # 半欄放不下就退回整幅
	text_left = index % 2 == 0           # 偶數頁文字在左
	return {
		"variant": "split",
		"text": left if text_left else right,
		"text_align": "left",
		"figure": right if text_left else left,
		"code": None,
	}
```

`stack` 的那段抽成 `_stack(slide, index)` 供降級重用——`regions_for` 不要變成一大坨 if。

- [ ] **Step 5：跑測試確認它綠**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: 全 passed

- [ ] **Step 6：`draw_text_block` 取代 `draw_centered`**

`render_slides.py` 現行的 `draw_centered(targets, measure, text, y, font, color)` 寫死 `CENTER_X` 與 `anchor="ma"`。改成：

```python
def draw_text_block(targets, measure, text, y, font, color, region=None, align="center"):
	"""在指定區域內畫一行文字。

	align="center" 沿用舊行為（畫布中線 + "ma" 錨點），"left" 錨在區域左緣。
	region 只有靠左時會用到——標題與副標永遠置中於 HEADER_BOX，不吃區域
	"""
	if align == "left" and region:
		x, anchor = region["x"], "la"
	else:
		x, anchor = CENTER_X, "ma"
	for d in targets:
		d.text((x, y), text, font=font, fill=color, anchor=anchor)
	return ink_box(measure, (x, y), text, font, anchor=anchor)
```

**把 `draw_centered` 整個刪掉**，所有呼叫點改用新函式（專案沒有外部使用者，留薄包裝只是多一層）。`title` 與 `subtitle` 用預設值即可（不傳 region、align 走 center）。

- [ ] **Step 7：條列改吃區域**

`render_slide` 裡條列與 callout 那一支：

- `fit_font` 的寬度上限由寫死的 `BULLET_MAX_W` 改成 `reg["text"]["w"]`
- 呼叫改成 `draw_text_block(targets, df, text, bullet_y, font, color, reg["text"], reg["text_align"])`
- 字級起始值與 `bullet_y` 的遞增量改用 `bullet_metrics(n_bullets)` 回傳的 `size` 與 `step`

**這一步必須與 `layout.py` 的 `_stack()` 同時改。** Task 2 的 `_stack()` 用的是固定 `BULLET_STEP`，因為當時繪製迴圈也是固定的；現在繪製改成自適應，`_stack()` 的 `bullets_h` 也要跟著改成 `bullet_metrics` 的 `step`。**只改一邊，7 條以上的頁面版位就會對不上**（`_stack` 算 738、迴圈實際畫 768），而條列會從內容卡下緣溢出。

加一則測試把這件事釘住：

```python
	def test_版位高度與繪製遞增量必須同源(self):
		# 只改一邊的話 7 條就分歧：_stack 算 738、繪製迴圈實際走 768
		for n in (3, 7, 12):
			step, _ = L.bullet_metrics(n)
			r = L.regions_for(slide(n_bullets=n), 0)
			self.assertEqual(r["text"]["h"], (n - 1) * step + 48, f"{n} 條")
```

**變數名是 `reg` 不是 `region`**（Task 2 Step 5 定的）。`reg["text"]["w"]` 在 `stack` 時等於 `BULLET_MAX_W`（Task 2 已加測試保證），所以 `stack` 頁的字級不會變。

- [ ] **Step 8：跑全套測試**

Run: `.venv/bin/python -m unittest discover -s tests -t . -v`
Expected: 全綠。**從這一步起 44 張 PNG 的雜湊會改變，這是預期的。**

- [ ] **Step 9：Commit**

```bash
git add video_engine/layout.py video_engine/render_slides.py tests/test_layout.py
git commit -m "feat: split 版型與文字靠左對齊"
```

---

### Task 3B: `draw_figure` 區域化與窄欄直排

**Files:**
- Modify: `video_engine/render_slides.py`（`draw_figure` 全部三個分支）
- Modify: `tests/test_render_slides.py`

**Interfaces:**
- Consumes：Task 3A 的 `split` 區域
- Produces：`draw_figure(targets, measure, el, th, region, guard)`

**這一步必須把三個分支一次改完，`compare` 不能留在舊簽名。** `compare` 分支現在有四處直接對 `top` 做整數運算（`[px, top, px + panel_w, top + 52]`、`y = top + 64`、`cy = top + h // 2`、`boxes[eid] = {..., "y": top, ...}`）。只改簽名不改內文的話，第一次渲染 `compare` 頁就炸 `TypeError: unsupported operand type(s) for +: 'dict' and 'int'`——而語料裡 `c_string`／`c_struct`／`c_loop` 的第一頁全是 `compare`，測試必死。

- [ ] **Step 1：先寫失敗的測試**

加進 `tests/test_render_slides.py`：

```python
class TestFigureInRegion(unittest.TestCase):
	"""窄欄裡的 figure 必須改直排，而且每個項目的量測框都要留下——
	少一個，指到它的動作就靜默失效"""

	def _render(self, kind, items, n_bullets=3):
		els = [{"id": "p1_title", "type": "title", "text": "測試"}]
		for i in range(n_bullets):
			els.append({"id": f"p1_b{i}", "type": "bullet", "text": "條列"})
		els.append({"id": "p1_fig", "type": "figure", "kind": kind, "items": items})
		lesson = {"lesson_id": "t", "title": "t",
			"slides": [{"id": "p1", "elements": els}]}
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
		path = os.path.join(d, "t.lesson.json")
		with open(path, "w", encoding="utf-8") as f:
			json.dump(lesson, f)
		old = sys.argv
		sys.argv = ["render_slides.py", path, d]
		try:
			self.assertEqual(R.main(), 0)
		finally:
			sys.argv = old
		with open(os.path.join(d, "layout.json"), encoding="utf-8") as f:
			return json.load(f)["slides"][0]["boxes"]

	def test_每個項目都留下量測框(self):
		boxes = self._render("boxes", ["甲", "乙", "丙"])
		for i in (1, 2, 3):
			self.assertIn(f"p1_fig:i{i}", boxes)

	def test_項目都關在圖區內(self):
		import layout as L
		boxes = self._render("steps", ["甲", "乙", "丙", "丁"])
		reg = L.regions_for({"id": "p1", "elements": [
			{"id": "p1_title", "type": "title", "text": "t"},
			{"id": "p1_b0", "type": "bullet", "text": "x"},
			{"id": "p1_b1", "type": "bullet", "text": "x"},
			{"id": "p1_b2", "type": "bullet", "text": "x"},
			{"id": "p1_fig", "type": "figure", "kind": "steps",
				"items": ["甲", "乙", "丙", "丁"]}]}, 0)["figure"]
		for i in (1, 2, 3, 4):
			b = boxes[f"p1_fig:i{i}"]
			self.assertGreaterEqual(b["x"], reg["x"], f"i{i} 跑到圖區左邊外")
			self.assertLessEqual(b["x"] + b["w"], reg["x"] + reg["w"], f"i{i} 跑到圖區右邊外")
			self.assertLessEqual(b["y"] + b["h"], reg["y"] + reg["h"], f"i{i} 跑到圖區下面外")

	def test_窄欄時真的改成直排(self):
		# 直排的判準：項目之間 y 遞增而 x 相同
		boxes = self._render("boxes", ["甲", "乙", "丙"])
		a, b = boxes["p1_fig:i1"], boxes["p1_fig:i2"]
		self.assertEqual(a["x"], b["x"], "還是橫排")
		self.assertGreater(b["y"], a["y"])

	def test_compare_頁不會崩潰(self):
		# compare 分支有四處直接對 top 做整數運算，簽名改了卻沒改內文就會炸
		els = [{"id": "p1_title", "type": "title", "text": "測試"},
			{"id": "p1_b0", "type": "bullet", "text": "條列"},
			{"id": "p1_fig", "type": "figure", "kind": "compare",
				"left": {"title": "前", "items": ["甲", "乙"]},
				"right": {"title": "後", "items": ["丙"]}}]
		lesson = {"lesson_id": "t", "title": "t",
			"slides": [{"id": "p1", "elements": els}]}
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
		path = os.path.join(d, "t.lesson.json")
		with open(path, "w", encoding="utf-8") as f:
			json.dump(lesson, f)
		old = sys.argv
		sys.argv = ["render_slides.py", path, d]
		try:
			self.assertEqual(R.main(), 0)
		finally:
			sys.argv = old
		with open(os.path.join(d, "layout.json"), encoding="utf-8") as f:
			boxes = json.load(f)["slides"][0]["boxes"]
		for k in ("p1_fig:l1", "p1_fig:l2", "p1_fig:r1"):
			self.assertIn(k, boxes)
```

- [ ] **Step 2：跑測試確認它紅**

Run: `.venv/bin/python -m unittest tests.test_render_slides -v`
Expected: `test_窄欄時真的改成直排` FAIL（目前是橫排）。其餘可能已綠——已綠的**不要刪掉**，它們是防止 3B 改壞的網。

- [ ] **Step 3：改簽名，三個分支一起**

`draw_figure(targets, measure, el, th, top, guard)` → `draw_figure(targets, measure, el, th, region, guard)`。

三個分支一律以 `top = region["y"]`、可用寬度 `region["w"]`、水平中心 `cx = region["x"] + region["w"] // 2` 取代原本的 `top` 參數與 `CENTER_X`。**不要用 `isinstance` 判斷型別當相容墊片**——那是把兩種契約同時留在程式裡，正是這輪要消除的東西。

- [ ] **Step 4：`boxes`／`steps` 依區域寬度決定橫排或直排**

```python
	n = max(1, len(items))
	gap = FIG_GAP + (34 if kind == "steps" else 0)
	need = 360 * n + gap * (n - 1)        # 橫排要的最小寬度
	vertical = need > region["w"]
```

- 橫排：維持現行邏輯，只是 `CENTER_X` 換成 `cx`、`FIG_MAX_W` 換成 `region["w"]`。
- 直排：每格寬 `min(360, region["w"])`、水平置中於 `cx`、垂直依序堆疊、整塊在區域內垂直置中。`steps` 的箭頭由指向右改為指向下（三角形頂點改成 `(cx, y + gap // 2)` 那一側）。
- **兩種排法都要寫 `boxes[f"{eid}:i{i}"]`，一個都不能少。**

- [ ] **Step 5：`compare` 分支改吃區域並在區域內垂直置中**

面板寬度由寫死的 700 改成 `(region["w"] - mid) // 2`，整塊起始 y 改成 `region["y"] + max(0, (region["h"] - h) // 2)`。`h` 是既有的 `64 + rows * 74`，得先算出來才能置中——把 `rows` 的計算提到繪製迴圈之前。

- [ ] **Step 6：跑全套測試 + 五份教材各產一次圖**

Run: `.venv/bin/python -m unittest discover -s tests -t . -v`
接著五份教材各跑一次 `render_slides.py`。
Expected: 全綠，五份都成功且無例外。

- [ ] **Step 7：Commit**

```bash
git add video_engine/render_slides.py tests/test_render_slides.py
git commit -m "feat: figure 改吃區域，窄欄改直向排列"
```

---

### Task 4: `stage` 與 `code` 版型

**Files:**
- Modify: `video_engine/layout.py`
- Modify: `video_engine/render_slides.py`
- Modify: `tests/test_layout.py`

**Interfaces:**
- Consumes：Task 3A 的 `pick_variant`、Task 3B 的 `draw_figure(…, region, …)`
- Produces：`layout.code_top(n)`、`regions_for` 支援 `"stage"` 與 `"code"`

**`stage`**（`figure.kind == "compare"`）：條列收到內容卡頂部一條帶狀區域（高度取 `min(bullets_h, 內容卡高 * 0.4)`），compare 拿下方剩餘的整片寬度，左右各留 `COL_PAD`。

**`code`**：`CODE_BOX` 外框不變（是錨點），但程式碼整塊依 `code_metrics` 算出的總高度**垂直置中**於 `CODE_BOX`，消掉 10 行時下方 210px 的死白。

- [ ] **Step 1：先寫失敗的測試**

```python
class TestRegionsStage(unittest.TestCase):
	def _r(self):
		return L.regions_for(slide("figure", kind="compare", n_bullets=3), 0)

	def test_版型真的是_stage(self):
		self.assertEqual(self._r()["variant"], "stage")

	def test_文字在上_圖在下_不重疊(self):
		r = self._r()
		self.assertLessEqual(r["text"]["y"] + r["text"]["h"], r["figure"]["y"])

	def test_圖區比_split_的欄位寬(self):
		# compare 走 stage 的唯一理由就是它需要寬度
		stage = self._r()["figure"]["w"]
		split = L.regions_for(slide("figure", kind="boxes", n_bullets=3), 0)["figure"]["w"]
		self.assertGreater(stage, split)

	def test_文字帶不超過內容卡四成高(self):
		card_h = L.CONTENT_BOX[3] - L.CONTENT_BOX[1]
		self.assertLessEqual(self._r()["text"]["h"], card_h * 0.4)

	def test_圖區關在內容卡裡(self):
		f = self._r()["figure"]
		self.assertGreaterEqual(f["x"], L.CONTENT_BOX[0])
		self.assertLessEqual(f["x"] + f["w"], L.CONTENT_BOX[2])
		self.assertLessEqual(f["y"] + f["h"], L.CONTENT_BOX[3])


class TestRegionsCode(unittest.TestCase):
	def test_版型與區域都要對(self):
		# 光測 code_metrics／code_top 是不夠的：regions_for 對 code 頁
		# 回傳錯結構或根本沒實作，那兩個函式照樣是綠的
		r = L.regions_for(slide("code"), 0)
		self.assertEqual(r["variant"], "code")
		self.assertEqual(r["code"], L.rect(*L.CODE_BOX))
		self.assertIsNone(r["figure"])

	def test_程式碼整塊垂直置中(self):
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
Expected: FAIL，`AttributeError: module 'layout' has no attribute 'code_top'`

- [ ] **Step 3：實作 `code_top` 與 `stage`**

```python
STAGE_TEXT_RATIO = 0.4


def code_top(n):
	"""程式碼整塊在 CODE_BOX 內垂直置中的起始 y。

	舊版固定從 CODE_Y0 開始，10 行的話下方留 210px 死白
	"""
	step, _ = code_metrics(n)
	return CODE_BOX[1] + max(0, (CODE_BOX[3] - CODE_BOX[1] - n * step) // 2)
```

`stage` 的切法：文字帶高度 `min(bullets_h, int((y1 - y0) * STAGE_TEXT_RATIO))`，圖區為其下方剩餘部分、左右各留 `COL_PAD`。文字帶維持 `text_align: "center"`（它橫跨整幅，靠左會很怪）。

- [ ] **Step 4：跑測試確認它綠**

Run: `.venv/bin/python -m unittest tests.test_layout -v`
Expected: 全 passed

- [ ] **Step 5：`render_slides.py` 接上**

- 匯入清單加 `code_top`。
- 程式碼繪製的起始 y 由 `CODE_Y0` 改成 `code_top(len(el["lines"]))`。**是 `el["lines"]`，`render_slide` 裡沒有叫 `lines` 的區域變數。**

- [ ] **Step 6：跑全套測試 + 五份教材各產一次圖**

Run: `.venv/bin/python -m unittest discover -s tests -t . -v`
Expected: 全綠，五份都成功。

- [ ] **Step 7：Commit**

```bash
git add video_engine/layout.py video_engine/render_slides.py tests/test_layout.py
git commit -m "feat: stage 版型與程式碼垂直置中"
```

---

### Task 5: 全語料不變量

**Files:**
- Modify: `tests/test_render_slides.py`

**Interfaces:**
- Consumes：Task 3A、3B、4 的全部版型
- Produces：不新增產品程式碼。這個 Task 只裝網。

降級邏輯已在 Task 3A Step 4 就位（`split` 一啟用就需要它，不能留一個 Task 的防禦空窗）。本 Task 專責把不變量對**真實語料**壓下去。

- [ ] **Step 1：寫全語料不變量測試**

```python
class TestCorpusInvariants(unittest.TestCase):
	"""五份現成教材是唯一的真實樣本，每個不變量都要對它們成立"""

	LESSONS = ("c_loop", "c_string", "c_struct", "c_struct_combo", "c_struct_v3")

	def _lesson(self, name):
		with open(os.path.join(ROOT, "video_engine/examples", f"{name}.lesson.json"),
				encoding="utf-8") as f:
			return json.load(f)

	def _render(self, name):
		d = tempfile.mkdtemp()
		self.addCleanup(shutil.rmtree, d, True)
		old = sys.argv
		sys.argv = ["render_slides.py",
			os.path.join(ROOT, "video_engine/examples", f"{name}.lesson.json"), d]
		try:
			self.assertEqual(R.main(), 0)
		finally:
			sys.argv = old
		with open(os.path.join(d, "layout.json"), encoding="utf-8") as f:
			return json.load(f), d

	def test_每個可定址代號都有量測框(self):
		# 只查元素 id 是不夠的：figure 的子代號（:i、:l、:r、:caption）
		# 才是動作真正指到的東西，漏掉的話這則測試會在版型改壞時仍然全綠
		for name in self.LESSONS:
			lay, _ = self._render(name)
			lesson = self._lesson(name)
			for page, sl in zip(lay["slides"], lesson["slides"]):
				bx = page["boxes"]
				for el in sl["elements"]:
					eid = el["id"]
					self.assertIn(eid, bx, f"{name} {eid}")
					if el["type"] == "code":
						for i in range(1, len(el["lines"]) + 1):
							self.assertIn(f"{eid}:L{i}", bx, f"{name} {eid}:L{i}")
					elif el["type"] == "figure":
						if el["kind"] in ("boxes", "steps"):
							for i in range(1, len(el.get("items", [])) + 1):
								self.assertIn(f"{eid}:i{i}", bx, f"{name} {eid}:i{i}")
						else:
							for j in range(1, len(el.get("left", {}).get("items", [])) + 1):
								self.assertIn(f"{eid}:l{j}", bx, f"{name} {eid}:l{j}")
							for j in range(1, len(el.get("right", {}).get("items", [])) + 1):
								self.assertIn(f"{eid}:r{j}", bx, f"{name} {eid}:r{j}")
						if el.get("caption"):
							self.assertIn(f"{eid}:caption", bx, f"{name} {eid}:caption")

	def test_所有框都在畫布內(self):
		import layout as L
		for name in self.LESSONS:
			lay, _ = self._render(name)
			for page in lay["slides"]:
				for key, b in page["boxes"].items():
					self.assertGreaterEqual(b["x"], 0, f"{name} {key}")
					self.assertGreaterEqual(b["y"], 0, f"{name} {key}")
					self.assertLessEqual(b["x"] + b["w"], L.W, f"{name} {key}")
					self.assertLessEqual(b["y"] + b["h"], L.H, f"{name} {key}")

	def test_五份教材各自連跑兩次都逐位元組相同(self):
		import hashlib

		def digest(name):
			_, d = self._render(name)
			h = hashlib.md5()
			for f in sorted(os.listdir(d)):
				if f.endswith(".png"):
					with open(os.path.join(d, f), "rb") as fh:
						h.update(fh.read())
			return h.hexdigest()

		for name in self.LESSONS:
			self.assertEqual(digest(name), digest(name), f"{name} 引入了非決定性")

	def test_每份教材至少用到兩種版型(self):
		# 這輪的目的就是消除單調。四種版型全部實作了但沒有一頁走到，
		# 測試照樣全綠——這裡把「目的達成了沒有」也變成可驗的
		import layout as L
		for name in self.LESSONS:
			used = {L.pick_variant(sl) for sl in self._lesson(name)["slides"]}
			self.assertGreaterEqual(len(used), 2, f"{name} 只用到 {used}")
```

- [ ] **Step 2：跑測試**

Run: `.venv/bin/python -m unittest tests.test_render_slides -v`
Expected: 全綠。**若有任何一則已經綠，不要因此刪掉它**——它證明前面的 Task 守住了，這正是它存在的理由。若有紅的，回報是哪一份教材的哪個代號，不要調整斷言去配合輸出。

- [ ] **Step 3：確認鏡頭與浮現的連帶效應**

`split` 把元素中心從畫布中線移到左右欄（`cx` 約 505／1415），鏡頭推近會因此產生水平平移；`compile_timeline.reveal_ms()` 依框面積分級進場時長，框變了時長可能跟著變。兩者都不會崩潰（`render_video.zoom()` 支援任意座標），屬預期效果。

實測記錄：`boxes`／`steps` 的單項今天就是 `360x104`（share 0.0181 → SMALL 260ms），直排後寬度仍是 `min(360, 欄寬)`，**面積不變、時長不變**。`compare` 的單項是 `700x62`（share 0.0209 → CARD 320ms），`stage` 加寬後 share 上升、仍在 CARD 級。

跑一次 `compile_timeline.py` 對 `c_loop` 產時間軸，確認沒有 ERROR 級診斷。
Expected: 零筆 ERROR。

- [ ] **Step 4：產出前後對照**

對五份教材各產一次圖，與 Task 1 之前的基準版並排存到 `/tmp/layout-compare/`，每頁一組（前／後）。這是給人看的，不進版控。
**不要自行判定視覺好壞**——產出後回報路徑即可。

- [ ] **Step 5：Commit**

```bash
git add tests/test_render_slides.py
git commit -m "test: 版型改造的全語料不變量"
```
