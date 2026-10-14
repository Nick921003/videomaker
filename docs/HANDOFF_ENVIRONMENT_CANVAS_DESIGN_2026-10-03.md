# Claude Opus 5.5：環境建立教學樣片交接

以下可直接交給使用者的Claude工作階段。工作目錄`/home/pjw92/projects/videomaker`，先讀`CLAUDE.md`與使用者提供的AGENTS規則。保留dirty worktree，不commit/push。

## 任務

讀取教材`/mnt/c/Users/pjw92/Desktop/計概課程資料/環境建立.md`，題為「從安裝到執行：VS Code + GCC 的第一支 C 程式」。它包含編輯器／編譯器差異、GCC安裝、PATH搜尋／設定／驗證、編譯階段與撰寫→編譯→執行循環。

先設計30秒「PATH為什麼讓gcc指令可被找到」的連續教學分鏡，供使用者看過再製作；不要立刻生成整支3–5分鐘影片。

參照：

- 使用者第一次接受的`video_engine/out/state_change_ac_20261001/c_string_ac.mp4`及同目錄`movie.html`。重要的是同一主角持續改變、來源／結果關係、掃描／停止、語句節奏，而非把所有場景做成卡片列表。
- 目前兩元件HTML樣片`video_engine/out/html_canvas_sample_20261003/scene.html`、`scene.js`、`timings.json`及`REPORT.md`。CodeWalkthrough、TerminalOutput只是一段原型，不是完整已完成元件庫。
- `docs/experiments/2026-10-03-rendering-architecture-evaluation.md`。

## 分工與交付

Claude負責教學敘事、視覺分鏡、before→action→after的因果，建議元件與必要的特殊動作。Codex負責可重用元件接口、字型／布局量測、連線與時間、瀏覽器匯出及驗收。不限制你只作分類或全部套四種基本方塊；特殊場景可以提出新元件，解釋為什麼現有元件不夠。

交付指定Markdown：`docs/experiments/2026-10-03-environment-path-storyboard.md`。每個鏡頭包含：

1. 原文依據／教學目的。
2. 自然旁白、字幕原文與必要的spoken別名。
3. 畫面之前的狀態、主要動作、之後留下的狀態。
4. 同一終端機與PATH資料夾清單如何持續；節點／文字的語意ID，來源與目的關係。
5. 動作對哪一句／詞的語意cue。先給相對節奏，不假裝有未生成語音的實測時間。
6. 需要哪些可重用元件；已具備哪些、尚需新增哪些。

建議故事：輸入gcc指令→沿PATH依序尋找→找不到→加入GCC所在資料夾→重開終端機→重新搜尋找到→顯示驗證結果。原文版本輸出只能標為教材示例，不當作使用者本機實際結果。

## 約束

- 本輪交付分鏡與設計；不呼叫新的付費LLM API/TTS，不重做聲音克隆，不替使用者安裝GCC或改PATH。
- 不修改現有pipeline、共用theme、schema或使用者檔案。要試HTML僅在新isolated原型目錄，先交設計文件與內容範圍。
- 分鏡內容只寫語意關係；像素與字體量測在後續幾何層實作。箭頭必須依當前物件錨點重算，不能用彼此無關的位置常數。
- `seek(t)`須純粹由t決定，動畫完成後線條穩定，文字不持續抖動。音訊定稿後再做實測cue；字元比例僅為初估。
- 用最少必要元件說清楚過程；核心動作不能被程式提示、字幕或轉場遮住。不把技術測試通過當作使用者已接受美感。

最後回報文件路徑、分鏡總長估值、需要新增元件清單與未決問題。指定Markdown文件是交付物，摘要不能取代。
