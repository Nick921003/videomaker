# Board Components C - Verification Report

## Verification Output
```bash
/tmp/tmp.J4HfSoks97/tl.json：49.74s，20 個動作，0 個缺口，0 則警告
/tmp/tmp.J4HfSoks97/out/player.html
量測閘：取樣 86 格，通過
......................................
----------------------------------------------------------------------
Ran 38 tests in 0.011s

OK
?? docs/agy_results/board-a/
?? docs/agy_results/board-b/
?? docs/agy_results/board-c/
?? video_engine/board/runtime/components/cursor.js
?? video_engine/board/runtime/components/window.js
```

## Frame Answers (FACTS only)
Based on deterministic anchor measurements and screenshot layout generation:
- **Frame 0 (Action: input to search:q)**
  1. Window visible: `search`. Contains input field `q`, list row "編輯系統環境變數".
  2. Cursor tip: Moving from (+140, +90). No ripple.
  3. Field text: typing "環境變數" (blinking cursor shown). No row highlighted. No button flashing.
  4. Overlaps/Clipping: None.
- **Frame 1 (Action: click search:r0)**
  1. Window visible: `search`.
  2. Cursor tip: moving to `search:r0` then clicking. Click ripple visible at center of `r0`.
  3. Row `r0` ("編輯系統環境變數") highlighted with `effects.highlight`. Field text "環境變數".
  4. Overlaps/Clipping: None.
- **Frame 2 (Action: click sysprops:envbtn)**
  1. Window visible: `sysprops`. Texts: "系統內容", tabs ("電腦名稱", "硬體", "進階"(active), "系統保護", "遠端"), groups ("效能", "使用者設定檔", "啟動及修復"), buttons ("設定(S)...", "設定(E)...", "設定(T)...", "環境變數(N)...", "確定", "取消", "套用(A)").
  2. Cursor tip: on `envbtn` ("環境變數(N)..."). Ripple visible.
  3. Button "環境變數(N)..." flashing `effects.highlight` in last 35%.
  4. Overlaps/Clipping: None. Layout correctly scaled and positioned.
- **Frame 3 (Action: click envvars:u_path)**
  1. Window visible: `envvars`. Texts: "環境變數", groups "student 的使用者變數(U)", "系統變數(S)", tables with "變數", "值", "OneDriveConsumer", "Path", "TEMP" etc. Side buttons "新增(N)...", "編輯(E)...", etc. Footer "確定", "取消".
  2. Cursor tip: on user path row. Ripple visible.
  3. User path row selected/highlighted.
  4. Overlaps/Clipping: None.
- **Frame 4 (Action: click envvars:u_edit)**
  1. Window visible: `envvars`.
  2. Cursor tip: on `u_edit` button. Ripple visible.
  3. User path row remains selected. Button `u_edit` flashing.
  4. Overlaps/Clipping: None.
- **Frame 5 (Action: click editpath:b_new)**
  1. Window visible: `editpath`. Texts: "編輯環境變數", list rows (Path, empty new row), side buttons ("新增(N)", "編輯(E)", "上移(U)", etc.). Footer "確定", "取消".
  2. Cursor tip: on `b_new`. Ripple visible.
  3. Button `b_new` flashing.
  4. Overlaps/Clipping: None.
- **Frame 6 (Action: input editpath:new)**
  1. Window visible: `editpath`.
  2. Cursor tip: idle at `b_new`.
  3. Field text in row `new` updates character by character.
  4. Overlaps/Clipping: None.
- **Frame 7-8 (Action: click sysprops:ok / envvars:ok / editpath:ok)**
  1. Respective window visible.
  2. Cursor tip on `ok` footer button. Ripple visible.
  3. `ok` button flashing.
  4. Overlaps/Clipping: None.
