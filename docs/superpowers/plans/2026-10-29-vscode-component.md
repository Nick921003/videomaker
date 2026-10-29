# VS Code 元件 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一個只靠分鏡描述就能畫出 VS Code 畫面的元件：手帳（鉛筆）、黑板（仿真）、文章配圖（PNG）三處共用。

**Architecture:** 元件拆成純函式三段：`model.js`（描述＋動作＋t → 狀態與錨點）、`paint.js`（狀態 → 繪圖指令，顏色只寫用途鍵）、`svg.js`（指令 → SVG 字串）。手帳用 `Board.register('vscode')` 把指令交給 `api.rect/text/ink`；黑板用 `vscode.chalk.js` 把 SVG 放進電腦畫面區；配圖用 Playwright 截圖。分鏡契約登記在 `board/catalog.json`，黑板分鏡也走同一個 `Compiler` 驗證。

**Tech Stack:** 純 JS（classic script，同時可被 node `require`），Python 3（unittest），Node 22（測試用），Playwright（webwright 的 venv，已存在），HyperFrames 0.8.81。

**Spec:** `docs/superpowers/specs/2026-10-29-vscode-component-design.md`

## Global Constraints

- 縮排 Tab；註解中文、稀疏，只寫為什麼。
- 不新增第三方依賴（Python：Pillow、fontTools、python-pptx；Playwright 用 `~/.local/share/pipx/venvs/webwright/bin/python`）。
- 元件 JS **純函式**：禁用 `Math.random`、`Date.now`、`performance.now`、`new Date(`。
- 元件 JS **不寫色碼**：顏色只從 theme 檔來（`themes/vscode_dark.json`、`themes/notebook.json`、黑板 kit 的 TONE）。
- 錨點只由 `model.js` 算，不依賴繪製；所有 catalog 宣告的錨點都要有框（不變量 2 的精神：缺框＝動作靜默失效）。
- 任何內容不得畫出元件框外；容不下先縮字級，再截斷加「…」，不准溢出。
- 決定性：同一份描述兩次輸出逐位元組相同。
- Python 一律 `.venv/bin/python`；全套測試 `.venv/bin/python -m unittest discover -s tests -t .`。
- TTS 與影片渲染不在本機跑（Colab）；本計畫的視覺驗收交使用者，不自行截圖評價。
- JS 模組樣式：`(function (g) { 'use strict'; … if (typeof module !== 'undefined') module.exports = X; else g.X = X; })(this);`
- 語氣名稱固定六個：`ink` `muted` `accent` `warn` `ok` `info`。

## Review Focus

1. **程式很長（> 編輯器可見行數）**：預期自動捲到被 `highlight` 的行，而不是畫出框外 → Task 3 測 40 行程式＋highlight L35，錨點 `L35` 在編輯器區內。
2. **檔名或輸出很長（含中文路徑）**：預期截斷加「…」，不溢出 → Task 4 測 200 字的 `[Running]` 行，所有 text 指令的 x+w ≤ 面板右緣。
3. **手帳縮放後字太小**：VS Code 自然尺寸大，放進手帳半版會低於量測閘的縮放下限 → Task 6 的 `vscode_full` fixture 用半版版面跑 `check.py`，失敗就調 `model.layout` 的 `size` 預設，不改閘。
4. **分鏡的 cue 不在旁白裡、或動作指到不存在的錨點**（例：`vs:tab:hello.c` 但 files 沒有 hello.c）：預期黑板 `storyboard.py` 直接報錯 → Task 8 測。
5. **同一句裡先 `run` 再 `input`（終端機面板）**：預期 input 字元接在 run 的輸出之後、時間不重疊 → Task 3 測狀態序列。

---

## 檔案地圖

