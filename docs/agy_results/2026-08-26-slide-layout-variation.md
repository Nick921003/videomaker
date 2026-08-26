# 投影片幾何佈局多樣化設計方案（Slide Layout Variation Proposal）

> **專案位置**：`/home/pjw92/projects/videomaker`  
> **目標**：在**嚴格保持既有暖色調配色（Warm Theme Palette）**的前提下，為教學影片投影片引入幾何與位置佈局的多樣性（Positional & Geometric Variety），解決目前 22 頁投影片高度單調的視覺痛點。  
> **設計性質**：架構與設計方案評估（Design Discussion），不更動任何生產代碼。

---

## 1. 核心立場與問題直接回答 (Core Position & Direct Answer)

### 核心問題直接回答：
> **「給定語料庫只有 2 種元素組合的現實，純渲染層（Renderer-Only）的變更值得做嗎？還是放寬提示詞（Authoring Prompt）是不可或缺的前提條件？」**

### 我們的明確立場：
**「純渲染層的變更是立即可行的 Quick Win，且極具價值；但若要達到真正的教學表達力與視覺節奏感，放寬提示詞是中期演進的不可或缺前提（Prerequisite）。我們強烈推薦採取『二階段無縫演進策略（Two-Phase Strategy）』。」**

#### 理由分析：
1. **為什麼純渲染層變更「絕對值得做」：**
   - 目前 17/22 頁的痛點**不只是元素相同，而是幾何排版過於粗暴**：頂部固定 Header Card（1840x140），底部固定 Content Card（1840x740），文字全部置中於 `x=960`，示意圖固定掛在文字正下方。
   - 即使元素完全相同（`title, subtitle, 2 bullets, callout, figure`），透過**渲染層的幾何分流**（例如：將 `boxes/steps` 與文字拆為左右雙欄 45-55 分割、依據 `figure.kind` 調整寬幅舞台、依據 `slide.role` 改變主視覺重心），即可在**零 API 成本、零破壞性、100% 向後相容**的前提下，立即讓現有 22 頁投影片的視覺豐富度提升 200%。
   - 此外，現有 5 頁 `code` 走讀頁在只有 8-10 行程式碼時，下方出現超過 300px 的巨大空白，純渲染層透過自適應高度與輔助卡片佈局即可立即修復此一空洞感。
2. **為什麼放寬提示詞「是徹底解決單調的前提」：**
   - 目前 `prompts/lesson_content.system.md` 的 **Rule 6（無 code 必有 figure）** 與 **Rule 7（code 頁嚴禁 bullet）** 屬於人為過度約束（Over-constraint）。
   - 教學影片的核心體驗是「視聽同步走讀」：在講解程式碼時，最需要的是「左側代碼、右側逐行重點說明（Step-by-step notes）」；在講解概念時，某些純金句或架構總結並不需要硬塞一個牽強的 `figure`。
   - 只有放寬 Prompt，才能解鎖更多符合認知心理學的教學視覺原型（Archetypes）。

---

## 2. 現行架構基線與不變量 (Architecture Baseline & Invariants)

在設計任何佈局方案前，必須嚴格遵守系統現有的三大契約與不變量：

1. **三層解耦契約（Three-Layer Contract）**：
   - `lesson.json`：僅描述語意內容，**嚴禁出現任何像素座標**。
   - `render_slides.py`：負責將內容繪製為 1080p 底圖（`slide_XX_base.png` / `slide_XX_full.png`），並量測所有可定址元素（含代碼行 `id:L4`、圖表項目 `fig:i2`）的實際邊界框（Bounding Box），輸出至 `layout.json`。
   - `compile_timeline.py` + `render_video.py`：動畫與鏡頭動作皆透過語意 ID 動態查詢 `layout.json` 的幾何資訊。
   - **關鍵優勢**：在 `render_slides.py` 調整任何繪製座標與卡片結構，後續的動畫、時間軸與高亮效果**完全免費自動同步**（Free Propagation）。
2. **視覺與配色不變量（Warm Palette Invariant）**：
   - 嚴格保留 `themes/warm.json` 的經典暖色文青調性：
     - 畫布背景：`#F4EDE2`
     - 卡片底色/邊框：`#FBF7F0` / `#DFD2BF`
     - 文字層級：標題 `#3B322A`、副標 `#A0673F`、內文 `#4B4238`、強調 Callout `#B85C38`
     - 代碼卡片：`#EFE6D8`
   - **佈局多樣性純粹來自空間幾何（Positional / Spatial Variation）、欄位劃分（Columnar Division）與對齊節奏（Alignment Rhythm），不引入新色彩或高對比雜訊。**

