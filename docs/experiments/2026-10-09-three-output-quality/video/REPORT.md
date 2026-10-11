# 影片固定基準、外部候選與共同規劃接點

日期：2026-10-09。這是可播放的 renderer 固定 fixture，未呼叫 LLM／TTS、未安裝依賴、未 commit／push。不是本輪 AI 自動生成或使用者視覺驗收完成的證據。

## 可直接 review 的產物

- [比較播放器](../../../../prototypes/three_output_quality/video/index.html)：切換 A、B、白板與文字候選，含片頭、兩次換場、程式／變數／結果、邊界與片尾快捷跳轉。
- [A 保存基準 MP4](../../../../prototypes/three_output_quality/video/out/A-original.mp4)：原檔副本，原稿保存在 `original.scene.json`。
- [B 同音檔 MP4](../../../../prototypes/three_output_quality/video/out/B-board.mp4)：69.666667 秒、1920×1080、24fps、1672 幀；原音訊維持不變。
- [B 交付音量版 MP4](../../../../prototypes/three_output_quality/video/out/B-delivery-normalized.mp4)：畫面 encoded-video SHA256 與 B 相同，另作 FFmpeg 響度處理。
- [白板候選 MP4](../../../../prototypes/three_output_quality/video/out/C-y3_whiteboard.mp4)、[文字候選 MP4](../../../../prototypes/three_output_quality/video/out/C-y5_kinetic_type.mp4)：各 13.458333 秒、323 幀、1080p、24fps，使用 A 開場相同兩句的音訊。
- [B 可拖曳播放器](../../../../prototypes/three_output_quality/video/out/B-player/player.html)、[外部候選可拖曳播放器](../../../../prototypes/three_output_quality/video/candidates.html)、[共同規劃 adapter 無聲播放器](../../../../prototypes/three_output_quality/video/out/shared-fixture-player/player.html)。最後一項是 39.77 秒估時，沒有相符配音，沒有套用邊界片舊音檔。

## 基準與配音身份

基準來自 `/tmp/videomaker-step1-preview-20261008/units/ecdc0848e6bb/q2`，原始教材和現存 `video_engine/materials/c_loop.md` 是同一個 C 迴圈題材；本片聚焦 `<`／`<=` 與起點、最後有效值，不宣稱涵蓋教材所有主題。保存的產品紀錄日期為 2026-10-04。

12 句保存配音的 `narration.text` 全部與原稿 `say` 相同，但原稿 5 句 `spoken` 已有後續修改。原稿完整保留；`reconciled.scene.json` 明示把 `spoken` 對回保存配音文字。B 再從核對稿做固定編排。原產物是否全部由模型生成，不能由本次保存資料證明；本輪所有適配與編排均標為固定 fixture。

逐句 WAV 加上原 renderer 的 lead-in、句間／換場停頓，可逐樣本重建 master PCM，完全相同。12 個 WAV、narration 與 timing 原檔另保存在 `out/saved-voice/`，不只留下 `/tmp` 引用。`identity.json` 保存 master、timing、逐句 WAV 的 SHA256、完整配音文字與既有 ASR 結果。保存資料可識別 Gemini TTS、速度 0.95 與模型 `gemini-3.8-flash-tts`；聲線名稱缺少可靠保存值，明示 unknown，未補猜測。

身份閘拒絕同句數的不同講稿、不同音檔、不同 timing；正反控制見 [identity-controls.json](../../../../prototypes/three_output_quality/video/out/identity-controls.json)。這驗證實際播放資料相符，不代表保存的 ASR 每個中文字都無誤。舊 ASR 有「差一／差異」「減／-」等辨識差異，仍需聽感驗收。

## B 對照與量測

B 沿用 Board 的 `code`、`vars`、`output`、`pipeline`，新增「1 + 2 + 3 + 4 + 5 = 15」結果卡與「先看起點 → 確認最後值 → 選擇條件」流程。原基準在「如果寫小於等於五」時仍圈正確的 `i < 5`；B 改為明示錯誤 `i <= 5`，講到修正時再還原 `<`。這是相同講稿／配音的編排改善對照，不是只有配色改變的純風格 A/B。

