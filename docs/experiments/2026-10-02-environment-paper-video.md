# 環境建立：紙上動畫試片與片長範圍驗收

> 使用者驗收未通過：本支風格與先前A＋C不符，摘要字幕也未對完整旁白。下列技術檢查不等於視覺／字幕驗收通過；新版修正見2026-10-03-ac-motion-restoration.md。

完成時間：2026-10-02T14:58:37.234336+00:00。原教材是使用者提供的 `環境建立.md`；原檔未修改，副本 SHA256：`545eea43e9220cde60c7f40801623b97e22348fc7ffe021b329380a2211fb110`。

## 交付物

- 修正版 MP4：`video_engine/out/environment_paper_20261002/environment_setup_paper_verified.mp4`，**285.79秒（4分46秒）**、1920×1080、24fps、H264＋AAC、約8.37MiB。
- [直接觀看與下載](http://127.0.0.1:8903/paper-video-test?job=cb622d84c7484cc5ab1e4825864515ac)；這是本機8903測試服務，重啟後工作狀態不保證保留，實際MP4與ledger保存在磁碟。
- 預覽：`verified_preview.gif`、`verified_preview.png`。講稿：`SCRIPT.md`。源分鏡：`board.json`。以上位於同一輸出目錄。
- Windows已用PowerShell Test-Path確認為True：

```text
\\wsl.localhost\Ubuntu\home\pjw92\projects\videomaker\video_engine\out\environment_paper_20261002\environment_setup_paper_verified.mp4
```

## 教材與分鏡範圍

以第一次接觸C的Windows學生為對象。六場、20段：工具分工→MSYS2/VS Code安裝概念→PATH搜尋與驗證→Hello World存檔、編譯、執行→GCC四階段→未存檔與未重編譯的版本差異。沒有把macOS/Linux安裝、所有選項與全部錯誤硬塞進影片。安裝畫面是示意，沒有宣稱實錄安裝成功。原教材末列截斷，略過不完整內容。

前兩場取自目前runtime轉接服務回報Claude模型的完整片段；第一句、程式碼與路徑經本機校正。後四場依原教材本機補寫。`board_provenance.json`與兩次request/response均保存。**本片不是Claude一次完整生成，也不能作為任意教材全自動生成成功的證據。** `scene_source_evidence.json`保存來源段落；canonical_board可定位每個source_quote與code非空行，這不等於每個主張已自動逐項證明。

## 期望片長欄位

`/paper-video-test`加入最短／最長分鐘（預設3／5，可用小數；換算整秒）。範圍為0.5–10分鐘；最短不可大於最長。前端、閉合API、計畫、PaperVideoJob與分鏡請求傳遞同一range；修改欄位使舊計畫失效，晚到回應不能恢復舊計畫。普通影片與PPT入口不接收新range。這是規劃目標，actual_duration與是否在範圍內由語音量測；不以空白湊長。

紙上分鏡專用output cap16384、effort=medium。普通lesson cap仍8192，原已存在的Opus medium預設未改。

## 時間紀錄

本輪總牆鐘時間：**53.0分鐘**，包含新增介面、開服務、失敗診斷、等待使用者決定、本機補稿、兩版渲染與驗收；不是日後單支影片正常生成所需時間。

| 環節 | 實測耗時 |
| --- | ---: |
| 教材整理請求（JSON解析失敗） | 20.63秒 |
| 首次分鏡請求（截斷） | 80.67秒 |
| 重試（相同response ID） | 0.072秒 |
| 本機TTS所有69次請求，含失敗與重製 | 195.68秒 |
| 初版影片渲染 | 163.22秒 |
| 修正版影片渲染 | 163.95秒 |
| ASR全文、片段與修正版核對合計 | 251.13秒 |

各環節可能平行執行，不能將此表相加當作總牆鐘時間。`production.json`保存原始秒數。

## 用量、估值與帳務限制

**以下只是回報tokens乘官方名目單價的參考估值，不能視為使用者帳戶實扣。**

| 回報模型 | 輸入 | 輸出（含思考） | 合計tokens | 名目估值USD |
| --- | ---: | ---: | ---: | ---: |
| Gemini 3.8 Flash，整理失敗仍列入 | 6134 | 6806 | 12940 | 0.030123 |
| Claude Opus 5.5，首次截斷 | 12004 | 8192 | 20196 | 0.211856 |
| 唯一回應用量合計 | 18138 | 14998 | **33136** | **0.241979** |

Claude原JSON另回報5941 thinking tokens，已包含在8192輸出內，不重複加總。SDK ledger未讀到該細項，本機報告由原response補記。

重試建立了medium/16384參數，但回來的response ID、content與usage完全相同；不把同一回應再算成一份新的唯一用量。若單純將兩次回報相加，參考估值為US$0.453835，這也不是已確認費用。`usage_including_duplicate_report.json`保留原始兩次回報，`usage.json`按唯一回應列示。無供應商帳單，無法確認重試實扣。

查證SDK實際base URL為runtime提供的localhost轉接；專案.env未設定ANTHROPIC_BASE_URL，環境已有的同名key與專案key不同，load_env的setdefault不會覆蓋它。離線測試證明程式建立medium/16384參數，但缺第二次HTTP body／server request-id，不能判定轉接故障原因或Claude官方故障，也不能證明本輪直接使用專案金鑰。`retry_diagnosis.json`保存不含密鑰的查證結果；本輪未改.env。

名目單價來源：[Anthropic模型價格](https://platform.claude.com/docs/en/about-claude/pricing)、[Gemini API價格](https://ai.google.dev/gemini-api/docs/pricing)，2026-10-02查閱。Opus輸入4／輸出20 USD/百萬tokens；Flash當日輸入0.75／輸出3.75 USD/百萬tokens。

本機GPT-SoVITS共**69次**請求，包含1次低峰值失敗；20段最終語音，最後兩段另外重製。外部TTS API費用0；未估計電費、硬體折舊、Codex對話或轉接服務可能的收費。

## 語音與同步驗收

原始旁白325.46秒，採atempo=1.138503保留音高後，最終音軌285.778秒。WAV、字幕、動畫依每段實測長度排程；這是段級同步，不是逐詞強制對齊。短句重製與改稿保留在ledger，不覆蓋原始fragment WAV。

首版音長、峰值與靜音閘合格，ASR仍發現最後兩段疑似漏句。把兩段縮短、按完整句分開合成後，修正版ASR可辨識存檔讓磁碟變版本三、執行檔仍版本二，以及重新編譯/執行後輸出版本三。其他段落仍有術語近音與末句截短疑慮；**沒有人工聽感認證，不宣稱逐字發音正確或TTS一次成功。** `asr_verified_version.json`保留辨識原文與限制。

目前TTS穩定自動化仍未驗收。下一輪應固定自然句分段、術語讀法、關鍵內容對稿、有限的段落重試與失敗保存，再以同組測試稿比較設定；不應只用音長合格作為出片標準。

## 已完成的檢查

- Python401項，400通過、1略過；前端30項通過，ES modules語法與git diff --check通過。沒有commit或push。
- 時間欄位9項流程與4項小數／未四捨五入邊界控制；正常page拒range、paper page接受並保存range。真實瀏覽器覆蓋1440／375px。
- 修正版FFprobe、全片解碼、20個實際影格對照timeline、正反seek決定性、layout量測框在panel內；最小正文約32.1px。視覺偏好與學生理解成效留待使用者驗收。
- 真實Chrome能載入及播放修正版，下載Range返回206，1440／375px無水平溢出。Windows Test-Path=True。
- 用本機Linux GCC編譯Hello World與版本二／版本三正反控制，符合未存檔、存檔未重編與重編後輸出差異；不宣稱已實測Windows安裝。

證據：`verified_ffprobe.json`、`verified_decode.log`、`verified_media_checks.json`、`player_browser_checks.json`、`range_browser_checks.json`、`range_fraction_checks.json`、`semantic_qa/checks.json`、`windows_access.json`及tts/asr ledgers。
