# 多元教材工作台（新版）設計

日期：2026-10-05。分享日：2026-10-14（三），對象是混合聽眾（指導老師、BridgeAI 團隊、授課老師）。
取代：`2026-10-04-board-studio-design.md` 的影片工作室獨立頁（併入本設計）。舊工作台（`serve.py`＋`web/`）不動，保留為「舊版」。

## 1. 決策摘要

| 項目 | 決定 |
|---|---|
| 後端主體 | 影片工作室伺服器（原 `video_engine/board/studio_server.py`）搬到 `workbench/server.py` 擴充；舊 `serve.py` 不改 |
| 擴充方式 | **教材形式登記表**：一種教材一個 Python 檔；伺服器、架構圖、用量頁都讀登記表，新增形式不改伺服器 |
| 教材與形式 | 分析出的「幾點」是共用骨架：影片逐點做，重點片／心智圖／簡報整份做 |
| 模型 | 全部 Gemini 3.8 Flash（心智圖、簡報的子程式設 `VIDEO_ENGINE_LLM=google:gemini-3.8-flash`）；配音 Gemini 3.8 Flash TTS |
| 介面 | 左側導覽列六頁；每頁一個螢幕高，不做長捲動；圖一律可縮放、拖曳、符合視窗、全螢幕 |
| 製作流程 | 四步驟：① 教材 → ② 分析結果 → ③ 生成 → ④ 成品 |
| 架構圖 | 一張總圖，點分支平滑放大；同一元件兩種模式：說明（點節點看細節）、即時（目前步驟亮起、失敗變紅） |
| 用量 | 不常駐；獨立「用量」頁，依「教材 → 成品 → 每筆呼叫」分類 |
| 示範方式 | 只做即時（不做重播）；失敗時列白話原因與建議（重試／稍後再試／回報） |
| 不搬的舊功能 | 自然語言「製作需求」框、講稿審核倒數、成品核可／退回（舊版工作台仍有） |
| 對外接口 | 第一版做 `/api/v1`、來源參照、成品清單 manifest、嵌入頁；預留回呼、API 金鑰、匯出目的地登記表 |

## 2. 對外接口（之後接 BridgeAI 平台與部落格不必大改）

- **素材庫是唯一真實來源**；平台、部落格都只是讀它或發布它。
- **版本化 API**：新前端只用 `/api/v1`，平台接入用同一套。
- **來源參照**：建立教材可附 `source_ref`（`{"platform": "bridgeai", "course": "...", "unit": "...", "topic": "...", "revision": "..."}`，不透明字串）。
  教材 id ＝ 教材 markdown 的 sha256 前 12 碼；同內容永遠同一個資料夾。身分、權限、額度由平台負責，引擎不認識 JWT、課程成員。
- **成品清單**：`GET /api/v1/units/<id>/manifest`，平台據此列出「換個方式理解」的選項。
- **嵌入頁**：`/embed/<unit_id>/<item>`，乾淨的影片播放器／心智圖檢視／簡報翻頁；④成品頁也用同一批檢視元件。
- **預留不實作**：生成完成回呼（`callback_url`）、API 金鑰與允許嵌入網域（設定檔）、匯出目的地登記表（靜態資料夾、BridgeAI Learn、BridgeAI 平台）。
- **待決架構問題**：使用者願景是「所有影片與多元素材都在部落格（BridgeAI Learn，Nuxt Content 靜態站）找得到；學生在平台提問先找部落格，沒有才生成並放上去」。
  靜態站每次要重建部署、影片放 repo 會撐爆容量；可能改成影片放 YouTube／物件儲存、部落格只放連結，或部落格改動態站。之後再討論，本設計不綁定。

## 3. 後端

### 3.1 目錄

```
workbench/
  server.py        HTTP 路由（由原 video_engine/board/studio_server.py 搬來再擴充）
  library.py       素材庫：所有 out/units/<id>/ 的讀寫都經過這裡（日後換雲端儲存只改這檔）
  jobs.py          單一工作佇列、子程式執行、@step／@error 解析、錯誤查表
  usage.py         讀取並彙整用量紀錄
  formats/
    __init__.py    載入與驗證登記表；list_formats()、get_format(id)
    stages.py      共用階段（教材整理、分析）的步驟描述，給總圖用
    video.py  highlight.py  mindmap.py  slides.py  planned.py
  run_mindmap.py  run_slides.py  run_normalize.py   子程式（沿用 studio/ 的生成與繪圖）
  web/             新前端（AGY）
  embed.html       嵌入頁（共用 web/js/viewers）
```

啟動：`.venv/bin/python -m workbench.server --port 8765`。`video_engine/board/studio/` 舊頁面由新前端取代（搬移前在計畫中列出、經確認再移）。

