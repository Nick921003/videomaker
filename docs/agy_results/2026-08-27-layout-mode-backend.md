# 版面模式選擇器後端管線實作報告

**日期**：2026-08-27  
**任務**：實作版面模式選擇器（Layout Mode Selector）後端與流水線整合，支援 `auto`、`split`、`center` 三種版面選擇模式。

---

## 1. 概述

本任務完成版面模式選擇器的後端管線端實作，讓呼叫端與前端服務能夠指定投影片版型推導模式（`auto`、`split`、`center`）。

實作嚴格遵循專案幾何規範與硬性不變量：
- `video_engine/layout.py` 維持純函式模組，零 `import`、零檔案 I/O、零副作用。
- 既有呼叫端相容性：`pick_variant(slide)` 與 `regions_for(slide, index)` 的二參數呼叫完全保留預設 `mode="auto"` 行為，既有 127 則測試無任何修改且全數通過。
- 模式只改變版型「選擇」，不修改任何版型的幾何常數與算式，且容量守門（Capacity Guard）降級機制完全生效（例如 `split` 容納不下時自動退回 `stack`）。
- 未識別的模式值明確拋出 `ValueError`，杜絕靜默降級。

---

## 2. 逐檔修改說明

### 2.1 `video_engine/layout.py`
- 定義合法模式常數 `LAYOUT_MODES = ("auto", "split", "center")`。
- 修改 `pick_variant(slide, mode="auto")`：
  - 驗證 `mode in LAYOUT_MODES`，若不合法則拋出 `ValueError(f"未知的版面模式：{mode!r}（支援：{', '.join(LAYOUT_MODES)}）")`。
  - 當包含程式碼時一律回傳 `"code"`。
  - 當 `mode == "center"` 時一律回傳 `"stack"`。
  - 當含 `image` 或多張圖時回傳 `"stack"`。
  - 當 `mode == "split"` 且為單張圖時，回傳 `"split"`（包含 `compare` 圖）。
  - 當 `mode == "auto"` 時維持既有邏輯（單張 `compare` 走 `"stage"`，其餘單圖走 `"split"`）。
- 修改 `regions_for(slide, index, mode="auto")`：
  - 傳遞 `mode=mode` 至 `pick_variant`。

### 2.2 `video_engine/render_slides.py`
- 修改 `render_slide(slide, guard, th, out_dir, idx, mode="auto")`：
  - 傳遞 `mode=mode` 至 `regions_for(slide, idx - 1, mode=mode)`。
- 修改 `main()` 與新增 `opt(name, default=None)`：
  - 支援從命令列參數解析 `--layout <mode>`（預設為 `"auto"`），並容許 `--layout` 接在輸出路徑之後。

### 2.3 `video_engine/run.py`
- 修改 `main()`：
  - 透過 `opt("--layout")` 解析命令列 `--layout` 參數。
  - 在 `want("slides")` 階段，將 `["--layout", layout]` 傳入 `render_slides.py` 執行參數。

### 2.4 `serve.py`
- 新增 `MultipartResult(tuple)` 類別：
  - 繼承自 `tuple` 並包裝 `(name, blob, sec)`，同時提供 `.name`、`.blob`、`.sec` 與 `.layout` 屬性。
  - 確保以 3-tuple 解包之舊測試程式碼（`name, got, sec = serve.parse_multipart(...)`）完全相容且不噴錯。
- 修改 `parse_multipart(body, ctype)`：
  - 解析表單欄位 `name="layout"`，回傳 `MultipartResult(name, blob, sec, layout)`。
- 修改 `real_runner(material, sec, layout=None)`：
  - 接收 `layout` 參數，若有給定則附加 `["--layout", str(layout)]` 至子行程參數。
- 修改 `Handler._create()`：
  - 從 `parse_multipart` 取出 `layout`，傳入 `real_runner(md, sec, layout)`。`Job` 類別與呼叫維持不變。