---

## 3. 三大方案深入評估 (Three Concrete Design Options)

---

### 方案一：純渲染層自適應多網格引擎 (Renderer-Only Deterministic Multi-Grid Engine)
> **定位**：零成本快速落地、100% 向後相容、零 API 支出

#### 1. 變更層級 (Layer Touched)
- **僅修改 `render_slides.py`**（以及抽取出 `layout_engine.py` 輔助計算幾何）。
- `lesson.schema.json` 與 `prompts/lesson_content.system.md` 完全不變。
- 現有 5 份教材（22 頁）直接重新跑 `render_slides.py` 即可獲得全新視覺。

#### 2. 具體幾何變形 (Concrete Layout Variants)

```
+-----------------------------------------------------------------------------+
| 1080p Canvas (1920 x 1080)                                                 |
|                                                                             |
|  [Variant 1A: Split 2-Column]       [Variant 1B: Code + Context 60/40]      |
|  +-------------------------------+  +-------------------------------+       |
|  | Header Card (1840 x 140)      |  | Header Card (1840 x 140)      |       |
|  +---------------+---------------+  +---------------------+---------+       |
|  | Left Card     | Right Card    |  | Code Card (60%)     | Note    |       |
|  | Bullets       | Figure        |  | Syntax Highlight    | Context |       |
|  | (860 x 740)   | (940 x 740)   |  | (1100 x 740)        | (700x740|       |
|  +---------------+---------------+  +---------------------+---------+       |
|                                                                             |
|  [Variant 1C: Wide Hero Stage]      [Variant 1D: Role-Asymmetric Layout]    |
|  +-------------------------------+  +---------------+-----------------------+
|  | Compact Header (1840 x 120)   |  | Left Anchor   | Main Stage            |
|  +-------------------------------+  | Title + Sub   | Bullets + Figure      |
|  | Hero Stage Card               |  | + Callout     | (1280 x 960)          |
|  | Compare / 4-5 Steps Figure    |  | (520 x 960)   |                       |
|  | (1840 x 760)                  |  +---------------+-----------------------+
+-----------------------------------------------------------------------------+
```

1. **Variant 1A: Split 2-Column (左右非對稱雙欄 / 45-55 分割)**
   - **適用情境**：`has_figure` 且 `figure.kind in ("boxes", "steps")` 且項目數 $\le 3$。
   - **幾何配置**：
     - `HEADER_BOX`：保留頂部 `(80, 60, 1840, 140)`。
     - `LEFT_CARD`（文字欄）：`(80, 230, 860, 790)`。
       - Bullets 與 Callout 垂直置中於左卡片，文字改為**靠左對齊**（Padding Left 48px），破除單調的全身置中。
     - `RIGHT_CARD`（圖表舞台）：`(980, 230, 940, 790)`。
       - 若為 `steps`，以垂直卡片流（Vertical Steps Flow）或緊湊橫向置中呈現；若為 `boxes`，以垂直疊構或 2x2 矩陣呈現。
2. **Variant 1B: Compact Code + Context Card (寬幅代碼走讀雙卡 / 60-40 分割)**
   - **適用情境**：`has_code` 頁面。
   - **幾何配置**：
     - `LEFT_CODE_CARD`：`(80, 230, 1140, 790)`。代碼放置於此，根據行數垂直置中，避免底部大片死白。
     - `RIGHT_CONTEXT_CARD`：`(1260, 230, 580, 790)`。
       - 自動將 slide 的 `note` 或 `subtitle` 作為重點金句卡片（Key Insight / Goal）展示於右側，並附帶語言標籤 Badge（如 `[C Language Walkthrough]`）。
3. **Variant 1C: Wide Hero Stage (寬幅大舞台置中型)**
   - **適用情境**：`figure.kind == "compare"`（需要左右對照空間）或 `steps` 項目數 $\ge 4$。
   - **幾何配置**：
     - `HEADER_BOX` 採用更緊湊的 `(80, 60, 1840, 120)`。
     - `STAGE_CARD`：`(80, 210, 1840, 810)`。
     - 上半部保留 1 條精簡的 Key Bullet（1840 寬幅置中），下半部給予 `compare` 完整的 1680px 寬度，每邊對照面板寬度由現有的 700px 擴展至 780px，字級提升至 30px。
