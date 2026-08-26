# 投影片版型多樣化實作計畫 — 對抗性審查報告 (Adversarial Review)

**審查對象：**
- 計畫文件：`docs/superpowers/plans/2026-08-26-slide-layout-variation.md`
- 設計文件：`docs/superpowers/specs/2026-08-26-slide-layout-variation-design.md`
- 現行核心程式碼：`video_engine/render_slides.py`、`video_engine/compile_timeline.py`、`video_engine/schema/lesson.schema.json`
- 語料庫：`video_engine/examples/*.lesson.json`（5 份教材，共 22 頁投影片）

---

## 執行摘要與最終判定

**審查判定：【需依具體修正調整後執行 (Safe after specific amendments)】**

整體架構設計方向（純函式模組 `video_engine/layout.py` 與 PIL 繪製徹底解耦、4 種內容驅動確定性版型、`HEADER_BOX` 與 `CONTENT_BOX` 外框絕對固定以保護 420ms 交叉淡化）具備高度合理性且符合專案原則。

然而，本計畫若**照字面直接執行將會在 Task 3 與 Task 5 遭遇嚴重的執行期崩潰與測試失敗**。核心缺陷包括：
1. **Task 3 修改 `draw_figure` 簽名卻未處理 `compare` 分支**，導致 `c_string` / `c_struct` 回歸測試直接拋出 `TypeError`/`NameError` 崩潰。
2. **`stack` 版型區域寬度（1760px）與 `BULLET_MAX_W`（1650px）存在 110px 數學矛盾**，計畫聲稱兩者等價但實際未保留 55px 邊距。
3. **Task 5 降級測試斷言 15 條條列不超出內容卡**，但 `stack` 本身缺乏垂直壓縮機制，15 條高達 1728px，導致測試必然噴紅。
4. **語料不變量測試遺漏所有示意圖部件（`:i{n}`, `:l{n}`, `:r{n}`, `:caption`）的檢驗**，使核心不變量門檻形成虛假綠燈（Vacuous Test）。
5. **完全忽略 schema 支援的 `image` 元素與單頁多圖（Multiple Figures）情境**，會產生致命圖文重疊。

以上問題均可透過本報告提出之精確修訂（Surgical Amendments）修正，無需推翻重寫。

---

## 軸線 1：範例程式碼執行可行性分析 (Will the sample code actually run?)

按 Task 逐行追蹤命名、簽名、匯入與變數生命週期，發現以下明確破壞點：

### 1.1 [HIGH] Task 3 Step 6：`draw_figure` 簽名改為 `region` 卻跳過 `compare`，導致執行期崩潰
- **位置：** Task 3 Step 6（第 451–459 行）
- **破壞機制：**
  Task 3 Step 6 將 `draw_figure(targets, measure, el, th, top, guard)` 改為 `draw_figure(targets, measure, el, th, region, guard)`，並明述「`compare` 這一步不動（它走 `stage`，Task 4 才處理）」。
  但在 `render_slides.py` 現行的 `compare` 繪製邏輯中，大量直接使用 `top` 進行整數運算：
  ```python
  d.rounded_rectangle([px, top, px + panel_w, top + 52], ...)
  y = top + 64
  cy = top + h // 2
  boxes[eid] = {"x": x0, "y": top, "w": panel_w * 2 + mid, "h": h}
  ```
  當傳入的第 5 個參數由整數 `top` 變成字典 `region`（例如 `{"x": 80, "y": 280, "w": 1760, "h": 700}`）時，`top + 52` 會立即引發 `TypeError: unsupported operand type(s) for +: 'dict' and 'int'`（或若參數改名為 `region` 則引發 `NameError: name 'top' is not defined`）。
  而在 Task 3 Step 7 執行的 `unittest discover` 會跑 `TestRegression`，對 `c_string` 與 `c_struct` 進行渲染——這兩份教材的第 1 頁皆為 `compare`，導致 Task 3 在 Step 7 必死無疑。
- **具體修正：**
  在 Task 3 Step 6 的 `draw_figure` 開頭統一解構座標：
  ```python
  top = region["y"] if isinstance(region, dict) else region
  ```
  確保過渡期間 `compare` 分支仍能取得整數 `top` 正常運作。

