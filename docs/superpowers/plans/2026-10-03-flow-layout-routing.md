# Flow Layout Routing Implementation Plan

Goal：修復13秒return0位置、跨排連線方向，沿用既有分鏡／旁白重新輸出。

Architecture：依原字級實測flow所有狀態的最大行數，選可讀的最多欄數；單一連線helper提供path/head/索引，metadata與renderer共用。沒有新依賴或LLM/TTS呼叫，不commit。

- [x] 新增實際預覽測試：五個短標籤同列且return0在printf後方；長標籤跨排的實際箭頭尖端與路徑方向一致。先執行並確認因既有問題失敗。
- [x] 修改`video_engine/paper_renderer.py`：flow欄數量測、slot邊界折线路由、方向正確的箭頭、共用metadata。更新相容測試且保留字級／邊界閘。
- [x] 同board/audio產生8–16秒前後短片與13秒實圖。驗收後再輸出1080p整片。
- [x] 執行renderer相關與全套Python測試、diff check。驗收實際編碼幀、整片解碼、AAC音訊一致與瀏覽器播放。
- [x] 記錄時間、US$0新增API費用、更新製作流程的排版／連線／轉場短片驗收規則，交付新版連結。

Review：不能僅靠箭頭AABB判斷折線是否撞節點，需逐段檢查；所有節點狀態參與量測以避免更新時跳版；兩行上限用於短flow標籤，長標籤應降欄數，不改語意。


完成：同資料8–16秒短片先驗後，再出110.89秒整片。455測試通過／1略過；5140連線逐段／箭頭頭檢查、30編碼幀與AAC一致。補字詞完整與單欄明確三行降級。報告：`video_engine/out/c_syntax_flow_fixed_20261003/REPORT.md`。
