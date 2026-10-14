# 多模態教材工作台產品與架構設計

日期：2026-09-23  
狀態：影片、線上簡報／PPTX 與心智圖的測試站流程已接通；漫畫是下一個新產物  
專案：`videomaker`（獨立驗證），未來整合 BridgeAI

## 1. 決策摘要

本專案由「教材轉教學影片」擴充為「學生閱讀教材時，遇到難懂內容可換一種形式理解」。
**最終主要使用者是 BridgeAI 的學生**：學生正在閱讀課程中已發布的知識點，選擇影片、心智圖、漫畫等形式觀看同一概念的另一種解釋。現有 `videomaker` 網站是功能驗證站，由開發者先用上傳教材測試；不是最終的教師製作後台。

未來入口放在 BridgeAI 的知識點閱讀頁及 AI 互動區。BridgeAI 將目前知識點、學生身分與授權範圍交給 adapter；模型只負責把「這段看不懂，換成心智圖」等意圖轉成受控的 `GenerationPlan`，實際執行仍由白名單能力、版本化模板與確定性的 dispatcher 負責。

第一條端到端路徑沿用現有影片管線，使用者已在網站成功生成影片；影片品質升級由獨立任務處理。
線上簡報與核可後 PPTX 匯出已接通，但真實模型輸出的簡報教學內容與部分瀏覽器尺寸仍待驗收。
心智圖的來源錨定、預覽與 SVG 下載已接通，尚待真實模型教學品質與瀏覽器視覺驗收；未實作的漫畫等型態顯示為「規劃中」，不提供會讓人誤以為可用的假按鈕。

## 2. 目標與成功條件

### 2.1 產品目標

1. 學生閱讀當前知識點時，可選影片、心智圖、漫畫等形式理解同一內容，不必重新上傳。
2. 學生可描述哪裡看不懂；產物需能對回原文及來源版本。
3. 系統先顯示生成內容與成本，經學生確認後才執行付費或耗時工作。
4. 產物可預覽與再次生成；學生私人產物與教師發布的全班版本分開。
5. 新增教材型態時，不需重寫知識點閱讀頁、工作狀態機與 BridgeAI 入口。

### 2.2 第一階段成功條件

- 開啟工作台後可看見來源區、自然語言指令區、能力目錄、計畫預覽、工作進度與產物區。
- 上傳 `.md`、`.txt` 或 `.pptx`，選擇「微課程影片」後，仍可完成現有八階段影片管線。
- 自然語言或快捷模板產生的請求都先正規化為同一個 `GenerationPlan`。
- 未實作能力明確標示狀態與用途，不能送出執行。
- 前端不依賴 BridgeAI，也不新增建置工具或 CDN。
- API 資料結構不含本機絕對路徑，未來 BridgeAI 可以用 topic/source reference 取代上傳檔。

## 3. 非目標

- 第一階段不修改 `/home/pjw92/projects/BridgeAI/BridgeAI-main`。
- 第一階段不實作登入、多使用者、課程權限、資料庫或雲端物件儲存。
- 第一階段不一次完成漫畫、PPTX、音訊、心智圖與互動教材生成器。
- 不讓 LLM 直接產生 shell command、檔案路徑、Python 函式名或任意模板名稱。
- 不依所謂「視覺型／聽覺型學習者」替學生貼固定標籤。
- 不在頁面中假裝尚未完成的產物已可生成。

## 4. 使用者與核心情境

### 4.1 最終主要使用者：學生

學生在 BridgeAI 已發布的知識點頁閱讀教材，遇到難懂的概念、流程或程式碼時，點選「換個方式理解」，選擇可用形式，確認成本後啟動。產物留在同一學習脈絡中，保留對應來源；回到原文或改選其他形式不必重新找教材。

### 4.2 現階段測試者與其他角色

- 現階段測試者：開發者在獨立工作台上傳教材，驗證每種產物與流程；上傳只是測試入口。
- 教師／助教：設定課程可用能力；必要時審核並發布全班共用版本，不是學生每次私人轉換的預設操作員。
- 學生：可使用教師發布的共用版本，也可依課程政策要求個人化轉換；個人產物預設只屬於本人。

### 4.3 代表性指令

