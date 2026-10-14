# videomaker

把教材變成教學影片。一份 markdown 進去，約三分鐘出一支 1080p 影片——
投影片、講稿、配音、動畫、字幕全自動。

```bash
.venv/bin/python video_engine/run.py video_engine/materials/c_struct.md --sec 110
```

## 多模態教材工作台（Phase 2）

在專案根目錄執行：

```bash
.venv/bin/python serve.py 8899
```

開啟 `http://127.0.0.1:8899/`。上傳 `.md`、`.txt` 或 `.pptx`，用自然語言描述需求，
先檢視免費的規則式製作計畫，再按「確認並開始生成」。可選「微課程影片」或「線上簡報」。
影片保留八階段進度、講稿審核、播放與 MP4 下載；線上簡報顯示三階段進度與逐頁預覽，
核可後可下載由同一份內容製成的原生可編輯 PPTX，內含講者備忘稿。舊展示頁保留在
`http://127.0.0.1:8899/legacy`。

兩種產物生成都會呼叫既有 LLM；只有影片需要 GPT-SoVITS 本機語音服務。
規則式計畫預覽本身不呼叫付費服務。簡報接受 3–12 頁、五種版型（重點、程式碼、比較、流程、概念圖），
每頁引用須出現在上傳教材中；這是來源定位驗證，教學內容仍需人工核對。
直接選「可編輯 PPTX」能力尚未開放，請先選「線上簡報」，核可後下載 PPTX。
工作狀態、簡報內容與計畫存放在伺服器記憶體，重啟後會清除；產物請在關閉服務前下載。
BridgeAI 與使用者提供的 AI 規劃 API 尚未接入，現階段只有規則式規劃。
Phase 2 的自動測試使用假 LLM；真實簡報生成的內容品質與各裝置視覺驗收仍需實測。

2026-10-02 新增生成用量區：每次工作分開顯示本次生成及教材 AI 整理累積的實際
input／output／thinking tokens、模型呼叫明細與估算 USD 費用；重用整理素材不重複計費。
有用量回報的失敗、截斷與重試均計入，供應商未回報時標示未知或已知小計。
費用按官方付費單價估算，非帳單實扣；未知模型不猜價格。統計與工作狀態同樣在
伺服器記憶體中，重啟後清除，舊工作不能補出未保存的用量。

新生成簡報採 Deck 1.1：供學生自讀，每頁附可見重點解釋，依內容選擇版型，
概念圖與流程在 PPTX 中保留原生可編輯圖形。既有 Deck 1.0 仍可預覽／匯出。
離線樣本與驗收見 [`docs/experiments/2026-10-02-demo-usage-self-study.md`](docs/experiments/2026-10-02-demo-usage-self-study.md)。

主要 API 為 `/api/studio/session`、`/catalog`、`/sources`、`/plans`、`/jobs` 與
`/artifacts`；所有變更請求需帶 session 回傳的 `X-Studio-CSRF`。完整契約見
[`docs/superpowers/specs/2026-09-23-multimodal-learning-studio-design.md`](docs/superpowers/specs/2026-09-23-multimodal-learning-studio-design.md)。

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
* 教材可以是 `.md`、`.txt`、`.pptx` 或 `.pdf`（PPTX 抽文字與備忘稿；PDF 按頁抽取）
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
├── storyboard.py       審稿分鏡表（排在語音合成前，改稿不用重跑 TTS）
├── synth.py            語音合成 + 驗收重試
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
| 用哪個模型 | `video_engine/llm.py`，或 `VIDEO_ENGINE_LLM=google:gemini-3.8-flash` |
| 動起來好不好看 | `video_engine/render_video.py` 的緩動與時長常數，規格見 [`docs/MOTION_SPEC.md`](docs/MOTION_SPEC.md) |

架構全貌見 [`docs/ARCHITECTURE.html`](docs/ARCHITECTURE.html)，接手看 [`docs/NEXT_STEPS.md`](docs/NEXT_STEPS.md)，
動態規格（緩動曲線、時長分級、效果語彙的存廢判定）見 [`docs/MOTION_SPEC.md`](docs/MOTION_SPEC.md)。


新影片風格的獨立測試入口：`/paper-video-test`，可填期望片長的最短／最長分鐘（預設3–5）。範圍用於規劃，實際片長由語音量測。環境建立試片已交付285.79秒1080p有聲MP4；本片包含本機補稿及兩段語音重製，尚不能宣稱任意教材全自動成功。[用量、耗時與驗收紀錄](docs/experiments/2026-10-02-environment-paper-video.md)。


2026-10-03：紙上動畫測試已接入通用A＋C動態（描線、飛值、掃描／逐次輸出、短程式提示），字幕取完整旁白。新測試服務8913，仍屬使用者試生成驗收階段。[免費效果對照與驗收](docs/experiments/2026-10-03-ac-motion-restoration.md)。
