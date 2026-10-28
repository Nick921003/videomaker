# 齒輪圖示（手帳版）＋黑板電腦混合 B 版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 手帳版「打開設定」頁畫出真的齒輪並演出「Ctrl+, 或 齒輪 → 選單 → 設定」；黑板片做出 B 版：黑板講原理、中段切到畫出來的簡化 VS Code 操作、再回黑板。

**Architecture:** 手帳版新增 board 元件 `icon`（純繪製、無動作），由 scene.json 用 row／stack 排版、cursor 點擊。黑板片在 story 加 `screens`，`f5_story.py` 依 pages／screens 排句間空檔；`index.html` 把螢幕段當成一個不寫粉筆標題的特殊頁（SLOT＝螢幕區），鏡頭進出時推近／拉遠；`beats.js` 畫簡化 VS Code 與螢幕內動作。

**Tech Stack:** Python 3（.venv、~/.venvs/f5tts）、board runtime（canvas JS）、岚叔 explainer（HyperFrames 0.8.81、SVG／GSAP）、F5-TTS（本機 GPU，快取）。

## Global Constraints

- 縮排 Tab；註解中文、稀疏、只寫為什麼；不新增第三方依賴。
- 畫面是 t 的純函式：不得 `Math.random`、`Date.now`、網路。
- 不得畫出所屬頁／螢幕區；元素兩兩不重疊（標註壓在目標上除外）。
- 只畫核對過的介面文字（齒輪選單：`截圖/printf/F_齒輪選單.png`；設定視窗：`G_設定視窗.png`、`B1`、`B2`）。
- 不跑付費 LLM；F5 只在文字變動時重唸（本機）。不 push、不 merge。
- 好不好看交使用者判斷；驗收只保證不越界、不重疊、不掉框、標註落在目標框內。

---

### Task 1: board `icon` 元件＋手帳版打開設定流程

**Files:**
- Create: `video_engine/board/runtime/components/icon.js`
- Modify: `video_engine/board/catalog.json`（types 加 `icon`）
- Modify: `video_engine/board/COMPONENTS.md`、`video_engine/board/prompts/components.md`（文件）
- Modify: `docs/experiments/2026-10-22-vscode-printf/video/printf.scene.json`（open 場景）
- Test: `tests/test_board_compile.py`（icon 可被 cursor click 指到、可 show）

**Interfaces:**
- Produces: 元件型別 `icon`，屬性 `name`（目前只有 `"gear"`）、選填 `caption`（圖下方小字）；錨點只有物件本身（`gear_icon`），沒有子錨點；沒有自己的動作（只吃通用 show／hide／circle）。

