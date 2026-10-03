# 連貫字幕與動畫試排（2026-10-01）

## 使用者要求與根因

使用者接受原型動畫，但指出旁白不像人在講課，逐項說第一格、第二格、第三格造成重複。本輪依要求只改字幕，沒有生成TTS。

原始 `prepare_models.py` 把 scan 分成五段並要求每段各有 speech，因而把五個視覺事件誤當成五個口語段落。後來將英文字母換成「這個字母」只處理發音，仍未處理段落重複。新試排將講解段落、字幕短句及視覺事件分開排程；同一講解段落可以配合多次資料變化。

## 實際製作

- 重用先前 Gemini 3.8 Flash 的教材整理與已核對的字串分鏡。
- 使用前一輪已完成的 Claude Opus 5.5 口語稿：四段 setup／copy／read_stop／summary；實際 request、response、model 與 usage 在 `video_engine/out/state_change_natural_20261001/`。
- 本機編輯將開場改成「三十二格，為什麼長度只有五？」；將「沒整理過的舊資料」改成較精確的容量與長度說明。Claude 原稿 `narrative.json` 與編輯稿 `narrative_edited.json` 分開保存，沒有把本機編輯稱為 Claude 原文。
- 四個講解段落配合九個視覺段落。五個 scan 共用 `narration_id=s3`，上方說明保持「從開頭讀，遇到結束字元就停」；字幕按完整語句分為十一條，不播報索引。
- 沿用同一陣列、游標、輸出面板、配色和字型，移除結尾考題，最後以容量32、長度5、至少6格收束。
- 44秒無聲MP4與GIF只供文字與動畫節奏評閱。未生成TTS，時間為人工試排，不宣稱完成語音同步或口語聽感驗收。原57.90秒有聲影片保留。

## 產物與用量

目錄：`video_engine/out/state_change_natural_20261001/`

- `SCRIPT.md`：可直接閱讀的連貫字幕稿。
- `subtitles.srt`：十一條有時間碼的字幕。
- `state_change_pilot.mp4`：44秒無聲字幕預覽。
- `preview.gif`、`contact_sheet.png`：快速檢視。
- `pilot_timeline.json`：分開記錄 subtitle_cues 與視覺 segments。
- `claude_response.json`、`claude_usage.json`、`token_usage.json`：來源與用量證據。

口語稿呼叫輸入1,423、輸出2,372（內含思考1,866），合計3,795 tokens；加上此前20,313，本系列累計24,108。此輪預覽新增付費呼叫0、TTS呼叫0。

## 驗證與流程限制

`subtitle_preview.py` 檢查旁白不含逐格播報、五次scan共用同一講解段落、輸出前綴正確、NUL停止及時間軸連續。原型狀態測試、文字框檢查與MP4完整解碼結果保存在產物目錄的 `verification.json`。

這仍是獨立原型。舊 `prepare_models.py` 用來保留首版製作方法；其一格一句的契約不應作為新版講解生成方式。正式接入時應由完整講解與視覺事件建立契約，不應要求每個動畫事件都附獨立旁白。
