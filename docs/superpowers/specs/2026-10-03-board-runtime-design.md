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

### 單元與片段（2026-10-04 與使用者確認，子專案 3 依此設計）

BridgeAI 一個知識點單元＝一份 md（例：`環境建立.md` 含 7 個學習目標），**不等於一支影片**。
每支影片 40–90 秒（前端有期望片長時從之），整個單元塞進一支只會每個目標各講一句。所以 LLM 分兩步：

1. **規劃**（每份 md 一次、依來源版本快取）：讀整份 md → 片段清單 `[{id, title, objectives, sec, required, after}]`。
   **覆蓋閘**：md 的每個學習目標都要對到至少一段，否則退回重規劃。這是確定性檢查，不靠模型自律。
2. **分鏡**（每段一次、做完全體學生共用）：依學生在 AI 助手說的卡點挑段，只產那幾段的 `scene.json`；
   要整個單元就依 `after` 順序產系列，第一段先好先播。

總時間預算不夠涵蓋全部時，**先產必看段並明示其餘未產**，不壓縮內容硬塞。

### 教材資產庫：生成一次，全體共用，也是 blog 的來源（2026-10-04 與使用者確認）

同一份教材不准每位學生重新分析、重新生成。所有產物進資產庫，以內容雜湊為鍵：

| 產物 | 鍵 | 失效條件 |
| --- | --- | --- |
| 單元規劃 `plan.json` | md 全文雜湊 | 教材改動 |
| 小節 `scene.json` | 該節 `sources` 段落雜湊＋詞彙表＋catalog 版本 | 只有那幾段改了才重做 |
| 配音 | 每句 spoken＋語速＋聲音模型版本 | 改哪句重合成哪句 |
| 播放器／mp4 | scene 雜湊＋時間＋runtime 版本＋主題 | — |

- 學生在 AI 助手提問 → 對到小節（小判斷，幾乎零成本）→ **資產庫有就直接呈現**，沒有才生成並存回。
- **不預先生成**：要生成哪一節取決於哪位學生卡在哪裡（差異化教學），預先生成只是猜測。第一位問到的學生觸發生成。
- 每個資產是**自給自足的靜態檔**，所有形式皆然（影片、PPT、心智圖、漫畫…）：例如影片＝播放器目錄（HTML＋音訊）、mp4，
  加 `meta.json`（標題、學習目標、教材出處段落、形式、時長）。
  BridgeAI_Blog（Nuxt 4）以 iframe 嵌入播放器、由 `meta.json` 產生 content 條目即可發布，不需要後端。

### 單元長片＝小節串接（2026-10-04 與使用者確認）

使用者也要整個單元的解說長片（可達 15 分鐘），做法是**每小節獨立生成，再以設計好的過場串接**，不另外生成長片：

- 結構：片頭目錄 → 過場 → 第 1 節 → 過場 → … → 片尾總結。小節各自是獨立 `scene.json`，各自快取。
- 過場（約 3–4 秒）：回到目錄頁，已講完的節打勾、圈起下一節、寫出節標題。由程式依計畫產生，**不呼叫 LLM**；
  旁白套固定句型（「接下來，第三節：○○」）。
- 銜接句只放在過場，**不寫進小節**——小節必須能單獨觀看，不能有「剛才說過」。
- 規劃階段產出單元詞彙表（例：統一說「編譯器」或「GCC」），每節生成時帶入，串接後用語才一致。
- 成本＝各節加總，串接本身零 token；改一節只重做那節。給學生用 HTML 播放器（目錄可跳章），需要離線檔才匯出 mp4。

**片段清單與形式無關**，接 `studio/` 的能力目錄（影片、心智圖、漫畫…）：計畫＝片段×形式，
AI 依片段性質推薦形式（操作→影片、概念關係→心智圖、迷思→漫畫），每個勾選格是一個生成步驟。
勾選介面只在問題廣泛時展開；問題具體時 AI 預選、學生一鍵開始。
現有 `studio/contracts.py` 限定「一次恰一個步驟」，接入時要放寬——另開 spec。

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
- PATH（估約 46 秒，比交接的 30 秒長，因保留教材強調的兩個坑）：同一 runtime、不新增手寫繪圖程式（只新增 `terminal`、`list` 元件），估時無聲版＋字幕先給使用者看分鏡。
  使用者同意後才跑本機 TTS 配音。
- 兩支的 `scene.json` 各自小於 6 KB。
- 單元測試＋量測閘全綠。

## 保留項目（使用者確認，之後處理）

- **SVG 輸出（給 PPT 用）**：影片完成後再做。元件只透過 `api.*` 繪圖，做一個 SVG 版的 api 即可讓同一套元件輸出向量靜態圖
  （任一畫面的落定格 → SVG），風格與影片一致；PPTX 內嵌 SVG 需附高解析 PNG 備援。
- **BridgeAI「快速解釋」視窗作為入口**：學生選取的文字＝最精確的卡點，可對到問題故事。使用者要再確認，先不實作。
- **一個 beat 只放一句**：中間夾句號的 beat 合成特別不穩（同句連兩輪漏念），可加進旁白閘。

## 不做

- 不接 `run.py`、不改既有 Pillow 管線、不改共用 theme 與 schema。
- 不呼叫付費 LLM。TTS 需經使用者同意。
- 不做角色動畫、不做 3D、不引入 GSAP／HyperFrames 等 npm 依賴。

## 狀態註記

- 2026-10-04 後續修正：通用標記避讓（箭頭直線→兩物件間折線→外側繞道、標籤找空位、同物件只留最新的圈、圈依空隙縮放）、量測閘納入標記與小標、鏡頭自動跟隨畫面外的動作（commit 待補 hash）
- 2026-10-04 後續修正：本機自我檢查 selftest.py＋測試分鏡庫 fixtures/（付費前自動跑）；只重寫出問題的場景（--repair-model、--resume）；必演畫面 screens；旁白程式符號／唸法撞名／唸法重複檢查（commit 待補 hash）
- 2026-10-04 後續修正：新元件 vars（變數面板）、stack（呼叫堆疊）；正式流程定為 Gemini 全包（規劃＋分鏡＋修正），配音預設 Gemini 3.8 Flash TTS 英文原音（narrate.py --tts sovits 可改回本機）；影片工作室獨立頁見 2026-10-04-board-studio-design.md（commit 待補 hash）
- 2026-10-04 後續修正：新元件 pipeline（流程管線）、scale（數值標尺）；cells（位址、對調、輸入緩衝區讀走）、code（前後對照、行內片段錨點）、output（接著印）、terminal（等待輸入）擴充（commit 待補 hash）
- 2026-10-04 後續修正：工作室端到端測試修正——拆場合併、失敗草稿接著修、太擠場景自動推近、推近目標晚出現時等它、每場最多 2 個主要物件、旁白口語化規則與重複／驚嘆號處理（commit 待補 hash）
- 2026-10-05 後續修正：旁白 AI 腔規則（改編自 speak-human-tw，MIT）與免費詞語檢查——28 個高信心 AI 用語、「不是…而是」整支最多一次，抓到只重寫該場景（commit 待補 hash）
