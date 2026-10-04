# videomaker 未提交工作分組計畫（2026-10-04）

## 範圍與核對基準

- 唯讀來源：`/home/pjw92/projects/videomaker`；branch：`feat/demo-frontend`。
- 核對 HEAD：`0ea1a329bd22f7603c819e5a4c0ea9118858f81b`。
- `git status --short --untracked-files=all`：**16 個 tracked 修改＋119 個 untracked＝135 檔**；index 原本沒有 staged 變更。
- 本計畫為 **10 組、128 個不同檔案**；另外 **7 個 scratch 檔不提交**，保留原地。
- 提交訊息沿用 repo 的 `type(scope): 繁體中文主旨`／`docs: 繁體中文主旨` 慣例。
- 使用者提供的上一輪驗收為 **456 tests OK**。本次重新核對 status、diff、檔案依賴與內容；**未重跑來源 repo 測試，未執行 add、commit、修改、搬移或刪除**。
- 本次只交付這份 Markdown；下方腳本是供使用者審閱後自行執行的文字。

## 提交順序與每組驗收

各組使用整個檔案，不做 hunk 拆分；每檔只出現於一組。測試指令均從來源 repo 根目錄執行，為該組提交後的預期驗收門檻，並非本次已執行的測試結果。Python 沿用 `.venv/bin/python`；保持 `E2E` 未設定，不啟用付費 lesson/actions 或 GPU synth 階段。

| 順序 | 檔數 | Conventional Commit subject |
| --- | ---: | --- |
| 1 | 9 | `feat(video): 記錄模型用量、限制輸出預算並調整教學提示` |
| 2 | 2 | `feat(ingest): 支援 PDF 抽取並限制教材輸入大小` |
| 3 | 19 | `feat(studio): 建立教材來源、規劃契約與共用執行權` |
| 4 | 8 | `feat(studio): 生成學生自讀簡報與可編輯 PPTX` |
| 5 | 4 | `feat(studio): 生成含教材證據的概念心智圖` |
| 6 | 13 | `feat(video): 加入紙上動畫影片、連貫字幕與版面路由` |
| 7 | 12 | `feat(web): 拆分教材工作台前端並保留舊版展示頁` |
| 8 | 6 | `feat(serve): 接通工作台生成、審核與用量 API` |
| 9 | 17 | `feat(prototype): 保存概念狀態變化與 A＋C 有聲試片工具` |
| 10 | 38 | `docs: 補齊工作台與影片設計的計畫、實驗及交接文件` |
| **合計** | **128** | **10 組，無重複、無遺漏** |

### 1. feat(video): 記錄模型用量、限制輸出預算並調整教學提示

**原因：**先建立後續生成工作共用的 usage、輸出預算與完成檢查，並收斂台灣用語及教學編排提示。

**精確檔案清單（9 檔）：**

```text
video_engine/llm.py
video_engine/usage.py
video_engine/run.py
video_engine/validate.py
video_engine/prompts/lesson_content.system.md
video_engine/prompts/slide_actions.system.md
jobstate.py
tests/test_llm_budget.py
tests/test_jobstate.py
```

**提交後應通過的測試：**

```bash
.venv/bin/python -m unittest tests.test_llm_budget tests.test_jobstate tests.test_pacing_validation
```

### 2. feat(ingest): 支援 PDF 抽取並限制教材輸入大小

**原因：**把 PDF、純圖片頁標記、PPTX 展開限制與文字大小檢查一併提交，供工作台來源層使用。

**精確檔案清單（2 檔）：**

```text
video_engine/ingest.py
tests/test_ingest.py
```

**提交後應通過的測試：**

```bash
.venv/bin/python -m unittest tests.test_ingest
```

### 3. feat(studio): 建立教材來源、規劃契約與共用執行權

**原因：**一起保存能力目錄、教材正規化、來源生命週期、canonical plan 與影片 facade，形成各產物共用的工作台底座。

**精確檔案清單（19 檔）：**

