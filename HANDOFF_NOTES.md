# 專案進度交接與架構說明書 (Project Handoff Notes)

> 本文件記錄至 2026-10-14。以下日期段落優先於後方歷史架構描述。

## 2026-10-14 重點清單第一期實跑

使用者同意後，以真實 Markdown 教材實跑（使用者決定不用 PDF）：for 迴圈、變數與資料型別、應用：感測資料統計，加上既有 q4 單元（AI 協作與單位換算）。共 5 次 gemini-3.8-flash，$0.11，無重試。證據在 `docs/experiments/2026-10-13-key-points-trial/`（檔名用中文教材名）。

- 修正：學習目標標題帶章節編號（`### 1. 學習目標`）被判成推論，改為允許編號；13 份教材判為 material 由 8 份變 10 份。快取鍵不含判定規則，修正後以 `request_reextract` 重抽變數那份。
- 修正：任務 8 新增 `key-points-review.json` 假資料卻沒登記到形狀表，Python 全套 1 項失敗；補上 `key_points` 形狀。
- 感測資料統計、多分支決策、比較運算三份教材本身沒有學習目標，走推論＋待確認，屬預期。
- q4 舊版共同教學規劃匯出 PPTX 失敗（`DeckError: 簡報文字過長`），舊路線問題，未修。
- 使用者判斷：重點對照表「還 OK」；講義 PPT 全是文字是嚴重問題（要接元件，但仍是 PPT）；影片不是 PPT 加旁白；心智圖要點一下長一層、內容長在樹上不用側欄。
- 後續分成 A1 概念樹逐層展開（規格 `docs/superpowers/specs/2026-10-14-concept-tree-progressive-design.md`，進行中）、A2 延伸分支、B 講義元件、C 影片。

## 2026-10-13 q4 重複旁白修正

使用者指出重複念；核對原稿每句只有一次，但第2／8／9／12分句WAV已念兩遍，原ASR只檢漏字、忽略多出的音節。新增六音節以上片語的超額重複檢查與ASR版本2，舊快取重驗，重配最多三輪，超限保留tts_repeat及逐句重配提示。內部配音服務重複的原因未由音檔證明，不把prompt改寫當作永久保證。

第2／8／9句重配通過，最後句三輪仍重複，改用同義且更精確的說法後單獨重配通過；其餘八句音檔摘要完全沿用。正式q4最新62.33秒1080p有聲片，12句ASR均通過、無重複problem；時間軸0警告／0缺口，1496幀。Chrome桌機／手機播放、46秒定位、Range與完整解碼通過。三句原有可能漏唸提示保留，沒有宣稱所有語音辨識誤差已解決。

Python799項（1skip）、Node102項；本輪已知費用US$0.019917，單元已知小計US$0.163030與4筆未知費用分列。原片及中間版本保存在out/recovery/4f2ef7bf2785，避免備份的usage ledger重複計費顯示。詳細證據docs/experiments/2026-10-13-q4-repeated-narration.md；後方84秒成品屬修復前歷史紀錄。

## 2026-10-12 引文與教學表達分離、q4 實際出片

使用者明確要求引文僅供參考，教學表達可以自然改寫，但意思、數字與推論要正確。共同規劃改用原文片段 ID，由程式恢復後台證據；旁白／圖解不必逐字符合教材。失敗候選現在另存診斷；保留原來源與契約檢查。修正共同規劃被 PPTX 長程式碼排版阻擋、未知費用 null 使 Board 預算加總崩潰兩個整合問題。簡報匯出仍保留容量檢查，本教材的長程式碼排版尚待改善。

正式單元4f2ef7bf2785／q4已實際完成，工作dce5d8ddad684c579848089acb06a6e6；84秒1080p有聲影片，2013幀，配音後時間軸0缺口／0警告。Chrome桌機／手機實測播放、46秒定位及HTTP206通過，無page error、無額外生成。第7／8／11句仍有ASR可能漏唸提示，保留逐句重配；人工試聽品質未代替使用者驗收。只製作q4，其他形式未代生成。