- 「這段指標傳值看不懂，給我一支 90 秒的影片。」
- 「用心智圖整理這份教材的概念與關係，讓我能對回原文。」
- 「用六格漫畫演示我常搞錯的觀念，最後解釋正確想法。」
- 「先看簡報版；還是不懂再換成影片。」

## 5. 產品資訊架構

桌面版採三區工作台，手機版改為同一份內容的分頁／抽屜，不建立兩套狀態。

```text
┌────────────────┬───────────────────────────────┬──────────────────┐
│ 教材來源       │ 工作區                        │ 能力與設定       │
│                │                               │                  │
│ 上傳／來源摘要 │ 自然語言指令                  │ 影片             │
│ 對象與限制     │ 「把這份教材做成……」          │ 簡報 / PPTX      │
│ 來源版本       │                               │ 漫畫             │
│                │ 執行計畫預覽                  │ 心智圖           │
│                │ 產物分頁與審核                │ 音訊／互動教材   │
├────────────────┴───────────────────────────────┴──────────────────┤
│ 工作進度：queued → planning → running → awaiting_review → done / failed │
└───────────────────────────────────────────────────────────────────┘
```

### 5.1 教材來源區

- 上傳 `.md`、`.txt`、`.pptx`。
- 顯示檔名、大小、教材 ID、正規化來源摘要與來源雜湊。
- 顯示 normalized text 的短預覽，確認系統讀到的內容正確。
- audience level、教師補充指引與不可更動專有名詞延後到生成器能真正消費這些欄位時再加入，Phase 1 不做
  只有 UI、下游卻忽略的假設定。

### 5.2 自然語言指令區

- 有可見 label，不以 placeholder 取代欄位名稱。
- 顯示可點選範例，但點選後仍形成一般文字指令。
- 先呼叫「規劃」，取得結構化計畫；不在 Enter 後立刻執行昂貴工作。
- 模型信心不足或缺少必要欄位時，回傳 `needs_clarification`，不得自行猜測。

### 5.3 能力目錄

每個能力卡顯示：名稱、教學目的、成熟度、預估資源、是否需要審核。

| 能力 ID | 顯示名稱 | 學生理解用途 | 2026-09-28 測試站狀態 |
|---|---|---|---|
| `video.micro_lesson.v1` | 微課程影片 | 動態解說、程式碼走讀 | 可用；使用者已完成真實生成 |
| `slides.lesson_deck.v1` | 線上簡報 | 分頁、分步理解概念 | 功能已接通；真實教學品質與瀏覽器驗收未完 |
| `pptx.editable_deck.v1` | 可編輯 PPTX | 教師匯出與修改共用版本 | 直接選用仍為規劃中；已核可簡報可下載 PPTX |
| `comic.misconception_story.v1` | 迷思澄清漫畫 | 看見迷思、衝突與正確解釋 | 規劃中；下一個新產物 |
| `mindmap.concept_overview.v1` | 概念心智圖 | 釐清概念、關係與全貌 | 測試站流程已接通；真實模型與瀏覽器視覺驗收未完 |
| `audio.teacher_student.v1` | 師生問答 podcast | 用短對話釐清迷思，可重聽並看逐字稿 | 規劃中 |
| `text.immersive_lesson.v1` | 互動圖文教材 | 分段閱讀、嵌入理解檢核 | 規劃中 |
| `interactive.worked_example.v1` | 引導式範例 | 步驟練習、除錯 | 規劃中 |

### 5.4 執行計畫預覽

執行前顯示：

- 使用哪一個版本化模板。
- 會產生哪些產物及其依賴順序。
- 對象、長度、版型與教師指引。
- 哪些步驟會使用 LLM、TTS 或圖像模型。
- 哪些階段會暫停等待審核。
- 無法辨識或被系統忽略的要求。

### 5.5 產物區

- 以產物分頁切換，不把不同媒體硬塞在同一預覽器。
- 每個產物顯示 `draft / needs_review / approved / rejected / stale`。
- Phase 1 可回到計畫修改並建立新 job；「只重生單一產物」等第二個可執行 capability 出現後再做。
- 影片保留講稿審核、投影片預覽、播放與下載。
- 未來漫畫文字與程式碼由確定性 renderer 疊字，不交給圖片模型畫字。