```text
studio/__init__.py
studio/catalog.py
studio/contracts.py
studio/material_normalizer.py
studio/sources.py
studio/planner.py
studio/planner_backends.py
studio/plans.py
studio/execution.py
studio/video_facade.py
tests/test_studio_catalog.py
tests/test_studio_contracts.py
tests/test_studio_material_normalizer.py
tests/test_studio_sources.py
tests/test_studio_planner.py
tests/test_studio_planner_backends.py
tests/test_studio_plans.py
tests/test_studio_execution.py
tests/test_studio_video_facade.py
```

**提交後應通過的測試：**

```bash
.venv/bin/python -m unittest tests.test_studio_catalog tests.test_studio_contracts tests.test_studio_material_normalizer tests.test_studio_sources tests.test_studio_planner tests.test_studio_planner_backends tests.test_studio_plans tests.test_studio_execution tests.test_studio_video_facade
```

### 4. feat(studio): 生成學生自讀簡報與可編輯 PPTX

**原因：**將簡報契約、可見重點、HTML/PPTX 產物生成及工作生命週期綁在同一組，避免格式與匯出版本不同步。

**精確檔案清單（8 檔）：**

```text
studio/deck_contracts.py
studio/deck_builder.py
studio/pptx_export.py
studio/deck_facade.py
tests/test_studio_deck_contracts.py
tests/test_studio_deck_builder.py
tests/test_studio_pptx_export.py
tests/test_studio_deck_facade.py
```

**提交後應通過的測試：**

```bash
.venv/bin/python -m unittest tests.test_studio_deck_contracts tests.test_studio_deck_builder tests.test_studio_pptx_export tests.test_studio_deck_facade
```

### 5. feat(studio): 生成含教材證據的概念心智圖

**原因：**把概念／關係驗證、教材原文證據、SVG 生成與 facade 一起交付。

**精確檔案清單（4 檔）：**

```text
studio/mindmap.py
studio/mindmap_facade.py
tests/test_studio_mindmap.py
tests/test_studio_mindmap_facade.py
```

**提交後應通過的測試：**

```bash
.venv/bin/python -m unittest tests.test_studio_mindmap tests.test_studio_mindmap_facade
```

### 6. feat(video): 加入紙上動畫影片、連貫字幕與版面路由

**原因：**紙上影片的契約、renderer、字幕、theme、job 與 facade 必須同版，並連同 A＋C、flow routing 及 renderer 修復測試提交。

**精確檔案清單（13 檔）：**

```text
video_engine/paper_contract.py
video_engine/paper_renderer.py
video_engine/paper_subtitles.py
video_engine/themes/paper.json
studio/paper_video.py
studio/paper_video_facade.py
tests/test_paper_contract.py
tests/test_paper_renderer.py
tests/test_paper_ac_renderer.py
tests/test_paper_flow_layout.py
tests/test_paper_renderer_repair.py
tests/test_paper_subtitles.py
tests/test_paper_video.py
```

**提交後應通過的測試：**

```bash
.venv/bin/python -m unittest tests.test_paper_contract tests.test_paper_renderer tests.test_paper_ac_renderer tests.test_paper_flow_layout tests.test_paper_renderer_repair tests.test_paper_subtitles tests.test_paper_video
```

### 7. feat(web): 拆分教材工作台前端並保留舊版展示頁

**原因：**一起保存新版首頁、ES modules、樣式、紙上影片測試入口與保留的 legacy 頁，避免首頁縮減被誤認為刪除功能。

**精確檔案清單（12 檔）：**

```text
web/index.html
web/legacy.html
web/paper-video-test.html
web/styles.css
web/js/api.mjs
web/js/state.mjs
web/js/render.mjs
web/js/app.mjs
tests/web/api.test.mjs
tests/web/state.test.mjs
tests/web/render.test.mjs
tests/web/usage.test.mjs
```

**提交後應通過的測試：**

```bash
node --test tests/web/api.test.mjs tests/web/state.test.mjs tests/web/render.test.mjs tests/web/usage.test.mjs
```

### 8. feat(serve): 接通工作台生成、審核與用量 API

**原因：**等全部 facade 與前端資源到位再提交 HTTP、CSRF、SSE、來源／計畫 API 及端到端用量傳遞測試，避免缺少 import 或靜態檔。

**精確檔案清單（6 檔）：**

