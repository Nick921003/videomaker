# 設計：現場 Demo 前端（含 pptx 輸入）

日期：2026-08-26
狀態：已核可，待實作計畫

## 背景

引擎目前只有 CLI：`run.py <教材.md> --sec 110`，八階段跑完約 167 秒出片。
要在現場對著人展示「教材進去、影片出來」，CLI 有三個問題：

1. 終端機畫面沒有說服力，觀眾看不出引擎在做什麼
2. 167 秒的等待是純冷場
3. 講稿是 LLM 寫的，現場看到問題也來不及改——只能等它跑完

## 目標

一個本機工具：丟一份 `.md` 或 `.pptx`，看著八階段跑，中途確認或修改講稿，拿到 MP4。

**成功條件**：現場丟一份沒看過的 `.pptx`，三分鐘內拿到可播放的教學影片，
過程中觀眾看得出每個階段在做什麼，且講稿有一次人為確認的機會。

## 非目標（YAGNI）

登入、多使用者、排隊、部署、Docker、PDF、`.ppt` 舊版二進位格式、
重生某一頁、線上播放器。這些都不是現場 Demo 需要的，做了就是提前付款。

## 架構

```
瀏覽器（單頁 HTML）
   │ POST /jobs                multipart 上傳教材
   │ GET  /jobs/{id}/events    SSE 進度串流
   │ POST /jobs/{id}/approve   帶編輯後的講稿
   │ GET  /jobs/{id}/video     下載 MP4
   ▼
serve.py            stdlib http.server，只管 HTTP 與 job 狀態機
   ▼ subprocess
run.py              既有八階段，靠 --from / --until 切成兩段呼叫
```

核心決定：**前端薄到幾乎沒有自己的邏輯**。所有影片知識留在引擎裡，
服務層只是呼叫兩次既有 CLI、讀 stdout 推 SSE。出錯面小，現場最不會翻車。

服務層零新增依賴（`http.server` 是 stdlib），前端零建置步驟。
整個 spec 只新增一個執行期依賴：`python-pptx`，而且只有讀 `.pptx` 時才會用到。
這跟專案原本「不含 torch／gradio，依賴很省」的調性一致。

## 元件與職責

| 檔案 | 動作 | 職責 | 依賴 |
| :--- | :--- | :--- | :--- |
| `video_engine/ingest.py` | 新增 | `extract_text(path) -> str`：`.md`／`.txt` 直讀，`.pptx` 抽每頁文字與講者備忘稿。只有這一個公開函式 | `python-pptx` |
| `video_engine/run.py` | 改 | ① 教材走 `ingest.extract_text`；非 `.md` 先落地成 `materials/<stem>.md` 保留可追溯 ② 新增 `--json-events`，每階段起訖印一行 JSON 到 stderr（人看的輸出不變）③ `storyboard` 階段從 `synth` 後移到 `validate` 後 | ingest |
| `serve.py` | 新增 | HTTP 端點與 job 狀態機。**不含任何影片邏輯** | stdlib、run.py（subprocess）、validate.py（import） |
| `web/index.html` | 新增 | 單頁：流程動畫、SSE 訂閱、講稿編輯器、倒數。無建置步驟、無外部資源 | 無 |
| `video_engine/storyboard.py` | 不動 | `durations.json` 已經是選用的（`storyboard.py:46`），本來就能在語音合成前產出 | — |

### 為什麼 storyboard 可以往前移

`storyboard.py:46` 是 `json.load(...) if os.path.exists(dur_path) else {}`。
音檔時長只影響分鏡表上的秒數欄位，沒有它照樣產得出來。
把審稿閘放在 TTS **之前**，改講稿的代價從「重跑 TTS 51 秒」降到零。

### 檔案落地與命名

上傳的檔案存進 `video_engine/materials/`。非 `.md` 的來源先抽成純文字再落地成
`<stem>.md`，保留可追溯——現場如果出片有問題，手上就有引擎實際讀到的文字。

`lesson_id` 沿用 `run.py` 既有規則（檔名去副檔名、非 `[a-z0-9_]` 換成底線），
產出一律進既有的 `video_engine/out/<lesson_id>/`。

**同名處理**：`materials/` 已存在同名檔時加序號（`c_string_2.md`），不覆寫。
產出目錄則沿用該 `lesson_id`，同名即覆蓋——產出是可重生的，教材不是。

## HTTP 介面契約

| 方法 | 路徑 | 請求 | 回應 |
| :--- | :--- | :--- | :--- |
| POST | `/jobs` | multipart：`file`、`sec`（目標秒數，選用，預設 110） | `201 {job_id}`；忙碌中回 `409`；TTS 未就緒回 `503` |
| GET | `/jobs/{id}/events` | — | SSE，每則 `{stage, status, pct, msg}` |
| GET | `/jobs/{id}/script` | — | `{segments: [{slide_id, idx, text}]}` |
| POST | `/jobs/{id}/approve` | `{segments: [...]}`（未修改則傳空陣列） | `200 {ok}` 或 `400 {errors: [...]}` |
| GET | `/jobs/{id}/video` | — | `video/mp4` |

## Job 狀態機

```
queued
  → lesson → slides → actions → validate
  → awaiting_review ─┬─ approve 或 60 秒超時 ──→ synth
                     └─ 有編輯 → 回寫 actions.json → 重跑 validate
                                  ├─ 通過 → synth
                                  └─ 有 ERROR → 推回前端，倒數重置一次；
                                                 再錯就用原稿繼續
  → timeline → video → done
任何階段非零退出 → failed
```

## 審稿閘

