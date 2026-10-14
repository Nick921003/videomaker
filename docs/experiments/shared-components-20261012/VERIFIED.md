# 簡報流程元件與心智圖層次 · 2026-10-12

這是固定 C 教材的人工驗證基準，不是付費 AI 成品。共同規劃只由固定 callback 提供一次；兩個正式 professional runner 共用同一份快取並產生實際 PPTX/SVG。未修改正式素材庫或代使用者生成影片。

## 重製

```bash
.venv/bin/python docs/experiments/shared-components-20261012/build_demo.py
.venv/bin/python -m workbench.server --port 8877 --out /tmp/videomaker-shared-components-preview-20261012/units
```

預覽：`http://127.0.0.1:8877/web/index.html?rev=shared-20261012#/make/4?unit=b69bfb8c3481`。正式製片服務是 8876；不要混用隔離資料。

## 實際驗證

- Python 全套 `python -m unittest discover -s tests -t .`：790 項，1 skip，無失敗。
- Node 全套 `node --test workbench/web/tests`：101 項，無失敗。
- 新回歸先重現 pipeline 不支援、心智圖不支援關係，以及展開跳到葉節點；實作後通過。測試包括重複階段代號、額外欄位、容量、缺失父節點、循環、自連、無法定位的關係引用，以及舊計畫／成品相容。
- 真實 Chrome 1440×900／375×812：流程前後步、Space／Shift+Space、既有程式走讀、PPTX 與 SVG 真實下載；心智圖兩組分支展開後根／兄弟座標不變、節點不相交、收合保留另一組、兩布局切換；頁面無橫向溢出、無 page error。簡報正文及節點16px。
- 原生 PPTX 16 頁、301 個圖形物件，文字框兩兩不相交，沒有整頁圖片。LibreOffice 24.2 實際轉 PDF；全部 514 個詞的實際文字邊界在頁內。檢查流程四頁圖，連線方向、目前階段與說明正確。
- 8876 從專案既有 `.env` 載入金鑰啟動；只讀 metadata 確認生成／配音模型可存取；Board 免費自檢37份通過。真正前端的文字輸入、單支選擇及生成按鈕可操作，無 mock，驗證時沒有 POST 生成。

瀏覽器報告：`/tmp/videomaker-shared-components-browser.txt`；截圖與腳本位於本次 Codex visualizations 目錄。PDF 及影格位於 `/tmp/videomaker-shared-components-pdf/`；這些臨時路徑不屬於永久成品。

## 邊界

pipeline 共用的是 Board 階段資料；HTML 用逐步閱讀，PPTX 用原生階段頁。六支外部風格樣片、圖表／公式／草圖並未因此全部接入簡報或正式影片。心智圖仍是單父節點樹，沒有跨概念連線。

關係引用存在於教材的驗證，不保證引用在語意上支持每個推導；真實模型內容與美觀仍需另驗。新規劃使用1.1，舊1.0仍可讀；提示／schema變更會在下次製作失效舊規劃快取，不主動重製既有成品。沒有重啟使用者的8876服務。

AGY 對抗式外部審查嘗試未完成；自動核准拒絕外部披露風險，後續以本機契約、回歸及真實渲染驗證完成審查，不把未收到的AGY報告列為通過。