- [ ] **Step 1: 失敗測試**：在 `tests/test_board_compile.py` 加測試，scene 含 `{"id":"g","type":"icon","name":"gear","caption":"左下角"}` 與 cursor，beat 內 `show g`、`click mouse on g`，編譯後 0 缺口、`g` 出現在可見物件、click 動作的 `on` 解析為 `g`。另一測試：`name` 不在允許清單（例 `"star"`）時編譯報缺口或錯誤。
- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_board_compile` → 新測試 FAIL（未知型別）。
- [ ] **Step 3:** catalog 加 `"icon": {"req": ["name"], "opt": ["caption"], "names": ["gear"], "anchors": [], "actions": {}}`；compile.py 若對未知 `name` 沒檢查就加（仿 note 的 `styles` 檢查）。
- [ ] **Step 4:** `icon.js`：`Board.register('icon', {measure, state, draw, anchors})`。measure：齒輪 140×140，有 caption 時下方加 32 字級一行；draw：用 `api.ink` 鉛筆線畫 8 齒齒輪外形（齒以多邊形頂點表示、`Board.seed(obj.id)` 定抖動）與中心圓，顏色 `text.body`；caption 用 `api.write` muted 置中。不得自己算世界座標。
- [ ] **Step 5:** 測試 PASS；全套 `.venv/bin/python -m unittest discover -s tests -t .` 綠。
- [ ] **Step 6:** scene.json：objects 加 `or`（note small「或」）、`gear_icon`（icon gear，caption「左下角」）；open 場景 layout `{"stack":[{"row":["keys","or","gear_icon"]},"gear"]}`；beats：
  1. 「解法是改一個設定。先按 Ctrl 加逗號打開設定，」：show keys（cue 逗號）
  2. 「或是點左下角的齒輪，選單跳出來，再點設定。」：show or＋gear_icon（cue 齒輪）→ click mouse on gear_icon（cue 齒輪, with prev 之後）→ show gear（cue 選單）→ click mouse on gear:settings（cue 點設定）→ circle gear:settings（with prev）
- [ ] **Step 7:** narrate_f5 → compile --timing → build → check.py（量測閘通過）→ export `vscode_printf_v5.mp4`；抽句末一格確認游標先在齒輪、後在「設定」。

### Task 2: 黑板 story 加螢幕段與換頁空檔

**Files:**
- Modify: `docs/experiments/2026-10-22-vscode-printf/video/chalk-story/script.md`（章節：fflush 只剩第 7 句；新章 `screen | 在電腦上做一次` 放 8–12）
- Create: `.../chalk-story/screens.json` → `[{"lines":[8,9,10,11,12],"kind":"vscode"}]`
- Modify: `.../chalk-story/pages.json` → `[[1,2],[3,4],[5,6],[7],[13,14]]`
- Modify: `video_engine/explainer/f5_story.py`
- Test: `tests/test_f5_story.py`（skipUnless f5 依賴，同 test_tts_f5）

**Interfaces:**
- Produces: `story.screens = [{"lines":[...], "kind":"vscode"}]`；`story.pages` 不含螢幕句；換頁（含進出螢幕）句間空檔 ≥ `TRAVEL_GAP = 0.9`，進出螢幕 ≥ `SCREEN_GAP = 1.6`（畫螢幕框＋推近需要時間）。
- `make_pages(s, story_dir)` 驗證：pages ∪ screens 依序涵蓋所有正文句、互不重疊、同頁不跨章、螢幕段不跨章。
- 純函式 `gap_after(prev_i, cur_i, page_of, screen_of, base)` 回傳句間空檔。

- [ ] **Step 1:** 失敗測試：`gap_after` 同頁回 base；換頁回 max(base, 0.9)；進／出螢幕回 max(base, 1.6)；螢幕內句與句回 base。`make_pages` 遇到 pages 與 screens 重疊句時 SystemExit。
- [ ] **Step 2:** 跑測試 FAIL。
- [ ] **Step 3:** 實作（`screen_of = {i: k for k, sc in enumerate(screens) for i in sc["lines"]}`；頁鍵以 `("p", n)`／`("s", k)` 區分）；`s["screens"] = screens`。
- [ ] **Step 4:** 測試 PASS。
- [ ] **Step 5:** `(cd <lanshu>/explainer && python3 tools/story.py <chalk-story> --dry)` 重產骨架（免費）→ `~/.venvs/f5tts/bin/python video_engine/explainer/f5_story.py <chalk-story>`；確認句句不重疊、換頁空檔符合。

### Task 3: index.html 螢幕頁、蛇行走位、進出鏡頭

**Files:**
- Modify: `video_engine/out/vscode_printf_chalk/index.html`

**Interfaces:**
- Consumes: `story.pages`、`story.screens`。
- Produces（給 beats.js）：`api.screen(k)` → `{P, x, y, w, h, lines, kind, tIn, tOut}`（螢幕區，面板座標，16:9，w=1600）；`api.slot(l)` 對螢幕句回傳整個螢幕區；螢幕句不寫粉筆標題、`api.head(l)` 回 null；`api.caption(l)` 由 beats 自行畫字幕條（index 不畫）。

- [ ] **Step 1:** 頁分組：螢幕段在其章節裡是一頁（`FIXED` 加入螢幕頁），頁物件帶 `screen: k`。
- [ ] **Step 2:** 螢幕頁不建 HEAD；SLOT 與 `screen(k)` 為面板中央 1600×900 區；章節徽章照畫。
- [ ] **Step 3:** 下排（row 1）章節內頁序反轉：`x = (row === 1 ? np - 1 - j : j) * (PW + GAP)`，徽章跟著第一頁（右端）走。
- [ ] **Step 4:** 鏡頭：進螢幕＝travel 到面板（s 1.0）於 `tIn = 第一句.start - 1.6 + 0.9`，粉筆框在 `[tIn, tIn+0.6]` 畫出（`K.S` 一筆、記 `mark('screenOn')`），`tIn+0.9` 推到螢幕中心 s=1.2（travel key）；螢幕內句不加 drift keys（留給 beats 的 `api.look`）；出螢幕＝`tOut = 最後一句.end + 0.1` 拉回 s 1.0，再照常 travel 到下一頁。
- [ ] **Step 5:** 驗：`npx --yes hyperframes@0.8.81 check .` 0 error；headless 逐句取 CAM，列出相鄰頁位移方向，確認蛇行（上排右、下、下排左）。

### Task 4: beats.js（委派）

**Files:** Modify `video_engine/out/vscode_printf_chalk/beats.js`（只動它）

- 螢幕段：簡化 VS Code（標題列、左側活動列含左下齒輪、檔案總管、編輯區 s2_scanf_fflush.c、下方面板 輸出／終端機、齒輪選單、設定視窗、游標），配色為 beats 內常數；字幕條在螢幕底部。動作：8 唯讀提示（游標點輸出面板、打字→「無法在唯讀編輯器中編輯」氣泡、紅圈）；9 游標點齒輪→選單→「設定」；10 設定視窗、搜尋框逐字打 run in terminal；11 勾選框打勾＋黃色底線；12 切到終端機、逐行「請輸入一個整數: 5」「你輸入的是 5」、綠勾。每動作綁 `api.at`，標註位置由元素框計算；必要時 `api.look` 推近再退回 1.2。
- 黑板頁：所有元素分散在整句旁白的詞上，句末剛好畫完；新頁分組下（7 獨頁、13–14 同頁）重排。
- 音效標記：點擊 `api.mark('click')`、打字 `api.mark('key')`（sfx.py 加對應輕聲）。

### Task 5: 邊框卡頓定位（回報，不先修）

- [ ] 用 headless 逐格擷取 v3 一段 travel（例：第 6→7 頁），比對相鄰幀邊框位移；確認是 CSS 3D rotateY＋軟體繪圖造成、還是 key 不連續。寫成回報給使用者。

### Task 6: 音效、字型、檢查、輸出

- [ ] `sfx.py` 加 `click`、`key` 兩種輕聲（-38 dB 以下）；`screenOn` 用一筆粉筆線聲。
- [ ] `fonts.py`、`sfx.sh`、`hyperframes check`、`render.sh`（DRAFT=1 先出低清審片版給使用者，確認後再出正式版）。
