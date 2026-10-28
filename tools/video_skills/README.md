# nick/：videomaker 的影片工作流

這個資料夾由 videomaker 專案的 `tools/video_skills_sync.py` 自動同步，**不要在這裡直接改**（下次同步會被蓋掉）。
來源版本記在 `SYNC.json`。流程說明與架構圖見 [`docs/影片製作流程說明.md`](docs/影片製作流程說明.md)。

## 依風格看

| 風格 | 狀態 | 從哪裡看 |
| --- | --- | --- |
| 手帳版 | 較穩定 | `video_engine/board/`（說明 `video_engine/board/README.md`、元件 `COMPONENTS.md`） |
| 黑板版 | 調整中 | `video_engine/explainer/`（黑板套件 `chalk/`、分鏡 `storyboard.py`、旁白 `f5_story.py`、同步 `sync_film.py`）；完整範例 `examples/printf-chalk/` |

## 可以單獨拿去用的模組

| 模組 | 做什麼 | 依賴 |
| --- | --- | --- |
| `tts_f5/` | F5-TTS 旁白：台灣口語轉寫、讀音表、切段、快取 | f5-tts、pypinyin、soundfile |
| `tts_f5/pick.py` | 多 seed 自動挑一版：兩種 ASR（拼音比對）＋句尾音高＋語速，全部不及格才標可疑 | 打分只要 numpy；ASR 與音高套件只在 GPU 機器上用 |
| `video_engine/explainer/storyboard.py` | 分鏡表 → 講稿、分頁、審稿用的每頁一句話骨架 | 無 |
| `video_engine/prompts/narration_style_tw.md` | 台灣老師口語旁白規則（擋 AI 腔、不念畫面符號） | 無 |

## 範例：printf 黑板片

- `examples/printf-chalk/story/storyboard.json`：分鏡表（唯一手寫的檔，其餘由它產生）
- `examples/printf-chalk/film/`：HyperFrames 影片專案（`beats.js` 是畫面，`index.html` 是風格）
- 影片、音檔不在 git（字型子集有附）；要重建見 `film/CLAUDE.md`

## 測試

```bash
cd nick && python -m pytest tests -q
```

參考過的專案、論文、工具記在 [`docs/參考紀錄.md`](docs/參考紀錄.md)。