### 1.2 [MEDIUM] Task 3 Step 5：`render_slide` 中未定義的變數 `region`
- **位置：** Task 3 Step 5（第 449 行）
- **破壞機制：**
  指示寫道：「條列的 `fit_font` 寬度上限改用 `region["w"]` 而非寫死的 `BULLET_MAX_W`」。
  但在 Task 2 Step 5 中，`render_slide` 內的變數命名為 `reg = regions_for(slide, idx - 1)`，其中文字區域為 `reg["text"]`。若實作者直接在 `fit_font` 中填入 `region["w"]`，將引發 `NameError: name 'region' is not defined`。
- **具體修正：**
  明確指示使用 `reg["text"]["w"]` 作為 `fit_font` 上限，呼叫 `draw_text_block(..., reg["text"], reg["text_align"])`。

### 1.3 [LOW] Task 4 Step 3：`code_top` 呼叫變數名稱錯誤與缺漏匯入
- **位置：** Task 4 Step 3（第 556 行）
- **破壞機制：**
  指示寫道：「`render_slides.py` 的程式碼繪製把起始 y 由 `CODE_Y0` 改成 `code_top(len(lines))`」。
  在 `render_slides.py` 第 248–254 行中，變數名稱為 `el["lines"]`（不存在名為 `lines` 的局部變數），直接複製會引發 `NameError: name 'lines' is not defined`。此外，`code_top` 必須加入 `from layout import ...` 的清單中。
- **具體修正：**
  修正為 `code_top(len(el["lines"]))`，並明確在 `render_slides.py` 的匯入清單加入 `code_top`。

### 1.4 [LOW] Task 3 Step 5：`draw_text_block` 在 `title`/`subtitle` 的 `region` 介面契約未明
- **位置：** Task 3 Step 5（第 435–447 行）
- **破壞機制：**
  `draw_text_block` 簽名要求 `(targets, measure, text, y, font, color, region, align)`。
  標題與副標題走 `align="center"`，但它們位於 `HEADER_BOX`（tuple `(80, 60, 1840, 200)`）。若傳入 `region=None`，函式在 `align="center"` 時雖不讀取 `region`，但若無預設引數則容易引發呼叫端傳參混亂。
- **具體修正：**
  在 `draw_text_block` 中將 `region=None, align="center"` 設為具備預設值之可選引數，或明確傳入 `rect(*HEADER_BOX)`。

---

## 軸線 2：逐像素不變性驗證門檻分析 (Is the pixel-identical gate actually achievable?)

### 2.1 [HIGH] `stack` 區域寬度與 `BULLET_MAX_W` 的 110px 數學矛盾
- **位置：** Task 2 Step 3（第 276 行）與 Task 3 Step 5（第 449 行）
- **數學驗證：**
  - `CONTENT_BOX = (80, 240, 1840, 980)`，其卡片總寬為 `1840 - 80 = 1760px`。
  - 現行常數 `BULLET_MAX_W = 1650px`，這意味著文字相對於卡片左右邊界各有 `(1760 - 1650) / 2 = 55px` 的安全內距（Padding）。
  - Task 2 Step 3 實作的 `stack` 文字區域為：
    ```python
    "text": rect(CONTENT_BOX[0], top, CONTENT_BOX[2], top + bullets_h)
    ```
    其 `w = CONTENT_BOX[2] - CONTENT_BOX[0] = 1840 - 80 = 1760px`。
  - Task 3 Step 5 聲稱：`stack 版型的區域寬度本來就是 BULLET_MAX_W 等價值——若不等價會導致 Task 2 的雜湊變動`。
  - **計算結果：**
    `1760px != 1650px`，差距達 **110px**！
  - **影響分析：**
    在現有 5 份教材中，實測最長條列為 `c_struct_v3` p1 的 996.5px，未觸及 1650px 縮字門檻，因此在現有語料上不會立即顯現雜湊變更；但若未來教材條列長度落在 1650px–1760px 之間，原本在 1650px 會觸發 `fit_font` 縮字級（floor 縮小），改用 1760px 則不會縮小，文字將緊貼卡片邊緣（0px 邊距），嚴重破壞視覺留白原則。