## 6. 視覺與互動原則

`uiuxpromax` 建議採簡潔、網格化、高對比的專業工作台。專案既有暖色主題已經形成識別，
因此保留 `warm.json`／現有前端的暖米色與陶土色，不改成工具建議的通用青綠配色，避免
同一產品出現兩套品牌。

- 使用系統字型與 `Noto Sans TC` fallback，不載入外部字型。
- 所有 icon-only button 具備 `aria-label`。
- 所有輸入都有可見 label、錯誤文字與焦點樣式。
- 色彩不是狀態唯一線索；狀態同時有文字或圖示。
- 引用、提示與內容卡片不要使用左側彩色直條作為裝飾或分類；以四周一致的淡邊框、底色和明確標題呈現。
- 支援鍵盤操作與 `prefers-reduced-motion`。
- 心智圖成果先顯示完整縮圖；放大視窗提供拖曳平移、縮放控制與符合視窗，關係詞應附於目標概念卡片而不壓在線上。
- 驗收寬度：375、768、1024、1440 px。
- 動畫只用於工作狀態、區塊切換與焦點，不做裝飾性 typewriter 或無限循環動畫。

## 7. 邏輯架構

```text
Source Adapter
  upload:file | future: bridgeai:topic
        ↓
Instruction Request
  instruction + source_ref + learner_context
        ↓
Intent Planner
  LLM structured output（或快捷模板直接建立）
        ↓
Plan Validator
  白名單 capability/template、型別、限制、成本確認
        ↓
Generation Plan（先預覽、後確認）
        ↓
Dispatcher
  capability_id → registered handler
        ↓
Job + Events + Review Gates
        ↓
Artifact Manifest + Validation Report
```

### 7.1 邊界

- `serve.py`：HTTP、multipart、SSE、靜態資源與 legacy route 相容。
- `studio/contracts.py`：資料契約、正規化與驗證；零 I/O。
- `studio/catalog.py`：能力與模板白名單；零 LLM、零 subprocess。
- `studio/sources.py`：不透明 source reference、來源雜湊與本機 material path 的私有對照。
- `studio/plans.py`：保存 server canonicalized plan，對外只提供 opaque `plan_id`。
- `studio/planner_backends.py`：自然語言規劃器的內部接口、規則版與結構化 AI 版。
- `studio/planner.py`：選擇 backend、建立 `GenerationPlan` 並強制通過本地驗證。
- `studio/execution.py`：legacy 與 studio 共用的唯一昂貴工作執行權。
- `studio/video_facade.py`：從既有 `jobstate.Job` 衍生 API 狀態、事件與 artifact；`Job` 是唯一狀態真相。
- `web/`：只消費 API，不知道本機檔案路徑與 subprocess。

現有 `video_engine/` 仍維持影片領域邏輯；新增工作台不得把漫畫、PPTX 或 BridgeAI 權限邏輯
塞進 `video_engine/run.py`。

## 8. 核心資料契約

### 8.1 規劃請求

```json
{
  "contract_version": "1.0",
  "instruction": "做成 90 秒、給初學者看的影片",
  "source": {
    "kind": "upload",
    "ref": "material:c_struct",
    "revision": "sha256:0123456789abcdef"
  }
}
```

未來 BridgeAI 只需把 `source.kind` 換成 `bridgeai_topic`，`ref` 換成不透明 topic reference；
工作台與生成器不直接依賴 course/unit/topic 資料表。`learner_context` 是未來契約擴充；Phase 1
不接受此欄位，避免宣稱會個人化、實際影片卻完全相同。

### 8.2 生成計畫

```json
{
  "contract_version": "1.0",
  "status": "ready",
  "summary": "建立一支初學者 90 秒微課程影片",
  "source": {
    "kind": "upload",
    "ref": "material:7df47c7c",
    "revision": "sha256:0123456789abcdef"
  },
  "steps": [
    {
      "step_id": "video-1",
      "action": "artifact.generate",
      "capability_id": "video.micro_lesson.v1",
      "template_id": "video.micro_lesson.default.v1",
      "options": {
        "duration_seconds": 90,
        "layout": "auto"
      },
      "requires": [],
      "review_gate": "script"
    }
  ],
  "warnings": []
}
```

