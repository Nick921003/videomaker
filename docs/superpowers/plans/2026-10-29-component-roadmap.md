# 元件化路線（VS Code 之後的五個階段）

> 這份是排程與驗收，不是逐步計畫。每個階段開工時先照 superpowers:writing-plans 寫自己的詳細計畫，因為它們都要用到上一階段做出來的介面（`model.js`／`paint.js`／皮膚轉接），介面定案前寫細節只會重寫。

**Spec：** `docs/superpowers/specs/2026-10-29-vscode-component-design.md`（「之後的元件路線」一節，使用者 2026-10-29 決定全部要做）
**前置：** `docs/superpowers/plans/2026-10-29-vscode-component.md`（階段 0）

## 順序與相依

```
階段0 VS Code ─┬─> 階段1 圖示 ─┐
              ├─> 階段2 手帳元件補粉筆皮膚 ─┼─> 階段3 黑板吃元件目錄 ─> 階段5 白板風格
              └─> 階段4 Windows 設定視窗
```

spec 的編號對照：spec 1＝階段3，spec 2＝階段2，spec 3＝階段1，spec 4＝階段5，spec 5＝階段4。順序依相依關係排：黑板要「只寫分鏡」，得先有夠多元件可挑。

| 階段 | 內容 | 規模 | 需要使用者 |
|---|---|---|---|
| 1 圖示 | 沙漏、鎖、鍵盤、齒輪做成 `icon` 元件的新名字，鉛筆、粉筆、仿真各一版 | 小 | 看圖 |
| 2 粉筆皮膚 | `list` `pipeline` `stack` `vars` `note` `scale` 拆成 model＋paint，加粉筆皮膚 | 大（六個元件） | 看圖 |
| 3 黑板吃目錄 | 黑板分鏡每頁都寫結構化描述，通用轉接取代每支片的 `beats.js`；併入原黑板套件設計 | 大 | 審 printf 重做版 |
| 4 Windows 視窗 | `presets/win11` 做成仿真＋鉛筆兩版 | 中 | 看圖、對真實截圖 |
| 5 白板風格 | 新皮膚一套；分鏡不改，換風格重出 printf 片 | 中 | **先選視覺參考**（花叔或其他） |

## 階段1 圖示

- `catalog.json` 的 `icon.names` 加 `hourglass` `lock` `keyboard`（`gear` 已有）。
- 每個圖示一個 `paint` 函式輸出繪圖指令（同 VS Code 的 op 格式），三種皮膚共用。
- 驗收：`fixtures/icon_full.scene.json` 過量測閘；printf 片 `beats.js` 的 `hourglass`／`drawLock`／`drawKeyboard`／`gearPath` 刪掉改用元件，anchor_check、hyperframes check 過；圖交使用者看。

## 階段2 手帳元件補粉筆皮膚

- 依黑板片常用度排：`list` → `pipeline` → `note` → `stack` → `vars` → `scale`。每個元件一個任務：拆 model／paint，手帳轉接改吃 paint，加粉筆轉接。
- **手帳不准變**：每拆一個元件，既有 fixture 的匯出畫面逐位元組相同（重構閘），不同就是拆錯。
- 粉筆皮膚用 kit.js 的筆畫（`line`、`rect`、`circ`、抖動）把 op 畫成粉筆。
- 驗收：每個元件的 min／full fixture 在黑板轉接下過 anchor_check，圖交使用者看。

## 階段3 黑板吃元件目錄

- `storyboard.json` 的 center／two-col 頁也寫 `objects`＋每句 `do`（與 scene.json 同格式），`storyboard.py` 全部交 `Compiler` 驗證。
- 通用黑板轉接（`video_engine/explainer/chalk/kit/board.chalk.js`）：讀分鏡、排版（置中／雙欄，沿用記憶「版面模板要穩」）、照逐字時間放動作。
- 併入 `2026-10-25-chalk-kit-design.md`：kit 搬到 `video_engine/explainer/chalk/`、`chalk_film.py` 一支指令從分鏡到打包。
- 驗收：printf 片用**零行專屬 JS** 重出，與 b25 並排交使用者審；之後另選一個新題材試做，確認 AI 只寫分鏡就能出片。

## 階段4 Windows 設定視窗

- 照 VS Code 的切法做 `win11` 元件（環境變數、系統內容、搜尋），預設檔已在 `presets/win11/`。
- 驗收：fixture 過量測閘；`env_path_howto` 範例改用新元件；PNG 交使用者對真實截圖。

## 階段5 白板風格

- **開工前**請使用者選視覺參考（`_vendor` 裡的花叔或其他），參考只看不改（記憶 style-library）。
- 新增白板皮膚（筆畫＋主題檔＋語氣對應），手帳／黑板的分鏡一字不改。
- 驗收：printf 分鏡換白板風格重出，交使用者審。
