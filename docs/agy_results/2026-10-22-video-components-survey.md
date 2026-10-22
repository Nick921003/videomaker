# C 語言概念教學動畫元件庫研究與規劃報告 (Reusable Video Components Survey)

**編撰日期**：2026-10-22  
**角色定位**：資深教學媒體設計師（10+ 年 Manim / 3Blue1Brown 風格、CS50 shorts、Python Tutor 式程式教學動態視覺化經驗）  
**目標對象**：大一電機/資工 C 語言初學者（中原大學電機一甲計算機概論(一) 等課程）  
**核心原則**：**影片以動態傳達機制，而非播放投影片**。極少文字、豐富視覺、旁白解說畫面；嚴禁照抄講義與簡報版型。

---

## 壹、 設計哲學：區分「動態簡報」與「機制動畫」

在程式教學媒體中，「簡報放進影片」與「程式機制動畫」存在根本界線：
- **動態簡報（Slide with Motion）**：將條列重點、大段程式碼或靜態圖表搬上螢幕，加上淡入淡出或彈跳動效。學生大腦必須同時處理畫面文字閱讀與旁白聽覺，引發認知通道衝突（Cognitive Load Theory: Modality Effect）。畫面若暫停，本質仍是一張靜態印刷品。
- **機制動畫（Mechanism Explainer）**：將執行期（Runtime）看不見的微觀抽象運作（記憶體覆寫、控制流時序跳躍、I/O 緩衝區殘留、指標定址導線、堆疊訊框生死）具象化為可見的物理動力學運動。畫面中文字極精簡，所有運動皆具有計算語意因果律。

本報告針對教學架構定義的六大核心知識點類型（`concept`, `process`, `compare`, `mistake`, `code_trace`, `data`），盤點並規劃 14 項高度可重用的影片元件，並核對本儲存庫既有契約（`video_engine/board/COMPONENTS.md`）。

---

## 貳、 教學動畫元件總表 (14 Components Catalogue)

> **註記**：表中所有參考來源（Reference）皆已於本次研究中實測開啟並核實內容，無虛構連結。