最新Python795項（1 skip）、Node101項通過。已知單元費用小計US$0.143113，另4筆未知費用保留，不當作帳單總額。完整原因與證據見docs/experiments/2026-10-12-q4-reference-retry.md。下方「未代按重試／影片仍失敗」屬先前紀錄，已由本段結果取代。

## 2026-10-12 使用者影片生成失敗與製作頁修正

單元 `4f2ef7bf2785` 的 q4、工作 `88262522b82c44ab8d1cb1fda3cb119c` 停在共同教學規劃，未配音／出片。紀錄為「簡報欄位不符合契約」；實際回應未保存，無法判定究竟哪個欄位缺失或多出。已重現並修正 `video_engine.llm._google` 接收 schema 卻未送給 Gemini 的缺口，現在使用 SDK 的 response_json_schema；不移除契約、引用、容量或預算驗證。mock SDK 回歸先失敗後通過；沒有代按付費重試，不能宣稱該影片已成功。

製作頁狀態／原因／佇列移至流程圖前，內容14px、標題15px、按鈕13px，清單有界捲動、流程圖220px；有工作時預設收合清單，失敗時只預選失敗項目，仍可展開增選。修正全域 status-failed 背景與佇列文字同色造成看不到名稱。Chrome1440×660、1280×720、768×900、375×812實際失敗頁驗證：佇列第一屏可見、展開收合／清單選擇／查看失敗步驟正常、無橫向溢出或page error、無POST生成。最新全套Python790項（1 skip）、Node101項通過。

## 2026-10-12 簡報流程元件與心智圖層次

使用者自行試生影片；8876 正式素材庫服務已載入既有設定啟動，生成／配音模型只讀metadata可存取，Board免費自檢37份通過。真正製片入口是 `/web/index.html#/make/1`，不是對話樣片頁；本輪未代按付費生成。服務可用 `.venv/bin/python -m workbench.server --port 8876` 啟動；模型轉接層 load_env() 會自行讀取專案 .env，既有環境變數優先。本輪啟動另行載入.env，不代表程式不會自行讀取。

共同教學規劃新增1.1：心智圖分類名稱concept_label與簡報標題分開，parent_id/relation/relation_quote保留教材支持的父子層次；阻擋缺父、循環、自連及無法定位的引用，仍相容舊1.0。簡報Deck1.2新增pipeline，與Board沿用stages{id,label,note}資料，線上逐步高亮與可編輯PPTX階段頁接入professional runner。六支外部風格候選仍未全部接入正式生成。

線上簡報／心智圖縮小正文到16px、內距與工具列；心智圖卡片270px上限，展開保留父概念視角，根及兄弟坐標不動。固定C教材人工基準、實際PPTX／SVG與重製指令在 `docs/experiments/shared-components-20261012/`；隔離预览8877，沒有改使用者素材或重啟8876。

驗證：Python788項（1 skip）、Node100項；Chrome1440/375px流程／心智圖／下載／鍵盤通過；LibreOffice實轉16頁PDF，PPTX301原生物件、文字框不相交，514詞實際文字邊界在頁內。真實模型教學品質及整體設計尚待驗收，完整多元教材對話仍未完成。

## 2026-10-12 AI 對話範圍更正

使用者試用後指出：AI 對話應從教材或學習問題開始，釐清要理解的內容，再選擇影片、簡報或心智圖；選定形式後展示內容確實對應的既有成品，沒有合適成品才進入新教材製作。影片內容提問、重播與定位只是一個分支。初始固定展示48秒樣片不應成為AI對話主入口。

目前僅完成下述影片互動分支，完整的教材對話入口、形式選擇、跨形式成品重用及生成流程尚未串接。不得把影片聊天計畫完成解讀為整個AI對話功能完成。

## 2026-10-12 影片互動分支的實作

使用者再次試用要求縮小整體元件。目前對話頁改為緊湊版：頂部只留「AI對話」及教材選單，內文14px、區塊標題15px、按鈕13px；縮小導覽、卡片內距及輸入區，移除大型送出按鈕與厚重卡片陰影。桌面1440×900、1440×660（收合導覽）、1280×720、平板768×900及手機375×812已做瀏覽器尺寸／捲動驗證；桌面輸入區完整可見，其他頁導覽尺寸保持原狀。

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
