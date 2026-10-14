# 工作台第二步後端與第三步計畫 對抗式審查報告

**審查日期**：2026-10-08
**審查立場**：資深技術懷疑論者（Adversarial Review）
**審查範疇**：
- 後端核心：`workbench/source_document.py`、`workbench/material.py`、`workbench/uploads.py`、`workbench/run_normalize.py`、`workbench/library.py`、`studio/material_normalizer.py`、`workbench/server.py`
- 測試套件：`tests/test_workbench_source_document.py`、`tests/test_workbench_material.py`、`tests/test_workbench_ingestion.py`
- 計畫：`docs/superpowers/plans/2026-10-08-common-material-consumers.md`

---

## 執行摘要（Executive Summary）

第二步在本地確定性抽取與來源雜湊保存建立良好基礎，且測試在 mock 環境下全數通過。然而以**對抗視角**深入檢視實際執行邊界，發現**4 個嚴重阻擋級問題（Blocking Issues）**與**6 個高／中風險缺陷**：

1. **Review 死鎖**：所有真實 DOCX/XLSX 因預設頁首或圖表觸發「待核對」，導致 `_check_material` 永久封鎖教材，且缺乏解鎖或人工確認 API。
2. **純文字來源靜默遺失**：TXT/MD 上傳時，`create_unit` 搶先寫入假來源，導致 `attach_source` 觸發早期返回，原始檔案與切塊定位完全遺棄。
3. **圖片付費前防護假通過**：20MP 圖片上傳檢查通過，但整理轉 PDF 體積膨脹超過 5MB，在付費確認後異步崩潰。
4. **第三步引文驗證將大量崩潰**：既有簡報與心智圖嚴格比對 `material.md` 原文；第三步若引入 `source_context`，模型引文將因不在 `material.md` 中而 100% 被驗證閘退件。

---

## 🔴 阻擋級問題（Blocking Issues）

### 1. 【付費前防護 / 來源忠實】永久審核死鎖：真實 DOCX/XLSX 必然觸發 `待核對`，導致教材永久被 `_check_material` 封鎖
- **涉及檔案**：
  - `workbench/source_document.py` (L48-52, L88-90)
  - `studio/material_normalizer.py` (L198-202)
  - `workbench/material.py` (L61-63)
  - `workbench/run_normalize.py` (L59-64)
  - `workbench/server.py` (L295-314, L329, L348, L399)
- **具體情境**：
  1. 微軟 Word 產生的 DOCX 檔絕大多數包含預設 `word/header1.xml`、頁尾、或形狀；Excel 檔常含圖表或圖片。
  2. `source_document.py` 偵測到後，在抽取文字尾端自動加上 `待核對：- 文件含圖片、公式或附加內容，請另附 PDF 核對。`。
  3. `material_normalizer.py` 將此字串加入 `uncertainties`。
  4. `run_normalize.py` 將其寫入 `normalization.json` (`requires_review: True`)，且 `attach_source` 將 `material.json` 的 `review['required']` 設為 `True`。
  5. 使用者欲進行「分析教材 (`/api/v1/units/{id}/analyze`)」或「製作成品 (`/api/v1/units/{id}/generate`)」時，`server.py` 的 `_check_material` 檢查到 `requires_review` 與 `review.required`，直接拋出 HTTP 409 APIError (`code="normalization_review"`，提示「請核對原始教材，將修正後內容以「貼上文字」建立新教材」)。
  6. **死鎖點**：後端與 API **完全沒有提供「使用者確認通過疑點」或「標記已核對」的 API/機制**。使用者被永久阻擋，唯一的出路是放棄上傳的單元，回到首頁用純文字貼上，這使整套多格式來源儲存與管線淪為無法實際產出成品的死胡同。
- **測試盲區**：`test_workbench_ingestion.py` 使用 `FakeRunner` 手動寫入 `'uncertainties': []`，刻意繞過疑點注入，掩蓋此一阻擋問題。

