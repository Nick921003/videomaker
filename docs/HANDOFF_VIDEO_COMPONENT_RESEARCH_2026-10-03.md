# 影片元件模板研究：供 Claude Opus 5.5 參考

查核日期：2026-10-03。使用者希望借用現成影片元件，減少逐一自行製作的時間；目前由使用者的 Opus 工作階段繼續設計，Codex 只負責查資料。

本檔是研究補充，不取代使用者當前指示，也不改動既有分鏡交接的 Deliverables 或驗收路徑。已查官方文件、GitHub registry、部分元件 README 與檔案清單；尚未安裝、執行或接入這些工具。下列適用性與接入成本是根據文件及目前專案結構的判斷，不是已通過渲染驗收的結果。

## 結論與建議順序

有可重用的現成元件，不必把程式碼面板、終端機、流程圖、比較畫面、字幕與一般動效全部從零寫起。

以目前 HTML／Canvas 方向，優先研究 **HyperFrames** 的 HTML 元件及時間控制契約；**Onda** 與 **Code Hike** 可提供程式教學的參考實作，但依賴 React／Remotion，接入或移植需另評估。**Motion Canvas** 適合程式變化與數學講解，採用另一套場景與時間編排模型。

這些來源可以減少重複製作視覺和動效的工作。教學敘事、狀態變化、旁白 cue、中文排版與幾何驗證仍須處理；目前沒有量測可支持「能省多少開發時間或 tokens」。

## 候選來源

