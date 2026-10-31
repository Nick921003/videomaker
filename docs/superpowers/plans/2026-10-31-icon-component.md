# 圖示元件＋黑板吃分鏡（最小版） Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 31 個圖示做成 `icon` 元件，形狀只寫一份，鉛筆、粉筆、仿真三種皮膚共用；黑板的置中／雙欄頁也吃分鏡；一份分鏡同時出手帳版和黑板版展示片。

**Architecture:** 圖示形狀放在 `components/icon/shapes.js`，純函式，在 100×100 的格子裡定義筆畫，陣列順序就是筆順。分鏡契約登記在 `board/catalog.json`，內容有意思對照表、筆畫數、動作，驗證都在 `board/compile.py`。通用標註框 `callout` 的擺放規則也是純函式，放在 `components/callout/callout.js`，手帳播放器和黑板轉接共用。黑板新增 `board.chalk.js`，讀 `storyboard.py` 產生的 `objects.json` 來排版、排時間。格子算式抽成純函式 `board_tpl.js`，讓頁面和檢查共用。手帳版由 `storyboard_to_scene.py` 從同一份 `storyboard.json` 轉出。

**Tech Stack:** 純 JS（classic script，也可以用 node `require`）、Python 3（unittest）、Node 22（測試用）、Playwright（webwright 的 venv）、HyperFrames 0.8.81。

**Spec:** `docs/superpowers/specs/2026-10-31-icon-component-design.md`

## Global Constraints

- 縮排用 Tab。註解寫中文，寫得稀疏，只寫為什麼。不新增第三方依賴。
- 元件 JS 必須是**純函式**：不准用 `Math.random`、`Date.now`、`performance.now`、`new Date(`。`shapes.js`、`callout.js`、`board_tpl.js` 不碰 DOM。
- 顏色只走 `themes/tones.json` 的六個語氣（`ink` `muted` `accent` `warn` `ok` `info`）；沒寫 `tone` 就用 `ink`。繪製器不寫色碼。
- 形狀只畫線條，不填色。座標全部在 100×100 格子內，四周留邊至少 8（所有點都落在 [8, 92]）。
- 意思對不到圖示就是**編譯錯誤**，錯誤訊息列出最接近的三個意思。不准退化成文字，也不准換成別的圖（反目標）。
- 任何東西都不准畫出區域外。放不下就要**明確報錯**：手帳寫進播放器的錯誤清單，黑板寫進 `window.__boardProblems`。不能只靠「越界框剛好被量測閘看到」。
- 決定性：同一份分鏡跑兩次，畫面逐位元組相同。
- **printf 片不動**：`video_engine/out/vscode_printf_chalk/` 的 `beats.js`、`index.html` 都不改；`vscode` 自己的 `tip`（`model.js` 的 `tipBox`）也不改。
- Python 一律用 `.venv/bin/python`。全套測試：`.venv/bin/python -m unittest discover -s tests -t .`。
- 要用 Playwright 的測試，在沒有瀏覽器時 skip；但設了 `E2E_GEOM=1` 就必須真的跑，跑不了要失敗，不准 skip（避免檢查自己壞掉卻顯示通過，記憶 fail-open-checks）。
- F5 配音與影片渲染**只在 Colab 跑**，開跑前另外徵得使用者同意。本機也不准 import torch 去跑 TTS。視覺好壞交使用者判斷，不自行截圖評價。
- JS 模組樣式：`(function (g) { 'use strict'; … if (typeof module !== 'undefined') module.exports = X; else g.X = X; })(this);`
- 計畫裡的程式片段是**介面與意圖，不是定稿**（記憶 plan-sample-code-quality），實作照現有檔案的寫法。

## Review Focus

1. **意思寫成同義但字不同**（例：分鏡寫「等一下」，目錄只有「等待」）：預期編譯失敗並建議「等待」，不是畫成別的圖 → Task 2 用真的意思表跑排序。
2. **黑板頁放了還沒有粉筆皮膚的元件**（例：置中頁放 `list`）：預期 `storyboard.py` 報錯，訊息是「黑板還沒有 list 的粉筆皮膚」，畫面不准空一塊 → Task 7 在交給編譯器**之前**就查原始型別。編譯器會把未知型別改成 `note`，交給它之後才查就查不到了。
3. **標註框指向畫面邊緣的錨點**：預期換到左邊、上面或下面；四邊都放不下時明確報錯 → Task 4。
4. **`blink` 的 `until` 寫成不存在的字，或 `blink` 後面還有別的動作**：前者預期編譯錯誤；後者預期後面的動作照常起跑，不被閃爍拖到頁尾 → Task 3。
5. **圖示第一個動作是 `blink`／`erase`，前面沒有 `draw`／`show`**：鉛筆版在第一次被引用時就出現，粉筆版要等 `draw`，兩版會不一致 → Task 3 直接判成編譯錯誤。

---

## 檔案地圖