### 2.5 `tests/test_layout_mode.py`
- 新增獨立測試檔（共 14 項測試），完整覆蓋預設模式、無效模式拋錯、各模式版型與幾何推導、容量守門降級、多圖/程式碼頁處理、以及服務層 multipart / real_runner 參數傳遞。

---

## 3. 逐位元組回歸閘（Byte-Identical Regression Gate）

依照規格要求，在修改前與修改後分別對 5 份教材執行全量渲染並計算 44 張 PNG 的正規化 MD5 Hash：

```bash
D=$(mktemp -d); for f in c_loop c_string c_struct c_struct_combo c_struct_v3; do .venv/bin/python video_engine/render_slides.py video_engine/examples/$f.lesson.json $D/$f >/dev/null; done; find $D -name '*.png' | sort | xargs md5sum | sed "s|$D|X|" | md5sum
```

- **修改前 Hash**：`79c146a7f51e7ee350c809a1aee042d9  -`
- **修改後 Hash**：`79c146a7f51e7ee350c809a1aee042d9  -`
- **回歸比對結果**：**完全一致（PASS）**。

---

## 4. 全量渲染與三種模式版型分佈

針對 5 份範例教材（`c_loop`、`c_string`、`c_struct`、`c_struct_combo`、`c_struct_v3`）共 22 頁投影片，分別在 3 種模式下渲染（共 15 次渲染，0 例外）：

| 模式 | 程式碼（code） | 雙欄（split） | 寬舞台（stage） | 置中單欄（stack） | 總頁數 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `auto`（預設） | 5 | 8 | 6 | 3 | 22 |
| `split`（雙欄優先） | 5 | 14 | 0 | 3 | 22 |
| `center`（置中單欄） | 5 | 0 | 0 | 17 | 22 |

**分佈分析**：
1. 三種模式產生的版型分佈各不相同，驗證模式選擇器切換明確生效。
2. 在 `split` 模式下，原先在 `auto` 走 `stage` 的 6 頁單張 `compare` 圖全數成功轉入 `split` 雙欄，故 `split` 頁數由 8 增至 14，`stage` 降為 0。
3. 在 `center` 模式下，除 5 頁不可分欄的 `code` 頁外，其餘 17 頁（8 頁 split + 6 頁 stage + 3 頁 stack）全數統一收斂為 `stack` 置中單欄。

---

## 5. 不變量與幾何約束驗證

1. **可定址代號完整性**：
   - 實測掃描所有模式渲染結果之 `layout.json`，累計檢查 717 個定址代號（包含 `{id}`、`{id}:L{n}`、`{id}:i{n}`、`{id}:l{n}`、`{id}:r{n}`、`{id}:caption`），**缺漏數為 0**。
2. **畫布邊界與內容卡約束**：
   - 所有元素量測框均嚴格限制在 1920×1080 畫布內，越界數為 0。
   - 所有內容元素量測框均在 `CONTENT_BOX`（80, 240, 1840, 980）之內，垂直越界數為 0。
3. **卡片外框簽章一致性**：
   - 採樣各模式全部 44 張 PNG 之 `HEADER_BOX` 與 `CONTENT_BOX` 外框像素，簽章在所有模式下均為唯一值 `((223, 210, 191), (223, 210, 191), (223, 210, 191), (223, 210, 191))`。
4. **決定性（Determinism）**：
   - 同教材同模式連續渲染兩次，產出之 PNG 正規化 MD5 完全一致：
     - `auto`：`79c146a7f51e7ee350c809a1aee042d9  -`
     - `split`：`606e175c9c0ba9f4265c541bfe1262f6  -`
     - `center`：`849726f8d70dbdfcc142d2c52c7a75a2  -`

---

## 6. Spec 第 6 節實測：Compare 放入 810px 雙欄量測數據

