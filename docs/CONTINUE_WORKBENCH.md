# 新對話交接：多元教材工作台

更新：2026-10-12（Asia/Taipei）。實際專案/home/pjw92/projects/videomaker；WindowsApps UNC預設cwd失效時明確使用WSL路徑。所有變更先做本機提交；未取得明確指示不push。

## 2026-10-12 當前入口

使用者試用後更正產品範圍：AI對話從教材或學習問題開始，釐清內容並選擇影片／簡報／心智圖；有對應成品先重用，沒有才製作新的。影片觀看後提問只是其中一個分支。下述影片聊天計畫僅完成該分支，完整的教材對話入口與跨形式選擇／重用／製作仍待串接；不得預設每次進入AI對話都先展示固定影片。

影片聊天計畫 `docs/superpowers/plans/2026-10-11-workbench-video-chat.md` 已完成：初始48秒成片、章節定位、正式 `/ask` 重用既有影片、其他課題元件樣片、補強需求紀錄、安全 `/trials/` Range路由與響應式介面皆已接入。新AI影片生成與補強派工仍未接入，不能把需求紀錄說成生成完成。

目前正式素材庫服務在8876，真實製片入口 `http://127.0.0.1:8876/web/index.html#/make/1`，不用mock；`.venv/bin/python -m workbench.server --port 8876` 可重啟，模型轉接層會自行讀取.env。已有使用者工作時先確認佇列，不直接重啟。

使用者單元4f2ef7bf2785的q4已實際出片（工作dce5d8ddad684c579848089acb06a6e6），成品入口 http://127.0.0.1:8876/web/index.html#/make/4?unit=4f2ef7bf2785 。影片約84秒1080p有聲；桌機／手機Chrome播放、定位46秒、HTTP206通過。使用者重試的來源引文錯誤已改用後台原文片段ID恢復，教學表達可自然改寫但須語意正確；保留失敗候選。共同規劃不再被PPTX長程式碼排版阻擋，未知費用null不再使Board預算崩潰。第7／8／11句仍保留可能漏唸提示與逐句重配，人工試聽品質待確認。只有q4生成，本教材長程式碼簡報容量問題仍待改善。既有緊湊製作頁正文14／標題15／按鈕13px及四種尺寸驗證保持。詳細證據：docs/experiments/2026-10-12-q4-reference-retry.md。

簡報第一批共用Board pipeline階段資料已接入Deck1.2、線上逐步高亮與原生PPTX；心智圖共同規劃1.1加入分類短名稱與父子关系引用，保留舊1.0相容與向外展開。人工基準在docs/experiments/shared-components-20261012，隔離預覽8877、單元b69bfb8c3481；不是付費AI成品。六種外部樣片尚未全部接入正式生成。

## 目標與進度

目前只推進影片、簡報、心智圖；暫不拓展Podcast、漫畫等格式。八步主計畫：docs/superpowers/plans/2026-10-08-independent-material-workbench.md。

第一、二步技術驗收完成；第三步共同教材資料及來源版本接入已實作。第四步共同教學規劃、模型選擇心智圖布局、程式走讀及pipeline資料適配已實作，但真實模型內容與設計品質尚未驗收，六種樣片未全整合。第五至八步待接續。不能把通過測試當成設計或真實模型品質驗收。

## 已確認的設計要求

- 學生自學，PPT專業圖解；完整概念、例子與推導，忠於原教材，教學順序合理。
- 心智圖分類只有名稱；解釋另成分支。點整個框即可向外展開，保留原始根與其他分支，不能重新以點選概念為中心生成子圖。
- 點一次展開並保留父概念視角；滾輪縮放、拖曳平移；全螢幕、返回收合最近展開、回到總覽；漸進／發散布局可切換，共同規劃可指定布局，真實模型選擇品質待驗。
- 不顯示「先理解」「確保前進」等小字、查看來源入口、下方解說面板與節點內捲軸。來源證據後端保留。
- 心智圖不顯示左側成品picker；全成品頁不重複顯示已選類型標題／費用摘要。各頁移除大標題與宣傳，製作頁保留教材名稱、步驟和必要操作。
- PPT Space下一頁、Shift+Space上一頁，輸入及可操作元件保留原生按鍵。

## 預覽與示範資料

網站 http://127.0.0.1:8765/web/index.html#/make/4?unit=ecdc0848e6bb 。服務使用隔離目錄/tmp/videomaker-step1-preview-20261008/units，pidfile在其上一層server.pid。先核對/proc/pid/cmdline再停服務，不能影響其他程序。

C教材與本轮人工編排的5頁PPT及9概念SVG已保存docs/experiments/workbench-step4-evidence-20261008/c-loop-demo；不是宣稱已付費呼叫Gemini的成品。必要時複製該目錄至預覽units/ecdc0848e6bb，保留其他已有影片。Python極短fixture只驗排版，使用者認為不能充當成品。

## 用量估價待修正

使用者發現單支顯示0.02而總額0.382。核對API：q1 .056、q2完成0、q3 .053、q4 .0545、q5 .05、highlight .168，合計.3815顯示.382。0.02是分鏡階段參考費用；highlight估價未扣同批短片可重用內容，估價可能重複。需改善明細與共享片段估價，不可說成已扣款。

## 外部參考與協作

AGY透過/home/pjw92/.local/bin/agy原生CLI，未完成報告不可當成已驗收。報告docs/agy_results/。使用者已授權共同執行與持續開發，有實質設計不確定立即問，不需重問已確認要求。

影片外部評估docs/experiments/2026-10-08-video-reference-evaluation.md：花叔動畫元件、岚叔口播／交付檢查，尚未整合。PPT/心智圖參考Slidev主題、Markmap、SimpleMindMap，尚未安裝或採為正式引擎。既有board catalog有code、vars、output、pipeline等可評估適配。

## 驗證與限制

最新Python全套795項OK（1略過）、前端101項通過。本次q4是真實模型與TTS成品，不是fixture；其他簡報／心智圖仍以之前的固定教材、Chrome互動及16頁PPTX實轉PDF證據為限。沒有新增依賴。單元已知費用小計US$0.143113，另4筆未知呼叫保留，不等於帳單總額。其他教材與整體教學／設計品質尚待驗收。

運行：.venv/bin/python -m unittest discover -s tests -t .；node --test workbench/web/tests。Playwright Python /home/pjw92/.local/share/pipx/venvs/webwright/bin/python。證據與各階段報告已保存在docs/experiments。