| 檔案 | 動作 | 職責 |
|---|---|---|
| `video_engine/components/icon/shapes.js` | 新增 | 31 個圖示的筆畫（筆順、粗細等級、是否為弧線）；`keycap` 回傳鍵帽上的字 |
| `video_engine/components/icon/svg.js` | 新增 | 筆畫 → SVG 字串（仿真皮膚） |
| `video_engine/components/icon/export_png.py` | 新增 | 單一圖示或 31 格總表 → PNG（仿真、鉛筆、粉筆三種皮膚） |
| `video_engine/components/icon/README.md` | 新增 | 用法、怎麼加意思、筆順原則 |
| `video_engine/components/callout/callout.js` | 新增 | 通用標註框：尺寸、四邊擺放、何時收起 |
| `video_engine/board/catalog.json` | 修改 | `icon` 契約；通用動作 `callout` |
| `video_engine/board/compile.py` | 修改 | 意思解析、目錄自檢、`draw` 時長、`until`、第一個動作的檢查、`draw` 時刻 |
| `video_engine/board/build.py` | 修改 | `SHARED_ORDER` 加上 `shapes.js`、`callout.js` |
| `video_engine/board/runtime/components/icon.js` | 改寫 | 鉛筆皮膚 |
| `video_engine/board/runtime/player.js` | 修改 | 畫 `callout`；放不下時明確報錯 |
| `video_engine/board/check.py` | 修改 | 播放器回報的版面錯誤算失敗 |
| `video_engine/board/fixtures/icon_*.scene.json`、`callout_*.scene.json` | 新增 | 見各任務 |
| `video_engine/explainer/chalk/kit/icon.chalk.js`、`note.chalk.js`、`board.chalk.js`、`board_tpl.js` | 新增 | 粉筆皮膚、黑板通用轉接、格子算式 |
| `video_engine/explainer/chalk/board_check.py` | 新增 | 開黑板頁讀 `window.__boardProblems`，非空或缺少就失敗 |
| `video_engine/explainer/chalk/tools/icon_sheet.html` | 新增 | 粉筆 31 格總表的單頁 |
| `video_engine/explainer/pages.py` | 新增 | 從 `f5_story.py` 抽出分頁、lead／hold，不 import torch；附草稿用 CLI |
| `video_engine/explainer/f5_story.py` | 修改 | 改 import `pages.py`（行為不變） |
| `video_engine/explainer/storyboard.py` | 修改 | 置中／雙欄頁的 `objects`＋`do` → `objects.json` |
| `video_engine/explainer/sync_film.py` | 修改 | 併入 `objects.json`；複製新的 kit 檔 |
| `video_engine/explainer/chalk/screen_check.js` | 修改 | 也檢查 objects 頁的排程 |
| `video_engine/explainer/chalk/starter/` | 新增 | 新片的起始樣板 |
| `video_engine/explainer/storyboard_to_scene.py` | 新增 | storyboard → 手帳的 scene.json、timing.json |
| `docs/experiments/2026-10-31-icon-demo/` | 新增 | 展示片的分鏡、兩版原始碼、總表 |
| `tools/video_skills_sync.py` | 修改 | `INCLUDE` 補上新檔 |
| `tests/test_icon_component.py`、`tests/js/icon_probe.js` | 新增 | 形狀、目錄、編譯、標註框、粉筆純函式 |
| `tests/test_storyboard.py`、`tests/test_sync_film.py`、`tests/test_f5_story.py` | 修改 | objects 頁、併入、抽出 pages |
| `tests/test_storyboard_to_scene.py` | 新增 | 一份分鏡兩種出片 |

---

### Task 0: 改動前的基準

**Files:**
- Create: `tests/fixtures/icon_baseline/`（`vscode_actions.json`、`printf_screens.json`、`printf_storyboard_out.json`）
- Test: `tests/test_icon_component.py`（`TestBaseline`）

- [ ] **Step 1**：在**還沒動任何程式**的 HEAD 上產生三份基準：
	- `vscode_actions.json`：`vscode_full.scene.json` 和一份新寫的 `video_engine/board/fixtures/vscode_tip.scene.json`（含 vscode 自己的 `tip`）跑 `compile_scene` 得到的 `actions` 清單（去掉 `spec`），再加上 probe 跑 `VSCodeModel.state`／`anchors` 在 tip 動作中點的結果。
	- `printf_screens.json`：`storyboard.py` 重跑 `docs/experiments/2026-10-22-vscode-printf/video/chalk-story` 得到的 `screens.json`。
	- `printf_storyboard_out.json`：同一次 `build()` 產生的所有檔名與內容 md5。
- [ ] **Step 2**：寫 `TestBaseline`，每次都重算並比對這三份。全部要通過，現在就是綠的。比對的是純資料，不比 PNG 的 md5，因為 PNG 會隨 Chromium 和字型版本變。
- [ ] **Step 3: Commit** `test: 圖示元件改動前的 VS Code 與 printf 分鏡基準`

之後每個任務的 Step 4 都要跑 `TestBaseline`。不同就是動到了 printf 或 vscode 的行為，要停下來回報，不准改基準。

### Task 1: 圖示形狀 `shapes.js`

**Files:**
- Create: `video_engine/components/icon/shapes.js`
- Create: `tests/js/icon_probe.js`（`node icon_probe.js <cmd> <json>`，做法比照 `tests/js/vscode_probe.js`）
- Test: `tests/test_icon_component.py`（`TestShapes`）

**Interfaces:**
- Produces:
	- `IconShapes.NAMES`：31 個名稱，順序同 spec 表，先 A 組 24 個，再接 B 組 7 個。
	- `IconShapes.strokes(name, opts) → {strokes: [{pts: [[x, y], …], w: 'main'|'detail', arc: bool, part: string}], text?: string}`：名稱不認得就 throw。`keycap` 的 `opts.text` 必填，原樣放進 `text`。
	- `IconShapes.count(name) → int`，等於 strokes 的長度。

- [ ] **Step 1: 寫失敗測試**：
	- `test_名稱清單`：`NAMES` 長度 31，含 spec 表的全部名稱，沒有重複。
	- `test_筆畫都在格子內`：所有點都滿足 `8 <= x, y <= 92`。
	- `test_筆畫格式`：每一筆 `len(pts) >= 2`，`w in ('main', 'detail')`；第一筆是 `main`（先外框後細節）。
	- `test_弧線有取樣`：`arc` 為真的筆畫，相鄰兩點距離 ≤ 6。直線兩點就好，不檢查。
	- `test_決定性`：同一個名稱呼叫兩次，JSON 相同。
	- `test_keycap_帶字`：`strokes('keycap', {text: 'Ctrl'}).text == 'Ctrl'`；不給 text 就 throw。
	- `test_未知名稱`：`strokes('nope')` 會 throw。
- [ ] **Step 2: 跑測試確認失敗**：`.venv/bin/python -m unittest tests.test_icon_component -v` → FAIL。
- [ ] **Step 3: 實作**
	- `gear` 取 `board/runtime/components/icon.js` 的齒形，**縮放**到 [8, 92]。原尺寸換算過去是 4.3..95.7，會超出留邊。鉛筆齒輪因此會比現在略小，Task 5 出總表時要跟使用者說明。
	- `hourglass`、`lock`、`keyboard`、`keycap` 只參考 printf `beats.js` 的形狀，那個檔不改。
	- 弧線用 `arc(cx, cy, r, a0, a1)` 取樣，並標上 `arc: true`。