### 2. 【來源忠實 / 資料版本】純文字 (TXT/MD) 上傳觸發 `attach_source` 早期返回，原始檔案與定位被靜默丟棄
- **涉及檔案**：
  - `workbench/library.py` (L58-59)
  - `workbench/material.py` (L43-46)
  - `workbench/run_normalize.py` (L57-58)
- **具體情境**：
  1. 使用者上傳 `txt` 或 `md` 檔案，呼叫整理流程。
  2. 在 `run_normalize.py` 中：
     ```python
     uid, _ = library.create_unit(markdown, title, source_kind=kind)
     attach_source(library, uid, raw_path, kind, extracted, pages)
     ```
  3. 在 `library.create_unit` 中，因為 `source_kind in ("md", "txt")`，它自動寫入 `material.json`，其中 `sources[0]['id'] = version`（即 sha256(`material.md`)），`path = 'material.md'`。
  4. 隨後呼叫 `attach_source`。當上傳檔案本身即為標準 UTF-8 文字，raw 檔案雜湊 `digest == version`。
  5. `attach_source` 執行到 L45：
     ```python
     if any(source['id'] == digest for source in data['sources']):
         return data
     ```
  6. **直接返回！** 原始上傳文字檔 `raw_path` **完全沒有被複製**到 `sources/{digest}/original.{kind}`，`sources/{digest}/extracted.md` 亦未被寫入，`source_blocks` 未被記錄，且由整理器回傳的 `pages`（含 `sections` 與 `uncertainties`）**完全未加入 `data['sections']`**。
  7. 若 `digest != version`（例如原檔含 CRLF 或 BOM），`sources` 則會同時存在 `material.md` 與 `original.txt` 兩個來源，且 `sections` 同時殘留 `plaintext_material` 的 dummy section 與 `pages` 的 section，導致資料結構混亂且引文對應錯位。

### 3. 【付費前防護 / 異步崩潰】高解析度圖片上傳驗收通過，但整理轉檔時超出 5MB 拋錯，於付費後異步失敗
- **涉及檔案**：
  - `workbench/source_document.py` (L134, L144-156)
  - `workbench/uploads.py` (L63-73)
  - `studio/material_normalizer.py` (L183-189)
- **具體情境**：
  1. `source_document.verified_image` 允許最多 2000 萬像素（20MP，例如 5000×4000）的 PNG/JPEG。
  2. 使用者上傳一個 3MB 的 20MP PNG，`uploads.py` 檢查 `len(data) <= 5MB` 通過；`extract_text` 僅回傳單行字串 `"圖片：5000 × 4000 像素；內容請核對原圖。"`。
  3. `uploads.create` 成功建立草稿，向前端回傳預估費用 `$0.01`。
  4. 使用者在前端點擊「確認整理」，進入付費管線 `run_normalize.py`。
  5. `studio/material_normalizer.py` 執行 `image_pdf(raw_path)`。Pillow 將 20MP RGB 影像轉成 PDF，產生的未深度壓縮 PDF 位元組極易膨脹至 8MB~15MB。
  6. `material_normalizer.py` L188：
     ```python
     if pdf_bytes is not None and len(pdf_bytes) > MAX_VISUAL_BYTES:
         raise NormalizationError("視覺教材檔案超過 5 MB")
     ```
  7. **在使用者確認後異步拋錯失敗**！`uploads.py` 在上傳階段（付費前防護）完全未進行轉 PDF 的位元組大小預檢，放行必定會在整理階段爆炸的合法圖片。

### 4. 【第三步計畫缺陷 / 引文驗證崩潰】第三步假設可直接注入 `source_context`，但既有簡報與心智圖引文檢查綁死 `material.md`
- **涉及檔案**：
  - `docs/superpowers/plans/2026-10-08-common-material-consumers.md` (L10-11)
  - `studio/deck_builder.py` (L88-93)
  - `studio/mindmap.py` (L149-152)
  - `video_engine/board/author.py` (L314-316)
