# 圖示元件

形狀只寫一份（`shapes.js`），三種皮膚共用：

| 皮膚 | 檔案 | 說明 |
| --- | --- | --- |
| 鉛筆（手帳） | `board/runtime/components/icon.js` | 筆畫縮放進元件框，依筆畫長度分配進度，交給 `api.ink` |
| 仿真（文章 PNG） | `svg.js` | `IconSVG.render(name, opts, color, px)`：等粗線、圓頭圓角，顏色由呼叫端傳入 |
| 粉筆（黑板） | `explainer/chalk/kit/icon.chalk.js` | 筆畫依長度分配時間，交給 `api.S`；文字另有 `note.chalk.js` |

## 形狀

`IconShapes.strokes(name, opts) → {strokes: [{pts, w, part, arc}], text?}`。座標在 100×100 格內，四周留邊 8，只畫線不填色；陣列順序就是筆順。`keycap` 必須帶 `opts.text`。`text` 寫組合鍵（`Ctrl+C`）時回傳 `{strokes, texts: [{text, cx}], w}`：鍵帽往右排、中間加號，格子高仍是 100、寬是 `w`（每多一顆加 130），各皮膚照 `w` 把圖示變寬。

## 匯出單張圖

需要有 Playwright 的 Python：

```bash
PY=~/.local/share/pipx/venvs/webwright/bin/python
$PY video_engine/components/icon/export_png.py out.png --sheet --skin flat      # 31 格總表，6 欄
$PY video_engine/components/icon/export_png.py out.png --sheet --skin pencil    # 取 board/fixtures/icon_sheet.scene.json
$PY video_engine/components/icon/export_png.py out.png --name 等待 --skin flat    # 單張；keycap 要加 --text
```

- `--name` 可以寫圖示名稱或任何一個意思，對不到會列出最接近的三個。
- `flat` 的顏色取手帳主題（`themes/notebook.json`）經 `tones.json` 對到的語氣色，`--tone` 選語氣。
- `pencil` 把分鏡編譯、build 到暫存目錄，開播放器跳到最後一刻截一張；`board/export.py` 輸出的是影片，不能拿來出單張圖。
- `chalk` 只出總表，開 `explainer/chalk/tools/icon_sheet.html?t=end`。

## 測試

`tests/test_icon_component.py`：`TestShapes`（形狀）、`TestSkins`（分鏡過量測閘、總表決定性、不寫色碼）。瀏覽器測試在沒有 Playwright 時 skip，設 `E2E_GEOM=1` 就必須真的跑。
