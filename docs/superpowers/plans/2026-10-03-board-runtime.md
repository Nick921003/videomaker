# 紙上動畫元件庫 實作計畫

> 執行方式：同一工作階段內依序執行（使用者授權 Claude 全權處理）。完整程式碼在各 commit，本計畫只定任務、介面、驗收指令。

**Goal:** 以 `scene.json`＋固定 runtime 取代每支手寫 Canvas HTML，先重現 A＋C 字串片，再做 PATH 30 秒。

**Architecture:** `compile.py`（純 Python）把 scene.json 與實測／估計音訊時間編成 timeline.json；瀏覽器 runtime 載入時量字排版，`render(t)` 純函式；`check.py`／`export.py` 透過 webwright 的 Python Playwright 驅動。

**Tech Stack:** Python 3（標準庫）、原生 Canvas 2D、Python Playwright 1.60（webwright venv）、FFmpeg。

## Global Constraints

- 縮排 Tab；註解中文、稀疏，只寫為什麼。
- 專案 venv 不新增依賴；JS 無 npm、無建置工具，classic script（file:// 可開）。
- 顏色只從 `video_engine/themes/paper.json` 讀；runtime 不寫 hex。
- `render(t)` 純函式：禁用 `Math.random`、`Date.now`、`performance.now`。
- 不改既有管線檔案、共用 theme、schema；不呼叫付費 LLM；TTS 需使用者同意。
- Python 測試：`.venv/bin/python -m unittest discover -s tests -t .`
- 瀏覽器端 Python：`~/.local/share/pipx/venvs/webwright/bin/python`

---

### Task 1：元件目錄與時間編譯器

**Files:** Create `video_engine/board/catalog.json`、`video_engine/board/compile.py`；Test `tests/test_board_compile.py`

**Interfaces（Produces）:**
- `compile_scene(scene: dict, timing: list[dict] | None, catalog: dict) -> dict`（timeline）
- `load_catalog() -> dict`
- CLI：`compile.py <scene.json> <out timeline.json> [--timing timing.json] [--gaps gaps.jsonl]`
- timeline 欄位：`duration`、`scenes[{id,t0,t1,title,label,keep,layout}]`、`beats[{scene,i,t0,t1,say,layout?}]`、
  `actions[{scene,beat,act,target,t0,t1,args}]`、`objects`（退化後）、`gaps[]`、`warnings[]`
- timing.json：`[{"t0": float, "t1": float}]`，長度須等於 beat 總數

**Tests（先寫、先看失敗）:**
1. 無 timing 時 beat 長度 = 字數×0.24，句間 0.35，換場另加 0.6，片尾 +1.2。
2. 有 timing 時 beat 起訖等於實測；長度不符 → `ValueError`。
3. `cue` 起點 = beat.t0 + 字元位置比例×長度；`cue` 不在 `say` → `ValueError`。
4. 無 cue 的動作接續前一動作終點；`with: prev` 同起點。
5. 序列動作長度夾在 `n×min`／`n×max`，可用時間不足時產生 `warnings` 中含「趕」。
6. 未知型別 → 物件改為 `note`，`text` 取 `fallback`，`gaps` 有一筆；不支援動作 → 移除並記 gap。
7. target 錨點前綴不是已知物件、layout 引用不存在 id → `ValueError`。

**驗收:** 測試全綠，commit。

### Task 2：runtime 骨架、note 元件、建置與量測閘

**Files:** Create `runtime/core.js`、`runtime/layout.js`、`runtime/player.js`、`runtime/player.html`、`runtime/components/note.js`、`runtime/components/marks.js`、`board/build.py`、`board/check.py`；Test `tests/test_board_build.py`

**Interfaces:**
- 全域 `Board.register(type, {measure(obj, api) -> {w,h}, anchors(obj, box, s, st) -> {name: rect}, state(obj, acts, t) -> st, draw(api, obj, box, s, st, t), overlay?(api, obj, ctx)})`
- `window.board = {ready, duration, seek(t) -> frameInfo, info(t)}`；frameInfo：`{t, boxes:[{owner, role, x,y,w,h}], scale, camera, errors}`
- `build.py <scene.json> <timeline.json> <out_dir> [--audio wav]`：複製 runtime、寫 `board_data.js`（`window.BOARD_DATA = {...}`，含 theme）
- `check.py <out_dir> [--samples N]`：輸出 `check.json`，失敗 exit 1

**Tests:** `build.py` 產出檔案齊全、`board_data.js` 內含 theme 且無 hex 出現在 runtime/*.js（掃描測試）、`register` 型別集合等於 catalog 型別（check.py 於瀏覽器內比對）。

**驗收:** 只含 note 的迷你 scene 通過 `check.py`（決定性、邊界），commit。

### Task 3：A＋C 元件與重現

**Files:** Create `components/cells.js`、`output.js`、`code.js`、`metrics.js`；`examples/c_string.scene.json`、`examples/c_string.timing.json`

**驗收:** compile → build（帶 `master.wav`）→ check 全綠；`scene.json` < 6 KB；關鍵幀截圖供自檢（非美感判斷）；commit。

### Task 4：平行匯出與並排對照

**Files:** Create `board/export.py`

**Interfaces:** `export.py <out_dir> <out.mp4> [--fps 24] [--workers 6] [--audio wav]`

**驗收:** 輸出 mp4 影格數＝ceil(duration×fps)、ffprobe 1920×1080；與 `c_string_ac.mp4` 做左右並排 `c_string_compare.mp4`；記錄渲染秒數；commit。

### Task 5：terminal、list 元件與 PATH 分鏡

**Files:** Create `components/terminal.js`、`components/list.js`、`examples/env_path.scene.json`

**驗收:** 估時無聲版通過 check、匯出 mp4；`scene.json` < 6 KB；未新增任何專為 PATH 的繪圖程式；commit。

### Task 6：文件

**Files:** Create `video_engine/board/README.md`；Modify `docs/NEXT_STEPS.md`（新增一節）

**驗收:** 走 sync-docs；commit。