```text
serve.py
tests/test_serve.py
tests/test_studio_api.py
tests/test_paper_entry.py
tests/test_paper_http.py
tests/test_usage.py
```

**提交後應通過的測試：**

```bash
.venv/bin/python -m unittest tests.test_serve tests.test_serve_children tests.test_studio_api tests.test_paper_entry tests.test_paper_http tests.test_usage
```

### 9. feat(prototype): 保存概念狀態變化與 A＋C 有聲試片工具

**原因：**把獨立原型的狀態模型、分場景 HTML、旁白／字幕／對齊及匯出工具完整保存，與正式引擎的紙上影片分開驗收。

**精確檔案清單（17 檔）：**

```text
prototypes/state_change_pilot/README.md
prototypes/state_change_pilot/state_model.py
prototypes/state_change_pilot/test_states.py
prototypes/state_change_pilot/semantic_check.c
prototypes/state_change_pilot/prepare_models.py
prototypes/state_change_pilot/render_pilot.py
prototypes/state_change_pilot/build_scene_samples.py
prototypes/state_change_pilot/scene_samples.html
prototypes/state_change_pilot/ac_movie_overrides.js
prototypes/state_change_pilot/build_ac_movie.py
prototypes/state_change_pilot/export_ac_video.py
prototypes/state_change_pilot/synth_ac_audio.py
prototypes/state_change_pilot/align_audio.py
prototypes/state_change_pilot/align_ac_audio.py
prototypes/state_change_pilot/repair_speech.py
prototypes/state_change_pilot/subtitle_preview.py
prototypes/state_change_pilot/sync_timeline.py
```

**提交後應通過的測試：**

```bash
PYTHONPATH=prototypes/state_change_pilot .venv/bin/python -m unittest discover -s prototypes/state_change_pilot -p test_states.py
```

### 10. docs: 補齊工作台與影片設計的計畫、實驗及交接文件

**原因：**功能收斂後集中保存 README、現況、歷史計畫、實驗紀錄與交接契約，避免文件先於可用程式落地。

**精確檔案清單（38 檔）：**

```text
README.md
video_engine/README.md
docs/NEXT_STEPS.md
docs/VIDEO_DESIGN_STATUS.md
docs/HANDOFF_DESKTOP_2026-10-01.md
docs/HANDOFF_ENVIRONMENT_CANVAS_DESIGN_2026-10-03.md
docs/HANDOFF_VIDEO_COMPONENT_RESEARCH_2026-10-03.md
docs/experiments/2026-10-01-ac-narrated-video.md
docs/experiments/2026-10-01-natural-subtitles.md
docs/experiments/2026-10-01-progressive-scene-samples.md
docs/experiments/2026-10-01-state-change-pilot.md
docs/experiments/2026-10-02-demo-usage-self-study.md
docs/experiments/2026-10-02-environment-paper-video.md
docs/experiments/2026-10-03-ac-motion-restoration.md
docs/experiments/2026-10-03-c-syntax-animation-review.md
docs/experiments/2026-10-03-cs101-component-coverage.md
docs/experiments/2026-10-03-rendering-architecture-evaluation.md
docs/experiments/2026-10-03-synth-first-speech-failure.md
docs/superpowers/plans/2026-09-17-quality-70-to-90.md
docs/superpowers/plans/2026-09-24-multimodal-learning-studio-phase1.md
docs/superpowers/plans/2026-09-28-ai-material-normalization.md
docs/superpowers/plans/2026-09-28-multimodal-learning-studio-phase2-decks.md
docs/superpowers/plans/2026-09-28-multimodal-learning-studio-ppt-quality.md
docs/superpowers/plans/2026-10-01-progressive-scenes.md
docs/superpowers/plans/2026-10-01-state-change-pilot.md
docs/superpowers/plans/2026-10-02-ac-motion-restoration.md
docs/superpowers/plans/2026-10-02-demo-usage-and-self-study-decks.md
docs/superpowers/plans/2026-10-02-duration-range-environment-video.md
docs/superpowers/plans/2026-10-02-paper-video-integration.md
docs/superpowers/plans/2026-10-03-flow-layout-routing.md
docs/superpowers/plans/2026-10-03-html-canvas-sample.md
docs/superpowers/plans/2026-10-03-paper-renderer-repair.md
docs/superpowers/specs/2026-09-23-multimodal-learning-studio-design.md
docs/superpowers/specs/2026-10-02-ac-motion-restoration.md
docs/superpowers/specs/2026-10-02-paper-video-integration.md
docs/superpowers/specs/2026-10-03-flow-layout-routing.md
docs/superpowers/specs/2026-10-03-html-canvas-sample.md
docs/superpowers/specs/2026-10-03-paper-renderer-repair.md
```

