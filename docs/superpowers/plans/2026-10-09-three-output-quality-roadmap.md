# 影片、簡報、心智圖品質與自動化計畫

> **For agentic workers:** 分批使用 `executing-plans` 執行；每批先讀目標程式與既有測試，再完成下列驗收。不得自行 commit、push 或呼叫付費生成。

**Goal:** 讓學生能用既有三種教材形式理解同一份教材；AI 依內容選擇圖解與編排，產物可讀、自然、可追溯，修改時只重製受影響部分。

**Architecture:** 延續 `workbench/`、共同 `material.json`、Board runtime、原生 PPTX 與 SVG。先補小型教學規劃資料與元件能力目錄，再逐一適配三種 renderer；內容、幾何、時間仍分層，模型不寫像素座標或實測時間。

**Tech Stack:** 既有 Python、原生 JS、Pillow、python-pptx、Canvas/SVG、Chromium、FFmpeg；內容模型與語音沿現有配置。外部程式採固定版本的小範圍適配，先查既有環境，不直接引入完整新引擎。

日期：2026-10-09。這是進度盤點與下一階段方案，並非已完成的功能或視覺驗收。本輪範圍以本文件為準；Podcast、海報、漫畫與平台串接暫緩，舊八步計畫保留作歷史。

## 1. 實際進度

| 原計畫 | 目前判定 | 證據與尚缺項目 |
| --- | --- | --- |
| 第一步：穩定新版工作台 | 技術驗收已記錄完成 | 佇列、進度、素材保存、預覽、下載、用量與重啟檢查已有紀錄；不能延伸成所有瀏覽器與真實生成品質都已驗收 |
| 第二步：多格式與共同教材資料 | 技術驗收已記錄完成 | MD/TXT/PDF/PPTX/DOCX/XLSX/CSV/圖片解析與來源保存；視覺辨識、公式與圖表各有限制，不宣稱所有檔案完整理解 |
| 第三步：三產物接共同資料 | 接入與審查修正已完成 | runner 讀取核對版本、模型前拒絕不一致資料、成品保存來源版本；來源存在不等於每項主張已被支持 |
| 第四步：簡報與心智圖品質 | **進行中、未通過使用者品質驗收** | PPT 字級／容量與心智圖操作已有修正；C 迴圈展示含人工編排，尚非模型全自動產出 |
| 第五步：影片升級 | **有既有基礎，外部適配與品質驗收未完成** | 已有 Board 影片、逐句語音快取、實測時間軸與 compose 串接；不能把既有重點片串接視為外部風格、多章節續跑與完整音畫驗收已完成 |
| 第六、七步：新產物 | 本輪暫緩 | 聚焦現有三種形式 |
| 第八步：部署 | 三產物流程穩定後收尾 | 只驗收本輪三產物所需環境，不以前五類產物全部完成作前置 |

來源：`2026-10-08-independent-material-workbench.md`、`2026-10-08-common-material-ingestion.md`、`2026-10-08-common-material-consumers.md`、`2026-10-08-ppt-mindmap-quality.md`，以及實際 runner／renderer。

本輪讀取基準 commit：`f45e51a`。README／NEXT_STEPS 主要敘述仍停在較早期 Studio；本輪判斷以新版工作台、近期計畫與程式為主。前述「已完成」為既有技術紀錄，視覺與語意驗收另列。

## 2. 為何現在容易像同一套 AI 模板

- Board 已有 13 種元件：`note/cells/output/code/metrics/terminal/list/window/cursor/vars/stack/pipeline/scale`，目錄在 `video_engine/board/catalog.json`。問題包含選擇與編排，並非完全缺乏元件。
- Deck 1.1 只有 `bullets/code/compare/steps/concept`，每頁單一主 block；`studio/deck_builder.py`、`deck_contracts.py` 尚未提供多元件教學場景與逐步揭示契約。
- Mindmap 1.0 是單父節點樹，每個概念只有 `explanation`；viewer 目前把它加成意思分支，尚無由 AI 生成「意思、用法、例子、常見錯誤」的完整契約。
- 三個產生器分別規劃內容。共同教材版本已有，但共同教學順序、具體例子與圖解用途尚未統一。
- 現有引文定位與結構驗證無法自動保證所有敘述、例子與推導正確；只加元件或換色不能解決內容空泛。

