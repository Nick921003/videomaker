# 紙上動畫元件庫（Board Runtime）設計

2026-10-03。取代「每支影片手寫一份 Canvas HTML」的做法。

## 問題

使用者唯一接受過的影片是 A＋C 字串片（`out/state_change_ac_20261001/movie.html`），
但它是專為那一支手寫的：`"Alice"` 寫死在 `row()` 裡，座標全是常數，時間是常數，
C 段還用猴子補丁覆寫整個 `worldScene`。後續的 `html_canvas_sample` 也一樣（`{x:440,y:290,...}`）。
每換一個題目就要重寫一份 HTML，於是品質看當次運氣、成本看當次修了幾輪。

## 目標

LLM 每支影片只產一份小 JSON（`scene.json`）：用哪些元件、做哪些動作、動作掛在哪句旁白。
畫面、排版、錨點、鏡頭、時間換算全由固定的 runtime 負責。
**品質由元件庫決定，每支成本由 JSON 大小決定。**

產品脈絡：學生看教材看不懂時按「換個方式理解」，系統當下產影片。
所以生成當下沒有人能補元件——元件做不到的畫面要**退化成保底畫法，並記入缺口紀錄**，不能停下來。

## 子專案切分

| # | 內容 | 本文件 |
| --- | --- | --- |
| 1 | runtime＋首批 7 元件；手寫 JSON 重現 A＋C，再做 PATH 30 秒 | **是** |
| 2 | 依缺口紀錄與 9 份教材盤點補元件（算式求值、型別轉換、差異比較…） | 否 |
| 3 | LLM 產 `scene.json`：prompt 帶元件目錄、驗證閘、接 `synth`、接 `run.py` | 否 |

子專案 1 的 JSON 由 Claude 在對話中手寫，模擬子專案 3 中 LLM 的角色。

## 架構

```
scene.json ──┐
(內容＋編排)  │   board/compile.py            board/runtime/*.js
             ├──► timeline.json ──────────► 播放器 player.html
timing.json ─┘   (絕對秒數、字幕)           ├─ 載入時：量字 → 版面 → 錨點
(實測音訊，可無)                              ├─ stateAt(t) → render(t)  純函式
                                             └─ frameInfo(t) 供量測閘
                 board/check.py   瀏覽器量測閘（越界、重疊、決定性）
                 board/export.py  多 worker 逐格截圖 → FFmpeg → mp4
```

三層契約沿用主管線精神：

| 層 | 檔案 | 作者 | 禁止 |
| --- | --- | --- | --- |
| 內容＋編排 | `scene.json` | LLM／人 | 像素座標、秒數 |
| 時間 | `timeline.json` | `compile.py` 自動 | 手改 |
| 幾何 | 瀏覽器內量測 | runtime 自動 | 寫死座標常數 |

## `scene.json` 格式

```json
{
  "version": 1,
  "title": "同一個 name[32]：容量 32，長度 5",
  "tag": "C 字串",
  "corner_note": "概念示意",
  "objects": [
    {"id": "name", "type": "cells", "label": "name：32 格空間", "count": 6, "tail": "其餘仍未知"},
    {"id": "out", "type": "output", "label": "輸出", "max_text": "Alice"}
  ],
  "scenes": [
    {
      "id": "read", "title": "從開頭讀，遇到結束字元就停", "label": "一路讀到終點",
      "keep": ["name"],
      "layout": {"stack": ["name", "out"]},
      "beats": [
        {"say": "把讀到的字母接起來。", "spoken": "…（可省略）",
         "do": [{"act": "scan", "target": "name", "to": "out", "range": [0, 4], "cue": "讀到"}]}
      ]
    }
  ]
}
```

- **object**：`id`、`type`（元件目錄中的型別）、元件專屬屬性、選填 `fallback`（退化時顯示的文字）。
  物件宣告一次，整片共用同一個實體——這是「同一主角持續改變」的來源。
- **scene**：紙上的一個區域，換場時鏡頭沿紙面平移。`title` 顯示在頁首，`label` 手寫在紙上該區左上角。
  `keep` 列出要跟著進新區域的物件（主角）；沒列的留在舊區域原地，當作紙上的歷史。
- **layout**：`{"stack": [...]}` 直排、`{"row": [...]}` 橫排，可巢狀。只列物件 id，沒有座標。
  不可見的物件自動略過。beat 可帶 `layout` 覆寫；可見集合或版面改變時，物件以動畫移到新位置。
