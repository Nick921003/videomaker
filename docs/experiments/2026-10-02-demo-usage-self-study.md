# Demo 生成用量與學生自讀簡報（2026-10-02）

## 使用者確認的範圍

影片風格工作停在10月1日A＋C有聲版。本輪完成Demo每次教材生成的真實tokens統計，採「本次生成」與「教材AI整理（共用素材）」分列，另顯示估算USD。PPT以學生自行閱讀為情境：清楚教學圖解、依內容變版，每頁關鍵解釋可見；有影響需求的模糊問題應暫停詢問。

## 用量功能

- 原始SDK response到達後、JSON解析與內容驗證前記錄usage，所以截斷、JSON錯誤及後續驗證失敗仍保留實際消耗。
- ContextVar隔離每個來源／job，直接SDK紀錄與runner返回metadata只採一次；工作台snapshots／SSE重播與PPTX匯出不增帳。
- Gemini合計含thinking，Claude／OpenAI thinking已在output，不能重複相加。Gemini cached是input子集，Claude cache read/write為原input外的tokens，分供應商處理。
- 缺usage標未取得，部分缺失標「至少」與已知小計，未知模型費用為null；供應商只報total時保留total，不捏造input/output。Gemini沒拆報thinking但有可信input和total時以total-input取得含思考output。
- 教材整理ledger為此來源累積（含失敗與重試），重用已完成整理不新增；整理錯誤的HTTP回應傳安全source摘要至前端。
- 影片子行程沿既有JSON stderr發送flush用量事件，Job累加且不影響進度。離線真subprocess測試覆蓋run.py→serve.real_runner→Job。
- 用量紀錄只含模型、階段、數字與估算費用，不保存prompt、教材或API key。來源／job仍是現有記憶體索引，服務重啟後消失；舊工作未保存的usage不能補帳。

### 費率

費率查證日2026-10-02；依官方付費Standard單價估算，而非帳單實扣、免費額度、折扣或匯率換算：

| 模型 | Input／百萬tokens | Output／百萬tokens | Cache |
| --- | ---: | ---: | --- |
| Claude Opus 5.5 | US$4 | US$20 | read US$0.20、5m write US$5、1h write US$8 |
| Gemini 3.8 Flash，至2026-12-31 | US$0.75 | US$3.75 | cached input US$0.075 |
| Gemini 3.8 Flash，2027起 | US$1.50 | US$7.50 | cached input US$0.15 |

來源：[Opus 5.5官方費率](https://platform.claude.com/docs/en/models/opus-5-5/overview)、[Gemini官方費率](https://ai.google.dev/gemini-api/docs/pricing)。費率於呼叫記錄時換算成本，已保存成本不會因重讀跨年而重新計算。其他模型沒有此處查證的單價時只顯示tokens。未計外部工具額外費、SDK隱藏且未回報的重試、TTS／Whisper／電費或Codex對話用量。

## PPT風格

- 新生成為Deck 1.1，每頁必填不超過120字的takeaway，直接呈現在HTML與PPTX頁面。
- 五種主版型：重點、程式碼、比較、流程、概念關係。新增concept中心（<=40字）及2–4分支（標題<=32字、解釋<=80字），PPTX保留原生可編輯文字、圖形與連線。
- 模型指令依內容選版，不強迫每頁圖解；學生必要解釋不只藏在備忘稿。引用應支持takeaway與概念關係，但現有自動驗證仍僅驗引文可定位，不宣稱逐項事實忠實度已解決。
- PPTX主內容／可見解釋／頁碼使用分離區域，放不下最低可讀字級就拒絕。舊Deck 1.0保持封閉契約與原幾何可預覽／匯出，新模型回退1.0則拒絕，避免缺頁面解釋。

## 實際驗收

1. Python完整回歸：`.venv/bin/python -m unittest discover -s tests -t .`，**362項，361通過、1略過**。日誌 `/tmp/videomaker-full-tests-final-20261002.log`。其中預期失敗控制會輸出warning／error日誌，最終unittest結果為OK。
2. 前端：`node --test tests/web/*.test.mjs`，**26項通過**；涵蓋錯誤用量傳遞、來源版本匹配、未知／部分統計、hostile文字、概念圖與takeaway呈現。
3. 真實Chromium 1440／375：隔離HTTP伺服器注入fake LLM，完成上傳→整理→生成→概念頁預覽→核可→下載原生PPTX→同來源再生成→重新整理網頁後查用量；generation各300、normalization2097，重用不倍增。失敗整理兩次保留4194／2calls。兩寬頁面scrollWidth等於viewport，0pageerrors。證據 `demo-http-qa.json`。
4. PPT離線sample／最大界限各4頁×兩寬共16筆，加usage兩寬共**18筆幾何量測**皆無橫向溢出。PPTX重新開檔驗全部形狀在頁內且不侵入takeaway，最大文字保留；LibreOffice轉PDF與pdftotext核對解釋／takeaway沒有丟失。
5. 舊1.0單項49／60／70／120字與高密度各版型原生PPTX相容回歸通過。
6. `git diff --check`與ES module語法檢查通過。獨立對抗審查找出的缺usage、舊幾何相容、新生成版本及Gemini思考分項缺漏皆有反例並修復。

## 可查看的交付物

`video_engine/out/self_study_deck_20261002/`：`sample.pptx`、`sample.pdf`、`sample.deck.json`、`sample-material.txt`、1440／375的PPT與Demo截圖、`browser-geometry.json`、`demo-http-qa.json`。

此樣本以公開合成教材及本機手製Deck示範排版，**不是新呼叫模型的教材內容驗收**；HTTP截圖的tokens是fake回應，僅驗證呈現與核算，不能當真實帳單。真實SDK回應格式由離線mock測試驗證，本輪新增付費LLM／TTS呼叫0。

新版Demo已在 `http://127.0.0.1:8899/` 啟動，使用 `/tmp/videomaker-demo-preview-20261002/` 隔離來源，沒有載入fake模型或測試帳目，保留專案既有暫存。啟動器為 `/tmp/videomaker_demo_preview_20261002.py`；HTTP首頁與renderer均確認200。按網站既有確認按鈕後才會進行真實模型呼叫。

保留原先dirty worktree，未commit／push。真實教材內容品質、學生閱讀體驗與PowerPoint手動編修仍由後續實測確認。
