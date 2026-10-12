# 專案進度交接與架構說明書 (Project Handoff Notes)

> 本文件記錄至 2026-10-11，整理當前專案現況、核心願景、已完成技術資產、溝通差距檢討與後續交接要點，方便接手者（如 GPT）無縫繼續推進。

## 2026-10-12 AI 對話範圍更正

使用者試用後指出：AI 對話應從教材或學習問題開始，釐清要理解的內容，再選擇影片、簡報或心智圖；選定形式後展示內容確實對應的既有成品，沒有合適成品才進入新教材製作。影片內容提問、重播與定位只是一個分支。初始固定展示48秒樣片不應成為AI對話主入口。

目前僅完成下述影片互動分支，完整的教材對話入口、形式選擇、跨形式成品重用及生成流程尚未串接。不得把影片聊天計畫完成解讀為整個AI對話功能完成。

## 2026-10-12 影片互動分支的實作

`workbench/web/js/pages/chat.mjs` 已取代2026-10-11的固定內容與定時器原型。現在初始播放 `coherent/out/coherent.mp4` 48秒既有成片，提供觀念、流程、回到條件18.3秒、操作次數與重播；六支15秒元件樣片收在「其他課題」區並標明不同教材。一般問題使用選定單元呼叫正式 `/api/v1/ask`，只重用素材庫既有成品；換風格只記錄補強需求，沒有宣稱或觸發AI新影片生成。

伺服器新增安全 `/trials/` 映射，固定在 `prototypes/component_trials_20261011`，沿用HEAD、Range與HTTP 206，阻擋 `..` 與symlink逃逸。聊天頁以DOM API建立，沒有使用者文字`innerHTML`、window全域方法或假進度計時器；換教材及離頁會停止舊影片，晚回應不會覆蓋新狀態。

2026-10-12驗證：Node 108項、Python伺服器31項通過。Playwright以1440×900、768×900、375×812實測真實MP4、18.3秒定位、ended單次追問、正式`/ask`、切元件、換教材、離頁與返回；無橫向溢出、console error或`/generate`請求。新AI補強片生成、版本庫與派工尚未接入。

## 2026-10-11 提交時的狀態更正

下文的對話頁「自動命中／拆解／生成」描述是前端模擬：chat.mjs 使用固定內容與定時器，沒有真正發出教材分析、TTS 或影片生成請求；儲存／匯出也尚未接通。正式素材庫的 server.ask 與 library.showAnswer 才有實際單元匹配及既有影片播放。

新增六支15秒真實動畫＋字幕候選，位於 prototypes/component_trials_20261011/；另有 coherent/ 的48秒同題材共同主視覺樣片。revision 2 修正數值文字重疊、流程標籤／箭頭末端提早出現及公式轉場相交；1152幀碰撞／時序、seek、字形與成片解碼驗證通過。來源與授權、重製指令和報告在各目錄 README.md／VERIFIED.md。

風格與對話需求記錄在 docs/TEACHING_VISUAL_CUSTOMIZATION.md：預設暖色手帳，同片一致、跨片多元；先顯示對應既有影片，看完追問理解情況，再重播、找其他既有版本或補做指定重點。使用者已要求整合到工作台，並簡化為大字、少圖示、少小字；本次先保存現有狀態，該整合尚未完成。

本次只建立本機提交，未推送遠端。Python 回歸共780項，其中1 skip；前端104項與示範模型5項。不得把這些測試通過解讀為聊天AI或正式元件自動選用已完成。

---

## 一、專案核心願景與使用者的產品定位

1. **產品核心**：
   - 一套以 **AI 對話驅動的多格式教學教材製作工作台**（Chat-driven Studio）。
   - 輸入一份教學教材，AI 自動進行重點分類與分析，使用者挑選/勾選重點後，能一鍵產出：
     - **動態教學影片 (MP4)**
     - **可編輯簡報 (PPTX)**
     - **概念心智圖 (SVG/Interactive)**
     - **素材庫問答檢索（免重複生成）**