### 3.2 登記表

```python
FORMAT = {
	"id": "mindmap",               # 唯一；也是成品 item 名（逐點形式的 item 是點 id，如 q2）
	"name": "概念心智圖",
	"scope": "unit",               # point：逐點；unit：整份
	"status": "available",         # available | planned
	"preview": "svg",              # video | svg | deck | none
	"steps": [                     # 架構圖與即時亮燈都用這份
		{"id": "generate", "name": "概念與關係生成", "model": "google:gemini-3.8-flash",
		 "paid": True, "cost": "試跑後填入", "detail": "3–12 個概念、父子關係與原文引用"},
		{"id": "validate", "name": "契約與引用驗證", "model": "本機", "paid": False, "cost": "免費",
		 "detail": "樹狀結構、無循環、每個概念與關係的引用確實在教材裡"},
		{"id": "render", "name": "繪製 SVG", "model": "本機", "paid": False, "cost": "免費",
		 "detail": "程式計算樹狀位置與換行，不由模型畫圖"},
	],
	"planned_note": None,          # planned 形式：路線圖用的說明、建議順序與理由
}
def estimate_usd(unit, item) -> float
def commands(unit, item) -> list[tuple[str, list[str]]]   # [(起始 step id, argv), ...]，依序執行
def outputs(unit, item) -> dict                           # {"video": "q2/video.mp4", "poster": ..., "svg": ..., "pptx": ...}（相對 unit 目錄）
def is_done(unit, item) -> bool
```

- `formats/__init__.py` 啟動時驗證：必填欄位、step id 不重複、`status=planned` 不得有 `commands`。驗證失敗伺服器不啟動。
- 第一版登記：`video`（point）、`highlight`、`mindmap`、`slides`（unit）；`planned.py` 列漫畫、師生 podcast、互動圖文、引導式範例、理解檢核。
- 影片步驟沿用 `pipelines.json` 的內容（分析之後：自我檢查、分鏡、驗證閘、修正、配音、出片）；
  重點片：補齊缺的段落分鏡、串接（程式產生目錄過場）、配音、出片。`pipelines.json` 由登記表取代。
- 步驟的單價寫實測值；還沒實測的（心智圖、簡報改 Gemini 後）寫「試跑後填入」，付費試跑後更新。

### 3.3 子程式協定（stdout）

- `@step <step_id>`：切換目前步驟（一個子程式內有多步時用，如 author.py 的 分鏡→驗證→修正）。
- `@error <code> <白話細節>`：失敗前印出，再以非零碼結束。
- `@warn <code> <白話細節>`：不中斷的提醒，記進工作與成品的 `warnings`，成品照樣產出（2026-10-05 決定：漏唸不判失敗）。
- `@unit <unit_id>`：教材整理子程式建立教材後印出，工作結果帶上 `unit_id`。
- 沒印 `@error` 的失敗：伺服器用 log 尾端比對 Gemini 暫時錯誤（429、503、UNAVAILABLE、RESOURCE_EXHAUSTED、timeout）→ `gemini_busy`，其餘 `unknown`。
- 既有 CLI（author.py、narrate.py、check.py、selftest.py）補印 `@step`／`@error`，不改其他行為。

### 3.4 錯誤查表（`jobs.py`）

| code | 原因（畫面） | 建議 | 可重試 |
|---|---|---|---|
| gemini_busy | Gemini 暫時忙碌或連線中斷 | 等 1–2 分鐘再按「重試」 | 是 |
| repair_exhausted | 分鏡還有 N 個問題（列前 2 個） | 重試會從失敗草稿接著修，約 US$0.01 | 是 |
| quote_mismatch | AI 引用的句子在教材裡找不到 | 重試，約 US$0.005 | 是 |
| tts_missing（提醒，不是失敗） | 第 X 句可能漏唸（檢查也可能誤判） | ④ 點進去聽；需要就按「重配這句」 | — |
| budget | 這份教材已花到上限 US$0.50 | 少選幾點或提高上限 | 否 |
| selftest | 元件檢查沒過，為了不浪費錢沒有呼叫 AI | 回報開發者 | 否 |
| too_large | 超過 5 MB／30 頁／6 萬字 | 拆小再上傳 | 否 |
| interrupted | 伺服器重啟，工作中斷 | 重試 | 是 |
| unknown | 顯示 log 最後幾行 | 重試或回報 | 是 |

重試：`POST /api/v1/jobs/<id>/retry` 建立新工作；影片有 `<item>.failed.json` 時自動 `--resume`。

### 3.5 素材庫（`out/units/<unit_id>/`）

