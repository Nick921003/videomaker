# 一條流程（文本先定稿、再依風格排畫面）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 寫稿拆成「文本段」與「排畫面段」，黑板變成吃共用 `scene.json` 的一種風格，同一份文本可出黑板與手帳兩支片。

**Architecture:** `author.py` 新增 `script`（產 `<id>.script.json`，只有語意）與 `stage --style`（拿定稿文本＋風格能力表產 `<id>.<style>.scene.json`）。風格能力表是 `video_engine/styles/<style>.json`，提示詞與驗證都讀它。黑板用新的 `scene_to_story.py` 把 `script.json`＋黑板 `scene.json` 轉成下游現有的 story 檔，取代手寫 `storyboard.json`。

**Tech Stack:** Python 3（`.venv/bin/python`、unittest）、Node（黑板 kit 的探針測試）、既有 `board/compile.py` 驗證器。不新增第三方依賴。

**Spec:** `docs/superpowers/specs/2026-11-10-one-pipeline-style-last-design.md`（另讀 `docs/專案目標與使用者.md`）

## Global Constraints

- 文本段的提示詞與 `script.json` 不得出現風格專屬字眼：`紙上`、`手帳`、`黑板`、`粉筆`、`白板`、`鏡頭`。
- 排畫面段不得改旁白：每頁句數、`say`、`spoken` 與 `script.json` 逐字相同。
- 風格不會畫的 type／動作／版面一律退件，不准悄悄換畫法；`show` 做不到的要寫進 `gaps`。
- 換風格不重新合成語音：兩種風格送進 F5 的每句文字相同、共用同一個快取資料夾。
- 付費階段（`plan`／`script`／`stage` 真的呼叫 LLM）、TTS、渲染：**未經使用者當下明確同意不得執行**；測試一律 `patch.object(BA, "call", ...)`。TTS 與渲染只在 Colab。
- 驗證不可失敗開放：檢查自己壞掉（找不到能力表、探針崩潰、沒瀏覽器但 `E2E_GEOM=1`）必須失敗，不能當通過。
- 縮排 Tab；註解中文、只寫為什麼；Python 用 `.venv/bin/python`。
- 每個 task 結尾 commit，不 push、不 merge。commit 前跑 `sync-docs` 技能。
- 舊教材 44 張 PNG 的逐位元組基準不得改變（指令見專案 `CLAUDE.md`）。

## Review Focus

1. **`script.json` 在排畫面之後又被改過**：拿舊的 `scene.json` 出片應該被擋下並說明要重跑 `stage`。→ Task 4（`script_digest`）、Task 5、Task 7。
2. **LLM 回傳的 `say` 只差標點或空白**：應退件並指出是哪一句，不能自動當成相同。→ Task 4。
3. **`--style` 打錯或能力表檔案壞掉**：應明確失敗並列出可用風格，不能退回某個預設風格。→ Task 1。
4. **版面形狀不在能力表裡（例如黑板收到三層巢狀）**：應指出是哪一頁、可用的版面有哪些，不能默默當成置中。→ Task 1、Task 5。
5. **同一小節同一風格重跑 `stage`**：`gaps.jsonl` 不應越疊越多，舊紀錄要被這次的取代。→ Task 4。

---

### Task 0: 提交目前未提交的改動

**Files:** 今天已改未提交的全部（黑板放大、`tts_f5/polyphone.json`、`docs/專案目標與使用者.md`、`docs/參考紀錄.md`、本計畫與規格、交接文件、`docs/devlog/2026-W46.md`）。`board/player/`、`board/timeline.json`、`renders/` 不進版控。

- [ ] **Step 1:** 問使用者是否可以提交（先前只對前兩批說過可以）。
- [ ] **Step 2:** 跑 `sync-docs` 技能；devlog 進度表把「b25」「b24 句尾飄」兩列結案（使用者 2026-11-10：b25 不出），加一段今天的紀錄。
- [ ] **Step 3:** `.venv/bin/python -m unittest discover -s tests -t .` → `OK`。
- [ ] **Step 4:** 分三個 commit：`feat(chalk): 黑板樣式放大 1.5 倍、標註框放不下時收小圖示`、`fix(tts): 「檔」念三聲`、`docs: 專案目標、一條流程的規格與計畫`。

