# 通用 A＋C 動畫與旁白字幕 Implementation Plan

Goal: 使用者在獨立紙上動畫測試入口生成一次，即使用新A＋C效果與完整旁白字幕。
Architecture: 有界語意motion／flow契約，Pillow長格紙與角色路徑動態，TTS實測fragment字幕時間；保留舊board與正式影片入口。
Tech Stack: 現有Pillow/numpy/FFmpeg/unittest/ES modules；無新依賴。

- [x] Task 1（字幕獨立模組與job）：先測完整speech可回拼、fragment實測排程、拒絕漏字資料，再實作paper_subtitles.py與PaperVideoJob保存speech_fragments.json。API：build_subtitle_cues(board,timeline,fragments=None)->list、subtitle_at(cues,t)->str。無fragment用字量估排且記basis。
- [x] Task 2（視覺renderer/theme）：以已接受PNG與MP4作參照；改paper_renderer.py與paper.json、tests/test_paper_ac_renderer.py。非code不畫大卡外框；cells/flow逐筆成形、沿路徑值轉移、掃描指標；visible狀態資料不重設；co-visible code短暫側邊提示聚焦行退場；鏡頭跟隨資料與交互移動，布局由實測幾何取得。編譯音訊接Task1 helper，SRT不再取caption。
- [x] Task 3（contract與prompt）：video_engine/paper_contract.py接受flow及可選motion/source/focus_index，閉合驗證；prompt要求語意動作與C提示配對，不把完整長程式／所有物件永久同頁。先測合法與非法引用／bounds／bool再實作。
- [x] Task 4（整合與驗收）：根代理核對實際diff與產物，審查spec／quality；離線同音訊舊新對照至少30秒，檢查字幕、值飛行、程式提示進退、seek與幾何，全套Python/Node與diff檢查；將測試服務啟動為新版，保留舊工作／產物，交付URL供使用者自行生成，不代按付費生成。

分工檔案所有權：字幕代理只改paper_subtitles.py、studio/paper_video.py、tests/test_paper_subtitles.py及必要job測試；視覺代理只改paper_renderer.py、themes/paper.json、tests/test_paper_ac_renderer.py及舊renderer測試必要SRT斷言；根代理只改paper_contract.py及對應tests/prompt/文件/免費驗收與服務。介面變動先互相通知。


執行補充：增加source_index與scan_output明確來源/前綴關係，字幕cue外帶資料亦校驗；C提示以秒數計生命週期，reserve與opacity分離防遮擋。完成443項Python/30項Node、同音訊37.22秒A/B、水循環免費控件、新服務8913及官方host配置檢查；未新呼叫模型/TTS，新教材生成留待使用者按鈕。
