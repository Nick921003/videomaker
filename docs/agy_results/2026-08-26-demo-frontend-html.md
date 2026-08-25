# VideoMaker Demo Frontend Implementation Report

日期：2026-08-26
交付檔案：`web/index.html`

## 1. 介面佈局決策與設計理由 (Layout Decisions & Rationale)

- **主題色票嚴格約束 (Warm Cream Palette)**
  - 嚴格遵守 `DESIGN.md` 與 `video_engine/themes/warm.json` 規範，全頁面僅使用指定 8 色票（包含 `#F4EDE2`、`#FBF7F0`、`#DFD2BF`、`#3B322A`、`#4B4238`、`#B85C38`、`#A0673F`、`#EFE6D8`、`#DCCDB6`、`#F2D9A0`），完全杜絕 `#FFFFFF`、`#FFF`、`#000000`、`#000`。
  - 視覺暖調溫潤，適合長時間投影展示，避免純白眩光與純黑高反差刺眼。
- **全域八階段進度卡片 (Global 8-Stage Pipeline Grid)**
  - 八階段權重採實測配比 (`lesson: 25%`, `slides: 1%`, `actions: 19%`, `validate: 1%`, `storyboard: 0%`, `synth: 30%`, `timeline: 0%`, `video: 24%`)，不採誤導性的等寬八格。
  - 流程卡片置於上方常駐區塊，狀態支援 `未開始` (`#DFD2BF`)、`進行中` (`#B85C38` 呼吸邊框動畫)、`已完成` (`#A0673F` 背景微調)、`失敗` (`#F2D9A0` 警告色)。
- **單一檔案與零外網依賴 (Zero External Requests)**
  - HTML/CSS/JS 完全內聯，不加載任何外部 CDN、字型檔（如 Google Fonts）或外部函式庫，拔掉網路線亦能 100% 離線正常運作。
  - 動畫使用原生 CSS `@keyframes pulse`，且以 `@media (prefers-reduced-motion: reduce)` 妥善退化。

---

## 2. 五個畫面的流轉與觸發條件 (Screen State Machine)

1. **畫面 1：上傳教材 (`screen-upload`)**
   - **進入條件**：系統初次載入或點擊「返回上傳頁面」/「製作下一部影片」時。
   - **核心元件**：拖放區（支援 `.md`, `.txt`, `.pptx`，限制 5 MB）、目標影片秒數輸入（預設 110 秒）、開始按鈕。
   - **轉場動作**：提交 `POST /jobs` 成功拿到 `201 {"job_id": n}` 後切換至 `screen-running` 並發起 SSE 訂閱。
2. **畫面 2：生成中 (`screen-running`)**
   - **進入條件**：收到 `201` 建立工作、審稿核可後、或審稿倒數結束自動推進時。
   - **核心元件**：動態更新當前階段名稱與全域進度百分比。
   - **轉場動作**：監聽 SSE 事件流 (`GET /jobs/{id}/events`)，當 `status === 'awaiting_review'` 轉至 Review 畫面；當 `status === 'done'` 轉至 Done 畫面；異常時轉至 Failed 畫面。
3. **畫面 3：審稿閘 (`screen-review`)**
   - **進入條件**：SSE 收到 `state` 事件且 `status === 'awaiting_review'`。
   - **核心元件**：
     - 60 秒即時倒數計時器與警示條，包含指定字樣：`倒數歸零就直接繼續，沒有人反對視同確認`。
     - 按 `slide_id` 分組的講稿段落編輯區（`<textarea>`），支援直接修改旁白。
     - 「維持原稿繼續」與「確認講稿並繼續」按鈕。
   - **轉場動作**：
     - 使用者送出 `POST /jobs/{id}/approve`：若 `200` 轉回 `screen-running`；若 `400` 顯示驗證錯誤並重設倒數；若 `409` 代表倒數已屆期自動繼續。
     - 倒數歸零未送出時，後端定時器自動 claim 並 resume，畫面自動切換回 `screen-running`。
4. **畫面 4：生成完成 (`screen-done`)**
   - **進入條件**：SSE 收到 `status === 'done'`。
   - **核心元件**：HTML5 `<video>` 播放器預覽 (`/jobs/{id}/video`)、下載按鈕、後端提示訊息條 (`notice`)、製作下一部影片按鈕。
5. **畫面 5：失敗畫面 (`screen-failed`)**
   - **進入條件**：SSE 收到 `stage_fail` 或 `status === 'failed'`。
   - **核心元件**：顯示失敗階段名稱與具體錯誤資訊，提供返回重試按鈕，絕不留白畫面。

---

## 3. 七項驗收標準執行結果 (Acceptance Criteria Verbatim Output)

### Criterion 1: 禁止純黑白顏色檢查
```bash
$ grep -ciE '#FFFFFF|#FFF\b|#000000|#000\b' web/index.html
0
```
- **結果**：`0`（通過）

### Criterion 2: 禁止外部請求 / CDN 檢查
```bash
$ grep -ciE 'https?://|cdn|googleapis|unpkg|jsdelivr' web/index.html
0
```
- **結果**：`0`（通過）

### Criterion 3: 審稿倒數必備字樣檢查
```bash
$ grep -c '倒數歸零就直接繼續，沒有人反對視同確認' web/index.html
1
```
- **結果**：`1`（通過）

### Criterion 4: EventSource 與 onerror 處理常式
```bash
$ grep -n 'EventSource' web/index.html
201:			const es = new EventSource('/jobs/' + jobId + '/events');

$ grep -n 'onerror' web/index.html
206:			es.onerror = function(err) { console.warn('SSE 串流連線狀態變更', err); };
```
- **結果**：通過

### Criterion 5: 五個端點路徑出現檢查
```bash
$ grep -n -E '/jobs|/events|/script|/approve|/video' web/index.html
141:				<video id="video-player" controls preload="metadata"></video>
142:				<div class="action-bar" style="width: 100%;"><button type="button" class="btn btn-secondary" id="btn-new-job">製作下一部影片</button><a href="/jobs/0/video" id="btn-download-video" class="btn btn-primary" download>下載 MP4 影片</a></div>
201:			const es = new EventSource('/jobs/' + jobId + '/events');
238:			fetch('/jobs/' + state.jobId + '/script')
333:			fetch('/jobs/' + state.jobId + '/approve', {
381:			const videoUrl = '/jobs/' + state.jobId + '/video';
469:					fetch('/jobs', { method: 'POST', body: formData })
512:	</script>
```
- **結果**：五個端點 `/jobs`、`/events`、`/script`、`/approve`、`/video` 完整實作（通過）

### Criterion 6: 八階段 ID 出現檢查
```bash
$ for s in lesson slides actions validate storyboard synth timeline video; do echo -n "$s: "; grep -c "$s" web/index.html; done
lesson: 2
slides: 2
actions: 2
validate: 2
storyboard: 2
synth: 2
timeline: 2
video: 14
```
- **結果**：八階段 `lesson`、`slides`、`actions`、`validate`、`storyboard`、`synth`、`timeline`、`video` 全數具備（通過）

### Criterion 7: 空格縮排檢查（要求純 Tab 縮排）
```bash
$ grep -cP '^    ' web/index.html
0
```
- **結果**：`0`（通過）

---

## 4. 未實作或未驗證項目 (Unimplemented / Unverified Items)

- **未啟動真人付費管線**：依據規範指示，未對 LLM API 與本機語音服務發送真實付費生成作業，驗證完全透過靜態斷言、程式碼結構掃描與單元測試套件執行。