- [ ] **Step 4: 跑測試確認通過**，`TestBaseline` 也要綠。
- [ ] **Step 5: Commit** `feat(components): 圖示形狀 31 個（筆順、粗細等級）`

### Task 2: 目錄契約與意思解析

**Files:**
- Modify: `video_engine/board/catalog.json`（`types.icon`）
- Modify: `video_engine/board/compile.py`（`load_catalog`、`normalize_objects`）
- Test: `tests/test_icon_component.py`（`TestCatalog`）

**Interfaces:**
- Produces:
	- `types.icon` = `{"req": ["name"], "opt": ["caption", "tone", "text", "size"], "sizes": ["s", "m", "l"], "names": [...31], "means": {名稱: [意思…]}, "strokes": {名稱: 筆畫數}, "anchors": ["caption"], "actions": {…Task 3…}}`。`means` 照 spec 表逐字抄，B 組用 spec 括號裡的詞。
	- `compile.check_icon_catalog(spec) -> None`：`means` 的鍵必須等於 `names`。同一個意思（包含圖示名稱本身）出現在兩個圖示下就 `ValueError`，訊息列出那個意思和兩個圖示名稱。`load_catalog()` 載入後呼叫它。
	- `compile.nearest_means(word, means, k=3) -> [str]`：依 Jaccard `|set(word) ∩ set(m)| / |set(word) ∪ set(m)|` 由大到小排；同分時比共同前綴長度，由長到短；再同分照字串排。不能用重疊字數排，那樣三個字的詞會一直贏（審查實測過：「等一下」會排出「再一次、寫下來、想一想」）。
	- `normalize_objects` 處理 `icon`：
		- `name` 可以寫圖示名稱，也可以寫任何一個意思。解析後 `obj["name"]` 改成圖示名稱，原文留在 `obj["_asked"]`。
		- 對不到就 `ValueError("…沒有「X」這個意思，最接近：A、B、C")`。
		- `keycap` 缺 `text` 要報錯；`size` 不在 `sizes` 裡要報錯；`tone` 不在 TONES 裡要報錯。
		- 原本的 `names` 檢查對 icon 跳過，改由意思解析取代。

- [ ] **Step 1: 寫失敗測試**：
	- `test_目錄筆畫數與形狀一致`：catalog 的 `strokes[n]` 等於 probe 跑出的 `IconShapes.count(n)`，31 個都要有。防止目錄和形狀各改各的。
	- `test_意思解析`：`"name": "唯讀"` → `name == "lock"`、`_asked == "唯讀"`；寫 `"name": "lock"` 照舊。
	- `test_對不到意思要報錯`：`"name": "等一下"` → `ValueError`，訊息裡有「等待」；編譯結果的 gaps 不准出現 icon。
	- `test_最接近排序`：用 catalog 的**真實** `means` 跑，`"等待" in nearest_means("等一下", means)`，`"錯誤" in nearest_means("錯了", means)`。先在 REPL 跑過實際結果，再寫斷言。
	- `test_重複意思載入就失敗`：複製 catalog，把「等待」加進 `clock`，`check_icon_catalog` 要擋下，訊息裡有「等待」「hourglass」「clock」。
	- `test_keycap_缺字`：`keycap` 沒給 `text` → `ValueError`。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 實作**，照 Interfaces。
- [ ] **Step 4: 跑測試確認通過**，`tests.test_board_compile`、`TestBaseline` 也要綠。
- [ ] **Step 5: Commit** `feat(board): 圖示用意思叫，對不到就報錯`

### Task 3: 圖示動作 draw／blink／erase

**Files:**
- Modify: `video_engine/board/catalog.json`（`types.icon.actions`）
- Modify: `video_engine/board/compile.py`（`collect_actions`、`time_actions`）
- Test: `tests/test_icon_component.py`（`TestActions`）

**Interfaces:**
- Produces:
	- `actions`：
		- `"draw": {"per_stroke": 0.12, "min": 0.5, "max": 1.6, "blocks": true}`
		- `"blink": {"period": 0.5, "opt": ["until"], "span": "until"}`
		- `"erase": {"dur": 0.4, "blocks": true}`
	- 時長：
		- `per_stroke` 的時長是 `clamp(strokes[name] * per_stroke, min, max)`。
		- `span: "until"` 的 t1 是 `until` 那幾個字開口的時刻，比例算法同 `anchored_start`，但不扣 `CUE_LEAD`。沒寫 `until` 就是這一場的 `scene_end`。
	- **排序規則**：`span: "until"` 的動作**不當後面動作的 `prev`**。沒有 cue、也不是該句第一個的動作，要接在「前一個不是 until 類的動作」的 t1 之後；如果前面只有 until 類動作，就從那個 until 動作的 t0 起跑。這和黑板 `schedule` 只看 `blocks` 前進的規則一致。
	- `collect_actions` 的檢查：
		- `until` 必須出現在**同一場、這句之後**某一句的 `say` 裡，否則 `ValueError`。找到的句子用全片句號存進 `args["until_beat"]`。
		- 每個 icon 的第一個動作必須是 `draw` 或 `show`，否則 `ValueError("…先 draw 再 blink／erase")`。
		- `note` 物件出現在黑板頁時，第一個動作必須是 `write` 或 `show`。這條由 Task 7 檢查。
	- `action_spec` 的查找順序**不改**（通用動作名稱改叫 `callout`，不會和 `vscode.tip` 撞名）。
	- 鉛筆執行期把 icon 的 `show` 當成 `draw` 來畫，這在 Task 5 做；編譯器不改寫動作名稱。

- [ ] **Step 1: 寫失敗測試**：
	- `test_draw_時長依筆畫`：筆畫少的（`check`）會被夾到 0.5；`keyboard` 的時長是 `min(n * 0.12, 1.6)`。
	- `test_blink_until`：兩句的場，第一句的 `blink` 寫 `until: 第二句裡的幾個字`，t1 要落在第二句的 t0..t1 之間；沒寫 until 時 `t1 == scene_end`。
	- `test_blink後面的動作不被拖住`：同一句 `draw A`、`blink A`、`draw B`（都沒有 cue），B 的 t0 要等於 A 的 draw 的 t1，不是 `scene_end`。
	- `test_until_不在這場`：寫成不存在的字 → `ValueError`；寫成上一句的字 → `ValueError`。
	- `test_第一個動作要是draw`：icon 第一個動作是 `blink` → `ValueError`。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 實作**。
