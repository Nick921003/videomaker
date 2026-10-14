# 第二步前端獨立驗收報告：教材來源多格式支援與上傳流程

日期：2026-10-08
驗收對象：工作台第一步「教材來源」多格式擴充（`workbench/web/js/pages/make-source.mjs`）與前端測試（`workbench/web/tests/make.test.mjs`、`workbench/web/tests/app.test.mjs`）
驗收模式：AGY 親自修改並執行測試；不修改其他頁面、無後端修改、無新增依賴、無付費 API 呼叫、未執行 git commit。

---

## 一、驗收方法與邊界劃分

### 1. 變更邊界控制
- **修改檔案嚴格限制**：
  - [make-source.mjs](file:///home/pjw92/projects/videomaker/workbench/web/js/pages/make-source.mjs)：擴充 `ACCEPTED_KINDS`、`sourceKind`、`fileInput.accept`、簡短提示（`uploadNote`）與格式錯誤提示。
  - [make.test.mjs](file:///home/pjw92/projects/videomaker/workbench/web/tests/make.test.mjs)：擴充十種副檔名大小寫、多點號及無效格式斷言。
  - [app.test.mjs](file:///home/pjw92/projects/videomaker/workbench/web/tests/app.test.mjs)：新增完整整合測試，涵蓋 DOM 屬性、簡短提示、DOCX 摘要與確認整理、MD 直存 `/units`，以及無效格式攔截。
- **無任何額外依賴**：沿用專案現有原生 JavaScript 模組與 Node.js 測試執行器。
- **無付費 API 呼叫**：全數使用本機測試與 mock 介面，未觸碰 Gemini API 或外部付費端點。
- **Git Commit 狀態**：遵守規則，未執行 `git commit`。

### 2. 親自執行測試套件
- 執行指令：`node --test workbench/web/tests`（使用系統 Node v22.20.0）。
- 執行結果：**88 項測試全數通過（pass: 88, fail: 0, duration: ~399ms）**。

---

## 二、功能點查核與實際測試結果

### 1. 支援格式清單與副檔名判斷 (`sourceKind` & `ACCEPTED_KINDS`)
- **十種格式支援**：
  - 定義 `ACCEPTED_KINDS = ['md', 'txt', 'pdf', 'pptx', 'docx', 'xlsx', 'csv', 'png', 'jpg', 'jpeg']`。
  - `sourceKind(name)` 正確解析副檔名，對應包含大寫（如 `.PDF`、`.DOCX`）、多點號檔名（如 `lesson.v2.PPTX`）皆能精確回傳小寫類型。
  - 非支援格式（如 `.exe`、`.mp4`、`.zip`、無副檔名、空字串）一律回傳 `null`。
- **測試驗證**：在 [make.test.mjs](file:///home/pjw92/projects/videomaker/workbench/web/tests/make.test.mjs) 通過單元斷言。

### 2. 檔案輸入屬性與簡短介面提示 (`accept` & `uploadNote`)
- **檔案選取器過濾**：
  - `fileInput.accept` 設定為 `.md,.txt,.pdf,.pptx,.docx,.xlsx,.csv,.png,.jpg,.jpeg`，對齊後端允許格式。
- **簡短介面提示**：
  - 提示文字設定為 `MD、TXT 直接讀取；PDF、PPTX、DOCX、XLSX、CSV 與圖片先看摘要，再確認整理。`。
  - 維持既有單一 `section-note` 簡潔樣式，不增加雜亂細則、不堆疊免責宣告小字，排版維持乾淨一致。
- **測試驗證**：在 [app.test.mjs](file:///home/pjw92/projects/videomaker/workbench/web/tests/app.test.mjs) 驗證 `file.accept` 屬性與 DOM 文字符合預期。

### 3. 文字直存 vs 多格式人工確認流程分流
- **MD / TXT 直接存文字**：
  - 檔案選取後使用 `FileReader` 讀取文字，直接向 `/units` 發送 POST 建立教材，並以檔名作為預設教材標題。
  - 完全略過 `/uploads` 與模型整理流程，無多餘確認等待。
- **其他格式（PDF, PPTX, DOCX, XLSX, CSV, PNG, JPG, JPEG）上傳後人工確認**：
  - 透過 `FormData` 向 `/uploads` 發起非同步抽取。
  - 介面展示摘要區塊（檔名、頁數、字數、文字摘錄、費用估計）。
  - 使用者必須親自點擊「確認整理（約 US$0.01）」按鈕，前端才向 `/uploads/:id/normalize` 發起整理工作並進入 Live 進度監控。
  - 在未確認前，絕不自動呼叫整理工作，杜絕未預期模型花費。
- **測試驗證**：在 [app.test.mjs](file:///home/pjw92/projects/videomaker/workbench/web/tests/app.test.mjs) 驗證 DOCX 上傳流程（`/uploads` -> 摘要 -> 點擊確認 -> `/uploads/up-docx/normalize`）與 MD 上傳流程（`/units` 直接建立），呼叫鏈與傳遞資料正確無誤。

### 4. 異常檔案防護
- **不支援格式阻擋**：
  - 若使用者強行選取不支援格式（如 `.exe`），拋出清晰錯誤提示：`請選 PDF、PPTX、DOCX、XLSX、CSV、MD、TXT、PNG 或 JPEG 教材。`。
  - 前端立即中斷，不送出任何 `/uploads` 或 `/units` 網路請求。
- **超量檔案防護**：
  - 維持 5 MB 上限檢查，超出時提示 `檔案超過 5 MB。` 並提供 `拆小再上傳。` 建議。
- **測試驗證**：在 [app.test.mjs](file:///home/pjw92/projects/videomaker/workbench/web/tests/app.test.mjs) 驗證無效格式攔截及警示顯示。

---

## 三、阻擋問題 (Blocking Issues)

- **無任何阻擋問題（No Blocking Issues）**。
- 所有 88 項前端測試執行順暢，邏輯精確，無未捕捉的非同步錯誤或記憶體流失。

---

## 四、未驗範圍 (Unverified Scope)

1. **後端多格式實際抽取品質**：
   - 本輪為前端驗收，後端各格式解析核心邏輯（`workbench/source_document.py`、`uploads.py`、`material.py`）已由後端專屬測試覆蓋，非本輪測試範圍。
2. **真實瀏覽器檔案對話框渲染**：
   - 瀏覽器 OS 原生檔案選擇視窗對 `accept` 屬性的過濾效果由作業系統與瀏覽器實作決定，DOM 層級屬性已完全對應。
3. **付費模型實際執行**：
   - 未呼叫真實 Gemini 模型，整理之實際 AI 產出待後續步驟整合驗收。

---

## 五、驗收結論

工作台第二步「前端多格式教材來源整合」任務圓滿達成：
1. `sourceKind` 與 `accept` 完整涵蓋 `pdf, pptx, docx, xlsx, csv, md, txt, png, jpg, jpeg` 10 種格式。
2. MD/TXT 維持直接讀取存文字，其餘 8 種格式落實上傳後人工確認整理。
3. 介面提示簡潔清晰，未增加雜亂小字。
4. 前端測試套件（88 項）全數通過，無破壞性變更、無新增依賴、未進行 commit。

**第二步前端工作驗收判定為通過**。