**提交後應通過的測試：**

```bash
test -s video_engine/out/demo3/durations.json && .venv/bin/python -m unittest discover -s tests -t . && node --test tests/web/*.test.mjs
```

## 排除的 7 個檔案

以下都是 untracked scratch，不列入任何 `git add`；排除只表示留在工作樹，不代表刪除。

| 檔案 | 排除原因 |
| --- | --- |
| `video_engine/examples/demo8.lesson.json` | demo8 臨時生成教材；未被目前測試、工作台或原型引用，缺少固定驗收契約。 |
| `video_engine/examples/demo8b.lesson.json` | demo8 的臨時變體；未被目前測試或正式程式引用。 |
| `video_engine/examples/fresh.lesson.json` | fresh 臨時生成教材；沒有穩定 fixture 用途。 |
| `video_engine/examples/fresh.actions.json` | fresh 教材的臨時編排產物；與 fresh.lesson.json 一起排除。 |
| `video_engine/materials/demo8.md` | demo8 試跑輸入，與臨時生成教材成套排除。 |
| `video_engine/materials/demo8b.md` | demo8b 試跑輸入，與臨時變體成套排除。 |
| `video_engine/materials/fresh.md` | fresh 試跑輸入，與其 lesson/actions 成套排除。 |

本次以 `rg` 檢查 tests、studio、web 與原型，未找到 demo8、demo8b、fresh 的檔案引用；這 7 檔沒有與功能提交綁定的必要。

## 已核對的風險與限制

1. **首頁大幅縮減已核對。** `HEAD:web/index.html` 為 **929 行／34,650 bytes**，目前 `web/index.html` 為 **47 行／9,502 bytes**。新版首頁引用 `/assets/styles.css` 與 `/assets/js/app.mjs`，其餘 modules 也都列入第 7 組。原頁面保存在 `web/legacy.html`（**942 行／35,199 bytes**）；逐行比較後，差異只包含新增 `csrfToken()` 與兩個 POST 的 `X-Studio-CSRF`，原介面沒有被大量刪除。第 8 組的 `serve.py` 接上 `/`、`/legacy`、`/paper-video-test` 及靜態資源；`tests/test_studio_api.py` 覆蓋首頁／legacy 與靜態資源存取。這是原始碼與 diff 核對，本次未做瀏覽器視覺驗收。

2. **乾淨 clone 的兩個 spotlight 測試缺 ignored fixture。** `tests/test_spotlight.py` 的 `TestCameraOnlyForCode.test_只有程式碼頁有鏡頭` 與 `TestCameraOnlyForCode.test_每個推近都指到自己那一行` 都會先讀取 `video_engine/out/demo3/durations.json`。這個檔案由 `.gitignore:2` 的 `video_engine/out/` 排除，沒有 tracked；使用的 `video_engine/examples/demo3.lesson.json` 與 `demo3.actions.json` 則已 tracked。即使本機上一輪 456 tests OK，乾淨 clone 缺 durations fixture 仍會報 `FileNotFoundError`。本計畫保留此既有風險，不把產出目錄強制加入 Git；第 10 組全套測試先要求 fixture 存在。可攜 fixture 的補強應另開修復，不能把本機測試結果當成 clean-clone 保證。

3. **paper theme 與 board 分支相同。** 目前 `video_engine/themes/paper.json` 與 `git show feat/board-runtime:video_engine/themes/paper.json` 逐位元組一致，SHA-256 為 `30182d2c077b605652e03722765bd7243e93a4431e465d1c33a3106fbacf23c9`。仍列入第 6 組，因它在 `feat/demo-frontend` 是 untracked，紙上 renderer 需要此檔；跨分支整合時避免把相同內容當成兩份新設計。

