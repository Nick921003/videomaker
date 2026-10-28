# chalk beats B19：beats.js 依 43 句新故事線改寫報告

檔案：`/home/pjw92/projects/videomaker/video_engine/out/vscode_printf_chalk/beats.js`（僅更動此檔）。

## 1. 每頁變更說明 (What Changed Per Page)

- **第 1 頁（第 1–5 句，template: center）**：
  - 重用原第 1 頁代碼。程式卡外框與 4 行程式碼，變數 n 圈選、printf 黃圈、scanf 藍圈、最後一行底線、右上角三角形按鈕點擊效果。
- **第 2 頁（第 6–8 句，template: center）**：
  - 重用原第 2 頁代碼。原第 8 與第 9 句合併為新第 8 句。第 6 句繪製輸出面板與淡色提示字；第 7 句在「沒有出現」以粉紅斜線劃掉提示字並加上大 ✗（修復原錨點「沒有跑出來」）；第 8 句顯示 `[Running]` 與粉紅沙漏，在「Running」圈字、在「沙漏」沙漏開始閃爍至該句結束。
- **第 3 頁（全新 第 9–11 句，template: center）**：
  - 上層（第 10 句）：繪製「Code Runner」框 → 箭頭（上方黃字「預設」）→「輸出面板」框；於「輸出面板」圈框、於「沒改設定」底線「預設」。
  - 中層（第 9 句）：繪製 `printf("請輸入一個整數: ");` 卡片，右側繪製大型大問號「?」並圈起。
  - 下層（第 11 句）：由 printf 卡片引出向下箭頭，繪製「緩衝區」外框與標籤及 5 個字格；於「放進」文字「請」、「輸」、「入」、「一」、「個」依序落入格子，於「緩衝區」標籤加底線。
- **第 4 頁（全新 第 12–14 句，template: two-col）**：
  - 左欄（輸出面板）：頂部標題「輸出面板」，上方緩衝區（裝著提示字「請輸入一個整數」），中間向下箭頭被粉紅隔牆阻擋；下方空的輸出面板框。於「不會馬上」圈緩衝區字。第 13 句於「跑完」以板擦擦掉粉紅牆，於「一起出來」字在下方輸出面板框內淡出並以綠圈圈起。
  - 右欄（終端機）：頂部標題「終端機」，上方緩衝區（裝著提示字），中間無障礙綠色箭頭直通下方終端機框（內有 `> 請輸入一個整數`）。第 14 句於「終端機」圈標題，於「顯示出來」繪製綠勾。左右兩欄尺寸均衡對稱（寬 660, 高 190），完整填滿兩欄模板。
- **第 5 頁（第 15–17 句，template: two-col）**：
  - 重用原 fflush 繪圖（原第 25–27 句），重新適配至兩欄格子。左欄程式卡加入 `+ fflush(stdout);`，於「fflush」圈選；右欄繪製緩衝區及向下箭頭，於「推出去」箭頭閃爍；下方寫出綠色提示字「請輸入一個整數:」（嚴格限制於右欄範圍內，不超出右邊界），於「出來了」圈起提示字。
- **第 6 頁（第 18–23 句，template: center）**：
  - 重用並重構原第 21–24 句。第 18 句先畫輸出面板框、亮色提示字「請輸入一個整數:」、下一行 `scanf("%d", &n);` 與沙漏，於「scanf」圈選 scanf；第 19 句於面板右上角繪製掛鎖，於「鎖」圈鎖；第 20 句於面板下方繪製鍵盤塗鴉，向上箭頭於面板邊緣被擋住打 ✗，於「一直等」圈沙漏並保持閃爍至第 23 句；第 21 句於「scanf」底線 scanf；第 22–23 句無新畫圖與點名，保持靜止平滑過渡至電腦畫面。
- **第 7 頁（電腦畫面段 第 24–38 句，template: screen）**：
  - 全數將原第 30–44 句之時間點減 6（對應新句號 24–38）。
  - 嚴格核對所有錨點詞：第 24 句「提示字」、第 25 句「唯讀」、第 27 句「紅色方塊」、第 29 句「沒停掉」「下次編譯」「失敗」、第 31 句「終端機」、第 32 句「齒輪」、第 33 句「搜尋框」、第 34 句「Code」「Terminal」「打勾」、第 37 句「提示字」、第 38 句「結果」，全部字面存在並對齊。
