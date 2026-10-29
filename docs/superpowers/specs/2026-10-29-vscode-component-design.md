# VS Code 元件：一份描述，各風格都能畫

日期：2026-10-29　狀態：設計待使用者審

## 目標

做一個 VS Code 畫面元件，**只寫分鏡、不寫程式**就能出現在任何風格的影片與文章配圖裡。它同時是平台元件化的第一個樣板：做通之後，其他元件照同樣方式補上各風格的皮膚。

## 使用者定的原則（2026-10-29）

1. **實作用 VS Code，原理用黑板。** 程式怎麼執行、跑出什麼，一律用這個元件展示，不另外手畫示意，免得觀眾分不清在講實作還是理論。
2. **AI 只寫分鏡。** 未來 AI 依教材架構寫分鏡、挑元件、填文字、選動畫，不碰任何元件程式。每一鏡的畫面要能在分鏡表裡講清楚。printf 片的大量手調是測試期，不是常態。
3. **外觀 A**：同一份狀態，兩種外觀都能畫。黑板片與文章配圖用仿真深色，手帳片用鉛筆手繪。
4. **範圍 B**：編輯器、檔案列表、執行鈕、輸出面板與終端機、游標點擊、齒輪選單、設定頁、擴充功能列表。分割視窗、搜尋、除錯面板不做。
5. **通用動作跨風格**：畫圈、底線、箭頭、推鏡頭由 AI 寫意思（「畫圈・警告」），顏色與筆法由風格決定。
6. 架構不換：兩邊和老師的 video-skills 都是 HTML＋JS（HyperFrames／自家 player），沒有 React 或 Vue。

## 兩邊現況（2026-10-29 查程式）

| | 手帳（`video_engine/board/`） | 黑板（`video_engine/out/vscode_printf_chalk/`） |
|---|---|---|
| 畫布 | Canvas 2D，`player.js` 自己播 | SVG＋DOM，HyperFrames 逐格截圖 |
| 時間 | 每格是 t 的純函式 | 每格是 t 的純函式（`core.js` 開頭寫明） |
| 元件 | `catalog.json` 14 種：note、cells、output、code、metrics、terminal、list、window、cursor、vars、stack、pipeline、scale、icon | 沒有元件目錄。`lib/kit/kit.js`（約 1000 行）是粉筆筆畫：線、框、圈、箭頭、雲、括號、標題、公式、流程、鏡頭、板擦 |
| 每支片的程式 | 不用寫，寫 `scene.json` | 要寫 `beats.js`（printf 約 1200 行），含沙漏、鎖、鍵盤、齒輪、`vscodeMock()` |
| 分鏡契約 | `scene.json`，`compile.py` 擋：型別不在目錄、欄位缺、動作指到不存在的錨點、cue 不在旁白裡 | `storyboard.json` 的 `draw`／`point` 是自由文字，給人和 Claude 讀，機器不能照畫 |
| 通用動作 | `generic_actions`：show、hide、circle、underline、arrow、focus、wide，由 `player.js` 畫並避讓 | `ring`、`underline`、`arrow` 是 kit 函式，每支片手動呼叫 |
| 配色 | `themes/notebook.json`，鍵是用途（`text.accent`、`code.error`…） | `kit.js` 的 `TONE`，鍵是語氣（`accent`、`warn`、`ok`、`muted`、`accent2`、`orange`） |
| 已有的 VS Code | `window` 元件＋`presets/vscode/gear_menu.json`（鉛筆線框，規範寫「不仿真截圖」） | `beats.js` 的 `vscodeMock()`（仿真 Dark+，開場與後段兩個電腦畫面共用） |

兩個關鍵事實：

- **兩邊畫布技術不同**（Canvas 對 SVG），所以元件不能直接共用繪製程式碼，要在中間隔一層。
- **兩邊都是「t 的純函式」**，所以狀態計算可以完全共用。

## 架構：三層

| 層 | 誰寫 | 內容 |
|---|---|---|
| 元件 | AI 填欄位 | 畫什麼：VS Code 開哪個檔、程式碼、輸出 |
| 通用動作 | AI 寫意思 | 在哪裡強調：畫圈・警告、底線・重點、箭頭、推鏡頭 |
| 皮膚 | 風格決定 | 用什麼筆、什麼顏色：粉筆、鉛筆、仿真 |