| 檔案 | 動作 | 職責 |
|---|---|---|
| `video_engine/themes/tones.json` | 新增 | 六個語氣 → 各皮膚的顏色鍵（唯一來源） |
| `video_engine/themes/vscode_dark.json` | 新增 | 仿真皮膚色碼（Dark+；值取自 `beats.js` 現有 `VS` 物件） |
| `video_engine/themes/notebook.json` | 修改 | 加 `text.ok`、`text.info` |
| `video_engine/board/catalog.json` | 修改 | 新增 `vscode` 型別；`circle/underline/arrow` 加選填 `tone` |
| `video_engine/board/compile.py` | 修改 | `{file}` 錨點樣式、vscode 預設檔內嵌、`tone` 驗證 |
| `video_engine/board/presets/vscode/{settings,extensions}.json` | 新增 | 設定頁、延伸模組頁內容 |
| `video_engine/board/fixtures/vscode_{min,full}.scene.json` | 新增 | 契約與量測閘的範例 |
| `video_engine/components/vscode/model.js` | 新增 | 版面、狀態、錨點 |
| `video_engine/components/vscode/paint.js` | 新增 | 繪圖指令 |
| `video_engine/components/vscode/svg.js` | 新增 | 指令 → SVG 字串 |
| `video_engine/components/vscode/export_png.py` | 新增 | 描述 → PNG |
| `video_engine/components/vscode/README.md` | 新增 | 給寫分鏡的人：欄位、動作、錨點、範例 |
| `video_engine/board/runtime/components/vscode.js` | 新增 | 手帳轉接 |
| `video_engine/board/runtime/player.js` | 修改 | 通用標記吃 `tone` |
| `video_engine/board/build.py` | 修改 | 把 `video_engine/components/` 帶進播放器 |
| `video_engine/explainer/chalk/kit/vscode.chalk.js` | 新增 | 黑板轉接 |
| `video_engine/explainer/storyboard.py` | 修改 | `screen` 欄位驗證並寫進 `screens.json` |
| `tests/test_vscode_component.py` | 新增 | 用 node 跑 JS 純函式並斷言 |
| `tests/js/vscode_probe.js` | 新增 | node 端：載入三個模組，依參數吐 JSON |

---

### Task 1: 語氣統一與仿真主題

**Files:**
- Create: `video_engine/themes/tones.json`, `video_engine/themes/vscode_dark.json`
- Modify: `video_engine/themes/notebook.json`, `video_engine/board/catalog.json`（`generic_actions` 的 circle／underline／arrow 加 `"opt": [..., "tone"]`）, `video_engine/board/compile.py`, `video_engine/board/runtime/player.js`, `video_engine/out/vscode_printf_chalk/lib/kit/kit.js`（TONE 加 `info`→`b`、`ink`→`w`，`accent2` 留別名）
- Test: `tests/test_board_compile.py`, `tests/test_board_build.py`

**Interfaces:**
- Produces: `tones.json` = `{"tones": ["ink","muted","accent","warn","ok","info"], "board": {tone: notebook 鍵}, "vscode": {tone: vscode_dark 鍵}, "chalk": {tone: kit 色字母}}`；`vscode_dark.json` 鍵沿用 `beats.js` 的 `VS` 物件名（`title, fg, dim, side, sel, edit, kw, str, …`）加 `ann.accent/warn/ok/info`；`compile.TONES`（從 tones.json 讀的 tuple）。

- [ ] **Step 1: 寫失敗測試**
  - `test_tones_各皮膚都對應六個語氣`：`tones.json` 的 board／vscode／chalk 三組鍵集合都等於 `tones`；board 的值都是 notebook.json 存在的鍵；vscode 的值都在 vscode_dark.json。
  - `test_通用標記的未知語氣要擋`：scene 裡 `{"act":"circle","target":"a","tone":"loud"}` → `compile_scene` raise ValueError，訊息含 `loud`。
  - `test_通用標記沒寫語氣預設accent`：編譯後該動作 `args["tone"] == "accent"`。
- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_board_compile -k 語氣` → FAIL
- [ ] **Step 3: 實作**：建兩個 theme 檔；`compile.py` 在 `collect_actions` 對 circle/underline/arrow 補預設並驗證；`player.js` 畫標記時用 `api.color(TONES.board[tone])`（tones 經 `build.py` 一起放進 `board_data.js`）。
- [ ] **Step 4:** 同上指令 PASS；全套 `tests.test_board_*` PASS（既有 fixture 沒寫 tone，畫面不變）。
- [ ] **Step 5: Commit** `feat(board): 通用標記語氣與仿真 VS Code 主題`

### Task 2: catalog 的 `vscode` 契約與預設檔

**Files:**
- Modify: `video_engine/board/catalog.json`, `video_engine/board/compile.py`
- Create: `video_engine/board/presets/vscode/settings.json`, `extensions.json`, `video_engine/board/fixtures/vscode_min.scene.json`, `vscode_full.scene.json`
- Test: `tests/test_board_compile.py`

**Interfaces:**
- Produces: catalog 型別 `vscode`（欄位與動作照 spec「元件契約」一節，`opt` 再加 `"menus"`、`"pages"`：要用到的預設名清單）；錨點樣式 `run` `gear` `panel` `panel:end` `term:cmd` `L{n}` `tab:{file}` `file:{file}` `{key}`；編譯後物件帶 `_presets: {name: 預設內容}`，預設裡每個項目有 `id`（供 `{key}`）。
- 預設檔格式：`settings.json` = `{"search": "", "items": [{"id": "run_in_terminal", "title": "Code-runner: Run In Terminal", "desc": "…", "check": false}, …]}`；`extensions.json` = `{"items": [{"id": "code_runner", "name": "Code Runner", "author": "Jun Han", "desc": "…"}]}`。真實文字以 `docs/experiments/2026-10-22-vscode-printf/截圖/` 核對。

- [ ] **Step 1: 寫失敗測試**
  - `test_vscode_min_能編譯`、`test_vscode_full_能編譯`（full 含 open、highlight、run、print、input、menu gear、page settings、close、cursor click `vs:run`、circle `vs:run_in_terminal`——設定頁項目 id，以 `{key}` 解析）。
  - `test_vscode_tab錨點指到沒有的檔要擋`：`vs:tab:hello.c`，files 只有 score.c → ValueError 含 `tab:hello.c`。
  - `test_vscode_L錨點超出行數要擋`：5 行程式指 `vs:L9` → ValueError 含「超出範圍」。
  - `test_vscode_未知預設要擋`：`"pages": ["debug"]` → ValueError 含 `debug`。
- [ ] **Step 2:** 跑 → FAIL
- [ ] **Step 3: 實作**：`check_anchor` 支援 `{file}`（比對 `obj["files"]` 的鍵）；`anchor_limit` 對 vscode 的 `L{n}` 用目前 open 檔（或任何檔的最大行數）；`normalize_objects` 對 vscode 讀 `presets/vscode/<name>.json` 填 `_presets`。
- [ ] **Step 4:** PASS；`tests.test_board_*` 全 PASS。
- [ ] **Step 5: Commit** `feat(board): vscode 元件契約、預設檔與範例`

### Task 3: `model.js`——版面、狀態、錨點

**Files:**
- Create: `video_engine/components/vscode/model.js`, `tests/js/vscode_probe.js`, `tests/test_vscode_component.py`

**Interfaces:**
- Consumes: Task 2 的物件格式（含 `_presets`）與編譯後動作格式 `{act, target, obj, args, n, t0, t1}`（見 `board/COMPONENTS.md`）。
- Produces（全域 `VSCodeModel`）：
  - `layout(desc, size=[1600, 1000]) -> {w, h, regions: {title, activity, explorer, tabs, editor, panel, status}}`（每個 region `{x,y,w,h}`）
  - `state(desc, acts, t, size) -> {open, highlight: [n...], scrollTop, panel: {kind, lines: [str], input: str, running: bool}, menu: name|null, page: name|null}`
  - `anchors(desc, st, size) -> {name: {x,y,w,h}}`，名稱不含物件 id
- `tests/js/vscode_probe.js` 用法：`node tests/js/vscode_probe.js <cmd> <json>`，`cmd` ∈ `layout|state|anchors|ops|svg`，stdout 印 JSON。Python 測試以 subprocess 呼叫，找不到 node 就 `skipTest`。

- [ ] **Step 1: 寫失敗測試**（`tests/test_vscode_component.py`，描述用 `vscode_full` fixture 的物件）
  - `test_每個宣告的錨點都有框`：對 full 描述在 t = 0、中段、結尾各取 anchors，`run gear panel panel:end term:cmd L1..L{行數} tab:{每個檔} file:{每個檔}` 全在，且開了 menu／page 的時段內其項目 id 也在。
  - `test_錨點都在元件框內`：所有框 `0 ≤ x, x+w ≤ w`（y 同理）。
  - `test_版面不隨時間改變`：`layout` 對同一描述兩次結果相同；state 的 t 不影響 layout。
  - `test_長程式自動捲到高亮行`：40 行、`highlight lines [35]` 之後的 t，`anchors["L35"]` 在 `regions.editor` 內。
  - `test_run後input接在輸出之後`：terminal 面板，run(output 2 行) 接 input "85"；input 時段的 state `panel.lines[-1]` 以 run 的最後輸出行開頭並逐字長出 "8"、"85"。
- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_vscode_component` → FAIL
- [ ] **Step 3: 實作** `model.js`；版面比例照 `beats.js` 的 `vscodeMock()`（活動列、側欄、分頁列、編輯器、面板、狀態列的相對寬高抽成以 `size` 計算的關係，不寫死像素）。
- [ ] **Step 4:** PASS
- [ ] **Step 5: Commit** `feat(components): VS Code 元件的版面與狀態模型`