---

### Task 1: 風格能力表與檢查

**Files:**
- Create: `video_engine/styles/chalk.json`、`video_engine/styles/handbook.json`
- Create: `video_engine/style_caps.py`
- Test: `tests/test_style_caps.py`

**Interfaces:**
- Produces:
  - `load_style(style_id: str) -> dict`：找不到或 JSON 壞掉 → `ValueError`，訊息含可用風格清單。
  - `layout_id(layout: dict, style: dict, objects: dict[str, dict]) -> str | None`：回傳符合的 `layouts[].id`，都不符合回 `None`。
  - `style_problems(scene: dict, style: dict) -> list[str]`：type、動作、版面、`keep`、每句附加欄位不在表內各一則，訊息含 scene id。
  - `components_for(style: dict, components_md: str) -> str`：只留表內 type 的 `## <type> — …` 章節與「通用動作」章節。
- 能力表欄位（兩份都要有）：`id`、`name`、`types`（`{type: [動作…] | "*"}`）、`marks`（list）、`layouts`（`[{id, shape, max?, max_per_col?, for_kind?}]` 或字串 `"free"`）、`keep`（bool）、`line_extras`（list）、`prompt`（相對 `video_engine/` 的路徑）。
- `chalk.json` 的值：`types` = `{"icon": ["draw","show","blink","erase"], "note": ["write","show","erase"], "vscode": "*", "cursor": "*"}`；`marks` = `["circle","underline","callout"]`；`layouts` = center（`{"stack": "ids"}`，max 3）、row（`{"row": "ids"}`，max 3）、two-col（`{"row": [{"stack":"ids"},{"stack":"ids"}]}`，max_per_col 2）、screen（`{"stack": ["vscode"]}`，for_kind screen）；`keep: false`；`line_extras: ["key"]`。
- `handbook.json`：`types` 列出 `board/catalog.json` 全部 15 種且都是 `"*"`；`marks` = `["circle","underline","arrow","brace","callout"]`；`layouts: "free"`；`keep: true`；`line_extras: []`。

- [ ] **Step 1: 寫失敗的測試** `tests/test_style_caps.py`

```python
def test_未知風格要列出可用的(self):
	with self.assertRaises(ValueError) as e: SC.load_style("chalkk")
	self.assertIn("chalk", str(e.exception)); self.assertIn("handbook", str(e.exception))
def test_壞掉的表要失敗(self):       # 暫存資料夾放一份缺 types 的 json，STYLE_DIR 指過去 → ValueError
def test_手帳表等於目錄(self):
	self.assertEqual(set(SC.load_style("handbook")["types"]), set(BC.load_catalog()["types"]))
def test_黑板版面判斷(self):
	st = SC.load_style("chalk"); objs = {i: {"id": i, "type": "icon"} for i in "abcd"} | {"v": {"id": "v", "type": "vscode"}}
	self.assertEqual(SC.layout_id({"stack": ["a", "b"]}, st, objs), "center")
	self.assertEqual(SC.layout_id({"row": ["a", "b"]}, st, objs), "row")
	self.assertEqual(SC.layout_id({"row": [{"stack": ["a"]}, {"stack": ["b", "c"]}]}, st, objs), "two-col")
	self.assertEqual(SC.layout_id({"stack": ["v"]}, st, objs), "screen")
	self.assertIsNone(SC.layout_id({"stack": ["a", "b", "c", "d"]}, st, objs))            # 超過 max
	self.assertIsNone(SC.layout_id({"row": [{"stack": [{"row": ["a", "b"]}]}, {"stack": ["c"]}]}, st, objs))  # 三層
def test_黑板不收的東西各報一則(self):
	# scene 用了 cells、icon 的 fill 動作、四個物件的 stack、keep、句上多了 foo 欄位
	# → 5 則問題，每則含 scene id；同一份 scene 用 handbook 表 → 只剩 foo 那一則
def test_元件說明只留表內的(self):
	md = open(COMPONENTS).read(); out = SC.components_for(SC.load_style("chalk"), md)
	self.assertIn("## icon", out); self.assertIn("## note", out); self.assertIn("通用動作", out)
	self.assertNotIn("## cells", out); self.assertNotIn("## stack", out)
```

- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_style_caps` → FAIL（模組不存在）。
- [ ] **Step 3: 實作** `style_caps.py` 與兩份表。純函式、不 import `board/`（`components_for` 收字串）。`shape` 比對：`"ids"` 代表一串物件 id；`["vscode"]` 代表恰好一個該 type 的物件（`cursor` 不佔版面，不算）。
- [ ] **Step 4:** 同指令 → PASS。
- [ ] **Step 5: Commit** `feat(styles): 風格能力表與檢查`

---

### Task 2: 能力表與實際畫法一致

**Files:**
- Modify: `video_engine/explainer/chalk/kit/board.chalk.js`（`ACTS`、`MARKS` 改讀能力表）
- Modify: `video_engine/explainer/sync_film.py`（把 `styles/chalk.json` 寫成片子的 `lib/style.js`）
- Modify: `video_engine/explainer/chalk/starter/index.html`（在 `board.chalk.js` 之前載入 `lib/style.js`）
- Test: `tests/test_style_caps.py`（加一個 class）、`tests/test_sync_film.py`

**Interfaces:**
- Consumes: Task 1 的 `chalk.json`。
- Produces: 瀏覽器端 `window.StyleCaps`（＝`chalk.json` 內容）；node 端 `board.chalk.js` 直接 `require('../../../styles/chalk.json')`。`board.chalk.js` 不再有自己的 `ACTS`／`MARKS` 常數。

- [ ] **Step 1: 寫失敗的測試**

```python
class TestChalkCapsAreReal(unittest.TestCase):
	def test_表裡每個動作都真的畫得出來(self):
		# 對 chalk.json 的 icon／note 每個動作各組一頁（board_page ＋ board_probe("mountAll")，沿用 tests/test_icon_component.py 的工具），
		# 斷言 problems == [] 且 log 裡有對應的筆畫（S）或寫字（seq）或淡出（fade）
	def test_表裡沒有的動作會被報出來(self):
		# icon 的 fill → problems 含「黑板還不會畫」
	def test_marks都畫得出來(self):   # circle、underline、callout 各一