AI 只碰前兩層。以後加白板風格只要多一套皮膚，已寫好的分鏡不用改。

### VS Code 元件內部切成三塊

```
video_engine/components/vscode/
  model.js     狀態與版面：(描述, 動作, t) → 畫面狀態、各錨點的框。純函式，不碰畫布
  paint.js     畫面狀態 → 繪圖指令清單（框、字、線、圖示，顏色寫用途鍵）。純函式
  svg.js       指令清單 → SVG（仿真皮膚；黑板片與文章配圖用）
```

- 手帳的鉛筆皮膚不另寫：`board/runtime/components/vscode.js` 用 `Board.register('vscode', …)` 接進來，`measure`／`state`／`anchors` 呼叫 `model.js`，`draw` 把指令清單交給 `api.rect`／`api.text`／`api.ink` 畫（自然帶鉛筆抖動，也讓量測閘看得到每個框和字）。
- 黑板片接一層 `vscode.chalk.js`：從分鏡讀描述，呼叫 `model.js`＋`paint.js`＋`svg.js`，放進電腦畫面區。鏡頭推近、粉筆圈照 kit 原本的做法疊在上面。
- 文章配圖 `export_png.py`：同一份描述 → 一張只有元件的 HTML → Playwright 截圖（webwright 的 Playwright，不新增依賴）。

> 為什麼不讓兩邊各寫一份繪製：VS Code 畫面有十幾種區塊，兩份很快就會對不上（手帳改了設定頁，黑板沒跟上）。指令清單這一層讓「畫什麼、在哪裡」只算一次。

## 元件契約（登記進 `catalog.json`）

```json
"vscode": {
	"req": ["files"],
	"opt": ["open", "explorer", "panel", "theme_note"],
	"anchors": ["run", "gear", "tab:{file}", "L{n}", "panel", "panel:end", "term:cmd",
		"menu:{id}", "setting:{id}", "ext:{id}", "file:{name}"],
	"actions": {
		"open":      {"dur": 0.5, "req": ["file"]},
		"highlight": {"dur": 0.5, "req": ["lines"]},
		"run":       {"dur": 0.8, "opt": ["output"], "blocks": true},
		"print":     {"seq": "lines", "per": [0.2, 0.6], "req": ["lines"], "blocks": true},
		"input":     {"seq": "chars", "per": [0.08, 0.16], "req": ["text"], "blocks": true},
		"stop":      {"dur": 0.5},
		"menu":      {"dur": 0.5, "req": ["name"]},
		"page":      {"dur": 0.6, "req": ["name"]},
		"close":     {"dur": 0.4}
	}
}
```

- `files`：`{"score.c": ["#include <stdio.h>", …]}`。`open` 是一開始開著的檔。
- `panel`：`"output"`（Code Runner 輸出面板，唯讀）或 `"terminal"`（可以打字）。printf 片的重點就是這兩者的差別，所以兩種都要能畫。
- `menu`：目前只有 `gear`，內容沿用 `presets/vscode/gear_menu.json`。
- `page`：`settings`（含搜尋框與勾選項）、`extensions`（延伸模組列表）。內容放 `presets/vscode/` 下，分鏡用 `id` 指。
- 游標不在元件內：沿用現有 `cursor` 元件的 `move`／`click`，`on` 指到 `vscode:run` 這類錨點。
- 錨點全部由 `model.js` 算出，**不能依賴繪製**（手帳 COMPONENTS.md 第 7 條）。

### 分鏡裡怎麼寫

手帳 `scene.json` 直接用上面的格式。黑板 `storyboard.json` 的電腦畫面頁多一個結構化欄位，`draw`／`point` 留著給人讀：

```json
{"template": "screen", "screen": {
	"type": "vscode", "id": "vs",
	"files": {"score.c": ["…"]}, "open": "score.c", "panel": "output"
},
"lines": [
	{"say": "程式寫好了，我們按右上角這個三角形，用 Code Runner 跑跑看。",
	 "do": [{"act": "click", "target": "cursor", "on": "vs:run", "cue": "跑跑看"},
	        {"act": "circle", "target": "vs:run", "cue": "三角形", "tone": "warn"}]},
	{"say": "結果什麼都沒有出來，輸出面板只有一行 Running，程式就停在這裡。",
	 "do": [{"act": "run", "target": "vs", "output": ["[Running] cd \"c:\\Users\\student\\c_homework\\\" …"], "cue": "Running"}]}
]}
```