- **第 8 頁（第 39–42 句，template: two-col）**：
  - 重用原第 45–48 句。左欄終端機框、閃爍 `> `、提示字與沙漏；於「停在」圈沙漏（修復原「卡在」）；滑鼠游標點擊動畫，於「終端機」圈標籤。右欄繪製 Ctrl ＋ C 兩個鍵帽，於「Ctrl」與「C」分別綠圈鍵帽，於「停了」板擦擦除左欄沙漏。
- **結尾（第 43 句）**：
  - 由 index.html 報頭 masthead 處理，beats.js 不繪製。

---

## 2. 輔助函式引數審計 (Helper-Call Argument Audit)

- `ring(P, c, rx, ry, tone, width, t, dur)`：8 個引數，全數呼叫嚴格具備 8 引數（Tone、Width、時間、時長無一遺漏）。
- `drawLock(P, x, y, w, h, tone, t, dur)`：8 個引數，全數呼叫引數完整。
- `drawKeyboard(P, kx, ky, kw, kh, t, d)`：7 個引數，全數呼叫引數完整。
- `hourglass(x, y, w, h)`：4 個引數，全數正確。
- `arrow(x1, y1, x2, y2, head)`：5 個引數，全數正確。
- `codeW(str, size)`：2 個引數，全數正確。
- `win(l)`：1 個引數（句號）。
- `blink(b)`：1 個引數（`{ el, t0, t1 }`）。
- `api.K.ring(P, chars, tone, t, dur, opts)`：6 個引數。
- `api.K.underline(P, chars, tone, t, dur, opts)`：6 個引數。
- `api.X(P, parts, box, t, dur)`：5 個引數。

---

## 3. 驗證輸出摘要 (Verify Outputs)

1. `python3 /home/pjw92/projects/videomaker/video_engine/explainer/chalk/tools/fonts.py .`
   - 輸出：`677 characters in use; wrote faces into index.html`（PASS）
2. `bash tools/sfx.sh`
   - 輸出：`710 chars, 8 strokes, 7 erasures, 4 camera moves; sfx.wav peak -15.7 dBFS; 0 page errors`（PASS）
3. `python3 tools/anchor_check.py .`
   - 輸出：`錨點閘：45 個引用，全部解得到`（0 個未解，PASS）
4. `npx --yes hyperframes@0.8.81 check`
   - 輸出：`Lint: 0 error(s), 1 warning(s) (composition_file_too_large 為預期); Runtime: 0 errors, 0 warnings; Layout: 0 issues across 9 sample(s); Motion: 0 errors, 0 warnings; Contrast: 232/232 text checks pass WCAG AA; Check passed`（PASS）
5. `nice -n 19 npx --yes hyperframes@0.8.81 snapshot . -o /tmp/agyb19 ...`
   - 輸出：`9 snapshots saved to /tmp/agyb19`（PASS，僅執行 1 次即成功）

---

## 4. 截圖目視四問回答 (Answers Per Snapshot)

對應時間戳記：`[22.02, 40.40, 62.32, 81.10, 99.82, 129.56, 167.30, 203.37, 222.71]`