```
`tests/test_sync_film.py`：從 starter 開新片後 `lib/style.js` 存在，內容解析後等於 `chalk.json`。

- [ ] **Step 2:** 跑兩個測試檔 → 新測試 FAIL。
- [ ] **Step 3: 實作**。`vscode`／`cursor` 的 `"*"` 不在這個測試範圍（它們走 `screen_check.js`，已有測試）。
- [ ] **Step 4:** `.venv/bin/python -m unittest tests.test_style_caps tests.test_sync_film tests.test_icon_component` → PASS。
- [ ] **Step 5: Commit** `refactor(chalk): 黑板會畫什麼改以能力表為準`

---

### Task 3: 文本段 `script.json`

**Files:**
- Create: `video_engine/board/script.py`
- Create: `video_engine/board/prompts/script.system.md`
- Modify: `video_engine/board/author.py`（`DEFAULT_MODEL`／`MAX_TOKENS` 加 `"script"`；新 `do_script`；CLI 加 `script`）
- Test: `tests/test_board_script.py`

**Interfaces:**
- Produces（`script.py`）：
  - `script_problems(script: dict, target_sec: int, glossary=()) -> list[str]`
  - `to_narration_doc(script: dict) -> dict`：`{"scenes": [{"id": page.id, "beats": [{"say", "spoken"?}]}]}`，含結語句（接在最後一頁），不含複習頁旁白。給既有的 `narration_problems`／`ai_tone_problems` 用。
  - `review_md(script: dict) -> str`：先骨架（每頁 `spine` 一行），`---`，再逐頁逐句（句號從 1 起算、全片連號），最後結語與複習。
  - `script_digest(script: dict) -> str`：`pages[].lines[].say/spoken`、`end.say`、`recap.say` 的 sha1 前 12 碼（只算會影響配音與對位的欄位）。
  - `with_closing(scene: dict, script: dict) -> dict`：回傳新 scene，結語句接在最後一個 scene 的 beats、另加一個 `id: "recap"` 的 scene（`list` 物件，`rows` = `recap.items`，一句 `recap.say` 配 `show`）。邏輯搬自 `storyboard_to_scene.to_scene` 的結尾段。
- Produces（`author.py`）：`do_script(md_path, out_dir, seg_id, budget, target=None, repair_target=None, resume=False)` 寫 `<id>.script.json`、`<id>.review.md`、`<id>.script.report.json`；CLI `author.py script <md> <out_dir> <segment>`。
- `script.json` 格式照 spec「1. 文本段」；`kind` ∈ `{"concept", "screen"}`；每頁 1–4 句；`end`、`recap` 必填。

- [ ] **Step 1: 寫失敗的測試** `tests/test_board_script.py`

```python
def test_提示詞沒有風格字眼(self):
	text = open(PROMPT, encoding="utf-8").read().replace("{{NARRATION_STYLE}}", "")
	for w in ("紙上", "手帳", "黑板", "粉筆", "白板", "鏡頭"): self.assertNotIn(w, text)
	self.assertIn("{{NARRATION_STYLE}}", open(PROMPT, encoding="utf-8").read())
def test_缺骨架或show要報(self):       # 一頁沒 spine、一頁沒 show、一頁 5 句、kind 寫 "board" → 各一則，含頁 id
def test_不准出現畫面欄位(self):       # 頁裡多了 objects／layout／do → 報「文本不寫元件與版面」
def test_旁白規則沿用(self):           # say 含「喔」、含「關鍵在於」、超過 40 字 → 都報（來自既有檢查）
def test_review先骨架再逐句(self):
	md = S.review_md(FIX); self.assertLess(md.index(FIX["pages"][1]["spine"]), md.index("---"))
	self.assertIn("1. " + FIX["pages"][0]["lines"][0]["say"], md)
def test_digest只看旁白(self):         # 改 show → digest 不變；改一個標點 → digest 變
def test_with_closing(self):           # 最後一個原 scene 的最後一句是 end.say；最後多一個 recap scene，rows == recap.items
def test_do_script寫出三個檔(self):     # patch BA.call 回傳合格 JSON、patch BA.preflight；斷言三個檔存在、review.md 非空
```
`FIX` 放 `tests/fixtures/one_pipeline/q1.script.json`（手寫，3 頁：2 頁 concept、1 頁 screen，共 7 句，有 end 與 recap；內容用迴圈邊界 `<` 與 `<=`）。

- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_board_script` → FAIL。
- [ ] **Step 3: 實作**。提示詞從 `scene.system.md` 搬「什麼叫好的分鏡」的 1、3、4、6、8、9 條（改寫成講內容與 `show`，不提元件名）與整段「旁白」；輸出格式換成 `script.json`。`do_script` 的 user 訊息沿用 `do_scene` 現在組的那一段（單元、問題、目標秒數、學習目標、`show`、用語表、教材段落、工作台出處檢查）。`do_script` 不跑 `preflight()`（不涉及元件）。
- [ ] **Step 4:** 同指令 → PASS。
- [ ] **Step 5: Commit** `feat(author): 文本段，產出與風格無關的 script.json`

---

### Task 4: 排畫面段 `stage --style`

