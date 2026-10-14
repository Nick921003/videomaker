# 桌面版交接：A＋C 教學動畫含 TTS

> **接續完成更新：** 本交接下方是當時快照，尚未完成項目已於後續完成。最終有聲影片為 `video_engine/out/state_change_ac_20261001/c_string_ac.mp4`（41.125秒、1080p、約2.74MB），含A＋C融合與結尾空白拉遠修正。四段音檔重用，新增外部API tokens 0。詳見 `docs/experiments/2026-10-01-ac-narrated-video.md`；不應重新生成TTS或覆寫已交付影片。

工作目錄：`/home/pjw92/projects/videomaker`

接手目標：以使用者喜歡的 A 紙上連續動畫為主體，融入 C 的程式走讀，製作單獨、完整、有自然旁白的 MP4。修正 A 結尾拉遠後上方空白的設計問題。先保留所有既有產物與未提交工作；不要重新呼叫已完成的四段 TTS。

## 1. 可開啟的 HTML 完整路徑

Linux／WSL：

```text
/home/pjw92/projects/videomaker/video_engine/out/state_change_scenes_20261001/scene_samples.html
```

Windows（已由 Windows PowerShell 確認可存取）：

```text
\\wsl.localhost\Ubuntu\home\pjw92\projects\videomaker\video_engine\out\state_change_scenes_20261001\scene_samples.html
```

這是單一 HTML，內含 A／B／C 三個可切換的 44 秒無聲樣本，不是最終有聲影片。CSS、JavaScript、分鏡與字幕均內嵌；可播放、暫停、拖曳進度，切換樣本保留時間。

靜態比較：`/home/pjw92/projects/videomaker/video_engine/out/state_change_scenes_20261001/samples_preview.png`

## 2. A／B／C 的差異

| 方案 | 呈現方式 | 適合的教學任務 |
| --- | --- | --- |
| A：紙上連續動畫 | 奶油色長方格紙、鉛筆描線、同一陣列沿過程移動，鏡頭跟隨形成／讀取／停止／比較 | 讓學生看見概念的連續變化與因果 |
| B：鏡頭聚焦講解 | 簡潔底面，依段落聚焦當下圖形，前一段資訊退場 | 解釋單一概念、降低同時可見資訊 |
| C：概念與程式走讀 | 在讀取開始時用側邊程式提示，之後讓程式退場，把焦點交回字串狀態與輸出 | 建立程式與資料變化的對應 |

三者共用同一份教材、口語字幕和一次 Claude 四場景分鏡；具體 Canvas 變體由本機實作，不是三次獨立 Claude 生成。

## 3. 使用者已作出的決定與回饋

- 教材的實際使用者是學生；AI 應先讀教材、挑概念與例子，學生不需要先寫教學重點、迷思或動畫分鏡。
- 咖啡動畫 prompt 是風格與過程呈現的參考，不是要製作咖啡影片，也不要求照搬其直向尺寸或22秒。
- Gemini 負責整理教材；Claude 負責講解及動畫狀態、因果與分鏡。
- 不喜歡旁白逐格說第一格、第二格、第三格；同一句自然講解可以配合多個動畫事件。字幕修訂後，使用者回饋文字有改善。
- 畫面不應把完整程式碼、陣列、輸出和計數永久擠在同一頁；可依教學目的使用不同場景模板。
- 最初很喜歡 A，要求將它單獨做成完整影片並加入 TTS；最新偏好是 **A＋C 合體**。這是接手時的最新方向。
- 指出 A 結尾拉遠後「上方空白、下方有東西」很怪，詢問是否設計錯誤；此問題尚未在既有 HTML 中修正。
- 要知道影片製作的 tokens 用量，須記錄真實 API usage，區分當輪新增、素材歸屬與所有試驗累計。
- 已授權使用子代理，以及環境變數中的 Claude／Gemini API。正常製作所需模型／TTS 可執行；若失敗需額外付費重試，要先診斷與告知。遇到需使用者決定的問題先問，不要自行追加付費重試。
- 最後要求切換到桌面版，先整理交接；目前只完成交接，不繼續渲染。

## 4. 助理的建議／已承諾的修正（勿當成使用者逐項指定）