- **beat**：一句旁白＝一段字幕。`say` 是字幕原文，`spoken` 是給 TTS 的唸法（`\0` → 結束字元）。
- **action**：`act` 動作名、`target` 目標（物件 id 或錨點，如 `name:i5`）、`cue` 掛在 `say` 中的哪個詞、
  其餘為動作參數。

## 時間規則（`compile.py`）

1. **beat 時間**：有 `timing.json`（實測音訊每句起訖）就用實測；沒有就估：每字 0.24 秒、句間 0.35 秒、換場 0.6 秒。
2. **動作起點**：有 `cue` → `beat.start + 詞在句中的字元位置比例 × beat 長度`；
   沒有 → beat 內前一個動作的終點（第一個動作則為 beat 起點）。`"with": "prev"` 表示與前一動作同時開始。
3. **動作長度**：一般動作用目錄預設值。**序列動作**（fill／scan／walk／type／print 多行）有每項的 `[min, max]`：
   長度 = 從起點到「同場景下一個序列或書寫動作的起點」之間的可用時間，夾在 `n×min` 與 `n×max` 之間。
   可用時間不足 `n×min` 時編譯報告會標示「趕」。
   這取代了 A＋C 用手調錨點把視覺時間扭到音訊上的做法。
4. 片尾多停 1.2 秒。字幕一 beat 一段，同 beat 起訖。

輸出 `timeline.json`：`duration`、每個 scene 的起訖、每個 beat 的起訖與字幕、每個動作的 `t0`／`t1`／參數、編譯警告。

## 版面與鏡頭

- 輸出 1920×1080。頁首帶 96px（場景標題、右側 tag），字幕帶 160px（兩行字幕、進度條、角落註記），中間是鏡頭視窗。
- 紙面寬 1920，場景區域依序往下排，大小與鏡頭視窗相同，區域之間留白。紙上有方格與左緣鉛筆進度線。
- **物件尺寸用整片最大內容量測**（輸出框以 `max_text` 量、清單含之後才 append 的列、終端機含所有輸出行），
  跟主管線「版位一律含 hidden」同一條規則，避免內容增長時版面跳動。
- 版面樹整體等比縮放以塞進內容框，縮放 ∈ [0.55, 1.25]。低於 0.55 → 量測閘失敗。放大上限讓少物件的畫面不留大片空白。
- 鏡頭預設框住當前區域；`focus` 推近到錨點框（最多 1.5 倍，不出區域），`wide` 拉回。
  換場鏡頭平移 1.0 秒，`keep` 的物件同時移到新區域，畫面上看起來主角不動、紙往上捲。

## 元件目錄（子專案 1）

視覺全部移植自 A＋C：方格紙、鉛筆線只在描線過程抖動（描完即穩定）、單一強調色、字元飛行帶弧線。

| 型別 | 用途 | 動作 | 錨點 |
| --- | --- | --- | --- |
| `note` | 問句、提示、字面值 | `write`（手寫揭露）、`show`、`hide` | `id` |
| `cells` | 陣列／記憶體格子 | `fill`（從 `from` 飛入）、`scan`（指標逐格走，字元飛到 `to`）、`stop`（指標停在某格並圈起）、`point`、`brace`（範圍括線＋標籤） | `id`、`id:i{n}`、`id:label` |
| `output` | 輸出框 | 由 `scan` 寫入；`set` | `id`、`id:text`、`id:end` |
| `code` | 深色程式面板 | `highlight`（行標記） | `id`、`id:L{n}` |
| `metrics` | 數字比較列 | `reveal`（逐項） | `id`、`id:m{n}` |
| `terminal` | 終端機 | `type`（打字＋游標）、`print`（輸出行，可標錯誤）、`restart`（關掉重開，清空） | `id`、`id:line{n}`、`id:cmd` |
| `list` | 依序搜尋的清單（PATH） | `walk`（逐列檢查，標 ✗ 或在 `found` 處圈起）、`append`（新列手寫加入） | `id`、`id:title`、`id:r{n}` |

**通用動作**（任何錨點）：`show`、`hide`、`circle`、`underline`、`arrow`（起訖錨點每格重算，不存座標）、`focus`、`wide`。

元件目錄同時存成 `board/catalog.json`（型別、必填屬性、動作與參數、錨點樣式、每項時長）。
`compile.py` 用它驗證；測試確保 JS 端註冊的元件與目錄一致。子專案 3 會把它塞進 LLM prompt。

### 外部元件參考

依 `docs/HANDOFF_VIDEO_COMPONENT_RESEARCH_2026-10-03.md`（GPT 查證）。**借介面設計，不搬程式碼**：
HyperFrames／Onda／Code Hike／Motion Canvas 都是 DOM 或 React 元件，綁各自的 runtime，
Canvas 截圖拿不到；且已接受的是方格紙鉛筆風，外觀本來就得重畫，重畫外觀即元件的主要工作量。

