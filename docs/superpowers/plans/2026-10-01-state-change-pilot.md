# 概念狀態變化試片實作與驗收

目標：以現有 C 字串教材製作 30–60 秒、有旁白且可由 Windows 開啟的 MP4；學生看見同一個讀取游標、字元陣列及逐步形成的輸出。

範圍：獨立 `prototypes/state_change_pilot/`；正式八階段管線與所有現有未提交工作保留。Pillow、NumPy、SciPy、FFmpeg 沿用現有環境，不新增依賴。

- [x] 核對整理器及快取：現有 Gemini ingest 產生逐頁 clean_text、verified_quotes、visual_notes、uncertainties；查找實際整理稿，不將 lesson JSON 當成 Gemini 整理證據。
- [x] 無可重用整理稿時，實際呼叫現有 Gemini 3.8 Flash 整理器一次，保存來源 hash、原始 JSON、驗證後 Markdown 與用量；禁止自動付費重試。
- [x] 實際呼叫 Anthropic Claude 一次，要求逐段旁白、學生看見的狀態、因果、來源行號、初始與最終狀態；保存 request、response、回應 model 及 usage。不將本機手寫文字標成 Claude 生成。
- [x] 依現有 actions schema 核對執行能力；原型只加入這個概念必要的 copy / scan / append / stop 視覺，不擴充正式 schema。
- [x] 先檢查 TTS 啟動設定與現有服務，使用現有聲線。每段 TTS 實測長度、靜音及峰值；時間軸依 WAV 實際長度建立，逐字步驟拆成短語音段同步。
- [x] 以測試驗證讀取遇到 NUL 停止、尾端未知資料不讀、容量與字串長度分開。保留未定義行為的正確說明，不照抄原教材過度概括的錯誤。
- [x] 生成 1280×720 / 24 fps MP4、全片 GIF、重要狀態 PNG 與來源/分鏡紀錄；FFprobe、解碼及實際影格檢查。報告同步驗證的精度及尚未接入正式流程之處。

風格：整支影片固定 explainer theme、Noto Sans CJK TC、相同物件版位及平滑游標位移。參考使用者描述的「同一主角、連續過程、狀態變化」，沒有取得咖啡影片本體，因此不宣稱做過參考影片逐格分析。

驗收：C 編譯執行結果為 Alice / 5 / 32；動畫停止時游標停在索引 5，輸出沒有 NUL、沒有索引 6 以後內容；所有段落以實測音長排程，重要動作與對應短句共享起點；檢查中間狀態而非只看結尾。
