# Demo 真實用量與學生自讀簡報 Implementation Plan

> Agent workflow: 使用 subagent-driven-development 分工及 adversarial-review 審查；不 commit／push，保留現有 dirty worktree。

**Goal:** 每次教材生成顯示供應商實際 tokens 與明確標示的估算 USD 費用；教材整理另列。PPT 以學生自讀、清楚教學圖解與內容決定版面為方向。

**Architecture:** 標準庫 ContextVar 在每個模型回應解析前收集用量，保留截斷及驗證失敗的回應；透過 job snapshot 傳至 Demo，影片子行程沿既有 JSON stderr 傳遞用量。Deck 契約保持舊版相容，增加有界概念圖及頁面上的重點解釋，HTML 與 PPTX 同步呈現。

**Tech Stack:** Python unittest／ContextVar、既有各供應商 SDK、原生 ES modules／node:test、python-pptx；不新增依賴，不呼叫付費 API 或 TTS。

## Task 1: 真實用量

Files: 新增 `video_engine/usage.py`、`tests/test_usage.py`；修改 `video_engine/llm.py`、`video_engine/run.py`、`jobstate.py`。

- [x] 先寫並執行失敗測試：Gemini input779/output805/thinking513 得2097；Claude thinking 不重加；截斷及壞JSON仍記錄；沒有usage不能宣稱0；未知模型費用為null；不同job不串帳。
- [x] 實作 UsageLedger／capture_call：收集安全的模型名稱及數字，清除任意附加欄位；標準化 input/output/thinking/cache，返回 calls、total_tokens、estimated_cost_usd、complete。費率依2026-10-02官方文件；Gemini優惠2027年起自動使用正常價格。SDK錯誤缺usage保留不完整狀態，不虛構消耗。

```python
assert normalize_usage('google', 'gemini-3.8-flash',
    {'in':779, 'out':805, 'thinking':513})['total_tokens'] == 2097
```

- [x] 供應商SDK取得response後立即紀錄，然後才檢查stop_reason或解析JSON。capture_call對注入runner回傳usage提供fallback，實際SDK已紀錄時不重複計算。
- [x] `run.py`只在JSON事件模式透過子行程env啟用用量事件；`Job._pump`累計用量事件，不影響進度或百分比。
- [x] 執行 `.venv/bin/python -m unittest tests.test_usage tests.test_llm_budget tests.test_jobstate`。

## Task 2: Demo API／UI

Files: `studio/sources.py`、`studio/{deck,mindmap,video}_facade.py`、`serve.py`、`web/{index.html,styles.css}`、`web/js/render.mjs`、現有facade／source／HTTP及前端測試。

- [x] 先測完成及失敗生成皆含usage、source整理重用不重算，snapshot及SSE重播不增加，PPTX匯出／預覽不呼叫模型，未知usage顯示「未取得」而非0。
- [x] 每個來源及job獨立ledger；source public新增normalization_usage，job snapshot新增usage；既有source payload複製至job，防止換教材後帳目錯配。整理失敗的usage透過錯誤回應／重新查詢保留。
- [x] UI在完成成果附近顯示「本次生成」與「教材整理（共用素材）」、輸入／輸出／思考及calls，估算成本明示不是帳單；失敗保留已回報消耗，不把部分統計稱作完整。沿用暖色、原生details及響應式layout。
- [x] 執行 `.venv/bin/python -m unittest tests.test_studio_sources tests.test_studio_deck_facade tests.test_studio_mindmap_facade tests.test_studio_video_facade tests.test_studio_api` 及 `node --test tests/web/*.test.mjs`。

## Task 3: 學生自讀 PPT

Files: `studio/deck_contracts.py`、`studio/deck_builder.py`、`studio/pptx_export.py`、`web/js/render.mjs`的renderDeck、`web/styles.css`簡報樣式、簡報契約／builder／PPTX／render測試。

- [x] 先測舊版Deck照常接受；新概念圖有2–4個有標題／解釋的分支，拒絕未知欄位與超長文字；PPTX原生可編輯圖形含全部解釋且不越界；HTML hostile text只用textContent。
- [x] 新生成Deck版本1.1要求每頁takeaway（上限120字），契約仍接受原1.0；concept layout以center與2–4個items（title／text）表達中心概念與關係。模型schema和prompt同步，要求依語意選版型、流程表達方向、自讀解釋可見、引用支持內容，不強迫每頁圖解。

```python
block = {'type':'concept', 'center':'迴圈', 'items':[
    {'title':'條件', 'text':'決定是否繼續'},
    {'title':'更新', 'text':'讓狀態向終止前進'}]}
```

- [x] HTML／PPTX概念中心與分支圖、steps方向提示；takeaway放在可見頁面。沿用暖色，不新增AI圖像、圖片依賴或固定事實；舊版輸出維持可用。
- [x] 執行 `.venv/bin/python -m unittest tests.test_studio_deck_contracts tests.test_studio_deck_builder tests.test_studio_pptx_export` 及前端render測試；以合成公開教材產生離線PPTX／預覽，驗1440與375寬度及PPTX幾何。

## Task 4: 驗證／交付

- [x] 對抗審查計畫並解決可觀察風險，獨立review最終diff。
- [x] `.venv/bin/python -m unittest discover -s tests -t .`、`node --test tests/web/*.test.mjs`、ES module語法檢查及`git diff --check`。
- [x] 用注入fake LLM的HTTP生成流程核對來源整理與job totals、失敗消耗；不產生付費驗收呼叫。
- [x] 更新README／NEXT_STEPS並交付Markdown驗收報告，列明實際檢查、用量費率來源、舊資料無法補帳及服務記憶體限制。

費率來源： https://platform.claude.com/docs/en/models/opus-5-5/overview 與 https://ai.google.dev/gemini-api/docs/pricing 。估算僅計token費，不含TTS／電費／Codex對話／供應商折扣。

## 審查後約束

- CLI與server的import路徑各使用單一usage模組；子行程直接記錄SDK response，JSON stderr事件flush，不依賴父行程ContextVar跨process。
- 每頁takeaway使用獨立保留區；各主版型2–6項、最長允許內容要實際開PPTX驗不越界、不覆蓋takeaway／頁碼。容不下明確拒絕，不能無聲縮成小字。
- 舊工作沒有usage標為未取得，不宣稱0；同job輪詢不得重算。若SDK自動重試無usage，不宣稱完整帳單。
