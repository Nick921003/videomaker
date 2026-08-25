# video_engine — 教材轉教學影片

一份 markdown 教材進去，一支 1080p 影片出來。取代 `../tts_lab/legacy/generate_v3_master_videos.py`。

```bash
.venv/bin/python video_engine/run.py video_engine/materials/c_struct.md --sec 110
```

約三分鐘。要先審講稿就 `--until storyboard`，看過再 `--from timeline` 續跑。

## 三層契約

內容、編排、幾何各有唯一作者，不得跨界。這是整個設計唯一要守的規矩。

| 層 | 檔案 | 誰產 | 禁止 |
| :--- | :--- | :--- | :--- |
| 內容 | `examples/*.lesson.json` | LLM | 座標、時間 |
| 編排 | `examples/*.actions.json` | LLM | 座標、秒數 |
| 幾何 | `out/<課程>/layout.json` | 繪製器自動 | 手改 |

動作只寫語意代號（`p3_code:L4-L6` 指程式碼行、`p1_fig:l2` 指示意圖左欄第二格），
座標編譯期查表得到。時間全部來自實測音檔長度，**沒有任何手寫時間碼**。

## 八個階段

| 腳本 | 做什麼 | 耗時 |
| :--- | :--- | ---: |
| `generate_lesson.py` | 教材 → lesson.json（LLM） | 15 秒 |
| `render_slides.py` | 畫投影片，順便量測每個元素落點 | 1 秒 |
| `generate_actions.py` | lesson → actions.json（LLM，內含驗證閘） | 20–45 秒 |
| `validate.py` | 編排驗證閘 | <1 秒 |
| `synth.py` | 語音合成＋驗收重試（GPT-SoVITS :9880） | 45 秒 |
| `storyboard.py` | 審稿分鏡表 | 1 秒 |
| `compile_timeline.py` | 時間軸＋字幕 | <1 秒 |
| `render_video.py` | 逐格合成＋FFmpeg | 45 秒 |

## 換模型

```bash
VIDEO_ENGINE_LLM=google:gemini-3.7-flash .venv/bin/python video_engine/run.py <教材>
```

沒設就用各階段預設（見 `llm.py`）：結構化 `claude-opus-5`、編排 `gemini-3.7-flash`。
LLM SDK 裝在獨立的 `.venv-llm`，避免 `google-genai` 連帶升級 pydantic 弄壞訓練環境。

## 改東西改哪裡

| 想改 | 改這裡 |
| :--- | :--- |
| 配色、效果顏色 | `themes/warm.json`（`dark.json` 是舊的深色） |
| 講稿風格、動作規則 | `prompts/slide_actions.system.md` |
| 投影片結構規則 | `prompts/lesson_content.system.md` |
| 什麼算不合格 | `validate.py`（改這裡比改 prompt 有效，模型會被打回重做） |
| 動畫的時長與曲線 | `render_video.py` 頂部常數 |

## 踩過的坑

聲音那三條硬規則（孤立片段、相對門檻失效、逐字母縮寫）寫在
[`../docs/bridgeai/PROJECT_NOTES.md`](../docs/bridgeai/PROJECT_NOTES.md) 與架構文件裡，違反會產生雜音。