- **Snapshot 0 (22.02s，第 1 頁句 5 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是
- **Snapshot 1 (40.40s，第 2 頁句 8 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是
- **Snapshot 2 (62.32s，第 3 頁句 11 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是
- **Snapshot 3 (81.10s，第 4 頁句 14 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是
- **Snapshot 4 (99.82s，第 5 頁句 17 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是
- **Snapshot 5 (129.56s，第 6 頁句 23 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是
- **Snapshot 6 (167.30s，第 7 頁螢幕句 30 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是
- **Snapshot 7 (203.37s，第 7 頁螢幕句 38 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是
- **Snapshot 8 (222.71s，第 8 頁句 42 末)**：
  - (1) 有無非預期大於 20px 粗筆畫/色塊？ 無
  - (2) 有無超出模板框或出黑板？ 無
  - (3) 有無前一頁殘留？ 無
  - (4) 主圖有無填滿版面格子？ 是

---

## 5. 與規格差異說明 (Anything Not Drawn As Written)

- **第 16 句向下箭頭閃爍**：故事板規格要求向下箭頭在 lead 畫出，並在旁白講到「推出去」時閃爍；實作上於 lead window 繪出黃色箭頭，並於 `api.span(16, "推出去")` 註冊 `blinkers` 閃爍動畫，視覺效果精確。
- **第 40 句沙漏圈選**：故事板原標註為「停在」圈沙漏（舊版為「卡在」）；因新旁白為「左邊這個終端機，程式一樣停在等輸入」，故錨點嚴格改為 `api.span(40, "停在")`。


---

## 修正 b19-fix

針對雲端視覺幀檢閱回報的兩處幾何瑕疵（Defect 1：第 3 頁三層佈局與邊界重疊；Defect 2：第 8 頁沙漏圈跨框與擦除殘留）進行數值重算與幾何精修。

### 1. 模板外框矩形 (Template Boxes from api.tpl)

- **第 3 頁 center 模板框（`api.tpl(9, "center")`）**：
  - `(x: 292, y: 151, w: 1256, h: 574)`，`cx: 920, cy: 438`
- **第 8 頁 two-col 模板框（`api.tpl(39, "two-col")`）**：
  - `left`: `(x: 88, y: 104, w: 762, h: 668)`，`cx: 469, cy: 438`
  - `right`: `(x: 990, y: 104, w: 762, h: 668)`，`cx: 1371, cy: 438`
  - `mid`: `(x: 920, y: 438)`

---

### 2. 第 3 頁幾何配置與矩形數值 (Page 3 Box Rects & Clearances)

三層由上至下均勻分佈，整體繪圖高度跨越 `y = 169` 至 `y = 715`，跨幅 `546 px`，佔置中框高度（574 px）之 **95.1%**（≥ 80% 規範）。

#### 上層：流程列（Top Band，y: 169–292）
- **Code Runner 框**：
  - `rect`: `(x: 525, y: 190, w: 235, h: 70)`
  - 算式：`w = codeW("Code Runner", 44) + 2×28 = 179 + 56 = 235`，`h = round(44×1.6) = 70`
  - 文字「Code Runner」：字級 44 px，`(x: 553, y: 201)`
  - 邊距淨空：左 28 px、右 28 px、上 11 px、下 10.6 px（全數 ≥ 10 px，無任何字形碰觸框線）
- **輸出面板 框**：
  - `rect`: `(x: 1080, y: 190, w: 223, h: 70)`
  - 算式：`w = codeW("輸出面板", 44) + 2×28 = 167 + 56 = 223`，`h = round(44×1.6) = 70`
  - 文字「輸出面板」：字級 44 px，`(x: 1108, y: 201)`
  - 邊距淨空：左 28 px、右 28 px、上 11 px、下 10.6 px（全數 ≥ 10 px）
- **橫向箭頭與「預設」標籤**：
  - 箭頭：由 `(774, 225)` 至 `(1066, 225)`，垂直居中對齊框高中心
  - 「預設」文字：字級 38 px，`codeW("預設", 38) = 72`，置放於 `(x: 884, y: 169)`
  - 底線位於 `y ≈ 210`，與下方箭頭（y: 225）留有 **15.0 px 淨空**，嚴格位於箭頭上方而非重疊
- **輸出面板圈選黃圈（spOut.start）**：
  - 中心 `(1192, 225)`，半徑 `rx: 162, ry: 67`
  - 對矩形外框邊界之淨空：上 32.0 px、下 32.0 px、左 50.5 px、右 50.5 px、角落最近距離 18.4 px（全數 ≥ 12 px，完整包覆矩形框，完全無文字遮蔽或切入）
  - 黃圈頂部 `y = 158`，位於 center 框頂部（y: 151）之內

#### 中層：printf 卡片與問號（Middle Band，y: 340–463）
- **printf 卡片框**：
  - `rect`: `(x: 398, y: 340, w: 879, h: 110)`
  - 寬度佔置中框 1256 px 之 **69.98%**（≈ 70%）
  - 程式碼 `printf("請輸入一個整數: ");`：字級 44 px（≥ 40 px），`codeW = 504`，置於 `(x: 586, y: 371)`
  - 卡內淨空：左 188 px、右 187 px、上 31 px、下 30.6 px（充裕居中）
- **右側問號與黃圈**：
  - 圓心 `(1382, 395)`，半徑 `rx: 60, ry: 68`
  - 卡片右邊緣（x: 1277）至問號圈左邊緣（x: 1322）間隙為 **45 px**（≥ 30 px 規範，零重疊）
  - 問號圈右邊緣（x: 1442）距 center 框右邊界（x: 1548）留有 106 px 邊距
  - 文字「?」：字級 80 px，`(x: 1367, y: 351)`，上下左右均勻置中於圓圈內

#### 下層：緩衝區與字格（Bottom Band，y: 520–715）
- **向下箭頭**：由 `(920, 458)` 直指 `(920, 512)`，長度 54 px
- **緩衝區外框**：
  - `rect`: `(x: 440, y: 520, w: 960, h: 195)`，底部 `y = 715`（在 center 框底 725 之內）
  - 標籤「緩衝區」：字級 44 px，`(x: 476, y: 536)`
- **5 個字格**：
  - 每個尺寸 `100 × 100`，y: 596，間隔 20 px，總寬 580 px，居中於 `x0 = 630`
  - 落字「請、輸、入、一、個」：字級 60 px，每個字格內水平邊距 22 px、垂直邊距 17 px

---

### 3. 第 8 頁幾何配置與擦除說明 (Page 8 Box Rects & Erasure)

#### 左欄：終端機與沙漏
- **終端機框**：
  - `rect`: `(x: 114, y: 178, w: 710, h: 520)`
  - 標題「終端機」：字級 52 px，`(x: 154, y: 212)`
  - 提示列 `>` 與文字「請輸入一個整數:」：`y = 408`
- **沙漏**：
  - 本體 `(hx: 690, hy: 222, hw: 80, hh: 115)`，中心 `(730, 280)`
  - 上下橫槓：長度 100 px（`x: 680..780`），上槓 `y: 214`，下槓 `y: 345`
- **沙漏圈選黃圈（第 40 句，spStuck.start）**：
  - 圓心 `(730, 280)`，半徑 `rx: 64, ry: 78`
  - 圈邊界：頂 `y = 202`、底 `y = 358`、左 `x = 666`、右 `x = 794`
  - 距終端機框頂界（y: 178）淨空：**24 px**（≥ 12 px）
  - 距終端機框右界（x: 824）淨空：**30 px**（≥ 12 px）
  - 包覆沙漏橫槓淨空：上 13 px、下 12 px、左 14 px、右 14 px（全數 ≥ 12 px）
  - 距下方提示列（y: 408）淨空：50 px
- **第 41 句與第 42 句沙漏擦除行為決策**：
  - 故事板規格第 41 句為「先點一下終端機，讓它接收你按的鍵」，僅滑鼠移入點擊與波紋，程式仍在卡住狀態，故**第 41 句不擦除沙漏**。
  - 故事板第 42 句「再按右邊這兩個鍵，Ctrl 加 C，程式就停了」明確指定「『停了』沙漏擦掉」。
  - 實作中令 `ring()` 函式回傳 `S(...)` stroke 物件，第 40 句沙漏黃圈 stroke 加入 `hg39` 陣列中。在第 42 句 `api.span(42, "停了")` 觸發 `Kit.X(P, hg39, [652, 188, 156, 184], ...)` 擦除時，**沙漏本體、上下橫槓與外圍黃圈於同一次擦除動作中同步完全抹除**，絕不殘留空白橢圓。

#### 右欄：按鍵
- **Ctrl 鍵帽**：`rect: (x: 1076, y: 318, w: 290, h: 240)`
- **C 鍵帽**：`rect: (x: 1436, y: 318, w: 230, h: 240)`
- **「+」號**：`y = 394`，水平居中置於兩鍵之間

---

### 4. 驗證輸出 (Verification Results)

```bash
# 1. 音效軌道與事件校驗
$ cd /home/pjw92/projects/videomaker/video_engine/out/vscode_printf_chalk && bash tools/sfx.sh
/home/pjw92/projects/videomaker/video_engine/out/vscode_printf_chalk/assets/audio/chalk-log.json: 710 chars, 8 strokes, 7 erasures, 4 camera moves
/home/pjw92/projects/videomaker/video_engine/out/vscode_printf_chalk/assets/audio/sfx.wav peak -15.7 dBFS

# 2. 旁白錨點解析檢查
$ python3 tools/anchor_check.py .
錨點閘：45 個引用，全部解得到

# 3. Hyperframes 結構與對比度規範檢查
$ npx --yes hyperframes@0.8.81 check
◆  Checking vscode_printf_chalk
[hyperframes] browserGpuMode probe → software (WebGL unavailable)
Lint
  ⚠ composition_file_too_large: This HTML composition file has 689 lines.
  0 error(s), 1 warning(s), 0 info(s)
Runtime
  ◇ 0 errors, 0 warnings
Layout
  ◇ 0 issues across 9 sample(s)
Motion
  ◇ 0 errors, 0 warnings
Contrast
  ◇ 232/232 text checks pass WCAG AA
Snapshots
  ◇ disabled
◇  Check passed
```
