# 第四步前端實作與驗收報告：PPT 與心智圖檢視器可讀性升級

日期：2026-10-08
執行角色：AGY 前端實作
共同執行計畫：`docs/superpowers/plans/2026-10-08-ppt-mindmap-quality.md`
約束遵守：僅修改指定前端檔案與測試，未修改後端，無新增依賴，無付費 API / TTS 呼叫，未執行 git commit。

---

## 一、修改檔案與職責邊界

本次第四步前端修改嚴格限制於以下檔案：
1. **`workbench/web/js/viewers/svg.mjs`**：
   - 實作概念節點 (`g[data-node-id]`) 的點選與鍵盤操作（Enter / Space）。
   - 解析 Codex 在節點新增之安全文字 metadata（`title[data-node-label]`、`desc[data-node-explanation]`、`desc[data-node-quote]`）。
   - 新增下方概念詳情面板 (`svg-inspector`)，初始保持總覽提示，選取後呈現解釋與折疊原文引用。
   - 工具列補齊「下載 SVG」按鈕，並以 `AbortController` 實作離頁清理。
   - 完整相容舊版無 metadata 之 SVG。
2. **`workbench/web/js/viewers/deck.mjs`**：
   - 替換舊版重複縮字 40 次（0.9^40 縮至微型字）的 `fitSlide` 實作。
   - 新 1.1 簡報禁止無限縮字：設定縮字下限（最多 2 次至 0.82，保持足夠字級）。
   - 超量時採可讀與明示處理：標記 `data-overflow="true"`、新增 `.deck-overflow-notice` 捲動提示，並維持垂直捲動可見，不默默隱藏內容。
   - 舊 1.0 簡報保留最多 40 次縮字邏輯，維持舊產出相容。
   - 完整維持頁跳轉（左右方向鍵、上一頁/下一頁、下拉選單）及講者筆記/原文同步。
3. **`workbench/web/styles.css`**：
   - 嚴格遵守「只能新增 viewer 規則，保留既有改動」之紅線。
   - 僅於檢視器樣式區塊新增：`.svg-download`、`.viewer-svg` 三列網格、`.svg-viewport`、`.svg-inspector` 面板與卡片樣式、`.diagram-svg g[data-node-id]` 焦點與選中高亮、`.deck-overflow-notice` 提示等規則。
4. **前端測試**：
   - 更新 `workbench/web/tests/dom-helper.mjs`：提供元素選擇器比對、`closest`、`localName`、`childNodes` 及輕量 XML 解析，以支援 Node 22 原生測試環境。
   - 新增 `workbench/web/tests/viewers.test.mjs`：完整覆蓋 SVG 點選、鍵盤選取、折疊來源、舊 SVG 相容、簡報 1.1 縮字限制與超量提示、1.0 相容與跳頁。
   - 更新 `workbench/web/tests/index.js`：將新測試納入全套測試。

---

## 二、實作細節查核

### 1. 心智圖檢視器 (`svg.mjs`)
- **無障礙與互動能力**：
  - 掃描所有 `g[data-node-id]`，設定 `tabindex="0"`、`role="button"`、`aria-pressed="false"` 及 `aria-label`。
  - 支援滑鼠直接點選節點或按下鍵盤 `Enter` / `Space` 選取概念。
  - 透過 `data-selected="true"` 與 `aria-pressed="true"` 同步狀態，並於 CSS 呈現強調外框與陰影。
- **安全文字 Metadata 解析 (`extractNodeMetadata`)**：
  - 優先讀取 `title[data-node-label]`（支援屬性或文字節點），未提供時 fallback 至節點內 text 標籤或 node-id。
  - 讀取 `desc[data-node-explanation]` 作為概念解釋。
  - 讀取 `desc[data-node-quote]` 作為教材原文引用。
  - 純使用 DOM 文字屬性與 `textContent` 渲染，避免 HTML 注入風險。
- **概念詳情與折疊來源 (`renderInspector`)**：
  - 初始載入時顯示中性提示：「點選或以鍵盤選取心智圖節點，檢視概念解釋與教材來源。」，保持概念總覽。
  - 選取概念後：
    - 顯示概念標題 (`h3.svg-inspector-title`)。
    - 顯示概念解釋 (`p.svg-inspector-explanation`)；若無解釋則提示 `（此概念未提供延伸說明）`。
    - 若有原文引用，以標準 `<details class="svg-inspector-quote"><summary>教材原文引用</summary><blockquote>...</blockquote></details>` 摺疊呈現。