在 `split` 模式下，`compare` 圖被分配至寬度約 810px 的雙欄欄位中，左右面板寬度各為 `panel_w = (810 - 60) // 2 = 375px`。面板內標題最大寬度為 `panel_w - 24 = 351px`，項目文字最大寬度為 `panel_w - 32 = 343px`。

使用實際教材內容測試每邊 2、3、4 項時的字級與排版實測數據如下：

### 6.1 每邊 2 項（例：`while 迴圈` vs `for 迴圈`）
- **左側標題** `while 迴圈`：字級 28px，寬度 138.0px（上限 351px，無溢出）。
- **右側標題** `for 迴圈`：字級 28px，寬度 102.2px（上限 351px，無溢出）。
- **左側項目 1** `次數不固定`：字級 26px，寬度 130.0px（上限 343px，無溢出）。
- **左側項目 2** `由條件決定結束`：字級 26px，寬度 182.0px（上限 343px，無溢出）。
- **右側項目 1** `次數固定`：字級 26px，寬度 104.0px（上限 343px，無溢出）。
- **右側項目 2** `由計數器推進`：字級 26px，寬度 156.0px（上限 343px，無溢出）。

### 6.2 每邊 3 項（例：`傳統陣列` vs `結構體（struct）`）
- **左側標題** `傳統陣列`：字級 28px，寬度 112.0px（上限 351px，無溢出）。
- **右側標題** `結構體（struct）`：字級 28px，寬度 221.2px（上限 351px，無溢出）。
- **左側項目**（`只能存同一種型態`、`用索引 0, 1, 2 存取`、`記憶體連續排列`）：字級 26px，寬度分別為 208.0px、216.6px、182.0px（上限 343px，無溢出）。
- **右側項目**（`可打包多種不同型態`、`用欄位名稱存取（.name）`、`欄位依序排列（有對齊）`）：字級 26px，寬度分別為 234.0px、314.7px、286.0px（上限 343px，無溢出）。

### 6.3 每邊 4 項（例：`指標存取 (->)` vs `變數存取 (.)`）
- **左側標題** `指標存取 (->)`：字級 28px，寬度 166.4px（上限 351px，無溢出）。
- **右側標題** `變數存取 (.)`：字級 28px，寬度 148.6px（上限 351px，無溢出）。
- **左側項目**（`透過位址間接讀寫`、`語法：ptr->field`、`需確認指標非 NULL`、`跨函式傳遞開銷小`）：字級 26px，寬度分別為 208.0px、198.1px、230.9px、208.0px（上限 343px，無溢出）。
- **右側項目**（`直接讀寫本體資料`、`語法：obj.field`、`編譯期直接綁定`、`傳值複製整份結構`）：字級 26px，寬度分別為 208.0px、185.0px、182.0px、208.0px（上限 343px，無溢出）。

**實測結論**：在每邊 2 至 4 項的典型中文教學語料下，`compare` 放入 375px 面板時標題均維持在頂標 28px、項目文字均維持在 26px，且最長文字（314.7px）仍小於 343px 寬度上限，**完全無文字溢出面板**的情形發生。

---

## 7. 新增測試與 Red/Green 驗證

在 `tests/test_layout_mode.py` 中新增 14 項測試，各測試之 Red/Green 因果關係說明如下：