2. **核心理念（別人從 1，我們到 100）**：
   - **絕不從零發明輪子**：充分吸納現有優秀開源專案（花叔 `huashu-art-motion` 與 嵐叔 `lanshu-create-ai-presenter-video`）所沉澱的多元視覺語言與元件模板庫。
   - **我們做到 100**：**所有的元件在呈現在畫面上之後，都必須能被使用者自由修改**！
     - 包括文字內容、排版位置、數值大小、色階主題、動畫節奏。
     - 元件不僅是展示，而是「模板 (Template) $\to$ 可視化修改 (Inspector) $\to$ 即時動態渲染 (Live Dynamic Render) $\to$ 儲存與匯出」。
   - **多元視覺工具箱**：教學影片絕不能千篇一律只用單一手帳鋼筆，需依據教學場景自動或手動配對最適元件：
     - 系統模組 / Web API 架構 $\to$ **現代 Keynote UI（毛玻璃、發光流向）**
     - 演算法時間複雜度評測 $\to$ **效能數據圖表（動態長條圖、數字翻滾）**
     - 指標與記憶體位址推導 $\to$ **課堂黑板粉筆（磨砂黑板、粉筆筆跡圈選）**
     - 系統記憶體 Stack vs Heap $\to$ **工程藍圖圖紙（CAD 等角引線、對向生長）**
     - 章節破題提問與金句 $\to$ **柔和動態文字（重力過衝回彈、刷筆高亮）**
     - 演算法走讀與變數追蹤 $\to$ **手帳鋼筆筆記（方格紙、墨水即時書寫）**

---

## 二、現有系統架構與檔案資產

### 1. 本地常駐伺服器
- **工作台伺服器 (Port: 8765)**：
  - 啟動指令：`.venv/bin/python -m workbench.server --port 8765`
  - 入口網址：`http://127.0.0.1:8765/#/chat`
  - 核心程式碼：[`workbench/server.py`](workbench/server.py)
  - 已打通 `/out/` 與 `/candidate/` 靜態路由，支援 HTTP 206 影片 Range 串流。
- **候選預覽伺服器 (Port: 8931)**：
  - 啟動指令：`.venv/bin/python -m http.server 8931 --directory prototypes/three_output_quality/video`
  - 入口網址：`http://127.0.0.1:8931/lanshu_notebook.html`

### 2. 前端工作台核心檔案
- **對話式製作頁面**：[`workbench/web/js/pages/chat.mjs`](workbench/web/js/pages/chat.mjs)
  - **左側對話流**：
    - 現代感輸入卡片：圓角卡片設計、內嵌圓形圖標發送鈕、Auto-grow 高度自適應、`Enter` 發送與 `Shift+Enter` 換行、留足底部安全邊距。
    - 素材庫自動命中：提問邊界條件 $\to$ 直接命中現有成品影片 $\to$ 右欄直接展開播放（免重製）。
    - 5 大重點拆解：貼上教材 $\to$ 自動拆解重點清單供勾選 $\to$ 原地動態進度條（腳本規劃 $\to$ Gemini TTS 配音 $\to$ 合成動畫）。
  - **右側多功能畫布**：
    - Tabs 切換：影片播放器、簡報 PPT 檢視、概念心智圖、**風格元件全集 (Showcase & Inspector)**。
- **全域樣式表**：[`workbench/web/styles.css`](workbench/web/styles.css)
  - 含滿版自適應佈局（`body.page-chat-active .main-viewport { padding: 0 !important; }`），解決了視窗底部被截斷的歷史問題。
  - 含現代發送卡片樣式、Live Stage 動態舞台樣式、Inspector 檢查器樣式、各元件 CSS 動態特效。

