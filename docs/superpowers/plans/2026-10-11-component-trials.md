# 動畫元件試片實作計畫

**Goal:** 交付六支 15 秒程式教材動畫＋字幕，讓使用者實際評選候選元件與節奏。

**Architecture:** 固定來源的 Canvas grammar 與 DOM/SVG kit 分別用純時間 wrapper，讀共用試片資料；同一評選頁載入 iframe 或 MP4。正式 pipeline、catalog、聊天頁不變。

**Tech Stack:** 現有 Python、Playwright Chromium、Canvas/SVG、FFmpeg；零新依賴與付費服務。

## 檔案與步驟

- [x] 1. 來源：將已讀的原始 t1/t2/t3、v4/v7/v8 kit 及必要 core/libs 保存至 `prototypes/component_trials_20261011/vendor/`。`sources.json` 保存 repo、commit、path、URL、SHA256；檢查 `sha256(file_bytes)==manifest.sha256`。所有原始碼不修改，適配僅在 wrapper。
- [x] 2. 資料：`trials.json` 六支各含 id、title、duration、renderer、source、subtitles、beats、payload；subtitle 區間有序，`0 <= start < end <= 15`；`min_size=28`。題材逐步呈現，核心物件不任意增添。
- [x] 3. 渲染：`sample.html`＋`sample.js` 使用 URL 的 id 選來源，建立 `renderFrame(t)`。Canvas ctx 的 `p=(t,at,d)=>clamp((t-at+1/24)/d)`；岚叔 factories 使用原始 `.render(t)`，chalk 由 `Kit.render(t)` 驅動。字幕由同份 JSON 查 `start<=t<end`；`.frame` 固定 1920×1080，預覽只整體縮放，匯出只擷取 frame。
- [x] 4. 比較：`index.html`＋`review.js` 提供六卡、同頁預览、效果/題材/時間階段、保留/待調/淘汰評選（localStorage）、下載 MP4/SRT、暫停/seek/播放。透過 `postMessage({type:'seek',time})` 且核對 source frame 控制 sample；不顯示製作成功或正式採入訊息。
- [x] 5. 驗證與匯出：`verify_export.py` 在 Chromium 讀 sample，對每 frame 呼叫 renderFrame(k/24)，量測文字，截圖送 FFmpeg，video-only、360 frames、1920×1080/24fps。全新頁面直接跳秒與連續／倒序播放的文字、位置、透明度與字幕狀態必須相同；SVG 抗鋸齒僅容許最多 250 個像素、單色差最多 24，並保存實際差值；核對 subtitles 幀狀態，產 MP4、SRT、關鍵 PNG、量測 report。先測 fixture 語意與 API 行為，再渲染；有越界/重疊需修題材布局，失敗不可報完成。
- [x] 6. 在 375/768/1440px 操作比較頁，實測評選刷新保留。核對實際 MP4 影格、全片解碼。執行現有 Python/JS 回歸；`git diff --check -- prototypes/component_trials_20261011 docs/superpowers/specs/2026-10-11-component-trials.md docs/superpowers/plans/2026-10-11-component-trials.md`。驗收報告記錄實際結果、未涵蓋的裝飾碰撞量測及使用者選擇仍待確認。

## 審查重點

原始元件是否真正被執行；字幕節奏是否從內容決定；圖表尺度與標籤可讀；動態容器與 CSS 是否破壞倒序 seek；匯出不能包含控制列；評選不是正式採入；簡短持續圖像不靠旁白冒充完整課程。

使用者已授權本次試片工作，計畫完成後直接於本對話執行並修正審查指出的實質問題；不另外要求執行方式確認。

## 已處理的審查與實測修正

原始 chart.js 與 paint.js 依賴已補齊；保存的繁體字型在元件初始化前載入。黑板圓圈使用 rx/ry 雙半徑，陣列改為連續格，紙帶位置用 wrapper 固定以避免來源 CSS 覆蓋。Canvas 量測同步處理 reset 和 width/height 重設。圖表字幕改為固定 n 的操作次數比較，預覽結束停在最後實際影格。SVG 尺寸文字採 geometricPrecision，避免 Chromium 對第一次顯示時的鏡頭縮放做不同的字體取整。

## 驗收

六支 15 秒 MP4 皆完成 1920×1080／24fps／360 幀、全片解碼與逐格文字邊界檢查。375／768／1440px 比較頁播放、暫停、跳秒、重播、評選刷新／匯出與六支 MP4 實播通過；靜態伺服器不支援 Range，短片以 Blob URL 完整載入，使 MP4 可跳秒。780 項 Python 回歸（1 skip）與 99 項前端回歸通過。新增檔案 no-index whitespace 檢查通過；全域 diff-check 的 styles.css 舊有 whitespace 不屬本次範圍。實測保存於 out/batch.report.json 與各片 report；所有候選等待使用者選擇。
