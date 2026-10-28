# chalk beats B20：第 6 頁 scanf 兩欄版面改寫報告

檔案：`/home/pjw92/projects/videomaker/video_engine/out/vscode_printf_chalk/beats.js`（僅更動第 18–23 句區塊，其他部分完全不變）。

## 1. 改寫背景與設計目標 (Design Motivation)

依據使用者對 B19 的回饋：
- 原版沙漏被擠在 `scanf` 行旁邊成為小圖示，黑板右半邊空曠，掛鎖孤立浮於右上角，導致視覺比重失衡。
- 使用者強調：**整支程式在等待，沙漏是這一頁的 Hero 元素**，應在右欄大幅呈現。
- 版面改為 `two-col` 雙欄對照結構：
  - **左欄**：輸出面板（標題「輸出面板」＋旁白講到「唯讀」時寫出「唯讀」並底線）、面板內亮色提示字「請輸入一個整數:」與 `scanf("%d", &n);`；面板右上角於講到「鎖住」時畫出掛鎖並圈起（圈維持 ≥ 12 px 安全邊距）；面板下方繪製鍵盤與向上受阻箭頭 ✗。面板＋鍵盤合計佔滿左欄高度 ≥ 80 %。
  - **右欄**：中央大沙漏（高度佔欄高約 60–70 %），下方標註「整個程式在等」；講到「一直等」時以橢圓圈起大沙漏並保持閃爍。
  - **雙欄對稱均衡**：所有圖元完全收斂於所屬欄位框內，距任何邊框維持 ≥ 10 px 間距。

---

## 2. 幾何座標與邊界數據 (Numerical Rects Audit)

### 模板欄位矩形 (`api.tpl(18, "two-col")`)
- **左欄 (`left`)**：`[x: 88, y: 104, w: 762, h: 668]`（中心點 `cx: 469, cy: 438`，右邊界 `850`）
- **右欄 (`right`)**：`[x: 990, y: 104, w: 762, h: 668]`（中心點 `cx: 1371, cy: 438`，右邊界 `1752`）
- **中線 (`mid`)**：`[x: 920, y: 438]`

### 左欄圖元矩形 (`left column`)
1. **輸出面板外框 (`rect`)**：
   - 矩形：`[x: 129, y: 160, w: 680, h: 350]`（底界 `510`，右界 `809`）
   - 左欄內邊界間距：左邊距 `129 - 88 = 41 px`、右邊距 `850 - 809 = 41 px`（嚴格對稱置中，≥ 10 px）。
2. **面板標題「輸出面板」**：
   - 矩形：`[x: 169, y: 184, w: 175, h: 46]`（距面板左框 40 px、頂框 24 px）。
3. **「唯讀」標籤 (`roTag19`)**：
   - 矩形：`[x: 362, y: 184, w: 87, h: 46]`（右界 `449`）。
   - 於第 19 句講到「唯讀」時寫出並底線，距右上掛鎖留有 `683 - 449 = 234 px` 寬裕間距。
4. **右上角掛鎖 (`drawLock`)**：
   - 矩形：`[x: 683, y: 184, w: 90, h: 120]`（右界 `773`，底界 `304`）。
   - 完全收納在面板右上內部（距面板右邊框 36 px，距頂框 24 px）。
5. **掛鎖粉筆圈 (`ring`)**：
   - 圓心：`[cx: 728, cy: 244]`，半徑：`rx: 69, ry: 84`。
   - 邊界跨度：`x ∈ [659, 797], y ∈ [160, 328]`。
   - **安全邊距檢查**：
     - 距左欄右外框（850）：`850 - 797 = 53 px`（遠大於 ≥ 12 px 要求）。
     - 距面板右外框（809）：`809 - 797 = 12 px`（≥ 10 px 要求）。
     - 完全位於左欄內，無出框。
6. **提示字「請輸入一個整數:」**：
   - 矩形：`[x: 179, y: 280, w: 399, h: 50]`（右界 `578`，距掛鎖 105 px）。
7. **`scanf("%d", &n);` 程式碼行**：
   - 矩形：`[x: 179, y: 380, w: 320, h: 54]`（右界 `499`，距面板底界 76 px）。
   - 第 18 句「scanf」黃圈：跨度 `x ∈ [157, 521], y ∈ [372, 442]`，距面板左框 28 px、底框 68 px。
8. **鍵盤塗鴉 (`drawKeyboard`)**：
   - 矩形：`[x: 209, y: 570, w: 520, h: 136]`（底界 `706`，左右邊距至左欄邊界均為 `121 px`）。
   - 鍵盤距左欄底部：`772 - 706 = 66 px`。
9. **向上阻擋箭頭與打叉 (`arrow` + `cross`)**：
   - 箭頭起訖：`x: 469`，`y1: 564` 至 `y2: 520`（由鍵盤朝面板下緣推進）。
   - 打叉 ✗：`[x: 447, y: 508, w: 44, h: 44]`（座落於面板下邊界阻隔點）。
10. **左欄垂直填充率檢查**：
    - 頂端頂界：`160`，底部底界：`706`。
    - 總跨度：`706 - 160 = 546 px`。
    - 左欄總高度：`668 px`。
    - **高度佔比**：`546 / 668 = 81.74 %`（符合 ≥ 80 % 要求）。

### 右欄圖元矩形 (`right column`)
1. **大沙漏本體 (`hourglass`)**：
   - 矩形：`[x: 1241, y: 180, w: 260, h: 420]`。
   - **高度佔比**：`420 / 668 = 62.87 %`（精準落入 60–70 % 要求範圍）。
   - 水平置中：於右欄 `cx: 1371` 置中，兩側距右欄邊界均為 `251 px`。
