# 現場 Demo 前端 — 執行進度

計畫：`docs/superpowers/plans/2026-08-26-demo-frontend.md`
分支：`feat/demo-frontend`（起點 675e9d4）

Task 1: complete (commits e83adaf..15f1704, review clean — spec ✅, 1 Important + 1 Minor 已修)
Task 2: complete (commits 4f6b37a, review clean — spec ✅, Approved)
  Minor（留給最終審查）：
  - tests/test_run_material.py 沒有 next_free 跳過序號空隙的測試（行為已人工驗證正確，只是覆蓋不足）
  - run.py resolve_material docstring 收尾引號風格與 next_free 不一致（純外觀，且沿用計畫原文）
Task 3: complete (commits a0a08e3, review clean — spec ✅, Approved)
  Minor（留給最終審查）：
  - run.py event(event=...) 函式名與 kwarg 同名，讀起來拗口（沿用計畫原文）
  - 階段編號字串 5 / 5.5 隨重排對調，屬 brief 明文指定的必然結果
Task 4: complete (commits 991d58d, controller-verified — 純文件 3 行 diff，階段順序與無副作用皆自行複驗)
Task 5: complete (commits a9b37d1..767b41a, review clean — spec ✅，1 Important 已修)
  Important 已修：brief 的 claim() 測試是同執行緒循序呼叫，拿掉鎖照樣全綠。
    補了 Barrier + 8 執行緒 × 50 輪的真並發測試，紅綠已驗（無鎖時 4 個同時搶贏）
  Minor（留給最終審查）：
  - jobstate.resume() 不檢查前置狀態，誤呼叫會靜默重跑 synth→video。
    服務層（Task 7）直接呼叫 resume() 前必須自行檢查 claim() 回傳值
  - 五個狀態字串散落在各方法，無中心宣告（可讀性拋光）
  - __init__ / pct / start / review_expired 無 docstring（沿用計畫原文）
Task 6: complete (commits 49cfdfa..8b7e741, review clean — spec ✅，3 Important 全修)
  Important 已修：
  - revalidate 沒檢查退出狀態，validate.py 崩潰時回傳空陣列＝偽裝成通過，閘被靜默關掉
  - 回寫測試只比對數量與 type 序列，非 text 欄位被動到抓不出來 → 改深度比對，紅綠已驗
  - temp 目錄沒清理（違反計畫自訂的約束）
  Minor（留給最終審查）：
  - write_segments 對 slide_id/idx 對不上的 segment 靜默略過，呼叫端無從得知
Task 7: complete (commits f853122..81a3cad, review clean — spec ✅ Approved，2 Important + 3 Minor 全修)
  Important 已修：
  - 三個背景執行緒目標無例外防護，炸掉會讓 status 永遠停在 running → 之後每個上傳吃 409，整台停擺。
    加 _guard 把失敗寫回 job，紅綠已驗
  - 測試清理在斷言之後才做，斷言失敗就留垃圾檔 → 改 addCleanup
  Minor 已修：tts_ready 回應未關閉、has_backup 只寫不讀、_approve 未走 job.clock()
  Minor（留給最終審查）：
  - real_runner 實作簽章 (material, sec) 與 brief 文字 (material, out_dir, sec) 不一致（功能無害，out_dir 由 run.py 自算）
  - test_計時器不可在持鎖狀態下同步跑管線 用字串比對驗結構，技法脆弱（brief 自帶）
Task 8: complete (commit 65e9ff7，AGY 交付 + Claude 收件檢查與邏輯驗證；視覺待使用者確認)
  七項驗收我自己重跑全過：零純白純黑、零外部資源、倒數警語在、EventSource onerror 有、
  零空格縮排、八個階段 id 齊、五個端點齊，且引擎檔案未被動
  Minor（留給最終審查／使用者）：
  - queued 狀態未處理（job 剛建立那一瞬間）
  - 倒數用瀏覽器 Date.now() 對比伺服器 deadline，跨機時鐘偏移會失準（本機 demo 無影響）
Task 9: complete (commits 3e01b8b..8a6a123 + E2E 路徑修正，controller-verified)
  修掉三個計畫缺陷：
  - E2E 用舊 fixture 簽章，照原樣跑會在建檔時炸
  - 回歸檢查 | grep; echo $? 取的是 grep 退出碼且只 pipe stdout → 崩潰時偽裝成通過。
    改成真的 unittest，紅綠已驗
  - E2E 硬寫衍生路徑，lesson_id_for 剝底線導致找不到產出（產品是對的，測試錯）
  付費 E2E 實跑通過：pptx → mp4，1920x1080 h264+aac 57 秒，89.7 秒跑完，清理無孤兒