`board/COMPONENTS.md` 列 `catalog.json`、`compile.py` 為不可改，那是對「寫元件的人」（派工對象）的限制；這次改契約本身是設計決定，由 Claude 改、測試把關，派工時仍照原限制。

`cue` 是旁白裡的一段字，跟手帳同一個規則；黑板用 `story.json` 的逐字實測時間，比手帳的字數估算準。檢查共用 `compile.py` 的驗證邏輯（抽成可單獨呼叫的函式，黑板的 `storyboard.py` 也呼叫它），所以黑板分鏡寫錯一樣會被擋。

## 語氣統一

兩邊改用同一組語氣名稱，各風格的主題檔自己對應顏色：

| 語氣 | 意思 | 黑板（現有 TONE） | 手帳（notebook） | 仿真 |
|---|---|---|---|---|
| `ink` | 一般 | `w` | `text.body` | 前景白 |
| `muted` | 次要 | `m` | `text.muted` | 灰 |
| `accent` | 重點 | `y` | `text.accent` | 黃 |
| `warn` | 警告、錯 | `p` | `code.error` | 紅 |
| `ok` | 正確、解法 | `g` | 新增 `text.ok` | 綠 |
| `info` | 第二重點 | `b`（現名 `accent2`，留別名） | 新增 `text.info` | 藍 |

通用動作多一個選填參數 `tone`，預設 `accent`。仿真皮膚的顏色放新主題檔 `themes/vscode_dark.json`（Dark+ 的實際色碼），繪製器不寫色碼（專案不變量 6）。

## 驗收

1. **契約**：`catalog.json` 新增 `vscode`；`fixtures/vscode_min.scene.json`、`vscode_full.scene.json` 過 `compile.py`；故意寫錯的錨點、cue 會被擋（單元測試）。
2. **手帳**：兩份 fixture 過 `check.py` 量測閘（不越界、不重疊、決定性）。
3. **黑板**：printf 片的兩個電腦畫面改用元件＋分鏡描述，刪掉 `beats.js` 的 `vscodeMock()`；`anchor_check` 全過、`hyperframes check` 0 錯。畫面好壞交使用者看。
4. **配圖**：用元件重產文章的截圖 A、C、C2、E（成績版程式），交使用者比對真實截圖。
5. **決定性**：同一份描述匯出兩次 PNG 逐位元組相同。
6. **同步**：新檔照 `tools/video_skills_sync.py` 檢查 INCLUDE。

## 不做

分割視窗、搜尋面板、除錯面板、Git 面板、亮色主題、捲動動畫。真的碰到再加。其他元件的粉筆皮膚不在這次。

## 之後的元件路線（使用者 2026-10-29 決定全部要做，排程見 `plans/2026-10-29-component-roadmap.md`）

1. **黑板吃元件目錄**：黑板 `storyboard.json` 的所有頁都改成結構化描述，`beats.js` 變成通用的轉接層，不再每支片手寫。這是原「黑板套件」設計（`2026-10-25-chalk-kit-design.md`）該併進來的方向。
2. **手帳元件補粉筆皮膚**，依黑板片常用程度排：`list`、`pipeline`、`stack`、`vars`、`note`、`scale`。
3. **圖示元件擴充**：沙漏（等待）、鎖（唯讀）、鍵盤（輸入）、齒輪，兩種風格各畫一版，取代 `beats.js` 的手刻版。
4. **白板風格**：新增一套皮膚，驗證「分鏡不用改」。
5. **作業系統畫面**：Windows 設定視窗（`presets/win11/`）照 VS Code 的方式做成仿真＋鉛筆兩版。

## 參考

見 `docs/參考紀錄.md`「VS Code 畫面元件（2026-10-29 設計前調查）」：Remotion 生態的 VS Code 區塊與終端機模擬元件（取「畫面由狀態決定」「終端機獨立」兩個做法，不用 React），Carbon／Ray.so 只產程式碼框、不適用。
