# 示意圖尺寸縮放改善報告（Part A）

**日期**：2026-08-28  
**執行範圍**：Part A（示意圖填滿區域與幾何一致性重構，不含 Part B 聚光燈）

---

## 1. 變更內容說明

### 1.1 `video_engine/layout.py`
- 新增常數 `FIG_MAX_BOX_W = 520`。
- 新增幾何推導函式 `fig_box_width(el, width)` 作為單一真理來源（Single Source of Truth）：
  - 橫排時依可用寬度與間距分配，上限拉高至 520px（`min(520, (width - gap * (n - 1)) // n)`）。
  - 直排時吃滿欄寬並保留內距（`max(40, width - 40)`）。
- 嚴格維持零 `import` 與零副作用之純函式不變量。

### 1.2 `video_engine/render_slides.py`
- 繪製器 `draw_figure` 改為直接諮詢 `layout.fig_box_width` 計算各單項寬度，移除所有硬編碼之 360px 上限。
- 提升 `fit_font` 初始字級：
  - `boxes` / `steps` 單項文字：由 30 提升至 34（搭配放大後的格寬，由 `fit_font` 自動調適）。
  - `compare` 面板標題由 28 提升至 30，項目文字由 26 提升至 28。

### 1.3 `tests/test_render_slides.py`
- 新增 `TestFigureHeightReconciliationGrid` 測試類別，建構橫跨 `kind` (`boxes`, `steps`, `compare`) × 項目數 (2..5) × 區域寬度 (300, 500, 810, 1200, 1760) 的完整回歸測試網，釘住 `layout.fig_height(el, w)` 與 `draw_figure` 實測輸出 `boxes[eid]["h"]` 的一致性。

---

## 2. 驗證數據與量測結果

### 項目 1：全套單元測試
- **指令**：`.venv/bin/python -m unittest discover -s tests -t .`
- **結果**：151 個測試通過，1 個 skipped，0 failures，0 errors。
- **說明**：未修改任何既有測試，全數維持綠燈。

### 項目 2：示意圖單項尺寸成長量測
量測 3 項 `boxes` 示意圖在不同區域寬度下的單項尺寸：
- **雙欄模式（區域寬 810，直排）**：
  - 修改前：`360 × 104`
  - 修改後：`770 × 104`
- **置中模式（區域寬 1760，橫排）**：
  - 修改前：`360 × 104`
  - 修改後：`520 × 104`
- **結論**：修改後兩者尺寸互不相同，且寬度均顯著大於 360px（770px 與 520px），有效填滿分配區域。

### 項目 3：預測與實繪高度一致性對照矩陣
- **測試維度**：
  - `kind`：`boxes`, `steps`, `compare`（3 種）
  - 項目數：2, 3, 4, 5（4 種）
  - 區域寬：300, 500, 810, 1200, 1760（5 種）
- **總檢查組合數**：60 種
- **分歧數量**：0（`disagreed = 0`）

### 項目 4：全教材與全模式無溢出驗證
- **測試範圍**：5 份範例教材（`c_loop`, `c_string`, `c_struct`, `c_struct_combo`, `c_struct_v3`）× 4 種模式（`auto`, `split`, `center`, `random`）= 20 次渲染
- **檢查框總數**：956 個 bounding boxes
- **溢出失敗數**：0（所有量測框均完全關在所屬區域與 1920×1080 畫布內）

### 項目 5：可定址代號完整性
- **檢查代號**：`{id}`, `{id}:i{n}`, `{id}:l{n}`, `{id}:r{n}`, `{id}:caption`
- **遺漏代號數**：0

### 項目 6：決定性驗證
- **測試方法**：相同教材與模式重複渲染兩次並比對 PNG 檔案雜湊值
- **不一致檔案數**：0（逐位元組相同）

### 項目 7：`layout.py` 零 Import 檢查
- **指令**：`grep -c "^import \|^from " video_engine/layout.py`
- **結果**：0

---

## 3. 未驗證項目說明

依照專案守則與任務限制，未執行 `lesson`、`actions` 與 `synth` 階段，以避免產生外部 LLM API 與本機 GPU TTS 費用。其餘渲染與幾何管線皆已完成自動化驗證。
