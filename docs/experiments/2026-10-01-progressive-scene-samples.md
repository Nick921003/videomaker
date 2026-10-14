# C 字串四場景 HTML 三樣本紀錄（2026-10-01）

## 範圍與來源

本輪以同一份 C 字串教材、既有 Gemini 整理與已接受的口語字幕，製作可比較的 44 秒無聲 HTML。使用者提供的是咖啡動畫的文字 prompt，未提供原影片；本輪只能依文字規格設計，不能宣稱分析過原影片的畫格、鏡頭或動作。

產物目錄為 `video_engine/out/state_change_scenes_20261001/`；HTML 為 `scene_samples.html`。A「紙上連續」、B「聚焦」、C「概念程式」是本機 Canvas 的三種實作方向，共用同一次 Claude 四場景分鏡；不是三個獨立 Claude 產出。HTML 與 JavaScript 的具體實作亦不等同於 Claude 原始 JSON。

本輪禁止 TTS；字幕與視覺事件採人工試排，不代表語音同步或聽感已通過驗收。本原型沒有接入正式八階段管線或 Studio；本機樣本製作與紀錄整理不另增模型呼叫，未安裝依賴、commit 或 push。

## 分鏡規範與實作

真實分鏡回應、request、usage 與解析後 JSON 分別為 `claude_response.json`、`claude_request.json`、`claude_usage.json`、`scenes.json`。模型實際回應為 `claude-opus-5-5`，一次呼叫，`stop_reason=end_turn`。

| 場景 | 時間 | Claude 分鏡的教學目的 |
| --- | --- | --- |
| hook | 0–7 秒 | 提出容量 32、長度 5 的差異 |
| formation | 7–16 秒 | 同一陣列前六格形成 `Alice` 與 NUL，尾端未知 |
| read_stop | 16–31 秒 | 輸出形成 `A → Al → Ali → Alic → Alice`，於索引 5 停止 |
| comparison | 31–44 秒 | 比較容量 32、長度 5、最少 6 格 |

`scenes.json` 的格紙、鉛筆顯現、配色、物件顯示／隱藏與鏡頭焦點是分鏡規範。A/B/C 是否具體符合各項規範，以實際 HTML 與瀏覽器驗收為準；不得只因 JSON 有記載就宣稱已實作。三樣本的比較目的如下，已完成實際瀏覽器驗收。

| 樣本 | 實作方向 | 驗收狀態 |
| --- | --- | --- |
| A 紙上連續 | 以連續紙面承接概念與物件狀態 | 通過 |
| B 聚焦 | 依場景集中注意力與可見資訊 | 通過 |
| C 概念程式 | 以概念狀態配合程式提示 | 通過 |

上述讀取是教學概念示意，不宣稱標準函式的底層實作必然逐位元組操作。NUL 不進入輸出；未知尾端不應被動畫讀取。未提供咖啡原影片，也未驗證學生理解成效。

## 真實 tokens 核算

| 呼叫 | Input | Output | Thinking | 合計 | 本輪素材歸屬 |
| --- | ---: | ---: | ---: | ---: | --- |
| Gemini 教材整理 | 779 | 805 | 513，另加 | 2,097 | 重用 |
| Claude 首版分鏡，截斷 | 2,891 | 6,000 | 1,954，已含於 output | 8,891 | 不計入本輪素材歸屬，保留於歷史累計 |
| Claude 首版分鏡，重試 | 2,891 | 6,434 | 2,466，已含於 output | 9,325 | 不計入本輪素材歸屬，保留於歷史累計 |
| Claude 口語稿 | 1,423 | 2,372 | 1,866，已含於 output | 3,795 | 重用 |
| Claude 本輪四場景分鏡 | 3,540 | 4,405 | 957，已含於 output | 7,945 | 本輪新增 |

- 本輪實際新增：**1 次外部模型呼叫，7,945 tokens；TTS 0 次**。三個 Canvas 樣本共用該次分鏡，不乘以三。
- 單支 HTML 素材歸屬核算：**2,097 + 3,795 + 7,945 = 13,837 tokens**。此值包含已重用素材，不是本輪實際新發生費用，也不是任何影片的固定用量。
- 本系列歷史累計：**24,108 + 7,945 = 32,053 tokens**，包含早期截斷與重試。

Gemini thinking 需另加；Claude thinking 已含在 output，不能再加一次。這是供應商 usage 的 tokens 統計，未換算貨幣費用，亦不包含無供應商 usage 可讀的 Codex 對話用量。

原始證據是前兩輪 `gemini_usage.json`、`token_usage.json`、`claude_usage.json` 與本輪 `claude_usage.json`；完整五次呼叫、三種核算與證據 SHA256 見本輪 `token_ledger_detailed.json`。既有 `token_summary.json` 的三個合計與原始 usage 相符。

## 驗收紀錄

- 已以 JSON parser 重算原始呼叫與三種合計；確認 thinking 沒有重複加算。
- 已核對 `scenes.json` 共有四場景，時間連續為 0–7–16–31–44 秒。
- 獨立子代理透過既有Chrome與CDP完成113項檢查，0失敗：三模式的任意seek像素決定性、正反向seek、NUL停止、播放控制、切換模式保留時間、字幕及375px/desktop無頁面溢出。
- 初版游標遮標籤、overview過場數字裁切及提前出現半個輸出框皆已修正；視覺框抽樣由266筆問題降至0。保留初版與修正版PNG；詳見 `browser_qa/browser_checks.json`。
- 主代理核對HTML SHA256與子代理報告一致，檢視實際Canvas截圖；全套unittest 337項通過（1略過），git diff --check通過。
- Windows PowerShell Test-Path回傳True；HTML 28,321 bytes，所有CSS/JS/教材資料內嵌。WindowsUNC路徑為 `\\wsl.localhost\Ubuntu\home\pjw92\projects\videomaker\video_engine\out\state_change_scenes_20261001\scene_samples.html`。
- TTS 與語音同步：未執行，依本輪限制維持無聲。

三樣本已完成上述技術與實際畫格檢查；尚未做學生理解成效驗證。375px畫面雖無溢出，但字體隨Canvas縮小，手機閱讀便利性仍待調整。A沿長紙連續移動，B以聚焦畫面切換，C以程式提示過渡到資料狀態；三者並不都採用咖啡規格的每一項細節。