`status` 只允許 `ready` 或 `needs_clarification`。後者必須附結構化 `questions`，不能直接執行。
`template_id` 與 `review_gate` 由 server 依 catalog 填入；AI 不能選擇或關閉必要審核。
Phase 1 的 `ready` plan 強制恰好一個 video step、`action=artifact.generate`、`requires=[]`；第二個
可執行 capability 出現後才設計真正 dispatcher／DAG。

### 8.3 產物 manifest

```json
{
  "artifact_id": "artifact-1",
  "kind": "video",
  "capability_id": "video.micro_lesson.v1",
  "source_revision": "sha256:0123456789abcdef",
  "status": "needs_review",
  "preview": { "type": "video", "url": "/api/studio/artifacts/artifact-1/content" },
  "download": { "file_name": "c_struct.mp4", "url": "/api/studio/artifacts/artifact-1/content?download=1" },
  "validation": { "status": "passed", "messages": [] }
}
```

## 9. API 邊界

| Method | Path | 用途 |
|---|---|---|
| `GET` | `/api/studio/session` | 取得同源 mutation 使用的短期 CSRF token 與 planner availability |
| `GET` | `/api/studio/catalog` | 能力、模板、狀態、輸入 schema |
| `POST` | `/api/studio/sources` | 上傳並正規化教材，回傳 source reference |
| `DELETE` | `/api/studio/sources/{ref}` | 釋放目前不用的本機暫存來源 |
| `POST` | `/api/studio/plans` | 自然語言／快捷操作轉成待確認計畫，回 `plan_id`＋canonical plan |
| `POST` | `/api/studio/jobs` | 以 `plan_id` 執行 server 保存且已驗證的計畫 |
| `GET` | `/api/studio/jobs/{id}` | 工作快照 |
| `GET` | `/api/studio/jobs/{id}/events` | SSE 增量事件 |
| `GET` | `/api/studio/jobs/{id}/review` | 取得生成中的審核資料，例如影片講稿 |
| `POST` | `/api/studio/jobs/{id}/review` | 提交生成中審核，不等同產物發布核可 |
| `GET` | `/api/studio/jobs/{id}/slides/{slide_id}` | 生成中審稿使用的不透明投影片預覽 |
| `GET` | `/api/studio/jobs/{id}/artifacts` | 該工作的產物清單 |
| `GET` | `/api/studio/artifacts/{id}/content` | 預覽或下載產物 |
| `POST` | `/api/studio/artifacts/{id}/review` | 生成完成後核可或退回產物；Phase 1 不在這裡編輯講稿 |

現有 `/jobs`、`/jobs/{id}/events`、`/approve`、`/video` 在第一階段保留；video adapter 穩定後
才讓新前端完全改走 `/api/studio/*`，避免一次重寫造成既有 demo 失效。

## 10. 自然語言呼叫功能的安全模型

1. planner 只能回傳 `catalog.py` 已註冊的 `capability_id`。
2. options 逐欄驗證，拒絕額外欄位、超界長度與未知 enum。
3. LLM 回傳不等於已授權執行；plan validator 通過且使用者確認後才 dispatch。
4. 所有付費步驟在計畫中可見；不得因模糊指令自動展開成多個昂貴產物。
5. source reference 是不透明 ID；不得讓模型或前端傳本機絕對路徑。
6. handler 由程式碼註冊，不能由模型指定 import path 或 shell command。
7. 相同 source revision、capability、template version 與 options 可形成冪等鍵，未來避免重複扣款。
8. job 建立時重新查 `source.ref`，並重新雜湊目前的 normalized material bytes；record、plan、檔案
   三者 revision 任一不同就回 `409 stale_source`；之後複製成 job 專用不可變 snapshot，runner 只讀
   snapshot，避免「驗完共享檔再執行共享檔」的 TOCTOU。
9. `/plans` 也必須驗證 upload source 存在且 revision 未變；不產生指向不存在來源的 ready plan。
10. 所有 mutation route（包含 legacy `/jobs`）必須先驗 `X-Studio-CSRF`；token 由同源 session API
    取得，不嵌入 HTML。跨來源請求在 TTS probe、snapshot、slot claim 前回 403。
