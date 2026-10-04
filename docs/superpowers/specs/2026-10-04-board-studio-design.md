# 影片工作室（獨立頁）設計

日期：2026-10-04。分支 `feat/board-runtime`。使用者決定：先做獨立頁面（不合併 GPT 工作台），第一版含
「上傳教材→看分段」「勾選→生成→播放」「學生提問入口」「素材庫列表」，外加「說明」按鈕（SVG 架構圖＋各教材產生步驟與模型）。

## 目標

老師丟一份知識點 md → 看到 AI 整理的問題故事（每段要回答的學生問題、建議秒數、必演畫面、推薦重點片、預估花費）
→ 勾選生成 → 看進度 → 播放／下載。學生提問時先查素材庫：有就直接播，沒有才生成；超出教材範圍則鎖住。

## 架構

```
瀏覽器 video_engine/board/studio/（index.html、app.js、styles.css、pipeline.svg）
   │  fetch JSON
studio_server.py（標準庫 http.server，不加新套件）
   │  單一工作佇列（一次一個，TTS 只有一台）
既有 CLI：author.py plan/scene → compose.py → narrate.py → compile.py → build.py → check.py → export.py
   │
out/units/<unit_id>/   ← 素材庫本體（靜態檔，跨學生共用）
```

- `unit_id` ＝ 教材內容 sha256 前 12 碼：同一份教材永遠對到同一個資料夾，不重複分析、不重複生成。
- 正式流程模型：規劃與分鏡都用 `google:gemini-3.8-flash`（server 傳 `--model`；CLI 預設仍是 Opus，供本機研究）。
- 每個 unit 預算上限 US$0.50（`--budget-usd`，最壞情況防爆）；實際花費讀 `usage.jsonl` 加總。
- 配音需要本機 GPT-SoVITS（:9880）；server 啟動與每個配音步驟前檢查，連不到就讓工作失敗並回報「配音伺服器沒開」。

## 資料夾（out/units/<unit_id>/）

| 檔案 | 來源 |
|---|---|
| `material.md`、`meta.json`（title、created_at） | 上傳 |
| `plan.json`、`usage.jsonl` | author.py plan／scene |
| `<q>.scene.json`、`<q>.report.json`、`<q>.failed.json` | author.py scene |
| `<q>/voice/`、`<q>/player/`、`<q>/video.mp4` | 單段影片 |
| `highlight.scene.json`、`highlight/voice/`、`highlight/player/`、`highlight/video.mp4` | 重點片 |

## API（全部 JSON；錯誤回 `{"error": "中文訊息"}` 與 4xx/5xx）

- `GET /` → studio/index.html；`GET /studio/<file>` → 靜態檔；`GET /media/<unit_id>/<path>` → out/units 裡的 mp4（支援 Range，影片才能拖曳）。
- `POST /api/units` body `{"title": "可省略", "markdown": "..."}` → `{"unit_id", "created": true|false}`（已存在回 false）。
- `GET /api/units` → `[{"unit_id", "title", "created_at", "planned": bool, "videos": n, "spent_usd"}]`（素材庫列表）。
- `GET /api/units/<id>` →
  ```json
  {"unit_id": "...", "title": "...", "planned": true, "spent_usd": 0.15,
   "plan": {"unit_title": "...", "scope": {"covers": [], "not_covers": []},
            "stories": [{"id": "q1", "question": "...", "also_asks": [], "title": "...", "sec": 60, "objectives": [1],
                         "screens": [], "show": "...", "status": "none|queued|running|done|failed",
                         "video": "/media/<id>/q1/video.mp4" | null, "duration": 61.2 | null, "cost_usd": 0.03 | null,
                         "estimate_usd": 0.035}],
            "highlight": {"stories": ["q1", "q2"], "total_sec": 270, "why": "...", "status": "...", "video": null,
                          "duration": null, "estimate_usd": 0.15}},
   "jobs": ["<job_id>", "..."]}
  ```
  `plan` 在還沒規劃時為 null。估價：每段 US$0.035、重點片＝所含各段估價加總（已生成的段不再計）。
- `POST /api/units/<id>/plan` → `{"job_id"}`（已有 plan.json 時直接回 `{"job_id": null, "planned": true}`）。
- `POST /api/units/<id>/videos` body `{"stories": ["q1", "q3"]}` 或 `{"highlight": true}` → `{"job_id"}`。
  已有影片的段跳過；重點片會先補齊缺的段分鏡（不需各段單獨出片），再 compose＋配音＋出片。
- `GET /api/jobs/<job_id>` →
  `{"job_id", "unit_id", "kind": "plan|stories|highlight", "state": "queued|running|done|failed",
    "stage": "規劃|分鏡 q2|配音 q2|出片 q2|...", "log": ["最後 40 行"], "spent_usd", "error": null|"..."}`