**Files:**
- Create: `video_engine/board/prompts/stage.system.md`、`video_engine/styles/chalk.stage.md`、`video_engine/styles/handbook.stage.md`
- Modify: `video_engine/board/author.py`（`stage_problems`、`do_stage`、CLI `stage`；`scene` 改成依序跑 `do_script`＋`do_stage(style="handbook")`）
- Modify: `video_engine/board/compile.py`（若句上的 `key` 會被當成錯誤才改：能力表 `line_extras` 列的欄位要放行）
- Delete: `video_engine/board/prompts/scene.system.md`（內容已拆到 `script.system.md` 與 `stage.system.md`）
- Test: `tests/test_board_stage.py`；`tests/test_board_author.py`、`tests/test_narration_style.py` 跟著改

**Interfaces:**
- Consumes: Task 1 `load_style`／`style_problems`／`components_for`；Task 3 `script_digest`／`with_closing`。
- Produces:
  - `stage_problems(scene: dict, script: dict, style: dict, catalog: dict) -> list[str]`
  - `do_stage(out_dir, seg_id, style_id, budget, target=None, repair_target=None, resume=False)`：讀 `<id>.script.json`，寫 `<id>.<style>.scene.json`（頂層多 `"style"`、`"script_digest"`、`"gaps"`），並把 `gaps` 寫進 `<out_dir>/gaps.jsonl`（每行 `{"segment", "style", "page", "wanted", "used"}`）。
  - CLI：`author.py stage <out_dir> <segment> --style chalk|handbook`；`author.py scene <md> <out_dir> <segment>` 行為不變地產出 `<id>.scene.json`（＝手帳 stage 的結果再經 `with_closing`），工作台不用改。
- `<id>.<style>.scene.json` 裡的 scene 只有文本的頁（一頁一個 scene，`id` 與頁相同），不含結語與複習；那兩個由程式用 `with_closing` 或 Task 5 補。

- [ ] **Step 1: 寫失敗的測試** `tests/test_board_stage.py`（fixture：`tests/fixtures/one_pipeline/q1.chalk.scene.json`、`q1.handbook.scene.json`，手寫，對應 Task 3 的 `q1.script.json`；手帳那份至少用一個黑板沒有的 type，例如 `vars`）

```python
def test_兩份fixture都過(self):
	for st in ("chalk", "handbook"): self.assertEqual(BA.stage_problems(load(st), SCRIPT, SC.load_style(st), CAT), [])
def test_旁白差一個標點就退件(self):
	d = load("chalk"); d["scenes"][0]["beats"][0]["say"] = d["scenes"][0]["beats"][0]["say"].replace("，", ",")
	p = BA.stage_problems(d, SCRIPT, CHALK, CAT); self.assertTrue(any("p1" in x and "旁白" in x for x in p), p)
def test_少一句或多一頁都退件(self):
def test_手帳的scene給黑板會退件(self):    # 用了 vars → 問題含 vars 與 scene id
def test_整頁只有文字卻沒寫gap要提醒(self):
def test_do_stage寫檔與gaps不重複(self):
	# patch BA.call 回傳 chalk fixture（含一筆 gaps）；跑兩次 do_stage → gaps.jsonl 只有一筆 segment=q1,style=chalk；
	# 輸出檔的 script_digest == S.script_digest(SCRIPT)、style == "chalk"
def test_未知風格在呼叫LLM前就失敗(self):   # patch BA.call，斷言沒被呼叫
def test_scene指令仍產出同名檔(self):       # patch do_script／do_stage 的 call；<id>.scene.json 存在且最後一個 scene 是 recap
def test_stage提示詞依風格篩元件(self):     # 組出來的 system 字串：chalk 不含「## cells」、handbook 含
```

- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_board_stage` → FAIL。
- [ ] **Step 3: 實作**。
  - `stage_problems` 順序：頁數與 id → 每句 `say`／`spoken` 逐字比對（訊息寫「第 N 頁第 M 句旁白被改動」）→ `style_problems` → `BC.compile_scene` 與既有的 `mark_problems`／`crowd_problems`／`measure_problems`（旁白類檢查不重跑，文本段已過）。
  - `stage.system.md`：從 `scene.system.md` 搬第 2、5、7 條與 `scene.json` 格式、cue 規則，加「每頁對應一個 scene、旁白照抄不可改、`show` 做不到就寫 `gaps`」。佔位符 `{{STYLE}}`（風格那一小段）、`{{COMPONENTS}}`、`{{EXAMPLE}}`。
  - `chalk.stage.md`：只畫原理、程式碼放電腦畫面（`kind: screen` 的頁用 `vscode`）、每頁物件少而大、每句可寫 `key`（黑板上留的關鍵詞，≤ 8 字）。`handbook.stage.md`：同一主角用 `keep` 帶到下一場、換場像翻到筆記下一段。
  - `do_stage` 沿用 `converse`（stage 名 `"stage"`）、`preflight()`、`auto_focus`、`publish`。
- [ ] **Step 4:** `.venv/bin/python -m unittest tests.test_board_stage tests.test_board_author tests.test_narration_style tests.test_workbench_formats` → PASS。
- [ ] **Step 5: Commit** `feat(author): 排畫面段，依風格能力表挑元件`

---

### Task 5: 黑板吃 `scene.json`

**Files:**
- Create: `video_engine/explainer/scene_to_story.py`
- Modify: `video_engine/explainer/f5_story.py`（story 資料夾有 `spoken.json` 時，該句送進 F5 的文字用它）
- Test: `tests/test_scene_to_story.py`

**Interfaces:**
- Consumes: Task 1 `load_style`／`layout_id`；Task 3 `script_digest`；Task 4 的 `<id>.chalk.scene.json`。
- Produces:
  - `build(script: dict, scene: dict, style: dict) -> dict[str, str]`：鍵＝`script.md`、`pages.json`、`screens.json`、`objects.json`（有黑板頁才有）、`keys.json`、`leads.json`、`holds.json`、`recap.json`、`spoken.json`、`review.md`，內容格式與現在 `storyboard.build` 產的相同（下游不改）。
  - CLI：`python3 video_engine/explainer/scene_to_story.py <單元資料夾> <segment> <story 資料夾>`。
  - `LEAD_DEFAULT = 1.2`：一句的第一個動作是沒有 `cue` 的 `draw` 時，該句 `leads` 給這個值。
- 章：連續 `title` 相同的頁併成一章，章 id 為 `c1`、`c2`…。
- `screen_actions`／`board_actions`／`action_out`／`action_dur` 從 `storyboard.py` 搬進這個檔（Task 8 才刪舊檔）。

- [ ] **Step 1: 寫失敗的測試** `tests/test_scene_to_story.py`

```python
def test_產出的檔與句號(self):
	out = STS.build(SCRIPT, CHALK_SCENE, CHALK)
	self.assertEqual(json.loads(out["pages.json"]), [[1, 2, 3], [4, 5]])        # 兩頁 concept
	self.assertEqual(json.loads(out["screens.json"])[0]["lines"], [6, 7])        # 一頁 screen
	self.assertIn(SCRIPT["end"]["say"], out["script.md"]); self.assertIn("## recap", out["script.md"])
def test_模板由版面判斷(self):          # objects.json 各頁的 template：stack→center、row→center＋dir row、兩欄→two-col＋物件帶 col
def test_key與lead(self):               # 句上的 key 進 keys.json；第一個動作是無 cue 的 draw → leads[句號] == 1.2；有 cue → 沒有 lead
def test_spoken(self):                   # script 某句有 spoken → spoken.json[句號] 是它
def test_script改過要擋(self):
	s = copy.deepcopy(SCRIPT); s["pages"][0]["lines"][0]["say"] += "！"
	with self.assertRaises(ValueError) as e: STS.build(s, CHALK_SCENE, CHALK)
	self.assertIn("stage", str(e.exception))
