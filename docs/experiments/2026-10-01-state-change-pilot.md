# 概念狀態變化教學試片：製作與驗收紀錄（2026-10-01）

## 交付與範圍

C 字串試片，57.90 秒，1280×720，24 fps。同一個 name[32] 陣列、讀取游標及輸出面板，連續呈現未初始化、複製、逐格讀取、形成 Alice、遇到 NUL 停止。

Windows MP4：`\\wsl.localhost\Ubuntu\home\pjw92\projects\videomaker\video_engine\out\state_change_pilot_20261001\state_change_pilot.mp4`

MP4、preview.gif、contact_sheet.png、原始模型回應、tokens 用量與音檔均在同一產物目錄。Windows PowerShell Test-Path 已回傳 True；最終編碼與解碼結果見 delivery_verification.json。

此為獨立 Pillow 狀態動畫原型；正式八階段流程、Studio API、網頁均未接入。不使用 image-to-video 模型，也沒有宣稱分析過未提供的咖啡影片。正式 actions schema 只有 speech、spotlight、laser、reveal、camera、pause，缺少持續資料改寫及輸出累積的狀態動作。沒有大幅改動正式架構或新增依賴。

## 實際分工與來源

1. 讀取 `video_engine/materials/c_string.md`，保留來源 SHA256（source_manifest.json）。查核 repo materials、out 與 /tmp 未找到此教材可重用的 Gemini 整理產物；既有 lesson/actions/audio 不能當成 Gemini 整理證據。
2. 沿用 `studio/material_normalizer.py` 的 SYSTEM、normalize_material 與引文驗證。實際呼叫 Gemini 3.8 Flash；原始 JSON 為 title/pages，每頁 clean_text、verified_quotes、visual_notes、uncertainties；驗證後保存 normalized.md。此稿已涵蓋核心概念與 Alice 範例，引文均可對回教材。
3. Gemini 只整理教材，動畫初始／逐步／最終狀態與因果由 Claude 分鏡。原型呼叫提示詞限制可渲染的階段與範例，Claude 產生 before、after、cause、student_sees、speech 及 source_lines/source_quote；不宣稱 Claude 自主選擇了整個題目或本機程式能理解任意分鏡。
4. 實際回應模型為 `claude-opus-5-5`，保留完整 request/response。第一次 max_tokens=6000 截斷，未拿不完整 JSON 出片；使用者授權後重試一次，上限 12000。第二次 10 段通過狀態與來源驗證。
5. 本機 GPT-SoVITS 王老師 3.0 合成旁白。第一版字母 l 段雖通過音長/靜音檢查，但兩個 ASR 模型無法還原；經使用者要求重做與驗證，先試字母發音提示，再將五段 TTS 旁白修訂成中文指涉字母。Claude 原稿、第一版與發音提示版音檔皆保留。字幕顯示最終旁白，而字元格仍是正確的 A l i c e。
6. 確認為靜音的句內長停頓縮短至0.32秒，保留未修整 WAV；全部20次為本機TTS，無新增付費LLM呼叫。

## 原教材需要核對之處

原稿將無終止符的讀取概括成必然亂碼、把陣列指定與位址指定混在一起，並稱字串位址比較永遠不相等。Gemini 依整理契約保留原文，這不等於內容已經過學科審查；本片聚焦可核實範例，未修改原教材。

語意依據為 [WG14 C11 draft N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)：7.24.2.3 strcpy 複製含 NUL；7.24.6.3 strlen 計算 NUL 前字元；7.21.6.1 的無精度 %s 輸出不含 NUL。動畫呈現概念行為，不保證標準函式在機器層級逐位元組讀取或輸出。`printf("%s", name)` 是原範例的簡化衍生示範，畫面明示。

## 最終分鏡

每段完整的 before/after/cause/學生視角與逐字引文見 storyboard.json；以下使用最終音長時間。

