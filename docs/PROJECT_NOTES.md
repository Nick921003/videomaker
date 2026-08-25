# BridgeAI 聲音模型與全自動影音生產引擎里程碑總覽 (Project Master Record)

> **更新日期**：2026-08-24  
> **專案狀態**：王老師 3.0（中英分段對齊微調版）推論驗收通過，已重新合成並導出 1080p 示範影片。

---

## 一、 核心聲音模型 (Wang Teacher 3.0 & 2.0)

### 🌟 王老師 3.0 (Wang Teacher 3.0 - 最新中英對齊強化版)
* **模型特點**：在 v2 錄音室級語料基礎上，引入 `large-v3` 校對逐字稿與 `text/mixed_frontend.py` 中英分段音素對齊，徹底改善中英夾雜專有名詞（如 `srcML-DKT`、`AST`、`compile`、`struct`）之發音流暢度與自然連貫性。
* **權重路徑**：
  * SoVITS (8 Epochs): `/home/pjw92/projects/GPT-SoVITS/SoVITS_weights_v2/wang_teacher_v3_e8_s648.pth`
  * GPT (15 Epochs): `/home/pjw92/projects/GPT-SoVITS/GPT_weights_v2/wang_teacher_v3-e15.ckpt`
* **黃金提示音訊 (Reference Prompt)**：
  * 音訊：`/home/pjw92/projects/GPT-SoVITS/teacher_dataset/sliced_audio_v2/AI-Menu_0000157760_0000317120.wav` (4.98 秒)
  * 提示文字：`「學生的成績資料然後也可以去做排序」`

---

## 二、 標準化影音生產核心參數與規範