- [ ] **Step 4: 跑測試確認通過**，`tests.test_board_compile`、`tests.test_vscode_component`、`TestBaseline` 都要綠。
- [ ] **Step 5: Commit** `feat(board): 圖示的畫出、閃爍、擦掉`

### Task 4: 通用標註框 `callout`

spec 裡叫通用 `tip`，這裡改名叫 `callout`。原因是 `vscode` 自己已經有一個叫 `tip` 的動作：如果同名，`{act: "tip", target: "vs:L3"}` 會被安靜地當成 VS Code 面板裡的提示，錨點直接被忽略。

**Files:**
- Create: `video_engine/components/callout/callout.js`
- Modify: `video_engine/board/catalog.json`（`generic_actions.callout`）、`video_engine/board/runtime/player.js`、`video_engine/board/build.py`、`video_engine/board/check.py`
- Create: `video_engine/board/fixtures/callout_edges.scene.json`（四個圖示分別貼著左、右、上、下邊緣，各掛一個 callout）、`video_engine/board/fixtures/callout_full.scene.json`（四邊都擠滿）
- Test: `tests/test_icon_component.py`（`TestCallout`）

**Interfaces:**
- Produces:
	- `generic_actions.callout = {"dur": 0.3, "req": ["text"], "opt": ["tone", "until"], "blocks": true}`；`until` 的規則同 Task 3，也不當 `prev`。
	- `Callout.PAD`、`Callout.ARROW`：數值從 `vscode/model.js` 的 `tipBox` 複製過來，`model.js` 不改。
	- `Callout.size(text, measure, style) → {w, h}`。
	- `Callout.place(anchor, size, bounds, obstacles) → {box, side, tip: [x, y]} | null`：依序試 `right`、`left`、`top`、`bottom`，用第一個「整個在 bounds 內、又不碰到 obstacles」的位置；都不行就回 `null`。
	- `Callout.endTime(acts, i, untilT, sceneEnd) → t`：有 `until` 就用 `until`；否則取 i 之後第一個同物件動作的 t0；都沒有就到 `sceneEnd`。
	- `player.js`：callout 畫成圓角框加小三角，框以 `{owner: <target 的物件 id>, role: 'label', value: text}` 推進 boxes。`place` 回 `null` 時，把「`<物件> 的 callout 四邊都放不下：<text>`」推進播放器的 `errors`。`check_frame` 本來就會把 errors 列成問題（`check.py:83`），所以 `check.py` 只需要補測試，不必改邏輯。

- [ ] **Step 1: 寫失敗測試**：
	- `test_place_四邊`（probe）：錨點貼著 bounds 右緣 → 放 `left`；bounds 很窄、左右都放不下 → 放 `top`；四邊都塞住 → `null`。
	- `test_endTime`：下一個同物件動作的 t0 比較早就用它；有 until 就用 until。
	- `test_callout_邊緣_過閘`：`callout_edges` 走 compile → build → `check.py`，結果要綠。
	- `test_callout_塞不下要失敗`：`callout_full` 跑 `check.py`，exit 1，訊息裡有「四邊都放不下」。
	- 這兩個 Playwright 測試遵守 Global Constraints 的 `E2E_GEOM` 規則。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 實作** `callout.js`、catalog、player。
- [ ] **Step 4: 跑測試確認通過**，`tests.test_vscode_component`、`TestBaseline` 也要綠。
- [ ] **Step 5: Commit** `feat(components): 通用標註框，任何錨點旁都能掛`

### Task 5: 鉛筆皮膚與仿真皮膚＋總表

**Files:**
- Rewrite: `video_engine/board/runtime/components/icon.js`
- Create: `video_engine/components/icon/svg.js`、`video_engine/components/icon/export_png.py`、`video_engine/components/icon/README.md`
- Create: `video_engine/board/fixtures/icon_full.scene.json`（31 個圖示分成幾場；三個動作、`caption`、`keycap`、`callout` 都用到）、`video_engine/board/fixtures/icon_sheet.scene.json`（一場放 31 格，給總表用）
- Modify: `video_engine/board/COMPONENTS.md`（icon 一節）
- Test: `tests/test_icon_component.py`（`TestSkins`）

**Interfaces:**
- Consumes: `IconShapes.strokes`、Task 3 排出的動作時間
- Produces:
	- 鉛筆 `icon.js`：
		- `measure` 依 `size` 決定大小：`s` 96、`m` 140（預設）、`l` 200，有 caption 再加上它的高度。
		- `state` 回 `{p, blinkOn, erased}`：`draw`／`show` 給進度 0..1；`blink` 每 `period` 秒亮暗一次，直到 t1；`erase` 之後就不畫。
		- `draw` 照筆順，把 p 依每筆的長度分給各筆，交給 `api.ink(pts, pi, {color, width, seed})`。`main` 寬 5、`detail` 寬 3.5，隨 size 等比放大縮小。
		- 用 `api.record(..., 'panel')` 記圖示框；`icon:caption` 有自己的框。
	- `IconSVG.render(name, opts, color, px) → string`：等粗線，`stroke-linecap` 和 `linejoin` 都用 round，顏色由呼叫端傳入主題色。
	- `export_png.py <out.png> [--name N | --sheet] [--skin flat|pencil|chalk] [--text T] [--tone ink]`：
		- 總表 6 欄，每格下方印名稱。截圖做法照 `components/vscode/export_png.py`。
		- `pencil`：把 `icon_sheet` 編譯、build 到暫存目錄，開 `player.html` 跳到最後一刻截一張。做法同 `check.py` 開播放器。
		- `chalk`：開 Task 6 的 `icon_sheet.html`。
		- `board/export.py` 輸出的是影片，不能拿來出單張圖。