| 來源 | 已查到的能力 | 授權與接入關係 |
| --- | --- | --- |
| [HyperFrames](https://github.com/heygen-com/hyperframes) | HTML／CSS／可 seek 動畫轉 MP4；catalog 有程式碼高亮、終端機、流程圖、比較與字幕。 | 專案採 Apache-2.0；最接近目前的瀏覽器逐格輸出方向，但有自己的 runtime 與子場景契約。 |
| [Onda](https://github.com/degueba/onda) | README 列有 code-block、terminal、code-diff、cursor、browser-frame、圖表與字幕；每個元件帶原始碼、schema 與說明。 | 專案採 MIT；元件為 React／Remotion TSX，不能直接貼進 Canvas 繪製函式。 |
| [Code Hike 官方 Remotion 模板](https://www.remotion.dev/templates/code-hike) | 程式碼片段之間的動畫轉換、多語言、主題，以及 TypeScript 錯誤註記。 | 屬於 Remotion 模板；適合參考多行程式走讀與修改，需核對所用模板、套件及引擎授權。 |
| [Motion Canvas Code](https://motioncanvas.io/docs/code/) | 語法高亮、code diff、insert／replace／remove、局部選取，以及字元／選取範圍的 bounding box 查詢。 | [專案採 MIT](https://github.com/motion-canvas/motion-canvas/blob/main/LICENSE)；採 TypeScript 場景／generator 動畫流程，接入成本高於單純借用 HTML 元件。 |

授權來源：[HyperFrames LICENSE](https://github.com/heygen-com/hyperframes/blob/main/LICENSE)、[Onda LICENSE](https://github.com/degueba/onda/blob/main/LICENSE)。MIT 元件不表示其依賴的 Remotion 引擎也是 MIT，請另看 [Remotion 官方授權說明](https://www.remotion.dev/docs/license)。

## HyperFrames：優先可借用的具體項目

已讀取 [registry.json](https://github.com/heygen-com/hyperframes/blob/main/registry/registry.json)，確認下列名稱存在；也確認程式碼高亮、流程圖、終端機與左右比較的目錄包含 HTML 原始檔。名稱存在不等於中文內容或本課程已驗收。

| 元件／模板 | 原始碼 | 本課程的可能用途 |
| --- | --- | --- |
| code-terminal-run | [README 與 HTML](https://github.com/heygen-com/hyperframes/tree/main/registry/components/code-terminal-run) | `gcc --version`、編譯命令、執行程式、結果或錯誤輸出。 |
| terminal-simulator | [HTML 與 demo](https://github.com/heygen-com/hyperframes/tree/main/registry/components/terminal-simulator) | 較完整的終端機操作示意；尚未實跑確認可調範圍。 |
| code-highlight | [HTML](https://github.com/heygen-com/hyperframes/tree/main/registry/blocks/code-highlight) | include／main／printf／分號與註解的局部強調。 |
| code-diff／code-morph | [registry 清單](https://github.com/heygen-com/hyperframes/blob/main/registry/registry.json) | 錯誤程式與修正、虛擬碼到 C 的對應，需確認實際變形邏輯。 |
| flowchart／flowchart-vertical | [橫向流程圖 HTML](https://github.com/heygen-com/hyperframes/tree/main/registry/blocks/flowchart)、[registry 清單](https://github.com/heygen-com/hyperframes/blob/main/registry/registry.json) | IPO、編譯階段、PATH 依序搜尋的視覺起點。 |
| comparison-split | [HTML 與 demo](https://github.com/heygen-com/hyperframes/tree/main/registry/components/comparison-split) | 預期／實際結果、整數／浮點除法、轉型前後對照。 |
| caption-pill-karaoke／caption-highlight | [registry 清單](https://github.com/heygen-com/hyperframes/blob/main/registry/registry.json) | 字幕膠囊或重點詞強調的參考；不必改動已接受的字幕原文規則。 |

### code-terminal-run 已確認的接口

[元件 README](https://github.com/heygen-com/hyperframes/tree/main/registry/components/code-terminal-run) 提供了可直接研究的時間與內容接口：

- 內容 slot 包含一個 command 與多個 output；命令逐字出現，輸出逐行顯示，最後留下新的 prompt。
- `cues` 是相對於元件掛載起點的秒數，可指定各輸出行的出現時間。
- `prompt_glyph`、`cadence`、`accent`、`exit` 可調；預設結尾保留畫面。
- README 說明文字按時間直接求值，使用固定 seed；輸出行預留布局空間，以透明度顯示，避免中途重排。
- 語法色彩由內容中的 span class 指定，並非自動解析 C 語法。
- `code-terminal-run.html` 是可掛載子場景，`demo.html` 是 1920×1080 的示範 host；需要理解 HyperFrames runtime 如何掛載與 seek。

以上是文件宣告，尚未以本專案音訊或繁體中文字型驗證。

## 與現有專案接入時的實際差異

目前樣片在 `video_engine/out/html_canvas_sample_20261003/`。`render.mjs` 使用 Playwright 呼叫 `window.seek(t)`，並以 `page.locator('#scene').screenshot()` 只截取 Canvas。

因此 **HTML 元件不能直接加在 Canvas 外面就期待被輸出**。後續若採 DOM／SVG 元件，需選擇完整場景容器擷取，或改用該工具的原生輸出流程；也需接通元件的時間控制。這是未實作的接口工作，不能把「同樣用瀏覽器」當作已相容。

HyperFrames 官方 README 說明使用 headless Chrome 逐格 seek、FFmpeg 合成，並有多種動畫 adapter；我們的樣片使用 Playwright。可以借用元件而不立即遷移整個引擎，但需逐一確認 runtime 依賴、樣式 token、字型載入與時間單位。

沿用本專案 `CLAUDE.md` 的契約：內容只寫語意，幾何來自實測，箭頭與動作查同一份框與錨點，配色來自 theme。模板若寫死位置或顏色，必須在正式使用前調整；現成模板仍可能發生遮擋與越界。

## 對前三週教材的覆蓋判斷

詳細教材需求見 [前三週教材與元件覆蓋](experiments/2026-10-03-cs101-component-coverage.md)。

- 環境建立／編譯執行：終端機、流程與比較模板能提供不少現成基礎；PATH 的逐一搜尋、找到／找不到與重開終端機後的狀態，仍要編排。
- C 語法／虛擬碼：程式碼高亮、變形、diff 可減少多行走讀的製作工作；自然語言與程式行的對應仍由分鏡決定。
- 變數／運算／型別轉換：面板、數字、比較與流程可以借用；本次尚未查核到可以直接涵蓋 C 整數除法、轉型時機與截斷規則的完整教學元件。
- 操作示範：browser-frame 或游標只能提供視覺外框；若要展示真實 VS Code／安裝畫面，仍需依實際界面，不憑空製作操作位置。

合理方向是借用通用呈現能力，再補課程特有的語意狀態與動作。不必先重做整庫，也不能把套用模板當作任意 Markdown 一鍵影片已完成。

## 供目前 Opus 工作階段使用

此資料可直接用於判斷現有分鏡是否有可借用的元件。若分鏡涉及終端機、流程圖、程式高亮或比較，先查上述來源，再決定借用、移植或自製；不要求因讀到本檔而中斷當前工作或更換框架。

既有環境建立分鏡交接仍見 [HANDOFF_ENVIRONMENT_CANVAS_DESIGN_2026-10-03.md](HANDOFF_ENVIRONMENT_CANVAS_DESIGN_2026-10-03.md)。本研究不新增付費 API／TTS、套件安裝或正式管線修改的授權。

其他可查的模板入口：[HyperFrames Catalog](https://hyperframes.heygen.com/catalog)、[Remotion 官方資源清單](https://www.remotion.dev/docs/resources)、[Remotion README Kit](https://github.com/ofershap/remotion-readme-kit)（MIT；有 CLI 輸入輸出及 before／after 程式比較模板）。