### Task 4: `paint.js` 與 `svg.js`——繪圖指令與仿真皮膚

**Files:**
- Create: `video_engine/components/vscode/paint.js`, `video_engine/components/vscode/svg.js`
- Modify: `tests/js/vscode_probe.js`, `tests/test_vscode_component.py`

**Interfaces:**
- Consumes: `VSCodeModel.layout/state`。
- Produces：
  - `VSCodePaint.ops(desc, st, t, size) -> [op]`，`op` 為 `{op:'rect', x,y,w,h, fill?:key, stroke?:key}`｜`{op:'text', str, x, y, size, mono, color:key, align?, w}`｜`{op:'line', pts:[[x,y]...], color:key, width}`｜`{op:'icon', name:'run'|'stop'|'gear'|'files'|'search'|'ext'|'file', x,y,s, color:key}`；`key` 一律是 `vscode_dark.json` 的鍵。程式碼上色用簡單的 C 詞法（關鍵字、字串、數字、函式名），不做完整解析。
  - `VSCodeSVG.render(ops, theme, size) -> string`（完整 `<svg>` 字串；字型 `'JetBrains Mono', 'Huninn', monospace` 與 `'Huninn', sans-serif`）。
- [ ] **Step 1: 寫失敗測試**
  - `test_指令顏色都是主題鍵`：所有 op 的顏色欄位都在 `vscode_dark.json`。
  - `test_長輸出截斷不溢出`：200 字 `[Running]` 行 → 所有 text op `x + w ≤ panel.x + panel.w`，且該行以「…」結尾。
  - `test_svg決定性`：同描述同 t 兩次 render 字串相同；字串中不含 `NaN`、`undefined`。
  - `test_元件不寫死色碼也不讀時鐘`：`video_engine/components/` 下所有 .js 不含 `#rgb` 色碼與禁用時鐘 API（沿用 `test_board_build` 的兩個 regex）。
- [ ] **Step 2:** FAIL
- [ ] **Step 3: 實作** 兩個模組。
- [ ] **Step 4:** PASS
- [ ] **Step 5: Commit** `feat(components): VS Code 繪圖指令與仿真 SVG`

### Task 5: 文章配圖 `export_png.py`

**Files:**
- Create: `video_engine/components/vscode/export_png.py`
- Test: `tests/test_vscode_component.py`

**Interfaces:**
- Produces：`export_png.py <desc.json> <out.png> [--t 秒] [--size 1600x1000]`；`desc.json` = 單一 vscode 物件，或 `{"object": {...}, "do": [動作...]}`（動作時間以出現順序每個 1 秒排，`--t` 不給就取最後狀態）。函式 `render_png(desc: dict, out: str, t: float | None, size: tuple[int, int]) -> None`。
- 實作要點：產一個暫時 HTML（內嵌三個 JS 與 `vscode_dark.json`、字型用 `video_engine/out/vscode_printf_chalk/assets/fonts/` 的 woff2，以相對專案根的路徑讀），Playwright 開 `device_scale_factor=1`、等 `document.fonts.ready` 後截圖。
- [ ] **Step 1: 寫失敗測試** `test_png兩次輸出逐位元組相同`（Playwright 不在就 skip）：同描述輸出兩次 md5 相同，尺寸等於 size。
- [ ] **Step 2:** 用 webwright 的 python 跑 → FAIL
- [ ] **Step 3: 實作**
- [ ] **Step 4:** PASS
- [ ] **Step 5: Commit** `feat(components): VS Code 描述匯出 PNG`

