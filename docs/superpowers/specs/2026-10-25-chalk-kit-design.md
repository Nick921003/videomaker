# 黑板風格套件：從岚叔複製成我們自己的穩定元件

日期：2026-10-25　狀態：方向使用者已同意，**尚未動工**（交接給下一個對話）

## 目標

以後開新題材的黑板片，直接是 printf b13 的樣子（板擦換頁、直線平移、字在下圖在上、電腦畫面段、無咻聲），一支指令從講稿跑到打包。跟岚叔原版完全脫鉤。

## 使用者定的原則

- `_vendor/` 只當參考庫，**不改、不再 sync**（見記憶 style-library）。
- 看中的風格整份複製成自己的元件，保留原作者 MIT LICENSE。手帳＝`video_engine/board/`，黑板＝`video_engine/explainer/chalk/`（本案），之後還要做白板（花叔）。
- VS Code 電腦畫面的畫法（printf beats.js 第 321–976 行）**這次不抽**，等下一個操作教學題材再抽成共用元件；範本保留電腦畫面段的版面與鏡頭。

## 要複製的東西（來源 `~/projects/_vendor/lanshu-create-ai-presenter-video/explainer/`，v1.0.0 commit 762d3ee）

| 來源 | 去處 `video_engine/explainer/chalk/` | 備註 |
| --- | --- | --- |
| `core/core.js`、`core/sfxlib.py` | `core/` | |
| `kits/v8-chalkboard/`（kit.js、kit.css、KIT.md、chalk-mask.png、grain.svg、chalklog.mjs） | `kit/` | |
| `kits/v8-chalkboard/starter/` | `starter/` | **換成 b13 的版本**（下表） |
| `tools/story.py`、`sync.sh`、`stamp.py`、`fonts.py`、`qa.py`、`render.sh`、`new_film.sh` | `tools/` | `sync.sh`／`new_film.sh` 的 ROOT 改指向 chalk/；kit 路徑由 `kits/<style>` 改成 `kit/` |
| 根目錄 `LICENSE` | `LICENSE` | MIT，保留原作者 |

starter 換成 printf 這支片（`video_engine/out/vscode_printf_chalk/`）的版本：

| 檔 | 說明 |
| --- | --- |
| `index.html` | b13：單列版面 [複習][報頭][粉筆][螢幕]、每頁一面板、`wipe()` 板擦、`travel(..., sway)`、CUE_LEAD／END_MARGIN、字在下圖在上、電腦畫面段（SCREENS）。fonts.py 會把字型寫進去，複製前要取「寫字型之前」的版本或讓 fonts.py 重寫 |
| `tools/sfx.py` | 拿掉換頁咻聲與換段敲板聲（使用者 2026-10-23） |
| `tools/anchor_check.py` | 錨點閘 |
| `beats.js` | 用原 starter 的佔位版（不要帶 printf 的內容） |

可以考慮把 index.html 裡的板擦換頁（`wipe`、`sweptAt`、`inked`）搬進 kit.js 成為正式功能——既然是自己的 kit 就能改。

## 流程指令（新寫 `video_engine/explainer/chalk_film.py`）

子命令依序：`new <story> <project>`（從 starter 開片）→ `narrate`（`f5_story.py`，`F5Narrator._infer` 擋掉，快取沒中就停下回報）→ `build`（sync、stamp、fonts、`PYTHON=~/.venvs/f5tts/bin/python bash tools/sfx.sh`）→ `check`（anchor_check、`npx --yes hyperframes@0.8.81 check`、qa.py）→ `pack`（排除 renders/qa 打 tgz 到 `/mnt/g/我的雲端硬碟/videomaker_render/`，印 md5）。

Colab 那兩格（等 md5 對上才解壓、`subprocess.Popen(start_new_session=True)`、ffmpeg `-nostdin` 縮審片版）存成 `video_engine/explainer/chalk/colab_render.py`，見記憶 render-off-local。

`f5_story.py` 現在的停頓常數：ERASE_GAP 1.8、TRAVEL_GAP 1.2、SCREEN_GAP 2.5，跟 index.html 的 ERASE_AT／ERASE_DUR（1.5）／LEAVE／PAN／SETTLE 成對，搬家時一起搬、註解寫明配對。

## 驗收（逐位元組閘）

用新套件從 `docs/experiments/2026-10-22-vscode-printf/video/chalk-story` 重開 printf，放回同一份 beats.js，`build` 後的 `index.html`、`lib/` 必須跟 `video_engine/out/vscode_printf_chalk/` 現在的逐位元組相同（音檔與 story.json 也相同）。不同＝範本漏東西。另跑 hyperframes check 0 錯、anchor_check 全過、qa 只剩複習頁結尾。

## 下一步

先照 superpowers:writing-plans 把本設計寫成計畫，再動工。
