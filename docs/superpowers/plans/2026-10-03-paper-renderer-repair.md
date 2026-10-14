# Paper Renderer Repair Implementation Plan

> **For agentic workers:** Inline execution after plan review. Steps use checkbox tracking. User has authorized the implementation and rerender; no commit or paid generation.

**Goal:** 修復紙上渲染器的文字混疊、識別字拆字和提示生命週期，沿用既有素材重新輸出C語法影片。

**Architecture:** 原位值更新共用短退場／進場時間，明確跨物件transfer保留原有曲線。排字先以詞為單位，cells格寬與必要字級用實測詞寬計算。提示持續時間由最近code focus的實測step音長決定。所有驗收來自實際渲染與編碼畫面。

**Tech Stack:** 現有Python、Pillow、NumPy、FFmpeg、unittest；不新增依賴。

**Spec:** `docs/superpowers/specs/2026-10-03-paper-renderer-repair.md`

## Task 1：先建立失敗證據

- [x] 在`tests/test_paper_ac_renderer.py`新增實際文字繪製追蹤：合法三場景值更新時，同一格不得同時畫舊字與新字。
- [x] 在同檔新增cells識別字排字檢查：讀`render_previews`產出的layout，重建同一排字，`#include`／`main()`／`printf()`／`return`不得被拆斷。
- [x] 新增長code focus的提示測試：8秒step在6秒仍可見；進入data step後短過渡退場，且reserve必須涵蓋整個可見期間。
- [x] 執行`.venv/bin/python -m unittest tests.test_paper_ac_renderer`，確認新增測試因原問題失敗。

## Task 2：最小渲染修復

- [x] 修改`paper_renderer.py`的局部更新：測量並追蹤原位新字；舊字先退至紙面，新字接著進場；整段音長不再把局部變字拖成數秒。明確來源transfer與逐格scan使用既有路徑語意。
- [x] `_wrap`以Latin識別字／數字／中文字元為單位排字；cells可依實測詞寬擴寬到欄位可用上限，再必要縮小字級，無法容納時保留既有超長文字的明確處理。
- [x] 提示在code step結束後再開始短退場，兩個生命週期helper共用同一計算，資料不提前回中央。
- [x] 更新與新生命週期衝突的舊測試，保留真正來源transfer、scan停止、seek、長文字量測、淡出避讓的正反控制。
- [x] 執行`.venv/bin/python -m unittest tests.test_paper_ac_renderer tests.test_paper_renderer tests.test_paper_video tests.test_paper_http`。

## Task 3：同素材重新輸出及驗收

- [x] 建立`video_engine/out/c_syntax_renderer_fixed_20261003/`，複製既有board/timeline/字幕，硬連結既有master.wav；記錄SHA256，禁止新LLM/TTS呼叫。
- [x] 渲染預覽並輸出新的1080p MP4；保留舊片。抽取99.79秒、98.5秒、code focus中後段及兩個場景過渡的實際編碼畫面。
- [x] 執行全套`.venv/bin/python -m unittest discover -s tests -t .`、`git diff --check`；檢查整片解碼、精確幀差、文字混疊、字詞完整、提示及資料空間避讓。
- [x] 啟動完成產物的預覽入口；驗證播放器載入／播放、Range下載及桌面手機無水平溢出。
- [x] 保存修復時間／成本／測試與產物報告，交付新預覽與影片；更新設計狀態，視覺風格保留使用者驗收。

## Review注意點

局部更新和真正transfer必須分開測；不同字寬的多行文字不能在到達後跳位。提示延長會讓資料在右側停留更久，須實圖確認長資料的可讀字級與邊界。不能用新renderer自行比對自己就宣稱內容正確，需獨立檢查繪字呼叫與識別字。SHA256防止旁白、字幕或分鏡被不必要重建。


完成證據：`video_engine/out/c_syntax_renderer_fixed_20261003/REPORT.md`。新增首次顯示／短段落與重現物件邊界控制；詞彙排字僅限定cells避免破壞scan prefix落點。451項全套測試450通過／1略過。原位更新與真正transfer已分離，transfer目的格舊字立即清空的細節記於報告。無新模型／TTS呼叫。