1. `test_預設值模式為_auto`：驗證未帶 `mode` 時預設為 `auto`（刪除預設值會引發 TypeError/AssertionError 轉紅）。
2. `test_未知模式值拋出_ValueError`：驗證 `pick_variant` 傳入未知字串時拋出 `ValueError`（若刪除模式檢查或靜默當成 auto 則測試轉紅）。
3. `test_未知模式值在_regions_for拋出_ValueError`：驗證 `regions_for` 傳入未知模式拋錯（若未向下傳遞模式檢查則轉紅）。
4. `test_split模式下單張compare圖走split`：驗證 `split` 模式使 `compare` 圖走 `split`（若刪除 split 模式分支則回傳 stage 轉紅）。
5. `test_split模式下單張boxes與steps圖維持split`：驗證單張 boxes/steps 在 split 模式下為 split。
6. `test_center模式下一律為stack`：驗證 `center` 模式使所有圖形頁轉為 `stack`（若刪除 center 分支則轉紅）。
7. `test_所有模式下code頁皆維持code`：驗證包含程式碼時在任何模式下均維持 `code`（若模式覆蓋 code 則轉紅）。
8. `test_所有模式下多圖與image皆維持stack`：驗證多圖或包含 image 時所有模式均退回 `stack`。
9. `test_regions_for預設值模式為_auto`：驗證 `regions_for` 預設行為與 `mode="auto"` 完全相同。
10. `test_regions_for_split模式下compare圖分配雙欄幾何`：驗證 `compare` 在 `split` 模式下分配得到雙欄座標與 `text_align="left"`。
11. `test_regions_for_split模式容量守門降級`：驗證當圖高超出欄高時（如 5-step steps 直排 760px > 660px），自動降級回 `stack`（若刪除容量守門則維持 split 轉紅）。
12. `test_regions_for_center模式一律為stack幾何`：驗證 `center` 模式產出置中單欄幾何。
13. `test_parse_multipart解析layout欄位且相容三元組解包`：驗證 `parse_multipart` 能正確提取 `layout`，且維持 3 元組解包相容性（若直接回傳 4 元組破壞舊程式碼則轉紅）。
14. `test_real_runner傳遞layout參數至子行程`：驗證 `real_runner` 於給定 `layout` 時正確在 subprocess 參數中附加 `--layout`（若未附加則斷言失敗轉紅）。

---

## 8. 測試套件執行結果

- **完整測試套件**：`.venv/bin/python -m unittest discover -s tests -t .`
- **結果**：`Ran 150 tests in 25.390s, OK (skipped=1)`（包含 127 則既有測試 + 14 則模式測試 + 9 則 random/seed 測試，全數通過）。

---

## 9. 未驗證項目說明

依照專案規範與安全守則：
1. 未執行 `lesson`、`actions`、`synth` 階段（避免產生付費 LLM 費用與本機 GPU 負載）。
2. 未修改前端檔案 `web/index.html`（屬於前端專屬任務範疇）。

---

## 10. 第四種模式 `random` 與 `seed` 參數實作與驗證（Spec 第 8 節）

### 10.1 修改概述

依據設計文件第 8 節追加需求，實作第四種版面模式 `random` 與種子化參數 `seed`，完整串接後端管線：

1. **`video_engine/layout.py`**：
   - `LAYOUT_MODES` 常數擴充為 `("auto", "split", "center", "random")`。
   - 新增 FNV-1a 純算術確定性混合函式 `_roll(seed, slide_id)`，不使用 `random` 亦不使用 `hashlib`，更嚴禁 Python 內建 `hash()`（避免 `PYTHONHASHSEED` 隨機化導致跨行程輸出不可重現）。維持模組零 `import` 與純函式約束。
   - `pick_variant(slide, mode="auto", seed=0)` 與 `regions_for(slide, index, mode="auto", seed=0)` 擴充 `seed` 參數。
   - `random` 模式版型抽取邏輯：
     - 程式碼頁（含 `code`）：固定回傳 `"code"`。
     - 純文字頁、多圖頁（含 `image` 或圖數不為 1）：固定回傳 `"stack"`。
     - 單張圖頁面：由 `("split", "stage", "stack")` 候選集中以 `_roll(seed, slide["id"]) % 3` 抽取。抽中後交由 `regions_for` 之容量守門把關（放不下時自動退回 `stack`）。
2. **`video_engine/render_slides.py`**：
   - 命令列支援 `--seed <int>`（預設值 `0`）。
   - `render_slide` 傳入 `seed=seed`。
   - 產出之 `layout.json` 新增 `"mode"` 與 `"seed"` 欄位，確保任何渲染結果皆可精確重現。