- [ ] **Step 1: 寫失敗測試**：
	- `test_每個圖示都有框`：`icon_full` 量出來，每個 icon 都有 `panel` 框；有 caption 的另外有 `:caption` 框。
	- `test_icon_full_過量測閘`：`check.py` 綠，涵蓋越界、重疊、縮放下限、決定性。
	- `test_svg_決定性`：總表匯出兩次，md5 相同（同一台機器、同一次執行，所以可以比 md5）。
	- `test_不寫色碼`：`svg.js`、`shapes.js`、`icon.js` 的原始碼裡 grep 不到 `#[0-9a-fA-F]{3,6}`。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 實作**。
- [ ] **Step 4: 跑測試確認通過**，再出兩張總表（單張圖，不是影片，可以在本機跑）：

```bash
~/.local/share/pipx/venvs/webwright/bin/python video_engine/components/icon/export_png.py docs/experiments/2026-10-31-icon-demo/sheets/pencil.png --sheet --skin pencil
~/.local/share/pipx/venvs/webwright/bin/python video_engine/components/icon/export_png.py docs/experiments/2026-10-31-icon-demo/sheets/flat.png --sheet --skin flat
```

- [ ] **Step 5: Commit** `feat(components): 圖示鉛筆與仿真皮膚、總表`

### Task 6: 粉筆皮膚 icon.chalk.js、note.chalk.js＋粉筆總表

**Files:**
- Create: `video_engine/explainer/chalk/kit/icon.chalk.js`、`video_engine/explainer/chalk/kit/note.chalk.js`
- Create: `video_engine/explainer/chalk/tools/icon_sheet.html`：載入 printf 片的 `lib/core.js`、`lib/kit/kit.js`、`kit.css`，以及 `shapes.js`、`icon.chalk.js`。在一塊面板上排 31 格，每格呼叫 `ChalkIcon.perform`。`?t=end` 時直接 render 最後一刻。
- Modify: `video_engine/explainer/chalk/kit/KIT.md`
- Test: `tests/test_icon_component.py`（`TestChalk`）

**Interfaces:**
- Consumes: `IconShapes.strokes`
- Produces:
	- `ChalkIcon.SIZE = {s: 120, m: 180, l: 260}`，是黑板 1080p 面板上的像素，對照 KIT.md 的字級。
	- `ChalkIcon.paths(name, opts, box) → [{d, w, len}]`：把筆畫縮放進 box；`main` 換成粉筆寬 6，`detail` 寬 4.5；`len` 是筆畫長度。
	- `ChalkIcon.perform(api, P, obj, box, acts, tone) → {els}`：
		- `draw`／`show`：依 `len` 的比例切分 t0..t1，逐筆呼叫 `api.S(P, d, tone, w, t, dur, {kind: 'draw'})`；`keycap` 的字用 `api.T`。
		- `blink`：照 printf `beats.js` 的 `blink()` 分段做 `K.fade`，暗下去再亮回來，不寫 `style.opacity`。
		- `erase`：`api.X(P, els, box, t0, 0.4)`。
	- `ChalkNote.STYLES = {headline: 60, body: 46, accent: 46, code: 46, small: 38}`，`MIN = 30`。
	- `ChalkNote.layout(text, style, maxW, maxH, measure) → {size, lines}`：先在 maxW 內斷行（中文逐字斷，英數以詞為單位）。總高 `lines × size × 1.3` 超過 maxH 就縮小一號（每次 −4px）重排；縮到 `MIN` 還放不下就 throw，訊息含原文。`measure(text, size) → w` 由呼叫端傳入。
	- `ChalkNote.perform(api, P, obj, box, acts) → {els}`：`write` 用 `api.seq` 逐字寫出來；`accent` 用 `accent` 語氣，`code` 用 `lat` 字面。

- [ ] **Step 1: 寫失敗測試**（假量測：全形字寬＝字級，半形＝字級×0.55）：
	- `test_粉筆路徑在框內`：31 個圖示 `paths` 的所有點都在 box 內。
	- `test_筆畫長度分配時間`：用假 api 記下每一筆的 (t, dur)，總和等於 draw 的 t1 − t0，順序同筆順。
	- `test_note_換行`：40 字句子、600×300 → 每行寬 ≤ 600，總高 ≤ 300，字級 ≥ 30。
	- `test_note_放不下要報錯`：200 字句子、300×200 → throw。
	- `test_不寫色碼與不用opacity`：兩個檔都 grep 不到色碼和 `style.opacity`。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 實作**。
- [ ] **Step 4: 跑測試確認通過**，出粉筆總表：`export_png.py docs/experiments/2026-10-31-icon-demo/sheets/chalk.png --sheet --skin chalk`。
- [ ] **Step 5: Commit** `feat(chalk): 圖示與文字的粉筆皮膚、粉筆總表`

### Task 7: 分鏡的 objects 頁 → objects.json

**Files:**
- Modify: `video_engine/explainer/storyboard.py`
- Modify: `video_engine/explainer/sync_film.py`（`merge_objects`；`copy_components` 多複製 `icon.chalk.js`、`note.chalk.js`、`board.chalk.js`、`board_tpl.js`）
- Test: `tests/test_storyboard.py`、`tests/test_sync_film.py`