```
meta.json        {"title", "created_at", "source_ref": null|{...}, "source_kind": "md|txt|pdf|pptx"}
material.md      教材（pdf/pptx 為整理後的 markdown）
plan.json        分析結果（author.py plan）
usage.jsonl      本教材所有 AI 呼叫（統一格式，見 3.6）
manifest.json    每次工作完成後重寫
q2/…  highlight/…  mindmap/{mindmap.json,mindmap.svg}  slides/{deck.json,deck.pptx}
jobs/<job_id>.json
```

上傳暫存：`out/uploads/<upload_id>/`（原檔、抽取文字）。伺服器重啟時，未完成工作標為 `interrupted`。每份教材預算上限 US$0.50。

### 3.6 用量

- 統一紀錄：`{"at", "item", "step", "model", "in", "out", "usd"}`（可另有 cache 欄位）。item：`ingest`、`analysis`、點 id、`highlight`、`mindmap`、`slides`。
- author.py 的紀錄補 `item`（plan → `analysis`；scene → 點 id 或 `highlight`）；TTS 紀錄依所在資料夾推 item；心智圖／簡報／整理子程式直接寫統一格式。
- `usage.py` 讀取時相容舊紀錄：沒有 item 的 plan → `analysis`，scene → `video`（未標點）。

### 3.7 API（`/api/v1`，全部 JSON；錯誤回 `{"error": {"code", "reason", "advice"}}`）

| 方法與路徑 | 說明 |
|---|---|
| `GET /api/v1/formats` | `{"stages": [...], "formats": [...]}`：登記表公開欄位（不含函式），供總覽、架構圖、路線圖 |
| `POST /api/v1/uploads`（multipart） | pdf/pptx：本機抽取 → `{"upload_id", "kind", "excerpt", "pages", "chars", "estimate_usd"}`；超限回 `too_large` |
| `POST /api/v1/uploads/<id>/normalize` | Gemini 整理（確認後才呼叫）→ `{"job_id"}`；完成時 job 帶 `unit_id` |
| `POST /api/v1/units` | `{"title"?, "markdown", "source_ref"?}` → `{"unit_id", "created"}`（md/txt 由前端讀檔後走這裡） |
| `GET /api/v1/units` | `[{"unit_id", "title", "created_at", "analyzed", "points", "products": {"video": n, "highlight", "mindmap", "slides"}, "spent_usd", "source_ref"}]` |
| `GET /api/v1/units/<id>` | `{"unit_id", "title", "source_ref", "spent_usd", "analysis": null|{"unit_title", "scope": {"covers", "not_covers"}, "points": [{"id", "question", "also_asks", "title", "sec", "objectives", "screens", "show"}], "glossary": [{"term", "say_as"}], "highlight": {"points", "total_sec", "why"}}, "items": [{"item", "format", "label", "status": "none|queued|running|done|failed", "estimate_usd", "cost_usd", "duration", "files", "job_id"}]}` |
| `POST /api/v1/units/<id>/analyze` | → `{"job_id"}`；已分析回 `{"job_id": null, "analyzed": true}` |
| `POST /api/v1/units/<id>/generate` | `{"items": ["q1", "q3", "highlight", "mindmap", "slides"]}` → `{"job_ids": [...]}`（一個 item 一個工作，依序排隊；已完成的略過） |
| `GET /api/v1/jobs/<id>` | `{"job_id", "unit_id", "item", "format", "state": "queued|running|done|failed", "steps": [{"id", "state": "pending|running|done|failed|skipped"}], "current", "log": [最後 40 行], "spent_usd", "error": null|{"code", "reason", "advice", "retry"}, "warnings": [{"code", "detail"}]}`（成品 item 也帶同樣的 `warnings`） |
| `POST /api/v1/jobs/<id>/retry` | → `{"job_id"}` |
| `POST /api/v1/units/<id>/items/<item>/renarrate` | `{"beats": [句號（從 1 起）]}` → `{"job_id"}`：只重配這幾句（不用快取），再重新出片 |
| `GET /api/v1/queue` | `{"running": job|null, "queued": [job...]}`（導覽列小圓點、③的排隊清單） |
| `GET /api/v1/usage` | `{"totals": {"today", "all", "by_model": {...}}, "units": [{"unit_id", "title", "usd", "items": [{"item", "label", "usd", "calls": [{"at", "step", "model", "in", "out", "usd"}]}]}]}` |
| `POST /api/v1/ask` | 沿用現有比對（雙字組 Jaccard ≥ 0.18；不呼叫 AI） |
| `GET /api/v1/units/<id>/manifest` | `{"unit_id", "title", "source_ref", "products": [{"item", "format", "label", "files", "duration", "cost_usd", "embed_url", "created_at"}]}` |
| `GET /embed/<unit_id>/<item>` | 嵌入頁 |
| `GET /media/<unit_id>/<path>` | 成品檔（支援 Range） |
| `GET /` | 新前端 |

