# 簡報流程圖與心智圖層次 Implementation Plan

> For agentic workers: execute sequentially in the current authorized feature checkout, using executing-plans and verification-before-completion. Keep the user's active video-generation service running.

**Goal:** 讓正式簡報生成能選用既有 Board pipeline 的階段資料，線上可逐步閱讀、PPTX 保持可編輯；讓新心智圖依教材關係分層，而非所有概念平鋪根節點。

**Architecture:** 延用共同教學規劃，新增 1.1 關係契約，保留 1.0 快取及 Deck 1.0/1.1/1.2 相容。pipeline 只接受有界 stages{id,label,note}，與現有 Board pipeline 共用資料形狀；HTML 和 PPTX 各自渲染，不移植 Canvas 或嵌入成片。模型不得輸出座標、時間、HTML。關係及階段內容仍需原文依據。影片 CLI/runtime 不變。

**Tech Stack:** Python unittest/python-pptx、原生 JS DOM/Node tests、既有 Chrome/Playwright；不新增依賴，不執行付費模型或 TTS。

## 已確認需求與驗收

- 學生自學；教材內容決定元件，不為花俏輪換風格。
- 心智圖整框展開，原始根／兄弟留在原圖；分類名稱及解說分支分開。
- 簡報流程有明確方向、階段名稱與說明，下一步／上一步可還原。
- PPTX 流程使用原生文字、圖形及連線，沒有整頁截圖；每個閱讀階段有對應頁。
- 畫布與工具列緊湊；手機可閱讀／捲動，無頁面橫向溢出。
- 用户自行在 8876 製作影片；驗證資料放隔離素材庫，不修改其教材或工作佇列。

## Task 1：確認使用者製片入口

- [x] 從專案 .env 載入既有金鑰啟動 8876；不得把金鑰輸出或加入 Git。
- [x] 只讀模型 metadata 確認兩個模型可用；Board preflight 通過。
- [x] 真實 API 頁面確認教材輸入、勾選單支影片、生成按鈕可操作；不代按付費生成。

## Task 2：共同元件及關係契約

Files: create `studio/visual_components.py`, `tests/test_shared_visual_components.py`; modify `studio/deck_contracts.py`, `studio/teaching_plan.py`.

- [x] 先寫測試：pipeline stage ID 唯一、數量 2–5、拒絕額外欄位；新版關係缺父、循環、無原文引用均拒絕；舊計畫仍可轉換。
- [x] 執行 `.venv/bin/python -m unittest tests.test_shared_visual_components`，確認未實作時失敗。
- [x] 實作 `pipeline_object(block, object_id)` 回傳 `{id,type:'pipeline',stages}`，沿用 Board stages 語意；Deck1.2 及新共同規劃可使用 pipeline。
- [x] 新計畫 1.1 的 unit 增加 concept_label/parent_id/relation/relation_quote；分類名稱與簡報標題分開，所有概念必須沿 parent_id 回到 root；mindmap adapter 保留父子關係及關係引用。
- [x] 同一測試通過，執行既有 teaching/deck/mindmap/runner 測試，確認相容。

## Task 3：簡報 HTML 與 PPTX

Files: modify `studio/pptx_export.py`, `workbench/web/js/viewers/deck.mjs`, `workbench/web/styles.css`, `workbench/web/tests/deck-learning.test.mjs`.

- [x] 測試 pipeline 的前後閱讀狀態、文字安全、鍵盤閱讀與 PPTX 原生文字／連線／階段頁；先看失敗。
- [x] HTML 用有序流程卡、方向箭頭及既有 stepControls；選定階段高亮，狀態回退可還原。
- [x] PPTX 各階段匯出一頁，原生圖形及連線；超過最低可讀容量明確失敗，不縮成小字。
- [x] 心智圖工具列／節點及新版線上簡報字級內距縮小，保留全框操作與拖曳。
- [x] Node tests 與相關 Python tests 通過。

## Task 4：真實端到端與交接

- [x] 固定 C 教材人工基準產生新版計畫、deck.json、可編輯 PPTX、mindmap SVG；放隔離預覽庫，不冒充 AI 成品。
- [x] 真實瀏覽器 1440/375px 驗證流程前後步、兩層心智圖展開、兄弟位置不变、布局切換、下載及無溢出；保存截图。
- [x] 更新 HANDOFF_NOTES.md／CONTINUE_WORKBENCH.md，明列本批新增及仍未整合的六種樣片風格。
- [x] 本機 commit，未授權不 push；8876 不重啟，不影響使用者生成。

## 使用者試生失敗後的修正與驗證

- [x] 核對正式q4工作log：共同教學規劃失敗，未到配音與出片。
- [x] Google SDK回歸重現未送出schema，修正response_json_schema；保留預算與契約閘。
- [x] 製作頁先顯示狀態、原因與佇列，縮小字級及元件；失敗優先只選該項目。
- [x] Chrome四種視窗驗證第一屏佇列可見、選擇可捲動、文字有對比，無POST生成及page error。
- [x] 全套Python790項（1 skip）、Node101項通過。

尚未完成：使用者q4修正後的真實付費重試與完整成片驗證。未留存舊模型回應，確切違反哪個欄位無法重建。
