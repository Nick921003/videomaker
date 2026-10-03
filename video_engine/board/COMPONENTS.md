# 元件撰寫契約

新增或修改 `runtime/components/*.js` 前必讀。規則來自 `docs/superpowers/specs/2026-10-03-board-runtime-design.md`。

## 不可改的檔案

`catalog.json`、`compile.py`、`build.py`、`check.py`、`runtime/core.js`、`runtime/layout.js`、`runtime/player.js`、`examples/*.json`。
覺得非改不可 → 停下來回報理由，不要自己改。

## 介面

每個元件一個檔案，classic script，IIFE 包起來，呼叫 `Board.register(type, impl)`。`type` 必須等於 `catalog.json` 的型別名。

```js
'use strict';
(() => {
	Board.register('cells', {
		measure(obj, api, acts) { return {w, h}; },        // 自然尺寸（縮放前），整片固定
		state(obj, acts, t, api) { return {...}; },          // t 時刻的狀態，純函式
		draw(api, obj, st, t) { },                           // 在本地座標 [0,w]×[0,h] 內畫
		anchors(obj, st, api) { return {name: {x,y,w,h}}; }, // 本地座標；名稱不含物件 id
		overlay(api, obj, st, t, world) { },                 // 選填：世界座標，畫跨物件的東西（飛行字元）
	});
})();
```

- `obj`：timeline 裡的物件（scene.json 原樣＋編譯器補的 `_max_text` 等底線欄位）。
- `acts`：**跟這個物件有關的所有動作**，依時間排序。包含 `target` 是本物件的，以及參數錨點指向本物件的
  （例：`output` 會收到 `scan` 動作，因為該動作的 `args.to` 是 `out:end`；`note` 會收到 `fill`，因為 `args.from` 指向它）。
  用 `a.obj === obj.id` 區分「我是 target」。
- 動作物件：`{scene, beat, act, target, obj, args, n, t0, t1}`。`n` 是序列項目數（非序列為 null）。
  **序列第 k 項（0 起算）的時段 = `[t0 + k·per, t0 + (k+1)·per]`，`per = (t1 - t0) / n`。**
- `world.anchor('out:end')` → 該錨點此刻的世界座標框，或 null。`world.alpha(id)`、`world.placement(id)`。

## 硬規則（`tests/test_board_build.py` 與 `check.py` 會擋）

1. **純函式**：只依賴參數。禁用 `Math.random`、`Date.now`、`performance.now`、`new Date(`。游標閃爍用 `Math.floor(t * 2) % 2`。
2. **不寫色碼**：一律 `api.color('鍵')`。可用的鍵（`themes/notebook.json`）：
   `canvas.bg` `canvas.grid` `canvas.margin` `card.fill` `card.edge` `text.title` `text.body` `text.muted` `text.accent`
   `code.bg` `code.normal` `code.muted` `code.highlight` `code.error` `effects.pencil` `effects.highlight`。
3. **尺寸以整片最大內容量測**：輸出框用 `obj._max_text`，清單含之後才 `append` 的列，終端機含整場最多的行數。
   `measure` 的回傳值不得隨 t 改變；內容增長不准推動版面。
4. **draw 不出界**：`draw` 只畫在 `[0,w]×[0,h]`。跨物件的飛行字元畫在 `overlay`。
5. **文字一律走 `api.text`／`api.write`，框線走 `api.rect`**（它們會記錄框給量測閘）。不要直接 `ctx.fillText`。
   純裝飾線條用 `api.ink`。填色背景可直接 `ctx.fillRect`，但顏色仍用 `api.color`。
6. 鉛筆抖動只在描線中（`p < 1`），描完要穩定——`api.ink` 已處理，傳固定 `seed`（`Board.seed(obj.id + '…')`）即可。
7. **錨點只能由 `state` 算出**：`anchors()` 不得依賴 `draw()` 寫進 state 的東西；`draw()` 不得改寫 `st`。
   runtime 會在載入時不繪製就查錨點（鏡頭預算），量測閘也會這樣驗。