- **相容與清理**：
  - 舊版 SVG（如既有 `workbench/web/mock/mindmap.svg`）無 metadata 時仍可正常載入、縮放、拖曳與點選，不拋出錯誤。
  - 檢視器 `dispose()` 呼叫 `abort.abort()` 與 `controls.destroy()`，徹底移除所有節點監聽與 panzoom 資源。

### 2. 簡報檢視器 (`deck.mjs`)
- **禁止無限縮字 (`fitSlide`)**：
  - 區分 `contract_version`：
    - **1.1 版**：最大嘗試次數設為 2 次（`maxPasses = 2`），縮小下限設為 `0.82`。主文字（原 23px）縮後仍維持在 ~19px，確保焦點清楚、少小字。
    - **1.0 版**：保留原本最多 40 次 0.9 縮字（`maxPasses = 40`），保證舊版本相容性。
- **超量明示與可讀處理**：
  - 於 1.1 版中，若在可讀字級下卡片或內容仍溢出（`scrollHeight > clientHeight + 1`）：
    - 在卡片標記 `data-overflow="true"`。
    - 在卡片底部插入明示提示：`<p class="deck-overflow-notice" role="note">內容較多 · 可向下捲動閱讀完整內容</p>`。
    - CSS 確保卡片具備 `overflow-y: auto`，內容不被裁切或隱藏。
  - 正常尺寸投影片不觸發縮字與提示；翻頁時隨卡片重建清理提示。
- **跳頁與講者筆記**：
  - 完整維持下拉選單直接跳頁、上一頁/下一頁按鈕、鍵盤左右箭頭翻頁。
  - 每頁同步更新講者筆記與教材原文引言。

### 3. CSS 規則追加 (`styles.css`)
- **SVG Viewer**：
  - `.viewer-svg`：採用 `grid-template-rows: auto minmax(0, 1fr) auto`，頂部工具列、中間畫布、底部詳情面板。
  - `.svg-download`：向右對齊。
  - `.svg-inspector`：包含背景色、捲動軸與字級規範（標題 15px、解釋 14px、原文 13px）。
  - `.diagram-svg g[data-node-id]`：設定 pointer 指標、`:focus-visible` 虛線外框、`[data-selected="true"]` 主題色實線外框與陰影。
- **Deck Viewer**：
  - `.deck-slide[data-overflow="true"]`：啟用 `overflow-y: auto`。
  - `.deck-overflow-notice`：淡紅底色與虛線邊框，呈現清楚而不喧賓奪主的捲動提示。

---

## 三、自動化測試驗證

本機環境：Node.js `v22.20.0`，執行指令：
```bash
node --test workbench/web/tests/index.js
```

### 測試輸出摘要：
```text
✔ 導覽會更新 hash 並編碼查詢參數 (0.37ms)
✔ 學生提問 mock 依問題選擇影片、超出範圍、未生成與沒有對應段落 (35.93ms)
✔ 建立教材後先維持未分析，分析工作完成才取得分析結果 (25.16ms)
✔ 重配完成品只跑 narrate/render、每兩秒前進並清掉指定句號 warning (11.74ms)
✔ 上傳 PDF 僅提供摘要，確認整理後的工作才建立教材 (55.29ms)
...
✔ SVG viewer: 初始維持總覽，點選節點顯示解釋與折疊來源，提供下載與離頁清理 (12.93ms)
✔ SVG viewer: 舊版 SVG 無 metadata 仍能正常載入與點選，不拋出錯誤 (4.63ms)
✔ 簡報 viewer: 新 1.1 簡報不可 fitSlide 無限縮字，超量時提供可讀標記與提示；舊 1.0 維持相容 (1.38ms)
✔ 簡報 viewer: 頁跳轉、講者筆記與原文完整維持 (9.39ms)
...
ℹ tests 93
ℹ suites 0
ℹ pass 93
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 860.93ms
```

93 項測試全數通過（舊既有 89 項 + 本次新增 4 項檢視器整合測試），零錯誤、零略過。

---

## 四、結論

第四步前端檢視器可讀性改造已全數完成：
1. 心智圖可直接點選或鍵盤選取節點，直覺閱讀概念解釋與折疊來源；舊 SVG 無 metadata 仍平穩運作。
2. 簡報 1.1 終止 40 次無限縮字，維持足夠字級並在超量時明示引導捲動閱讀，舊 1.0 維持相容。
3. 程式碼乾淨、縮排遵循 Tab (4格)、無外部依賴、全套測試通過。