## 4. 前端（`workbench/web/`，AGY 實作）

- 原生 HTML／CSS／ES modules，零建置、不用 CDN；暖色紙張風（背景 #ECE6DA、卡片 #FFFDF7、線 #2E2622、強調 #A04435、柔和字 #796F62）。
- 雜湊路由：`#/overview`、`#/make/1`…`#/make/4`、`#/pipelines`、`#/library`、`#/usage`、`#/roadmap`；`?mock=1` 改讀 `web/mock/*.json`。
- 每頁 100vh；長清單只在框內捲動或分頁。窄螢幕時導覽列收成上方列。
- 有工作在跑時，導覽列「製作」旁亮小圓點（每 3 秒查 `/api/v1/queue`）。

| 頁 | 內容 |
|---|---|
| 總覽 | 目標一句話；三個數字（可用形式數、一支片平均花費、素材庫成品數）；形式卡片（逐點／整份、狀態、模型、單價），點卡片跳流程架構並放大該分支 |
| 製作 ① | 上傳 md/txt/pdf/pptx、貼上、或從素材庫挑；pdf/pptx 顯示整理預估，確認才送；「開始分析」（約 US$0.015） |
| 製作 ② | 範圍（涵蓋／不涵蓋）；左點清單＋右詳情（學生問題、也會這樣問、必演畫面、建議秒數）；詞彙表；建議重點片 |
| 製作 ③ | 勾選點＋整份項目，各自預估與總計 → 開始；左排隊清單，右目前項目的即時流程圖；失敗：紅色步驟＋原因＋建議＋「重試」 |
| 製作 ④ | 頁籤：每點影片（一次一支，上一點／下一點）、重點片、心智圖（縮放拖曳）、簡報（翻頁＋下載 PPTX）；標實際花費 |
| 流程架構 | 總圖：教材 →（整理）→ 分析 → 各形式 → 素材庫；未做形式虛線；點分支平滑放大；點節點側欄顯示模型、花費、檢查什麼；−／＋／符合視窗／全螢幕／返回全圖、滾輪縮放、拖曳 |
| 素材庫 | 上方「學生提問」（選教材＋問題 → 播放／生成這段／超出範圍鎖住）；下方教材卡片一頁 6 張，點進去開製作 ④ |
| 用量 | 總計（今天、全部、依模型）；依教材 → 成品分組，展開看每筆呼叫；只在此頁且有工作在跑時每 2 秒更新 |
| 路線圖 | planned 形式（建議順序與理由）＋接口計畫（平台、部落格） |

架構圖元件（`web/js/diagram.mjs`）：輸入登記表步驟，純函式算版面（可用 `node --test` 測），SVG 輸出；`mode: "explain" | "live"`；縮放拖曳在 `panzoom.mjs`。

## 5. 測試與驗證

- 後端（不呼叫 AI）：登記表驗證、API（假子程式）、`@step`／`@error` 解析與錯誤查表、用量彙整與舊紀錄相容、manifest、心智圖／簡報子程式（假模型）、伺服器重啟標 interrupted。舊 576 個測試全過。
- 前端：`diagram.mjs`、`panzoom.mjs` 純函式用 `node --test`；畫面由使用者驗收（Claude 不自行截圖）。
- 付費試跑（使用者同意後）：一份教材做分析、2 點影片、心智圖、簡報，約 US$0.10–0.15；確認 Gemini 的原文引用穩定度。不穩時把「引用改標原文位置」加進修正步驟。

## 6. 派工與時程

- Claude：規格、API 契約與假資料、拆任務、審查、跑測試、小修。Codex：後端（3 節全部）。AGY：前端（4 節全部）。
- 先定契約與 `web/mock/*.json`，Codex 與 AGY 同時開工。

| 日期 | 工作 |
|---|---|
| 10/5–6 | 規格、計畫、API 契約、假資料 |
| 10/6–8 | Codex 後端；AGY 用假資料做前端 |
| 10/9 | 前端接真 API、修整合問題 |
| 10/10 | 付費試跑（經同意） |
| 10/11–12 | 依使用者看畫面的意見修改 |
| 10/13 | 彩排、緩衝 |
| 10/14 | 分享 |

## 7. 不做（第一版）

生成完成回呼、API 金鑰、部落格匯出、自然語言製作需求、講稿審核與成品核可、planned 形式的實作、帳號與多人同時生成、BridgeAI 實際串接。