4. **中間提交只以各組指定測試為門檻。** `serve.py` 一個 diff 同時 import 簡報、心智圖與紙上影片 facade，不能在這些檔案之前整檔提交。第 7 組前端先落地，第 8 組才接通 HTTP；兩組之間新版頁面的資源路由尚未完整。第 2 組已接受 PDF，但既有 `tests/test_serve.py` 對 PDF／413 的更新與 server 行為要等第 8 組，因此不能宣稱每個中間 commit 的全套測試都通過。要讓所有中間 commit 都全套綠，需另做 hunk 層級重切，超出這份整檔 10 組計畫。

5. **測試與原型重製的成本不同。** PDF 測試沿用現有 `pdfinfo`／`pdftotext`；renderer 測試沿用本機字型、Pillow 與 FFmpeg。原型完整重製另需既有旁白、ASR、Chromium 等環境與 ignored 產物；第 9 組只跑免費狀態正反向測試，不能代表已重新生成有聲影片。文件保留原計畫與實驗的歷史狀態，不能把它們一律解讀為完成承諾。

## 可複製的逐組提交腳本（本次未執行）

這份腳本以核對時的 branch、HEAD 與空 index 為前提；每組都明列檔案並以 `git add <files> && git commit -m ...` 提交，隨後跑該組門檻。任一指令失敗就停止，使用者可逐組審閱／執行。請先確保本機原有測試環境及第 10 組需要的 ignored fixture 已備妥；腳本不安裝依賴、不啟用付費生成，也不處理 7 個 scratch 檔。

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /home/pjw92/projects/videomaker
test "$(git branch --show-current)" = 'feat/demo-frontend'
test "$(git rev-parse HEAD)" = '0ea1a329bd22f7603c819e5a4c0ea9118858f81b'
git diff --cached --quiet

# 第 1 組（9 檔）
git add -- \
  'video_engine/llm.py' \
  'video_engine/usage.py' \
  'video_engine/run.py' \
  'video_engine/validate.py' \
  'video_engine/prompts/lesson_content.system.md' \
  'video_engine/prompts/slide_actions.system.md' \
  'jobstate.py' \
  'tests/test_llm_budget.py' \
  'tests/test_jobstate.py' && \
  git commit -m 'feat(video): 記錄模型用量、限制輸出預算並調整教學提示'
.venv/bin/python -m unittest tests.test_llm_budget tests.test_jobstate tests.test_pacing_validation

# 第 2 組（2 檔）
git add -- \
  'video_engine/ingest.py' \
  'tests/test_ingest.py' && \
  git commit -m 'feat(ingest): 支援 PDF 抽取並限制教材輸入大小'
.venv/bin/python -m unittest tests.test_ingest

# 第 3 組（19 檔）
git add -- \
  'studio/__init__.py' \
  'studio/catalog.py' \
  'studio/contracts.py' \
  'studio/material_normalizer.py' \
  'studio/sources.py' \
  'studio/planner.py' \
  'studio/planner_backends.py' \
  'studio/plans.py' \
  'studio/execution.py' \
  'studio/video_facade.py' \
  'tests/test_studio_catalog.py' \
  'tests/test_studio_contracts.py' \
  'tests/test_studio_material_normalizer.py' \
  'tests/test_studio_sources.py' \
  'tests/test_studio_planner.py' \
  'tests/test_studio_planner_backends.py' \
  'tests/test_studio_plans.py' \
  'tests/test_studio_execution.py' \
  'tests/test_studio_video_facade.py' && \
  git commit -m 'feat(studio): 建立教材來源、規劃契約與共用執行權'
.venv/bin/python -m unittest tests.test_studio_catalog tests.test_studio_contracts tests.test_studio_material_normalizer tests.test_studio_sources tests.test_studio_planner tests.test_studio_planner_backends tests.test_studio_plans tests.test_studio_execution tests.test_studio_video_facade

