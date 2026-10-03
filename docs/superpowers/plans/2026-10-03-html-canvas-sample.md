# HTML Canvas Sample Implementation Plan

Goal：交付20秒可觀看HTML/MP4，實際呈現printf輸出與游標換行，以既有配音比較效果。

Architecture：樣片目錄的scene.html載入theme/timings與兩個Canvas元件，所有視覺由seek(t)計算；Playwright連到本機HTML，等font ready後逐幀截圖送FFmpeg。音軌由既有master裁切與loudnorm形成，未新生成。

- [x] 保存source與audio provenance，生成20秒原音／音量正規化音軌與原稿字幕cue；標示來源語句／ASR近似錨點限制。
- [x] 實作scene.html、timings.js、scene.js、theme.json與本機字型資產；元件layout與連線共用當前幾何，不以各自常數漂移。
- [x] 使用臨時工具目錄Playwright與已快取Chromium，不在專案新增依賴；寫render.mjs，先檢查關鍵帧／reverse seek／端點／可讀性，先3秒，再20秒逐幀輸出。
- [x] 由實際MP4驗解碼、fps、音訊、抽幀與本機瀏覽器播放；保存HTML與MP4、製作時間及0新增Claude/TTS費用。
- [x] 交付可直接觀看URL與MP4，技術驗收與使用者對視覺效果的偏好分開；此為兩元件樣片，不稱元件庫全面完成。


完成：20秒600影格的實際Playwright Canvas樣片、同聲對照與互動HTML。15關鍵幀、600時點、reverse/reload seek、輸出／游標、解碼與播放器已驗。報告`video_engine/out/html_canvas_sample_20261003/REPORT.md`。技術完成不等於使用者已接受美感；未移植正式入口或建立完整元件庫。