8. **動作留下的標記只活在該場景**：指標、停止圈這類由動作產生的標記，從 `api.sceneEnd(a.scene)` 起 0.4 秒淡出。
   物件本身的內容（格子的值、輸出文字）不受影響。

## api（`runtime/core.js`）

| 函式 | 說明 |
| --- | --- |
| `api.text(str, x, y, {size, weight, mono, color, align, alpha, role})` | `y` 是垂直中線；回傳寬度 |
| `api.write(str, x, y, p, opts)` | 手寫揭露，`p` 0→1 |
| `api.measure(str, {size, weight, mono})` | `{w, h}` |
| `api.ink(points, p, {color, width, seed})` | 鉛筆折線 |
| `api.rect(x, y, w, h, p, {color, fill, width, seed, role})` | 鉛筆框；`fill` 為背景色 |
| `api.ellipse(cx, cy, rx, ry, p, {color, seed})` | 強調圈，預設 accent |
| `api.hatch(x, y, w, h, seed)` | 未知內容的淡斜線 |
| `api.pointer(x, y, size, p)` | A＋C 的讀取指標（小圈＋箭頭） |
| `api.fly(str, from{x,y}, to{x,y}, p, {size, color, lift})` | 弧線飛行字元，`p` 0→1 |
| `api.phase(t, a, b)`、`api.ease`、`api.clamp`、`api.mix`、`Board.seed(str)` | 數學 |

## 字級（1080p 自然尺寸）

標題 80／內文 48／標籤 36／小字 30／程式 42／格內字元 64／輸出字 80／大數字 118。字型由 api 決定，元件只傳 `mono: true`。

## 視覺參考

A＋C 已接受版：`/home/pjw92/projects/videomaker/video_engine/out/state_change_ac_20261001/movie.html`（720p，數值乘 1.5 即 1080p）。
對照函式：`row()`＝cells、`pointer()`＝`api.pointer`、`outputBox()`＝output、`codeScene`／C 段深色面板＝code、
`comparison` 三欄＝metrics、`copies`／`scans` 的飛行字元＝fill／scan 的 overlay、`termination_note` 的圈＝stop。

## 各元件規格

### cells
- 屬性：`count`、`label`、`values`（初始值，null＝未知）、`tail`（右側「其餘」框的文字，無則不畫）、`accent`（用強調色畫的值，例 `["\\0"]`）。
- 版面（上到下）：標籤列（小字 36、muted）→ 指標區（高 ≈ 0.55 格）→ 格子列（格寬 150、間距 26、高 = 格寬 × 1.09）→
  停止註記列（若有 `stop` 帶 `note`）→ 每個 `brace` 一列（高 76）。右側：短連接線＋tail 框（寬 = 格寬 × 1.65，內畫「…」與 tail 文字）。
- 已知格：`card.fill` 底、鉛筆框、格內字元置中（mono 64，accent 值用 `text.accent`）。未知格：`api.hatch`。
- `fill`：第 k 項，字元從 `args.from` 錨點中心飛到第 `start+k` 格中心（overlay），該項結束時格子變成已知。
- `point`：指標在 dur 內滑到 `index` 上方。指標自第一個 point／scan／stop 起出現，之後一直在。
- `scan`：第 k 項前 40% 指標滑到第 `lo+k` 格，後 60% 該格字元（`args.chars[k]`）飛到 `args.to` 錨點中心（overlay，強調色）。
- `stop`：指標滑到 `index`，該格畫強調圈（之後一直在），`note` 文字以強調色寫在該格正下方的停止註記列。
- `brace`：第 j 個 brace 畫在第 j 個 brace 列：範圍左緣到右緣的鉛筆線（第一個用強調色，其餘 pencil）＋線下置中標籤。
- 錨點：`label`、`i{n}`（第 n 格的框）。