# 第 4 組（8 檔）
git add -- \
  'studio/deck_contracts.py' \
  'studio/deck_builder.py' \
  'studio/pptx_export.py' \
  'studio/deck_facade.py' \
  'tests/test_studio_deck_contracts.py' \
  'tests/test_studio_deck_builder.py' \
  'tests/test_studio_pptx_export.py' \
  'tests/test_studio_deck_facade.py' && \
  git commit -m 'feat(studio): 生成學生自讀簡報與可編輯 PPTX'
.venv/bin/python -m unittest tests.test_studio_deck_contracts tests.test_studio_deck_builder tests.test_studio_pptx_export tests.test_studio_deck_facade

# 第 5 組（4 檔）
git add -- \
  'studio/mindmap.py' \
  'studio/mindmap_facade.py' \
  'tests/test_studio_mindmap.py' \
  'tests/test_studio_mindmap_facade.py' && \
  git commit -m 'feat(studio): 生成含教材證據的概念心智圖'
.venv/bin/python -m unittest tests.test_studio_mindmap tests.test_studio_mindmap_facade

# 第 6 組（13 檔）
git add -- \
  'video_engine/paper_contract.py' \
  'video_engine/paper_renderer.py' \
  'video_engine/paper_subtitles.py' \
  'video_engine/themes/paper.json' \
  'studio/paper_video.py' \
  'studio/paper_video_facade.py' \
  'tests/test_paper_contract.py' \
  'tests/test_paper_renderer.py' \
  'tests/test_paper_ac_renderer.py' \
  'tests/test_paper_flow_layout.py' \
  'tests/test_paper_renderer_repair.py' \
  'tests/test_paper_subtitles.py' \
  'tests/test_paper_video.py' && \
  git commit -m 'feat(video): 加入紙上動畫影片、連貫字幕與版面路由'
.venv/bin/python -m unittest tests.test_paper_contract tests.test_paper_renderer tests.test_paper_ac_renderer tests.test_paper_flow_layout tests.test_paper_renderer_repair tests.test_paper_subtitles tests.test_paper_video

# 第 7 組（12 檔）
git add -- \
  'web/index.html' \
  'web/legacy.html' \
  'web/paper-video-test.html' \
  'web/styles.css' \
  'web/js/api.mjs' \
  'web/js/state.mjs' \
  'web/js/render.mjs' \
  'web/js/app.mjs' \
  'tests/web/api.test.mjs' \
  'tests/web/state.test.mjs' \
  'tests/web/render.test.mjs' \
  'tests/web/usage.test.mjs' && \
  git commit -m 'feat(web): 拆分教材工作台前端並保留舊版展示頁'
node --test tests/web/api.test.mjs tests/web/state.test.mjs tests/web/render.test.mjs tests/web/usage.test.mjs

# 第 8 組（6 檔）
git add -- \
  'serve.py' \
  'tests/test_serve.py' \
  'tests/test_studio_api.py' \
  'tests/test_paper_entry.py' \
  'tests/test_paper_http.py' \
  'tests/test_usage.py' && \
  git commit -m 'feat(serve): 接通工作台生成、審核與用量 API'
.venv/bin/python -m unittest tests.test_serve tests.test_serve_children tests.test_studio_api tests.test_paper_entry tests.test_paper_http tests.test_usage

# 第 9 組（17 檔）
git add -- \
  'prototypes/state_change_pilot/README.md' \
  'prototypes/state_change_pilot/state_model.py' \
  'prototypes/state_change_pilot/test_states.py' \
  'prototypes/state_change_pilot/semantic_check.c' \
  'prototypes/state_change_pilot/prepare_models.py' \
  'prototypes/state_change_pilot/render_pilot.py' \
  'prototypes/state_change_pilot/build_scene_samples.py' \
  'prototypes/state_change_pilot/scene_samples.html' \
  'prototypes/state_change_pilot/ac_movie_overrides.js' \
  'prototypes/state_change_pilot/build_ac_movie.py' \
  'prototypes/state_change_pilot/export_ac_video.py' \
  'prototypes/state_change_pilot/synth_ac_audio.py' \
  'prototypes/state_change_pilot/align_audio.py' \
  'prototypes/state_change_pilot/align_ac_audio.py' \
  'prototypes/state_change_pilot/repair_speech.py' \
  'prototypes/state_change_pilot/subtitle_preview.py' \
  'prototypes/state_change_pilot/sync_timeline.py' && \
  git commit -m 'feat(prototype): 保存概念狀態變化與 A＋C 有聲試片工具'
