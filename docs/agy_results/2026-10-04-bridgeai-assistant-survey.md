# BridgeAI Platform: AI 助理與學習單元架構調查報告

本調查依據 `bridgeai-origin`（唯讀工作區）的程式碼進行。

## 1. AI Assistant (聊天對話)
*   **前端元件**: `frontend/components/ai/AiTopicChatPanel.vue`，依賴 composable `frontend/composables/useTopicAiChat.ts` 處理 UI 狀態與發送 API 請求。
*   **後端 API**: 位於 `backend/app/api/topics.py`（例如 `topic_ai_chat` 方法），內部呼叫 `backend/app/services/ai_topic_chat.py`。
*   **LLM Provider/Model**: 透過 Langchain 管理，模型路由實作於 `backend/app/ai_framework/core/model_router.py`（支援 openai, anthropic, google, openrouter）。預設模型依序從資料庫 (`Setting` 表) -> 環境變數 `AI_DEFAULT_MODEL` -> 硬編碼 `gpt-4o-mini` (`_get_default_model`)。
*   **系統提示詞 (System Prompt)**: 提示詞存放在 `backend/app/ai_framework/constants.py`（如 `PSEUDOCODE_CONVERT_PROMPT`）。
*   **學習內容接收方式**: 在 `backend/app/services/ai_topic_chat.py` 中，呼叫 `resolve_approved_topic_content(topic)` 取得目前審核通過的文本內容，然後與 `metadata_json` 內含的 `learning_objectives` 等資訊，一同注入 prompt。
*   **工具與函數調用 (Tools/Functions)**: 查無直接讓 AI 呼叫工具的外部 Tool bindings。
*   **對話記憶/上下文**: 歷史訊息由 `AiTopicChatSession` 與 `AiTopicChatMessage`（在 DB）持久化保存，並將最近 `_MAX_HISTORY_TURNS` 傳入 AI（位於 `backend/app/services/ai_topic_chat.py`）。
*   **學生專屬 Context**: 會藉由 `topic.metadata_json["knowledge_unit"]` 中的額外指引，以及 `AiTopicChatSession` 區分不同的 `user_id`（見 `backend/app/api/topics.py`）。

## 2. Learning Units / Knowledge Points
*   **資料模型**: `backend/app/models/course_content.py` 內的 `CourseUnit` 與 `KnowledgeTopic` (存於 PostgreSQL DB)。
*   **儲存位置**: 若 `content_type` 為 "text"，Markdown 原文存於 `content_body`。
*   **IDs 與 Sections**: `id` 為整數 (`Integer`)。層級關係為 Unit -> Topic (`unit_id` 欄位)。
*   **版本控制/Content Hashing**:
    * 在 `backend/app/services/topic_source_context.py` 中的 `build_source_extract` 函式，會為內容生成 SHA256 (`hash`)。
    * 提供 `draft_context` 與 `approved_context` 管理內容審核流程。
*   **頁面渲染方式**: 新版（v2 統一內容模型）會從 `metadata_json` 的 `source_extract` 讀取資料渲染。
*   **學習目標 (Learning Objectives)**: 存放在 `topic.metadata_json["knowledge_unit"]["learning_objectives"]` 屬性內。

## 3. 現有生成或替代解釋功能
| 功能 | 狀態 | 檔案與備註 |
| :--- | :--- | :--- |
| **快速解釋 (換個方式理解)** | **已實作** | `frontend/components/ai/AiQuickExplainModal.vue` 提供選取文字後的解釋。 |
| **Quizzes (測驗)** | **已實作** | `frontend/components/unit/TopicQuizRoom.vue` 等；後端由 `ai_topic_chat.py: generate_topic_quiz_ai_questions` 生成。 |
| **Mind Maps (心智圖)** | **部分實作** | `constants.py` 中允許 AI 輸出 Mermaid 的 `mindmap` 語法，但無獨立生成按鈕。 |
| **Slides (簡報)** | **無生成功能** | `backend/app/services/topic_source_context.py` 僅負責萃取 PPTX 內文供 AI 參考。 |
| **Flashcards (閃卡)** | **已實作** | `frontend/components/unit/TopicFlashcards.vue`；後端由 `ai_topic_chat.py: generate_flashcards` 處理。 |
| **Videos (影片)** | **無生成功能** | `KnowledgeTopic.content_type == "video"` 僅允許外部影片（無 AI 自動生成機制）。 |
| **Homework Helper (作業)** | **已移除** | `git log` 顯示 `fix: rm homework (assistant) (#422)`。 |

## 4. 產出物儲存 (Storage of generated artifacts)
*   **Object Storage**: 使用 Cloudflare R2 / S3-compatible（參見 `backend/app/services/storage.py`）。DB 中僅儲存 Metadata，不存檔案實體。
*   **AI 輸出快取**: 部分生成的結構化資料（如閃卡）會直接快取在 `topic.metadata_json` 中（例：`meta["flashcards"]`，見 `backend/app/services/ai_topic_chat.py`）。
*   **靜態資源派發**: 使用 Signed URL 提供短期讀取權限下載（如 `export_service.py` 內的 `S3_SIGNED_URL_EXPIRY` 邏輯）。

## 5. 角色與權限 (Roles & auth)
*   **身分識別**: 在 `backend/app/api/topics.py` 中，透過 `get_jwt_identity()` 取得 JWT 識別碼，再經由 `_get_membership(course_id, user_id)` 驗證權限，並區分身分（例如 `_is_teacher_or_ta`）。
*   **用量與成本追蹤**:
    * `backend/app/models/ai_usage_log.py` 的 `AiUsageLog` 主要記錄 AI Pseudocode 功能的使用量與內容。
    * 全域追蹤：利用 OpenTelemetry（`backend/app/ai_framework/core/framework.py` 的 `_record_tokens`），自動將 `input_tokens` 與 `output_tokens` 記錄至 `bridgeai.ai.tokens.total` metrics。

## 6. Blog 關聯 (Blog relation)
*   **結果**: **無關聯。** 系統內部完全查無 `blog-assets` 資料夾或任何對外發布功能（Grep 僅在 `AI_Learning_Architecture.md` 提及「檢索權威技術 Blog」）。

## 7. 整合點 (Integration points)
針對**新增「generate/serve video or mindmap for section X」能力**的建議切入點：
*   **Backend Endpoint**: 在 `backend/app/api/topics.py` 中擴增 `@expose("/<int:course_id>/units/<int:unit_id>/topics/<int:topic_id>/generate-multimedia", methods=("POST",))`。
*   **Backend Service**: 在 `backend/app/services/ai_topic_chat.py` 內擴增函式，利用 `get_framework().invoke_with_usage()` 要求 AI 產生腳本或 Mermaid 碼。
*   **Data Model**: 若是影片，可將檔案用 `backend/app/services/storage.py` 上傳至 S3，並存為新的 `KnowledgeTopic`（設為 `content_type="video"`）；若是心智圖則可存入原 Topic 的 `metadata_json["mindmap"]` 中作為快取。
*   **Frontend Component**: 新增按鈕到 `frontend/components/unit/LearningToolsPanel.vue`，並設計如 `TopicAiMultimediaAssistant.vue` 等對話框組件。
*   **Deployment Conventions**: 前端專案位於 Vercel (`frontend/vercel.json`)；後端透過 SSH Script (`.github/workflows/deploy-prod.yml`) 直接部署，若影片生成需依賴 ffmpeg 等系統套件，必須於後端主機環境預先安裝。
