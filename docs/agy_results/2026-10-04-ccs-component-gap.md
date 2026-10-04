# 1151 電機一甲計算機概論(一) 教學動畫元件缺口分析報告

本報告以中原大學電機一甲「計算機概論(一)」（王佳盈老師，C/C++，課程代碼 EE240A）之 18 週課程計畫為基準，結合 `env_setup.md` 之板書動畫教學風格（40–90 秒紙繪風格、主物件隨時間演繹狀態變化），全面檢視現行 `catalog.json` 元件庫之支援度與功能缺口。

---

## 一、 課程摘要

- **課程名稱與定位**：計算機概論(一)（電機一甲必修 3 學分，科學B06機房上課）。兩學期之上學期，以 C/C++ 為核心，強調「邏輯歸人、語法歸 AI」的計算思維，培養問題拆解、語法審查、邊界測試與 AI 協作能力。
- **評分標準**：平時成績 40%（出席、討論、作業、小考）、期中考 20%（上機測驗）、期末考 40%（專案報告）。
- **工具鏈與平台**：
  - **開發工具**：VS Code、GCC 編譯器（MSYS2 / MinGW-w64）、C11 / C++ 標準。
  - **AI 平台與系統**：生成式 AI 教學平台（除錯提示與問答）、虛擬碼轉換器、知識點預習系統。
  - **歷程與版本控制**：Markdown（README 撰寫與 AI 使用說明九點格式）、Git/GitHub 預習（init, add, commit, diff）。

---

## 二、 週次 × 主題 × 卡關概念 × 動畫過程 × 元件缺口對照表