| 借什麼 | 來源 | 用在 |
| --- | --- | --- |
| command 逐字、輸出逐行、結尾留新 prompt、`cadence`；輸出行預留空間以透明度顯示 | HyperFrames `code-terminal-run` | `terminal`（本次） |
| 程式 insert／replace／remove 變形、字元範圍 bbox 查詢 | Motion Canvas Code、Code Hike | `code` 的 diff 動作（子專案 2） |
| 預期／實際左右對照的 slot | HyperFrames `comparison-split` | `compare` 元件（子專案 2） |

## 缺口與退化

- 未知元件型別 → 改用 `note` 顯示 `fallback`（沒有就用 id），寫入缺口紀錄。
- 元件不支援的動作 → 略過該動作，寫入缺口紀錄。
- `target` 解析不到、`cue` 不在 `say` 中、layout 引用不存在的物件 → **編譯失敗**（這是 JSON 錯，不是元件缺口，子專案 3 會讓 LLM 重產）。
- 缺口紀錄：`compile.py` 在 `timeline.json` 的 `gaps` 欄位列出，並附加一行到 `board/gaps.jsonl`（時間、題目、想要的型別或動作、實際退化成什麼）。

## 驗收閘（`check.py`，瀏覽器內）

在每個動作的起點、中點、終點，以及每個場景的落定點取樣：

1. 物件完全可見且不在移動中時，所有文字框在鏡頭視窗內；字幕在字幕帶內。
2. 不同物件的框不重疊（飛行字元、指標、圈選、箭頭等覆蓋標記除外）。
3. 版面縮放 ≥ 0.55。
4. 決定性：同一 t 先往後再往回 seek，畫面雜湊相同；重新載入後同 t 相同。
5. 無 JS 錯誤。

通過不代表好看。視覺好壞交使用者判斷。

## 匯出（`export.py`）

用 webwright venv 的 Python Playwright（專案 venv 不新增依賴）。`seek(t)` 是純函式，所以影格可以切段平行：
N 個 worker 各渲一段 → 各自編成 H.264 片段 → concat → 混入音訊。預設 24fps、1920×1080、CRF 18。

播放器 `player.html` 同時是審片工具：可播放音訊、拖時間軸。日後也可直接把它給學生看，省下編碼時間（不在本次範圍）。

## 檔案配置

```
video_engine/board/
├── catalog.json        元件目錄
├── compile.py          scene.json＋timing.json → timeline.json（純 Python，零依賴）
├── check.py            瀏覽器量測閘
├── export.py           平行逐格匯出
├── build.py            打包成可直接開的 player 目錄（runtime＋資料 inline 成 board_data.js）
├── runtime/
│   ├── core.js         數學、筆觸、文字、量測紀錄
│   ├── layout.js       版面樹、鏡頭
│   ├── player.js       載入、stateAt、render、frameInfo、播放器 UI
│   ├── player.html
│   └── components/     note、cells、output、code、metrics、terminal、list、marks
└── examples/
    ├── c_string.scene.json  c_string.timing.json
    └── env_path.scene.json
```

顏色只從 `themes/paper.json` 讀。runtime 不寫 hex。

## 不變量

1. `render(t)` 只依賴 t 與載入時算好的版面，不依賴上一格。禁用 `Math.random`、`Date.now`、`performance.now`。
2. 筆觸抖動只在描線過程中出現，描完的線條穩定。
3. 錨點每格由當前版面算出，箭頭、飛行、鏡頭都查錨點，不存座標。
4. 版面以整片最大內容量測，內容增長不改變版位。
5. 不溢出：放不下就縮，縮到 0.55 還放不下就讓量測閘失敗，不准畫出界。

## 子專案 1 驗收

- A＋C 重現：用既有 `master.wav` 與實測字幕時間，`c_string.scene.json` 產出的片與已接受版本並排，
  使用者判定「品質沒有退步」。
- PATH 30 秒：同一 runtime、不新增手寫繪圖程式（只新增 `terminal`、`list` 元件），估時無聲版＋字幕先給使用者看分鏡。
  使用者同意後才跑本機 TTS 配音。
- 兩支的 `scene.json` 各自小於 6 KB。
- 單元測試＋量測閘全綠。

## 不做

- 不接 `run.py`、不改既有 Pillow 管線、不改共用 theme 與 schema。
- 不呼叫付費 LLM。TTS 需經使用者同意。
- 不做角色動畫、不做 3D、不引入 GSAP／HyperFrames 等 npm 依賴。