### Task 6: 手帳轉接

**Files:**
- Create: `video_engine/board/runtime/components/vscode.js`
- Modify: `video_engine/board/build.py`（把 `video_engine/components/**/*.js` 複製到 `<out>/components/` 並在元件之前載入；`vscode_dark.json` 不帶，手帳用 notebook）、`tests/test_board_build.py`、`video_engine/board/COMPONENTS.md`（加 vscode 一節）
- Test: `tests/test_board_build.py`

**Interfaces:**
- Consumes：`VSCodeModel`、`VSCodePaint`、`tones.json`。
- Produces：`Board.register('vscode', {measure, state, draw, anchors})`；`draw` 把 op 映射到 `api.rect`／`api.text`／`api.ink`（icon 用 `api.ink` 折線）。vscode 色鍵 → notebook 鍵的對應寫在 `tones.json` 新增的 `"vscode_to_board"` 段（例 `edit → code.bg`、`kw → code.highlight`、`fg → code.normal`），每個 vscode 鍵都要有對應。
- [ ] **Step 1: 寫失敗測試**
  - `test_產出目錄帶共用元件`：build 後 `components/vscode/model.js` 存在，player.html 在 `runtime/components/vscode.js` 之前載入它。
  - `test_vscode色鍵都對到手帳主題`：`vscode_to_board` 涵蓋 vscode_dark 全部鍵，值都在 notebook.json。
- [ ] **Step 2:** FAIL
- [ ] **Step 3: 實作**
- [ ] **Step 4:** PASS；再跑量測閘：
  ```bash
  P=~/.local/share/pipx/venvs/webwright/bin/python
  for f in vscode_min vscode_full; do
  	.venv/bin/python video_engine/board/compile.py video_engine/board/fixtures/$f.scene.json /tmp/$f.tl.json &&
  	.venv/bin/python video_engine/board/build.py /tmp/$f.tl.json /tmp/$f.player &&
  	$P video_engine/board/check.py /tmp/$f.player || echo FAIL $f
  done
  ```
  預期：沒有 `FAIL`。縮放下限不過就調 `model.layout` 的 `size` 預設與字級（Review Focus 3），不改閘。
- [ ] **Step 5: Commit** `feat(board): 手帳接上 VS Code 元件（鉛筆皮膚）`

### Task 7: 黑板分鏡的 `screen` 欄位與驗證

**Files:**
- Modify: `video_engine/explainer/storyboard.py`, `tests/test_storyboard.py`

**Interfaces:**
- Consumes：`board/compile.py` 的 `Compiler`、`load_catalog`。
- Produces：分鏡頁 `{"template": "screen", "screen": <vscode 物件>, "lines": [{"say", "do": [...]}]}`；`storyboard.build()` 對有 `screen` 的頁組出暫時 scene（objects = screen 物件＋`{"id":"cursor","type":"cursor"}`，每句一個 beat，`say` 當旁白）交 `Compiler(...).run()` 驗證；`screens.json` 每頁多 `"screen"` 與 `"do": {句號: [動作...]}`。沒有 `screen` 的舊頁照舊（向下相容）。
- [ ] **Step 1: 寫失敗測試**
  - `test_screen頁寫進screens_json`：輸出含 screen 物件與按句號分的 do。
  - `test_screen頁cue不在旁白要擋`：cue「跑跑看囉」不在 say → ValueError。
  - `test_screen頁錨點不存在要擋`：`vs:tab:hello.c` → ValueError。
  - `test_舊的screen頁沒有screen欄位照舊`：輸出與現在一致。
- [ ] **Step 2:** FAIL
- [ ] **Step 3: 實作**
- [ ] **Step 4:** PASS
- [ ] **Step 5: Commit** `feat(chalk): 分鏡的電腦畫面頁可寫元件描述並驗證`

### Task 8: 黑板轉接 `vscode.chalk.js`

