# 三產物優化方案：盤點與對抗審查

日期：2026-10-09。範圍為進度盤點與方案，未修改產生器、未呼叫付費 LLM／TTS、未安裝依賴或提交／推送。

計畫：[`2026-10-09-three-output-quality-roadmap.md`](../superpowers/plans/2026-10-09-three-output-quality-roadmap.md)。

## 獨立審查與裁決

依 `adversarial-review` 技能，由 Codex 唯讀子代理審查，再由主代理核對程式；使用目前協作工具，未假設 agy CLI 或其模型可直接使用。審查判定方向可行，以下四項需補。

| 問題 | 核對證據 | 計畫修正 |
| --- | --- | --- |
| 心智圖可能繼續独立生成另一套例子 | `workbench/run_mindmap.py`、`studio/mindmap.py` 目前各自生成；原方案 C 未明示讀 B 的共同教學規劃 | B 增共用規劃讀取、版本驗證與單次保存；C、D 消費同份規劃 |
| 同句數的不同講稿可能套用舊 timing；關鍵 cue 仍估時 | `video_engine/board/compile.py` 的 `time_beats()` 只核對筆數與時間順序，`anchored_start()` 以字元位置比例定位 | D 納入既有 Board 校準、實際 spoken／聲音／音檔身份綁定及反向控制 |
| 插句或移序導致已有語音重配 | `video_engine/board/narrate.py` 用序號＋digest 命名 WAV，命中還須該位置檔案存在 | E 音訊身份與位置分離，新增插句、移序、compose 與聲音配置失效控制；舊檔相容 |
| 逐項來源可能被舊路徑裁切 | `studio/deck_builder.py` 的 `_narrow_discontinuous_quotes()` 會只保留最長引文片段 | B 新版保留逐項／多段引用，繞過此裁切；不宣稱原文存在即支持整頁主張 |

以上均已補入計畫；這是方案修正，相關程式缺口仍待各批實作。未發現必須換架構或拓展產物才能進行的阻擋因素。

## 本輪驗證

- `.venv/bin/python -m unittest discover -s tests -t .`：735 項、734 通過、1 略過，`OK (skipped=1)`。
- `node --test workbench/web/tests/`：94 項全部通過。
- `git diff --check`：通過。
- 核對計畫引用的 25 個既有關鍵檔案存在；五批未實作工作均未勾選完成。
- 重新閱讀使用者兩個 GitHub 專案的官方 README 與核心參數化渲染／風格／交付檔；僅靜態評估，不宣稱外部引擎已接入或可直接運作。

回歸日誌：`/tmp/videomaker-quality-audit-python-20261009.log`、`/tmp/videomaker-quality-audit-web-20261009.log`。回歸通過不能替代本輪未執行的真實生成、視覺、來源語意與 PowerPoint 手動編輯驗收。