- A 的結尾問題原因：比較段的鏡頭39.5秒切到 overview，但前面問題、字串來源等物件已經退場；鏡頭拉遠只剩下方陣列與比較圖，上方沒有足夠回顧內容。
- 建議移除這段沒有有效內容的 overview，結尾停在清楚、完整的容量／長度比較畫面。尚未實作；若保留拉遠，應先補上真正的過程回顧內容，不能只有空紙。
- 建議 A 為整支影片的視覺主體，在「執行程式」時加入 C 的程式提示；提示退場後回到 A 的連續資料動畫。不是把 A 和 C 各自整段直接拼接。
- 沿用已接受的自然字幕，依真實 WAV 與 ASR 詞時間安排動作、字幕和鏡頭；不要把新旁白硬塞進原44秒。
- 規劃輸出1920×1080、24 fps、有聲MP4，附GIF／靜態預覽與驗收紀錄；1080p為助理選擇，使用者未指定解析度。

## 5. 已完成與已驗證

### HTML 三樣本

- 完成四場景：問題0–7、形成7–16、讀取與停止16–31、比較31–44秒。
- 真實新增一次 Claude API 回應：`claude-opus-5-5`，四場景規格、顯示／隱藏物件、事件、鏡頭語意目標、來源引文均已保存。
- 已以 Chrome／CDP 完成113項檢查，0失敗，包含 seek 決定性、正反向 seek、NUL停止、樣本切換、播放控制及頁面無溢出。
- 已修正原 HTML 的游標遮標籤、鏡頭過場比較數字裁切、提前顯示半個空輸出框；實際PNG與初版證據保存。**這些修正不等於已修正最新指出的空白 overview 設計問題。**
- 全套 unittest337項通過（1項略過）；git diff --check通過。
- 375px沒有水平溢出，但Canvas等比例縮小後字體偏小；尚未驗證手機閱讀便利性或學生理解成效。

### A＋C 有聲版的語音

已生成四段本機王老師3.0 TTS，每段一次，沒有新增外部 LLM 呼叫。字幕保留 Alice，僅TTS輸入使用「愛麗絲」。主代理已讀取實際WAV核對長度與ledger一致：

| 段落 | 可用音檔（相對A＋C輸出目錄） | 秒數 | 狀態 |
| --- | --- | ---: | --- |
| s1 | audio/s1_74559b26b7d4_pause_clean.wav | 8.36 | 原音含4.48秒內部空白；保留原音，確定性縮短異常靜音，修整版通過品質檢查 |
| s2 | audio/s2_688e69dfd2c2.wav | 8.52 | 通過音長／靜音／峰值檢查 |
| s3 | audio/s3_509f634828bc.wav | 9.39 | 通過音長／靜音／峰值檢查 |
| s4 | audio/s4_ea4769cb274d.wav | 9.87 | 通過音長／靜音／峰值檢查 |

音訊合計36.14秒，尚未加轉场停頓。**ASR內容核對、詞時間同步和人工聽感尚未完成。** 不要把「音長／峰值檢查合格」當成旁白語意與同步已驗證。

語音目錄：`/home/pjw92/projects/videomaker/video_engine/out/state_change_ac_20261001/audio/`

語音紀錄：`/home/pjw92/projects/videomaker/video_engine/out/state_change_ac_20261001/tts_usage.json`

### 匯出器

- 已新增 `prototypes/state_change_pilot/export_ac_video.py`，完成語法解析與 `--help`，尚未實際渲染。
- 匯出器使用CDP讀取 `window.renderMovie(realSeconds)`，Canvas向量／文字以1.5倍重繪為1920×1080，再由FFmpeg合成H264＋AAC。
- 需要 `movie.html` 提供 `window.sourceCanvas` 或 `id=sourceCanvas`；目前這個有聲版HTML還未建立。

**尚不存在**：A＋C `movie.html`、`movie_timeline.json`、`master.wav`、`c_string_ac.mp4`。不要宣稱最終影片已完成，也不要把舊有聲字串MP4當成A＋C成品。

## 6. 下一步（建議順序）

1. 讀本交接與 `CLAUDE.md`、`docs/VIDEO_DESIGN_STATUS.md`，檢查git status，保留dirty worktree。可重用既有Gemini整理、Claude分鏡、字幕及四段新WAV；不重新付費生成。
2. 由已驗證 `scene_samples.html` 建立獨立A＋C `movie.html`：保留A紙張／描線／跟隨鏡頭，加入C程式提示與資料對應；修正結尾空白overview。原三樣本保留。
3. 用既有Whisper large-v3快取逐段辨識新WAV，核對完整語句及「從開頭」「遇到結束字元」「長度」「至少六格」等錨點。不要再按索引拆旁白。
4. 合成 `master.wav`，建立 `movie_timeline.json` 與字幕時間。可使用單調時間映射，把實際音訊時間對應到既有視覺事件，確保五次輸出在「遇到結束字元」前完成，並在NUL停住。
5. 實作 `window.renderMovie(realSeconds)`；可任意seek，畫面由指定時間決定。建立單獨HTML播放器或匯出來源，不把樣本切換UI燒進影片。
6. 先以實際Chrome檢查A＋C幾何、字幕、鏡頭及結尾；確認無上方空白回顧、游標遮字或比較數字裁切。
7. 啟動專用CDP Chrome後執行 `export_ac_video.py`，再FFprobe、全片解碼、擷取關鍵畫格、驗證語音同步。匯出GIF／靜態預覽，確認Windows可存取。
8. 完成A＋C製作報告及tokens/TTS ledger；更新設計狀態。未經使用者要求不commit/push或改正式架構。

