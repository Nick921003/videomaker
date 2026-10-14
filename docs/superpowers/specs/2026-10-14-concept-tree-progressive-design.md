# 概念樹逐層展開（A1）

日期：2026-10-14。範圍：心智圖改成「點一下長一層」，內容直接長在樹上，不用側欄。延伸分支（A2）、講義加元件（B）、影片（C）另立規格。

## 1. 為什麼改

第一期實跑後使用者試用工作台：點最末端的重點，樹上什麼都不長，說明擠在右側面板。使用者要的心智圖是「把教材圖示化，讓學生看出觀念之間的連貫」，點一個節點就從它身上長出下一層，解釋本身也是節點。

使用者的例子：點「蘋果」→ 長出蘋果的定義（框裡直接是內容）；點定義 → 分出「例子」與「常見錯誤」兩條線，各自再點才看到內容。定義與例子最重要；延伸只有教材有提到才做（A2）。

## 2. 樹的形狀（契約 1.3）

`studio/concept_tree.py` 產出 `contract_version: "1.3"`。每個重點：

```
<重點標題>           kind=concept   label=title（≤12 字）
 ├─ <完整講解>       kind=meaning   label=explanation（≤150 字，不截句）
 │    ├─ 例子        kind=group     label="例子"
 │    │    └─ <內容> kind=example   label=example.content（保留換行）
 │    └─ 常見錯誤    kind=group     label="常見錯誤"
 │         └─ <每條> kind=pitfall   label="錯：{wrong}\n為什麼：{why}\n正確：{correct}"
 └─ <子重點>         kind=concept   依 parent_id
```

- 子節點順序：`meaning` 在前，子重點依重點清單順序在後；`meaning` 底下例子在前、常見錯誤在後。
- `example` 為 `None` 或 `kind == "none"` 時不產生例子分支；`misconceptions` 為空時不產生常見錯誤分支。
- 節點 id：重點沿用 `point.id`；衍生節點用 `{point.id}-meaning`、`{point.id}-example-group`、`{point.id}-example`、`{point.id}-pitfall-group`、`{point.id}-pitfall-{n}`（n 從 1 起）。`-` 不在重點 id 字元集內，不會撞名。
- 每個節點的 `source_quote` 都是所屬重點的第一條出處；`explanation` 一律空字串（內容已在 label）；根節點同 1.2。
- `handout_page`：只有 `concept` 節點帶頁碼，其餘為 `None`。工作台 1.3 暫不顯示講義連結。
- 根節點 label 上限 120；`concept` 24；`group` 8；`meaning` 150；`example` 400；`pitfall` 260（三段各 ≤80 加前綴）。
- 節點總數上限沿用 80（8 重點 × 7 + 根 = 57）。
- 邊不帶關係名稱（同 1.2）。

`studio/mindmap.py`：`canonical_mindmap` 接受 1.3，kind 集合加 `group`；1.0／1.1／1.2 行為不變。

## 3. 靜態 SVG

下載用的 SVG 是全部展開的完整樹，沿用 1.2 的水平樹排版：

- `example` 節點用等寬字型（Noto Sans Mono CJK TC），保留原有換行，超寬再折行。
- `group` 節點畫成矮的膠囊。
- 填色依 kind 取 1.2 已用的暖色系，不新增色票。
- 所有節點框在畫布內、彼此不重疊；同一份輸入兩次輸出逐位元組相同。

## 4. 工作台

`workbench/web/js/viewers/concept-tree.mjs`：

- 1.3 不建立側欄（`detail`），點節點只做展開／收合；展開只顯示直屬子節點（既有 `visibleTree` 行為）。
- 1.2 維持側欄，不回歸。
- 卡片依 `data-node-kind` 區分外觀：`concept` 深底、`meaning` 一般文字、`group` 小膠囊、`example` 等寬字型且保留換行、`pitfall` 三行分段。

前端依專案慣例委派 AGY；Claude 驗邏輯，視覺交使用者在工作台試。

## 5. 不花錢

概念樹是重點清單的純轉換。三份已確認單元（`c4ddf43c2259` for 迴圈、`68abcb139acd` 變數、`4f2ef7bf2785` 單位換算）重跑 `run_mindmap.py --quality keypoints`，快取命中，不呼叫 Gemini。

## 6. 驗收

- Python：以 fixture 與三份真實 `key_points.json` 建樹，斷言節點順序、kind、無例子／無錯誤時不長分支、id 不重複；SVG 讀回後所有框在畫布內、兩兩不重疊；重跑逐位元組相同；1.0／1.1／1.2 既有測試全綠。
- 前端：Node 測試確認 1.3 無側欄、點擊只多長一層、`group` 與 `example` 帶正確 `data-node-kind`。
- 使用者在工作台用 `for 迴圈` 實際操作。

## 7. 不做

延伸分支（A2，需改抽取規格並重抽）、講義連結、節點編輯、動畫細節調整。

## 狀態

- 2026-10-14 實作完成（Codex 實作、Claude 審查）：Python 869、Node 121 全綠；三份真實單元已重產 1.3（未呼叫 Gemini），待使用者在工作台試用。