| 週次 | 主題 | 學生常見卡關概念（2–3項） | 動畫演繹過程（主物件與狀態變化） | 對應元件或缺口 |
| :--- | :--- | :--- | :--- | :--- |
| **W1** | 環境建置與編譯流程 | 1. PATH 變數找不到編譯器<br/>2. GCC 四階段（前置處理/編譯/組譯/連結）產物搞混<br/>3. 未存檔 vs 未重編譯快照差異 | 清單逐項尋找 gcc.exe 失敗跳錯；檔案管線（.c→.i→.s→.o→.exe）產物轉換；磁碟檔與暫存快照狀態對照。 | PATH 用現有 `list` (`walk`)；編譯四階段需 **`pipeline`**（缺）；快照用現有 `window`+`terminal`。 |
| **W2** | 程式基本結構與虛擬碼 | 1. `scanf` 殘留 `\n` 卡住下一次輸入<br/>2. 變數未初始化含垃圾值（garbage）<br/>3. 輸入→處理→輸出（IPO）資料流動 | 字元隊列指標推進，數值被讀走但 `\n` 滯留；變數格子從問號/亂數被賦值覆寫；資料從鍵盤流向變數再到螢幕。 | 隊列殘留需 **`buffer`**（缺）；變數追蹤需 **`vars`**（缺）；IPO 流程需 **`pipeline`**（缺）。 |
| **W3** | 教師節放假 | — | — | — |
| **W4** | 條件判斷與決策邏輯 | 1. `=` 賦值與 `==` 比較混淆（條件副作用）<br/>2. 短路求值（`&&`/`\|\|`）未執行右式<br/>3. switch 漏寫 `break` 造成穿透（fall-through） | 運算式求值時變數值被覆寫；布林表達式鏈左式定案後直接阻斷右式求值；分支標籤由命中點垂直貫穿往下執行。 | 運算式與變數連動需 **`vars`**（缺）；保護閾值需 **`scale`**（缺）；穿透可用現有 `code` (`highlight`)。 |
| **W5** | 迴圈與重複處理 | 1. for 三要素（init/cond/step/body）執行時序<br/>2. while vs do-while 邊界差異（0次 vs 1次）<br/>3. 迭代維護極值（如 10 筆溫度找最大值 max） | 程式碼四區塊與變數 `i` 遞增流轉；流程指針先判斷 vs 先執行；歷次輸入值與當前 `max` 比較並動態覆寫。 | 迴圈變數追蹤需 **`vars`**（缺）；極值區間需 **`scale`**（缺）；流程可用現有 `code` 輔助。 |
| **W6** | 函式與問題拆解 | 1. 傳值呼叫（Call by Value）記憶體隔離<br/>2. return 回傳值傳遞與訊框（Frame）銷毀<br/>3. 費氏數列遞迴呼叫展開與收合（unwinding） | 主函式與子函式獨立訊框，引數單向複製；訊框自堆疊頂端彈出並將值回填呼叫點；堆疊層層壓入後依序回傳坍縮。 | 訊框堆疊與遞迴展開需 **`stack`**（缺）；區域變數需 **`vars`**（缺）。 |
| **W7** | 臺灣光復紀念日補假 | — | — | — |
| **W8** | 陣列與指標 | 1. 陣列索引越界（out of bounds）<br/>2. `&` 取址與 `*` 解引用箭頭指向<br/>3. 傳址呼叫跨訊框修改外部變數 | 連續記憶體格子超出安全範圍亮紅；指標變數記錄位址並射出箭頭指向目標格，解引用覆寫目標值；箭頭跨訊框。 | 連續記憶體用現有 `cells`（需擴充 `addrs`）；指標箭頭與跨訊框需 **`vars`**+**`stack`**（缺）。 |
| **W9** | 期中整合與除錯 | 1. 多變數多迴圈追蹤表（Trace Table）<br/>2. 編譯期語法錯 vs 執行期記憶體崩潰（Segfault） | 表格隨程式碼行號推進同步變更變數；編譯期紅字攔截 vs 執行期指標指向 NULL 觸發系統崩潰。 | 變數狀態追蹤表需 **`vars`**（缺）；錯誤訊息展示可用現有 `code`+`terminal`。 |
| **W10** | 字串與結構體 | 1. 字串缺少 `\0` 結尾導致函式越界狂讀<br/>2. struct 記憶體打包與成員欄位偏移<br/>3. struct 陣列走訪與存取 | 讀取指針沿字元格子掃描，撞到 `\0` 停止，若遺失則越界讀取亂碼；複合方塊切割具名子欄位，透過 `.` 存取。 | 字串掃描用現有 `cells` (`scan`/`stop`)；struct 欄位封裝與溢位隊列需 **`vars`**/**`buffer`**（缺）。 |
| **W11** | C++ 基礎工具 | 1. `cin`/`cout` 串流提取與插入方向<br/>2. `string` 動態長度 vs C-string 固定長度<br/>3. `std::sort` 雙指標元素比較與位置交換（swap） | 資料流經管線流入變數或螢幕；字串方塊隨字元填入動態拉伸；兩格元素懸浮對調位置。 | 串流隊列需 **`buffer`**（缺）；元素交換可用現有 `cells`（需擴充 `swap` 動作）。 |
| **W12** | Markdown 與 AI 協作 | 1. Markdown 原始標記與渲染視圖映射<br/>2. README 結構與 AI 使用說明九點格式 | 左側輸入 Markdown 標題/列表/表格，右側同步渲染為美觀版面；光標依序填寫九點欄位。 | 現有 `code` + `note` + `window` 完全可直接涵蓋。 |
| **W13** | 系統化測試與驗證 | 1. 測試資料劃分（一般值/邊界值/異常輸入）<br/>2. AI 生成程式碼之隱蔽邊界 bug（off-by-one） | 數值軸劃分三個區間，測試探針在邊界點（0, 100, 101）落點，下方測試清單逐項亮出 Pass/Fail。 | 邊界測試標尺需 **`scale`**（缺）；測試清單用現有 `list` (`walk`)。 |
| **W14** | 應用任務一：獨立實作 | 1. 序列埠字串解析有限狀態機（FSM）<br/>2. 模組化函式職責切分與資料傳遞 | 狀態節點隨輸入字元（如 `$TEMP`）切換高亮；資料在多個函式呼叫間傳遞推進。 | 狀態轉換需 **`pipeline`**（缺）；字元解析需 **`buffer`**（缺）；函式切分需 **`stack`**（缺）。 |
| **W15** | 應用任務二：AI 對照 | 1. 獨立版 vs AI 版差異比對（Diff View）<br/>2. 複雜 AI 語法逐行吸收與難點聚焦 | 雙欄程式碼差異高亮（紅刪綠增）；關鍵三行放大聚焦並拉出註解卡片解說。 | 比對可用現有 `code`（需擴充 `diff` 屬性）；聚集用現有 `focus` + `note`。 |
| **W16** | 期末整合展示 | 1. 學期核心架構整合（語法→模組→系統）<br/>2. 學習歷程回顧與表達 | 各單元核心物件卡片拼裝成系統架構圖；能力向度數據揭露。 | 現有 `window` + `note` + `metrics` 完全可直接涵蓋。 |
| **W17** | Git 預習與重構 | 1. Git 三大區域（工作區/暫存區/倉庫）檔案流轉<br/>2. Commit 節點鏈生成與 HEAD 指針推進 | 檔案卡片隨 `git add` 飛入暫存區，隨 `commit` 凝結為節點；HEAD 指針隨新提交前移。 | 三大區檔案流轉需 **`pipeline`**（缺）；指令與輸出用現有 `terminal`。 |
| **W18** | 成果整理與反思 | 1. 三層能力（問題建構/情境判斷/整合負責）反思 | 成果數據指標逐一揭露，重點文字手寫劃記。 | 現有 `metrics` (`reveal`) + `note` (`write`) 完全可直接涵蓋。 |

---

## 三、 缺口元件排行（依週次複用次數由高至低）

### 1. `vars` — 變數與記憶體狀態監控面板
- **複用次數**：9 週（W2, W4, W5, W6, W8, W9, W10, W11, W14）
- **核心價值**：解決初學者「無法在腦中建立變數狀態與記憶體位址映射」的最大痛點。支援指標連線與 struct 複合欄位。
- **catalog 規格**：
  ```json
  "vars": {
      "req": ["variables"],
      "opt": ["title", "layout"],
      "anchors": ["v_{name}", "v_{name}:val", "v_{name}:addr"],
      "actions": {
          "declare": { "dur": 0.6, "req": ["name", "type"], "opt": ["val", "addr"], "blocks": true },
          "set": { "dur": 0.5, "req": ["name", "val"], "opt": ["expr"], "blocks": true },
          "point": { "dur": 0.8, "req": ["name", "to"], "opt": ["label"], "anchor_args": ["to"], "blocks": true },
          "discard": { "dur": 0.4, "req": ["name"], "blocks": true }
      }
  }
  ```

### 2. `stack` — 函式呼叫堆疊與訊框（Call Stack & Frames）
- **複用次數**：5 週（W6, W8, W9, W14, W17概念）
- **核心價值**：具體演繹傳值呼叫的記憶體隔離、區域變數生命週期、return 回傳值注入，以及費氏數列遞迴呼叫的展開與收合。
- **catalog 規格**：
  ```json
  "stack": {
      "req": [],
      "opt": ["title", "max_frames"],
      "anchors": ["f{n}", "f{n}:{var}", "top"],
      "actions": {
          "push": { "dur": 0.7, "req": ["func"], "opt": ["args", "locals"], "blocks": true },
          "pop": { "dur": 0.6, "opt": ["ret_val", "to"], "anchor_args": ["to"], "blocks": true },
          "update": { "dur": 0.45, "req": ["frame", "var", "val"], "blocks": true },
          "highlight": { "dur": 0.4, "req": ["frame"] }
      }
  }
  ```

### 3. `pipeline` — 多階段流轉管線 / 狀態機
- **複用次數**：5 週（W1, W2, W14, W15, W17）
- **核心價值**：整合編譯四階段（.c→.i→.s→.o→.exe）、IPO 三段結構、序列埠 FSM 狀態跳轉、AI 協作五步流程與 Git 三大區域流轉。
- **catalog 規格**：
  ```json
  "pipeline": {
      "req": ["stages"],
      "opt": ["title", "active"],
      "anchors": ["s{n}", "item_{id}"],
      "actions": {
          "step": { "dur": 0.6, "req": ["stage"], "opt": ["note"], "blocks": true },
          "transfer": { "dur": 0.8, "req": ["item", "from", "to"], "blocks": true },
          "reject": { "dur": 0.7, "req": ["stage", "back_to", "reason"], "blocks": true }
      }
  }
  ```

### 4. `buffer` — I/O 緩衝區隊列（Stream / UART Buffer）
- **複用次數**：4 週（W2, W10, W11, W14）
- **核心價值**：化解 C 語言第一大經典 Bug（`scanf` 殘留 `\n` 吞食後續輸入）、演繹 `cin`/`cout` 串流管線與序列埠資料封包逐字元解析。
- **catalog 規格**：
  ```json
  "buffer": {
      "req": [],
      "opt": ["title", "tokens", "capacity"],
      "anchors": ["head", "t{n}"],
      "actions": {
          "feed": { "dur": 0.5, "req": ["tokens"], "opt": ["from"], "blocks": true },
          "consume": { "dur": 0.5, "opt": ["count", "to"], "anchor_args": ["to"], "blocks": true },
          "peek": { "dur": 0.4, "req": ["index"], "opt": ["match"], "blocks": true },
          "flush": { "dur": 0.4, "blocks": true }
      }
  }
  ```

### 5. `scale` — 數值區間與測試邊界標尺
- **複用次數**：4 週（W4, W5, W13, W14）
- **核心價值**：演繹電路過載閾值判斷、溫度感測極值範圍，以及系統化測試（一般值、極端邊界值、異常值）之區間落點驗證。
- **catalog 規格**：
  ```json
  "scale": {
      "req": ["range", "zones"],
      "opt": ["unit", "title"],
      "anchors": ["p{n}", "z{n}"],
      "actions": {
          "probe": { "dur": 0.6, "req": ["value"], "opt": ["label", "result"], "blocks": true },
          "mark": { "dur": 0.5, "req": ["value", "label"], "opt": ["status"], "blocks": true },
          "set_zone": { "dur": 0.5, "req": ["zone", "range"], "blocks": true }
      }
  }
  ```

---

## 四、 現有元件小擴充即可涵蓋之項目

1. **`cells` 擴充**：
   - **新增 `addrs` 屬性**：在格子下方顯示 16 進位記憶體位址（如 `["0x1000", "0x1004", ...]`），直接支援 W8 陣列連續記憶體配置與指標偏移計算。
   - **新增 `swap` 動作**：`{"swap": {"from": 0, "to": 1}}`，演繹兩格數值對調浮動動畫，直接涵蓋 W5 溫度極值置換與 W11 `std::sort` 排序過程。
2. **`code` 擴充**：
   - **新增 `diff` 屬性與模式**：支援行增刪標記（`add: [行號]`, `del: [行號]`），直接支援 W15 獨立版 vs AI 版代碼對照與 W17 git diff 審查。
   - **新增 `token` 錨點與微聚焦**：支援行內局部標記（如 `L4:tok_op`），精準圈選標記 `=` 與 `==` 差異或缺失的分號 `;`。
3. **`output` 擴充**：
   - **新增 `append` 動作**：支援字串串接而非只能整段 `set` 替換，自然演繹多個 `printf` 或迴圈連續輸出的累積過程。
4. **`terminal` 擴充**：
   - **新增 `input_wait` 動作**：指令執行後游標停駐閃爍等待輸入，再逐字鍵入資料，真實還原 `scanf` / `cin` 的人機互動等待狀態。
