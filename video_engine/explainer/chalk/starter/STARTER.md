# 黑板片 starter

從 printf 黑板片（`video_engine/out/vscode_printf_chalk/`）抽出來的起始樣板：板擦換頁、平移鏡頭、電腦畫面段、報頭、複習頁都在
`index.html`，多掛了黑板通用轉接（`lib/kit/board.chalk.js`），所以**置中／雙欄頁只要寫分鏡，不用寫程式**。`beats.js` 是空樣板。

## 開一支新片

```bash
cp -r video_engine/explainer/chalk/starter <片子>
python3 video_engine/explainer/sync_film.py <story 資料夾> <片子>   # lib/、旁白音檔、captions.srt
python3 video_engine/explainer/chalk/tools/stamp.py <片子>          # 依 story 改 data-duration
python3 video_engine/explainer/chalk/tools/fonts.py <片子>          # 依 fonts.json 子集化字型 → assets/fonts/
bash <片子>/tools/sfx.sh                                             # 粉筆音效 → assets/audio/sfx.wav
```

驗收（都要 0 錯）：

```bash
node video_engine/explainer/chalk/screen_check.js <片子>             # 電腦畫面錨點＋黑板頁排程（cue、until）
~/.local/share/pipx/venvs/webwright/bin/python video_engine/explainer/chalk/board_check.py <片子>   # 黑板頁版面（放不下、畫不出）
(cd <片子> && npx --yes hyperframes@0.8.81 check)
```

`sync_film.py` 會複製 story 的 `audio/narration.wav`；還沒配音的草稿要先放一個靜音檔。

## 檔案分三類

盤點來源：`git ls-files video_engine/out/vscode_printf_chalk` 與它的 `lib/`。

| 類別 | 檔案 | 誰負責 |
| --- | --- | --- |
| 風格層 | `index.html`（含 `lib/kit/kit.css` 參照）、`hyperframes.json`、`package.json`、`meta.json`、`fonts.json`、`AGENTS.md`、`CLAUDE.md`、`tools/`（`sfx.sh`、`sfx.py`、`anchor_check.py`） | starter 提供，換風格才改 |
| 產生的 | `lib/story.js`、`lib/themes.js`、`lib/components/`、`captions.srt` | `sync_film.py` |
| | `lib/core.js`、`lib/sfxlib.py`、`lib/kit/`（`kit.js`、`kit.css`、`chalk-mask.png`、`grain.svg`、`chalklog.mjs`、四個 `*.chalk.js`、`board_tpl.js`） | `sync_film.copy_components`，正本在 `explainer/chalk/core/`、`explainer/chalk/kit/` |
| | `assets/fonts/` | `tools/fonts.py`（依 `fonts.json`） |
| | `assets/audio/sfx.wav`、`chalk-log.json` | `tools/sfx.sh` |
| 每支片自己的 | `beats.js`、`assets/audio/`（旁白） | 片子 |

- `lib/core.js` 與 `lib/kit/` 原本靠 `tools/sync.sh` 從 `kits/<風格>` 複製，但那個目錄在這個 repo 不存在，改由 `sync_film.copy_components`
  帶。改動時用 `cmp` 確認過：`core.js`、`sfxlib.py`、`kit.js`、`kit.css`、`chalk-mask.png`、`grain.svg`、`chalklog.mjs`、
  `vscode.chalk.js` 和 printf 片 `lib/` 底下的逐位元組相同。
- 不帶的：printf 片的 `STARTER.md`（V8 黑板報的舊說明，指向不存在的 `new_film.sh`）、`lib/kit/KIT.md`（文件，正本
  `explainer/chalk/kit/KIT.md` 已比 printf 片那份新）。

## 黑板頁怎麼畫（`ChalkBoard`）

- 格子：`BoardTpl.tpl(api.area(第一句), template)`，數值照抄 printf 片的 `api.tpl`。
- 置中：物件由上而下、間距 40，整組在格子裡置中；雙欄：照 `col` 分左右，兩欄各自置中。整組太高或太寬就等比縮小物件（間距不縮），
  縮到 0.6 還放不下就報錯。
- 時間：`ChalkVSCode.schedule`（有 cue 從那幾個字開口起跑，沒有的從開口前 lead 開始畫）；`until` 類動作畫到 until 那幾個字開口，
  沒寫就到這頁最後一句講完。物件在第一個 `draw`／`show`／`write` 之前不出現。
- 會畫的動作：圖示 `draw` `show` `blink` `erase`、文字 `write` `show` `erase`、`callout`（圖示旁的標註框）。其他動作、圖示的
  `caption` 黑板還不會畫，會收進 `window.__boardProblems`，`board_check.py` 擋下。