def test_不是黑板的scene要擋(self):      # scene["style"] == "handbook" → ValueError
def test_版面不在表內要指出哪一頁(self):  # 把某頁 layout 改成四個物件的 stack → ValueError 含頁 id 與可用版面
def test_同標題併成一章(self):
```
另加一個產物層測試（沿用 `tests/test_icon_component.py` 的 E2E 寫法，`E2E_GEOM=1` 時沒瀏覽器要失敗）：`build` 的檔寫進暫存 story 資料夾 → `tools/story.py --dry` → `pages.py` → 從 starter 開片 `sync_film.py` → `screen_check.js` 與 `board_check.py` 都過。

- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_scene_to_story` → FAIL。
- [ ] **Step 3: 實作**。
- [ ] **Step 4:** `E2E_GEOM=1 .venv/bin/python -m unittest tests.test_scene_to_story tests.test_f5_story` → PASS。
- [ ] **Step 5: Commit** `feat(chalk): 黑板改吃共用的 scene.json`

---

### Task 6: 配音一次、兩種風格共用

**Files:**
- Modify: `video_engine/board/narrate_f5.py`、`video_engine/explainer/f5_story.py`（都加 `--cache-dir`，預設維持現狀）
- Test: `tests/test_shared_audio.py`

**Interfaces:**
- Consumes: Task 3 `with_closing`、Task 5 `spoken.json`。
- Produces: 兩支程式的 `--cache-dir <資料夾>`；`spoken_lines(script: dict) -> list[str]`（放 `video_engine/board/script.py`）：全片每句實際送進 TTS 的文字，順序＝頁內句子、結語、複習旁白。

- [ ] **Step 1: 寫失敗的測試**

```python
def test_兩種風格送進TTS的文字相同(self):
	# 用一個只記錄 speak(text) 的假 F5Narrator（patch 兩支程式的 F5Narrator），
	# 手帳：narrate_f5 對 with_closing(q1.handbook.scene.json) 跑；黑板：f5_story 對 Task 5 產的 story 資料夾跑（dry 骨架）
	# 斷言兩邊記到的文字 list 都等於 S.spoken_lines(SCRIPT)
def test_cache_dir會傳給Narrator(self):   # 兩支程式帶 --cache-dir X → 假 Narrator 收到 cache_dir == X
```

- [ ] **Step 2:** `.venv/bin/python -m unittest tests.test_shared_audio` → FAIL。
- [ ] **Step 3: 實作**。兩邊文字不一樣時先修到一樣（最可能是黑板沒用 `spoken`、或複習旁白的順序）。手帳出片一律帶 `narrate_f5.py` 產的 `timing.json` 給 `compile.py --timing`（實測時間，不用估的）；這條寫進 Task 7 的操作說明。
- [ ] **Step 4:** 同指令 → PASS。
- [ ] **Step 5: Commit** `feat(tts): 兩種風格共用同一批逐句配音`

---

### Task 7: 假文本走完兩種風格（不花錢）

**Files:**
- Create: `tests/test_one_pipeline_e2e.py`
- Create: `docs/一條流程操作說明.md`（每一步的指令、吃什麼檔、吐什麼檔、哪幾步要花錢或上 Colab）

**Interfaces:**
- Consumes: Task 3–6 全部；`tests/fixtures/one_pipeline/` 的三份 fixture。

- [ ] **Step 1: 寫測試**（`E2E_GEOM=1` 時沒瀏覽器要失敗）

```python
def test_手帳(self):   # with_closing(handbook fixture) → BC.compile_scene → build → check.py：無 gaps、無 warnings、版面檢查過
def test_黑板(self):   # Task 5 的產物層流程，另外斷言 objects.json 每頁的物件都在 board_check 的結果裡沒有問題
def test_同一份文本(self):   # 兩份 fixture 的 script_digest 相同且等於 S.script_digest(SCRIPT)
def test_舊scene擋下(self):  # 改 script 一個字後，手帳路徑（with_closing 前先比對 digest 的入口）與黑板路徑都拒絕
```
手帳路徑的 digest 比對放在一個小函式 `check_fresh(scene, script)`（`video_engine/board/script.py`），`with_closing` 與 `scene_to_story.build` 開頭都呼叫它。