全部 9 個 Task 完成。43 個測試（1 個付費 E2E 預設 skip）。

=== 最終全分支審查（opus）完成 ===
判定：Fix first。6 個 Important 全修 + 2 個被升級的 carried-forward。
已修：
- real_runner 扔掉所有 stderr 診斷（spec 第 168 行明文要求，規格→計畫就掉了）
- 重驗退回會洗掉操作者剛改好的講稿（審稿閘唯一的錯誤恢復路徑摧毀恢復所需的上下文）
- _approve 的同步段沒被 _guard 保護，例外會讓服務永久卡死
- 錯誤回應不排空 request body，大檔上傳時 503/409 訊息可能到不了瀏覽器
- E2E 漏清 examples/*.json 兩個孤兒（examples/ 不在 gitignore 內）
- test_regression 依賴 gitignore 的本機產物，全新 clone 會 ERROR → 改 skipUnless
- jobstate.resume() 無前置檢查（approve() 護欄只有測試在用，生產走旁邊）
- test_serve 用原始碼字串斷言結構，是一則無法失敗的測試 → 改行為測試，紅綠已驗

接受為技術債（審查已逐項裁定，未修）：
- 衍生路徑佈局在 5 處各自重新編碼（建議日後收斂成 ingest.artifact_paths）
- stage_fail 後 Popen 未 kill（目前 run.py 自己會死，但不變量守在 Job 而非子行程）
- serve.py 依賴 urllib.request 的匯入副作用取得 urllib.error
- SSE catch 的 OSError 過寬，會吞掉區塊內任何 OSError
- STAGES[].weight 是死資料，且 HTML 標記另有第三份百分比副本
- 被拒絕的上傳會在 materials/ 留下孤兒
- 內嵌 <video> 播放器超出 spec 的 YAGNI 清單（唯一一處越界）
- spec 的 SSE payload 契約已過時，應回填
- next_free 序號空隙、event(event=) 命名、狀態字串無中心宣告、四個方法缺 docstring

=========================================================
第二輪：技術債處理
計畫：docs/superpowers/plans/2026-08-26-tech-debt.md
分支：feat/demo-frontend（延續，起點 94730fb）
債 Task 1: complete (commit 5049a5a, controller-verified)
  子行程生命週期：spawn/reap/kill_children/shutdown。real_runner 的迴圈包進 try/finally，
  generator 被丟棄時靠 finally 收掉子行程；serve_forever 加收尾。
  紅綠已驗（kill_children 換成 0 → test_shutdown 變紅 AssertionError: 0 != 1）
  實作者兩處偏離皆正確：reap 補 p.stderr.close()、測試補 addCleanup(srv.server_close)
  53 個測試，無 sleep 孤兒殘留
債 Task 2: complete (commit 25f77de, controller-verified)
  回歸測試改讀 tests/fixtures/regression/ 的委交 fixture，skipUnless 全移除，兩則現在真的跑。
  紅綠已驗（關掉 settle_starts → 兩則都紅並印出「settle_starts 沒排開」）
  過程中擋下一次真實洩漏：c_struct/durations.json 有 16 筆指向 /home/pjw92/projects/GPT-SoVITS，
  scrub() 只剝本專案 ROOT 認不得跨專案殘留。實作者依指示停下回報而非手改 JSON，
  改的是產生器不是資料——否則下次重跑又會洩漏一次
  已對 git blob（非工作區）逐檔查證：四個 fixture 零絕對路徑
債 Task 3: complete (controller 直接執行——前一個 agent 因 session limit 中斷且未留下改動)
  SSE 契約逐欄對著 serve.py 核實後改寫（初版 spec 的 msg 欄位根本不存在）
  內嵌播放器移出 YAGNI 並記下翻轉理由與代價
  新增「刻意不處理的技術債」節：9 項拒絕理由 + 2 個被推翻的論斷
技術債三個 Task 全部完成。53 個測試。

## 版型多樣化（plan: 2026-08-26-slide-layout-variation.md）
Task 1: complete (commits b523450..c8a0f00, review clean)
  Minor（plan-mandated）：render_slides.py 匯入了 CARD_PAD_X／bullet_metrics 但沒用到。
  處置：Task 2 起把匯入清單收斂成「實際用到的」，不做前瞻匯入。
Task 2: complete (commits c8a0f00..5517016, review clean after one fix round)
  Review 抓到 plan-mandated 缺陷：_stack 用 bullet_metrics 的自適應行距算高度，
  但繪製迴圈仍以固定 BULLET_STEP 遞增，7 條起分歧（738 vs 768）。
  已修（退回固定行距）＋ 加回歸測試，計畫的 Task 3A 也改成兩處必須同時換。
  Minor：新測試用裸 assertEqual 而非 subTest，診斷廣度略窄。留給最終審查裁決。
Task 3A: complete (commits 7ddcadc..b911f5a, review clean after one fix round)
  Important x2：(a) 三則掛在 TestRegionsStack 的測試因 pick_variant 上線而實際跑去測 split，
  _stack 的垂直邊界與 hidden 不變量變成零覆蓋；(b) 跨模組哨兵被 plan 的範例碼削弱成同檔內自證。
  兩者已修：TestRegionsStack 加 variant 斷言防再漂移、新增真的渲染 7 條條列的端對端哨兵。
  順帶：count_bullets() 收掉三處重複計數；draw_text_block 靠左卻沒給區域改成丟 ValueError。
Task 3B: complete (commits b911f5a..a11f3b5, review clean after one fix round)
  Important：實作自加的「多圖剩餘空間切片」可達且有實測 bug——圖疊在一起、畫到 y=1090。
  根因兩個：fig_height 不知道直排會變高（回傳橫排高度）、切片後又垂直置中吃掉後面的空間。
  已修：fig_vertical() 讓橫直排判準只活在 layout.py 一處；單圖頁原樣傳區域，多圖頁每張只拿自己的高度依序疊；超出 CONTENT_BOX 明確 raise。
  複審用 worktree 做 red/green、75 組參數對帳 fig_height vs draw_figure、44 張 PNG 逐位元組確認改名零行為差異。
  Minor：單圖頁的 _stack 負偏移溢出未補守門；多圖＋caption 未被覆蓋。留給最終審查。
Task 4: complete (commits 25d95e0..d0be36a, review clean after one fix round)
  Important：_stage 把條列帶壓到卡片 40%，但繪製迴圈不看那個上限，compare 頁 4 條時
  最後一條畫到 y=612 落進圖區（576-980）。prompt 規則 4 允許 2-4 條＝產得出來的輸入。
  已修：加從常數推導的容量守門（cap=int(740*0.4)=296，n=3 是 288 過、n=4 是 408 降級）。
  六張 compare 頁全部維持 stage，44 張 PNG 逐位元組不變。
  Minor（留給最終審查）：bullet_metrics 的 +48 是平的高度預算不是量測的字身下緣，
  實測墨跡溢出 0-4px 且與內容有關（結尾「，」多 4px），實作宣稱的「固定 +2px」不成立。
  未越進圖區（中間有 40px 間隙），但 bounds check 從沒查過條列框 vs 文字區。Task 5 補。
Task 5: complete (commits d0be36a..41ad9c7, review clean after one fix round)
  我寫的 test_條列溢出不得侵入圖區 假設文字在圖上方，但 split 是並排（同 y 不同 x），
  24 筆全是誤判。實作者拒絕放寬斷言、照實回報——正確。已改成真正的二維不相交判定，
  並構造真重疊案例證明改後的斷言不是恆真。
  實測 ink_slack(38)=16px，真實語料最糟溢出 4px（c_loop p1 p1_c，結尾全形「，」）。
版型計畫五個 Task 全部完成。114 個測試。

最終全分支審查（Opus）：2 Critical + 5 Important，全數修完（commit f50425c）。
  C1 split 無圖側守門（5 項 steps 溢出 60px）；根因更深：fig_vertical 連滿版寬也翻直排，
     而直排 760px 比整張卡片還高。改成直排只在窄欄啟用 + 補守門。
  C2 caption 被排除在置中高度外（fig_height 算進、draw_figure 自己重算一份漏掉）。
  I1 單圖 stack 零守門（實測 top=-62）；I2 stage 只守條列不守圖；
  I3 stage 守門測試 fixture 太小；I4 變異度測試讀意圖非結果；I5 只查畫布不查 CONTENT_BOX。
  五個突變（M1–M5）全部轉紅，守門確實被測到。
  六條不變量在真實語料上全數成立：239 框零越界、零代號缺漏、外框簽章 1 種、
  hidden 不影響版位、五份決定性。版型分布 stage 6 / split 8 / code 5 / stack 3。
事故：我用 git checkout 還原突變，抹掉 tests/test_render_slides.py 一整輪未提交的改動。
  已全部重寫。教訓：突變驗證一律用檔案備份還原，git checkout 是破壞性操作。