11. public snapshot/event/error 只輸出 `{code,safe_message}`；raw exception、stderr tail、路徑與
    provider error 只寫 server log。

### 10.1 AI Planner 內部接口

前端與生成器不得依賴特定 AI 供應商。工作台只認下列內部語意：

```text
PlannerBackend.plan(
  request: PlanRequest,
  public_catalog: list[Capability]
) -> PlanDraft
```

Phase 1 提供兩個 backend：

- `RulePlannerBackend`：免費、可離線，處理明確單一媒體與秒數；作為 fallback 與測試控制組。
- `StructuredAiPlannerBackend`：接收注入的 `complete_json(system, user, schema)` callable；AI API 的
  Base URL、認證、model 與 wire format 由 transport adapter 負責，不滲入 planner、前端或 catalog。

不論使用哪個 backend，draft 都必須由 server `canonicalize_plan()` 驗證，並從 catalog 補入
`template_id` 與必要 `review_gate` 後才成為 GenerationPlan。AI API timeout、壞 JSON、
未知 capability、額外欄位或超界 options 都轉成結構化錯誤；不回退成「猜一個最像的功能」自動執行。

### 10.2 接入使用者提供 API 時需要的資料

| 資料 | 用途 |
|---|---|
| Base URL 與 endpoint path | 建立 transport，不硬編到 UI |
| 認證方式與 header 名稱 | API key 只讀環境變數，不寫前端或 log |
| model／deployment 名稱 | 可配置、可觀測 |
| request／response JSON 範例 | 正確映射 system、user、schema 與 token usage |
| JSON Schema 或 tool calling 支援程度 | 決定原生 structured output 或文字 JSON fallback |
| timeout、rate limit、錯誤格式 | 明確重試與錯誤分類；planning 預設不自動重試付費請求 |

在上述資料尚未提供前，`StructuredAiPlannerBackend` 可用 fake callable 完成契約與流程測試；真實 HTTP
transport 不列入 Phase 1 完成宣稱，避免假設錯誤協定。

規則 planner 免費；未來啟用 AI backend 時，UI 必須把按鈕標成「用 AI 規劃（會呼叫 API）」並在
呼叫前明確呈現。原本的「先預覽才做付費工作」只適用生成步驟，不能假裝 AI planning 本身免費。

## 11. BridgeAI 整合預留

### 11.1 依據 BridgeAI 目前架構（2026-09-28 檢查 GitHub main `5c8b52f`）

| BridgeAI 現有位置 | 已有責任 | 本專案接法 |
|---|---|---|
| `frontend/pages/courses/[id]/units/[uid]/topics/[tid]/index.vue` | 學生閱讀知識點的頁面 | 在原文旁加「換個方式理解」入口與產物預覽，不複製整個閱讀頁 |
| `backend/app/models/course_content.py`、`backend/app/api/topics.py` | `KnowledgeTopic` 內容、課程成員與 published 可見性 | 由 BridgeAI 伺服器取目前已發布且學生可讀的 topic，不讓瀏覽器傳任意教材文字或本機路徑 |
| `backend/app/services/topic_source_context.py` | 文字教材與其他媒體的來源文字整理 | 建立「學生可用的已核可來源」adapter；不得直接沿用其中在缺少核可時退回 draft 的分支 |
| `backend/app/ai_framework/core/feature_registry.py`、`prompt_manager.py`、`feature_config_resolver.py` | 功能對應提示詞、模型與管理設定 | 日後註冊教材規劃／各生成能力的 feature key，重用現有模型治理；產出模板仍由 studio catalog 鎖定 |
| `backend/app/api/ai_topic_chat.py` | 學生個人知識點對話 session | 可在既有 AI 互動區顯示轉換入口，但生成 job/artifact 是獨立資源，不能塞進聊天訊息當唯一儲存 |

上表是程式碼核對結果與整合設計；**目前兩個系統尚未串接**，也未聲稱 BridgeAI 線上部署已更新到此 commit。
BridgeAI 的「提示詞模板」決定 AI 如何回答；studio 的 `template_id` 決定影片／心智圖／漫畫如何產出，
兩者由受控 feature/capability 對映，模型不能任意指定模板。

