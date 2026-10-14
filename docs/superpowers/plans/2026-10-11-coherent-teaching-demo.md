# Coherent Teaching Demo Implementation Plan

> **For agentic workers:** Use executing-plans to execute the scoped steps in this session; native adversarial review checks the plan. The user has already chosen the direction and authorized sample creation.

**Goal:** 交付一支可播放、可跳秒的 48 秒共同主視覺迴圈動畫，含字幕與同內容 A/B。

**Architecture:** `prototypes/component_trials_20261011/coherent/` 隔離示範。lesson 只放語意和時間，model 純函式計算執行軌跡，runtime 實測 DOM/Canvas 文字且由同一時間驅動保存的 CH/DG/Kit 元件。`video_engine/themes/coherent_demo.json` 獨立色表，不改預設 theme；本機靜態伺服器從 repo root 啟動讓示範載入它。

**Tech Stack:** 原有 Canvas/SVG kits、現有 Chromium/Playwright、FFmpeg、Node test；不安裝依賴。

- [x] 1. 在 `coherent/model.test.mjs` 先寫有意義的狀態驗證：從 init 到 check/body/update/return/exit，五次累加及第六次判斷、全片各字幕、A/B 的教材狀態一致；用 `node --test` 見到缺少 model 的失敗後實作 `model.mjs`＋`lesson.json`。數值由循環計算，不硬編錯誤執行结果。
- [x] 2. 新增 `video_engine/themes/coherent_demo.json`，保存暖色、紙面、深圖區、平面圖表與語意色；新增 `coherent/stage.html`、`runtime.mjs`。固定框架 1920×1080、標題／content／字幕分區。以 layout 關係建立量測框；Kit 引線實際執行且用色覆寫由 theme 決定；CH grid/bars 原始執行帶 theme options。公式匹配符號適配 t1，`DG.math` 執行。折角只動局部，紙片不整面翻起。
- [x] 3. 新增 `coherent/index.html`、`review.mjs`：iframe renderFrame(t) 驅動 HTML 預覽，A/B 只改皮膚而保持 t；預覽字幕全片，進度／章節跳秒／播放暫停重播；另提供成片 MP4、SRT，MP4 Blob 載入克服 SimpleHTTPServer 無 Range。控制列不進匯出 frame。
- [x] 4. 新增 `coherent/verify_export.py`，先實測冷／倒序狀態及像素、來源雜湊、字形 coverage、各幀文字框與 panel、字幕閱讀速度、UI 375/768/1440 操作。截取實際 frame PNG 送 FFmpeg，輸出 1152 幀無音訊 MP4/SRT，ffprobe／完整解碼；保存 report、關鍵 PNG，觀看導入、兩次過場、code focus、終止條件、量化與折角。
- [x] 5. `coherent/README.md` 記錄目前使用者方向、來源適配與限制、重製命令及實測結果。跑正式 Python 回歸與新增 Node checks，新增檔 no-index whitespace 檢查，分辨 pre-existing 變更。完成後開新比較頁給使用者，不覆蓋舊評選。

## 審查關注

圖表的 5/6 次口徑需精確；初始化不應在回邊重複；exit 不可在第 5 次主體前發生。教學 state 與 visual snapshot 均須 seek 決定性。保存的 font subset 不一定含新教材字，生成獨立新 subset 並量測實際 glyph；不得改舊字型影響既有六片。皮膚對照不能宣稱為原元件拼接或正式 pipeline 整合。修改紙藝效果必須有可看見的收尾動作，不能只換色。

## 初版實測結果與修正（revision 1）

2026-10-11：48 秒、1152 幀、1920×1080、24fps、無音訊 MP4 完成，1152 幀文字／所屬 panel 邊界與完整解碼通過。96 次冷／前進／倒序／跨模式影格比較，最大 201 個邊緣像素差、單通道差 9；內容狀態、字框、字幕完全一致。原始來源 SHA256 與字形覆蓋通過。375／768／1440px UI 播放、暫停、seek、重播、模式保持時間、MP4 實播通過；375px 另實測字型延遲時禁用控制及 MP4 延遲請求回切 HTML 的競態。

審查指出的輪次提前增加已修正，先補紅測試再修 model，五項語意測試通過。未 ready 的切換保護、MP4 共享 load promise／requestVersion 已實測。原 Kit flow dots 未啟用，使用唯一當前 edge marker。工程 SVG 固定合成層後 seek 邊緣差減少。正式 Python 回歸 780 項（1 skip）、前端回歸 104 項通過。新增文字檔 whitespace 檢查通過；全域 diff-check 的 workbench/web/styles.css 舊有空白不在本次變更範圍。

實看 MP4 第23秒及47.95秒、全部章節 PNG 與375px 比較頁，完成交付檢查。檔案／報告在 coherent/out/；候選原片與正式預設未改，整體風格與節奏待使用者評價。

## 看片回饋修正與重新驗證（revision 2）

初版只測文字所屬 panel 邊界，不能防止同區文字相交。新增 presentation_checks.py／check_presentation.py，修前重現8.4秒數值互撞、流程標籤與箭頭末端提早存在，另抓到44.4／44.7秒公式互撞。修後指定影格及全1152幀通過；重新 MP4 匯出也逐幀執行文字兩兩相交、分支首次揭露及路徑完成依賴檢查。

revision 2 report：48秒、1152幀、MP4 1,085,022 bytes，完整解碼、來源雜湊與字形覆蓋、三種寬度 UI 操作通過；96次 seek 比較最大8像素／單通道2，未放寬原容差。正式 Python 回歸780項（1 skip）、前端104項及模型5項重新通過。實看成片8.4與29.3秒以確認回報問題修正。

新增 docs/TEACHING_VISUAL_CUSTOMIZATION.md：同片連貫、跨片可變主風格；影片先重用，觀看後追問理解情況，再找適合的既有版本或補做指定重點。已核對正式 server.ask／library.showAnswer 支援既有影片觀看；聊天頁仍為模擬，對話補強路由屬後續需求，這次未改聊天生成。
