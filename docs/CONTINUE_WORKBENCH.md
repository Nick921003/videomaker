# 新對話交接：多元教材工作台

更新：2026-10-08（Asia/Taipei）。實際專案/home/pjw92/projects/videomaker；WindowsApps UNC預設cwd失效時明確使用WSL路徑。使用者要求先保存所有改動到分支並push。

## 目標與進度

學生原教材看不懂或不好看時，轉換成簡報、心智圖、重點／串接長影片、Podcast、海報／漫畫自學。專案自行讀取文件與生成，不依賴聊天框。八步主計畫：docs/superpowers/plans/2026-10-08-independent-material-workbench.md。

第一、二步技術驗收完成；第三步共同教材資料及來源版本接入已實作並修正AGY審查；第四步仍未完成：使用者否決初版內容與風格，後續以C教材重做互動，但AI教學規劃、布局自動選擇、既有動畫元件接入仍待實作。第五至八步待接續。不能把通過測試當成設計或真實模型品質驗收。

## 已確認的設計要求

- 學生自學，PPT專業圖解；完整概念、例子與推導，忠於原教材，教學順序合理。
- 心智圖分類只有名稱；解釋另成分支。點整個框即可向外展開，保留原始根與其他分支，不能重新以點選概念為中心生成子圖。
- 點一次展開並自動調整視角；滾輪縮放、拖曳平移；全螢幕、返回收合最近展開、回到總覽；漸進／發散布局可切換，AI自動選擇未接入。
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

本次backend全套先前735項通過（1略過）；之後互動與CSS修改需跑最新前端與瀏覽器驗證。前端94項先前通過。免費fixture與隔離資料；不呼叫真實付費模型、TTS或圖像服務，未新增依賴。真實生成與教學品質需另驗。

運行：.venv/bin/python -m unittest discover -s tests -t .；node --test workbench/web/tests。Playwright Python /home/pjw92/.local/share/pipx/venvs/webwright/bin/python。證據與各階段報告已保存在docs/experiments。