4. **Variant 1D: Role-driven Asymmetry (依據教學角色打破 17 頁雷同)**
   - **適用情境**：依據 `slide["role"]`（`hook` / `concept` / `pitfall`）與頁碼索引 `idx` 進行動態變奏。
   - **幾何配置**：
     - `role == "hook"`：採用 **左側錨點大字（Left Anchor Layout）**，將 Title + Subtitle + 痛點 Callout 合併於左側獨立深色感 Card `(80, 60, 520, 960)`，右側 `(640, 60, 1200, 960)` 作為情境展演。
     - `role == "pitfall"`：在卡片左側增加 6px 的 Warning Accent Bar (`#B85C38`)，Callout 移至頂部 Hero 欄位。

#### 3. 選擇機制 (Selection Mechanism)
- **100% 確定性規則引擎（Deterministic Dispatcher）**：
  輸入參數包含：`elements` 類型集合、`figure.kind`、`len(figure.items)`、`len(code.lines)`、`slide.role`、`slide_index`。
  ```python
  def select_layout_variant(slide, slide_index):
      has_code = any(e["type"] == "code" for e in slide["elements"])
      fig = next((e for e in slide["elements"] if e["type"] == "figure"), None)
      role = slide.get("role", "concept")

      if has_code:
          code_el = next(e for e in slide["elements"] if e["type"] == "code")
          if len(code_el["lines"]) <= 12:
              return "VARIANT_1B_CODE_CONTEXT_SPLIT"
          return "VARIANT_FULLWIDTH_CODE"

      if fig:
          if fig["kind"] == "compare" or len(fig.get("items", [])) >= 4:
              return "VARIANT_1C_WIDE_HERO"
          if role == "hook":
              return "VARIANT_1D_LEFT_ANCHOR"
          # 對於一般的 concept 頁面，依據頁碼奇偶數交替左右欄位
          return "VARIANT_1A_SPLIT_LR" if (slide_index % 2 == 1) else "VARIANT_1A_SPLIT_RL"

      return "VARIANT_STANDARD_STACK"
  ```
- **拒絕隨機性（No Randomness）**：完全由語意與結構決定，保證同一份 `lesson.json` 多次渲染的輸出像素級一致。

#### 4. 溢出與邊界行為 (Overflow & Edge-case Handling)
- **5 條 Bullets**：雙欄高度不足時，Dispatcher 自動偵測並**降級回退為 Standard Single Column**，並啟動 `fit_font` 將字級由 38px 自動階梯降至 28px、`BULLET_STEP` 由 120px 壓縮至 80px。
- **20 行 Code**：自動選用全寬模式（Full-width Code Box），字級縮為 24px，`CODE_STEP` 設為 32px，完全容納 20 行且不超出 `y=1000`。
- **Compare Figure 帶 4 個項目**：選用 Variant 1C（Wide Stage），面板高度自動計算 `64 + 4 * 74 = 360px`，總高度 500px，完美容納於 810px 的舞台卡片內。

#### 5. 驗證成本 (Verification Cost)
- **$0（零成本）**：
  直接使用專案現有指令：
  `.venv/bin/python video_engine/render_slides.py video_engine/examples/c_struct.lesson.json /tmp/test_layout`
  即可秒級產生 5 頁 PNG 與 `layout.json`，並透過圖片檢視驗證幾何正確性。

#### 6. 風險與 Anti-Monotony 分析
- **優勢**：零風險、開發速度極快（約 1-2 個工作天可完成）。
- **Anti-Monotony 效果**：原本 5 門課 22 頁只有 2 種版型，實施後將擴展為 **5 種幾何版型**（雙欄左圖右文、雙欄右圖左文、代碼/說明 60-40、寬幅對比舞台、左側錨點 Hook），單調感立即消除 80%。
- **局限**：受限於 Prompt 產出的 elements 依然固定，無法呈現更進階的教學版面（如代碼行與解說 bullet 同時存在）。

---

### 方案二：全管線協同演進：Prompt 語意解鎖 + 語意教學原型 (Pipeline-Wide: Expressive Prompt + Semantic Layout Archetypes)
> **定位**：架構最優解、教學表達力最大化、最符合長遠產品需求