### output
- 屬性：`label`；編譯器補 `_max_text`（整片最長文字）。
- 卡片：`card.fill` 底鉛筆框，左上小標籤（muted 30），文字 mono 80。寬 = max(440, `_max_text` 寬 + 120)，高 150。
- 文字**靠左成長、最終置中**：起點 x = (w − `_max_text` 寬) / 2。
- 內容：每個 `args.to` 指向本物件的 `scan`，第 k 項結束時接上 `args.chars[k]`；`set`（target 是本物件）在 t1 時換成 `args.text`。
- 錨點：`text`（目前文字的框；空字串時為起點處寬 0 的框）、`end`（目前文字尾端、寬一個字的框，下一個字落在這裡）。

### code
- 屬性：`lines`、`caption`、`footer`。深色面板 `code.bg` 直接填色（不畫鉛筆框，但要 `api.record` 一個 panel 框：用 `api.rect(..., {fill, color: api.color('code.bg')})` 亦可）。
- caption 在上（`code.muted` 36）、程式行 mono 42（`code.normal`）、footer 在下（`code.muted` 36）。左右內距 56。
- `highlight`：`args.line`（1 起算）那行底下鋪 `code.highlight` 色帶，dur 內淡入，之後一直在。
- 錨點：`L{n}`（1 起算）。

### metrics
- 屬性：`items: [{label, value, note}]`，橫排等寬三欄，欄寬 = 三欄內容最大寬 + 80。
- 每欄：label（muted 36）→ value（118、weight 600、`text.body`）→ note（muted 30）。
- `reveal`：有 `args.index` 只揭露該項；沒有就依序揭露全部（序列）。揭露前不畫（但空間保留）。value 用 `api.write`。
- 錨點：`m{n}`。

### terminal
- 屬性：`title`（預設「終端機」）、`prompt`（預設 `C:\>`）。深色面板 `code.bg`；上方標題列高 56（`code.muted` 30），下方內容區。
- 每行 mono 34、行高 50、內距 36。提示字元 `code.muted`，指令與輸出 `code.normal`，`print` 的 `style: "error"` 用 `code.error`。
- `type`：新的一行出現「prompt＋空白」，`args.text` 逐字打出（每項＝一字），打字中游標實心，閒置時以 `Math.floor(t * 2) % 2` 閃爍。
- `print`：`args.lines` 逐行出現（每項＝一行，0.15 秒淡入）；全部印完後下一行出現新的空白 prompt（帶游標）。
- `restart`：dur 前 40% 內容淡出，中段在內容區置中顯示 `args.note`（`code.muted`），最後 30% 出現全新的空白 prompt；之前的行全部清掉。
- 尺寸：模擬整片，以「兩次 restart 之間最多同時存在的行數（含最後的空 prompt）」與最長一行決定；最小寬 760。
- 錨點：`cmd`（最近一次 `type` 的指令文字框；尚未打字時為 prompt 尾端寬 0 框）、`line{n}`（本次 session 第 n 行，0 起算）。

### list
- 屬性：`title`、`rows`。標題（muted 34）在上；每列一張 `card.fill` 鉛筆框卡片，mono 34，列高 74、列距 14、左右內距 28，右側保留 70 放結果符號。
- `append`：新列接在最後，dur 內 `api.write` 寫出；之前不畫（空間保留）。
- `walk`：每項＝一列。`args.item`（例 "gcc"）畫成小標籤（強調色框＋文字），在卡片左側逐列下移：
  第 k 項前 35% 標籤移到第 k 列，後段揭曉結果——非 `found` 的列右側寫「✗」（muted）且列文字轉 muted；
  `found` 那列右側寫「✓」（強調色）。沒有 `found` 時每列都是 ✗。結果保留到下一次 `walk` 開始時清除。
- 錨點：`title`、`r{n}`（第 n 列卡片）。

## 驗收指令

```bash
S=$(mktemp -d)
.venv/bin/python video_engine/board/compile.py video_engine/board/examples/<ex>.scene.json $S/tl.json --gaps /dev/null
.venv/bin/python video_engine/board/build.py $S/tl.json $S/out
~/.local/share/pipx/venvs/webwright/bin/python video_engine/board/check.py $S/out --partial
.venv/bin/python -m unittest tests.test_board_build tests.test_board_compile
```

`check.py` 必須印出「量測閘：取樣 N 格，通過」。**不准為了通過而修改 check.py、預期值或範例 JSON。**
