# 多模態教材工作台 Phase 2 簡報 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一份已上傳教材先產生可逐頁預覽與核可的線上簡報，再由同一份已核可 deck 資料匯出文字、圖形與講者備忘稿可編輯的 PPTX。

**產品對象註記（2026-09-28）：** 簡報是學生閱讀難懂知識點時可選的另一種解釋；PPTX 主要供教師編修／發布。本計畫的真實模型內容品質與瀏覽器驗收只指簡報，影片已由使用者成功生成，影片品質升級由獨立任務處理。

**實作進度（2026-09-28）：** Deck v1 契約、候選生成驗證、簡報 job/API、三階段前端進度、逐頁預覽、核可後原生 PPTX 匯出已接通。fake LLM API 閉環、Python/Node 回歸、LibreOffice 樣本轉檔與兩頁目視檢查已做。公開合成教材的真實 LLM 六頁簡報、PPTX 結構／PDF 視覺檢查與瀏覽器四種寬度已通過；尚待使用者教材的教學品質、Microsoft PowerPoint 編輯與跨任務影片重用整合。直接選 `pptx.editable_deck.v1` 仍保持 planned。



**Architecture:** 以版本化、無座標的 `Deck` 契約作為唯一內容真相；LLM 只產生候選內容，server 驗證後才保存。線上預覽用 DOM 安全呈現同一份 Deck，PPTX 用現有 `python-pptx` 畫原生文字與圖形。簡報 job 與影片共用 `ExecutionSlot`、source snapshot、plan/CSRF/manifest 路由，但有獨立 facade；影片八階段管線不改。先交付線上預覽，PPTX 從已核可 deck 匯出，不重跑 LLM。

**Tech Stack:** Python 3.10+、現有 `video_engine/llm.py` adapter、python-pptx 1.0.2、stdlib HTTP/SSE、原生 HTML/CSS/ES modules、`unittest`、`node:test`。

**基線與邊界：** Phase 1 工作樹目前有未提交的工作台程式，故此計畫在原工作樹執行；影片優化任務須使用獨立工作樹。此計畫不處理影片視覺優化、BridgeAI、多人持久化、線上協作編輯、任意外部字型或新增第三方依賴。真實 LLM 生成另作人工驗收；自動測試一律注入 fake completion，不呼叫付費服務。影片重用已核可 deck 的接線在兩邊產物穩定後另開整合任務，不偷渡進第一個線上簡報交付。

## 共用 Deck v1 契約

```json
{
  "contract_version": "1.0",
  "title": "課程標題",
  "slides": [{
    "slide_id": "s1",
    "role": "hook",
    "title": "本頁標題",
    "layout": "bullets",
    "blocks": [{"type": "bullets", "items": ["重點一", "重點二"]}],
    "speaker_notes": "講者補充說明",
    "source_quote": "教材中的短原文"
  }]
}
```

`role` 限 `hook/concept/example/pitfall/summary`；`layout` 限 `bullets/code/compare/steps`；block 限 `bullets`（1–5 個純文字）、`code`（語言和 1–16 行純文字）、`compare`（左右兩欄各 1–4 項）、`steps`（2–6 個節點）。每頁恰好一個與 layout 相符的主 block；Deck 3–12 頁、slide_id 唯一。標題、字數、陣列與總 JSON 大小都有上限；每頁 `source_quote` 須能在 normalized 教材中以空白正規化後找到，作為人工忠實度審查的定位線索。未知欄位拒絕，文字中的 URL/HTML 僅當純文字而不執行。`source_revision`、`template_id`、`review_gate` 與 artifact id 僅由 server 補入；模型不能指定。Deck v1 無像素座標，兩個 renderer 各自負責幾何。前端永遠用 `textContent` 建節點。

## 檔案責任圖

| 檔案 | 責任 |
|---|---|
| `studio/deck_contracts.py` | 驗證和 deep-copy Deck v1，拒絕未知結構、超界與重複 id |
| `studio/deck_builder.py` | 注入式 `complete_json`、bounded source、prompt、候選 Deck 驗證；不執行 job |
| `studio/deck_facade.py` | 簡報 job、進度事件、artifact 審核、Deck 保存與輸出檔 containment |
| `studio/pptx_export.py` | Deck v1 → 原生 PowerPoint shapes/text/notes；不把 PNG 當整頁 |
| `studio/catalog.py`、`studio/contracts.py`、`studio/planner_backends.py` | 放行已實作的簡報能力，保持單一受控 plan step |
| `serve.py` | 依 capability dispatch；簡報 preview JSON/PPTX content route；保留影片 route |
| `web/js/state.mjs`、`render.mjs`、`app.mjs`、`web/index.html`、`web/styles.css` | 依 artifact.kind 呈現逐頁簡報、審核、下載；保留影片播放器 |
| `tests/test_studio_deck_*.py`、`tests/web/*.test.mjs` | 契約、非法計畫、job、PPTX round-trip 與 UI 狀態回歸 |

---

### Task 1: Deck v1 契約與 catalog 第一個能力

