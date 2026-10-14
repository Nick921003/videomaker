# 通用 A＋C 效果與完整旁白字幕（2026-10-03）

完成時間：2026-10-03T07:23:48.175534+00:00。

## 可測試入口與免費樣片

- [新測試入口](http://127.0.0.1:8913/paper-video-test)：上傳教材、確認AI整理、填期望片長3–5分鐘、預覽計畫、確認生成；之後審核講稿。本機TTS preflight正常。
- [37.22秒新版效果樣片](http://127.0.0.1:8913/paper-video-test?job=1c964a1c018c40589e0299d9fef2340c)。
- [同board／同音訊的舊版對照](http://127.0.0.1:8913/paper-video-test?job=4efd4624f83a47269142a8bf461e776c)；舊版摘要字幕與卡片問題刻意保留作對照，沒有作新成品交付。

本輪新增外部LLM tokens **0**、新TTS **0次**。沿用已接受A＋C字串試片的四段WAV，分割S3成程式／掃描／結果，沒有重新合成。通用PaperBoard為本機受控驗收fixture，不稱為新Claude生成。

## 已接入的效果

- 恢復原參照的奶油格紙、棕黑鉛筆描線、12Hz決定性筆觸微顫；文字與資料不抖動。
- 非code取消永久大矩形卡，cells畫資料格、flow畫有順序節點；text為並列短註，不自動畫箭頭捏造因果。
- 值沿曲線飛入、主角跨scene持續、scan依focus_index停住；明確scan_output可逐格累積輸出前綴，不一次丟入整串，也不靠Alice/NUL關鍵字硬編碼。
- C程式只短暫呈現聚焦行±1（1.4–3.6秒），資料先移到另一側；程式完全退場後資料才平滑回A，避免淡出遮字。多code與data同場超出能力時明確要求分步，不靜默丟掉程式。
- 幾何來自layout／frame_metadata實測，含字形、飛值、指針、箭頭與提示行。長來源飛行使用來源排字；無法容納時明確失敗，不把長字串裁掉。

## 字幕修正

SRT與燒錄字幕取完整step.speech，不再取caption摘要。每cue最多36字並依自然停頓切分，拼接需保留所有非空白字符與標點。

正式TTS把trim/pad後每段PCM的實測局部start/end記為speech_fragments.json；長片段內仍以字量估排、沒有片段資料時以整段WAV估排，明示timing_basis，不宣稱逐詞強制對齊。外帶subtitle_cues也驗ID、時間、step範圍、全文回拼，錯摘要、漏字、多字／反序／越界會拒絕。

新TTS切段保持70字上限與至少12字語境，整份講稿在首次TTS前預檢，避免無中文長尾被孤立送入模型。**本輪未重新測新的語音生成；TTS品質仍需使用者生成後試聽。**

## 驗收結果與證據

- Python443項：442通過、1略過；Node30項通過，ES module語法／git diff --check通過。無commit/push。
- 同一board、timeline、master.wav的新舊1080p H264＋AAC MP4均全片解碼成功。
- 13個實際編碼影格按精確frame index抽取對照render，測量字形／飛值／提示／指針不越界，seek同t逐byte一致。
- 實證C提示與字母飛入同場，提示消失後資料返回；scan輸出Alice並停在第六格，停止格由語意指定排除。
- 修正前抓到C提示fade時遮字，修正後實際24fps的74個提示畫面、1102個資料框無碰撞；另有長50字來源、6值更新只一條explicit transfer、多字符scan值及includeStop正反控制。
- 非程式的水循環fixture已驗flow、scan、source、字幕與幾何，不插入程式提示；僅免費PNG／metadata，不用不同旁白冒充水循環影片。
- 新服務Chromium實際載入播放、MP4 Range206、1440／375px無水平溢出；時間範圍欄位維持3–5預設。

證據於 `video_engine/out/ac_motion_restoration_20261002/`：`accepted_media_checks.json`、`ready_contact_sheet.png`、`ready_player_browser_checks.json`、`after_ffprobe.json`、`before_ffprobe.json`、`speech_fragments.json`、`provenance.json`、`water/checks.json`；測試原始log於/tmp/videomaker-ac-ready-python.log與ready-node.log。

## 模型設定與本輪限制

8913專用服務明確讀取專案.env原設定，不修改.env，保留普通服務與既有工作。離線確認Anthropic/Gemini使用的key與專案一致、SDK host為官方主機；這只是配置檢查，**沒有發出新的模型請求，也不能宣稱官方生成已實測成功**。此專用服務禁SDK額外重試，失敗不默默追加付費，也不改成本機代寫後宣稱模型生成完成。安全bool證據：model_route_configuration.json，不含任何憑證。

新分鏡prompt已指示以資料／流程為主角、一次少量可見物件、程式與資料配對，source_quote只選支持重點的必要引文。效果程式是本機實作；按生成後才由既有模型流程產生新教材分鏡，影片畫面由通用renderer執行。

視覺偏好與新教材端到端效果由使用者本次生成驗收；不把本輪離線fixture通過當作所有教材都已驗收。正式cards與PPT預設未改。原環境建立影片已由使用者否決風格及字幕，不再列為風格驗收通過。

## 重新啟動

```bash
.venv/bin/python video_engine/out/ac_motion_restoration_20261002/start_test_demo.py
```

先確認8913未被既有服務使用。可直接以磁碟MP4檢視，不依賴服務記憶體保留。sample與素材來源在provenance.json。

最後實圖修正：scan圓圈／箭頭／位置與資料共用scale，避讓label實測框；實際85個scan畫面，零label／字形碰撞。最後版本為ac_generic_after_accepted_ready.mp4，已重新編碼、13影格／全片解碼、瀏覽器播放下載驗收。
