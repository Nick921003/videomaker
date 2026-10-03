# A＋C 紙上字串教學影片（2026-10-01）

## 交付

最終影片：`/home/pjw92/projects/videomaker/video_engine/out/state_change_ac_20261001/c_string_ac.mp4`

Windows：

```text
\\wsl.localhost\Ubuntu\home\pjw92\projects\videomaker\video_engine\out\state_change_ac_20261001\c_string_ac.mp4
```

H264、1920×1080、24 fps，影片41.125秒，AAC單聲道32kHz旁白41.120秒；2,737,045 bytes。附同目錄 `preview.gif`、`contact_sheet.png`、`subtitles.srt` 及有聲播放來源 `movie.html`／`master.wav`。

## 使用者選擇與實作

- 使用者選擇A的紙上連續過程＋C的程式走讀，要求完整有聲MP4；指出A原結尾拉遠時上方空白。
- 保留長方格紙、鉛筆描線、同一陣列持續改變及跟隨鏡頭。在讀取開始時呈現側邊程式提示，陣列先移到右方；提示完全退場後，陣列才回到中央。
- 結尾移除原overview鏡頭，固定在完整的容量32／長度5／至少6格比較圖。
- 沿用已接受的自然講解，不逐格播報索引。五個讀取事件共用一段旁白。
- 重用實際Gemini整理、Claude四場景分鏡與口語稿。合體模板、結尾修正與音訊時間映射是本機編排，沒有冒稱新Claude生成。

## 旁白與同步

四段本機王老師3.0 TTS已於交接前完成，每段一次；此次重用，沒有再次生成。Alice僅在TTS輸入改成愛麗絲，字幕仍顯示Alice。

| 段落 | 全片旁白時間 | WAV音長 |
| --- | --- | ---: |
| 問題與容量／長度 | 0.35–8.71秒 | 8.36秒 |
| 複製字串與結束字元 | 9.36–17.88秒 | 8.52秒 |
| 讀取與停止 | 19.98–29.37秒 | 9.39秒 |
| 整理比較 | 30.02–39.89秒 | 9.87秒 |

合成音軌41.14秒，包含開頭、場景銜接及結尾停留。s1原音有4.48秒內部長靜音，原WAV保留；已確定性縮短此異常空白，正常句讀保留。

既有Whisper large-v3以CPU逐WAV核對內容與詞時間，保存原ASR及詞彙提示複核。動畫時間採單調映射；字幕按語句錨點切換。停止字「停」位於s3局部5.32秒，加全片起點19.98，得到25.30秒；瀏覽器25.299仍未停止、25.30首次停止。24fps第一個對應畫格約25.333秒，量化誤差約33毫秒，相對ASR錨點。

ASR仍有同音誤辨與「程式」漏詞，不是逐音素認證；未宣稱人工聽感或學生理解成效已驗收。容器音／畫長度差0.005秒與語句／動作對齊是不同檢查，未混為單一同步指標。

## 實際驗證

- 主代理確認合成音軌各段取樣與已生成WAV一致，時間映射單調、十一條字幕連續。
- 本機ASR共158個詞時間核對音長與順序；原文、候選及複核保留。
- 獨立瀏覽器驗收104／104通過：相同時間正反seek像素一致，paused RAF不重設畫面，輸出只為Alice前綴，游標不超過索引5。
- 程式面板／游標／標籤的55筆退場重疊已修正；比較數字等待鏡頭安定才顯示。最後34–41.14秒每0.01秒抽樣，鏡頭恆為comparison，不再拉到空紙。
- 匯出1080p向量／文字重繪，實際MP4抽取7個關鍵畫面，主代理檢視程式卡、停止與結尾。
- FFprobe確認H264＋AAC；全片FFmpeg解碼exit0、stderr空；音畫容器時長差0.005秒。
- 全套unittest337項通過（1略過）；git diff --check通過。保留既有dirty worktree，未commit／push。
- Windows PowerShell已確認MP4可存取。原A／B／C樣本未修改；首版匯出與問題截圖保留為draft1。

最終MP4 SHA256：`e83f141067b37137e4c15ef6007653d47270e9058554782ed1ec2ff309fc7bb7`

## Tokens

- 此次接續、合體、同步、匯出新增Claude／Gemini API tokens：**0**。
- 本支使用的來源整理2,097＋口語稿3,795＋四場景分鏡7,945，素材歸屬核算 **13,837 tokens**，含重用素材；非每支影片固定用量。
- 所有先前試驗外部模型累計 **32,053 tokens**，包含截斷／重試，此次未增加。
- 本支旁白使用 **4次本機TTS**；本輪重用，新增0次。Whisper本機推論與影片渲染不列入Claude／Gemini API tokens。

## 檔案與重現

`prototypes/state_change_pilot/align_ac_audio.py`：ASR與原詞時間；`build_ac_movie.py`：主音軌、時間映射、字幕、有聲HTML；`ac_movie_overrides.js`：A＋C圖形、結尾與音訊播放；`export_ac_video.py`：Canvas至1080p MP4。

產物目錄：`video_engine/out/state_change_ac_20261001/`。

- `tts_usage.json`、`audio/`：四段已完成語音，不應重新付費／生成。
- `asr.json`、`asr_vocabulary_recheck.json`、`asr_alignment_notes.json`：原始與複核證據。
- `movie_timeline.json`：41.14秒實測排程與錨點；`subtitles.srt`：字幕。
- `browser_qa/ac_browser_checks.json`：104項檢查、HTML hash與截圖。
- `export_validation.json`：媒體metadata、完整解碼、MP4 hash與抽幀。

此仍是獨立原型，尚未接入正式八階段／Studio流程。此支已完成交付，下一輪可依使用者觀看回饋調整質感，不需重做來源整理。