#### 1. 變更層級 (Layer Touched)
- **`lesson.schema.json`**：放寬約束，允許 `code` 與 `bullet/callout` 共同存在於同一 slide；新增可選的 `layout_hint`（如 `split_code_notes`, `dual_cards`, `hero_quote`）。
- **`prompts/lesson_content.system.md`**：
  - 移除「Rule 6 (無 code 必有 figure)」與「Rule 7 (code 頁嚴禁 bullet)」的生硬限制。
  - 定義 4 種具體的**教學視覺原型（Teaching Archetypes）**與對應的 elements 組織範例。
- **`render_slides.py`**：實作 4 大原型的專屬幾何排版模板。

#### 2. 具體幾何變形 (Semantic Layout Archetypes)

1. **Archetype 2A: Code-Walkthrough & Step Notes (代碼逐步導讀原型)**
   - **教學目的**：解決走讀時「只有代碼、無文字指示」的空虛感。
   - **幾何配置**：
     - 左欄 Code Card `(80, 230, 1080, 790)`：展示 8-12 行程式碼。
     - 右欄 Notes Card `(1200, 230, 640, 790)`：放置 2-3 條精煉的 bullet/callout。
     - **聯動效果**：Timeline 動畫在 `reveal` 第 2 條 bullet 時，代碼卡同步執行 `highlight` 框選對應行號！
2. **Archetype 2B: Concept Dual-Card Showdown (雙卡對決原型)**
   - **教學目的**：取代過於死板的 `figure.compare`，讓兩側各自具備標題、說明與小型代碼/圖解。
   - **幾何配置**：
     - `LEFT_CARD (Before / Pitfall)`：`(80, 230, 850, 790)`，帶有淺紅褐色邊框。
     - `RIGHT_CARD (After / Solution)`：`(990, 230, 850, 790)`，帶有主題強調色邊框。
3. **Archetype 2C: Full-Bleed Architectural Diagram (大圖解主視覺原型)**
   - **教學目的**：針對記憶體佈局（Memory Layout）、結構體對齊（Struct Padding）等核心難點。
   - **幾何配置**：
     - 頂部一條金句 Callout `(80, 180, 1840, 100)`。
     - 整面寬幅卡片 `(80, 300, 1840, 720)` 專屬用於繪製多層級結構圖（Multi-tier Boxes & Arrows）。
4. **Archetype 2D: Hook / Big Statement Callout (痛點大字金句卡)**
   - **教學目的**：第 1 頁 Hook 頁面不需硬塞示意圖，以具衝擊力的大字排版切入主題。
   - **幾何配置**：
     - 中央巨型卡片 `(240, 200, 1440, 680)`，48px 大字標題與 36px 痛點問句，搭配精緻的引號裝飾。

#### 3. 選擇機制 (Selection Mechanism)
- **語意匹配優先（Semantic-First Matching）**：
  LLM 根據教材內容自由挑選最適合的 elements 組合，Renderer 依據元素組合自動匹配原型：
  - `has_code and has_bullets` $\to$ `Archetype 2A (Code-Walkthrough)`
  - `has_figure(kind="compare")` $\to$ `Archetype 2B (Dual-Card)`
  - `has_figure(kind in ["boxes", "steps"]) and not has_bullets` $\to$ `Archetype 2C (Full-Bleed Diagram)`
  - `not has_code and not has_figure` $\to$ `Archetype 2D (Big Statement)`
- `layout_hint` 僅作為可選的覆寫標記（Override Tag），95% 以上情況完全自動分流。

#### 4. 溢出與邊界行為
- **Prompt 端主動約束**：在 Prompt 中明確規範各原型的容量上限（如「雙欄走讀頁代碼最多 12 行，右側說明最多 3 條」）。
- **Renderer 端自動防護**：若 LLM 產生的代碼超過 12 行，Renderer 自動切換至縮小字級（24px）或降級為單欄全寬展示。

#### 5. 驗證成本
- **開發階段**：撰寫 4 份測試 `lesson.json`（涵蓋 4 大原型），運行 `render_slides.py` 進行幾何驗證（**$0 成本**）。
- **整合驗收階段**：使用 `video_engine/generate_lesson.py` 測試 2-3 篇教材生成，單次 API 成本約 $0.05 美元，總驗證成本低於 $0.50 美元。