- **具體情境**：
  1. 第三步計畫規劃：「簡報／心智圖runner載入共同教材，透過可選source_context參數提供來源定位與核對引文；保留原始material給既有引文驗證。」
  2. 當模型在 prompt 接收到包含原始文件的 `source_context` 時，模型產生的教學簡報 `source_quote` 或心智圖節點 `source_quote`，必然會引用出現在 `source_context`（如原始段落或表格細節）但在整理後 `material.md` 中已被改寫或省略的語句。
  3. 然而既有的 `deck_builder.validate_source_quotes` 實作如下：
     ```python
     source = _normalized(material)
     for slide in deck["slides"]:
         if _normalized(slide["source_quote"]) not in source:
             raise DeckError(f"第 {slide['slide_id']} 頁引文不在教材原文中")
     ```
  4. 同理，`mindmap.validate_citations` 亦只比對 `material.md`。
  5. **結果**：模型呼叫已付費，但驗證閘 100% 失敗並拋出 `DeckError` / `MindmapError`，直接報銷生成結果！
  6. 同樣地，`author.py plan` 的 `plan_problems` 嚴格比對 `s["sources"]` 是否存在於 `headings(md)`。若規劃模型參照了 `source_context` 的標籤，將引發 2 次修復失敗後拋出 `RuntimeError`，付費 token 泡湯。

---

## 🟡 高與中風險問題（High / Medium Risk Issues）

### 5. 【格式遺失】DOCX 靜默丟棄內容控制項 (`w:sdt`)、丟失軟換行 (`<w:br/>`)、表格儲存格文字黏合
- **涉及檔案**：`workbench/source_document.py` (L34-53)
- **具體情境**：
  - `_docx` 只遍歷 `body` 下的直接子元素 `w:p` 與 `w:tbl`。許多 Word 範本或表單把段落包在 `w:sdt`（Structured Document Tag）內，這些段落直接被忽略，完全沒有抽取。
  - Word 的軟換行 `<w:br/>` 不是 `<w:t>`，被 `findall('.//w:t')` 忽略，導致段落內文字合併。
  - 表格儲存格內若有多個段落，`''.join(...)` 導致段落之間無任何空白或換行直接黏合（例："項目A" 與 "說明B" 變成 "項目A說明B"）。

### 6. 【格式遺失 / 崩潰】XLSX 空白儲存格 `t="s"` 缺少 `<v>` 引發 `ValueError` 崩潰；布林值與錯誤代碼型別遺失
- **涉及檔案**：`workbench/source_document.py` (L74-87)
- **具體情境**：
  - 若儲存格定義為字串型別 `t="s"` 但未填入值（無 `<s:v>` 或為空），`cell.findtext('s:v', default='', namespaces=NS)` 回傳 `""`，接續執行 `int(value)` 即觸發 `ValueError: invalid literal for int() with base 10: ''` 導致整個檔案抽取失敗。
  - Excel 的布林值 (`t="b"`) 被當作字串 `'1'` / `'0'`，公式錯誤 (`t="e"`) 被當作普通字串，無型別標示。

### 7. 【定位斷鏈】`source_blocks` 的細粒度定位（段落號、工作表、儲存格）完全未傳遞給 `material.json` 的 `sections`
- **涉及檔案**：
  - `workbench/source_document.py` (L159-195)
  - `workbench/material.py` (L57-60)
- **具體情境**：
  - `source_document.py` 辛苦計算出 CSV `row`、DOCX `body_block` / `table_row`、XLSX `sheet` / `cell`，並保存在 `sources[i]['blocks']`。
  - 但是在 `workbench/material.py` 的 `attach_source` 中，`sections` 的 locator 卻被寫死為：
    `locator={('page' if kind == 'pdf' else 'slide' if kind == 'pptx' else 'extracted_part'): page['page']}`。
  - 所有非 PDF/PPTX 的單元，其 `sections` 裡面的定位永遠只有 `{'extracted_part': 1}`！
  - 第三步計畫宣稱「提供來源定位與核對引文」，但後端 `sections` 與 `source.blocks` 之間毫無關聯 index 或 mapping，根本無法定位到具體段落或儲存格。