- 進入 `awaiting_review` 時，服務層從 `actions.json` 抽出所有 `speech` 動作的
  `text`，附上所屬 `slide_id` 與索引交給前端
- 前端逐段顯示、可編輯，**畫面上有 60 秒倒數**
- 倒數歸零等同核可，且**畫面要明講「沒人反對就繼續」**——不然「確認過」是假的
- 送出時若有修改：回寫 `actions.json` → 重跑 `validate.py`
- 重跑驗證是硬需求：現場很容易改出唸函式名（`strcpy`）、全大寫縮寫這類
  TTS 會出事的稿。驗證閘本來就擋這些，回寫後不重跑等於把閘關掉
- 重驗失敗最多重來一次，之後一律用原稿繼續。**現場不能卡死**

## 進度權重

等寬八格會騙人——卡在第一格不動半分鐘。權重照實測配。

實測條件：`c_string.md`（810 字）→ 5 頁 98 秒影片，
`lesson` 用 `anthropic:claude-opus-5`、`actions` 用 `google:gemini-3.7-flash`，
總計 167 秒。

| 階段 | 實測 | 權重 |
| :--- | ---: | ---: |
| lesson 教材結構化（LLM） | 41s | 25% |
| slides 投影片繪製與量測 | 1s | 1% |
| actions 動作編排（LLM） | 32s | 19% |
| validate、storyboard、timeline | 合計 0s | 1% |
| **審稿閘** | 0–60s | 人的時間，進度條不算 |
| synth 語音合成 | 51s | 30% |
| video 影格渲染與封裝 | 42s | 24% |

（合計 100%。三個瞬間完成的階段合成一列，各自佔一格會讓進度條抖動。）

階段內的百分比由 `run.py --json-events` 的階段起訖事件插值，
渲染階段另有既有的 `%` 輸出可直接用。

## 視覺規範

介面配色**直接沿用 `video_engine/themes/warm.json`**，不另立一套。
投影片與介面是同一個世界，暖色底對眼睛也比純白背景舒服。

| 用途 | 色票 | 來源 |
| :--- | :--- | :--- |
| 頁面底色 | `#F4EDE2` | `canvas.bg` |
| 卡片／面板 | `#FBF7F0`，邊 `#DFD2BF` | `card.fill` / `card.edge` |
| 主要文字 | `#3B322A` | `text.title` |
| 次要文字 | `#4B4238` | `text.bullet` |
| 強調／進行中 | `#B85C38` | `text.callout` |
| 已完成標記 | `#A0673F` | `text.subtitle` |
| 講稿編輯區底 | `#EFE6D8`，邊 `#DCCDB6` | `code.bg` / `code.edge` |
| 倒數警示 | `#F2D9A0` 底 + `#B85C38` 字 | `effects.highlight` |

硬約束：

- **不用純白 `#FFF` 或純黑 `#000`**，一律走上表色票
- 不引入任何外部字型、CSS 框架、CDN 資源——單一 HTML 檔，離線可跑
- 不做深色模式（現場投影用暖色亮底，YAGNI）
- 流程動畫用 CSS，不引 JS 動畫函式庫
- 進行中的階段用 `#B85C38` 標示，已完成用 `#A0673F`，未開始用 `#DFD2BF`

實作依專案慣例委派 AGY：Claude 定邊界（上表色票、硬約束、驗收標準），
AGY 實作 HTML/CSS，Claude 驗邏輯，視覺交使用者確認。

## 錯誤處理

| 情境 | 處理 |
| :--- | :--- |
| GPT-SoVITS 未啟動 | **收件前先探測 `:9880`**，沒回應直接 `503` 並說明。這是現場最常見的翻車點，不能等跑到第五階段才炸 |
| 副檔名不在白名單 | `400`。白名單：`.md`／`.txt`／`.pptx` |
| 檔案過大 | `413`，上限 5 MB |
| 已有 job 在跑 | `409`。LLM、TTS、CPU 都是單一資源，併發沒有意義 |
| 階段非零退出 | job 轉 `failed`，前端顯示階段名稱與 stderr 末 20 行，不是白畫面 |
| `.pptx` 抽不出文字（全是圖） | `400` 並說明「這份簡報沒有文字層」 |

## 測試

| 層級 | 內容 |
| :--- | :--- |
| 單元 | `extract_text` 對 `.md`／`.txt`／`.pptx` 的行為，含一份最小 `.pptx` fixture 與「全是圖」的失敗案例 |
| 單元 | job 狀態機用假 runner 測轉場、超時、重驗失敗路徑——**不真跑管線** |
| 整合 | 講稿回寫後 `actions.json` 仍符合 schema，且 `validate.py` 能抓到刻意植入的違規稿 |
| 端到端 | 跑一次真的 `.md`，斷言 MP4 存在且時長 > 0 |
| 回歸 | `c_struct` 與 `c_string` 兩份既有 actions 的驗證閘與時序 lint 維持零診斷 |

## 風險與未決

1. **`--json-events` 的解析穩定性**：`run.py` 現在的輸出是給人看的中文格式。
   加旗標印獨立的 JSON 事件流到 stderr，比正則抓中文可靠。約 15 行。
2. **`.pptx` 的內容品質**：pptx 自帶頁面邊界與講者備忘稿，理論上比裸文字好，
   但實際簡報常常只有條列關鍵字、沒有完整句子。若首次實測品質不佳，
   後續可能需要一個「正規化階段」讓 LLM 先把素材整理成教材結構——
   **這不在本 spec 範圍**，屬於下一輪。
3. **審稿閘的 60 秒是猜的**。首次現場實測後再調。
