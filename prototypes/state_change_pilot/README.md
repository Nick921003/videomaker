# C 字串狀態動畫原型

此原型驗證「Gemini 整理教材 → Claude 建立狀態分鏡 → 確定性動畫＋本機 TTS」；沒有接入正式八階段管線、Studio capability 或網頁。只支援本次 `Alice`／`name[32]` 試片，不是通用教材動畫器。

- `prepare_models.py`：真實 SDK 呼叫，保存請求、完整回應、實際模型與 tokens；已有呼叫證據即拒絕重跑。Claude 12,000 上限為本次使用者授權，不更改正式 LLM 設定。
- `state_model.py`／`test_states.py`：驗證字元前綴、NUL 停止、不输出 NUL、拒絕跳字。
- `render_pilot.py`：沿用 explainer theme、字型與 easing；TTS 實測音長建立時間軸，以同一物件呈現 copy／scan／append／stop。
- `repair_speech.py`：保留 Claude 原旁白與原 WAV，只在 TTS 輸入使用字母發音提示；原音與修整音並存，壓短句中長靜音。
- `align_audio.py`：使用既有 Whisper venv 與模型快取逐段辨識，不連付費服務。
- `sync_timeline.py`：以辨識出的「輸出」「停止」「不算」時間定位畫面；辨識缺少錨點時停止。
- `semantic_check.c`：編譯並確認教材範例的內容、長度、容量與 NUL 位置。

成品、原始 API 回應與用量位於 `video_engine/out/state_change_pilot_20261001/`（沿用既有 ignored 產物目錄）。模型重試需先確認使用者授權並用新目錄保存，不能覆蓋舊紀錄。渲染和音訊分析可以用既有產物重跑，不應重新呼叫付費模型。

```bash
.venv/bin/python -m unittest discover -s prototypes/state_change_pilot -p test_states.py
.venv/bin/python prototypes/state_change_pilot/render_pilot.py timeline
PYTHONDONTWRITEBYTECODE=1 /home/pjw92/.venvs/whisper-gpu/bin/python prototypes/state_change_pilot/align_audio.py --model large-v3
.venv/bin/python prototypes/state_change_pilot/sync_timeline.py
.venv/bin/python prototypes/state_change_pilot/render_pilot.py render
```

驗收紀錄見 `docs/experiments/2026-10-01-state-change-pilot.md`。