- **具體修正：**
  在 `layout.py` 中明確定義 `CARD_PAD_X = (CONTENT_BOX[2] - CONTENT_BOX[0] - BULLET_MAX_W) // 2 = 55`，`stack` 的文字區域計算應為：
  ```python
  rect(CONTENT_BOX[0] + CARD_PAD_X, top, CONTENT_BOX[2] - CARD_PAD_X, top + bullets_h)
  ```
  使其寬度精確等於 `BULLET_MAX_W`（1650px）。

### 2.2 [MEDIUM] `split` 欄間距公式錯誤（60px 膨脹為 140px）
- **位置：** Task 3 Step 3（第 411–415 行）
- **數學驗證：**
  計畫設定 `COL_GAP = 60`、`COL_PAD = 40`，內容卡寬 `1760px`。
  範例程式碼寫法為：
  ```python
  half = (x1 - x0 - COL_GAP) // 2   # (1760 - 60) // 2 = 850
  left = rect(x0 + COL_PAD, y0 + COL_PAD, x0 + half - COL_PAD, y1 - COL_PAD)
  right = rect(x0 + half + COL_GAP + COL_PAD, y0 + COL_PAD, x1 - COL_PAD, y1 - COL_PAD)
  ```
  計算各欄座標與間距：
  - `left` 範圍：`x0 + 40 = 120` 至 `x0 + 850 - 40 = 890`（寬度 770px）。
  - `right` 範圍：`x0 + 850 + 60 + 40 = 1030` 至 `1840 - 40 = 1800`（寬度 770px）。
  - **中間溝寬（Gap）：** `1030 - 890 = 140px`！
  - 原因是程式碼在 `half` 扣除 `COL_GAP` 後，又在左右兩欄的內側各自重複扣減了 `COL_PAD`（40px + 40px），導致原本設定的 60px 中溝膨脹為 140px，每欄寬度無端損失 40px（由 810px 縮水至 770px）。
- **具體修正：**
  修正欄位計算幾何算式：
  ```python
  col_w = (x1 - x0 - 2 * COL_PAD - COL_GAP) // 2  # (1760 - 80 - 60) // 2 = 810px
  left = rect(x0 + COL_PAD, y0 + COL_PAD, x0 + COL_PAD + col_w, y1 - COL_PAD)
  right = rect(x0 + COL_PAD + col_w + COL_GAP, y0 + COL_PAD, x1 - COL_PAD, y1 - COL_PAD)
  ```
  使外側內距為 40px，中溝為精確的 60px，可用欄寬最大化至 810px。

---

## 軸線 3：測試有效性與無效/偽綠測試檢驗 (Are the tests real?)

### 3.1 [HIGH] Task 5 Step 1：`TestDowngrade` 測試斷言在 `n >= 7` 時必然失敗
- **位置：** Task 5 Step 1（第 599–608 行）
- **破壞機制：**
  測試迴圈斷言：
  ```python
  def test_降級後仍不溢出內容卡(self):
      for n in range(1, 16):
          r = L.regions_for(slide("figure", kind="boxes", n_bullets=n), 0)
          for key in ("text", "figure"):
              b = r[key]
              if not b: continue
              self.assertGreaterEqual(b["y"], L.CONTENT_BOX[1], f"{n} 條 {key}")
              self.assertLessEqual(b["y"] + b["h"], L.CONTENT_BOX[3], f"{n} 條 {key}")
  ```
  當 `n = 12` 或 `15` 時，`split` 正確觸發降級回 `stack`。
  但在 `stack` 中，條列高度計算為 `bullets_h = (n - 1) * BULLET_STEP + 48`。
  以 `n = 15` 為例，`bullets_h = 14 * 120 + 48 = 1728px`，加上示意圖高 `144px`，`block_h = 1872px`。
  內容卡可用高度僅 `980 - 240 = 740px`。
  置中計算 `top = 240 + (740 - 1872) // 2 = -326px`。
  結果 `b["y"] = -326 < 240`，且 `b["y"] + b["h"] = 1402 > 980`。
  事實上當 `n >= 7` 時，`stack` 本身就已經溢出 `CONTENT_BOX`（`6 * 120 + 48 = 768 > 740`）。
  因為 `stack` 版型未實作類似程式碼的 `bullet_metrics` 動態行距壓縮，降級後的 `stack` **無法在 `n in range(7, 16)` 滿足此測試斷言**，導致測試永遠報紅！