| 時間 | 狀態／學生看見的變化 | 最終旁白 | 教材行號 |
| --- | --- | --- | --- |
| 0.00–6.22s | setup：name[32] 出現，32 格全部未知。 | 先宣告字元陣列 name，共有三十二格，現在每格的內容都還未知。 | 26 |
| 6.22–13.46s | copy：索引 0..5 為 A l i c e \0；索引 6..31 仍未知。 | 接著用字串複製，把愛麗絲五個字母和結束字元一起放進前六格，索引六以後仍未知。 | 27 |
| 13.46–19.80s | scan：游標在索引 0；輸出 A；已輸出字元 1。 | 游標移到第零格，讀到這個字母，送進輸出，畫面先出現一個字母。 | 28 |
| 19.80–24.76s | scan：游標在索引 1；輸出 Al；已輸出字元 2。 | 往前一格到第一格，讀到這個字母，接在後面，輸出又多一個字母。 | 28 |
| 24.76–29.50s | scan：游標在索引 2；輸出 Ali；已輸出字元 3。 | 再前進到第二格，讀到這個字母，輸出又多一個字母。 | 28 |
| 29.50–33.76s | scan：游標在索引 3；輸出 Alic；已輸出字元 4。 | 前進到第三格，讀到這個字母，輸出又多一個字母。 | 28 |
| 33.76–39.06s | scan：游標在索引 4；輸出 Alice；已輸出字元 5。 | 前進到第四格，讀到這個字母，輸出完整拼成愛麗絲。 | 28 |
| 39.06–45.24s | stop：游標停在索引 5；輸出 Alice；已輸出字元 5。 | 第五格是結束字元，讀到它就停止，不印出它，也不去讀後面的未知格。 | 16 |
| 45.24–52.54s | summary：畫面加上容量、長度、最少格數三張標籤。 | 容量是三十二格，長度是五，存五個字母至少要六格，多出的一格留給結束字元。 | 17 |
| 52.54–57.90s | question：畫面加上問題與答案。 | 小問題：結束字元算在長度裡嗎？答案是不算，所以長度是五。 | 18 |

## Tokens 與呼叫紀錄

| 呼叫 | 實際模型 | Input | Output | Thinking | 合計 |
| --- | --- | ---: | ---: | ---: | ---: |
| Gemini 教材整理 第1次（complete） | gemini-3.8-flash | 779 | 805 | 513 | 2097 |
| Claude 分鏡 第1次（max_tokens） | claude-opus-5-5 | 2891 | 6000 | 1954 | 8891 |
| Claude 分鏡 第2次（complete） | claude-opus-5-5 | 2891 | 6434 | 2466 | 9325 |

外部模型累計 **20,313 tokens**，包含失敗與已授權重試。Gemini 的 thinking 另加，Claude 的 thinking 已包含在 output，沒有重複相加。第一份 claude_usage 舊註解稱 SDK 未獨立回報思考量不正確；彙總直接使用原始 output_tokens_details.thinking_tokens。此統計不包含無 usage 可讀的 Codex 對話本身。TTS 20次與所有 Whisper 分析均為本機執行，另外保存於 tts_call_ledger.json。

## 驗證與限制

- 全套既有 unittest：337項，1項略過；原型狀態測試：4項通過。git diff --check 通過。沒有修改原本的未提交程式檔，也未 commit/push。
- C11 編譯（-Wall -Wextra -Werror）與執行：Alice 共 5 個字；length=5 capacity=32 nul_index=5。未讀取未初始化尾端來驗證內容。
- 檢查20張原型影格：未知尾端像素相同、5次輸出變化存在、文字框未越界；檢視實際MP4擷取的初始、複製、中間前綴、停止、摘要及問答影格。
- 以既有 cached Whisper large-v3 在CPU逐WAV辨識，取得每段語句；使用「讀到」「輸出／多一個字母」「停止」「不算」詞時間排程。5次輸出與停止的同步紀錄見 sync_checks.json，成品畫格誤差由24fps限制至41.7ms以內（相對ASR錨點）。
- ASR仍有同音字、變量名稱及簡繁字誤辨；它用於確認整段存在及時間錨點，不能當逐音素發音認證，也未做學生理解成效或人工聽感驗收。
- 此原型的array/copy/scan/append/stop尚未成為正式lesson/actions契約。若要接入正式產品，需另提語意狀態契約、量測框及時間同步方案。

詳細驗證、媒體hash與畫格檢查結果會隨成品保存在同一目錄，供重現與交接。