動作改採保存的句界，移除字元位置比例 cue。句界由實際逐句 WAV 長度、保存的裁切 padding 與 master 的樣本放置核對；没有音素或詞級強制對齊資料，不能宣稱關鍵詞誤差 ≤200ms。24fps 句界 cue 的影格排程量化上限為 38.33ms，這是排程量化，並非詞級同步誤差。

| 檢查 | 實際結果與證據 |
| --- | --- |
| 越界、重疊、鏡頭／seek | B 81 個既有閘取樣通過；[check.json](../../../../prototypes/three_output_quality/video/out/B-player/check.json) |
| 文字 | A 最小 23.29px → B 最小 28.17px；字幕 40px；小字目標取樣無低於 28px。`B-typography-adaptation.json` 列出 runtime 副本的字級／標籤高度適配，正式 renderer 未修改 |
| 缺字 | 實際本機 Noto Sans CJK TC cmap 覆蓋 B fixture 和候選文字，缺字 0；字體檔 SHA256 存在量測紀錄，字體授權存於 vendor |
| MP4 | B 1672 幀，完整解碼 exit 0，AAC 音軌存在；[export.json](../../../../prototypes/three_output_quality/video/out/B-board.export.json)、[probe.json](../../../../prototypes/three_output_quality/video/out/B-probe.json) |
| 音訊結尾 | 最後保存旁白句界 68.46s，音軌長 68.71s，影片長 69.666667s，音軌保留 250ms、畫面保留 1.206667s；沒有為 `-shortest` 截掉尾端 |
| 響度 | 同音檔 B：−18.22 LUFS、−0.91 dBTP，未達目標；另出的交付版：−16.29 LUFS、−1.19 dBTP，達 −16 ±0.5、≤−1 目標。量測的是最終 AAC，未拿 FFmpeg 預測 output 欄位冒充成片值 |
| 交付版畫面相同 | 最終兩 MP4 video stream SHA256 相同，精確值見 `delivery-check.json:encoded_video_sha256` |
| 播放器 | Chromium MP4 `readyState=4`、無 media error；375／768／1440px 無橫向溢出，保存在 `player-*.png` |

[B-measurements.json](../../../../prototypes/three_output_quality/video/out/B-measurements.json) 保存 A／B 相同方法的最小字級、逐項框、時刻與字體身份；[delivery-check.json](../../../../prototypes/three_output_quality/video/out/delivery-check.json) 保存端點與交付量測。

片頭 2s、第一換場前後 13.6／15.5s、程式焦點與結果 24.5／26.5s、第二換場前後 29.1／31.2s、陣列邊界 43s、片尾 67.3／69.6s 的實際 PNG 和 frame JSON 已保存，並已檢視。B 換場起點為 13.87、29.48、40.04、47.53、52.92s，各比新章旁白早 0.5s；不要把此提前量當成已達章節端點 ≤200ms。畫面單焦點、停留與旁白是否自然，仍由使用者 review。

## 外部來源：讀 source 並真正試跑

選擇的是可參數化的動畫元件，而非只讀 README 或引用作者形象。固定 source、SHA256 與 MIT 授權存於 [vendor/sources.json](../../../../prototypes/three_output_quality/video/vendor/sources.json)。未導入作者角色圖、筆順資料或外部字體包。

