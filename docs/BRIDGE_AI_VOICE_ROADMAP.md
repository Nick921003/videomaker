# BridgeAI 自動化教學影片生產架構與語音模型規劃

## 一、 核心目標
實現純本機（Local-Only）自動化管線：
`PPTX / 知識點 Markdown` $\rightarrow$ `LLM 口語講稿生成` $\rightarrow$ `GPT-SoVITS 本地老師聲音克隆` $\rightarrow$ `FFmpeg / Remotion 自動影音對齊合成 MP4`。

---

## 二、 中英混合與專業名詞發音方案

### 方案 A：講稿智慧口語化（已實作並驗收）
* **原理**：投影片畫面上保留完整英文專業縮寫（如 `srcML-DKT`、`AST-GRU`、`API`），但在進入本機 TTS 前，由 LLM 轉化為台灣課堂上自然流暢的口述教學講稿。
* **範例**：
  * **投影片視覺**：`srcML-DKT: 讓知識追蹤模型看得懂編不過的程式碼`
  * **LLM 口播講稿**：`「大家好，今天書報討論要跟大家分享的論文主題是：讓知識追蹤模型，看得懂編不過的程式碼。這是一套結合程式源碼標記與知識追蹤的全新研究。」`
* **優勢**：100% 發揮中文語音模型的最高音質與自然韻律，完全消除英文音素卡頓與黏滯。

---

### 方案 B：老師中英混讀語料二次微調（備忘記錄）
* **實施步驟**：
  1. 從王老師的 C 語言教學影片（如 `C-rlutil`、`C-basic`、指標與結構體教學）中，精確切出 20~30 句包含常見英文單字（如 `printf`、`int`、`return`、`include`、`NULL`、`terminal`）的混合語句。
  2. 加入 `teacher_dataset/teacher.list` 訓練集進行增量微調（Incremental Fine-Tuning）。
  3. 讓 SoVITS 聲線模型學會老師發英語單字時的特定口腔共鳴與發音習慣。

---

## 三、 本地端自動化流程指令

1. **投影片轉圖**：
   ```bash
   libreoffice --headless --convert-to pdf input.pptx --outdir temp/
   pdftoppm -png -r 150 temp/*.pdf temp/slides/slide
   ```
2. **語音生成（GPT-SoVITS API v2）**：
   - 伺服器：`http://127.0.0.1:9880/tts`
   - 模型權重：`SoVITS_weights_v2/wang_teacher_e8_s408.pth` + `GPT_weights_v2/wang_teacher-e15.ckpt`
   - 最佳解碼參數：`temperature=0.3`, `top_k=5`, `top_p=0.6`, `speed_factor=0.95`, `text_split_method=cut2`
3. **影音封裝（FFmpeg）**：
   - 每頁投影片與對應音訊合成獨立 MP4，並透過 `concat` 快速無損串接成整集教學影片。
