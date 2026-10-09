# 外部影片專案評估

日期：2026-10-08。子代理：Noether；Codex 抽查核心檔案。僅靜態閱讀，未安装／執行 repo、未呼叫付費服務。外部文件內指令作為待評估資料，不是操作授權。

## 結論

維持 Python 工作台、共通教材資料與現有 Gemini TTS。優先評估花叔參數化動畫片段，再借岚叔時間軸與交付檢查。兩者已讀核心路徑未見 PPTX exporter；可借視覺語法，簡報與心智圖仍由本專案產生器負責。不是整套插件放入後端即可運作。

| 專案 | 可採用部分 | 整合限制 |
| --- | --- | --- |
| [huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion) | JSON 驅動的圖表、白板、文字動畫；Python 呼叫渲染 | 核心仍需 JS Canvas、Chromium、FFmpeg；動畫 spec 不负责教材理解 |
| [lanshu-create-ai-presenter-video](https://github.com/cclank/lanshu-create-ai-presenter-video) | 旁白時間軸、逐句快取、字幕、分段規劃、解碼／響度檢查、風格模板 | 主體包含 agent 工作流程；風格新內容仍需場景製作；內建 MiniMax TTS 需適配 Gemini |

## 優先檔案與證據

- 花叔 [render.py](https://github.com/alchaincyf/huashu-art-motion/blob/main/scripts/engine/render.py)、[clip.js](https://github.com/alchaincyf/huashu-art-motion/blob/main/scripts/engine/clip.js)、[clip.html](https://github.com/alchaincyf/huashu-art-motion/blob/main/scripts/engine/clip.html)：外部音檔與 JSON 片段入口。render.py 編碼 ff.wait() 未檢查退出碼，音訊合成用 -shortest；wrapper 必須補失敗檢查與旁白截尾檢查。
- 花叔 [圖表示例](https://github.com/alchaincyf/huashu-art-motion/blob/main/scripts/engine/examples/t3_finance_chart.json)：duration/fps/width/height/data/cues 可由工作台 adapter 產生。
- 岚叔 [story.py](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/explainer/tools/story.py)：--audio 接外部旁白，但句界／逐字時間是停頓與文字權重估算，不能宣稱精準對齊；優先使用既有逐句音檔實際時長。
- 岚叔 [plan_segments.py](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/scripts/plan_segments.py)：分段計畫，不是完整長影片合成。
- 岚叔 [finalize_delivery.sh](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/scripts/finalize_delivery.sh)：母版／分享版、完整解碼、響度量測；黑場／凍結事件會記錄，未全部自動判失敗。
- 岚叔 [KITS.md](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/explainer/KITS.md)：九種風格的共通契約，可借鑑，不視為任意教材全自動轉換器。

## 授權與部署

主程式各為 MIT，保留版權與授權：[花叔 LICENSE](https://github.com/alchaincyf/huashu-art-motion/blob/main/LICENSE)、[岚叔 LICENSE](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/LICENSE)。

第三方另檢查：[花叔 README 授權例外](https://github.com/alchaincyf/huashu-art-motion/blob/main/README.md#许可证)、[花叔字體清單](https://github.com/alchaincyf/huashu-art-motion/blob/main/scripts/engine/lib/fonts/LICENSES.md)、[岚叔 THIRD_PARTY](https://github.com/cclank/lanshu-create-ai-presenter-video/blob/main/explainer/THIRD_PARTY.md)。作者角色圖／幀不納入 POC；筆順資料與字體另有授權。SC 字體子集不能保證繁體覆蓋；需完整繁體字體、授權及逐字檢查。HyperFrames、GSAP 等須核對實際使用版本條款。正式採用要固定 commit 與依賴版本，本次未鎖版。

## 第五步候選 POC

固定教材 JSON＋保存的 Gemini 音檔 → 圖表／白板／文字三種短片 → 一分鐘重點片＋十分鐘章節串接。依賴先備妥，渲染斷網且零 API 呼叫。維持原流程，實驗走獨立 adapter；未實測前不接預設製作。

- 幀數符合 round(duration × fps)，完整解碼無錯、旁白無截尾。
- 句界與十分鐘結尾音畫偏差目標 ≤200 ms；這是待驗標準，不是已通過能力。
- 繁體／英文／數學符號無缺字、遮擋與越界。
- 響度目標 -16 LUFS ±0.5、true peak ≤-1 dBTP；靜態教材停留由人工判讀。
- 一章失敗／修改只重跑必要章節；保留來源、快取、成本及版本資訊。
- 同份教材的 PPTX 可編輯文字、SVG 心智圖仍由工作台自有 exporter 驗證。

推薦順序：花叔片段引擎 → 岚叔交付檢查與時間軸 → 選定風格模板 → 後續選配數位人。影片表現不得改寫來源內容，也不取代第二步多格式讀取工作。