## 7. 相關檔案

所有相對路徑均以 `/home/pjw92/projects/videomaker/` 為根。

| 路徑 | 用途 |
| --- | --- |
| CLAUDE.md | 專案契約與執行規則 |
| docs/VIDEO_DESIGN_STATUS.md | 歷次試片與驗收狀態 |
| video_engine/materials/c_string.md | 原教材；部分過度概括已記錄，勿直接照抄 |
| video_engine/out/state_change_pilot_20261001/normalized.md | 實際Gemini整理稿 |
| video_engine/out/state_change_natural_20261001/narrative_edited.json | 已接受、由Claude稿經本機編輯的四段自然字幕 |
| video_engine/out/state_change_natural_20261001/SCRIPT.md | 可讀字幕稿 |
| video_engine/out/state_change_scenes_20261001/scenes.json | 真實Claude四場景分鏡 |
| video_engine/out/state_change_scenes_20261001/claude_request.json / claude_response.json / claude_usage.json | 實際呼叫與tokens證據 |
| prototypes/state_change_pilot/scene_samples.html | 未嵌教材資料的三樣本模板 |
| prototypes/state_change_pilot/build_scene_samples.py | 嵌入模型規格／字幕，重建單一HTML；不呼叫模型或TTS |
| video_engine/out/state_change_scenes_20261001/browser_qa/browser_checks.json | 113項驗收與實際截圖索引 |
| docs/experiments/2026-10-01-progressive-scene-samples.md | 三樣本來源、分鏡、tokens與驗收紀錄 |
| video_engine/out/state_change_scenes_20261001/token_ledger_detailed.json | 五次外部呼叫與用量核算 |
| prototypes/state_change_pilot/synth_ac_audio.py | 本次四段語音生成，已完成；重跑會先讀既有ledger |
| prototypes/state_change_pilot/export_ac_video.py | 尚未實際執行的1080p影片匯出器 |
| video_engine/out/state_change_ac_20261001/ | 最終A＋C工作產物目錄，目前僅語音與ledger |

## 8. 用量與服務注意

- 最新外部模型新增：Claude四場景分鏡7,945 tokens。
- 本支所用Gemini整理、口語稿、四場景分鏡歸屬核算：13,837 tokens，包含重用素材；不是本輪新發生用量，也不是任何影片固定用量。
- 所有試驗外部模型累計：32,053 tokens，含首版截斷與重試。
- 本次加入TTS：新增外部模型tokens **0**，本機TTS **4次**；累計API tokens仍32,053。TTS與Whisper本機推論另記，不加入Claude／Gemini tokens。
- API金鑰在環境變數／專案 `.env`；不得把值搬進交接、Git或日誌。只需確認設定存在，不輸出值。
- 本機TTS使用9880。跨會話時服務是否仍存活必須重查，不可假設。啟動方式見 `docs/NEXT_STEPS.md`；權重維持王老師3.0。
- CDP9334是匯出器預設，**本輪尚未啟動這個專用瀏覽器**。既有QA用的9333已關閉，不可假設仍在。
- Python用 `.venv/bin/python`；Whisper使用既有 `/home/pjw92/.venvs/whisper-gpu/bin/python`，模型快取已存在，可CPU執行，不安裝新依賴。
- `/tmp`暫存與執行session跨環境不保證可用；以repo中實際檔案為交接證據。

## 桌面版可貼的接續指令

> 請在 `/home/pjw92/projects/videomaker` 接續，先讀 `docs/HANDOFF_DESKTOP_2026-10-01.md`。我要A紙上連續動畫＋C程式走讀的完整有聲MP4；修正最後拉遠上方空白的設計。四段TTS已生成，請重用，先做ASR核對與同步，再完成A＋C獨立HTML和影片匯出。保留dirty worktree與既有樣本；記錄本次新增及累計tokens，付費失敗重試先告知。可使用子代理。
