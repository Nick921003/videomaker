# 可用元件（只能用這裡列的型別、屬性、動作、錨點）

錨點寫法：`物件id` 指整個物件；`物件id:名稱` 指物件內某部分（下表「錨點」欄）。`{n}` 是從 0 起算的編號，code 的行號從 1 起算。

## note — 一段文字（問句、提示、字面值、註記）
- 屬性：`text`（必填，可用 `\n` 分兩行，每行 ≤ 18 字）、`style`：`headline` 大標問句｜`body` 一般｜`accent` 強調色加底線｜`code` 等寬大字（字面值，如 `"Alice"`）｜`small` 小字註記
- 動作：`write` 手寫寫出
- 錨點：只有整個物件

## cells — 一排格子（陣列、記憶體、字串的每個字元）
- 屬性：`count`（必填，格數 ≤ 8）、`label` 格子上方標籤、`values` 初始值（null＝未知，畫成斜線）、`tail` 右側「…其餘」框的說明、`accent` 用強調色畫的值（例 `["\\0"]`）
- 動作：
  - `fill`：`values` 依序從 `from`（錨點，可省略）飛進格子；`start` 起始格
  - `scan`：讀取指標從 `range[0]` 走到 `range[1]`，每格的字元飛到 `to`（錨點，通常是 output 的 `:end`）
  - `point`：指標移到 `index` 格
  - `stop`：指標停在 `index` 格並圈起；`note` 可加一句短註記（≤ 8 字）
  - `brace`：在 `range` 範圍下方畫括線並寫 `label`
- 錨點：`label`、`i{n}`

## output — 輸出框（程式印出的結果）
- 屬性：`label`（例「輸出」）
- 動作：被 cells 的 `scan` 寫入（文字逐字長出）；`set` 直接換成 `text`
- 錨點：`text` 目前文字、`end` 文字尾端（下一個字落點）

## code — 深色程式碼面板
- 屬性：`lines`（必填，每行 ≤ 40 字元）、`caption` 上方說明、`footer` 下方說明
- 動作：`highlight` 標記第 `line` 行（1 起算）
- 錨點：`L{n}`

## metrics — 並排的數字比較（2–4 欄）
- 屬性：`items: [{label, value, note}]`（value 短，例 "32"；note ≤ 10 字）
- 動作：`reveal` 揭露（給 `index` 只揭露那一欄，不給就依序全部）
- 錨點：`m{n}`

## terminal — 終端機
- 屬性：`title`、`prompt`（例 `C:\cs101>`）
- 動作：`type` 逐字打出指令 `text`｜`print` 印出 `lines`（`style: "error"` 為錯誤紅字），印完自動出現新提示字元｜`restart` 關掉重開（清空），`note` 可寫「新的終端機」
- 錨點：`cmd` 最近打的指令、`line{n}` 本次開啟後的第 n 行（0 起算，提示字元＋指令那行也算一行）

## list — 依序檢查的清單（資料夾清單、步驟清單）
- 屬性：`rows`（必填，每列 ≤ 28 字元）、`title`
- 動作：`walk` 用 `item`（例 "gcc"）標籤由上往下逐列檢查，`found` 是找到的列（不給＝每列都沒有，全打 ✗）｜`append` 在最後手寫加入新列 `text`
- 錨點：`title`、`r{n}`（含之後 append 的列）

## window — 軟體視窗（鉛筆線框示意，用來示範操作）
- 屬性：`title`、`tabs: [{id, text, active}]`、`body: [區塊…]`、`footer: [{id, text}]`（右下按鈕）
- 區塊：`{"field": {"id"}}` 輸入框｜`{"list": {"rows": [{id, text}], "min_rows", "side": [[按鈕…], …]}}` 有框清單（side 為右側直排按鈕欄）｜
  `{"table": {"columns": [..], "rows": [{id, cells: [..]}]}}`｜`{"buttons": {"items": [{id, text}], "align": "left"|"right"}}`｜
  `{"group": {"id", "title", "body": [區塊…]}}` 有標題的框
- 動作：`input` 在 `視窗id:元素id`（field 或清單列）逐字打入 `text`；要預留空白列給 input 就寫 `{"id": "new", "text": ""}`
- 被 cursor 點到時：按鈕閃一下；清單列／表格列變成選取狀態
- 錨點：每個有 `id` 的元素（分頁、輸入框、列、按鈕、group）
- **下列畫面一律用 preset**（已用真實截圖核對過），物件只寫 `{"id": "…", "preset": "…"}`，要改標題等才另外覆寫屬性。
  preset 以外的介面才自己寫，且**介面文字只能用教材原文裡出現的字樣**，教材沒寫的不要編。

| preset | 畫面 | 可指的元素 id |
| --- | --- | --- |
| `win11.search` | 開始選單搜尋 | 輸入框 `q`；結果列 `r0`「編輯系統環境變數」 |
| `win11.sys_props` | 系統內容・進階分頁 | 分頁 `t_name` `t_hw` `t_adv`（進階）`t_prot` `t_remote`；三個「設定」鈕 `perf` `profile` `startup`；`envbtn`「環境變數(N)...」；`ok` `cancel` `apply` |
| `win11.env_vars` | 環境變數 | 群組 `user`（使用者變數）：列 `u_onedrive` `u_path`（Path）`u_temp`，鈕 `u_new` `u_edit`「編輯(E)...」`u_del`；群組 `sys`（系統變數）：列 `s_comspec` `s_os` `s_path`，鈕 `s_new` `s_edit` `s_del`；`ok` `cancel` |
| `win11.edit_env_var` | 編輯環境變數（Path） | 清單列 `r0`（原有的 WindowsApps）、`new`（空白列，用 `input` 打字）；右側鈕 `b_new`「新增(N)」`b_edit` `b_browse` `b_del` `b_up` `b_down` `b_text`；`ok` `cancel` |

## cursor — 滑鼠游標（不佔版面，畫在最上層；整片只需一個）
- 動作：`click` 移到 `on`（錨點）並點一下｜`move` 移到 `to`
- 錨點：無

## 通用動作（任何物件或錨點都能用）
- `show` 淡入、`hide` 淡出（物件會先自動在第一次被動作指到時出現，通常不必 show）
- `circle` 圈起、`underline` 劃底線、`arrow` 從 target 畫箭頭到 `to`（可加 `label`）
  ——這三種標記換場時自動消失
- `focus` 鏡頭推近 target（字太小或要看細節時用）、`wide` 拉回全景（不需 target）