* **詳細規格書**：[`BRIDGE_AI_VIDEO_ENGINE_SPEC.md`](file:///home/pjw92/projects/GPT-SoVITS/BRIDGE_AI_VIDEO_ENGINE_SPEC.md)
* **核心防錯與聲學參數**：
  1. **語言模式**：**強制指定 `text_lang = "zh"`**（杜絕中文字元被誤判為日語發音）。
  2. **語速標準**：`speed_factor = 0.95`（流暢緊湊教學節奏，全片約 50 秒）。
  3. **斷句換氣**：`text_split_method = "cut5"`、`fragment_interval = 0.12s`（依標點符號自然換氣，零冗餘長停頓）。
  4. **聲波 VAD 修齊**：前置 `pad_start_sec = 0.15s`，收尾 `pad_end_sec = 0.25s`（翻頁即刻發聲）。
  5. **Visual QA 攔截器**：自動偵測字型 `cmap`，將 Emoji 轉為合法 CJK 幾何標記（`▶ 步驟 X`），消滅 `☒` 亂碼。
  6. **幾何佈局防護**：`LayoutAnchorEngine` 自動推算行高與框選座標，確保與相鄰行保留 4px 以上安全間距，100% 杜絕切字。

---

## 三、 測試影片產出位置一覽表 (Output Video Artifacts)

所有產出之 1080p 示範影片均統一集中存放於本專案目錄內（不污染外部知識庫）：

### 📁 專案影片存檔目錄
* **最新 Wang 3.0 Master 影片目錄**：[`/home/pjw92/projects/GPT-SoVITS/output_videos/`](file:///home/pjw92/projects/GPT-SoVITS/output_videos/)
* **歷史版本 2.0 存檔目錄**：[`/home/pjw92/projects/GPT-SoVITS/output_videos/v2_legacy/`](file:///home/pjw92/projects/GPT-SoVITS/output_videos/v2_legacy/)

| 影片檔案名稱 | 專案存放路徑 | 類型 / 版本說明 | 長度 / 規格 | 關鍵驗收重點 |
| :--- | :--- | :--- | :---: | :--- |
| **`BridgeAI_Topic_C_Struct_MicroLecture_Wang3.0.mp4`** | `output_videos/` 或 `bridgeai_topic_demo/v3_output/` | **【Wang 3.0 微課程】C 結構體標準示範片** | **52 秒**<br>1080p | • 4 頁微課程 + 4 段程式碼動態聚光燈<br>• **中英混讀 (struct, typedef, Student) 發音顯著提昇**<br>• 0.95x 流暢節奏與緊湊換氣 |
| **`srcML_DKT_Teaching_Wang3.0_Demo.mp4`** | `output_videos/` 或 `teacher_dataset/test_ppt/v3_output/` | **【Wang 3.0 書報討論】開場示範片** | **37 秒**<br>1080p | • 專有名詞自然混讀 (srcML-DKT, AST, compile)<br>• 人聲自然純淨無殘響 |
| `BridgeAI_Topic_C_Struct_MicroLecture.mp4` | `output_videos/v2_legacy/` 或 `bridgeai_topic_demo/` | BridgeAI 知識點微課程 2.0 版存檔 | 53 秒<br>1080p | 2.0 基礎音訊示範 |
| `srcML_DKT_Teaching_Demo.mp4` | `output_videos/v2_legacy/` 或 `teacher_dataset/test_ppt/` | 書報討論：王老師 2.0 存檔 | 50 秒<br>1080p | 2.0 基礎音訊示範 |

---

## 四、 核心執行腳本 (Scripts & Pipelines)

* **Wang 3.0 全影音一鍵生產管線**：
  `/home/pjw92/projects/GPT-SoVITS/tts_lab/legacy/generate_v3_master_videos.py`
* **端到端微課程自動化管線**：
  `/home/pjw92/projects/GPT-SoVITS/tts_lab/legacy/bridgeai_topic_video_pipeline.py`
* **王老師 3.0 自動化微調訓練管線**：
  `/home/pjw92/projects/GPT-SoVITS/tts_lab/train/auto_train_teacher_v3.py`
* **資料集重建與驗證工具鏈**：`tts_lab/rework/`
  * `reasr_large_v3.py` — 用 large-v3 重跑逐字稿
  * `audit_transcripts.py` — 逐字稿風險評分，篩出需人耳確認的少數
  * `proofread.html` — 本機試聽校對介面（需 `python3 -m http.server`）
  * `test_english_survives.py` — 訓練前端回歸測試
  * `ab_compare.py` / `ab_repeat.py` — v2/v3 A/B 驗證
  * `build_deck.py` — 成果簡報產生器

---

## 五、 王老師 3.0 的根因修復記錄 (Root Cause & Fix)

> 記錄「為什麼需要 3.0」。這段是踩過的坑，重建資料集前務必先讀。

### 5.1 症狀與根因

v2 在中英混合時**音量塌陷、發音含糊**，純中文正常。根因是**訓練端與推論端用了不同的文字前端**：

| 路徑 | 程式 | 行為 |
| :--- | :--- | :--- |
| 推論 | `TTS_infer_pack/TextPreprocessor.py` | 先 `LangSegmenter` 切中英，再逐段 g2p ✅ |
| 訓練（修復前） | `prepare_datasets/1-get-text.py` | 直接 `clean_text(text, "zh")`，拉丁字母被中文前端吃掉 ❌ |

實例：ASR 逐字稿 `那這邊呢,老師有設定的Windows跟無棒圖`，訓練實際使用的是 `那这边呢,老师有设定的秒跟无棒图`——`Windows` 的 `s` 被 `zh_normalization/quantifier.py` 的量詞規則轉成「秒」，其餘字母刪除。

**規模**：89/317 條切片、7.7/25.2 分鐘，**30.6% 的訓練音訊沒有對應音素**。模型因此學會在英文附近產生無對齊的填充音。

次要因素：英文段的 BERT 條件向量為全零（`get_bert_inf()` 原生設計，**架構限制，重訓修不掉**）；推論取樣參數 `top_k=5, temperature=0.28` 在零條件下會塌到低能量 token，放大症狀。

### 5.2 修復

1. **訓練前端對稱化** — 新增 `GPT_SoVITS/text/mixed_frontend.py`，把推論端的 `LangSegmenter` 切分抽出共用；`1-get-text.py` 於 `lan == "zh"` 時改走它。非 zh 資料集維持原路徑。
2. **逐字稿重做** — Whisper `base` → `large-v3`。原本連中文都在錯（`程式碼`→`城市碼`、`Copilot`→`口拍了`、`Ubuntu`→`無棒圖`）。
3. **人工校對** — 用聲學與解碼證據把 317 筆篩到 15 筆需人耳確認。
4. **縮寫發音字典** — `text/engdict-hot.rep` 補上 `AST`／`DKT`／`SRCML`／`API`／`CNN` 等逐字母 ARPAbet。
   ⚠️ **2026-08-24 更正**：這些表項後來證實是**冗餘的**，全大寫規則本來就會逐字母拆。見 5.7。

### 5.3 重建資料集時的硬規則

* **ASR 不要給含主題詞的 `initial_prompt`**。實測會讓 Whisper 把提示詞原樣輸出，並**截斷句子**（黃金句 `學生的成績資料然後也可以去做排序` 被縮成 `學生的成績資料,排序`）。改用不含主題詞的短提示（`"好，那我們接下來看一下。"`）即可保留標點又不截斷。
* **逐字稿不可「順稿」**。目標是精確對應音訊，不是通順好讀。語助詞（老師的口頭禪是「齁」）、重複、口誤只要嘴巴有講就要寫進去。刪贅字等於親手製造對齊錯誤。
* 音訊有聲卻不想讓模型學的內容，正確做法是**整條切片剔除**，不是留著音訊卻不寫字。

### 5.4 驗收數據

| 指標 | v2 | v3 |
| :--- | ---: | ---: |
| 含英文音素的訓練行 | 0 / 317 | **108 / 317** |
| 音量穩定度 dip｜純中文 | 0.91 | 0.88 |
| 音量穩定度 dip｜中英夾字 | 0.91 ±.06 | **0.98 ±.08** |
| 音量穩定度 dip｜重度混合 | 0.67 ±.21 | **0.85 ±.09** |
| 可懂度｜重度混合 | 4.2 / 6 | **5.2 / 6** |

每種條件取樣 5 次。**判斷根因正確的依據是劑量反應**：英文越多改善越大、純中文不動。

⚠️ 單次取樣曾給出相反結論（v3 看起來較差），重複 5 次後反轉。**A/B 不可只跑一次。**

### 5.5 已知殘留

* 語助詞「齁」約 **10%** 音訊仍未標註（65 筆未覆蓋比例落在 15–30%）。若要再進一步，需做語助詞回收後重訓。
* 英文段 BERT 全零為架構限制，非資料問題。

### 5.6 環境 gotcha

**這個環境問題是整條 bug 鏈的起點。**

Gemini 寫的 8 支腳本，whisper 呼叫全部是 `WhisperModel("base", device="cpu", compute_type="int8")`，
沒有任何一支用 `cuda`。HuggingFace 快取顯示 2026-08-18 20:12~20:19 之間連續下載 tiny → base → small，
是在試不同大小後定案。推測的因果鏈：

```
CUDA 版本對不上（ctranslate2 要 cu12，訓練 venv 的 torch 是 cu13）
  → faster-whisper 只能跑 CPU
  → CPU 上大模型太慢（large-v3 跑 317 條要 30–50 分鐘）
  → 妥協選 base（142MB，最小之一）
  → 逐字稿品質差（「程式碼」→「城市碼」、「Copilot」→「口拍了」）
  → 訓練資料品質差
```

**所以「選錯模型」不是粗心，是環境限制下的合理妥協 —— 但沒有人回頭檢查。**
解法不是換模型，是解掉環境問題：獨立 venv 跑 GPU 後，同樣工作 30–50 分鐘 → **3 分鐘**，就沒有妥協的必要了。

注意：**訓練（s2/s1）一直都是 GPU**，用 CPU 的只有聽打這一步。

訓練 venv（torch cu13）**無法用 GPU 跑 faster-whisper**——`ctranslate2` 需 `libcublas.so.12`。已另建 `~/.venvs/whisper-gpu`，啟動前需設 `LD_LIBRARY_PATH`（`nvidia` 是 namespace package，要走 `__path__` 而非 `__file__`）。詳見 memory `gptsovits-whisper-gpu-venv`。

### 5.7 大小寫決定英文唸法（2026-08-24 補記）

英文前端的行為由**輸入的大小寫**決定，`engdict-hot.rep` 只在**非全大寫**時才會被查到：

| 寫法 | 結果 | 說明 |
| :--- | :--- | :--- |
| `AST` `DKT` `srcML` | 逐字母唸 A-S-T | 全大寫 → 內建規則自動拆字母 |
| `Json` `json` | 「傑森」 | 非全大寫 → 查 `engdict-hot.rep` |
| `JSON` | J-S-O-N ❌ | 全大寫，表項**失效** |
| `ChatGPT` | chat-G-P-T | 非全大寫 → 查表 |
| `CHATGPT` | C-H-A-T-G-P-T ❌ | 全大寫，表項**失效** |

**因此 `engdict-hot.rep` 現有的 9 個逐字母縮寫（SRCML/DKT/AST/API/LLM/CNN/RNN/NLP/GRU）是冗餘的** ——
不寫它們，全大寫規則也會給相同結果。真正會改變行為的 `JSON`/`CHATGPT`/`CONDA` 反而因為在文本中寫成全大寫而沒有生效。

**規則同時適用訓練逐字稿與教材講稿**：老師當單字唸的東西不可寫成全大寫。

### 5.8 v4 待辦

1. **修 7 筆大小寫錯誤的逐字稿**（2.2%，同 5.7 的問題）：
   * `Header-File_0005416960_0005632320` — `END IF` 應為 `end if`
   * `Student-Struct_0013802880_0014005440` — `ALTZALTZ` / `REF` 應為 `Alt Z、Alt Z` / `ref`
   * `Student-Struct_0014166720_0014334080` — `ALTZ` 應為 `Alt Z`
   * `Student-Struct_0008841920_0008965440`、`_0010480000_0010595200`、`_0012834880_0012937920`、`_0016015040_0016257280`
     — `SRAC` / `SREC` / `RAC` 為 ASR 聽錯結構名，需人耳確認實際用字
2. **補錄「逐字母唸縮寫」語料** —— 現有 317 條裡 30 條含英文，全是單字或詞組，**沒有任何一條是逐字母唸的**。縮寫弱是結構性缺口，補資料才能解。
3. **語助詞回收** —— 「齁」約 10% 音訊未標註（65 筆未覆蓋比例落在 15–30%）。
4. **改用 v2Pro 底模重訓（值得優先試）** —— 官方 README 稱 v2Pro 性能超過 v4，顯存僅略高於 v2，6GB 跑得動。
   底模已下載於 `pretrained_models/v2Pro/`（`s2Gv2Pro.pth` / `s2Dv2Pro.pth`），不需再抓。
   前置：訓練管線需多插一步 `prepare_datasets/2-get-sv.py` 產生 `7-sv_cn` 特徵，並把 s2 config 的 `version` 設為 `v2Pro`。
   注意：中英分段對齊修復在文字前端，與底模無關，**兩者是疊加而非取代**。
   v3/v4 底模亦已下載（`gsv-v4-pretrained`、`s1v3.ckpt`、`s2Gv3.pth`），但顯存需求較高，6GB 風險大。

5. **生成穩定性：加上「產出後自動驗收 + 失敗重試」（優先度高）**

   TTS 不穩定是架構本質，不是模型壞掉。原因由重到輕：

   | 成因 | 說明 | 證據 |
   | :--- | :--- | :--- |
   | **AR 生成無長度約束** | s1 是自迴歸模型，靠自己吐 `EOS`（`t2s_model.py` token 1024）決定何時停。沒有時長預測器或注意力對齊，`EOS` 不出現就一直生成 | v2 出現 23.5s 空白、孤立短句跑成 8.3s |
   | **對齊是隱式學的** | 訓練資料不對齊 → 模型學到「聲音可與文字脫鉤」→ 生成易失控 | v2（30% 不對齊）卡住 4/10；v3（修好英文）卡住 0/10 |
   | **短輸入更危險** | 上下文太少，AR 缺乏判斷停止的訊息 | 孤立合成「Bridge AI」（6 音素）5 次中 1 次跑掉 |
   | **`top_k=5` 太小** | 前 5 個 token 若都是「繼續」，容易進入重複迴圈；`temperature=0.28` 偏低會強化 | 生成長度 17.7–19.7s 波動 |

   **對策（依 CP 值）**：

   1. **產出後自動驗收 + 重試**（最有效）——檢查長度是否落在預期區間、有無 >1.5s 異常靜音、有無重複，不合格就重跑（上限 3 次）。
      檢測邏輯已存在於 `rework/v3_stability.py` 的 `analyse()`，包成函式接進 `tts_lab/legacy/generate_v3_master_videos.py` 即可，約 30 行。
   2. **固定 `seed`**（API 參數，現為 `-1` 隨機）——可重現，找到好種子可鎖定；但壞種子也會固定壞。
   3. **`repetition_penalty`** 現為 1.35，可試 1.5 抑制重複迴圈。
   4. `cut5` 斷句已在做——長句切片後單段失控的影響範圍較小，這也是成品影片比孤立測試穩定的原因。

   ⚠️ 另注意：測試腳本用 `fragment_interval=0.3`（API 預設），但 `tts_lab/legacy/generate_v3_master_videos.py` 用 `0.12`。
   比較音檔時參數要對齊，否則測到的接縫靜音會比實際出片多 1.5 倍。

### 5.9 穩定度驗收（N=10，2026-08-24）

同一句 srcML-DKT 講稿，各跑 10 次：

| 指標 | v2 | v3 |
| :--- | ---: | ---: |
| 十次裡卡住幾次（空白 >1.5s） | **4 次** | **0 次** |
| 全長 | 22.7s ±7.2 | 18.5s ±0.6 |
| 實際講話時間 | 15.1s ±0.7 | 15.4s ±0.4 |
| 最長一次空白 | **23.5s** | 1.1s |

**實際講話時間幾乎相同，差異全在空白** —— v2 會在句中卡住，v3 不會。
測試腳本：`rework/v3_stability.py` / `rework/v2_stability.py`。
