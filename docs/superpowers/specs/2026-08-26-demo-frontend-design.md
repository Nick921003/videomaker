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
重生某一頁。這些都不是現場 Demo 需要的，做了就是提前付款。

### 決策翻轉：內嵌播放器保留（2026-08-26）

「線上播放器」原本列在上面這串非目標裡。實作階段做了，全分支審查後決定**保留**。

理由：現場 Demo 的價值就在「當場看到成品」。跳到下載、開檔案管理員、再開播放器
會打斷節奏，而那個節奏正是這支工具要展示的東西。

**代價講清楚**：`GET /video` 會把整支 MP4 讀進記憶體，而且不支援 Range 請求。
現場檔案實測約 3.4 MB，在 localhost 不構成問題。**若日後片長或解析度大幅成長，
這個決定要重新評估**——一支 20 分鐘的課程影片就不是這樣處理的。

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
| GET | `/jobs/{id}/events` | — | SSE。見下方「SSE 實際載荷」 |
| GET | `/jobs/{id}/script` | — | `{segments: [{slide_id, idx, text}]}` |
| POST | `/jobs/{id}/approve` | `{segments: [...]}`（未修改則傳空陣列） | `200 {ok}` 或 `400 {errors: [...]}` |
| GET | `/jobs/{id}/video` | — | `video/mp4` |

### SSE 實際載荷

**同一條串流上有兩種形狀**，而且沒有 `msg` 欄位（初版 spec 寫錯，2026-08-26 依
`serve.py` 實況更正）：

階段事件——由 `run.py --json-events` 產出，`real_runner` 轉發：

```json
{"event": "stage_start", "stage": "synth"}
{"event": "stage_end",   "stage": "synth", "sec": 51.2}
{"event": "stage_fail",  "stage": "synth", "code": 1, "tail": ["...", "..."]}
```

狀態事件——由服務層自己組，只在 `status` 或 `stage` 真的變動時才推：

```json
{"event": "state", "status": "awaiting_review", "pct": 46,
 "stage": "storyboard", "error": null, "deadline": 1787695119.4}
```

**每一則推出去之前都會補上 `status` 與 `pct`**（`ev.update(status=..., pct=...)`），
所以階段事件也帶得到這兩個欄位。

`tail` 是失敗階段 stderr 的最後 20 行，經 `job.error` 送到前端顯示——這就是
下方「錯誤處理」節要求的「顯示階段名稱與 stderr 末 20 行」的落實位置。沒有它的話，
金鑰過期、額度用盡、語音服務沒開在畫面上長得一模一樣。

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
   但實際簡報常常只有條列關鍵字、沒有完整句子。

   ### 記錄：要不要加一個「正規化階段」

   構想是在 `lesson` 之前插一個 LLM 階段，把任意來源的裸文字先整理成
   引擎期待的教材結構（學習目標／痛點情境／核心觀念／程式碼範例）。

   **目前判斷：不做，而且不該當成前置條件。** 理由：

   - `generate_lesson.py` 搭配 `lesson_content.system.md` **本身就是一個 LLM
     正規化階段**。再加一層等於兩次呼叫做重疊的事
   - 多 30–40 秒。現場 Demo 最貴的資源就是時間
   - 多一個 prompt 要維護，而且它與 `lesson_content.system.md` 的職責邊界難劃
   - **還沒有證據說需要它**

   **決策條件**：先讓 `.pptx` 走現有管線實測。若 `lesson.json` 品質不足，
   優先順序是 ① 補強 `lesson_content.system.md`（零成本）→ ② 才考慮新階段。
   量到再改，不預先付款。
3. **審稿閘的 60 秒是猜的**。首次現場實測後再調。

- 2026-08-26 後續修正：整支分支審查揪出的 6 個缺陷全部補上——`stage_fail` 的 stderr 尾段接回 `job.error`（補上本節「階段非零退出」那行原本沒做到的行為）、`_approve` 的同步段加上例外防護、`/jobs` 的 409／503／413 提前回覆前先把 request body 讀乾淨、E2E 測試補上 `examples/` 孤兒檔清理、回歸測試在缺本機管線產物時改成明確 SKIP、計時器鎖測試從原始碼字串比對改成真的行為驗證（commit 待補 hash）

---

## 刻意不處理的技術債（2026-08-26）

全分支審查列出 11 項技術債，交由第二意見以「一個操作者、一台筆電、現場 Demo」的
定位重新裁決，結論是**只做 3 項、拒絕 9 項**。做掉的三項見
`docs/superpowers/plans/2026-08-26-tech-debt.md`。

**這節存在的理由**：不記下來的話，下一個讀這份程式碼的人會把同樣的東西重新發現一次、
重新討論一次，然後可能得到相反的結論。以下是拒絕的項目與**當時的理由**。