PYTHONPATH=prototypes/state_change_pilot .venv/bin/python -m unittest discover -s prototypes/state_change_pilot -p test_states.py

# 第 10 組（38 檔）
git add -- \
  'README.md' \
  'video_engine/README.md' \
  'docs/NEXT_STEPS.md' \
  'docs/VIDEO_DESIGN_STATUS.md' \
  'docs/HANDOFF_DESKTOP_2026-10-01.md' \
  'docs/HANDOFF_ENVIRONMENT_CANVAS_DESIGN_2026-10-03.md' \
  'docs/HANDOFF_VIDEO_COMPONENT_RESEARCH_2026-10-03.md' \
  'docs/experiments/2026-10-01-ac-narrated-video.md' \
  'docs/experiments/2026-10-01-natural-subtitles.md' \
  'docs/experiments/2026-10-01-progressive-scene-samples.md' \
  'docs/experiments/2026-10-01-state-change-pilot.md' \
  'docs/experiments/2026-10-02-demo-usage-self-study.md' \
  'docs/experiments/2026-10-02-environment-paper-video.md' \
  'docs/experiments/2026-10-03-ac-motion-restoration.md' \
  'docs/experiments/2026-10-03-c-syntax-animation-review.md' \
  'docs/experiments/2026-10-03-cs101-component-coverage.md' \
  'docs/experiments/2026-10-03-rendering-architecture-evaluation.md' \
  'docs/experiments/2026-10-03-synth-first-speech-failure.md' \
  'docs/superpowers/plans/2026-09-17-quality-70-to-90.md' \
  'docs/superpowers/plans/2026-09-24-multimodal-learning-studio-phase1.md' \
  'docs/superpowers/plans/2026-09-28-ai-material-normalization.md' \
  'docs/superpowers/plans/2026-09-28-multimodal-learning-studio-phase2-decks.md' \
  'docs/superpowers/plans/2026-09-28-multimodal-learning-studio-ppt-quality.md' \
  'docs/superpowers/plans/2026-10-01-progressive-scenes.md' \
  'docs/superpowers/plans/2026-10-01-state-change-pilot.md' \
  'docs/superpowers/plans/2026-10-02-ac-motion-restoration.md' \
  'docs/superpowers/plans/2026-10-02-demo-usage-and-self-study-decks.md' \
  'docs/superpowers/plans/2026-10-02-duration-range-environment-video.md' \
  'docs/superpowers/plans/2026-10-02-paper-video-integration.md' \
  'docs/superpowers/plans/2026-10-03-flow-layout-routing.md' \
  'docs/superpowers/plans/2026-10-03-html-canvas-sample.md' \
  'docs/superpowers/plans/2026-10-03-paper-renderer-repair.md' \
  'docs/superpowers/specs/2026-09-23-multimodal-learning-studio-design.md' \
  'docs/superpowers/specs/2026-10-02-ac-motion-restoration.md' \
  'docs/superpowers/specs/2026-10-02-paper-video-integration.md' \
  'docs/superpowers/specs/2026-10-03-flow-layout-routing.md' \
  'docs/superpowers/specs/2026-10-03-html-canvas-sample.md' \
  'docs/superpowers/specs/2026-10-03-paper-renderer-repair.md' && \
  git commit -m 'docs: 補齊工作台與影片設計的計畫、實驗及交接文件'
test -s video_engine/out/demo3/durations.json && .venv/bin/python -m unittest discover -s tests -t . && node --test tests/web/*.test.mjs

```

## 本次報告驗收範圍

核對 135 檔被 128 個提交檔與 7 個排除檔完整分割，提交清單與腳本逐檔一致，10 個 subject 一致，並用 `bash -n` 檢查腳本語法。來源 `git diff --check` 無錯誤；完成前比對來源 HEAD、Git status、index 雜湊及 135 檔內容雜湊，以確認本次工作沒有改變來源。

