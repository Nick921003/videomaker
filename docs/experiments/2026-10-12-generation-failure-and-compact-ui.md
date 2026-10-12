# 影片生成失敗與製作頁可讀性

## 症狀與證據

使用者自行生成正式單元4f2ef7bf2785的q4；工作88262522b82c44ab8d1cb1fda3cb119c於2026-10-12T14:47:56Z建立，停在共同教學規劃。selftest已完成、storyboard失敗，配音與出片尚未開始。紀錄為 `簡報欄位不符合契約` / `run_teaching_plan.py失敗（結束碼 1）`。舊模型回應未保存，不能重建具體缺失或額外的欄位。

只讀檢查並以mock SDK重現：Google轉接層收到schema，卻只傳application/json MIME，沒有把指定欄位傳給模型。補入GenerateContentConfig.response_json_schema，使用正式共同規劃的完整schema驗證；未修改模型、預算、引用或容量閘。回歸在修正前失敗、修正後通過。無schema的教材整理仍可運作。

原1280×720畫面佇列始於y=883，375×812始於y=2717；長選擇清單、300–480px流程圖與大字／內距將重要狀態擠出畫面。佇列項目的status-failed另套用紅底與紅字，名稱沒有對比。

## 修正

正文14px、標題15px、按鈕13px；狀態、失敗原因、佇列先顯示，流程圖220px。清單可捲動而不撐開整页；有工作時先收合選擇，失敗時只預選失敗項目，仍可展開增選。佇列使用淺底與深色文字。共同規劃欄位錯誤顯示可讀說明，原始錯誤留在可展開的紀錄；「查看失敗步驟」捲到流程圖。

## 驗證與限制

- Python全套790項，1 skip，無失敗；Node全套101項，無失敗。
- 真實Chrome1440×660、1280×720、768×900、375×812：失敗佇列第一屏可見、項目名稱有對比、清單有界捲動且僅q4勾選；選擇／錯誤紀錄展開收合、失敗步驟查看通過，無頁面橫向溢出或page error。
- 瀏覽器驗證沒有POST生成／重試；未重啟8876，原失敗工作與用量保留。
- 尚未代使用者付費重試或產出此影片。schema漏傳已確認修正，但這不等於真實模型的內容、引用、完整製片鏈路都已通過。

實測腳本／截圖位於本次Codex visualizations目录；瀏覽器結果 `/tmp/videomaker-generation-browser.txt`，Python／Node結果 `/tmp/videomaker-final-python-tests.txt`、`/tmp/videomaker-final-node-tests.txt`。固定簡報／心智圖驗證與可重製成品另見shared-components-20261012。
