# 現場 Demo 前端 — 執行進度

計畫：`docs/superpowers/plans/2026-08-26-demo-frontend.md`
分支：`feat/demo-frontend`（起點 675e9d4）

Task 1: complete (commits e83adaf..15f1704, review clean — spec ✅, 1 Important + 1 Minor 已修)
Task 2: complete (commits 4f6b37a, review clean — spec ✅, Approved)
  Minor（留給最終審查）：
  - tests/test_run_material.py 沒有 next_free 跳過序號空隙的測試（行為已人工驗證正確，只是覆蓋不足）
  - run.py resolve_material docstring 收尾引號風格與 next_free 不一致（純外觀，且沿用計畫原文）
Task 3: complete (commits a0a08e3, review clean — spec ✅, Approved)
  Minor（留給最終審查）：
  - run.py event(event=...) 函式名與 kwarg 同名，讀起來拗口（沿用計畫原文）
  - 階段編號字串 5 / 5.5 隨重排對調，屬 brief 明文指定的必然結果
Task 4: complete (commits 991d58d, controller-verified — 純文件 3 行 diff，階段順序與無副作用皆自行複驗)
Task 5: complete (commits a9b37d1..767b41a, review clean — spec ✅，1 Important 已修)
  Important 已修：brief 的 claim() 測試是同執行緒循序呼叫，拿掉鎖照樣全綠。
    補了 Barrier + 8 執行緒 × 50 輪的真並發測試，紅綠已驗（無鎖時 4 個同時搶贏）
  Minor（留給最終審查）：
  - jobstate.resume() 不檢查前置狀態，誤呼叫會靜默重跑 synth→video。
    服務層（Task 7）直接呼叫 resume() 前必須自行檢查 claim() 回傳值
  - 五個狀態字串散落在各方法，無中心宣告（可讀性拋光）
  - __init__ / pct / start / review_expired 無 docstring（沿用計畫原文）
Task 6: complete (commits 49cfdfa..8b7e741, review clean — spec ✅，3 Important 全修)
  Important 已修：
  - revalidate 沒檢查退出狀態，validate.py 崩潰時回傳空陣列＝偽裝成通過，閘被靜默關掉
  - 回寫測試只比對數量與 type 序列，非 text 欄位被動到抓不出來 → 改深度比對，紅綠已驗
  - temp 目錄沒清理（違反計畫自訂的約束）
  Minor（留給最終審查）：
  - write_segments 對 slide_id/idx 對不上的 segment 靜默略過，呼叫端無從得知
