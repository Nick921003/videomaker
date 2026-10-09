# 第二步：共同來源資料與多格式讀取

2026-10-08，執行既有八步計畫。Codex後端與AGY來源頁共同完成本批實作；未加套件、未commit、未呼叫真實模型／TTS。

共同契約material.json版本1，content_version為完整正文SHA256。來源按原檔SHA256保存，各份原檔、抽取稿與來源定位均保留。同正文不同原檔會合併來源而不覆蓋；舊單元只讀Markdown fallback並標derived_from_legacy，不推測原檔或批量改寫。GET /api/v1/units/:id/material讀取契約；原檔可由來源相對path對應既有media路由下載。

PDF定位頁碼、PPTX定位投影片；DOCX定位本文段落／表格列、CSV定位列、XLSX定位工作表／儲存格；非分頁文件不宣稱原稿頁码。JSON節點保留整理文字、已核對引文、圖表觀察、疑點。來源雜湊與正文版本、來源路徑／節點引用在讀取時檢查；來源或版本異常在付費分析前409拒絕。

後端上傳接受PDF/PPTX/DOCX/XLSX/CSV/MD/TXT/PNG/JPG/JPEG；前端MD/TXT維持文字直存，其餘先抽取摘要、確認後才模型整理。OpenXML讀取有ZIP/XML/文字大小限制；保留表格空值及原始數值字串，Excel公式與快取明確分開，不重算、不推論日期格式。DOCX圖片、公式、頁首頁尾及未支援內容、XLSX圖表／圖片標待核對；需要完整視覺內容時另附PDF。圖片驗實際格式、像素上限，再轉一頁PDF沿用視覺接口。純圖片辨識標待核對原圖，不能當成已逐字驗證。

證據：tests/test_workbench_source_document.py、material.py、ingestion.py與server/runners測試。新格式真實HTTP＋fake模型跑上傳→確認→整理→原檔下載，驗證原檔逐位元組一致，無付費呼叫。Chromium桌面1350×700／手機375×900實際上傳DOCX/XLSX/CSV/PNG，摘要顯示、人工確認前零整理請求、無頁面錯誤／橫向溢出。證據在workbench-step2-evidence-20261008。AGY親自更新來源頁及測試，88項前端通過：docs/agy_results/2026-10-08-workbench-step2-source.md。

本批不宣稱所有Office特性完整解析；舊DOC/XLS/PPT需另存現代格式。模型內容準確性、OCR與付費視覺整理品質尚未實際付費驗收。第三步消費者完整接入另有計畫。

## AGY審查後修正與判定

- 核對恢復：新增POST units/:id/review，要求confirmed=true與精確content_version；保留疑點紀錄，寫確認者／時間／來源ID集合。原稿或来源集合改變即失效；網站能開原檔、讀全文並確認。修改內容另建教材，source_ref保存原單元版本，原資料不刪除。手機畫面改自然捲動，修正核對區裁切。
- TXT/MD上傳整理不預先把整理稿當原始來源（persist_plaintext=False）；實際HTTP原檔逐位元組讀回測試加入TXT/MD。前端直接讀文字則以fatal UTF-8解碼保留BOM／CRLF，source_kind跟隨原副檔名。
- 換行問題是Python read_text的通用換行轉換造成；共同資料改read_bytes().decode，維持既定精確版本身份，不以放寬雜湊掩蓋變更。
- 圖片上傳即轉PDF做大小預檢，超量413，不送整理工作。原先轉檔失敗也發生在模型呼叫之前，AGY所述「已付費」不準確，但確實應提前提示，已修正。
- DOCX保留content control、軟換行／表格段落分隔；不支援附加內容仍明示待核對。XLSX保留空shared-string與布林／錯誤型別，不把公式快取當重算結果。
- 抽取blocks各有ID，sections保存source_block_ids關聯；非分頁原稿不猜頁碼。第三步source_context只含ID／定位，引用來源仍為正文，沒有引入第二套文字。
- CLI簡報／心智圖用共同generation_material，在模型前檢查版本、原檔與review。
- media原檔下載是本機單使用者追溯來源的既定功能；不在本步把它當公開多人服務。第八步部署需按實際部署界線驗收。

第二步最終：726項後端測試（1略過），89項前端通過；browser-upload/review-browser證據通過。新加入程式與既有檢查均未呼叫真實付費API。