## 3. 兩個 GitHub 專案的採用方式

本輪重新閱讀官方 README、片段 runtime、KITS 與核心交付程式；未安裝或實跑外部 repo。

| 來源 | 優先借用 | 在本專案的接法 |
| --- | --- | --- |
| [花叔 huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) | 參數化動畫、白板關係、文字揭示、數據圖表的視覺語法 | 固定 JSON／保存音檔先做離線片段；adapter 把語意動作與實測時間轉成 `data/cues`。圖表只在來源有適合數據時使用 |
| [岚叔 lanshu-create-ai-presenter-video](https://github.com/cclank/lanshu-create-ai-presenter-video) | 同一元件 API 對應不同 style kit；旁白驅動編排、逐句快取及解碼／響度交付檢查 | 先借內容、樣式、時間分離的設計；補強現有快取与 export。沿用現有語音，不為接風格改用另一供應商 |

原始接點：[花叔 clip.js](https://github.com/alchaincyf/huashu-art-motion/blob/main/scripts/engine/clip.js)、[render.py](https://github.com/alchaincyf/huashu-art-motion/blob/main/scripts/engine/render.py)、[岚叔 KITS.md](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/explainer/KITS.md)、[story.py](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/explainer/tools/story.py)、[交付檢查](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/scripts/finalize_delivery.sh)。既有詳細評估：`docs/experiments/2026-10-08-video-reference-evaluation.md`。

不能把 Canvas 動画直接貼進原生 PPTX。三種輸出共用教學內容與視覺語法，各自保留 rendering：影片呈現狀態變化、線上簡報可逐步揭示、PPTX 保留可編輯重點狀態、心智圖展開解說。若某元件只能輸出圖片，能力目錄必須明示，不以圖片冒充可編輯圖形；第一批核心圖解要求原生編輯。

採用前固定 commit、必要依賴與字體，保存授權。僅導入程式與可使用素材；不挪用作者角色圖。外部動畫 runtime 的字幕安全區、繁體缺字、編碼退出狀態與旁白截尾需由本專案驗證，不能只信外部警告或檔案存在。

岚叔「每秒保持動態」等規則不直接作教學硬閘：走讀、算式與長中文要有閱讀停留。動態是否有助理解，由對照樣片與使用者驗收判斷。

## 4. AI 更多選擇的具體設計

先建立小型能力目錄，為每個元件記錄教學用途、必要資料、容量、支援輸出、動作、原生可編輯能力、已通過的 fixture 與版本。第一批先用 `code + vars + output + pipeline`；既有其他元件繼續可用，但新增三產物適配須逐項驗收。

AI 只從本批已驗收的能力選擇，並給出選擇理由。程式驗證輸入、容量、來源與 target；無法支援時記錄缺口並使用明示的相容方案，不能讓未知元件靜默變成條列。

| 教學任務 | 可選表現 | C 迴圈示例 |
| --- | --- | --- |
| 建立概念 | 專業圖解、結構與關係 | 初始化、條件、更新三者各負責什麼 |
| 演示機制 | 程式碼＋狀態＋輸出，逐步走讀 | 同步標亮執行行、i 的值與印出的結果 |
| 辨別選擇 | 並排比較、決策圖解 | for／while 的適用情境，有來源支持才產生 |
| 修正迷思 | 錯誤前後、邊界標示 | 條件邊界如何多跑或少跑一輪 |
| 說明操作 | 流程、終端機、視窗與游標 | 編譯與執行；不套在純概念段落 |
| 回顧 | 關係總覽與可展開概念 | 三要素如何形成重複執行 |

同一單元維持一套字體、色彩角色與動態語言；段落依理解任務變化。第一批以已確認的專業圖解為主，白板推導與狀態走讀作表現選擇，不預設每頁換風格。同輸入、配置與 seed 應可重現，增加可選配置而非不可控隨機。

自然感的工作包括：以具體問題開場、句子長短配合推導、講到變化才演出變化、提供具體例子、刪掉無信息的過場與重複總結。套話密度與版型重複先作編輯提醒；來源錯誤、缺字、越界和漏掉必要內容才是硬錯誤。人工感受不能用一個「去 AI 分數」取代。

## 5. 五批執行與交付

以下為建議批次，所有 checkbox 均未完成；不是日期承諾。每批獨立驗收，前三批先補原第四步，第四批接續影片品質，第五批收斂自動化。

### A：固定基準與元件能力（先做）

**檔案接點：** `video_engine/materials/c_loop.md`、`video_engine/board/catalog.json`、`prompts/components.md`、`studio/deck_contracts.py`、`studio/mindmap.py`。新增樣本與量測結果放 `docs/experiments/2026-10-09-three-output-quality/`；能力適配資料先由 `studio/teaching_components.json` 保存，不重寫 Board 動作目錄。

- [ ] 保存同教材、內容、來源版本與可用音檔的基準；分開標示模型生成與人工展示。
- [ ] 盤點 13 個既有元件，為第一批四個元件填入輸出支援矩陣；未適配輸出不能標為支援。
- [ ] 準備概念、流程、程式走讀、比較、長中文五組固定 fixture；數據圖表另用來源確有數值的 fixture。
- [ ] 保存字級、越界、重疊、來源支持與閱讀停留的基準；純風格 A/B 固定內容和音檔，內容改善另列前後講稿與來源。

**交付／驗收：** 元件能力表、三種舊版實際樣本、五組 fixture、每組預期理解任務。先有可比較基準再調 renderer。

### B：AI 教學規劃與簡報元件適配

**檔案接點：** 新增 `studio/teaching_plan.py` 與共用讀取接點 `workbench/teaching.py`，修改 `workbench/library.py`、`studio/deck_builder.py`、`deck_contracts.py`、`pptx_export.py`、`workbench/run_slides.py`、`workbench/web/js/viewers/deck.mjs`；擴充現有 deck／PPTX 測試。

- [ ] 小型版本化規劃資料保存問題、教學順序、例子、逐項來源定位與元件選擇理由。暫不強迫舊分析 plan 改版；新資料並存，透過 adapter 接入。
- [ ] 共用接點在模型前驗證教材核對狀態與版本；按正文／規劃契約／提示／模型配置保存 `teaching_plan.json`。先生成一次再由 B、C、D 消費同一份規劃；不要由三個 runner 各自重生例子。沿現有佇列避免同版本重複生成，費用獨立記錄；規劃失敗不留下可重用的成功檔。
- [ ] 每個解釋／例子有來源對應；程式檢查定位與內容未被省略，人工核對推導是否受來源支持。引用存在不能升格為語意忠實保證。
- [ ] 新版逐項引用不走 `deck_builder.py` 的 `_narrow_discontinuous_quotes()` 最長片段裁切；完整保留每項主張的來源識別與引文。舊版維持相容，新版不以單一最長引用冒充整頁支持。
- [ ] 先適配程式＋變數＋輸出的走讀，以及流程圖；新版 Deck 使用明確版本，舊 1.0／1.1 照常讀取，不覆寫既有成品。
- [ ] 線上簡報用語意揭示步驟；PPTX 匯出原生文字／形狀的關鍵狀態或分頁，不承諾保留網頁動畫。
- [ ] 主體字級以 20pt 為目標、16pt 為最低底線；標題、程式碼與圖解標籤另有層級。容量不足先拆頁；不以縮字或隱藏資訊強行通過。

**交付／驗收：** C 迴圈專業圖解簡報，含情境→三要素→執行走讀→選擇／邊界錯誤→回顧；只有教材有支持的段落才保留。提供 HTML 與可編輯 PPTX、來源對照、LibreOffice 轉 PDF 量測；Microsoft PowerPoint 手動編修另列未驗項目。至少再通過不同內容的概念／流程 fixture，避免只為 C 迴圈硬編碼。

### C：AI 心智圖解說分支與穩定展開

**檔案接點：** `studio/mindmap.py`、`workbench/run_mindmap.py`、`workbench/web/js/viewers/concept-tree.mjs`，現有 `tests/test_studio_mindmap.py`、`workbench/web/tests/concept-tree.test.mjs`。

- [ ] 新版契約提供意思、用法、例子、常見錯誤等有來源支持的分支；無材料的項目可省略，不補成固定四格空話。
- [ ] runner 由 B 的共用接點取得同一份核對版本教學規劃，心智圖 adapter 保留共同例子與來源；只對輸出形態另作組織，不另生成一套互相矛盾的例子。
- [ ] 保留原始根節點、展開分支與兄弟分支；點選後圖由原根向外生長，返回收合最近展開。不把點選概念改成全圖新中心。
- [ ] AI 可依資料建議既有發散／漸進布局，程式測量尺寸並拒絕無效選擇；保留手動切換。
- [ ] 維持圖上解說，來源保留在資料層；不重新加入底部閱讀面板、來源按鈕或密集關係小字。跨概念連線後續有實際教材需要才另定契約，不把流程／因果硬作從屬關係。
- [ ] 展開後字仍可讀，聚焦新分支、其餘圖保留可拖曳查看；下載 SVG 的展開內容與預覽一致，或明確提供總覽／完整圖兩種匯出，不漏掉新增解說。

**交付／驗收：** C 迴圈可操作圖＋新版 AI 生成契約、375／768／1440px 展開與返回證據；長中文節點無捲軸、遮擋或裁切，舊 SVG 相容。另用非程式概念 fixture 驗證不是專用展示。

### D：影片表現選擇與外部動畫試片

**檔案接點：** `video_engine/board/author.py`、`prompts/plan.system.md`、`prompts/scene.system.md`、`compile.py`、`build.py`、`check.py`、`export.py`；外部片段試驗隔離在 `prototypes/three_output_quality/`。來源與生成器選擇接 `workbench/formats/video.py`。

- [ ] 將 B 的教學規劃選擇接入既有 Board 元件；模型可選已驗收組合，鏡頭／動畫由語意 target 和實測框編譯。
- [ ] 現有程式走讀先完成一支 60–90 秒樣片；保存音檔不足則先交付明示無聲草稿，不自行呼叫 TTS。
- [ ] 外部先測白板與文字揭示兩個候選；有真實數據的教材才加圖表。固定外部版本、對應能力、字体與字幕安全區；未通過不接預設生成。
- [ ] 使用本機保存音檔和實測句界校準 cue；只有通過對齊驗證的關鍵詞才做詞級同步，不把字數估算當精準詞時間。
- [ ] 校準涵蓋既有 Board：目前 `compile.py` 的 `anchored_start()` 用 cue 的字元位置比例估時，需區分估算與實測。關鍵動作加驗證過的對齊資料；無法對齊時退回明示的句界動作，不宣稱關鍵詞偏差已達標。對齊資料不符當前講稿／音檔版本時拒絕沿用。
- [ ] timing 必須綁定每個 beat 的實際 `spoken`／旁白、聲音配置與音檔 digest；不能只核對句數和時間單調。反向控制使用同句數的不同講稿／音檔，必須在出片前拒絕舊 timing。無身份資訊的舊格式仍可讀，但新品質模式先建立對應後才能通過同步閘。
- [ ] 保留單焦點、適當停留与語意轉場；畫面不因字幕揭示整段跳動。動態只服務狀態變化、推導和閱讀順序。

**交付／驗收：** 同講稿／音檔舊版與新版 MP4，至少檢查片頭、兩次場景切換、程式焦點、字幕與旁白。1080p 核心標籤目標 ≥28px，字幕 38–46px；原 renderer 幾何契約與決定性不能破壞。外部 adapter 若無量測框，先補 instrumentation；沒有幾何驗證的元件保持實驗狀態。

### E：局部重製、品質閘與網站自動化

**檔案接點：** `workbench/jobs.py`、`library.py`、`formats/video.py`、`formats/highlight.py`、`run_slides.py`、`run_mindmap.py`、`video_engine/board/narrate.py`、`compose.py`、`export.py`。

- [ ] 重用已核對共同教材與教學規劃，網站操作即可完成生成，日常流程不依賴聊天框人工改檔。
- [ ] 延續現有逐句音訊快取／重配、分鏡修正與 compose；補完整依賴資訊：正文版本、規劃、提示、模型、元件／renderer、樣式、語音配置。區分音訊快取與畫面快取，變更主題不重配旁白。
- [ ] 音訊身份以文字與聲音配置為主，與句子序號／場景位置分離；保存清單再決定組裝順序。現有 `narrate.py` 路徑含序號，插句或移序會漏掉快取，需相容讀取舊 WAV／ASR／用量，並讓 compose 可重用原段語音，只生成新增銜接句。
- [ ] 正反控制：只改某句講稿重配該句；只改某頁／樣式不呼叫 TTS；改正文使受影響規劃與產物失效；失敗草稿不成為正式完成產物。先列出無法局部更新的跨段依賴，不承諾任意改動都只重跑一小段。
- [ ] 插句、移序與重點片 compose 另作快取控制：原句不因位置變動而重配，新增句才呼叫 TTS；同句改聲線／語速／模型則必須失效。跨段快取取用仍驗證檔案存在、音訊格式及內容身份。
- [ ] 影片交付檢查完整解碼、時長、音訊存在、旁白不截尾與響度；靜態閱讀段不能被凍結偵測直接判錯。建議音畫關鍵 cue／章節端點偏差 ≤200ms，響度 -16 LUFS ±0.5、true peak ≤-1dBTP，均為待校準目標。
- [ ] 三種成品保留生成配置、來源版本、已回報用量、缺口與驗收狀態；先低成本預覽，再按現有明確操作出片。已完成成品在重製成功前保持可讀，失敗不覆蓋。

**交付／驗收：** 同教材版本從網站完成三種產出；一次單句修改、一次樣式修改、一次來源修改與一次注入失敗的重跑範圍／用量證據。C 教材與非程式教材都通過，才宣告一般化自动流程完成。

## 6. 驗收與進度更新規則

功能、視覺偏好與內容忠實度分別記錄。先用固定 fixture／保存音檔驗收 renderer；再以明確授權的真實生成驗收 AI 的選擇與內容。人工精修稿不能冒充模型能力，模型不同結果不能冒充純版面 A/B。

免費回歸指令：

```bash
.venv/bin/python -m unittest discover -s tests -t .
node --test workbench/web/tests/
git diff --check
```

適用批次需另驗證实际 PPTX／SVG／MP4 與 375／768／1440px 網頁；單元測試不取代使用者視覺驗收。交付時附：程式 diff、樣本、來源對照、量測、執行命令、成本及未驗限制。

執行前每批展開精確 schema／adapter 與測試案例；本文件不把尚未選定的外部 API 固定成已完成整合。

本輪重新執行回歸：Python 735 項，734 通過、1 略過；工作台前端 94 項全部通過。日誌分別為 `/tmp/videomaker-quality-audit-python-20261009.log`、`/tmp/videomaker-quality-audit-web-20261009.log`。這些結果證明既有免費回歸基準，不代表上述新功能已實作、真實 AI 內容或視覺品質已驗收。本輪只修改規劃文件，未呼叫付費模型／TTS、未新增依賴、未 commit／push。

對抗審查已完成；主代理核對後補上共用教學規劃消費、講稿／音檔／timing 身份、插句／移序／compose 快取、逐項來源不被裁切四項條件。[審查與驗證紀錄](../../experiments/2026-10-09-three-output-quality-review.md)。目前交付為可展開執行的分批方案，各批實作與使用者成品驗收尚未完成。