### 3. 各視覺元件與動態成果
- **嵐叔手帳 (v3-notebook)**：
  - 實體 1080p MP4：[`prototypes/three_output_quality/video/out/C-lanshu_notebook.mp4`](prototypes/three_output_quality/video/out/C-lanshu_notebook.mp4)
  - 獨立 HTML 預覽：[`prototypes/three_output_quality/video/lanshu_notebook.html`](prototypes/three_output_quality/video/lanshu_notebook.html)（已附帶視窗自適應縮放、懸浮毛玻璃播放控制列、自動播放）。
  - 匯出壓片腳本：[`prototypes/three_output_quality/video/export_lanshu.py`](prototypes/three_output_quality/video/export_lanshu.py)
- **Keynote UI / 數據圖表 / 黑板粉筆 / 工程藍圖 / 動態文字**：
  - 目前在 `chat.mjs` 中已實作高影格率動態舞台（Live Stage），點擊各卡片即可即時觀看動態效果。
  - 下方已具備客製化檢查器（Inspector），使用者修改文字或數值後點擊「套用修改並重播」，畫布立即重新演出更新後的動態。

### 4. 測試狀態
- **Python 測試**：`780 passed`（`python -m unittest discover tests`）。
- **前端測試**：`104 passed, 0 failed`（`node --test workbench/web/tests/*.test.mjs`）。

---

## 三、溝通差距與問題檢討

1. **先前的溝通不到位點**：
   - **過度聚焦單一風格**：在先前的對話中，花費了過多心力在微調手帳風格的筆記與白板符號間距，而沒有及時意識到使用者的整體戰略是「建立多元工具箱，以利後續套用到各種教材，不要只做手帳」。
   - **未及時給出真正的動態與可視化編輯器**：一開始在展示其他風格時，僅提供靜態 mock 卡片，而忽略了使用者要看的是「真實動態渲染效果」，且所有的元件「呈現後必須能夠讓使用者修改文字與位置」。
   - **UI 敏銳度不足**：第一次設計的發送框採用了原生粗糙的表單 input，且高度計算溢出導致底部被截斷，缺乏現代 AI 應用的設計質感。
2. **已建立的硬性規範**：
   - 記錄在 [`~/.gemini/GEMINI.md`](/home/pjw92/.gemini/GEMINI.md) 與 [`~/.agents/skills/my-dev-rules/SKILL.md`](/home/pjw92/.agents/skills/my-dev-rules/SKILL.md)：
     - **交付前必驗證（硬性紅線）**：任何功能、UI 調整或 Bug 修復，交付給使用者前必須先自行端到端驗證（跑測試、Playwright 截圖確認視覺效果與操作正常），嚴禁未經驗證直接交差。
     - **禁止自行 Push / Merge**：所有改動只停留在本地分支，需由使用者指示。

---

## 四、交接給後續接手者（如 GPT）的推進建議

1. **元件庫資料驅動化 (Component Schema)**：
   - 將目前寫在 `chat.mjs` 裡的 5 大元件資料（`COMPONENT_DATA`）標準化，抽離成獨立的 JSON Schema，例如：
     ```json
     {
       "id": "keynote-ui",
       "name": "現代 Keynote 卡片",
       "props": {
         "nodes": [
           {"label": "Client 請求端", "highlight": false},
           {"label": "API Gateway", "highlight": true},
           {"label": "Database", "highlight": false}
         ],
         "flow": "horizontal"
       }
     }
     ```
2. **打通後端教材規劃派工 (Teaching Plan Pipeline)**：
   - 當前工作台已有 `teaching_plan.json` 的規劃器（位於 `video_engine/author.py` 或 `workbench/jobs.py`）。
   - 下一步應讓 AI 分析教材後，能自動向這 5 大元件分配對應型態（例如系統架構自動選 Keynote，複雜度評測自動選數據圖表），並將分析出來的文字自動帶入元件的 props 供使用者確認與微調。
3. **客製化成果的獨立出片與匯出**：
   - 使用者在 Inspector 修改完畢後，除了在前端畫布重播，可進一步支援「匯出 MP4 影片」與「匯出可編輯 PPTX」，讓使用者完成從 1 到 100 的全鏈路創作。