**Files:** Create `studio/deck_contracts.py`, `tests/test_studio_deck_contracts.py`; modify `studio/catalog.py`, `studio/contracts.py`, `tests/test_studio_catalog.py`, `tests/test_studio_contracts.py`.

- [ ] **Step 1: 寫失敗測試。** `canonical_deck(sample)` 必須回傳 deep copy；拒絕少於三頁、重複 `slide_id`、未知 block、超界文字、外加 `script` 欄位。此 Task 保持 `slides.lesson_deck.v1` 為 `planned` 並仍拒絕執行；完整 API/UI 就緒後才開放。

```python
with self.assertRaises(DeckError):
    canonical_deck({**sample, "slides": [sample["slides"][0]] * 3})
self.assertEqual(canonical_deck(sample)["slides"][0]["blocks"][0]["type"], "bullets")
```

- [ ] **Step 2: 跑 `.venv/bin/python -m unittest tests.test_studio_deck_contracts tests.test_studio_contracts -v`，確認因 `studio.deck_contracts` 尚不存在而失敗。**
- [ ] **Step 3: 實作封閉 Deck 契約。** 保留 `artifact.generate` 單步及 `requires=[]`；計畫驗證只接受 catalog 中標記為 `available` 的註冊能力，不再寫死 `kind == video`。此時 catalog 不改可用狀態；`template_id` 與 `review_gate` 繼續由 server 決定。Deck 校驗必須在建立任何 artifact 前執行。
- [ ] **Step 4: 重跑上述測試與 `tests.test_studio_catalog`，預期全部通過。**

### Task 2: 明確簡報意圖與安全內容生成

**Files:** Create `studio/deck_builder.py`, `tests/test_studio_deck_builder.py`; modify `studio/planner_backends.py`, `tests/test_studio_planner_backends.py`.

- [ ] **Step 1: 寫失敗測試。** 「做線上簡報」在 catalog 尚標為 planned 時回 `needs_clarification`，開放後才回 `slides.lesson_deck.v1` ready plan；「做影片和簡報」永遠需釐清；指定 PPTX 在其可執行前仍須釐清；超過 deck source 上限明確失敗，不可默默截斷；fake completion 回未知欄位或不在教材中的 `source_quote` 不得保存。

```python
fake = lambda system, user, schema: ({"contract_version": "1.0", "title": "x", "slides": []}, {})
with self.assertRaises(DeckError):
    build_deck("教材文字", fake)
```

- [ ] **Step 2: 跑 `.venv/bin/python -m unittest tests.test_studio_deck_builder tests.test_studio_planner_backends -v`，確認因新 builder/意圖缺失而失敗。**
- [ ] **Step 3: `build_deck(material, instruction, complete_json)` 只呼叫現有 adapter 一次，來源限定 30,000 字元，失敗回安全碼，模型回傳經 `canonical_deck()` 與 `validate_source_quotes()` 後才交 facade。** Prompt 要求每頁講者備忘稿、來源忠實、先解概念再舉例；不得輸出圖片 URL、shell、座標。規則 planner 的 PPTX 辨識從泛用 slides 分離，避免「下載 PPTX」誤判線上簡報。
- [ ] **Step 4: 重跑此組測試；測試不得設真實 API key 或執行 `video_engine/run.py`。**

### Task 3: 簡報 job 與 API 閉環

**Files:** Create `studio/deck_facade.py`, `tests/test_studio_deck_facade.py`; modify `serve.py`, `tests/test_studio_api.py`.

- [ ] **Step 1: 寫失敗測試。** 正確簡報 plan 建 job 不需 TTS、佔用共用 slot，`queued → running → done/failed` 可 snapshot/SSE；來源在 job 建立時再驗雜湊並取 immutable snapshot；非法 plan、失效來源、slot busy、壞模型回應的安全狀態可復原。`get_review()` 對沒有講稿閘的簡報回 409；artifact approval/rejection 和影片一致。
- [ ] **Step 2: 跑 `.venv/bin/python -m unittest tests.test_studio_deck_facade tests.test_studio_api -v`，確認簡報建立仍被目前影片專用路由拒絕。**
- [ ] **Step 3: `serve.py` 先依 canonical plan 的 capability id dispatch；影片路徑不變，簡報由 `DeckJobFacade` 在背景執行。** 只有影片先 probe TTS。Deck 結果以 deep copy 保存在 process-local facade，不落地新檔；對外 manifest 的 `kind` 與 `preview.type` 為 `deck`、`preview.url` 為既有 artifact content 路由，content type 為 JSON，PPTX 加入前 `download` 可為 null；公開 snapshot/event/error 不暴露檔案路徑或 raw provider 錯誤。完成或失敗都釋放 source snapshot 和 execution slot；服務重啟後 deck 與 approval 狀態消失。
- [ ] **Step 4: 重跑此組及 legacy `tests.test_serve`，預期全通過。**

### Task 4: 線上簡報逐頁檢視與審核

**Files:** Modify `web/index.html`, `web/styles.css`, `web/js/state.mjs`, `web/js/render.mjs`, `web/js/app.mjs`, `tests/web/state.test.mjs`.

