# A＋C 通用紙上動畫整合 Implementation Plan

> Agent workflow: subagent-driven-development 分工，adversarial-review 與 spec／quality 審查；不commit／push、不覆蓋原型或dirty worktree。

**Goal:** Demo上傳其他教材可選paper，完成來源分鏡、審稿、旁白、1080p影片與用量統計。

**Architecture:** PaperBoard語意契約→固定長紙面物件與持續狀態→量測幾何→實測語音時間與跟隨鏡頭。獨立paper job/facade接既有8階段API，舊影片與PPT相容。

**Tech Stack:** 既有LLM SDK、Pillow、numpy／scipy、FFmpeg、ThreadingHTTPServer、ES modules、unittest／node:test；無新依賴。

## Task 1: 分鏡／job／facade

新增video_engine/paper_contract.py、studio/paper_video.py、studio/paper_video_facade.py、tests/test_paper_contract.py、tests/test_paper_video.py。

- [ ] 先測水循環與程式累加兩份board；拒未知欄位、重複ID、超限、無來源quote/code、未知或hidden focus、非法line。觀察失敗再實作。
- [ ] canonical_board(value, material=None)依spec閉合結構與界限回deepcopy。build_paper_board(material,instruction,seconds,complete_json)單次lesson callback，prompt包含持續物件、自然旁白與來源；私有job目錄保存board／usage，不公開prompt。
- [ ] PaperVideoJob(material_path,out_dir,sec,complete_json,instruction='',synthesizer=None,renderer=None)繼承Job，重用claim/pct/clock；start生成board与preview／layout後awaiting_review。segments使用scene.id作slide_id、idx索引steps；語意審稿一次驗完整ID與speech後原子修改，不再呼叫LLM。
- [ ] resume呼叫lazy既有TTS，synthesizer注入signature (speech)->(sample_rate,mono_pcm)，品質不合格拒絕；step.id WAV→compile_paper_audio→renderer(board,timeline,master_audio,video_path,cancelled)→completion check。終態釋放一次。
- [ ] PaperVideoJobFacade繼承VideoJobFacade的containment／download／timer，覆寫paper get_review/submit_review/close。取消時不得事後啟動TTS或留FFmpeg孤兒。
- [ ] Run .venv/bin/python -m unittest tests.test_paper_contract tests.test_paper_video。

## Task 2: 紙面／時間軸／影片

新增video_engine/paper_renderer.py、video_engine/themes/paper.json、tests/test_paper_renderer.py。

- [ ] 先測跨scene更新保留、行焦點、PNG決定性、量測bbox在panel內、seek順逆相同。board不含座標。
- [ ] layout_board(board)->dict；render_previews(board,out_dir)->layout写layout.json（slides含scene.id作slide_id）与slide_NN_full.png；frame_at(board,timeline,time_seconds,size=(1920,1080))->PIL.Image。
- [ ] 整板物件固定在同一長格紙，更新累積，鏡頭平滑跟隨focus及必要visible物件；描線、值變化、code高亮行、字幕固定screen區不隨world裁切。配色來自paper.json，字体重用。
- [ ] compile_paper_audio(board,wavs,out_dir)->dict，wavs為step.id:WAV Path；timeline.steps每entry含scene_id,step_id,start,end与duration；寫master.wav及subtitles.srt，全部排程依WAV實測含短過場停留。
- [ ] render_paper_video(board,timeline,master_audio,video_path,cancelled=None)以FFmpeg raw RGB image2pipe產H264/AAC，partial完成後原子rename、不覆蓋；每frame驗cancelled Event，finally terminate/wait。
- [ ] Run .venv/bin/python -m unittest tests.test_paper_renderer。兩種領域離線board重用已有WAV輸出真MP4，FFprobe1080p/AAC与完整decode、抽帧驗正反seek與不越界；不新呼叫LLM/TTS。

## Task 3: 獨立 Demo 測試入口（最終使用者確認）

修改studio/catalog.py、contracts.py、planner.py、planner_backends.py、serve.py、web/index.html、web/js/api.mjs、state.mjs、render.mjs、app.mjs与既有測試。

- [ ] 普通catalog／video plan完全保持舊契約；新增experimental video.paper_preview.v1，catalog?experiments=paper才列出。未知experiment或job自帶style／capability拒絕。
- [ ] /paper-video-test獨立測試頁，普通Demo加「新影片風格測試」連結按鈕。api catalog/plan透過明確paper-test模式取得測試能力／計畫，state保存testMode，reset仍在測試模式，UI注明驗收後再正式接入。
- [ ] PaperTestPlannerBackend只在/api/studio/plans?mode=paper-test回傳試驗capability与duration_seconds，source契約不改；job capability只來自server保存plan。
- [ ] serve試驗capability建立PaperVideoJob+Facade，正常影片仍原Job；snapshot／artifact capability為試驗ID，8階段review／TTS preflight／slot／source revision／tokens／Range通。
- [ ] 離線fake HTTP与真Chromium測上傳→選style→plan→審稿修改→resume→MP4播放／下載，兩教材來源不串帳。新埠隔離preview保留已開服務資料。

## Task 4: 審查／驗收／交付

- [ ] 對抗review計畫，逐task spec／quality review，修重要遺漏。
- [ ] 全套unittest、node tests、ES module語法、git diff --check，实际抽帧／decode與媒體metadata。
- [ ] 更新README／NEXT_STEPS／VIDEO_DESIGN_STATUS，交付docs/experiments/2026-10-02-paper-video-integration.md、範例MP4與Demo URL，說明通用封閉圖形与旁白段級同步限制。
