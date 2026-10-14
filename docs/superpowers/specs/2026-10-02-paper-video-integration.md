# A＋C 紙上連續動畫正式 Demo 整合

使用者已確認 A＋C 效果，要求其他教材也能生成同類動畫；PPT 已完成，本輪不修改 PPT。最後範圍確認：先新增獨立「新影片風格測試」按鈕與測試頁，使用者驗收後才納入正式影片；不得更改正式預設或普通影片入口。

Demo 選「紙上連續動畫（A＋C）」→上傳教材→既有 AI 整理→免費計畫→新教材分鏡→可編輯旁白審稿→本機 TTS→實測時間軸→1080p MP4 播放／下載／核可。來源、tokens 與產物屬於此工作；不借用 Alice 成品冒充新教材。

視覺參照是10月1日41.125秒A＋C成品。沿用格紙、鉛筆描線、持續物件、狀態變化、平滑鏡頭與可選程式走讀。非程式教材不插入程式碼。使用確定性圖形文字，無影片模型。

## PaperBoard 1.0 語意契約

    {"contract_version":"1.0","title":"水循環","objects":[
      {"id":"water","kind":"cells","label":"水的狀態","values":["水","水氣","雲"]},
      {"id":"cause","kind":"text","label":"原因","values":["受熱"]}
    ],"scenes":[{"id":"s1","title":"蒸發","source_quote":"水受熱後蒸發成水氣。","steps":[
      {"id":"b1","speech":"水受熱後，會蒸發成水氣，我們先看這個變化。","caption":"受熱使水蒸發","focus":"water","visible":["water","cause"],"updates":[{"target":"water","values":["水","→","水氣"]}],"code_line":-1}
    ]}]}

完整板需要objects 1–6、scenes 3–8、每scene steps 1–4、總steps <=24，所有object／scene／step IDs合法唯一。kind限text/cells/code；text 1–3項每項<=50字、cells 1–8格每格<=12字、code 1–8行每行<=80字。title<=60、label<=30、scene title<=50、quote<=1200、speech12–160、caption<=48字。

focus及updates引用已知且可見物件，同step不可重複updates；更新values符合kind容量，code不可更新。code_line=-1或focus code內的有效0-based行號。初值及updates跨scene累積，不重設物件。不允許像素座標／時間碼／執行命令／圖片URL。每scene引用對回原教材；code非空行必須對回教材（只忽略空白）。引用定位不等於逐項事實忠實度驗證。

每step採完整自然旁白，實測WAV排程；狀態在此段旁白開始改變，字幕與鏡頭按同一時間軸。同步精度為旁白段級，不宣稱ASR逐詞同步。使用者指定秒數為目標，實際以語音長度為準。

新board與舊lesson/actions契約分開；新幾何由渲染器量測layout.json，顏色只從paper theme JSON，字型沿用現有Noto。同board/timeline/time畫格決定性。

測試能力video.paper_preview.v1，只由/paper-video-test測試頁與/api/studio/plans?mode=paper-test進入。普通catalog不顯示；測試頁專用catalog query experiments=paper才提供，get_capability可驗其閉合duration_seconds選項。server保存計畫決定此job，不接受job request覆寫。正式video.micro_lesson.v1、cards預設与PPT不改，沿用8階段、review、artifact／Range、CSRF、execution slot。

timeline.steps.start/end是各段speech真正界限，pause只算master總長；gap保持上一step，下一speech開始才更新。所有sr相同、PCM為int16mono且有效有限值，duration=master樣本數/sr。renderer在step內逐格stagger呈現prev→new值與游標，不能退化成翻頁卡片；code visible時保留先前行焦點。

close使用cancelled Event，已在LLM/TTS中者等response後終止，不提前放slot或清來源；awaiting_review／claimed-before-resume可直接終態。取消FFmpeg要能terminate/kill中斷pipe阻塞。lazy synth import的SystemExit必須轉成工作失敗。隔離preview明確注入自己的SourceStore／OUT，避免make_server全域cleanup損及既有資料。

LLM單次使用既有lesson 8192上限，无應用層自動重試；usage在解析前保存。TTS沿既有品質閘，不合格明確失敗。close取消工作与FFmpeg、釋放slot／快照。自動驗收不呼叫付費LLM／TTS；以離線board和既有音訊驗證，使用者按Demo確認後測真生成。