- [ ] **Step 1: 寫失敗測試。** `kind=deck` 的 artifact 不操作 `<video>`；結果頁顯示標題、頁數、前後頁、備忘稿與核可/退回，鍵盤可操作；簡報 `draft/validate/publish` 進度不顯示影片八階段，重新整理後依 snapshot 的 `capability_id` 重建；影片 artifact 仍保留現有播放器。惡意文字如 `<img onerror=...>` 只能成為文字。
- [ ] **Step 2: 跑 `node --test tests/web/*.test.mjs` 與瀏覽器案例，確認新 deck 結果尚不能顯示。**
- [ ] **Step 3: 先使 `DeckJobFacade.snapshot()` 與 `VideoJobFacade.snapshot()` 都提供 `capability_id`，前端依此選擇階段清單；在 catalog、API、viewer 都可用後才把 `slides.lesson_deck.v1` 改為 `available`。以 DOM API/render 函式逐頁產生 Deck v1，所有教材字串用 `textContent`。** 結果區依 artifact.kind 顯示 deck 或 video；deck 用有限的 CSS 版型渲染 bullets/code/compare/steps，頁碼、備忘稿、前後頁和手機窄版可見。結果仍置於工作台頂部。對已核可 deck 顯示「匯出 PPTX」入口之前，保持該控制隱藏。
- [ ] **Step 4: 跑前端測試與 375/768/1024/1440 px 瀏覽器人工檢查，驗文字不溢出、不跑版、影片仍播放。**

### Task 5: 從同一份 deck 輸出可編輯 PPTX

**Files:** Create `studio/pptx_export.py`, `tests/test_studio_pptx_export.py`; modify `studio/deck_facade.py`, `serve.py`, `studio/catalog.py`, `studio/contracts.py`, `studio/planner_backends.py`, `web/js/render.mjs`, `web/js/app.mjs`, `web/index.html`, `tests/test_studio_api.py`.

- [ ] **Step 1: 寫失敗測試。** 同一份 Deck 匯出後以 `pptx.Presentation` 重新打開，頁數、標題、文字、code、比較欄、講者備忘稿都可從原生 shapes/notes 讀回；不得只有單張全頁圖片。未知 deck id、未核可、重複匯出、傳入本機路徑要安全處理；exporter 以 `BytesIO` 回傳 PPTX bytes，不建立可被 symlink 跳脫的公開輸出路徑。線上簡報已核可後匯出不得再呼叫 LLM。

```python
prs = Presentation(path)
self.assertEqual(len(prs.slides), len(deck["slides"]))
self.assertIn(deck["slides"][0]["title"], [shape.text for shape in prs.slides[0].shapes if shape.has_text_frame])
self.assertEqual(prs.slides[0].notes_slide.notes_text_frame.text, deck["slides"][0]["speaker_notes"])
```

- [ ] **Step 2: 跑 `.venv/bin/python -m unittest tests.test_studio_pptx_export -v`，確認 exporter 尚不存在而失敗。**
- [ ] **Step 3: 用現有 `python-pptx` 的 textbox、AutoShape、paragraph 與 notes API 實作 16:9 PPTX。** 內容來自已核可 Deck v1；保留可編輯元素、確定性版位和暖色主題。從 artifact id 取得已核可 deck，server 用 `BytesIO` 生成 PPTX，決定安全下載檔名並回傳正確 MIME；不接受呼叫端指定輸出路徑。Deck artifact 的 preview 仍是線上簡報，核可後同一 artifact 增加 PPTX download URL；`pptx.editable_deck.v1` 完成獨立驗收後才標 `available`。若使用者直接選 PPTX，計畫先生成同一 Deck，再提供線上預覽與 PPTX，不暗中建立第二次付費 job。
- [ ] **Step 4: 重跑 exporter/API/legacy 測試，並以 PowerPoint 或 LibreOffice 人工確認可編輯性與講者備忘稿。**

### Task 6: 回歸、交接與跨任務整合點

**Files:** Modify `README.md`, `docs/NEXT_STEPS.md`, `docs/superpowers/specs/2026-09-23-multimodal-learning-studio-design.md`.

- [ ] **Step 1: 跑 `.venv/bin/python -m unittest discover -s tests -t .`、`node --test tests/web/*.test.mjs`、`node --check web/js/*.mjs`、`git diff --check`；全部 0 failures/errors。**
- [ ] **Step 2: 用 fake LLM 完成 API → Deck → 線上逐頁 → 核可 → 原生 PPTX 下載 E2E；再由使用者授權的一份小教材做真實內容品質驗收。** 驗源文正確性、概念完整、文字可讀、備忘稿有用；自動測試通過不代表教學品質通過。
- [ ] **Step 3: 文件明確記錄 Deck v1、LLM 成本、暫存狀態、可編輯元素、限制與待整合點。** 影片優化任務提出的 `audience_level`、`learning_goal` 和 A/B 版本欄位仍只是提案，等兩邊確認後再擴充受控契約；不在此計畫中猜值。Phase 2 原始規格另含「影片可選擇重用已核可 deck」；這需要影片引擎與簡報契約共同設計，列為兩個任務完成後的獨立整合驗收，不把未實作的選項放到 UI。
