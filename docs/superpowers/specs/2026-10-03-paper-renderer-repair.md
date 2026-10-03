# 紙上渲染器修復

使用者已確認診斷並要求修復後直接重新輸出影片。目標素材固定為`video_engine/out/c_syntax_resumed_20261003/board.json`、`timeline.json`、`master.wav`與字幕；不重新呼叫Claude、Gemini或TTS。原影片與素材保留。

修復範圍是實際出片的`video_engine/paper_renderer.py`，不修改正式cards/PPT、PaperBoard契約、模型prompt或講稿。先前原因隔離見`video_engine/out/renderer_audit_20261003/REPORT.md`。

成功條件：

1. 無跨物件來源的值更新採原位、短時間的先退舊字後進新字，不再同時混疊。明確transfer/scan的來源、路徑與停止語意保留。
2. cells中的`#include`、`main()`、`printf()`、`return`保持完整，以實測詞寬調整格寬／字級。中文可自然換行，過長單詞保留可讀性的明確降級。字形／slot／標籤量測與實際渲染共用同一排字。
3. 聚焦程式的step內提示保持可見，退出後保留短暫過渡再退場；opacity與資料側空間保留時間一致，不能遮住資料。使用該step實測音長，不能固定3.6秒截斷。
4. 修復前後board、timeline、字幕、master.wav的SHA256相同。新片110.89秒、1080p/24fps，同一AAC編碼設定，配音來源不變。
5. 實際PNG與編碼幀驗收新舊字不混疊、常用識別字完整、提示持續，以及資料／提示／字形沒有越界或重疊。精確frame index比對；整支FFmpeg解碼與瀏覽器播放通過。

視覺偏好仍交使用者觀看決定，本次修復不宣稱已完全重現專用A＋C原型。新增來源事件／語句錨點不在這次三項渲染器bug修復範圍。
