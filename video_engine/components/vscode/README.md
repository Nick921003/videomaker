# VS Code 元件

寫分鏡就能畫出 VS Code 畫面，手帳（鉛筆）、黑板（仿真）、文章配圖（PNG）共用同一份描述。不用寫程式。

| 檔案 | 職責 |
|---|---|
| `model.js` | 描述＋動作＋時間 → 版面、狀態、錨點（純函式） |
| `paint.js` | 狀態 → 繪圖指令（rect／text／line），顏色只寫 `themes/vscode_dark.json` 的鍵 |
| `svg.js` | 指令 → SVG 字串（仿真皮膚） |
| `export_png.py` | 描述 → PNG（文章配圖） |

轉接：手帳 `board/runtime/components/vscode.js`、黑板 `explainer/chalk/kit/vscode.chalk.js`。契約登記在 `board/catalog.json` 的 `vscode`，寫錯會被 `board/compile.py` 擋下。

## 描述

```json
{"type": "vscode", "id": "vs", "folder": "c_homework", "open": "score.c", "panel": "output",
 "explorer": ["score.c", "score.exe"], "menus": ["gear"], "pages": ["settings"],
 "files": {"score.c": ["#include <stdio.h>", "int main(void) {", "\tint score;", "}"]}}
```

- `files` 必填：每個檔一份程式（一行一個字串，縮排用 `\t`）。分頁列固定列出所有檔。
- `open`：一開始開哪個檔（預設第一個）。`panel`：`output`（Code Runner 輸出面板，唯讀）或 `terminal`。
- `explorer`：檔案總管列的檔（預設同 `files`，可多列 `.exe`）。
- `menus`／`pages`：會打開的選單（`gear`）與頁面（`settings`、`extensions`），內容在 `board/presets/vscode/`。

## 動作

| 動作 | 參數 | 效果 |
|---|---|---|
| `open` | `file` | 切到那個檔的分頁 |
| `highlight` | `lines`、選填 `file` | 螢光筆標行；行不在畫面內會自動捲過去 |
| `run` | 選填 `output` | ▶ 變紅色方塊；輸出面板會先清空，終端機往下接 |
| `print` | `lines` | 面板逐行印出 |
| `input` | `text` | 在面板最後一行逐字打入 |
| `stop` | | 紅色方塊變回 ▶ |
| `panel` | `name` | 切換輸出面板／終端機，各自保留內容 |
| `tip` | `text` | 面板最後一行旁的提示框（例：無法在唯讀編輯器中編輯），下一個操作就收 |
| `menu` | `name` | 打開選單 |
| `page` | `name` | 打開設定頁／延伸模組頁 |
| `type` | `text` | 在設定頁搜尋框逐字打入；打完整才出現結果 |
| `check` | （target 寫項目，例 `vs:run_in_terminal`） | 勾選或取消勾選 |
| `close` | | 關掉選單或頁面 |

游標用 `cursor` 元件：`{"act": "move", "target": "cursor", "to": "vs:run"}`、`{"act": "click", "target": "cursor", "on": "vs:run"}`。
通用標記：`circle`、`underline`、`arrow` 加 `tone`（`ink` `muted` `accent` `warn` `ok` `info`），顏色由風格決定。

## 錨點

`run`（執行鈕）、`gear`、`explorer`、`editor`、`panel`、`panel:end`（面板最後一行的行尾）、`P1`…（面板第幾行）、
`ptab:output`、`ptab:terminal`、`tip`、`settings:search`、`L1`…（程式第幾行）、`tab:score.c`、`file:score.c`，
以及選單、頁面項目的 id（例：`settings`、`run_in_terminal`、`code_runner`，只在打開時存在）。

## 三種用法

- **手帳**：寫在 `scene.json` 的 `objects` 與每句 `do`。通用標記留到場景結束，所以關掉頁面要放到下一個場景，不然圈住頁面項目的標記會找不到錨點。
- **黑板**：寫在 `storyboard.json` 電腦畫面頁的 `screen` 與每句 `do`，`storyboard.py` 驗證、`sync_film.py` 帶進片子。
  有 `cue` 的動作從那幾個字開口時開始；沒有的從這句開始畫（開口前 lead 秒）就起跑、一個接一個。標記留到該句講完。
- **配圖**：`{"object": 描述, "do": [動作]}` 存成 JSON，
  `~/.local/share/pipx/venvs/webwright/bin/python video_engine/components/vscode/export_png.py desc.json out.png`。
  範例在 `docs/experiments/2026-10-22-vscode-printf/截圖/descs/`。
