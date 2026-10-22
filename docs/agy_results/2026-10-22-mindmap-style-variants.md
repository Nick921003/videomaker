# 心智圖視覺風格提案評估報告 (Mind Map Style Variants)

- 日期：2026-10-22
- 執行角色：`worker-frontend (agy)`
- 交付目錄：`prototypes/mindmap_styles_20261022/`
- 交付檔案：`index.html`, `variants.css`, `render.js` (資料源：`data.json`)

---

## 1. 啟動與檢視方式

本原型為純原生前端實作（無 CDN 依賴、無建置步驟、無對外網路請求），可直接透過 Python 內建 HTTP 伺服器啟動：

```bash
# 於專案根目錄執行：
python3 -m http.server 8000

# 瀏覽器開啟：
http://127.0.0.1:8000/prototypes/mindmap_styles_20261022/index.html
```

或直接在原型目錄啟動：
```bash
python3 -m http.server 8000 --directory prototypes/mindmap_styles_20261022
# 瀏覽器開啟 http://127.0.0.1:8000/
```

---

## 2. 三種視覺風格設計說明

針對使用者對既有檢視器「全部卡片均為相同米黃色、無漸變、背景與卡片缺乏區隔、缺乏層次感、偏向模板 AI 感」之反饋，本原型提供三種具備強烈專業心智圖產品風格的視覺方案：

### 方案 A：分支色彩 (Branch Color)
- **視覺哲學**：專業心智圖軟體（XMind / MindNode）經典分支視覺架構。
- **色彩系統**：
  - **根節點**：深色實心底色（`#0f172a` 深深藍灰），搭配白字與鮮明投影，建立堅實視覺核心。
  - **5 大主概念分支**：各被指派獨立色系（Branch 0: 藍綠 Teal、Branch 1: 皇家靛藍 Indigo、Branch 2: 亮紫 Violet、Branch 3: 溫暖琥珀 Amber、Branch 4: 翠綠 Emerald）。
  - **深度淡化繼承**：各分支的子節點（群組、範例、錯誤）繼承該分支色彩，底色與邊框隨層級加深逐層漸淡。
  - **連接線**：直接採用該分支色彩之平滑三次貝茲曲線（Cubic Bezier），層級流向一目了然。

### 方案 B：階層漸變 (Depth Gradient)
- **視覺哲學**：現代深色模式 (Modern Dark Slate) 與發光漸變層次，解決原版卡片與背景混濁不清的痛點。
- **色彩與明暗對比**：
  - **畫布背景**：深冷藍底色（`#0b1329`）搭配微細藍色方格紋理。
  - **卡片線性漸變**：卡片全面採用明亮線性漸變（`linear-gradient`），與背景形成鮮明對比與浮空立體感。
  - **飽和度與尺寸遞減**：
    - 深度 0（根節點）：最高彩度漸變（Sky Blue -> Royal Blue），尺寸最大（字級 20px，內距 18px 24px）。
    - 深度 1（概念主結構）：次高飽和漸變，字級 17px。
    - 深度 2（分支概念）：中等飽和天藍漸變，字級 15px。
    - 深度 3..5（群組與範例）：微弱飽和至金屬冷灰階漸變，字級 13px..12px，卡片緊湊輕盈。

### 方案 C：大綱骨架 (Outline / XMind-like)
- **視覺哲學**：極簡大綱線條風格，大幅減輕視覺負擔與卡片框線干擾。
- **架構呈現**：
  - **根節點**：圓潤膠囊形狀（`border-radius: 9999px`，底色 `#18181b`）。
  - **概念節點**：保有簡潔清晰之矩形邊框卡片（白色底色 + 分支色邊框）。
  - **深層節點（解說、群組、範例、常見錯誤）**：完全去除外框卡片與背景框，文字直接座落於彩色分支底線（`border-bottom`）之線架構上。
  - **連線整合**：貝茲曲線直接連接至各節點的底線端點，展現自然流暢的手繪導圖骨架感。