### 11.2 學生請求與責任邊界

```text
學生閱讀已發布 KnowledgeTopic
  → 選「換個方式理解」和形式，或描述不懂之處
  → BridgeAI 驗證身分、課程成員、topic 可見性與課程能力政策
  → BridgeAI 建立不透明 source ref（course/unit/topic/revision）
  → studio 回傳受控 GenerationPlan 與成本／審核資訊
  → 學生確認後啟動背景 job
  → BridgeAI 依學生歸屬檢查 job、事件、產物與下載
  → 學生預覽，必要時回看來源或改用另一形式
```

- 學生的私人轉換結果預設只供本人查看；教師要發給全班需走獨立的審核／發布流程。
- 本機 demo 的講稿／內容人工 review gate 是測試與編輯流程。BridgeAI 學生自助模式需另定課程政策與
  自動驗證通過條件，不應要求教師逐筆手動核可，也不能把「生成完成」當成已發布。
- 每次規劃、啟動、查詢、預覽和下載都要重新檢查身分、成員、topic published 狀態、owner 與來源版本；
  topic 更新後舊產物標示來源版本並依政策決定是否可繼續觀看。
- `learner_context` 只放完成任務所需的學習程度與當前困惑；學生姓名、成績、對話全文不預設進 prompt。
- 付費能力由 BridgeAI 課程政策與額度控管；學生確認前列出形式與預期資源，重複請求可用 source revision、
  capability、template version、options 和 owner 形成冪等鍵。

BridgeAI 負責認證、可見性、來源 adapter、AI 功能模型治理、課程政策、持久化 job/artifact 與 Object Storage。
工作台／媒體引擎負責 catalog、計畫驗證、生成、品質檢查和預覽 manifest；不認識 BridgeAI 的 FAB model、
JWT 或 Nuxt component。兩者間維持版本化契約，避免本機 demo 的 in-memory store 成為正式整合依賴。

## 12. 分階段路線

### Phase 1：工作台骨架＋影片垂直切片

- 建立 catalog、contracts、plan preview、artifact manifest。
- 拆分現有單檔前端，完成三區工作台與響應式介面。
- 用 `VideoJobFacade` 接回現有八階段管線與講稿審核。
- legacy 與 studio 共用單一 `ExecutionSlot`；不建立第二套 job 狀態機。

### Phase 2：簡報與 PPTX

- 從同一份結構化內容輸出線上簡報。
- 使用既有 `python-pptx` 輸出可編輯文字、圖形與講者備忘稿。
- 影片可選擇重用已核可 deck，避免再次生成內容骨架。

### Phase 3：心智圖流程已接通，接著做真實內容與視覺驗收

- 第一個交付是「同一份教材 → 概念節點與有標籤的關係 → 可預覽、可下載心智圖」完整流程，
  不只新增 catalog 卡片；節點與重要關係要連回來源原文，方便學生核對。
- 本機上傳、計畫、job、事件、原文定位、預覽、核可與 SVG 下載已接通；35 項相關 Python 測試與 17 項前端測試通過。
- 真實模型的概念／關係／來源忠實度、窄螢幕可讀性及鍵盤操作仍需驗收；不把 fake LLM 流程通過等同學生教學品質達標。
- 分段閱讀與理解檢核另行安排，與 BridgeAI 測驗資料結構保持可映射。

### Phase 4：漫畫與音訊

- 先交付學生可自行選用的迷思澄清漫畫：分鏡 JSON、圖片背景、確定性文字疊加與來源忠實度檢查。
- 再做短篇師生問答 podcast：迷思角色與教師澄清分離，重用 TTS；提供逐字稿、段落定位與原文出處，
  讓學生可重聽或只看文字，不把朗讀整份教材當成 podcast。

### Phase 5：BridgeAI 學生入口與互動式教材

- 在 BridgeAI 知識點閱讀頁接入「換個方式理解」，驗證學生本人、已發布 topic、私人產物與課程額度。
- 透過 BridgeAI 的 AI feature registry／PromptManager 和 studio 的受控 catalog 接線；完成背景任務、
  Object Storage 與獨立教師發布流程。
- Worked example／程式追蹤／除錯挑戰以學生理解檢核為目的逐項加入，不讓任意 generative UI 先行。