- `POST /api/ask` body `{"unit_id": "...", "question": "..."}` →
  `{"kind": "story|highlight|out_of_scope|no_match", "story": "q2"|null, "score": 0.42, "reason": "中文說明",
    "video": "/media/..." | null}`
  比對規則（確定性，不呼叫 LLM）：問題與每段 `question`＋`also_asks`＋`title` 的中文字元雙字組 Jaccard，取最高分；
  ≥ 0.18 視為對到。命中 `highlight.question/also_asks` 或含「重點」「整個單元」等字樣 → highlight。
  沒對到且與 `scope.not_covers` 任一項分數 ≥ 0.15，或問題含教材沒出現的程式語言名（Python、Java…）→ out_of_scope
  （前端鎖住多元教材按鈕並顯示「這份教材沒有教這個」）。其餘 → no_match。
- `GET /api/pipelines` → `studio/pipelines.json`（說明頁內容：各教材產生步驟與模型，見下）。

## 工作佇列

- 單一背景執行緒依序處理；每步是一個子行程（沿用既有 CLI，不重寫流程），stdout/stderr 收進該工作的 log。
- 每個 author 呼叫前 author.py 會自己跑本機自我檢查（selftest，不花錢）；失敗就讓工作 failed 並附 log。
- 單段影片：`author.py scene` → `narrate.py <q>.scene.json <q>/voice` → `compile.py --timing` → `build.py --audio`
  → `check.py`（Playwright python）→ `export.py <q>/player <q>/video.mp4`。
- 重點片：缺的段先 `author.py scene` → `compose.py plan.json <dir> highlight.scene.json` → 同上配音出片到 `highlight/`。
- 伺服器重啟時，未完成的工作標成 failed（狀態存在 `out/units/<id>/jobs/<job_id>.json`）。

## 說明頁（`studio/pipelines.json` ＋ `studio/pipeline.svg`）

說明按鈕打開對話框：上方是影片產生流程的 SVG 架構圖，下方分頁列出各教材的步驟與模型。

影片（board 流程，本分支）：
1. 教材整理（規劃）— Gemini 3.8 Flash，約 US$0.015：學生會問的問題故事、建議秒數、詞彙表（含程式符號唸法）、必演畫面、重點片。
2. 本機自我檢查 — 不花錢：測試分鏡庫＋歷來分鏡全部過量測閘，元件有 bug 就不准呼叫 AI。
3. 分鏡 — Gemini 3.8 Flash，每段約 US$0.02–0.04：只寫 scene.json（元件＋動作＋旁白），不寫座標與秒數。
4. 驗證閘 — 不花錢：編譯、旁白（英文／程式符號／唸法撞名）、標註數、必演畫面、量測閘（越界、重疊、字級、決定性）。
5. 修正 — Gemini，只重寫出問題的場景，每次約 US$0.005–0.015，最多 2 次。
6. 配音 — Gemini 3.8 Flash TTS（預設，英文照原文唸，5 分鐘約 US$0.09，花費記在 voice/tts_usage.jsonl）；可改回本機 GPT-SoVITS（`BOARD_TTS=sovits`，免費）。faster-whisper 拼音級漏字檢查，漏了重配最多 3 輪。
7. 出片 — 本機 Canvas runtime＋Playwright 截圖＋ffmpeg。不花錢。
8. 重點片 — 把 3–5 段串起來，程式產生目錄過場（不呼叫 AI）。
合計：一支 3–5 分鐘重點片約 US$0.21–0.25（分鏡實測 US$0.148＋Gemini 配音）。

心智圖、簡報：沿用 GPT 工作台（`~/projects/videomaker/studio/`）的既有流程，內容由 Codex 讀程式碼確認後填入（標明「工作台既有流程」）。
SVG 只畫影片流程；節點用主題色（notebook：背景 #ECE6DA、卡片 #FFFDF7、線 #2E2622、強調 #A04435、柔和字 #796F62），
付費步驟標金額、本機步驟標「本機・免費」。

## 介面（studio/）

- 單頁兩欄：左欄「素材庫」（unit 列表＋「新增教材」：貼上 md 或選檔）；右欄目前 unit。
- unit 頁：範圍（涵蓋／不涵蓋）、重點片卡（推薦段落、總秒數、理由、預估、生成鈕或播放器）、
  問題故事卡（學生問題、標題、建議秒數、必演畫面標籤、狀態、預估／實際花費、勾選框、播放）。
  底部「生成勾選的段落」鈕；進行中的工作顯示階段＋log 尾巴＋已花費，每 2 秒輪詢 `/api/jobs/<id>`。
- 「學生提問」框：送出後依 `/api/ask` 結果——有片就播；對到但沒片就顯示「生成這段」；out_of_scope 顯示鎖頭與說明。
- 頁首右上「說明」鈕：對話框顯示 pipeline.svg 與 pipelines.json 的分頁內容。
- 配色只用主題色（同上），暖色紙張風；繁體中文；手機寬度可用。

## 不做（這一版）

接入 BridgeAI、帳號權限、多人同時生成、SVG 給 PPT 用的輸出、快速解釋入口。

## 狀態註記

- 2026-10-05 後續修正：本獨立頁併入新工作台，設計改見 `2026-10-05-learning-workbench-design.md`（commit 待補 hash）