#### 6. 風險與 Anti-Monotony 分析
- **徹底杜絕單調**：每堂課的 Hook、Concept、Walkthrough、Pitfall 皆擁有完全不同的幾何外觀與節奏。
- **風險控制**：需調整 Prompt 與 Schema，需做一次輕量級的 Prompt 效果回歸測試。

---

### 方案三：基於約束求解的動態彈性排版引擎 (Constraint-Based Dynamic Box Packing Engine)
> **定位**：純演算法幾何求解器、最高靈活性、但工程複雜度與不可預測性過高（High Risk / Over-engineered）

#### 1. 變更層級 (Layer Touched)
- **重寫 `render_slides.py` 的排版核心**，引入 2D Bin Packing 或線性規劃約束求解器（如 Cassowary 演算法或類似 Flexbox 的自研演算法）。

#### 2. 幾何運作機制
- 不再有預定義的 Card 與 Box。將 1920x1080 畫布劃分為 12 欄格網（12-Column Grid）。
- 每個元素計算其「最小墨水框（Min Ink Box）」與「期望寬高比（Aspect Ratio）」：
  - 文本短 + 圖表寬 $\to$ 自動將 Header 縮小置於左上角，右側放圖表，下方放說明。
  - 只有代碼 $\to$ 自動計算代碼行數與行長，緊湊包裹代碼卡並動態居中。

#### 3. 為什麼強烈反對此方案（What We Would NOT Do & Why）：
1. **破壞教學視訊的視覺穩定度（Visual Stability Violation）**：
   動態求解器容易產生微小的像素抖動（Sub-pixel shifts）。連續兩頁投影片若因字數差了 2 個字，導致標題卡片寬度由 800px 跳動至 840px，在視訊播放時會造成強烈的視覺干擾與閃爍感。
2. **與 Timeline 動畫系統難以協同**：
   `compile_timeline.py` 依賴可預測的空間分佈來計算相機推進（Camera Push）與雷射筆軌跡。不可預測的幾何形狀極易導致鏡頭推近後裁切失誤。
3. **過度設計（Over-engineering）**：
   對於只有 4-5 頁的微課程，引入完整的 CSS 排版求解器是嚴重的過度工程。

---

## 4. 三大方案決策評估矩陣 (Comparative Decision Matrix)

| 評估維度 | 方案一：純渲染層自適應多網格 | 方案二：全管線協同演進 (推薦) | 方案三：動態彈性排版求解器 |
| :--- | :--- | :--- | :--- |
| **變更層級** | 純 `render_slides.py` | Schema + Prompt + Renderer | 純 `render_slides.py` 重構 |
| **打破單調感能力** | ★★★★☆ (由 2 種增至 5 種幾何) | ★★★★★ (教學語意與幾何深度結合) | ★★★★☆ (幾何隨機多變但缺乏語意) |
| **向後相容性** | 100% (舊教材完全受益) | 100% (舊教材回退至預設原型) | 需大量回歸測試 |
| **驗證成本** | **$0 (純本地驗證)** | **極低 (< $0.50 API 測試)** | $0 (但調試工時極高) |
| **教學表達力** | 良好 | **極佳 (解鎖代碼+條列導讀)** | 中等 |
| **工程複雜度** | 低 (1-2 天) | 中 (2-3 天) | 極高 (> 5 天) |
| **綜合推薦等級** | **第一階段首選 (Quick Win)** | **最終目標架構 (Target State)** | ❌ 不推薦 (Over-engineering) |

---

## 5. 最終推薦與實施路線圖 (Final Recommendation & Roadmap)

### 推薦路徑：二階段無縫演進 (Two-Phase Strategy)

```
[ Phase 1: 立即見效 (Option 1) ]  -->  [ Phase 2: 系統演進 (Option 2) ]
1. 重構 render_slides.py 幾何分流     1. 放寬 prompts/lesson_content.system.md
2. 實作 1A(雙欄), 1B(代碼60/40),     2. 擴充 lesson.schema.json (code+bullet)
   1C(大舞台), 1D(角色非對稱)          3. 實現 Archetype 2A (代碼導讀雙欄)
3. 零成本驗證現有 22 頁投影片          4. 小額 API 驗收新教材生成效果
```