### 跨方案通用特色（精細閱讀體驗）
- **長文本解說收斂**：長達 100~150 字的 `meaning` 節點在樹狀圖中以單行省略（`text-overflow: ellipsis`）呈現，右側附加「看說明」小晶片。
- **互動彈窗詳情**：點擊「看說明」晶片會開啟對話框（`<dialog>`），完整展示概念說明文字、教材原文引用（`source_quote`）以及講義對應頁數（`handout_page`）。
- **零外部字型與依賴**：字型堆疊使用 `'Noto Sans TC', system-ui, sans-serif`，程式碼使用等寬字型，支援滾輪平滑縮放與滑鼠抓取拖曳平移。

---

## 3. 端到端驗收數據 (Acceptance Facts)

透過 Playwright 無頭瀏覽器（Chromium）於本地 HTTP 伺服器進行實測，獲取每種方案在 29 個節點之精確 DOM 與 `getBoundingClientRect()` 數據：

| 驗收項目 | 方案 A (Branch Color) | 方案 B (Depth Gradient) | 方案 C (Outline) |
|---|---|---|---|
| **(a) 算繪節點數量** | **29** (通過) | **29** (通過) | **29** (通過) |
| **(b) 節點重疊狀況** | **none** (0 處重疊) | **none** (0 處重疊) | **none** (0 處重疊) |
| **(c) 文字或外框溢出** | **none** (0 處溢出) | **none** (0 處溢出) | **none** (0 處溢出) |

### 實測驗證程序與輸出數據記錄

- **測試指令**：
  ```bash
  ~/.local/share/pipx/venvs/webwright/bin/python -c '
  import subprocess, time, json
  from playwright.sync_api import sync_playwright

  PORT = 8768
  proc = subprocess.Popen(["python3", "-m", "http.server", str(PORT), "--directory", "prototypes/mindmap_styles_20261022"])
  try:
      time.sleep(1)
      with sync_playwright() as p:
          browser = p.chromium.launch(headless=True)
          page = browser.new_page(viewport={"width": 1600, "height": 1000})
          page.goto(f"http://127.0.0.1:{PORT}/index.html")
          for var in ["variant-a", "variant-b", "variant-c"]:
              page.click(f"[data-variant=\"{var}\"]")
              page.wait_for_timeout(200)
              res = page.evaluate("""() => {
                  const nodes = Array.from(document.querySelectorAll(".mindmap-node"));
                  const boxes = nodes.map(n => ({ id: n.getAttribute("data-id"), r: n.getBoundingClientRect(), sw: n.scrollWidth, cw: n.clientWidth, sh: n.scrollHeight, ch: n.clientHeight }));
                  const overlaps = [];
                  for (let i = 0; i < boxes.length; i++) {
                      for (let j = i + 1; j < boxes.length; j++) {
                          const b1 = boxes[i].r, b2 = boxes[j].r;
                          const ox = Math.max(0, Math.min(b1.right, b2.right) - Math.max(b1.left, b2.left));
                          const oy = Math.max(0, Math.min(b1.bottom, b2.bottom) - Math.max(b1.top, b2.top));
                          if (ox > 0.5 && oy > 0.5) overlaps.push(`${boxes[i].id} & ${boxes[j].id}`);
                      }
                  }
                  const overflows = boxes.filter(b => b.sw > b.cw + 1 || b.sh > b.ch + 1).map(b => b.id);
                  return { count: nodes.length, overlaps: overlaps.length ? overlaps : "none", overflows: overflows.length ? overflows : "none" };
              }""")
              print("[{}] count={}, overlaps={}, overflows={}".format(var, res["count"], res["overlaps"], res["overflows"]))
          browser.close()
  finally:
      proc.terminate(); proc.wait()
  '
  ```

- **實測標準輸出 (STDOUT)**：
  ```text
  [variant-a] count=29, overlaps=none, overflows=none
  [variant-b] count=29, overlaps=none, overflows=none
  [variant-c] count=29, overlaps=none, overflows=none
  ```

- **結論**：所有 29 個節點在 3 種方案下均精準安置、零邊界框重疊、零文字框溢出，互動彈窗與切換正常。
