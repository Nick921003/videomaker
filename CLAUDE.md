# videomaker — 專案守則

教材 → 帶旁白的 1080p 教學影片。八階段管線：`lesson → slides → actions → validate → storyboard → synth → timeline → video`。

## 三層契約（動任何東西前先讀懂這條）

| 層 | 檔案 | 職責 |
| --- | --- | --- |
| 內容 | `lesson.json` | 只有語意，**嚴禁任何像素座標** |
| 幾何 | `render_slides.py` → `layout.json` | 畫 PNG，並吐出**實測**的 bounding box |
| 編排 | `compile_timeline.py`、`render_video.py` | 動作只寫語意代號（`p3_code:L4-L6`），座標一律查 `layout.json` |

推論：**改繪製座標，動畫會自己跟上。** `validate.py` 對幾何零假設，`reveal_ms()` 依框面積分級進場時長會自動調整。所以版位可以大改，不必動下游。

`video_engine/layout.py` 是**純函式模組**：零 import、不碰檔案、無副作用。幾何算式住這裡，繪製住 `render_slides.py`。

## 硬性不變量

違反其中任何一條就是 bug，不管測試綠不綠。

1. **`base` 與 `full` 兩張圖的版位逐像素相同。** `hidden` 元素只畫在 `full`，但**版位計算一律含 hidden**。影片的逐條浮現是從 `full` 裁該區域疊回 `base`——版位一旦因 hidden 而不同，裁出來就是錯位畫面。
2. **所有可定址代號都要有量測框**，一個都不能少：元素 id 本身、`{id}:L{n}`、`{id}:i{n}`、`{id}:l{n}`、`{id}:r{n}`、`{id}:caption`。缺一個，指到它的動作**靜默失效**（`resolve_box` 找不到就回 `None`）。
3. **任何輸入都不得溢出所屬區域。** 容不下就縮字級／行距，再不夠就降級版型，最後才明確失敗——不准畫到區域外。
4. **決定性。** 同一份 `lesson.json` 重跑兩次，PNG 逐位元組相同。不得引入隨機或時間相依。
5. **`HEADER_BOX` 與 `CONTENT_BOX` 外框在所有版型中相同。** 換頁是 420ms 交叉淡化，外框一變就會在淡化中互相穿插。
6. **配色只從 theme 檔來。** 繪製器不得寫死任何顏色。`themes/warm.json` 是現用的。

## 幾何工作的紀律

版面的錯**不會炸，只會安靜地畫出一張看起來很正常的圖**。所以：

- **不寫座標常數，寫關係。** `CARD_PAD_X = (CONTENT_BOX[2] - CONTENT_BOX[0] - BULLET_MAX_W) // 2`，不是 `= 55`。
- **一種矩形形狀。** `layout.rect(x0,y0,x1,y1)` 一律吐 `{x,y,w,h}`。注意 `HEADER_BOX`／`CONTENT_BOX`／`CODE_BOX` 這些常數是 PIL 的 `(x0,y0,x1,y1)`——**它跟 `(x,y,w,h)` 都是四個 int，混用不會報錯**。
- **斷言打在產物上，不打在算式上。** 不要拿 `layout.py` 的回傳值去比 `layout.py` 的另一個函式；要把教材真的畫出來、讀 `layout.json`、斷言每個框都在該在的地方。這條抓到過算式測試全綠但圖疊在一起、畫到 y=1090 的 bug。
- **宣稱「純重構」就要逐位元組閘**：五份教材 44 張 PNG 的正規化 md5 必須不變。
- **視覺好壞交使用者判斷**，不自行截圖評價。能保證的是「沒越界、沒重疊、沒掉框」。

## 花錢的階段

`lesson` 與 `actions` 走付費 LLM，`synth` 走本機 GPU TTS。**未經明確指示不要跑這三個階段，也不要在子代理裡設 `E2E=1`。**

`render_slides.py` 完全免費（純 Pillow），所以幾何改動一律用它驗：

```bash
.venv/bin/python video_engine/render_slides.py video_engine/examples/c_loop.lesson.json /tmp/out
```

## 執行環境

- Python 一律用 `.venv/bin/python`，不要用裸 `python`。
- 全套測試：`.venv/bin/python -m unittest discover -s tests -t .`
- 逐位元組回歸基準：

```bash
D=$(mktemp -d); for f in c_loop c_string c_struct c_struct_combo c_struct_v3; do \
  .venv/bin/python video_engine/render_slides.py video_engine/examples/$f.lesson.json $D/$f >/dev/null; done; \
  find $D -name '*.png' | sort | xargs md5sum | sed "s|$D|X|" | md5sum
```

## 風格

縮排 **Tab（4 格）**。註解用**中文**，密度跟隨檔案既有慣例——稀疏但實在，只寫「為什麼」不寫「做什麼」。不新增第三方依賴（現有：Pillow、fontTools、python-pptx）。