### 8. 【資料版本 / 跨平台脆弱性】`content_version` 依賴 raw sha256(`material.md`)，CRLF/LF 換行直接導致整份教材失效
- **涉及檔案**：
  - `workbench/material.py` (L11, L38, L83)
  - `workbench/server.py` (L307-310)
- **具體情境**：
  - `content_version` 採用 `hashlib.sha256(markdown.encode('utf-8')).hexdigest()`。只要在 Windows 下被編輯器存成 CRLF，或者稍有換行差異，`read_material` 即拋出 `ValueError('教材正文版本或共同資料契約不一致')`。
  - 此時 `workbench/server.py` 的 `_check_material` 一律拋出 HTTP 409 `code="material_version"`，阻斷所有製作請求，要求使用者「請重新加入原始教材」，缺乏空白正規化或 hash tolerance。

### 9. 【安全路徑 / 邊界控制】`/media/` 路由直接暴露 `unit_dir` 下的敏感運算與系統內部檔案
- **涉及檔案**：`workbench/server.py` (L540-544)
- **具體情境**：
  - `/media/{uid}/{path}` 允許透過 HTTP GET 讀取 `unit_dir` 下任何相對路徑。
  - 除了合法媒體成品，使用者可直接下載 `/media/{uid}/usage.jsonl`（包含內部每次 API 呼叫 token 與計費細節）、`/media/{uid}/sources/{digest}/original.{ext}`（原始未脫敏上傳檔）、`/media/{uid}/sources/{digest}/extracted.md`、`/media/{uid}/normalization.json` 等。
  - 雖然 `safe_path` 擋住了 `../` 越界，但單元內部的全部系統工作檔皆處於無防護可公開下載狀態。

### 10. 【付費前防護 / 缺乏 Runner 內嵌防護】CLI 執行 `run_slides.py` / `run_mindmap.py` 繞過 HTTP 檢查，直接花錢呼叫 Gemini Flash
- **涉及檔案**：
  - `workbench/run_slides.py` (L26-36)
  - `workbench/run_mindmap.py` (L24-34)
- **具體情境**：
  - `_check_material` 只寫在 `server.py` 的 HTTP 接口。
  - 若直接以 CLI 執行 `run_slides.py <unit_dir>` 或 `run_mindmap.py <unit_dir>`，腳本直接讀取 `material.md`，完全不讀取 `material.json`，不檢查 `content_version`，也不檢查 `review.required`。
  - 即使資料已經損毀或有未核對疑點，腳本依然直接發起真實的 Gemini LLM 請求並扣款。

---

## 結論與對第三步計畫的具體修正建議

當前第二步後端與第三步計畫**不建議直接進行第三步消費端接入**，必須先解決上述阻擋問題：

1. **修正審核閘門（解除死鎖）**：
   - 區分「硬阻擋（模型輸入不可讀/損毀）」與「軟注意（含未抽取之圖表/公式）」。
   - 在 API 增加允許使用者明確確認/覆核的機制（或在非致命視覺附註下允許生成，僅提示注意）。
2. **修復 TXT/MD 上傳資料流**：
   - 在 `create_unit` 區分「文字貼上」與「檔案上傳」，避免上傳 TXT/MD 時因假來源提早返回而丟棄原檔與定位。
3. **完善付費前圖片驗證**：
   - `uploads.py` 在上傳階段即必須執行 `image_pdf` 轉檔試算，若轉出的 PDF 超過 5MB 應在上傳時立即拒絕（HTTP 413），而非在異步付費整理時拋錯。
4. **重構第三步引文比對策略**：
   - 明確界定 `source_context` 是僅供 LLM 理解背景，還是允許作為引文來源。
   - 若僅供背景理解，prompt 必須嚴格要求引文僅能取自 `material.md`；若允許引用原始來源，則 `deck_builder` 與 `mindmap` 的驗證邏輯必須同步支援雙向來源比對。