**Interfaces:**
- Produces:
	- 分鏡頁（`center`／`two-col`）可以寫 `objects: [...]`，格式同 scene.json 的物件；每句可以寫 `do`。雙欄頁的每個物件都要寫 `col: "left"|"right"`。
	- `storyboard.BOARD_TYPES = ("icon", "note")`。在交給編譯器**之前**先查原始的 `type`，其他型別就 `ValueError("黑板還沒有 X 的粉筆皮膚")`。
	- 版面文法：置中頁超過 3 個物件、雙欄任一欄超過 2 個、雙欄物件缺 `col`，都是 `ValueError`。`note` 的第一個動作必須是 `write` 或 `show`。
	- `storyboard.board_actions(pg, first) -> (objects, {句號: [動作]})`：做法同 `screen_actions`，交給 `BC.Compiler` 驗證。layout：置中是 `{"stack": ids}`，雙欄是 `{"row": [{"stack": 左}, {"stack": 右}]}`。
	- **動作時長改用編譯器算好的 `t1 − t0`**，不要再用 `spec["per"]` 自己算（`storyboard.py:37` 碰到 `per_stroke` 或 `until` 的 spec 會 KeyError）。`span: "until"` 的動作 `dur` 填 `null`，由黑板端換算。`args.until_beat` 換成全片句號的 `until_line`。`screen_actions` 也改用同一個 helper，算出來的時長必須和 Task 0 的 `printf_screens.json` 相同。
	- `build()` 只有在**至少一頁寫了 `objects`** 時才產出 `objects.json`，內容是 `[{"lines": [...], "template": ..., "objects": [...], "do": {...}}]`。
	- `sync_film.merge_objects(story, objects)`：用 `lines` 對 `story["pages"]`，併成 `story["boards"]`。對不上就 `ValueError`，理由同 `merge_screens`：不能安靜略過。沒有 `objects.json`、或內容是空的，就不寫 `boards` 這個鍵。

- [ ] **Step 1: 寫失敗測試**：
	- `test_objects頁產出`：置中頁兩個 icon 加一句 `draw` → `objects.json` 有一筆，`do["1"][0]["act"] == "draw"`，`dur` 等於編譯器算出的時長。
	- `test_置中最多三個`、`test_雙欄每欄最多兩個`、`test_雙欄缺col`：都要 `ValueError`。
	- `test_黑板沒有粉筆皮膚的元件`：置中頁放 `list` → `ValueError`，訊息裡有「list」。放不存在的型別 `foo` 也一樣報錯，不准被改成 note。
	- `test_意思對不到也在分鏡階段擋`：`name: "等一下"` → `ValueError`。
	- `test_沒有objects頁就不產objects檔`：printf 分鏡 `build()` 的結果和 Task 0 基準相同。
	- `test_merge_objects_對不上`（`test_sync_film.py`）：句號不在 pages 裡 → `ValueError`；`objects=[]` 時 story 不出現 `boards`。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 實作**。
- [ ] **Step 4: 跑測試確認通過**，`TestBaseline` 也要綠。
- [ ] **Step 5: Commit** `feat(chalk): 黑板頁也能寫元件描述並驗證`

### Task 8: 黑板通用轉接 board.chalk.js＋starter

**Files:**
- Create: `video_engine/explainer/chalk/kit/board_tpl.js`、`video_engine/explainer/chalk/kit/board.chalk.js`、`video_engine/explainer/chalk/board_check.py`
- Create: `video_engine/explainer/chalk/starter/` 的檔案，清單見 Step 3（目錄已經存在，裡面只有一個空的 `tools/`）
- Modify: `video_engine/explainer/chalk/screen_check.js`
- Test: `tests/test_icon_component.py`（`TestBoardChalk`）

**Interfaces:**
- Consumes: `ChalkIcon`、`ChalkNote`、`Callout`、`ChalkVSCode.schedule`（直接呼叫，不複製）
- Produces:
	- `BoardTpl.tpl(area, kind)`：從 printf `index.html:359-378` 的 `tpl` 搬過來的純函式，數值逐字照抄。starter 的 `index.html` 改呼叫它；printf 片自己的 `index.html` 不改。
	- `ChalkBoard.place(board, tpl, sizeOf) → {id: {x, y, w, h}}`：
		- 置中：物件由上而下排，間距 40，整組在 `tpl` 裡置中。
		- 雙欄：照 `col` 分進 `tpl.left`、`tpl.right`，兩欄各自由上而下置中。
		- 整組高度超出格子就等比縮小；縮到 0.6 還放不下就 throw。
	- `ChalkBoard.mountAll(api, boards) → {render(t), problems: [字串]}`：
		- 每頁用 `BoardTpl.tpl(api.area(第一句), template)` 取格子，用 `place` 排好。
		- 用 `ChalkVSCode.schedule(board, api.span, api.drawAt)` 排時間。`dur` 為 `null` 的動作，用 `api.span(until_line, until)` 換算，或取該頁最後一句的 `api.lineEnd`。
		- 物件交給 `ChalkIcon.perform` 或 `ChalkNote.perform` 畫。`callout` 用 `Callout.place` 放，bounds 是 `api.area(第一句)`。
		- `place` throw、`ChalkNote.layout` throw、`Callout.place` 回 `null`，都**收進 `problems`**，不中斷整片。
		- 物件在第一個 `show`／`draw`／`write` 之前不出現。
	- `ChalkBoard.checkSchedule(boards, span) → [字串]`：純排程檢查，在 node 跑。內容是每個 `until` 都換算得到時間，每個 cue 都在句子裡。
	- starter `index.html`：
		- `<script>` 依序掛上 `lib/components/icon/shapes.js`、`lib/components/callout/callout.js`、`lib/kit/board_tpl.js`、`lib/kit/{icon,note,board}.chalk.js`。
		- 在 `ChalkVSCode.mountAll` 那行旁邊加 `var boards = window.ChalkBoard ? ChalkBoard.mountAll(API, D.boards) : null; window.__boardProblems = boards ? boards.problems : [];`。
		- 在每格的 `frame(t)`（printf `index.html:712` 附近，`vsScreens` 被呼叫的地方）加上 `boards && boards.render(t)`。
	- starter `beats.js`：`window.Beats = function (api) { "use strict"; };`，加一行註解說明這支片不寫專屬程式。
	- `board_check.py <影片專案>`：用 Playwright 開 `index.html`，等字型載完，讀 `window.__boardProblems`。是 `undefined`（代表沒掛上）或非空都 exit 1。
	- `screen_check.js`：多載入 `shapes.js`、`callout.js`、三個 chalk 轉接，也跑 `ChalkBoard.checkSchedule`。

