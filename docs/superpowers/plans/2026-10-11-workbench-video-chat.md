# Workbench Video Chat Implementation Plan

> **For agentic workers:** 使用既有工作區執行；使用者已要求先提交現況，再整合供自行操作。依 writing-plans、adversarial-review 與 verification-before-completion 驗證；不覆蓋先前樣片或評選。維持現在含原型資產的 checkout，避免遺失剛提交的上下文。

**Goal:** 在目前工作台用簡潔大字介面播放已確認的48秒教材與既有元件示範，觀看後可以對話定位、重播或留下指定重點的補強需求。

**Architecture:** chat.mjs 以 DOM API 建構兩欄頁，讀正式 /units 和 /ask 以重用影片；新增 chat-data.mjs 保存示範與重播範圍、保守判別操作意圖，不把不同教材宣稱成同題另一風格。既有48秒MP4透過安全的 /trials/ 靜態映射提供，沿用伺服器的 Range 支援。對話中的生成僅整理可查看的補強需求，不宣稱AI生成完成。

**Tech Stack:** 原有原生JS／CSS、Python HTTP伺服器、Node tests、現有Playwright；不新增依賴，不呼叫付費模型或TTS。

## Task 1: 行為與媒體路由

Files: workbench/web/tests/chat.test.mjs、tests/test_workbench_server.py、workbench/server.py、workbench/web/js/pages/chat-data.mjs。

- [ ] 先寫測試：初始既有影片，不呼叫生成；播放 ended 只追問一次；「回到條件」定位18.3秒；換風格無同題版本時記錄補強需求而非換不相關影片；/ask 使用選定教材；離頁忽略晚回應並停止播放。
- [ ] 先測安全 /trials/coherent/out/coherent.mp4 的HEAD／Range可用，../與symlink不得逃出試片目錄；修前404證明缺少路由。
- [ ] 最小實作：`if path.startswith('/trials/'): return self._file(safe_path(ROOT / 'prototypes' / 'component_trials_20261011', path[len('/trials/'):]))`，把ValueError換APIError404，沿用GET／HEAD及Range；不暴露repo root。

## Task 2: 可操作的清楚介面

Files: workbench/web/js/pages/chat.mjs、workbench/web/chat.css、workbench/web/index.html。

- [ ] 取代原本定時器與固定生成成功訊息，保留舊文件／原始碼於提交cd54f9e；新介面不建立window全域方法、不使用使用者文字innerHTML。
- [ ] 初始直接顯示48秒成片，原生影片控制；明確列「觀念／流程／操作次數」定位按鈕；其他元件示範放收合區，題名標示各自教材，保留原評選頁入口。
- [ ] 對話支持 Enter 送出、Shift+Enter換行、空白不送、送出時防重、API失敗可重試、ended後追問；回覆已理解提供下一段操作。無法定位的問題問一個定位問題。
- [ ] 主標題26px、正文及输入20px、按鈕和選單18px，不加頭像／圖示工具列／多個頂部tabs。桌面影片優先，窄螢幕依序影片→對話，頁面能捲動到輸入區。
- [ ] 換教材清空對话及舊片；預覽影片／章節切換與離頁停止舊播放。新增CSS只作用於teaching-chat，不影響製作、素材庫、簡報、心智圖。

## Task 3: 驗證與文件

Files: docs/TEACHING_VISUAL_CUSTOMIZATION.md、HANDOFF_NOTES.md、docs/superpowers/plans/2026-10-11-workbench-video-chat.md。

- [ ] Node：`/home/pjw92/.local/bin/node --test workbench/web/tests/*.test.mjs`；Python路由：`.venv/bin/python -m unittest tests.test_workbench_server`。新增行為先看紅、實作後看綠。
- [ ] 真實啟動工作台新伺服器（避免中斷8765），在1440／768／375px測真實MP4播放、定位、結束追問、輸入、切樣片、離頁、返回及API；檢查沒有橫向溢出，截圖實看，不發生成請求。
- [ ] 更新文件區分已完成的操作介面／素材庫重用與尚未接入的AI新影片生成，記錄實際測試及試用網址。既有樣片逐幀驗證仍有效，本次不改動畫本體。
- [ ] 完成後交付工作台連結，清楚指出本機checkpoint與後續整合變更的提交狀態。