拒絕的共同判準：**改動代價落在一個 53 個測試全綠、端到端實證過的系統上，
而收益說不出具體會避免哪個失敗。「比較乾淨」不是收益。**

| 項目 | 為什麼不做 |
| :--- | :--- |
| 衍生路徑佈局（`out/<id>/<id>.mp4` 那組）在 5 處各自重新編碼 | 確實造成過一次真實失敗——E2E 硬寫路徑而 `lesson_id_for` 會剝底線。但那次已改成推導修掉，剩下的重複漂移風險低，而收斂要動 5 個檔 |
| `stage_fail` 後 `Popen` 未 kill | **後來做了**，見技術債 Task 1。當時判定不做是錯的，Ctrl+C 孤兒讓它升級成真缺陷 |
| `serve.py` 靠 `urllib.request` 的匯入副作用取得 `urllib.error` | `urllib.request` 一定會匯入 `urllib.error`，純屬形式主義 |
| SSE 的 `except (BrokenPipeError, ConnectionResetError, OSError)` 過寬 | `OSError` 確實是前兩者的父類、`try` 也確實包住整塊（第二意見說「只包 `wfile.write`」是錯的，已查證）。但那區塊裡只有 `_push` 會丟 `OSError`，實務上抓不到別的 |
| 前端 `STAGES[].weight` 是死資料，HTML 標記另有第三份百分比副本 | 畫面是好的。改成動態注入等於為了消除重複而增加 DOM 操作 |
| 被拒絕的上傳在 `materials/` 留下孤兒 | 單人筆電，留下幾個小檔案不造成任何操作失敗 |
| 內嵌 `<video>` 播放器超出原 YAGNI 清單 | **決定保留**，見上方「決策翻轉」 |
| spec 的 SSE 契約過時 | **改文件不改程式**，見上方「SSE 實際載荷」 |
| `write_segments` 對 `slide_id`／`idx` 對不上的 segment 靜默略過 | 這確實是「以訊號缺席推論成功」的形狀，但現行流程觸發不到——segments 來自同一份檔案數秒前的讀取，而 `write_segments` 從不改動結構。真正的風險是未來有人改動作編排的結構 |
| 雜項拋光（`next_free` 序號空隙測試、`event(event=)` 命名、狀態字串無中心宣告、四個方法缺 docstring） | 純粹是把工作看起來變多 |

另外記錄兩個**被查證推翻的論斷**，免得日後有人照著改：

- 「SSE 的 `try` 只包 `wfile.write`」——**錯**，包住整個內層區塊含 `while` 迴圈
- 「需要加 `allow_reuse_address = True`」——**錯**，`http.server.HTTPServer` 預設就是 `1`，沒有 TIME_WAIT 問題

---

## 2026-08-26 後續修正：現場實測回饋

首次真人操作（`c_loop.md`）暴露四個問題，全部已修（commit 待補 hash）：

| 問題 | 根因 | 修法 |
| --- | --- | --- |
| 影片進度條拖不動 | `/video` 整支回 200，不理 `Range`、不送 `Accept-Ranges`。瀏覽器沒看到該 header 就停用拖曳 | `serve.py` 新增 `parse_range()` 與 `_video()`，支援 206／416，分塊送出 |
| 同上（次要成因） | ffmpeg 沒下 `-movflags +faststart`，`moov` 寫在檔尾，實測 atom 順序 `ftyp → free → mdat → moov` | `render_video.py` 加上該旗標，實測後變為 `ftyp → moov → free → mdat` |
| 審稿頁只有講稿、看不到投影片，等於盲改 | **spec 的漏洞**：只設想「講稿要能改」，沒設想「改的人得看得到那一頁」。圖其實早就有——`slides` 階段排在審稿閘之前 | 新增 `GET /jobs/N/slide/<slide_id>`，前端每頁塞一張 `slide_NN_full.png` |
| 下載的檔案沒有副檔名 | 沒送 `Content-Disposition`，`<a download>` 只好拿網址最後一段命名，存成 `video` | 下載鈕改帶 `?dl=1`，伺服器據此回 `attachment; filename="<lesson_id>.mp4"`，一般播放仍為 `inline` |

順帶修正：審稿頁的「旁白段落 #N」印的是**動作陣列索引**，畫面上會跳成 #2 / #5 / #8（中間夾著 spotlight、reveal）。改為該頁的旁白流水號。

`/slide/` 端點刻意**不採用 `layout.json` 存的絕對路徑**，而是照 `render_slides.py` 的命名規則自行推算檔名——那些路徑是產生當下那台機器的，且同一個問題在 `durations.json` 已經咬過一次（見 memory `durations-json-cross-project-paths`）。自行推算也順帶杜絕了 `slide_id` 夾帶路徑元素的可能。