- [ ] **Step 1: 寫失敗測試**：
	- `test_tpl_與printf相同`：用 printf 片一頁的 area，`BoardTpl.tpl` 算出的 center 和 two-col 格子，要等於從 `index.html` 原文抽出那段 `tpl` 函式在 node 跑的結果。
	- `test_place_置中`：三個 m 圖示 → 水平置中，垂直間距 40，全部在 tpl 內。
	- `test_place_雙欄`：左欄 2 個、右欄 1 個 → 左欄兩個都在 `tpl.left` 內。
	- `test_place_放不下要報錯`：三個 l 圖示放進很矮的格子 → throw。
	- `test_checkSchedule_抓到until`：`until_line` 指到的句子裡沒有那幾個字 → 問題清單非空。
	- `test_starter_beats是空樣板`：去掉註解與空白後，等於 `window.Beats=function(api){"use strict";};`。
	- `test_starter_檔案齊全`：Step 3 清單上的檔案都存在。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 盤點並建 starter**
	1. 先列出 printf 片進版控的檔案（`git ls-files video_engine/out/vscode_printf_chalk`）和 `lib/` 底下所有檔案。
	2. 分成三類，寫進 `starter/STARTER.md`：
		- 風格層，由 starter 提供：`index.html`、`kit.css` 參照、`hyperframes.json`、`package.json`、`meta.json`、`fonts.json`、`AGENTS.md`、`CLAUDE.md`、`tools/`。
		- 由 `sync_film.py` 或 `tools/` 產生：`lib/story.js`、`lib/components/`、`lib/themes.js`、`captions.srt`。
		- 每支片自己的：`beats.js`、`assets/audio/`。
	3. `lib/core.js`、`lib/kit/kit.js`、`kit.css`、`chalk-mask.png`、`grain.svg` 目前靠 `tools/sync.sh` 從 `$ROOT/kits/$STYLE` 複製，但那個目錄不存在（`sync.sh:12,16`）。改成 `sync_film.copy_components` 從 `explainer/chalk/kit/`、`explainer/chalk/core/` 複製。用 `cmp` 確認這些檔和 printf 片 `lib/` 底下的相同；不同就停下回報，先不要動。
	4. 字型與 `tools/sfx*` 照 printf 片的做法帶進 starter 的 `tools/`。
- [ ] **Step 4: 實作** `board_tpl.js`、`board.chalk.js`、`board_check.py`、`screen_check.js`。
- [ ] **Step 5: 跑測試確認通過**。printf 片 `lib/` 重新同步後：
	- `node video_engine/explainer/chalk/screen_check.js video_engine/out/vscode_printf_chalk` 結果和改動前相同。
	- `git diff --stat video_engine/out/vscode_printf_chalk` 只多出 `lib/` 的新檔，`lib/story.js` 沒有變動（printf 沒有 objects 頁，所以不會出現 `boards`）。
	- `TestBaseline` 綠。
- [ ] **Step 6: Commit** `feat(chalk): 黑板通用轉接與 starter，置中／雙欄頁不寫程式`

### Task 9: 草稿時間軸 pages.py（不配音）

**Files:**
- Create: `video_engine/explainer/pages.py`
- Modify: `video_engine/explainer/f5_story.py`（`make_pages`、`load_pauses`、lead／hold 的套用改成 import `pages.py`）
- Test: `tests/test_f5_story.py`

**Interfaces:**
- Produces:
	- `pages.make_pages(story, story_dir) -> (pages, screens)`、`pages.load_pauses(story_dir)`、`pages.apply_leads(story, story_dir) -> story`，邏輯從 `f5_story.py` 原樣搬過來。`pages.py` 不 import numpy、torch、soundfile。
	- CLI：`pages.py <story 資料夾>`。讀 `story.json`，只接受 `story.draft == true`；把 pages、screens、lead、hold 套上去，再寫回去。給沒有配音的草稿用；真正配音照舊走 `f5_story.py`（在 Colab）。

- [ ] **Step 1: 寫失敗測試**：
	- `test_pages_不碰torch`：用 `python -c "import sys; import pages; assert 'torch' not in sys.modules"` 跑子行程。
	- `test_草稿套用`：小 story 資料夾（`story.py --dry` 的輸出，加上 pages.json、leads.json）→ `story["pages"]` 正確、有 lead 的句子帶 `lead`。
	- `test_非草稿拒絕`：`draft == false` → exit 非 0。
	- `test_f5_story` 原有的測試照舊要綠。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 實作**（只搬函式，不改邏輯）。
- [ ] **Step 4: 跑測試確認通過**。
- [ ] **Step 5: Commit** `refactor(explainer): 分頁與 lead 抽出成不需 GPU 的 pages.py`

### Task 10: 一份分鏡兩種出片 storyboard_to_scene.py

**Files:**
- Create: `video_engine/explainer/storyboard_to_scene.py`
- Modify: `video_engine/board/compile.py`（timing 每筆可以帶 `draw`）
- Test: `tests/test_storyboard_to_scene.py`

**Interfaces:**
- Consumes: Task 7 的分鏡格式；`story.json`（`lines[].start/end/lead`）
- Produces:
	- `to_scene(sb) -> dict`，產出手帳 `scene.json`：
		- 一頁變一個 scene：`id` 是 `{章 id}_p{n}`，`title` 是章標題。
		- 置中頁：`{"stack": ids}`。雙欄頁：`{"row": [{"stack": 左}, {"stack": 右}]}`。
		- 電腦畫面頁：`screen` 物件加上 `{"id": "cursor", "type": "cursor"}`，layout 是 `{"stack": [screen id]}`。
		- `end` 那句接在最後一個 scene 的最後一句。
		- `recap` 變成最後一個 scene，物件是 `{"type": "list", "rows": recap.items}`，`say` 用 `recap.say`。
		- 物件 `id` 全片唯一，重複就 `ValueError`。不自動改名，因為改名會讓 `do` 的 target 對不上。
		- 每句的 `say`／`do` 照搬，`col` 欄位轉換後刪掉。
	- `to_timing(story) -> [{"t0", "t1", "draw"}]`：`t0 = start`，`t1 = end`，`draw = max(start − lead, 上一句的 t1)`。**句子本身的 t0 不提前**，所以字幕和 cue 仍然對著聲音。
	- `compile.py`：timing 那一筆有 `draw` 時，`anchored_start` 碰到「該句第一個、沒有 cue」的動作，從 `draw` 起跑，不從 `t0`。其他動作的算法不變。
	- CLI：`storyboard_to_scene.py <story 資料夾> <輸出資料夾>`，寫出 `scene.json`；有 `story.json` 才寫 `timing.json`。

