# 驗證記錄 · 2026-10-11 · revision 2

最新匯出命令：

```sh
/home/pjw92/.local/share/pipx/venvs/webwright/bin/python prototypes/component_trials_20261011/coherent/verify_export.py --export
```

退出碼 0。`out/report.json`：revision 2、48 秒、1152 幀、1920×1080、24fps；只有影片軌，完整 FFmpeg 解碼成功。MP4 為 1,085,022 bytes，字幕燒入並另存 SRT。所有匯出影格檢查可見文字及所屬固定 panel 邊界、同區文字兩兩碰撞、流程標籤及箭頭的揭露依賴、繁體字形覆蓋；來源與字型 SHA256 通過。

96 次冷啟動／前進／倒序／跨模式的影格比较，教材狀態、輪次、文字、位置、字幕一致；最大 8 像素差、單通道差 2，低於既定瀏覽器邊緣容差 250／24 上限。工程區採固定合成層，降低淡入歷程對 SVG stroke 抗鋸齒的影響；公式與折角的幾個影格有 2–3 像素微差。這個容差不允許教材內容或位置改變。

375／768／1440px 無橫向溢出，HTML 與成片的播放、暫停、seek、重播、末幀字幕、模式保持秒數皆通過，page errors 為空。375px 另外把字型請求暫停，確認 controls disabled、不呼叫未定義 setMode；把 MP4 請求暫停再回切 HTML，確認完成載入後不會把畫面切回影片。

語意模型 5 項 Node 測試通過，包括五輪累加 1/3/6/10/15、第六次判斷 i=6 離開，以及同輪 body/update/return 保持輪次。正式既有 Python 測試 780 項（1 skip）和前端 104 項通過。新增文字檔 whitespace 通過；全域 diff-check 指出既有 workbench styles.css 兩處空白，未動它。

修前以使用者回報的8.4秒重現數值／狀態文字相交，以及流程標籤與箭頭過早出現；新增檢查另抓出44.4／44.7秒公式轉場相交。修後 check_presentation.py 指定影格及全1152幀通過；export 再逐幀檢查通過。數值用獨立 grid row、移除重複狀態區；標籤依首次執行事件揭露，箭頭末端依實際路徑完成度揭露；公式退場／移動／進場分段。

實看章節的 browser PNG、MP4 的8.4與29.3秒修正影格；其他章節與最後影格均重新擷取。美觀、是否需要更強折角效果、是否適合完整教材，交由使用者看片確認。多元風格及既有影片優先／觀看後對話補強的需求記錄在 docs/TEACHING_VISUAL_CUSTOMIZATION.md；本次未接入正式 catalog、AI 自動選用或對話生成。