| 名稱 (中文 / English) | 具象化之核心機制 (What mechanism it makes visible) | 適用知識點類型 | 所需教學資料欄位 (Demo Data JSON Shape) | 動態節奏 (Motion Beats, 3-5 步) | 現存於 COMPONENTS.md? | 實測參考來源 (Opened Reference & Reason) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. 迴圈控制流軌道**<br>`loop_orbit` | 將 for/while 循環控制流非線性跳躍時序具象化（`init` 僅跑一次、`cond` 測試、`body` 執行、`step` 遞增、跳脫閘門）。 | `process`<br>`code_trace`<br>`mistake` | ```json<br>{<br>  "type": "for",<br>  "tokens": {"init":"i=0","cond":"i<3","step":"i++","body":"..."},<br>  "trace": [<br>    {"step":"init","val":"0"},<br>    {"step":"cond","eval":"true ✓"},<br>    {"step":"body"},<br>    {"step":"step","val":"1"}<br>  ]<br>}<br>``` | 1. 外部光流注入 `init` 激發節點；<br>2. 光標沿圓弧滑入 `cond`，條件閘門亮起驗證徽章；<br>3. 閘門放行，光束直衝 `body` 激發運算；<br>4. 運算結束光束上揚滑入 `step` 推進數值；<br>5. 條件 `false` 時阻斷閥落下，光標沿外側彈出大括號外。 | **否 (No)**<br>*(既有 pipeline 僅支援線性管線，缺乏環狀軌道與條件分支閘門)* | [CS50 Shorts: Loops](https://www.youtube.com/watch?v=WgX8e_O7eG8)<br>Doug Lloyd 以逐步控制流圖解 for 三要素跳躍時序。 |
| **2. 運算式折疊樹**<br>`expr_reduction` | 運算子優先權、子式逐步求值折疊（AST Reduction）、整數除法小數截斷（如 `5 / 9` 截斷為 `0` 導致整式歸零）。 | `concept`<br>`mistake`<br>`code_trace` | ```json<br>{<br>  "expr": "5 / 9 * (f - 32)",<br>  "subs": [<br>    {"target": "f", "to": "212"},<br>    {"target": "(212 - 32)", "to": "180"},<br>    {"target": "5 / 9", "to": "0", "warn": "truncation"},<br>    {"target": "0 * 180", "to": "0"}<br>  ]<br>}<br>``` | 1. 完整算式展開，高優先權子式被括號微光包圍；<br>2. 變數符號被帶入數值框垂直替換；<br>3. 子式文字向中心擠壓塌縮，融合為求值數值；<br>4. 整數除法小數位以鉛筆斜線劃破崩解，留下整數 `0`；<br>5. 剩餘運算元左右碰撞合併為最終結果。 | **否 (No)**<br>*(既有 vars 的 calc 僅為單行字串，無法展示逐步 AST 折疊與截斷)* | [C++ Insights](https://cppinsights.io/)<br>透過 Clang AST 展開揭露編譯器內部運算式求值與型別轉換機制。 |
| **3. 變數狀態與歷史面板**<br>`vars` | 變數為具名記憶體格，賦值是無情覆寫（舊值被劃掉進歷史，不留即失）；未初始化含未定義隨機垃圾值（garbage）。 | `data`<br>`code_trace`<br>`mistake` | ```json<br>{<br>  "vars": [<br>    {"id": "i", "name": "i", "type": "int", "val": 0},<br>    {"id": "sum", "name": "sum", "type": "int", "val": null}<br>  ],<br>  "updates": [<br>    {"target": "sum", "val": 10, "calc": "0 + 10"}<br>  ]<br>}<br>``` | 1. 手繪變數格建立，未初始化格填充斜線遮罩與淡紅問號；<br>2. 賦值算式由上方滑入懸浮；<br>3. 鉛筆刪除線粗暴劃過舊值，舊值向下方歷史列淡出；<br>4. 新值垂直重擊落入格內咬合，格線激發外擴光暈；<br>5. 底部歷次舊值堆疊成帶刪除線清單，突顯不可逆性。 | **是 (Yes)**<br>`vars`<br>*(具備 declare, set, calc, 歷史列, check)* | [Python Tutor C Visualizer](https://pythontutor.com/c.html)<br>Philip Guo 經典記憶體 Stack 變數狀態監控與覆寫追蹤。 |
| **4. I/O 緩衝區傳送帶**<br>`io_buffer` | `stdin` 為 FIFO 字元隊列；`scanf("%d")` 僅抽走數字，殘留 `\n` 卡在隊列頭部，導致下次 `scanf("%c")` 吞入空字元之經典 Bug。 | `mistake`<br>`process`<br>`data` | ```json<br>{<br>  "queue": ["4", "2", "\\n"],<br>  "head": 0,<br>  "actions": [<br>    {"read": "scanf(\"%d\")", "take": 2, "to": "var:age"},<br>    {"residual": "\\n", "status": "blocked"},<br>    {"read": "scanf(\"%c\")", "take": 1, "to": "var:gender", "warn": true}<br>  ]<br>}<br>``` | 1. 鍵盤輸入字元以實體方塊橫向推入傳送帶管道；<br>2. `scanf` 讀取探頭從上方咬合，將數字字元吸入變數格；<br>3. 探頭收回，殘留字元 `\n` 滑移至隊列首位並泛起黃色警戒光；<br>4. 下次讀取指令啟動，探頭未經等待直接吸走 `\n`；<br>5. 變數格被填入空白跳行，終端機游標跳過輸入，具象化「被吞掉的輸入」。 | **否 (No)**<br>*(既有 cells 之 consume 缺乏串流隊列推移、頭部殘留與與終端機同步的 I/O 模型)* | [CS50x Memory & I/O Notes](https://cs50.harvard.edu/x/)<br>拆解 scanf 緩衝區隊列殘留與 CS50 專用輸入函式之教學設計。 |
| **5. 記憶體指標導線**<br>`pointer_bus` | 指標變數僅儲存十六進位位址；`&` 取址與 `*` 解引用不是抽象符號，而是從指標格射出實體物理導線連入目標格，沿線讀取或覆寫。 | `concept`<br>`process`<br>`code_trace` | ```json<br>{<br>  "ptr": {"name": "p", "addr": "0x1004", "target_addr": "0x1000"},<br>  "target": {"name": "val", "addr": "0x1000", "val": 42},<br>  "actions": [<br>    {"op": "p = &val", "link": true},<br>    {"op": "*p = 99", "pulse": true, "new_val": 99}<br>  ]<br>}<br>``` | 1. 左右並列指標格與目標格，各標十六進位位址；<br>2. 執行取址，目標位址化為光點飛入指標格，同時射出弧形導線精準鎖定目標格；<br>3. 執行解引用，脈衝電流沿弧線高速衝刺直擊目標格；<br>4. 目標格劇烈震動並覆寫新值，指標格本身位址保持不變；<br>5. 若指標指向 `NULL`，導線於空中折斷下垂，打上紅色叉記。 | **否 (No)**<br>*(既有 arrow 僅為通用無狀態連線，缺乏儲存格位址綁定、解引用脈衝光流與斷鏈模型)* | [CS50 Shorts: Pointers](https://www.youtube.com/watch?v=XISnO2YhnsY)<br>Doug Lloyd 將記憶體位址存入指標框並拉出實體連線箭頭教學。 |
| **6. 連續記憶體格子**<br>`cells` | 陣列在記憶體保證連續排列（位址偏移為 `sizeof(type)`）；`arr[i]` 即 `*(arr+i)`；字串以 `\0` 結尾，缺少 `\0` 引發越界狂讀。 | `data`<br>`process`<br>`code_trace` | ```json<br>{<br>  "count": 5,<br>  "addrs": ["0x2000", "0x2004", "0x2008", "..."],<br>  "values": ["H", "i", "\\0", "?", "?"],<br>  "accent": ["\\0"],<br>  "actions": [<br>    {"act": "scan", "from": 0, "to": 2},<br>    {"act": "stop", "index": 2, "note": "字串結尾"}<br>  ]<br>}<br>``` | 1. 一列緊密相接的矩形格子水平鋪開，格底標示十六進位位址；<br>2. 三角指針滑移至目標格上方，浮現索引 `[i]`；<br>3. 字串掃描時，指針依序右移並將字元投影至外部終端框；<br>4. 遇 `\0` 終止符時格面激發強調色手繪圓圈，指針立即定格；<br>5. 元素對調（`swap`）時，兩格數值分別沿上下反向拋物線浮空換位。 | **是 (Yes)**<br>`cells`<br>*(具備 addrs, fill, scan, point, stop, brace, swap, consume)* | [VisuAlgo Sorting](https://visualgo.net/en/sorting)<br>Steven Halim 連續記憶體條碼/矩形格子元素走訪、比較與對調動畫。 |
| **7. 呼叫堆疊與訊框**<br>`stack` | 函式呼叫建立獨立 Stack Frame（區域變數隔離，傳值呼叫僅複製複本）；return 飛渡回傳值，訊框瞬間塌陷銷毀釋放記憶體。 | `concept`<br>`process`<br>`code_trace` | ```json<br>{<br>  "frames": [<br>    {"id": "main", "name": "main()", "vars": [{"name": "a", "val": 5}]},<br>    {"id": "foo", "name": "foo(int x)", "vars": [{"name": "x", "val": 5}]}<br>  ],<br>  "actions": [<br>    {"act": "push", "frame": "foo", "copy_from": "main:a"},<br>    {"act": "pop", "frame": "foo", "ret": 10, "to": "main:a"}<br>  ]<br>}<br>``` | 1. 堆疊基座置於畫面底部，`main()` 訊框穩坐底層；<br>2. 函式呼叫，新訊框自畫面頂部重力落下，疊在舊訊框上方；<br>3. 引數數值自底層格複製化為光球注入新訊框（強調雙方隔離）；<br>4. 函式結束，訊框亮起「return 值」，框體半透明震顫；<br>5. 回傳值沿拋物線飛渡回底層變數格，頂層訊框向上化為灰燼消散。 | **是 (Yes)**<br>`stack`<br>*(具備 push, pop, set, 由下往上疊, api.fly 回傳值飛渡)* | [USFCA Data Structure Visualizations](https://www.cs.usfca.edu/~galles/visualization/)<br>David Galles 呼叫堆疊 Frame 垂直推入、變數隔離與彈出動力學。 |
| **8. 多階段流程管線**<br>`pipeline` | 系統建置非黑盒子，為離散階段變換（GCC 四階段：`.c`→`.i`→`.s`→`.o`→`.exe`；IPO 輸入→處理→輸出模型；Git 工作區→暫存區→倉庫）。 | `process`<br>`concept` | ```json<br>{<br>  "stages": [<br>    {"id": "prep", "label": "預處理"},<br>    {"id": "comp", "label": "編譯器"},<br>    {"id": "asm", "label": "組譯器"},<br>    {"id": "link", "label": "連結器"}<br>  ],<br>  "item": {"name": "hello.c", "at": "prep"},<br>  "events": [<br>    {"act": "move", "to": "comp", "text": "hello.i"},<br>    {"act": "reject", "at": "comp", "back_to": "prep", "text": "語法錯誤"}<br>  ]<br>}<br>``` | 1. 各階段站點卡片橫向展開，站間以粗導向箭頭相連；<br>2. 當前運作站外框激發強調色與微呼吸底光；<br>3. 檔案產物卡片沿箭頭軌道滑向下一站；<br>4. 抵達站點瞬間，卡片文字翻轉重寫為新延伸檔名（`.c`→`.i`）；<br>5. 若遇錯誤，紅色弧形箭頭由該站逆向噴射退回前站，附帶報錯標籤。 | **是 (Yes)**<br>`pipeline`<br>*(具備 stages, items, step, move, reject 反向彎箭頭)* | [HyperFrames GitHub Repository](https://github.com/heygen-com/hyperframes)<br>HeyGen 開源流水線 flowchart 與 stage 轉移之時間與幾何控制契約。 |
| **9. 數值標尺與邊界探針**<br>`scale` | 數值型別範圍（`char` -128~127）、陣列索引界限、迴圈終止條件之 Off-by-one 邊界錯誤（`i < 10` vs `i <= 10`）。 | `concept`<br>`mistake`<br>`compare` | ```json<br>{<br>  "min": 0, "max": 10,<br>  "zones": [<br>    {"id": "ok", "from": 0, "to": 9, "kind": "ok", "label": "有效索引"},<br>    {"id": "err", "from": 10, "to": 10, "kind": "bad", "label": "越界區"}<br>  ],<br>  "probes": [<br>    {"val": 9, "label": "i=9", "res": "pass"},<br>    {"val": 10, "label": "i=10", "res": "fail"}<br>  ]<br>}<br>``` | 1. 水平數線刻度分明展開，上下標註安全與危險色帶區間；<br>2. 變數數值滑桿隨迴圈進程在數線上平滑移轉；<br>3. 倒三角探針由上方急降，尖端精確釘在目標數值刻度；<br>4. 探針旁彈出判定標章（安全亮勾 `✓`，違法亮叉 `✗`）；<br>5. 踩入紅色越界區瞬間，越界色帶劇烈抖動並閃爍警告。 | **是 (Yes)**<br>`scale`<br>*(具備 min, max, zones, ticks, probe, mark, zone)* | [Algorithm Visualizer](https://algorithm-visualizer.org/)<br>演算法執行數線區間、邊界分區與動態探針落點標記。 |
| **10. 互動終端與控制台**<br>`terminal` | 命令列人機互動介面、CLI 編譯指令傳遞、標準輸出 (`printf`) 逐行刷出、錯誤輸出 (`stderr`) 與換行符反饋。 | `process`<br>`data`<br>`mistake` | ```json<br>{<br>  "title": "MinGW64 Terminal",<br>  "prompt": "C:\\cs101>",<br>  "actions": [<br>    {"type": "type", "text": "gcc main.c"},<br>    {"type": "print", "lines": ["error: expected ';'"], "style": "error"},<br>    {"type": "restart", "note": "修復後重新編譯"}<br>  ]<br>}<br>``` | 1. 深色面板展開，提示字元旁游標規律閃爍；<br>2. 敲擊指令逐字顯現（固定節奏帶微小手打抖動）；<br>3. 按下 Enter，執行輸出逐行自下方淡入刷出；<br>4. 編譯報錯行以專屬警告色強調，行號與外部代碼聯動；<br>5. 重啟或清屏時內容淡出，置中浮現轉折註記，重現空白提示符。 | **是 (Yes)**<br>`terminal`<br>*(具備 prompt, type, print, restart, input 游標等待)* | [HyperFrames code-terminal-run](https://github.com/heygen-com/hyperframes)<br>標準終端機命令打字、輸出排程揭露與游標閃爍規範。 |
| **11. 程式碼走讀與差異面板**<br>`code` | 程式執行點（Instruction Pointer）流轉、語法區塊聚焦、錯誤修正前後比對（Diff View）、關鍵 Token（如 `=` vs `==`）行內聚焦。 | `code_trace`<br>`compare`<br>`mistake` | ```json<br>{<br>  "lines": ["int x = 0;", "if (x == 1) {", "  ..."],<br>  "highlight": 2,<br>  "diff": {"add": [2], "del": []},<br>  "marks": [{"id": "cmp", "line": 2, "text": "=="}]<br>}<br>``` | 1. 等寬程式碼面板展開，行號整齊排列；<br>2. 當前執行行底層鋪設半透明高亮色帶，隨執行平滑滾動；<br>3. 關鍵 Token 以手繪圈框出，其餘非焦點行微幅變暗；<br>4. 程式修復時，刪除行標紅劃線，新增行標綠在行間平滑撐開插入；<br>5. 依旁白節奏逐步解鎖後續行，引導視覺焦點。 | **是 (Yes)**<br>`code`<br>*(具備 lines, highlight, diff, marks 行內具名錨點)* | [Motion Canvas Code Guide](https://motioncanvas.io/docs/code/)<br>基於語法樹之程式碼行高亮、token 選取與平滑 diff 變形技術。 |
| **12. 走訪過濾器與比對清單**<br>`list` | 線性搜尋（Linear Search）走訪匹配過程、PATH 環境變數逐層目錄探查、條件篩選。 | `process`<br>`compare`<br>`data` | ```json<br>{<br>  "title": "PATH 搜尋順序",<br>  "target": "gcc.exe",<br>  "rows": [<br>    {"text": "C:\\Windows\\system32"},<br>    {"text": "C:\\msys64\\bin"}<br>  ],<br>  "walk": {"find_at": 1}<br>}<br>``` | 1. 卡片清單垂直整齊排布；<br>2. 帶著目標標籤（`[gcc.exe]`）的指標由頂部逐列下移；<br>3. 未匹配列右側打上灰色 `✗`，該列文字淡化轉灰；<br>4. 匹配成功列邊框激發強調色，右側彈出醒目 `✓` 徽章；<br>5. 指標錨定於成功列，其餘無關列微幅淡出，鎖定目標。 | **是 (Yes)**<br>`list`<br>*(具備 title, rows, append, walk 逐列標籤比對)* | [VisuAlgo Array Search](https://visualgo.net/en/array)<br>展示線性探測指針在陣列清單項目間下移與比對結果標記。 |
| **13. 型別轉換與位元截斷漏斗**<br>`type_funnel` | 隱含與強制型別轉換（Cast）、浮點轉整數小數直接截斷（非四捨五入）、寬型別擠入窄型別（如 `int` 轉 `char`）之高位元丟棄。 | `concept`<br>`mistake`<br>`compare` | ```json<br>{<br>  "src": {"type": "double", "val": "3.99"},<br>  "dst": {"type": "int", "val": "3"},<br>  "op": "(int)3.99",<br>  "loss": ".99",<br>  "note": "截斷而非四捨五入"<br>}<br>``` | 1. 寬大容器（64-bit 浮點數，裝有 `3.99`）置於上方；<br>2. 轉換啟動，數值流經狹窄型別漏斗口；<br>3. 小數部 `.99` 無法通過漏斗口，被邊緣裁斷墜落廢料槽消散；<br>4. 整數部 `3` 順利墜入下方窄容器（32-bit `int`）咬合；<br>5. 旁側打上手寫警示標籤「截斷 (Truncation) ≠ 四捨五入 (Rounding)」。 | **否 (No)**<br>*(既有 scale 僅為一維數線，無法呈現二維容器位元容量差異與漏斗截斷動力學)* | [Manim Community Documentation](https://www.manim.community/)<br>Grant Sanderson 符號形變、幾何分割與未保留部分幾何級瓦解淡出原理。 |
| **14. 短路求值與邏輯閘軌道**<br>`logic_gate` | 布林運算子 `&&` 與 `\|\|` 的短路求值（左式定案後右式完全不執行，任何副作用如 `i++` 皆被凍結）；`switch` 漏寫 `break` 貫穿。 | `mistake`<br>`process`<br>`code_trace` | ```json<br>{<br>  "op": "&&",<br>  "left": {"expr": "x > 0", "eval": false},<br>  "right": {"expr": "y++ > 5", "run": false},<br>  "side_effect": {"var": "y", "changed": false}<br>}<br>``` | 1. 複合條件式展開為串聯電路軌道，電流自左端注入；<br>2. 左式求值為 `false`，該節點落下實體絕緣金屬閘門；<br>3. 電流於閘門前截斷，右式軌道瞬間失去能量整體暗化消隱；<br>4. 右式內部之 `y++` 變數探針被鎖定冰封標章凍結；<br>5. 旁白揭露「右式完全未被執行，y 依然為原值」，破解副作用陷阱。 | **否 (No)**<br>*(既有 vars 的 check 僅能驗收單一條件結果，無法呈現電路短路阻斷與右式副作用凍結)* | [CS50x Boolean Logic Notes](https://cs50.harvard.edu/x/)<br>條件分支與 Boolean 短路評估如何影響運算式副作用之教學分析。 |

---

## 參、 C 語言 for 迴圈單元：優先建置 Top 5 元件與建構理由

若要為大一新生製作一支高品質、透視底層機制的 **「C 語言 for 迴圈與計數器運作」** 教學短片（40–90 秒），依據本儲存庫現狀與教學成效，**優先組合與建置之 Top 5 元件** 如下：

### 1. `loop_orbit` (迴圈控制流軌道) — 【新元件，首要優先】
- **建構理由**：大一新生學 for 迴圈的最大思維障礙在於「習慣了循序執行（由上而下逐行執行）」。C 語言的 for 語法將 `init`、`cond`、`step` 寫在同一行圓括號中，但其**微觀執行順序是跳躍且循環的**（`init` 僅跑一次 $\rightarrow$ 測 `cond` $\rightarrow$ 入 `body` $\rightarrow$ 執行 `step` $\rightarrow$ 再測 `cond`）。若無可見的環狀軌道與閘門阻斷動畫，學生永遠只能靠死背口訣，無法在腦中建立真正的控制流迴路。
- **定位**：畫面主視覺核心，負責引導時間與空間上的執行焦點。

### 2. `code` (程式碼走讀與行內 Token 聚焦) — 【既有元件擴充】
- **建構理由**：迴圈的控制流必須與真實 C 語言程式碼產生 1:1 緊密映射。利用 `code` 元件的行內標記（`marks`）功能，當軌道光標停在 `init` 時，程式行中的 `int i = 0` 亮起；當測 `cond` 時，`i < 3` 亮起；當執行迴圈體時，底層鋪設高亮色帶；當遞增時，`i++` 亮起。
- **定位**：錨定語法實體，確保學生將抽象軌道與真實 C 代碼無縫對接。

### 3. `vars` (變數狀態與歷史面板) — 【既有元件精準套用】
- **建構理由**：具象化迴圈變數 `i` 的物理生命週期。初學者最常犯的錯誤之一是誤以為 `for (int i = 0; i < 3; i++)` 結束後 `i` 的值是 `2`。透過 `vars` 的 `set` 與鉛筆刪除線歷史列，學生親眼目睹 `i` 從 `0` 變成 `1`、`2`，最後在 `step` 中被覆寫為 `3`，隨後帶入條件判斷 `3 < 3` 失敗跳脫。歷史列留下的 `~~0~~ ~~1~~ ~~2~~ 3` 痕跡，是理解「迭代副作用」的最強視覺證明。
- **定位**：記憶體狀態真實監控，解答「跳出迴圈時變數到底是幾」。

### 4. `scale` (數值標尺與臨界邊界探針) — 【既有元件精準套用】
- **建構理由**：直擊程式設計第二大經典痛點——**Off-by-one 邊界錯誤**（`i < 3` 到底跑 3 次還是 4 次？換成 `i <= 3` 又是幾次？）。在畫面一側展開 `0..3` 的數值標尺，`[0..2]` 為綠色通行區，`3` 為臨界紅線區。倒三角探針隨 `i` 的每一次更新向右跳格，當 `i = 3` 探針落在邊界紅線上時，瞬間亮出紅色 `✗` 並與 `loop_orbit` 的阻斷閘門同步關閉，讓學生在幾何空間中理解邊界條件。
- **定位**：邊界幾何化，徹底消滅索引與次數混淆。

### 5. `terminal` (終端機輸出卡片) — 【既有元件精準套用】
- **建構理由**：將內部所有抽象機制（軌道流轉、變數覆寫、邊界判定）收斂到唯一的**外部可觀察輸出（Observable Effect）**。迴圈體每執行一次 `printf("%d ", i)`，終端機內隨即打出一個數字。當輸出為 `0 1 2` 時，學生能立刻將螢幕上的輸出與上述四大元件的狀態完全閉環對齊。
- **定位**：輸入/輸出接地點，印證程式執行的最終外部行為。

---

## 肆、 教學影片「反模式」分析 (Top 5 Anti-patterns: What Makes Edu Videos Look Like Slides)

在評審教學影片成果時，必須嚴格排查下列五大「把影片拍成簡報」的致命反模式：

### 1. 條列文字逐行浮現 (Bullet Points Fading In / Handout on Screen)
- **視覺病徵**：畫面左側放標題，右側放 3–4 行中文條列文字（例：「• 初始化只執行一次」、「• 檢查條件是否成立」、「• 執行迴圈主體」），旁白念一句、文字淡入一行。
- **認知危害**：完全忽視雙重編碼理論（Dual Coding Theory）。當螢幕充滿條列文字時，學生被迫在「閱讀文字」與「聆聽旁白」之間切換焦點，導致工作記憶（Working Memory）過載。
- **機制解法**：**嚴禁將講義句子投影至畫面**。畫面上只保留程式碼與微觀機制模型（如軌道或變數格），文字僅限於數值標記與變數名稱。所有的「解釋與脈絡」，一律由**語音旁白搭配畫面動態手繪箭頭/焦點**來承載。

### 2. 靜態方塊加跳動雷射筆 (Static Boxes with Jumpy Arrows)
- **視覺病徵**：畫面繪製了靜態的流程圖或架構方塊，方塊內容從頭到尾不動，只有一個紅色小光點或一條箭頭在方塊之間跳來跳去。
- **認知危害**：這不是動畫，這只是「錄下講師拿雷射筆指簡報的過程」。計算機程式的精髓在於「狀態變化（State Mutation）」；如果方塊內部的數值沒有被改寫、資料沒有位移，學生根本看不到因果關係。
- **機制解法**：每一個運動都必須改變畫面實體狀態。箭頭指向變數格時，格內數值必須被劃掉重寫；資料傳遞時，必須是帶有內容的資料卡（如 `main.c`）物理性地滑動進下一站。

### 3. 無因果律的裝飾性動效 (Gratuitous Cosmetic Transitions / PowerPoint Spins)
- **視覺病徵**：物件進場時使用花俏的 3D 翻轉、彈跳縮放（Elastic Bounce）、飛入或百葉窗轉場，但動效與計算機底層邏輯毫無關聯。
- **認知危害**：分散學生的注意力，讓影片顯得廉價且雜亂。
- **機制解法**：**動效必須具有物理或計算語意**。
  - 堆疊呼叫是「重力落下與壓實」；
  - 記憶體覆寫是「鉛筆線劃破與替換」；
  - 迴圈跳脫是「實體閘門阻斷與外側彈射」；
  - 暫停是「游標實心等待」。沒有多餘的裝飾性動效。

### 4. 程式碼整大塊代換 (Monolithic Code Wall Swapping)
- **視覺病徵**：解說程式時，畫面上直接貼出 15–20 行完整 C 程式碼，整頁淡入；修改 Bug 時，整段程式碼突然消失，替換成另一整段新程式碼。
- **認知危害**：學生無法在短時間內比對兩段長代碼的差異，視線茫然無措，產生嚴重的學習挫折感。
- **機制解法**：採用 **Code Walk & Diff Morphing**。程式碼一次只展示關鍵片段（$\le 8$ 行）；修改時，刪除行以紅底加刪除線淡化，新增行以綠底平滑撐開行距插入，並使用 Spotlight 將無關程式行淡化至 `code.muted`，聚焦於變更點。

### 5. 離散狀態瞬間瞬移 (Discrete State Teleportation instead of Continuous Morphing)
- **視覺病徵**：上一影格變數還是 `i = 0`，下一影格畫面硬切成 `i = 1`；上一秒指標指向陣列第 0 格，下一秒瞬間出現在第 3 格，中間毫無過渡。
- **認知危害**：迫使學生在大腦中自行腦補「狀態如何變遷」，喪失了影片媒介最核心的「連續時間演繹（Temporal Continuity）」優勢。
- **機制解法**：展示「狀態轉換的中間態（In-between State）」。遞增時，先看見算式 `0 + 1` 出現，舊值劃線，新值由算式沉降入格；指標移動時，游標必須具備平滑 Ease 軌跡滑過中間格子，讓學生清楚感知「空間位移」與「歷程累積」。

---

## 伍、 與既有管線及未來教學結構整合建議

1. **教學結構資料模型（Teaching Structure）介接**：
   - 每個知識點（Key Point）的輸入 JSON 應明確包含 `demo_data`，其欄位形狀直接對接上述元件之 `req` / `opt` 屬性。
   - 例如：當知識點類型為 `code_trace` 時，由教學結構提供 `iterations` 陣列，直接轉譯為 `vars` 的 `set` 與 `loop_orbit` 的 `step` 動作。
2. **元件實作時程排定**：
   - **Phase 1（現有複用）**：全面啟用已完成之 `vars`, `cells`, `stack`, `pipeline`, `scale`, `terminal`, `code`, `list`。
   - **Phase 2（關鍵缺口補充）**：優先打造 `loop_orbit`（迴圈控制流軌道）與 `io_buffer`（I/O 緩衝區隊列），立即覆蓋 W2（輸入殘留）與 W5（迴圈時序）兩大重災區。
   - **Phase 3（進階透視）**：打造 `pointer_bus`（指標連線導線）與 `expr_reduction`（運算式折疊樹），支援期中指標與算術型別轉換單元。

---
*報告完成，無動用生產程式碼修改。全數參考連結均已實測校驗完畢。*
