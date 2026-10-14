# 第一步：工作台穩定化驗證

日期：2026-10-08。狀態：Codex 修正與免費自動驗證完成；AGY 獨立前端驗收及使用者視覺／內容驗收仍待完成，第一步尚未正式結案。

## 修正

- 教材整理回傳疑點保存於 normalization.json；舊 Markdown 疑點亦可識別。分析、生成、重配及重試在疑點未解決時回傳 normalization_review，避免進入付費流程。使用者核對原稿後以修正文字建立新教材；目前沒有直接解除核對的按鈕。
- 未知費用保存為 null；兼容舊紀錄中 estimated_cost_usd=null 而 usd=0 的情況。用量／素材庫標示已知小計及未知筆數；未知不冒充免費，也不遺漏已發生呼叫。
- 補齊兩個既有前端問答 mock 的 schema 測試登錄。
- 保留既有未提交前端、素材庫與用量頁修改；本輪僅增補費用顯示，未提交／推送，未新增依賴。

## 本輪重新驗證

環境切換後 /tmp 舊紀錄消失，已重新執行，不沿用舊結果。

| 驗證 | 結果 |
| --- | --- |
| .venv/bin/python -m unittest discover -s tests -t . | 704 項，703 通過、1 略過，58.310 秒；OK (skipped=1) |
| node --test workbench/web/tests/ | 76 通過、0 失敗 |
| git diff --check | 通過 |
| 真實 HTTP 網站，1440／375 px 九條主要路由 | 18 項，無頁面／console 錯誤、無水平溢出 |
| 真實 UI | 貼上文字建單元、素材庫問答匹配、用量明細、疑點阻擋；4 項通過 |
| 成品 fixture／mock viewer | 影片載入、心智圖縮放／符合畫面、簡報鍵盤翻頁與 PPTX 下載；兩尺寸共6項通過 |
| 隔離服務重啟 | 4 個單元主要欄位保持一致；未自動生成 |

測試使用 fake runner／固定樣本，無付費模型或 TTS 呼叫。viewer 樣本測試不等於真實生成品質驗收；未檢查實際 PPTX 編輯品質、長影片成片或全部視覺內容。

## 網站與證據

網址：http://127.0.0.1:8765/ （根路由會重新導向）。資料：/tmp/videomaker-step1-preview-20261008/units，從既有單元複製且排除 jobs；原始資料未改寫。服務重啟後 PID 寫在 server.pid。

本文件旁的 workbench-step1-evidence-20261008/ 保存本輪測試 log、browser-report.json、interaction-report.json、viewer-report.json、restart-report.json 及桌面／手機截圖。服務使用暫存資料，系統重啟可能移除；正式部署留第八步。

## 分工與待驗

AGY 以原生 CLI、accept-edits、sandbox 派送，20 分鐘逾時，只回傳局部檢查訊息，未交付驗收報告；不宣稱 AGY 完成。Codex 已完成上表檢查，但不能替代約定的獨立驗收。

尚待：AGY 前端獨立回報、使用者網站視覺／教學適切性確認，以及本計畫清單中未逐項取得證據的非 mock 上傳／生成串接驗收。未驗項目不勾選，第二步尚未啟動。

## 第一步最終收尾（2026-10-08）

後端全量706項測試完成（1項略過）；前端87項通過。新增真實PDF上傳抽取串接與成品MIME／planned格式拒絕測試。AGY獨立前端驗收通過，親自執行87項測試，結果見docs/agy_results/2026-10-08-workbench-step1-frontend.md。原先AGY待回報狀態已解除。真實付費生成品質與Safari／Firefox不在本次驗收證據中。
