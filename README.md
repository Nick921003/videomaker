# videomaker

把教材變成教學影片。一份 markdown 進去，約三分鐘出一支 1080p 影片——
投影片、講稿、配音、動畫、字幕全自動。

```bash
.venv/bin/python video_engine/run.py video_engine/materials/c_struct.md --sec 110
```

## 這是怎麼運作的

三層契約，各層只透過 JSON 溝通，所以換教材不用改程式碼：

| 層 | 檔案 | 誰產 | 禁止出現 |
| :--- | :--- | :--- | :--- |
| 內容 | `lesson.json` | LLM | 座標、時間 |
| 編排 | `actions.json` | LLM | 座標、秒數 |
| 幾何 | `layout.json` | 繪製器自動 | 手改 |

動作只寫語意代號（`p3_code:L4-L6` 指程式碼第 4 到 7 行、`p1_fig:l2` 指示意圖左欄第二格），
座標在編譯期查表得到。時間全部來自實測音檔長度，**沒有任何手寫時間碼**。

兩道驗證閘擋品質：編排閘檢查動作密度、target 能不能解析、講稿有沒有直接唸函式名；
語音閘檢查異常靜音與 AR 失控。不合格自動重生。實測四家 LLM 接上驗證閘後產出收斂到同一水準——
**決定品質的是驗證閘，不是模型**。

## 需要什麼

* **Python 3.10+**、**FFmpeg**、**Noto Sans CJK** 字型
* 教材可以是 `.md`、`.txt` 或 `.pptx`（`.pptx` 走 `python-pptx` 抽文字與講者備忘稿）
* **一個 GPT-SoVITS 服務**跑在 `:9880`，提供聲音克隆。它是獨立專案，本專案只透過 HTTP 呼叫，
  端點與參考音訊寫在 `.env`（見 `.env.example`）
* **一把 LLM 金鑰**（Anthropic／OpenAI／Google 任一，或本機 OpenAI 相容端點）

```bash
uv venv .venv && uv pip install --python .venv/bin/python \
  numpy scipy pillow fonttools anthropic google-genai openai python-pptx
```

## 目錄

```
video_engine/
├── run.py              一行指令跑完八個階段
├── generate_lesson.py  教材 → lesson.json（LLM）
├── render_slides.py    畫投影片，順便量測每個元素落點
├── generate_actions.py lesson → actions.json（LLM，內含驗證閘）
├── validate.py         編排驗證閘
├── synth.py            語音合成 + 驗收重試
├── storyboard.py       出片前的審稿分鏡表
├── compile_timeline.py 時間軸 + 字幕
├── render_video.py     逐格合成 + FFmpeg 封裝
├── prompts/  schema/  themes/  materials/  examples/
docs/                   架構文件、接手指南、踩坑筆記
patches/                對 GPT-SoVITS 的修改備份（中英分段對齊前端）
```

## 改東西改哪裡

| 想改 | 改這裡 |
| :--- | :--- |
| 配色、效果顏色 | `video_engine/themes/warm.json` |
| 講稿風格、動作規則 | `video_engine/prompts/slide_actions.system.md` |
| 投影片結構規則 | `video_engine/prompts/lesson_content.system.md` |
| 什麼算不合格 | `video_engine/validate.py`（比改 prompt 有效，模型會被打回重做） |
| 用哪個模型 | `video_engine/llm.py`，或 `VIDEO_ENGINE_LLM=google:gemini-3.7-flash` |
| 動起來好不好看 | `video_engine/render_video.py` 的緩動與時長常數，規格見 [`docs/MOTION_SPEC.md`](docs/MOTION_SPEC.md) |

架構全貌見 [`docs/ARCHITECTURE.html`](docs/ARCHITECTURE.html)，接手看 [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md)，
動態規格（緩動曲線、時長分級、效果語彙的存廢判定）見 [`docs/MOTION_SPEC.md`](docs/MOTION_SPEC.md)。
