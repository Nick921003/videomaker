# 接手指南

> 更新：2026-08-25　狀態：影音引擎可全自動出片，使用者評「70 分」

換對話框後從這裡接。架構全貌看 [`../../video_engine/ARCHITECTURE.html`](../../video_engine/ARCHITECTURE.html)，
踩過的坑看 [`PROJECT_NOTES.md`](PROJECT_NOTES.md)。

---

## 現在能做到什麼

```bash
.venv/bin/python video_engine/run.py video_engine/materials/c_struct.md --sec 110
```

一份 markdown 教材進去，約三分鐘出一支 1080p 影片。全自動，中間不用手動改任何東西。
成本約 US$0.05（Opus 5 做教材結構化 + Gemini 3.7 Flash 做動作編排）。

要先審講稿就 `--until storyboard`，看過 `out/<課程>/storyboard.html` 再 `--from timeline` 續跑。
改一段講稿只重生那一段（約 2 秒），全片重出約 50 秒。

## 三個已知的下一步

### 一　教材輸入太窄（優先）

現在只吃 markdown。實際教材常常是 PPTX 或 PDF。

- PPTX：`libreoffice --headless --convert-to pdf` + `pdftoppm` 可以轉圖，但那樣會變回「用別人排好的版面」，
  失去 layout.json 可量測的好處。比較對的作法是抽文字重排，或支援「外部圖片當背景 + 自己標註可量測區域」。
- PDF：同上，另外要處理雙欄與圖表抽取。

### 二　`legacy/` 那九支沒實測過

2026-08-24 修好 Tab 與空格混用（先前八支根本無法被 Python 解析），但只確認語法過，**沒有實際執行**。
要嘛挑一支跑通確認舊管線還活著，要嘛確認不再需要就整個刪掉。

### 三　本機開源模型還沒試

四家商用模型（Opus 5 / Sonnet 5 / GPT-5.6-terra / Gemini 3.7 Flash）接上驗證閘之後產出收斂到同一水準，
代表**決定品質的是驗證閘不是模型**。值得試 7B 量化模型能不能守住那十幾條規則。

限制：RTX 3060 Laptop 只有 6 GB，TTS 已經佔著。本機 LLM 要排隊跑（先產完 JSON 再開 TTS）。
`llm.py` 已支援 `VIDEO_ENGINE_LLM=openai-compatible:<model>` + `LLM_BASE_URL`，接 vLLM／Ollama 即可。

## 聲音模型的待辦（與影音引擎無關）

`PROJECT_NOTES.md` 5.8 的 v4 清單仍然有效，其中最該做的是**補錄逐字母唸的縮寫語料**——
現有 317 條語料裡沒有任何一條是逐字母唸的，所以「Bridge AI」「AST」這類縮寫會發出氣音雜訊。
目前只能靠講稿規避（規則已寫進 `video_engine/prompts/slide_actions.system.md`），根治要補資料。

## 不要重蹈的覆轍

- **改 prompt 不如改 `validate.py`**。規則寫進驗證閘，模型會被打回重做；只寫在 prompt 裡，模型看心情。
- **但驗證規則訂錯比模型笨更麻煩**。曾經把圖形標籤上限訂成 12 字，`char name[32]` 是 13 字，
  模型重試三次全被自己的爛規則打回。
- **不要在訓練 venv 裝 LLM SDK**。`google-genai` 會連帶升級 pydantic 與 websockets，
  那是 gradio／FastAPI 在用的。LLM SDK 全部裝在獨立的 `.venv-llm`。
- **靜音偵測不能只用相對門檻**。AR 失控產生的低電平雜訊會剛好高於「峰值 2%」而被當成有聲音。