### 候選能力（提出想法，尚未承諾排程）

| 學生遇到的困難 | 候選形式 | 與現有能力的關係 |
|---|---|---|
| 想用聽的重整一個概念 | 2–4 分鐘師生問答 podcast，附逐字稿、段落與來源 | 已有 `audio.teacher_student.v1` 規劃卡，可在漫畫後細化 |
| 看不懂程式逐行執行或變數變化 | 可暫停／預測下一步的程式執行圖 | 作為 `interactive.worked_example.v1` 的一種具體實作 |
| 看過影片或心智圖仍不確定自己是否理解 | 2–3 題取回式檢核與錯因回饋 | BridgeAI 已有 flashcard／quiz 功能，優先接其既有資料結構，不重做第二套 |
| 只卡在教材的一句話 | 原文旁的局部解釋、例子或反例 | 優先延伸 BridgeAI 現有知識點 AI 對話，不強迫每次生成完整媒體產物 |

排序依學生實際試用時的理解改善、來源忠實度、生成成本與可及性決定；不以媒體種類數量作為成功指標。

每一 Phase 都要有獨立、可用、可驗證的產物；不得以「先把所有卡片畫出來」代替功能完成。

## 13. 驗證與觀測

### 13.1 工程驗證

- 契約：未知 capability、額外欄位、超界值、stale source 必須明確失敗。
- 正反向控制：合法 plan 可執行；相近但非法 plan 必須被拒絕。
- UI：鍵盤、焦點、錯誤恢復、SSE 斷線、重整與 reduced motion。
- 相容性：舊 `/jobs` 影片流程在遷移期間仍通過既有測試。

### 13.2 教學驗證

- 來源忠實度、學習目標覆蓋、迷思澄清、教師修改時間。
- 不以「產生成功」或「看起來漂亮」當作教學品質通過。
- 每種新媒體先用相同教材做 A/B 人工評估，再考慮學生使用研究。

## 14. 設計模糊點、目前決定與翻轉條件

下列項目仍可能隨實測調整，但不阻擋 Phase 1；目前決定與何時重談均明確記錄：

| 模糊點 | 目前決定 | 翻轉條件 |
|---|---|---|
| 工作台名稱 | 暫用「多模態教材工作台」 | 進入 BridgeAI 對外發布前再命名 |
| 自然語言是否立即使用 LLM | 先完成 provider-neutral AI 接口與規則 fallback；收到使用者 API 協定後另接 transport | API 資料齊全且契約測試通過時啟用 AI backend |
| 來源與 job 是否持久化 | source index、job、artifact manifest 放記憶體；studio 教材、snapshot、examples、out 使用保留前綴，正常關機與下次啟動清理；需保留的 MP4 必須先下載；重啟不恢復 | 需要跨重啟續跑或多人使用時，交由 BridgeAI PostgreSQL＋Object Storage |
| 生成中審核與產物核可 | job review gate 與 artifact approval 分開 | 不翻轉；未來只擴充 review 類型 |
| 前端技術 | 原生 HTML/CSS/ES modules，零建置 | 工作台出現多頁、複雜路由或正式嵌入 BridgeAI 時改由 Nuxt UI 重建外殼 |
| 可用能力 | 測試站中影片、線上簡報與心智圖 `available`；心智圖真實內容與視覺驗收未完；PPTX 直接能力仍 `planned` | 學生使用前完成各能力的教學與權限驗收 |
| 下一個生成器 | 漫畫；短篇師生問答 podcast 是之後的候選 | 學生試用顯示其他理解困難更優先時 |
| 視覺方向 | 保留既有暖色識別，不引入外部字型或 Tailwind | BridgeAI 設計系統正式提供可共用 tokens 時 |
| 並行限制 | 本機同時一個昂貴 job；API contract 不寫死限制 | BridgeAI queue／worker 接手排程時 |
| 本機容量 | 最多 20 個 source／50 MB normalized source、100 個 plan；超過先刪來源或重啟 | BridgeAI 儲存層接手時 |

本節是持續更新的產品決策。若學生自助權限、課程額度或教學成效的實測結果與預設不符，
應先修改設計與驗收標準，再實作對應階段。