- [ ] **Step 2:** `E2E_GEOM=1 .venv/bin/python -m unittest tests.test_one_pipeline_e2e` → 先 FAIL（`check_fresh` 未接）後 PASS。
- [ ] **Step 3:** 寫操作說明文件。
- [ ] **Step 4: Commit** `test: 同一份文本走完黑板與手帳`

---

### Task 8: 拿掉黑板的手寫分鏡入口，文件與同步清單對齊

**Files:**
- Delete: `video_engine/explainer/storyboard.py`、`video_engine/explainer/storyboard_to_scene.py`、`tests/test_storyboard.py`、`tests/test_storyboard_to_scene.py`
- Modify: `tests/test_icon_component.py`（用到 `SB.board_actions` 的地方改 import `scene_to_story`）
- Modify: `video_engine/explainer/chalk/starter/STARTER.md`、`video_engine/board/COMPONENTS.md`、`tools/video_skills/README.md`、`tools/video_skills_sync.py`（`INCLUDE` 與測試清單：去掉兩個舊測試，加 `test_style_caps.py`、`test_board_script.py`、`test_board_stage.py`、`test_scene_to_story.py`、`test_shared_audio.py`、`test_one_pipeline_e2e.py` 與 fixture、`docs/一條流程操作說明.md`）
- Modify: `CLAUDE.md`（專案）：開頭的管線說明補上這條流程與 `board/`、`explainer/chalk/`、`styles/`
- Modify: `docs/superpowers/plans/2026-10-29-component-roadmap.md`（階段 3「黑板吃元件目錄」標記由本計畫完成的部分）
- Modify: `docs/experiments/2026-10-31-icon-demo/` 與 `docs/experiments/2026-10-22-vscode-printf/` 各加一行說明：舊格式，留作紀錄，不再能重建

- [ ] **Step 1:** 刪檔、改 import、改文件。
- [ ] **Step 2:** `rtk proxy grep -rn -E "storyboard\.py|storyboard_to_scene|storyboard\.json" --include=*.py --include=*.md --include=*.js video_engine tools tests CLAUDE.md` → 只剩舊實驗資料夾的說明文字與 devlog。
- [ ] **Step 3:** `E2E_GEOM=1 .venv/bin/python -m unittest discover -s tests -t .` → `OK`。
- [ ] **Step 4:** 逐位元組基準（指令見專案 `CLAUDE.md`）與改動前相同。
- [ ] **Step 5:** `python3 tools/video_skills_sync.py`（不加 `--push`）→ 沒有被擋下的模組。
- [ ] **Step 6: Commit** `refactor(explainer): 拿掉黑板的手寫分鏡入口`；提醒使用者分支有未推送的 commit，推送要他確認。

---

### Task 9: 真教材實跑（每一步先問使用者）

不寫程式。每個 step 開始前把「要花什麼」講清楚並等使用者說可以。

- [ ] **Step 1:** 問使用者用哪份教材（清單見記憶 `course-materials-folder`）、哪一個小節、LLM 預算上限。
- [ ] **Step 2:** `author.py plan`（已有 `plan.json` 就跳過）→ `author.py script` → 把 `<id>.review.md` 交給使用者審骨架與旁白。要改就改文本重跑，審過才往下。
- [ ] **Step 3:** `author.py stage --style chalk`、`--style handbook`；回報兩份各修正幾次、`gaps.jsonl` 內容、`usage.jsonl` 花費。
- [ ] **Step 4:** Colab（先印 `os.cpu_count()`；GPU 配音、之後 CPU 渲染）：F5 逐句合成一次 → 兩種風格各自組時間軸 → 各出一支審片版（指令見 `docs/一條流程操作說明.md` 與記憶 `render-off-local`）。md5 核對後送給使用者。
- [ ] **Step 5:** 使用者看完，把回饋分成三類記進 devlog：旁白寫法（改 `script.system.md`／`narration_style_tw.md`）、挑元件（改 `stage.system.md` 或風格那段）、缺元件（進元件化階段 2 的清單）。