- [ ] **Step 1: 寫失敗測試**：
	- `test_置中雙欄電腦畫面`：三頁分鏡轉出三個 scene，layout 如上；`compile_scene(to_scene(sb), None, catalog)` 成功。
	- `test_先畫後講`：lead 1.0 的句子 `draw == start − 1.0`、`t0 == start`；該句第一個動作的 t0 等於 `draw`，有 cue 的動作仍照 cue 對齊。
	- `test_lead比空檔長`：`draw` 被夾在上一句的 `t1`。
	- `test_同一份分鏡兩邊都驗過`：同一份 `sb` 分別交給 `storyboard.build` 和 `to_scene` → compile，兩邊都不丟例外，動作總數相同（不算 recap）。
	- `test_id重複要報錯`。
	- `TestBaseline` 綠：沒有 `draw` 的 timing，行為不變。
- [ ] **Step 2: 跑測試確認失敗**。
- [ ] **Step 3: 實作**。
- [ ] **Step 4: 跑測試確認通過**。
- [ ] **Step 5: Commit** `feat(explainer): 黑板分鏡轉手帳 scene，一份分鏡兩種出片`

### Task 11: 展示片（有使用者閘）

**Files:**
- Create: `docs/experiments/2026-10-31-icon-demo/story/`（`storyboard.json` 和它的產物）
- Create: `docs/experiments/2026-10-31-icon-demo/chalk/`（從 starter 開的影片專案；原始碼進版控，渲染結果不進）
- Create: `docs/experiments/2026-10-31-icon-demo/board/`（`scene.json`、`timing.json`）

- [ ] **Step 1: 骨架**：寫「每頁一句話」骨架。
	- 題材：一支作業程式從寫到交出去。
	- 主線依序用到 A 組 24 個圖示；結尾一段「聊聊」用 B 組 7 個。
	- 一頁放一到兩個圖示，只用置中或雙欄；片長約 4–5 分鐘。
	- 用 `storyboard.py` 產出 `review.md`，**交使用者審順序，停下來等回覆**（記憶 narrative-spine-first）。
- [ ] **Step 2: 逐句旁白與 do**：骨架通過後才寫。
	- 先讀 `narration_style_tw.md`。旁白講意思、不念符號；新東西先畫後講（用 `lead`）。
	- 每個圖示至少出現一次，`blink`、`erase`、`callout` 也都至少用一次。
	- `storyboard.py` 必須跑成功。再寫一行小腳本，確認 31 個圖示都用到了。
- [ ] **Step 3: 黑板版建置（不配音）**：
	1. `python3 video_engine/explainer/chalk/tools/story.py <story> --dry`，再跑 `pages.py <story>`。
	2. 從 starter 開影片專案，跑 `sync_film.py`。
	3. 跑 `screen_check.js`、`board_check.py`、`npx --yes hyperframes@0.8.81 check`，三項都要 0 錯。
	4. `cmp` 確認 `beats.js` 和 starter 的一模一樣。
- [ ] **Step 4: 手帳版建置（不配音）**：`storyboard_to_scene.py` → `compile.py` → `build.py` → `check.py`，要綠。
- [ ] **Step 5: Commit** `docs(experiments): 圖示展示片分鏡與兩版建置`
- [ ] **Step 6: 配音與渲染**：**先問使用者同意**，才在 Colab 跑 F5 配音和兩版渲染（記憶 render-off-local；新句要經多 seed 篩選，見記憶 f5-narration）。成片並排交使用者審，不自行評價畫面。

### Task 12: 收尾：同步清單、文件、全套測試

**Files:**
- Modify: `tools/video_skills_sync.py`（`INCLUDE`）
- Modify: `video_engine/components/icon/README.md`、`video_engine/board/COMPONENTS.md`、`video_engine/explainer/chalk/kit/KIT.md`
- Modify: `docs/參考紀錄.md`（實作時參考到的東西）

- [ ] **Step 1**：`INCLUDE` 加上 `components/icon/`、`components/callout/`、新的 chalk 檔、`chalk/starter/`、`board_check.py`、`pages.py`、`storyboard_to_scene.py`、新測試和 `tests/js/icon_probe.js`。跑 `python3 tools/video_skills_sync.py`（不 commit），不能有被擋下的項目。
- [ ] **Step 2**：設 `E2E_GEOM=1` 跑全套測試 `.venv/bin/python -m unittest discover -s tests -t .`，要綠。再跑 CLAUDE.md 的逐位元組回歸基準，改動前後 md5 相同。
- [ ] **Step 3: Commit** `chore: 圖示元件同步清單與文件`

---

## 計畫層代為決定的事（spec 沒寫死的技術細節）

1. **通用提示框改叫 `callout`**：spec 叫 `tip`，但 `vscode` 自己已經有一個 `tip` 動作，同名的話錨點會被安靜地吃掉。改名之後也不必動 `action_spec` 的查找順序。
2. **筆畫數寫在目錄裡**（`catalog.json` 的 `strokes`）：編譯器是 Python，讀不到 JS 的形狀。由測試比對目錄和形狀是否一致。
3. **閃爍類動作不推遲後面的動作**：手帳和黑板因此用同一套排程規則。
4. **先畫後講用獨立的 `draw` 時刻**：句子的 t0 不提前，字幕和 cue 仍然對著聲音。
5. **黑板的版面錯誤收進 `window.__boardProblems`，由 `board_check.py` 開瀏覽器讀**：格子大小和文字量測只有頁面裡才準，node 裡沒有字型。
6. **黑板頁先只准放 `icon`、`note`**。圖示大小分三級：手帳 s／m／l 是 96／140／200，黑板是 120／180／260，分鏡不寫像素。
7. **分頁和 lead 的邏輯從 `f5_story.py` 抽出成 `pages.py`**：草稿片要用，但原檔一開頭就 import torch。
8. **齒輪縮進留邊**：鉛筆齒輪會比現在略小，出總表時交給使用者看。