3. **`video_engine/run.py`**：
   - 解析命令列 `--seed` 參數，並於 `slides` 階段透傳 `["--seed", seed]` 至 `render_slides.py`。
4. **`serve.py`**：
   - `MultipartResult` 擴充 `seed` 欄位，同時維持 3-tuple 解包相容性。
   - `parse_multipart` 解析 `seed` 表單欄位。
   - `real_runner` 於給定 `seed` 時附加 `["--seed", str(seed)]`。
   - `Handler._create` 將 `seed` 傳入 `real_runner`。
5. **`tests/test_layout_mode.py`**：
   - 追加 `TestRandomModeAndSeed` 測試類別（共 9 則新測試），涵蓋候選集抽取、決定性、FNV-1a 計算、容量守門降級、multipart/real_runner 參數傳遞、以及 `layout.py` 零 import / 零 hash 靜態檢查。

---

### 10.2 驗證項目與實測數據

#### 1. 單元測試全數通過
- **指令**：`.venv/bin/python -m unittest discover -s tests -t .`
- **結果**：`Ran 150 tests in 25.390s, OK (skipped=1)`，全部測試通過。

#### 2. `auto` 模式回歸閘不受 `--seed` 影響
- **基準指令**：
  ```bash
  D=$(mktemp -d); for f in c_loop c_string c_struct c_struct_combo c_struct_v3; do .venv/bin/python video_engine/render_slides.py video_engine/examples/$f.lesson.json $D/$f >/dev/null; done; find $D -name '*.png' | sort | xargs md5sum | sed "s|$D|X|" | md5sum
  ```
- **無 seed 輸出**：`79c146a7f51e7ee350c809a1aee042d9  -`
- **帶入 `--seed 42` 輸出**：`79c146a7f51e7ee350c809a1aee042d9  -`
- **驗證結論**：`auto` 模式回歸閘 Hash 完全不變。

#### 3. `random` 模式同種子逐位元組完全相同（Determinism）
- **實測方式**：以 5 份教材在 `random` 模式下指定 `--seed 12345` 連續渲染至兩個獨立暫存目錄。
- **目錄 1 PNG 正規化 Hash**：`5ab050a109d878b41aff88e402381298  -`
- **目錄 2 PNG 正規化 Hash**：`5ab050a109d878b41aff88e402381298  -`
- **驗證結論**：44 張 PNG 逐位元組完全相同。

#### 4. 不同種子之版型分佈差異實測
實測 5 份教材共 22 頁在不同種子下的版型分佈：

| 種子（seed） | 程式碼（code） | 雙欄（split） | 寬舞台（stage） | 置中單欄（stack） | 總頁數 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `0` | 5 | 1 | 7 | 9 | 22 |
| `1` | 5 | 4 | 3 | 10 | 22 |
| `2` | 5 | 0 | 10 | 7 | 22 |
| `7` | 5 | 4 | 7 | 6 | 22 |
| `42` | 5 | 11 | 3 | 3 | 22 |
| `100` | 5 | 3 | 4 | 10 | 22 |
| `2026` | 5 | 11 | 3 | 3 | 22 |

**驗證結論**：不同種子明確產生多樣且具差異性之版型組合，且程式碼頁（5 頁）在所有種子下均穩定維持 `code`。

#### 5. `random` 模式畫布與內容卡邊界驗證
- **實測方式**：跨 5 份教材在 7 組不同種子（0, 1, 2, 7, 42, 100, 999）下渲染並檢查全部元素量測框。
- **檢查元素總數**：1,673 個
- **超出畫布（1920×1080）數**：`0`
- **超出內容卡（`CONTENT_BOX`）數**：`0`

#### 6. 模組純淨度靜態檢查
- `grep -c "hash(" video_engine/layout.py` → **0**
- `grep -c "^import \|^from " video_engine/layout.py` → **0**

