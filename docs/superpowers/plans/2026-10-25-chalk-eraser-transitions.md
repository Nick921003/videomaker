# 黑板版板擦換頁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 黑板版的粉筆頁改成「板擦擦掉、在同一格寫下一頁」，進出電腦畫面／報頭／複習頁改成直線平移。

**Architecture:** 只改片子自己的 `index.html`（風格世界：版面、鏡頭）與 `video_engine/explainer/f5_story.py`（句間停頓）。版面改成單列，粉筆頁全疊在同一格，每頁一個面板；所有東西建好後，再對每張粉筆頁排一次擦除（kit 的 `X` 畫板擦，`fade` 依位置逐個淡掉）。beats.js 與 `lib/` 不動。

**Tech Stack:** HyperFrames 0.8.81、v8-chalkboard kit、F5 快取音檔、Colab 輸出。

## Global Constraints

- 設計：`docs/superpowers/specs/2026-10-25-chalk-eraser-transitions-design.md`
- 每一格畫面是 t 的純函式：不用 `Math.random`／`Date.now`。
- 不重新合成語音：`f5_story.py` 跑之前把 `F5Narrator._infer` 換成直接中止。
- 縮排：index.html 沿用 2 空白（檔案既有慣例）；Python 用 Tab。
- 不 commit（使用者另行決定）。

---

### Task 1: 句間停頓（f5_story.py）

**Files:** Modify `video_engine/explainer/f5_story.py`（TRAVEL_GAP、SCREEN_GAP、recap_start）；Test `tests/test_f5_story.py:76`

- [ ] 常數改成：

```python
# 換頁：板擦（講完 0.1＋擦 0.9＋0.2 後開口）或直線平移（講完 0.2 出發＋平移 0.9＋到位 0.1），都是 1.2 秒。
# 黑板 index.html 的 ERASE_*／LEAVE／PAN／SETTLE 配合這裡
TRAVEL_GAP = 1.2
# 進電腦畫面：講完 0.2 出發＋平移 0.9＋畫螢幕框與推近 1.4
SCREEN_GAP = 2.5
```

- [ ] `recap_start` 改成 `max(mapped, last_end + TRAVEL_GAP - 0.65)`（複習頁開始後 0.55 秒到位：出發 0.2＋平移 0.9＝1.1），註解同步；測試第 76 行期望值改成 `80.0 + self.F.TRAVEL_GAP - 0.65`。
- [ ] `.venv/bin/python -m unittest tests.test_f5_story` 通過。

### Task 2: 單列版面與每頁一個面板（index.html）

**Files:** Modify `video_engine/out/vscode_printf_chalk/index.html`：LAY 選版（約 85–119 行）、STA（約 124–135 行）、SLOT／HEAD（約 186–222 行）

- [ ] 刪掉 `packRow`／`packRing`／`SUM`／舊 `LAY`，換成：

```js
        // 粉筆頁全疊在同一格、換頁用板擦擦掉；電腦畫面各占一格排右邊，報頭、複習頁排左邊。
        // 使用者 2026-10-25：鏡頭一直往右甩又晃，手帳版直線滑過去比較順
        var NSCR = (D.screens || []).length;
        var COL_CHALK = (REC ? 1 : 0) + (END ? 1 : 0), COL_SCREEN = COL_CHALK + 1;
        var LAY = { rows: 1, cols: COL_SCREEN + NSCR, lessonCols: 1 + NSCR,
          mast: END ? { col: COL_CHALK - 1, row: 0 } : null, recap: REC ? { col: 0, row: 0 } : null };
```

- [ ] STA：每段一個框面板（邊框＋徽章），第一頁是電腦畫面的段放在那一格，否則放粉筆區；每頁自己一個面板，`x: 0`、`top: 104`（徽章一直在），`bx/by` 取自己面板中心：

```js
        var STA = CH.map(function (c, k) {
          var ls = chLines[k], np = pagesOf[k], g0 = FIXED && FIXED[k][0];
          var P = K.panel("ch" + c.n, g0 && g0.screen != null ? COL_SCREEN + g0.screen : COL_CHALK, 0);
          var pages = [], rem = ls.length, idx = 0;
          for (var j = 0; j < np; j++) {
            var fg = FIXED && FIXED[k][j], q = fg ? fg.lines.length : Math.ceil(rem / (np - j)), scr = fg && fg.screen != null ? fg.screen : null;
            var PP = K.panel("ch" + c.n + "p" + j, scr != null ? COL_SCREEN + scr : COL_CHALK, 0);
            pages.push({ j: j, x: 0, y: 0, w: PW, h: PH, top: 104, lines: ls.slice(idx, idx + q), P: PP, bx: PP.ox + PW / 2, by: PP.oy + PH / 2, screen: scr });
            idx += q; rem -= q;
          }
          return { /* 其餘欄位照舊 */ };
        });
```

- [ ] SLOT／HEAD／SCREENS 建置裡的 `st.P` 一律改成 `pg.P`。
- [ ] `npx --yes hyperframes@0.8.81 check` 0 錯。

### Task 3: 直線平移的鏡頭（index.html camera 段）

- [ ] `travel(from, to, tArrive, tMin, sway)`：同一格（粉筆頁換頁）不加鍵直接回 `tArrive`；`sway` 為真才走原本的拉遠＋轉角度（留給換章），否則只放出發、到達兩鍵，時長 `PAN = 0.9`。
- [ ] `LEAVE = 0.2`（講完後多久出發），`SETTLE = 0.1`；所有 `prev.L.end - LEAVE`／`lastLineEnd - LEAVE` 改回 `+ LEAVE`，螢幕段拉遠後的假句尾改成 `scr.tOut + 0.6 - LEAVE`。

### Task 4: 擦除排程（index.html，chrome 建完之後、camera 之前）

- [ ] 依時間排出所有粉筆頁；對每張 A 找下一張粉筆頁 B：
  - A、B 之間沒有電腦畫面的句子 → `X(A.P, [], rect, A.end + 0.1, 0.9)` 畫板擦，A 面板上每個東西依位置在板擦經過時 `fade(el, at, 0.12, 0)`；A、B 不同段時 A 段的框面板（在粉筆區時）一起擦。
  - 中間有電腦畫面 → 在第一句電腦畫面句開口時瞬間 `fade(..., 0.01, 0)`。
  - 最後一張粉筆頁不擦。
- [ ] 經過時間照 kit 的 `eraseAt`：三條帶、奇數條反向，`at = t0 + (帶 + 沿線比例) / 3 × dur`；svg 元素用 `getBBox()` 中心，HTML 元素用 `offsetLeft/Top + 寬高一半`。

### Task 5: 重建與輸出

- [ ] `f5_story.py`（`_infer` 擋掉）→ `sync.sh` → 確認 index.html 沒被蓋 → 複製 narration.wav → `stamp.py` → `fonts.py` → `PYTHON=~/.venvs/f5tts/bin/python bash tools/sfx.sh` → `tools/anchor_check.py` → `hyperframes check` → `qa.py`。
- [ ] 打包（排除 renders、qa）到 `/mnt/g/我的雲端硬碟/videomaker_render/`，Colab 先印 `os.cpu_count()`、md5 對上才解壓，`subprocess.Popen(start_new_session=True)` 起 `hyperframes render --quality draft --fps 30`，ffmpeg `-nostdin` 縮成審片版；取回後核對 md5 再傳給使用者。
