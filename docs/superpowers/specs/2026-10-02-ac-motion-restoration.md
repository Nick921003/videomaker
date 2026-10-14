# 通用紙上動畫恢復 A＋C 呈現與旁白字幕

使用者否決環境建立的文字卡風格，要求先完成A＋C影片效果，再由使用者生成一次。參照為已接受的state_change_ac_20261001/c_string_ac.mp4；12秒字串形成、20.4秒C程式提示、25.32秒NUL停止、33秒比較。旁白字幕必須對完整speech，不得以caption摘要替代。

成功條件：/paper-video-test新生成使用通用A＋C渲染；長格紙、可見鉛筆描線、資料主角持續、值可沿路徑轉移、掃描指標可停在語意focus_index、鏡頭跟隨正在變化的主角；code與資料並顯時只短暫顯示聚焦行提示，之後回到資料。不可只是固定大矩形文字卡。theme配色對齊已接受參照，來源、座標契約與決定性維持。

PaperBoard兼容舊text/cells/code，新增flow（1–8項、每項<=18字）。step可選motion=reveal/transform/scan/transfer、source（必須已知且visible，transfer才可使用）、focus_index（非bool整數-1或focus非code更新後有效索引）；舊board仍合法且不填默認新keys。指示模型選適合的持續物件與語意動作；不從關鍵字猜教材內容或插入不相關圖示。

字幕取自完整speech，按自然短句拆行。真TTS記錄每個fragment的文字與實測局部start/end，compile輸出subtitle_cues與SRT，frame_at按cue顯示；有實測片段時使用片段邊界，沒有時標記為整段字量估排。不宣稱逐字/ASR強制對齊。字幕拼接必須還原speech非空白字符；reject缺字／多字fragment資料。

免費A/B evidence以同一board/timeline/WAV渲染舊／新，至少字串與另一份教材；檢查實際PNG/MP4、字幕全文、程式提示進退、camera連續、seek決定性、量測bbox不越界、正文可讀。此次不呼叫付費LLM、不新生成TTS、不改.env、不commit/push、不改普通cards/PPT；保留被否決成品並標為未通過風格驗收。


審查補充：transfer來源禁止code，必須指定已知visible source；多值來源必須source_index（非bool整數），對來源在此步更新前的持續values驗bounds，單值來源預設0。focus_index對目標此步更新後的持續values驗bounds。同物件內transfer可用舊值，但不得未知slot。C提示沿用兩步：先code focus+code_line，再data focus且保留code visible、code_line=-1；提示生命週期從最近有效code line建立時起算，不因每step重進場。測動態screen metadata含glyph、箭頭、指針、飛行值與hint，不只大panel。字幕fragment拒絕bool/NaN/inf、重疊逆序、未知step與部分speech覆蓋；TTS無標點160字仍應分到<=70字且避免尾段不足12字。

語意補充：text多個values只表並列短註解，不自動畫箭頭暗示先後/因果；flow才顯示有序連接。transfer的source路徑須由明確語意指定，不能依字詞猜關係。
