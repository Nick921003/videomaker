# 期望片長範圍與環境建立影片 Implementation Plan

Goal: 紙上動畫測試頁可輸入最短／最長分鐘，以環境建立.md完成約3–5分鐘有聲影片，交付耗時與費用證據。
Architecture: 使用閉合duration_range {min_seconds,max_seconds}，測試規劃保存range與中位duration_seconds；PaperVideoJob將range傳入分鏡請求。實測語音決定片長，目標範圍不以空白湊長。無range請求保持現有行為，普通入口拒絕range。
Tech Stack: 現有Python unittest、原生ES modules／node:test、Pillow、FFmpeg、GPT-SoVITS與既有模型SDK；不新增依賴，不commit。

- [x] 先加Python和JS測試：180–300秒完整傳遞、非法反向／bool／NaN／超界拒絕、改range使舊plan失效、舊60秒行為保持。
- [x] studio/contracts.py加可選閉合range；PaperTestPlannerBackend回duration_range，紙上capability加可選object型別驗證（不放寬其他能力）。serve.py傳range到PaperVideoJob；build_paper_board保存range到JSON請求與自然講稿指示。
- [x] 測試HTML加入有label的min/max number（分鐘、0.5–10、step0.5、預設3/5）；state/api/app傳秒數，前後端驗证；render顯示範圍，修改任何端點清plan。沿用既有樣式。
- [x] 執行focused tests與全套回歸、ES語法／diff檢查、實際瀏覽器欄位與非法範圍驗收。
- [x] 保存來源hash與開始UTC；讀教材、核對官方GCC/MSYS2/VSCode資料及模型價格；啟動現有TTS（必要log/cache在repo或/tmp），只做授權產片所需呼叫。
- [x] Gemini教材整理＋Claude分鏡，每次API保存真實usage、耗時與候選回應；無自動付費重試。旁白自然中文，重點工具分工／PATH／存檔編譯執行，安裝畫面為示意。
- [x] 本機TTS保存每次文本hash與WAV、耗時，復用已完成段。品質不合格先診斷，確定性靜音修剪可保留原音。編譯音訊量測片長，渲染1080p有聲MP4。
- [x] FFprobe、全片解碼、實際抽幀、程式語意與ASR核對，保存REPORT.md及ledger（API估價非實扣、TTS本機無API費、排除電費／Codex對話）；交付Windows UNC與預覽。


執行差異：Gemini整理JSON無法解析，Claude首次截斷且重試回傳相同response ID；沒有追加付費呼叫，改由本機依原教材補齊後四場。片長用本機語音量測並調整語速，末兩段經ASR發現漏句後重製。完整串接與TTS自動化仍未驗收，詳見環境建立試片報告。