- **具體修正：**
  雙軌修正：
  1. 測試端：將單純降級測試範圍限縮於物理上容得下的合理條數 `for n in range(1, 6):`。
  2. 若需支援 15 條不溢出，必須在 `layout.py` 中引入 `bullet_step_for(n)` 動態縮小行距（從 120 壓至 80）。

### 3.2 [HIGH] Task 5 Step 1：`TestCorpusInvariants` 遺漏所有示意圖可定址代號檢驗
- **位置：** Task 5 Step 1 `test_每個元素都有量測框`（第 637–649 行）
- **破壞機制：**
  測試代碼僅迭代：
  ```python
  for el in sl["elements"]:
      self.assertIn(el["id"], page["boxes"], f"{name} {el['id']} 沒有量測框")
      if el["type"] == "code":
          for i in range(1, len(el["lines"]) + 1):
              self.assertIn(f"{el['id']}:L{i}", page["boxes"], f"{name} 第 {i} 行")
  ```
  它**完全沒有檢查**示意圖的子代號：
  - `figure/boxes` 與 `steps` 的 `{eid}:i{n}`
  - `figure/compare` 的 `{eid}:l{n}` 與 `{eid}:r{n}`
  - `{eid}:caption`
  這意味著：若 Task 3 在將 `boxes`/`steps` 轉為直排時，漏記了 `p2_fig:i2`，或者 Task 4 在重構 `compare` 時漏記了 `p1_fig:l1`，此語料不變量測試**依然會保持綠燈**！這嚴重違反了 Spec 第 5 節第 2 條的不變量承諾。
- **具體修正：**
  在 `test_每個元素都有量測框` 中補齊所有 figure 子代號檢查：
  ```python
  elif el["type"] == "figure":
      kind = el.get("kind")
      if kind in ("boxes", "steps"):
          for i in range(1, len(el.get("items", [])) + 1):
              self.assertIn(f"{el['id']}:i{i}", page["boxes"])
      elif kind == "compare":
          for j in range(1, len(el.get("left", {}).get("items", [])) + 1):
              self.assertIn(f"{el['id']}:l{j}", page["boxes"])
          for j in range(1, len(el.get("right", {}).get("items", [])) + 1):
              self.assertIn(f"{el['id']}:r{j}", page["boxes"])
      if el.get("caption"):
          self.assertIn(f"{el['id']}:caption", page["boxes"])
  ```

### 3.3 [MEDIUM] Task 4 Step 1：`TestRegionsCode` 存在無效呼叫（Vacuous Assertion）
- **位置：** Task 4 Step 1（第 522 行）
- **破壞機制：**
  測試中呼叫了 `r = L.regions_for(slide("code"), 0)`，但在後續的斷言中**完全沒有使用 `r`**，只斷言了獨立函式 `L.code_metrics(10)` 與 `L.code_top(10)`。
  若 `regions_for` 對於 `code` 版型回傳錯誤結構（或根本未實作），該測試仍然全綠。
- **具體修正：**
  在 `TestRegionsCode` 中加入對 `r["code"]` 與 `r["variant"] == "code"` 的明確斷言。

### 3.4 [LOW] Task 5 Step 1：決定性測試僅測試單一教材 `c_loop`
- **位置：** Task 5 Step 1（第 670 行）
- **破壞機制：**
  `test_同一份教材連跑兩次逐位元組相同` 只比對了 `c_loop`，遺漏了唯一純文字教材 `c_struct_v3` 以及其他 3 份教材。
- **具體修正：**
  改為走訪 `self.LESSONS` 清單中的所有 5 份教材。

---

## 軸線 4：計畫未提及的隱性破壞與邊界缺陷 (What breaks that the plan does not mention?)