| 來源與固定版本 | 閱讀／採用內容 | 本輪接法與限制 |
| --- | --- | --- |
| [Motion Canvas 官方 Code 文件](https://motioncanvas.io/docs/code/)，[Code.ts](https://github.com/motion-canvas/motion-canvas/blob/7b91435c301d530351dcf5ebb91dd139c002e405/packages/2d/src/lib/components/Code.ts)，commit `7b91435c301d530351dcf5ebb91dd139c002e405` | `selection`、行／range、selection bounding box；程式碼內容與選取動作分開 | 借用語意行選取作接點：共同規劃 1 起的 `line` → Board `highlight`。未安裝 Motion Canvas，未宣稱執行其引擎或具 C parser |
| 花叔，[clip.js](https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/scripts/engine/clip.js)，commit `57d67608ab458f57d9b153b1a2831b921e22498b` | `duration/fps/data/cues`、cue 在所在影格揭示、safe area，純 `draw(c,t,ctx)` | 本機 wrapper 沿 cue、safe 與純 seek，固定本機 TC 字體別名；未使用外部 boot 的 XHR／eval 載入路徑 |
| 花叔，[y3_whiteboard.js](https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/scripts/engine/clips/y3_whiteboard.js)、[y5_kinetic_type.js](https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/scripts/engine/clips/y5_kinetic_type.js) | 白板文字寫入、筆與累積版面；文字主句／輔句揭示與換頁 | 直接執行保存 grammar 與必要 utils。各 323 幀可見文字越界 0、字幕 42px、逆序 seek 像素相同；無法由這個短片升格為任意教材能力 |
| 花叔，[render.py](https://github.com/alchaincyf/huashu-art-motion/blob/57d67608ab458f57d9b153b1a2831b921e22498b/scripts/engine/render.py) | 瀏覽器逐格擷取與 FFmpeg 匯出 | 使用 repo 環境的本地 exporter，檢查退出碼、幀數、解碼與音訊結尾；不直接信檔案存在 |
| 岚叔，[v3-notebook/kit.js](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/c24720a85d63b1bd494f6447e48a59384733647b/explainer/kits/v3-notebook/kit.js)，commit `c24720a85d63b1bd494f6447e48a59384733647b` | `stroke/write` 以 at/dur 編排，pure `render(t)`，固定種子幾何 | 採樣式／內容／時間分層與同一純 seek 檢查；本輪未執行岚叔 kit，不把它列成已支援影片元件 |
| 岚叔，[story.py](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/c24720a85d63b1bd494f6447e48a59384733647b/explainer/tools/story.py)、[finalize_delivery.sh](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/c24720a85d63b1bd494f6447e48a59384733647b/scripts/finalize_delivery.sh) | 自備音訊的句界／詞權重估算、逐句快取與解碼／響度量測 | 沿用現有 Gemini 保存音訊，借交付檢查；沒有把詞權重估算當實測詞時間，未呼叫 MiniMax |

文字候選原長標題的 spring 曾在 0.583333s 溢出 2.67px，全幀量測抓出後，改為等義的「＜ 或 ≤？」並重匯出。採參數化內容修正，不改外部 source 或把溢出裁掉冒充通過。

外部候選已補四角 transform 的可見文字 AABB instrumentation。筆、圈、其他裝飾 path 尚未提供完整 geometry／碰撞檢查，故白板／文字兩者仍為實驗候選，未接預設生成。這是 source 加本機 fixture 幀的觀察，未聲稱已分析外部影片的實際 timecode。

## 共用教學規劃接點與能力

`prototypes/three_output_quality/video/teaching_adapter.py` 的 `adapt_units(plan)` 回傳 `(scene, source_map)`。不重寫教學規劃；完整保留每個 unit 的來源引文、unit id 與選擇理由。模型不提供像素與實測時間。旁白與 timing 另走身份核對。

| 教學規劃適用對象 | Board 元件／動作 | 本輪實證與容量 |
| --- | --- | --- |
| `walkthrough` 的程式執行位置 | `code` → `highlight`，1 起行號 | 共同 `trace` 5 行、6 個狀態；最後聚焦第 5 行。無效行號先拒絕 |
| 同一步驟的具名變數快照 | `vars` → 每變數 `set`，同拍並行 | 共同 `trace` 的 i／sum；變數名稱與順序須一致，不自行產生新值 |
| 執行後能觀察的輸出 | `output` → `set` | 共同 `trace` 最終輸出 15；完整配音 B 另展示總和結果 |
| 有先後關係的操作／檢查步驟 | `pipeline` → `step` | 共同 `problem`、`termination` 各三步；目前 adapter 明確限 1–4 步 |
| 概念、比較、回顧 | 尚未驗收此 video adapter | `concept/compare/bullets/code` 明確拒絕，不靜默變成條列；既有 Board 原始場景仍可使用其他元件 |

共同 fixture 使用 `tests/fixtures/teaching_quality.py:sample_plan()`，只取本批已支援的 problem／trace／termination，完整規劃仍由主工作流保存。無聲播放器的 70 個閘取樣通過，來源保持、最後輸出／行焦點，以及同資料的無效行號／未知元件反向控制通過。[shared-fixture-verification.json](../../../../prototypes/three_output_quality/video/out/shared-fixture-verification.json)。這是明示的三單元子集，不是完整 seven-unit plan 已接入影片。

尚未驗證任意長程式、過多變數、長輸出的一般化可讀性；適配後必須跑實際 `check.py`。共同 fixture 最後的 i 欄位包含狀態文字，不可把它當 C `int` 的真實數值；`for(int i...)` 離開迴圈後 i 已離開作用域。

## 精確重現命令

在 repo 根目錄執行。`prepare.py` 只讀保存目錄，寫隔離 out；保存來源不存在時會直接失敗，不自動生成旁白。

```bash
.venv/bin/python prototypes/three_output_quality/video/prepare.py
/home/pjw92/.local/share/pipx/venvs/webwright/bin/python video_engine/board/check.py prototypes/three_output_quality/video/out/B-player
/home/pjw92/.local/share/pipx/venvs/webwright/bin/python prototypes/three_output_quality/video/measure.py
/home/pjw92/.local/share/pipx/venvs/webwright/bin/python video_engine/board/export.py prototypes/three_output_quality/video/out/B-player prototypes/three_output_quality/video/out/B-board.mp4 --fps 24 --workers 2
ffmpeg -hide_banner -loglevel error -y -i prototypes/three_output_quality/video/out/audio.wav -t 13.42 prototypes/three_output_quality/video/out/candidate-audio.wav
/home/pjw92/.local/share/pipx/venvs/webwright/bin/python prototypes/three_output_quality/video/export_candidates.py
/home/pjw92/.local/share/pipx/venvs/webwright/bin/python prototypes/three_output_quality/video/measure_candidates.py
.venv/bin/python prototypes/three_output_quality/video/verify_adapter.py
/home/pjw92/.local/share/pipx/venvs/webwright/bin/python video_engine/board/check.py prototypes/three_output_quality/video/out/shared-fixture-player
ffmpeg -hide_banner -v error -xerror -i prototypes/three_output_quality/video/out/B-board.mp4 -f null -
ffmpeg -hide_banner -i prototypes/three_output_quality/video/out/B-board.mp4 -af loudnorm=I=-16:TP=-1:LRA=11:print_format=json -f null -
ffmpeg -hide_banner -loglevel error -y -i prototypes/three_output_quality/video/out/B-board.mp4 -map 0:v:0 -map 0:a:0 -c:v copy -af loudnorm=I=-16:TP=-1.5:LRA=11 -c:a aac -b:a 160k -movflags +faststart prototypes/three_output_quality/video/out/B-delivery-normalized.mp4
ffmpeg -hide_banner -i prototypes/three_output_quality/video/out/B-delivery-normalized.mp4 -af loudnorm=I=-16:TP=-1:LRA=11:print_format=json -f null -
ffmpeg -hide_banner -v error -xerror -i prototypes/three_output_quality/video/out/B-delivery-normalized.mp4 -f null -
.venv/bin/python prototypes/three_output_quality/video/verify_delivery.py
git diff --check -- prototypes/three_output_quality/video docs/experiments/2026-10-09-three-output-quality/video
```

不需要啟動 TTS／LLM 服務，也不需要新套件。觀看可直接開 `index.html`，或由 repo 根目錄以 `.venv/bin/python -m http.server 8765 --bind 127.0.0.1` 提供，開啟 `http://127.0.0.1:8765/prototypes/three_output_quality/video/index.html`。大螢幕實際可讀性、聽感與教學自然度仍待使用者 review；本批沒有改網站預設生成或正式 renderer。