**Files:**
- Create: `video_engine/explainer/chalk/kit/vscode.chalk.js`（`sync_film` 或片子的 `lib/` 複製方式照現有 kit.js 做法；片子 `index.html` 加一行 script）
- Modify: `video_engine/out/vscode_printf_chalk/index.html`（載入共用元件三檔與 vscode.chalk.js，`render` 對有 `screen` 描述的電腦畫面頁呼叫它）
- Test: `tests/test_vscode_component.py`（node 端可測的部分）

**Interfaces:**
- Consumes：`VSCodeModel`、`VSCodePaint`、`VSCodeSVG`、`tones.json`；`story.json` 的逐字時間（index.html 現有 `api.span(i, 字串)`）；`screens.json` 的 `screen`／`do`。
- Produces：`ChalkVSCode.mount(scr, page, api) -> {render(t)}`。把分鏡動作轉成元件動作格式：每個動作 `t0 = api.span(句號, cue).t0`（cue 沒給用句首）、`t1 = t0 + catalog 的 dur`（序列動作照 `per` 與字數算）；cursor 的 move/click 與 circle/underline/arrow 由這層畫（游標樣式沿用 `vscodeMock` 的 `cursor()`，圈用仿真皮膚的 `ann.<tone>`）。另外輸出 `anchorsAt(t)` 給鏡頭推近用。
- [ ] **Step 1: 寫失敗測試** `test_黑板轉接的動作時間取自逐字時間`：給假的 span 函式（cue「三角形」在 2.0 秒），轉出的 circle 動作 `t0 == 2.0`、`t1 == 2.7`（circle dur 0.7）。
- [ ] **Step 2:** FAIL
- [ ] **Step 3: 實作**
- [ ] **Step 4:** PASS
- [ ] **Step 5: Commit** `feat(chalk): 黑板接上 VS Code 元件（仿真皮膚）`

### Task 9: printf 片改用元件

**Files:**
- Modify: `docs/experiments/2026-10-22-vscode-printf/video/chalk-story/storyboard.json`（兩個電腦畫面頁：開場第 1–4 句、後段終端機段，把 `draw`／`point` 寫成 `screen`＋`do`，文字保留給人讀）
- Modify: `video_engine/out/vscode_printf_chalk/beats.js`（刪 `vscodeMock`、`openBeat`、`screenBeat` 及只有它們用的函式）

- [ ] **Step 1:** 改分鏡；`.venv/bin/python video_engine/explainer/storyboard.py docs/experiments/2026-10-22-vscode-printf/video/chalk-story` → 無錯誤。
- [ ] **Step 2:** `sync_film.py`、`stamp.py`、`fonts.py`（流程同 b24），然後：
  ```bash
  cd video_engine/out/vscode_printf_chalk && .venv/bin/python tools/anchor_check.py && npx --yes hyperframes@0.8.81 check
  ```
  預期：anchor_check 全過、check 0 錯。
- [ ] **Step 3:** `grep -c "vscodeMock\|openBeat\|screenBeat" beats.js` → 0。
- [ ] **Step 4:** 打包上 Colab 出 b25 審片版（流程同記憶 render-off-local），**交使用者看**兩段電腦畫面。旁白未改，不必重跑 TTS。
- [ ] **Step 5: Commit** `refactor(chalk): printf 片電腦畫面改用 VS Code 元件`

### Task 10: 文章配圖、文件、同步

**Files:**
- Create: `docs/experiments/2026-10-22-vscode-printf/截圖/descs/{A,C,C2,E}.json`、對應 PNG
- Create: `video_engine/components/vscode/README.md`（欄位、動作、錨點、三種用法各一個範例）
- Modify: `tools/video_skills_sync.py`（INCLUDE 加 `video_engine/components`、`video_engine/themes/tones.json`、`vscode_dark.json`、`tests/test_vscode_component.py`、`tests/js/`）、`docs/參考紀錄.md`（狀態改「已參考實作」）

- [ ] **Step 1:** 寫四份描述，`export_png.py` 產圖；**交使用者**與舊截圖並排比對。
- [ ] **Step 2:** `python3 tools/video_skills_sync.py`（不推）→ 無擋下項目。
- [ ] **Step 3:** 全套測試 `.venv/bin/python -m unittest discover -s tests -t .` → OK。
- [ ] **Step 4:** 先跑 `sync-docs`，再 Commit `docs(components): VS Code 元件說明、文章配圖與同步清單`