### 4.1 [HIGH] `image` 元素型態被 `layout.py` 徹底忽略，導致圖文重疊
- **機制：**
  `lesson.schema.json`（第 165 行）明訂支援 `imageElement`（`type: "image"`），且 `render_slides.py` 第 274–283 行以寫死座標 `pos = ((W - im.width) // 2, 320)` 繪製。
  但在 `layout.py` 的 `pick_variant` 與 `regions_for` 中，**完全未提及也不計算 `image`**。
  若教材包含條列與 `image`，`regions_for` 會將版型判定為 `stack`，並將條列計算在 `top = 526` 置中。繪製器隨後在 `y = 320..880` 貼上圖片，**條列文字將直接硬生生覆蓋在圖片上方**。
- **具體修正：**
  在 `layout.py` 中納入 `image` 高度計算（預設高度 560px + gap 40px），並在 `pick_variant` 遇 `image` 時回傳 `stack` 且正確將文字與圖片總高度合併計算 `top`。

### 4.2 [HIGH] 單頁包含多個示意圖（Multiple Figures）在 `split` 中產生 100% 重疊碰撞
- **機制：**
  `pick_variant` 僅取第一個 figure：`fig = next((e for e in els if e["type"] == "figure"), None)`。
  當一頁有 2 個 figure 時，版型被判定為 `split`，`regions_for` 僅回傳單一 `"figure"` 區域。
  在 `render_slide` 走訪元素時，兩個 figure 都拿到相同的 `region`，且都從 `region["y"]` 開始畫，導致第二張圖直接壓在第一張圖上面。
- **具體修正：**
  在 `pick_variant` 加入防禦：若 `sum(1 for e in els if e["type"] == "figure") > 1`，一律回退（降級）至 `stack`，由 `stack` 的垂直累加邏輯（`fig_y += fig_height(el) + 40`）處理。

### 4.3 [MEDIUM] `stage` 版型中 `compare` 示意圖缺乏垂直置中
- **機制：**
  `stage` 版型將文字帶壓在上方 40%（`min(bullets_h, 0.4 * card_h)`），圖區占據下方剩餘空間。
  當條列僅 1 條且 `compare` 僅 2 列（高度約 212px）時，下方圖區高度約 600px。若 `draw_figure` 直接從 `region["y"]` 開始繪製，示意圖會緊貼上方條列，下方留下近 400px 的巨大空白。
- **具體修正：**
  在 `draw_figure` 的 `compare` 分支中，加入區域內垂直置中偏移：
  ```python
  top = region["y"] + max(0, (region["h"] - h) // 2)
  ```

### 4.4 [MEDIUM] 動畫層 `reveal_ms()` 與鏡頭推近（Camera Zoom）行為變更
- **機制：**
  - `compile_timeline.py:133-140` 之 `reveal_ms()` 根據 box 面積佔畫布比例決定浮現時間（`< 0.02` 為 240ms，`< 0.10` 為 360ms）。在 `split` 直排後，單項 `p2_fig:i1` 面積由原本橫排的約 `40,000 px^2` 降至 `37,440 px^2`（比例 0.018 < 0.02），浮現速度將由 360ms 自動加速為 240ms（提速 33%）。
  - 在原本 `stack` 版型中，所有元素中心點 `cx` 恆為 960（畫布正中），鏡頭推近（Camera Zoom）只有垂直推近；在 `split` 版型中，左欄 `cx ≈ 505`、右欄 `cx ≈ 1415`，鏡頭將產生水平平移（Horizontal Pan）。
- **影響評估：**
  經查證 `render_video.py:zoom()` 與 `compile_timeline.py`，動畫層數學函式支援任意座標推近與非阻塞浮現，不會引發崩潰，但視覺節奏與鏡頭軌跡會顯著改變。此屬預期效果，但計畫應正式記錄此項連帶效應。

---

## 軸線 5：任務拆解與相依性評估 (Is the task decomposition right?)

### 5.1 [HIGH] Task 3 承載過重且產生中間狀態破壞
- **現況問題：**
  Task 3 同時包攬了：
  1. `layout.py` 的 `pick_variant` 與 `split` 幾何。
  2. `render_slides.py` 文字繪製重構（`draw_centered` 改名為 `draw_text_block`、靠左對齊、寬度限制）。
  3. `render_slides.py` 示意圖繪製重大重構（`draw_figure` 簽名變更、`boxes`/`steps` 直排與箭頭方向重繪）。
  4. 既有 `compare` 在 Task 3 被宣告為「不動」，卻因簽名變更直接損壞。
