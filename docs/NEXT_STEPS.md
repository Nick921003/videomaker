# 接手指南

> 更新：2026-08-25　狀態：可全自動出片，使用者評「70 分」

換對話框後從這裡接。架構全貌看 [`ARCHITECTURE.html`](ARCHITECTURE.html)，
聲音踩過的坑看 [`PROJECT_NOTES.md`](PROJECT_NOTES.md)。

---

## 兩個專案，各管一件事

```
~/projects/videomaker/        ← 本專案。影音生產，推 GitHub
~/projects/GPT-SoVITS/        ← 聲音模型工廠。只在本機，不推
```

**本專案裡沒有 TTS 模型。** 王老師的權重（約 500 MB）在 GPT-SoVITS 那邊，
而且要載進 GPU 才能用。所以本專案不「內建」聲音，是**打 HTTP 去要**。

| | videomaker | GPT-SoVITS |
| :--- | :--- | :--- |
| 做什麼 | 教材 → 投影片 → 講稿 → 動畫 → 影片 | 訓練聲音模型、跑推論服務 |
| 有什麼 | 引擎程式碼（348 KB） | 上游程式碼、語料 284 MB、訓練 log 6.5 GB、權重 |
| venv | numpy／PIL／scipy + LLM SDK（291 MB） | torch cu130（6.7 GB） |
| 版控 | GitHub `Nick921003/videomaker` | 本機 fork，origin 指著官方上游 |

**唯一的往來是 `:9880` 的 HTTP。** 所以之後換聲音模型、把服務搬到別台機器、
甚至換掉整個 TTS 引擎，videomaker 都只要改 `.env`。

## 要出片，先開聲音服務

```bash
cd ~/projects/GPT-SoVITS
.venv/bin/python api_v2.py -a 127.0.0.1 -p 9880
```

它會依 `GPT_SoVITS/configs/tts_infer.yaml` 的 `custom:` 區塊載入權重，目前指向：

```
t2s_weights_path:   GPT_weights_v2/wang_teacher_v3-e15.ckpt
vits_weights_path:  SoVITS_weights_v2/wang_teacher_v3_e8_s648.pth
```

**換聲音就是改這兩行再重啟服務**，videomaker 那邊完全不用動。

服務起來後（`curl http://127.0.0.1:9880/tts` 回 500 就代表活著，只是缺參數）：

```bash
cd ~/projects/videomaker
.venv/bin/python video_engine/run.py video_engine/materials/c_struct.md --sec 110
```

約三分鐘出一支 1080p 影片，成本約 US$0.05。
沒開服務的話會停在階段 5，錯誤訊息會指出連不上 `:9880`。

要先審講稿就 `--until storyboard`，看過 `out/<課程>/storyboard.html` 再 `--from timeline` 續跑。
改一段講稿只重生那一段（約 2 秒），全片重出約 50 秒。

## 三個已知的下一步

### 一　教材輸入太窄（優先）

現在只吃 markdown。實際教材常是 PPTX 或 PDF。

難點：直接把 PPTX 轉成圖片當背景，就失去 `layout.json` 可量測的好處，動畫沒東西可以指。
比較對的作法是抽文字重排成 `lesson.json`，或支援「外部圖片當背景 + 額外標註可量測區域」。

### 二　`GPT-SoVITS/tts_lab/legacy/` 那九支沒實測過

2026-08-24 修好 Tab 與空格混用（先前八支根本無法被 Python 解析），但只確認語法過，
**沒有實際執行**。跑通一支確認舊管線還活著，或確定不需要就整個刪掉。

### 三　本機開源模型還沒試

四家商用模型（Opus 5 / Sonnet 5 / GPT-5.6-terra / Gemini 3.7 Flash）接上驗證閘之後
產出收斂到同一水準——**決定品質的是驗證閘，不是模型**。值得試 7B 量化模型能不能守住規則。

限制：RTX 3060 Laptop 只有 6 GB，TTS 服務已經佔著。本機 LLM 要排隊跑（先產完 JSON 再開 TTS）。
`llm.py` 已支援 `VIDEO_ENGINE_LLM=openai-compatible:<model>` + `LLM_BASE_URL`，接 vLLM／Ollama 即可。

## 聲音模型的待辦（在 GPT-SoVITS 那邊做）

`PROJECT_NOTES.md` 5.8 的 v4 清單仍然有效，最該做的是**補錄逐字母唸的縮寫語料**——
現有 317 條語料裡沒有任何一條是逐字母唸的，所以「Bridge AI」「AST」這類縮寫會發出氣音雜訊。
目前只能靠講稿規避（規則已寫進 `video_engine/prompts/slide_actions.system.md`），根治要補資料。

`patches/` 放著本專案對 GPT-SoVITS 的修改備份（中英分段對齊前端）。
那個 repo 沒有推到任何遠端，硬碟壞了就沒了——之後值得開一個 private fork 備份。

## 不要重蹈的覆轍

- **改 prompt 不如改 `validate.py`**。規則寫進驗證閘，模型會被打回重做；只寫在 prompt 裡，模型看心情。
- **但驗證規則訂錯比模型笨更麻煩**。曾經把圖形標籤上限訂成 12 字，`char name[32]` 是 13 字，
  模型重試三次全被自己的爛規則打回。
- **靜音偵測不能只用相對門檻**。AR 失控產生的低電平雜訊會剛好高於「峰值 2%」而被當成有聲音，
  必須同時加絕對門檻（逐框 RMS < 0.015）。
- **不要把 LLM SDK 裝進 GPT-SoVITS 的 venv**。`google-genai` 會連帶升級 pydantic 與 websockets，
  那是 gradio／FastAPI 在用的。本專案自己有 venv，沒有這個問題。
