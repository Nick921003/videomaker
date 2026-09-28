# 影片動態升級規格（第一輪）

## 目標

讓開場在第一秒出現有意義的動態，換頁時不再讓兩頁文字互相疊影；保留目前語意動作、版位和聲音資料。

## 範圍

1. 僅第一頁且 `role=hook` 時，標題與副標以短距離位移和淡入進場。終點必須與原始 PNG 逐像素同位。
2. 後續頁面以 420 ms 先退到乾淨卡面、再顯示新頁；兩頁文字不在同一格疊色，頁面外框仍沿用既有固定版位。
3. 程式碼走讀現有聚焦效果先測實際影片與時間軸是否一致；只有確認渲染錯誤才改程式。

## 不變量

- `lesson.json` 不新增像素座標；時間軸從 `layout.json` 的實測框取得標題位置。
- `base` 與 `full` PNG 不因影片效果改變；同輸入重跑輸出仍決定性。
- 所有過場色彩取自 theme；不新增依賴，不跑付費 LLM 或 TTS 階段。
- 對沒有 hook、沒有標題框、只有一頁的舊資料，渲染行為仍有效。

## 驗收

- 開場第 0 格沒有標題字，第 600 ms 與原始底圖標題區像素一致；標題只在 `HEADER_BOX` 內移動。
- 換頁過場起點是上一頁、終點是下一頁，中點是只有固定外框的乾淨卡面；任何影格都不把新舊文字直接混合。
- 用同一份已存在的教材與音檔渲染短片 A/B，檢查首秒、兩處換頁和一段程式碼走讀。
- 既有幾何、時間軸及影片測試通過，PNG 決定性與可定址框不退化。

## A/B 後修訂

最初的 32 px 軟邊水平揭露在 22.60 秒截斷新頁文字，還露出舊頁表格色塊。AGY 對三張 A/B 對照圖指出此瑕疵；本機原型也顯示垂直推移會切到整行與圖框，因此換頁改為兩階段退到卡面再進場。這是依實測修正原方案。

## Current sample check

The final `fresh` A/B sample confirms the opening and page transitions at 0.0–0.6 s, 22.4–22.8 s, 47.2–47.6 s, and 62.1–62.5 s. The existing code-focus event times agree with explicit spoken line numbers; no renderer mismatch was reproduced. The visual audit also found a content issue outside this motion slice: page 2 narrates six character-array cells while the figure draws five boxes. That lesson/figure needs editorial correction before using the sample as a teaching release.