- **重構建議：拆分為 Task 3A 與 Task 3B**
  - **Task 3A（文字與版型分流）：** 實作 `layout.pick_variant`、`split` 文字幾何，以及 `render_slides.py` 的 `draw_text_block`（支援靠左對齊）。保持 `draw_figure` 舊簽名或相容層。
  - **Task 3B（示意圖區域化與直排）：** 改造 `draw_figure` 接受 `region`，實作 `boxes`/`steps` 窄欄直排，並確保 `compare` 具備安全相容墊片。

### 5.2 [MEDIUM] 降級邏輯延遲至 Task 5 造成防禦空窗
- **現況問題：**
  Task 3 啟用了 `split`，但容量不足的降級保護卻被排在 Task 5。若在 Task 3/4 遇到多條列案例會直接爆版。
- **重構建議：**
  將 `split` 基礎容量檢查併入 Task 3，Task 5 專注於全語料回歸驗證與邊界測試。

---

## 具體修訂建議彙整表 (Surgical Amendments Matrix)

| 編號 | 所在位置 | 嚴重度 | 缺陷描述 | 具體修訂方式 (Surgical Fix) |
|---|---|---|---|---|
| **F-01** | Task 3 Step 6 | **HIGH** | `draw_figure` 改吃 `region` 但未相容 `compare`，引發 `TypeError` | 在 `draw_figure` 開頭加入 `top = region["y"] if isinstance(region, dict) else region`。 |
| **F-02** | Task 2 Step 3 / Task 3 Step 5 | **HIGH** | `stack` 文字寬 1760px 與 `BULLET_MAX_W=1650` 矛盾（差 110px） | `layout.py` 中 `stack` 文字區左右各加 55px padding，使寬度精確等於 1650px。 |
| **F-03** | Task 5 Step 1 | **HIGH** | `TestDowngrade` 斷言 15 條在 `stack` 不溢出必掛（高達 1728px） | 將測試迴圈上限調整至合理條數 `range(1, 6)`，或在 `layout.py` 加入動態條列行距壓縮。 |
| **F-04** | Task 5 Step 1 | **HIGH** | `TestCorpusInvariants` 漏測 figure 子代號（`:i*`, `:l*`, `:r*`, `:caption`） | 補齊所有 figure 項目與 caption 的 `assertIn(key, page["boxes"])` 斷言。 |
| **F-05** | Task 3 Step 3 | **MEDIUM** | `split` 欄位計算將中溝由 60px 誤放大至 140px | 修正 `col_w = (x1 - x0 - 2*COL_PAD - COL_GAP) // 2`，消除重複扣減 padding。 |
| **F-06** | Task 3 Step 5 | **MEDIUM** | `render_slide` 引用未定義變數 `region` | 改為明確使用 `reg["text"]["w"]` 與 `reg["text_align"]`。 |
| **F-07** | `layout.py` | **HIGH** | 漏處理 `image` 元素與多圖情境（Multiple Figures） | `pick_variant` 遇 `image` 或多圖時回退 `stack`，並正確累加總高度。 |
| **F-08** | Task 4 Step 3 | **MEDIUM** | `stage` 中 `compare` 靠頂未垂直置中，底部留白過大 | 在 `draw_figure` 的 `compare` 分支加入 `top = region["y"] + max(0, (region["h"] - h) // 2)`。 |
| **F-09** | Task 4 Step 3 | **LOW** | `code_top` 呼叫寫成 `len(lines)` 且缺匯入 | 改為 `code_top(len(el["lines"]))` 並在匯入清單加入 `code_top`。 |
| **F-10** | 結構組織 | **HIGH** | Task 3 同時改文字與圖形過於龐大 | 拆分為 Task 3A（版型與文字）與 Task 3B（示意圖區域化與直排）。 |

---

## 結論

本計畫的核心理念精準、架構分層優良，但在幾何數值細節、執行期變數命名相容性以及測試斷言的真實有效性上存在若干盲點。只要在實作前將上述 **F-01 至 F-10** 具體修訂納入計畫，即可安全無虞地推進實作，確保 1080p 影片幾何版位平滑升級且達成零回歸破壞。
