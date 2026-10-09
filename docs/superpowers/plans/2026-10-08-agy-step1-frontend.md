# AGY：第一步前端穩定與驗收

使用者已要求 Codex 與 AGY 共同執行。請在 `/home/pjw92/projects/videomaker` 執行此任務；你是 AGY 前端負責者，Codex 同時負責後端與整合。

先讀 `docs/superpowers/plans/2026-10-08-independent-material-workbench.md`、`docs/superpowers/plans/2026-10-05-learning-workbench.md` 與現有前端程式。舊計畫的產物優先順序以新八步計畫為準；第四步新增 PPT／心智圖優化，不擴大本次任務。這次只做第一步，不新增 Podcast、海報、漫畫或新來源格式。

## 範圍與邊界

- 只修改 `workbench/web/` 及 `docs/agy_results/2026-10-08-workbench-step1-frontend.md`；不要修改 Python、主計畫、舊 `web/`、`studio/` 或 `serve.py`。
- 素材庫、用量頁、API／app／UI／CSS／測試已有未提交工作。先看差異，保留內容，不還原或整檔覆蓋。
- 不 commit、push、安裝新依賴，不呼叫付費模型、TTS 或真實生成，不讀取或輸出 API 金鑰。
- 使用既有 Node 與測試；瀏覽器測試使用 fixture／mock，不能按鈕誤觸真實付費生成。
- HTTP 欄位缺口先寫報告提供實際路由、預期欄位與重現方式，交由 Codex 修後端；不要自行改契約或加入掩蓋問題的假資料。

## 工作與完成標準

1. 記錄現有前端差異，執行 `node --test workbench/web/tests/`；保留實際結果。
2. 檢查總覽、製作四步、流程架構、素材庫、用量與路線圖，尤其素材庫與用量頁目前的未提交整合。
3. 檢查 API 錯誤、空狀態、重試、頁面切換與輪詢清理；檢查完成與未完成產物不被混淆。
4. 檢查影片／SVG／簡報預覽、下載、翻頁、縮放與拖曳；只修阻礙現有流程的具體問題。
5. 如瀏覽器工具可用，用不連外的 fixture／mock 檢查桌面與 375px 窄螢幕；按 repo 規則把視覺偏好留給使用者，記錄功能、越界與操作證據。無工具時明示未驗，不聲稱通過。
6. 修復後執行前端測試及 `git diff --check -- workbench/web/`；測試需覆蓋真實缺陷，不為小文案增加鏡像測試。
7. 寫前端報告：修改檔案、修復原因、測試數與結果、瀏覽器證據、待 Codex 處理的後端契約问题、未驗項目。

完成時輸出精簡摘要與報告路徑。若執行遇到權限或工具阻擋，保存已完成的盤點與明確阻擋原因，不繞過權限、不聲稱已通過。