2. **大沙漏上下蓋板 (`caps`)**：
   - 頂部蓋板：線段 `(1217, 168)` 至 `(1525, 168)`（寬 308 px）。
   - 底部蓋板：線段 `(1217, 612)` 至 `(1525, 612)`（寬 308 px）。
3. **沙漏下方標註「整個程式在等」**：
   - 矩形：`[x: 1240, y: 648, w: 262, h: 46]`（底界 `694`）。
   - 距右欄底界間距：`772 - 694 = 78 px`。
4. **大沙漏粉筆圈 (`ring`，第 20 句「一直等」)**：
   - 圓心：`[cx: 1371, cy: 390]`，半徑：`rx: 170, ry: 240`。
   - 邊界跨度：`x ∈ [1201, 1541], y ∈ [150, 630]`。
   - **安全邊距檢查**：
     - 距右欄左邊界（990）：`1201 - 990 = 211 px`（≥ 12 px）。
     - 距右欄右邊界（1752）：`1752 - 1541 = 211 px`（≥ 12 px）。
     - 距右欄頂邊界（104）：`150 - 104 = 46 px`（≥ 12 px）。
     - 距右欄底邊界（772）：`772 - 630 = 142 px`（≥ 12 px）。
     - 距下方說明文字（648）：`648 - 630 = 18 px`（無重疊遮擋）。
5. **右欄垂直填充率檢查**：
   - 頂界（頂蓋）：`168`，底界（文字底部）：`694`。
   - 總跨度：`694 - 168 = 526 px`。
   - **高度佔比**：`526 / 668 = 78.74 %`。
   - 左右雙欄高度跨度（546 px vs 526 px）極致平衡對稱。

---

## 3. 輔助函式呼叫引數審計 (Helper-Call Argument Audit)

- `win(l)`：1 個引數（`win(18)`, `win(20)`）。
- `drawLock(P, x, y, w, h, tone, t, dur)`：8 個引數（`P18_23, lkX19, lkY19, lkW19, lkH19, "y", spLock.start, 0.28`）。
- `ring(P, c, rx, ry, tone, width, t, dur)`：8 個引數：
  - 掛鎖圈：`P18_23, [cx_lk19, cy_lk19], rx_lk19, ry_lk19, "y", 4.2, spLock.start + 0.2, 0.25`
  - 大沙漏圈：`P18_23, [cx_hg18, cy_hg18], rx_hg18, ry_hg18, "p", 4.2, spWait.start, 0.25`
- `drawKeyboard(P, kx, ky, kw, kh, t, d)`：7 個引數（`P18_23, kx20, ky20, kw20, kh20, w.at(0), 0.35`）。
- `hourglass(x, y, w, h)`：4 個引數（`hx18, hy18, hw18, hh18`）。
- `arrow(x1, y1, x2, y2, head)`：5 個引數（`ax, ky20 - 6, ax, by18 + bh18 + 10, 18`）。
- `codeW(str, size)`：2 個引數。
- `api.K.ring(P, chars, tone, t, dur, opts)`：6 個引數（`P18_23, scLine18.chars, "y", spScanf.start, 0.25, { sprite: false, pad: 22, padY: 8 }`）。
- `api.K.underline(P, chars, tone, t, dur, opts)`：6 個引數：
  - 唯讀底線：`P18_23, roTag19.chars, "y", spReadOnly.start + 0.15, 0.22, { sprite: false, width: 4.5 }`
  - scanf 底線：`P18_23, scLine18.chars, "y", spScanf.start, 0.25, { sprite: false, width: 5 }`
- `blinkers.push({ el, t0, t1 })`：沙漏兩組 SVG 元素於 `spWait.start` 至 `api.lineEnd(23) + 0.05` 期間持續純函式閃爍。

---

## 4. 驗證輸出日誌 (Verification Outputs)

### (1) `bash tools/sfx.sh`
```
/home/pjw92/projects/videomaker/video_engine/out/vscode_printf_chalk/assets/audio/chalk-log.json: 718 chars, 8 strokes, 7 erasures, 4 camera moves
/home/pjw92/projects/videomaker/video_engine/out/vscode_printf_chalk/assets/audio/sfx.wav peak -16.0 dBFS
```
狀態：**PASS**

### (2) `python3 tools/anchor_check.py .`
```
錨點閘：46 個引用，全部解得到
```
狀態：**PASS**（包含 `18: "scanf"`, `19: "唯讀"`, `19: "鎖住"`, `20: "一直等"`, `21: "scanf"` 全部精準對齊旁白）

### (3) `npx --yes hyperframes@0.8.81 check`
```
◆  Checking vscode_printf_chalk
[hyperframes] browserGpuMode probe → software (WebGL unavailable)

Lint
  ⚠ composition_file_too_large: This HTML composition file has 689 lines. Smaller sub-compositions are easier to read, iterate on, and diff.
    /home/pjw92/projects/videomaker/video_engine/out/vscode_printf_chalk/index.html [data-composition-id] t=0s
    Fix: Split coherent scenes or layers into separate .html files under compositions/, then mount them from the parent with data-composition-src so each file stays small enough to inspect, revise, and validate independently.
  0 error(s), 1 warning(s), 0 info(s)

Runtime
  ◇ 0 errors, 0 warnings

Layout
  ◇ 0 issues across 9 sample(s)

Motion
  ◇ 0 errors, 0 warnings

Contrast
  ◇ 240/240 text checks pass WCAG AA

Snapshots
  ◇ disabled

◇  Check passed
```
狀態：**PASS**（240/240 文字通過 WCAG AA，0 Layout 異常，0 執行期警告/錯誤）
