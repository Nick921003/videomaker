# 黑板片（從 explainer/chalk/starter 開的）

- **每支片自己的只有 `beats.js` 和 `assets/audio/`。** 電腦畫面（`story.screens`）與置中／雙欄頁（`story.boards`）都寫在分鏡
  `storyboard.json`，由共用轉接照逐字時間畫；`beats.js` 維持空樣板。分鏡畫不出來的東西才寫進 `beats.js`。
- `index.html` 是風格層（黑板、板擦換頁、鏡頭、報頭、複習頁），只有要改風格才動它。
- `lib/`、`captions.srt` 是產生的：改分鏡 → `storyboard.py` → 配音 → `video_engine/explainer/sync_film.py <story> .`，不要手改。
- 每一格都是 t 的純函式：不准 `Math.random`、`Date.now`、網路抓取。
- 出片前三道閘都要 0 錯：`node <repo>/video_engine/explainer/chalk/screen_check.js .`、
  `<webwright python> <repo>/video_engine/explainer/chalk/board_check.py .`、`npx --yes hyperframes@0.8.81 check`。
- 配音與渲染只在 Colab 跑。細節見 `STARTER.md`。