### 明確排除事項 (What NOT to Do)：
1. ❌ **嚴禁改動暖色文青配色（Warm Palette）**：所有多樣性純靠幾何與排版節奏，絕不引進刺眼色彩。
2. ❌ **嚴禁在 Prompt / LLM 端輸出像素座標**：絕對維持三層解耦契約，LLM 只管語意，像素與測量永遠歸 `render_slides.py`。
3. ❌ **嚴禁使用動態隨機佈局（Random Layout Selection）**：所有版型選擇必須是 100% 確定性（Deterministic），相同輸入保證產生相同輸出。
4. ❌ **嚴禁自研 Flexbox/CSS 求解器**：避免畫面在換頁時產生無規律的跳動感。

---

## 6. 規劃任務合約預覽 (Planning Task Contracts)

為方便後續 `dev-orchestrator-agy` 調度，以下提供實施 Phase 1 所需的原子任務分解：

```yaml
result:
  summary: |
    Completed architectural analysis and proposed 3 concrete slide layout variation options for videomaker.
    Recommended a Two-Phase Strategy: Phase 1 (Renderer-only deterministic multi-grid engine) for immediate zero-cost wins,
    followed by Phase 2 (Authoring prompt loosening + semantic archetypes) for maximal pedagogical expressiveness.
  verification_output: "Analysis document written to docs/agy_results/2026-08-26-slide-layout-variation.md"
  artifacts:
    - docs/agy_results/2026-08-26-slide-layout-variation.md
  errors: []
  status: planned
  spec: |
    Slide Layout Variation Engine: Transform hardcoded single-column layouts in render_slides.py
    into a deterministic multi-grid system supporting 2-Column Split, 60/40 Code-Context, Wide Stage Hero,
    and Role-Asymmetric layouts while preserving the warm theme and 3-layer semantic contract.
  contracts:
    - id: TASK-001
      title: "Refactor render_slides.py geometry into modular layout dispatcher"
      scope: |
        Extract hardcoded layout constants into a layout engine module within video_engine/render_slides.py.
        Implement deterministic variant selection based on element presence, figure.kind, and code line count.
      acceptance_criteria:
        - "render_slides.py cleanly dispatches to at least 4 distinct layout geometries."
        - "layout.json continues to output accurate bounding boxes for all element IDs without schema regression."
        - "Zero changes to themes/warm.json or color assignments."
      risk_class: medium
      files_to_touch:
        - video_engine/render_slides.py
      dependencies: []
      assignee_agent: worker-coder
      verification_commands:
        - ".venv/bin/python video_engine/render_slides.py video_engine/examples/c_struct.lesson.json /tmp/test_task001"
      stack_profile: {file_ext: .py, test_command: "pytest tests/", test_file: "tests/test_*.py"}
      reuse_patterns:
        - {symbol: "draw_centered", how: "Refactor to support alignment and bounding box measurement in sub-cards"}
        - {symbol: "draw_figure", how: "Adapt figure drawing inside varying card widths"}
      context_refs:
        - docs/agy_results/2026-08-26-slide-layout-variation.md
        - video_engine/render_slides.py
      skill_hints: []

    - id: TASK-002
      title: "Implement 2-Column Split and 60/40 Code-Context Layout Variants"
      scope: |
        Implement Split 2-Column (Left Bullets + Right Figure) and 60/40 Code-Context Card geometry
        in render_slides.py. Include automatic font fitting and vertical centering for both columns.
      acceptance_criteria:
        - "Text+Figure slides render in balanced 2-column format when figure.kind is boxes or steps."
        - "Code walkthrough slides render with a 60% code card and 40% context card when lines <= 12."
        - "All action targets (e.g. id:L1, fig:i1) emit correct bounding boxes in layout.json."
      risk_class: medium
      files_to_touch:
        - video_engine/render_slides.py
      dependencies:
        - TASK-001
      assignee_agent: worker-coder
      verification_commands:
        - ".venv/bin/python video_engine/render_slides.py video_engine/examples/c_loop.lesson.json /tmp/test_task002"
        - ".venv/bin/python video_engine/render_slides.py video_engine/examples/c_struct.lesson.json /tmp/test_task002"
      stack_profile: {file_ext: .py, test_command: "pytest tests/", test_file: "tests/test_*.py"}
      reuse_patterns: []
      context_refs:
        - docs/agy_results/2026-08-26-slide-layout-variation.md
      skill_hints: []
