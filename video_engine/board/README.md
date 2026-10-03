# board：紙上動畫元件庫

LLM（或人）只寫 `scene.json`：用哪些元件、做哪些動作、動作掛在哪句旁白。
畫面、排版、錨點、鏡頭、時間全由固定 runtime 處理。設計見
`docs/superpowers/specs/2026-10-03-board-runtime-design.md`，寫元件前讀 [`COMPONENTS.md`](COMPONENTS.md)。

## 出片

```bash
P=~/.local/share/pipx/venvs/webwright/bin/python   # 有 Playwright 的 Python
.venv/bin/python video_engine/board/compile.py scene.json out/tl.json [--timing timing.json]
.venv/bin/python video_engine/board/build.py out/tl.json out/player [--audio master.wav]
$P video_engine/board/check.py out/player          # 量測閘，失敗 exit 1
$P video_engine/board/export.py out/player out/video.mp4 --workers 8
```

- `timing.json`：每句旁白實測起訖 `[{"t0":..,"t1":..}]`，筆數＝beat 數。沒給就依字數估（每字 0.24 秒）。
- `out/player/player.html` 可直接用瀏覽器開，邊聽邊拖時間軸審片。
- 元件做不到的畫面會退化成文字並寫進 `gaps.jsonl`；定期看它決定下一個要補的元件。

## 範例

| 檔案 | 內容 |
| --- | --- |
| `examples/c_string.scene.json`＋`c_string.timing.json` | 重現已接受的 A＋C 字串片（沿用原配音的實測時間） |
| `examples/env_path.scene.json` | PATH 依序搜尋→找不到→加入→重開→找到，估時無聲 |

## 檔案

| 檔案 | 職責 |
| --- | --- |
| `catalog.json` | 元件目錄：型別、屬性、動作、錨點、時長。編譯器與 runtime 共用 |
| `compile.py` | 時間、可見性、版面時段（純 Python） |
| `build.py` | 產自給自足的播放器目錄 |
| `check.py` | 瀏覽器量測閘：越界、重疊、縮放下限、決定性 |
| `export.py` | 平行逐格匯出 mp4 |
| `runtime/` | `core.js` 繪製 API、`layout.js` 版面與鏡頭、`player.js` 播放、`components/` 元件 |
