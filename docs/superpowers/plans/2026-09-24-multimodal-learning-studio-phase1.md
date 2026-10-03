# 多模態教材工作台 Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立獨立、可測試、可逐項擴充的多模態教材工作台；Phase 1 以既有微課程影片作為唯一可執行能力，並預留 BridgeAI AI 對話與使用者提供 AI API 的穩定接口。

**產品對象註記（2026-09-28）：** 此計畫實作的是開發者用的獨立測試站；最終產品的主要使用者是 BridgeAI 中正在閱讀知識點、希望把難懂內容換成影片／心智圖／漫畫的學生。學生入口、課程權限與私人產物屬後續 BridgeAI adapter。

**進度（2026-09-28）：** Task 1–8 的功能已接通。Task 9 免費回歸：Python 224 項執行，223 項通過、1 項略過；前端 12 項通過；ES modules 語法與差異格式檢查通過。375／768／1024／1440 px 瀏覽器顯示、真實免費上傳與規則計畫預覽、模擬八階段流程動畫與服務重啟後的驗證碼更新均已驗證。
使用者已執行真實影片生成與產物核可；既有 MP4 在本機 Chromium 可播放，Range 回傳 206。內嵌瀏覽器原本的載入問題未能直接重現，已提供替代播放入口。Task 9 的其他手動異常情境與 legacy/studio 同時建 job 的驗收仍未完成；真實 AI planner transport 依 Phase 1 邊界未接入。
本計畫內各步驟的建議 commit 尚未執行，工作保留在目前工作樹供檢視。

**Architecture:** `Catalog + Contract + PlanStore` 負責受控規劃，`SourceStore` 產生不透明來源與 job 專用不可變快照；legacy 與 studio 共用一個 `ExecutionSlot`。`VideoJobFacade` 只衍生既有 `jobstate.Job` 的狀態、事件、審稿與 artifact，不建立第二套 job 狀態機。前端維持零建置 HTML/CSS/ES modules。

**Tech Stack:** Python 3.10+ stdlib、既有 `http.server`／SSE／影片管線、HTML5、CSS、原生 ES modules、Node.js 22 `node:test`、Python `unittest`。

**Spec:** `docs/superpowers/specs/2026-09-23-multimodal-learning-studio-design.md`

---

## Phase 1 邊界

本計畫完成工作台、自然語言 plan preview、影片生成、講稿審核、投影片預覽、影片播放下載與
產物核可。其他能力只以 `planned` 出現在 catalog。Phase 1 明確不做：漫畫／PPTX／心智圖生成、
單一產物重生、多使用者、登入、資料庫、跨重啟恢復與真實外部 AI HTTP transport。

使用者提供 AI API 後，只新增 transport adapter。接線前仍需：Base URL、認證 header、model、
request/response 範例、structured output 支援、timeout/rate-limit/error 格式。

## 檔案責任圖

| 檔案 | 動作 | 責任 |
|---|---|---|
| `studio/__init__.py` | Create | package marker |
| `studio/catalog.py` | Create | capability/template 白名單；影片 layout 直接引用引擎常數 |
| `studio/contracts.py` | Create | request、plan draft、canonical plan、artifact 契約與惡意輸入拒絕 |
| `studio/plans.py` | Create | opaque `plan_id` 與 server canonical plan 記憶體索引 |
| `studio/sources.py` | Create | source ref、revision、暫存生命週期與 job immutable snapshot |
| `studio/planner_backends.py` | Create |規則 backend、注入式 AI backend、安全錯誤 |
| `studio/planner.py` | Create | backend → canonical plan → PlanStore 協調 |
| `studio/execution.py` | Create | legacy/studio 共用的唯一 execution slot |
| `studio/video_facade.py` | Create | 既有 `Job` 的 API facade、審稿、event seq、artifact |
| `jobstate.py` | Modify | 可選 completion check，讓輸出缺失在唯一 Job 狀態內成為 failed |
| `video_engine/ingest.py` | Modify | PPTX 展開量、頁數、正規化文字上限 |
| `serve.py` | Modify | studio routes、bounded body、共用 slot、static exact map |
| `web/index.html` | Modify | 工作台 shell |
| `web/styles.css` | Create | tokens、layout、responsive、focus、reduced motion |
| `web/js/api.mjs` | Create | fetch、SSE reconnect、錯誤正規化 |
| `web/js/state.mjs` | Create | `uiPhase` reducer、plan invalidation、derived guards |
| `web/js/render.mjs` | Create | DOM rendering；不使用 `innerHTML` 插入不可信字串 |
| `web/js/app.mjs` | Create | UI orchestration、session recovery |
| `tests/test_studio_*.py` | Create | catalog/contracts/plans/sources/planner/execution/facade/API 測試 |
| `tests/web/*.test.mjs` | Create | state、API、SSE 純函式測試 |

---

### Task 1: 建立能力與模板唯一真相

**Files:**
- Create: `studio/__init__.py`
- Create: `studio/catalog.py`
- Create: `tests/test_studio_catalog.py`

- [ ] **Step 1: 寫 catalog 失敗測試**

```python
import unittest

from studio.catalog import CAPABILITIES, capability_index, public_catalog
from video_engine.layout import LAYOUT_MODES


class TestCatalog(unittest.TestCase):
	def test_id與template_id唯一且版本化(self):
		ids = [item["id"] for item in CAPABILITIES]
		templates = [item["template_id"] for item in CAPABILITIES]
		self.assertEqual(len(ids), len(set(ids)))
		self.assertEqual(len(templates), len(set(templates)))
		self.assertTrue(all(value.endswith(".v1") for value in ids + templates))

	def test_phase1只有影片可執行(self):
		available = [item["id"] for item in CAPABILITIES
			if item["availability"] == "available"]
		self.assertEqual(available, ["video.micro_lesson.v1"])

	def test影片layout與引擎唯一常數一致(self):
		video = capability_index()["video.micro_lesson.v1"]
		self.assertEqual(tuple(video["options"]["layout"]["enum"]), LAYOUT_MODES)
		self.assertNotIn("stage", video["options"]["layout"]["enum"])

	def test影片必要講稿審核由catalog決定(self):
		video = capability_index()["video.micro_lesson.v1"]
		self.assertEqual(video["review_gate"], "script")

	def test_public_catalog是deepcopy且沒有handler(self):
		public = public_catalog()
		public[0]["options"]["layout"]["enum"].append("evil")
		self.assertNotIn("evil", capability_index()["video.micro_lesson.v1"]["options"]["layout"]["enum"])
		self.assertTrue(all("handler" not in item for item in public))
```

- [ ] **Step 2: 跑測試確認 module 缺少**

Run: `.venv/bin/python -m unittest tests.test_studio_catalog -v`  
Expected: FAIL，`ModuleNotFoundError: studio`。

- [ ] **Step 3: 實作 catalog 與查詢函式**

影片資料固定為：

```python
from copy import deepcopy
from video_engine.layout import LAYOUT_MODES

CAPABILITIES = [{
	"id": "video.micro_lesson.v1",
	"template_id": "video.micro_lesson.default.v1",
	"kind": "video", "label": "微課程影片",
	"description": "帶旁白、字幕與程式碼走讀的短影片",
	"availability": "available", "cost_tier": "high",
	"review_gate": "script",
	"options": {
		"duration_seconds": {"type": "integer", "minimum": 30, "maximum": 600, "default": 110},
		"layout": {"type": "string", "enum": list(LAYOUT_MODES), "default": "auto"},
	},
}]

def capability_index():
	return {item["id"]: deepcopy(item) for item in CAPABILITIES}

def capability_ids():
	return set(capability_index())

def get_capability(capability_id):
	return capability_index().get(capability_id)

def public_catalog():
	return [{key: deepcopy(value) for key, value in item.items() if key != "handler"}
		for item in CAPABILITIES]
```

再依 spec 加七個 `planned` 項目；每項也必須有唯一 `template_id`、`review_gate` 與空或封閉的 options。

- [ ] **Step 4: 跑 catalog 測試**

Run: `.venv/bin/python -m unittest tests.test_studio_catalog -v`  
Expected: PASS。

- [ ] **Step 5: 建議 commit**

```bash
git add studio/__init__.py studio/catalog.py tests/test_studio_catalog.py
git commit -m "feat: 建立多模態教材能力與模板目錄"
```

---

### Task 2: 建立 canonical plan 契約與 PlanStore

**Files:**
- Create: `studio/contracts.py`
- Create: `studio/plans.py`
- Create: `tests/test_studio_contracts.py`
- Create: `tests/test_studio_plans.py`

- [ ] **Step 1: 寫惡意 plan table tests**

```python
import unittest

from studio.contracts import ContractError, canonicalize_plan

SOURCE = {"kind": "upload", "ref": "material:x", "revision": "sha256:" + "a" * 64}

def draft(**overrides):
	value = {
		"contract_version": "1.0", "status": "ready", "summary": "建立影片",
		"source": SOURCE, "questions": [], "warnings": [],
		"steps": [{
			"step_id": "video-1", "action": "artifact.generate",
			"capability_id": "video.micro_lesson.v1",
			"options": {"duration_seconds": 90, "layout": "auto"}, "requires": [],
		}],
	}
	value.update(overrides)
	return value

class TestCanonicalPlan(unittest.TestCase):
	def test_server補template與review_gate(self):
		plan = canonicalize_plan(draft())
		self.assertEqual(plan["steps"][0]["template_id"], "video.micro_lesson.default.v1")
		self.assertEqual(plan["steps"][0]["review_gate"], "script")

	def test_model不可關閉審核或指定template(self):
		for injected in ({"review_gate": "none"}, {"template_id": "evil.v1"}):
			value = draft()
			value["steps"][0].update(injected)
			with self.subTest(injected=injected), self.assertRaises(ContractError):
				canonicalize_plan(value)

	def test惡意options全部拒絕(self):
		bad = [
			{"duration_seconds": True, "layout": "auto"},
			{"duration_seconds": 29, "layout": "auto"},
			{"duration_seconds": 90, "layout": "stage"},
			{"duration_seconds": 90, "layout": "auto", "shell": "x"},
		]
		for options in bad:
			value = draft(); value["steps"][0]["options"] = options
			with self.subTest(options=options), self.assertRaises(ContractError):
				canonicalize_plan(value)

	def test_planned與未知能力不可ready(self):
		for capability_id in ("comic.misconception_story.v1", "shell.anything.v1"):
			value = draft(); value["steps"][0]["capability_id"] = capability_id
			with self.subTest(capability_id=capability_id), self.assertRaises(ContractError):
				canonicalize_plan(value)

	def test_phase1只允許單一無相依video_step(self):
		mutations = (
			lambda value: value.update(steps=[]),
			lambda value: value["steps"].append(dict(value["steps"][0], step_id="video-2")),
			lambda value: value["steps"][0].update(action="shell.exec"),
			lambda value: value["steps"][0].update(requires=["other"]),
		)
		for mutate in mutations:
			value = draft(); mutate(value)
			with self.subTest(value=value), self.assertRaises(ContractError):
				canonicalize_plan(value)
```

- [ ] **Step 2: 寫 PlanStore copy 與 opaque ID 測試**

```python
import unittest
from studio.contracts import canonicalize_plan
from studio.plans import PlanStore
from tests.test_studio_contracts import draft

class TestPlanStore(unittest.TestCase):
	def test_save回opaque_id且get不受呼叫端修改(self):
		store = PlanStore()
		record = store.save_canonical(canonicalize_plan(draft()))
		self.assertRegex(record.plan_id, r"^[0-9a-f]{32}$")
		got = store.get(record.plan_id)
		got.plan["summary"] = "被改"
		self.assertEqual(store.get(record.plan_id).plan["summary"], "建立影片")
```

- [ ] **Step 3: 跑測試確認 modules 缺少**

Run: `.venv/bin/python -m unittest tests.test_studio_contracts tests.test_studio_plans -v`  
Expected: FAIL。

- [ ] **Step 4: 實作封閉契約與 canonicalizer**

`studio/contracts.py` 必須：驗證 `contract_version`、closed fields、完整 SHA-256、source ref、
`ready/needs_clarification` invariant、options 型別與界線；Phase 1 ready plan 強制恰好一個
`artifact.generate` video step 且 `requires=[]`；integer 檢查使用
`isinstance(value, int) and not isinstance(value, bool)`。`canonicalize_plan()` 建立新 dict，依 catalog
填入 `template_id` 與 `review_gate`，不修改輸入。`assert_canonical_plan()` 驗證已含 catalog canonical
欄位的 plan，但不再次 canonicalize。

同檔輸出 `generation_plan_schema(capability_ids)`；給 AI 的 step schema刻意不接受
`template_id/review_gate`，兩欄只存在 canonical response。

- [ ] **Step 5: 實作 PlanStore**

```python
from copy import deepcopy
from dataclasses import dataclass
import threading, uuid
from studio.contracts import assert_canonical_plan

@dataclass(frozen=True)
class PlanRecord:
	plan_id: str
	plan: dict

class PlanStore:
	MAX_PLANS = 100
	def __init__(self):
		self._items = {}; self._lock = threading.Lock()
	def save_canonical(self, plan):
		assert_canonical_plan(plan)
		record = PlanRecord(uuid.uuid4().hex, deepcopy(plan))
		with self._lock:
			self._items[record.plan_id] = deepcopy(record.plan)
			while len(self._items) > self.MAX_PLANS:
				self._items.pop(next(iter(self._items)))
		return PlanRecord(record.plan_id, deepcopy(record.plan))
	def get(self, plan_id):
		with self._lock: plan = deepcopy(self._items.get(plan_id))
		return PlanRecord(plan_id, plan) if plan else None
```

- [ ] **Step 6: 跑 Task 1–2 測試**

Run: `.venv/bin/python -m unittest tests.test_studio_catalog tests.test_studio_contracts tests.test_studio_plans -v`  
Expected: PASS。

- [ ] **Step 7: 建議 commit**

```bash
git add studio/contracts.py studio/plans.py tests/test_studio_contracts.py tests/test_studio_plans.py
git commit -m "feat: 建立受控生成計畫契約與索引"
```

---

### Task 3: 建立安全來源生命週期與上傳 API

**Files:**
- Create: `studio/sources.py`
- Modify: `video_engine/ingest.py`
- Modify: `serve.py`
- Create: `tests/test_studio_sources.py`
- Create: `tests/test_studio_api.py`
- Modify: `tests/test_ingest.py`
- Modify: `tests/test_serve.py`

- [ ] **Step 1: 寫 SourceStore snapshot 與 cleanup 測試**

測試必須覆蓋：public payload 無 path、revision 為 normalized bytes SHA-256、檔案修改／消失為 stale、
job snapshot 名稱使用 `.studio_job_` 保留前綴且內容雜湊一致、`close()` 與下次啟動只清
`.studio_source_`／`.studio_job_` 普通檔，不碰 `teacher.md` 或 symlink。

- [ ] **Step 2: 寫 bounded body 與 malformed multipart 測試**

在 `tests/test_studio_api.py`／`tests/test_serve.py` 加：缺失、非數字、負數 Content-Length；宣告超過
上限時立即 413＋Connection close、不等待完整 body；短 body；壞 boundary；缺 filename；不支援副檔名；
錯誤一律為安全 400/411/413，response 不含絕對路徑。

同檔測 `GET /api/studio/session` 回不可預測 CSRF token；legacy/studio 所有 POST/DELETE 在缺 token、
錯 token、cross-origin 時回 403，且發生在讀 body、TTS probe、snapshot、slot claim 前。正確
`X-Studio-CSRF` 才進入 route；response 不提供 CORS headers。

- [ ] **Step 3: 寫 PPTX bomb 與 normalized text 上限測試**

以 `zipfile` 建超過 member count／uncompressed bytes 的測試檔，及超過頁數／正規化 2 MB 的輸入；
`extract_text()` 必須在 `Presentation()` 前拒絕 archive bomb，並拒絕空白、非 UTF-8 `.md/.txt`。

- [ ] **Step 4: 實作 SourceStore**

server 以 `SourceStore(MATERIALS)` 建立 store，確保 snapshot 仍符合既有 `Job` 對
`video_engine/materials/<name>.md` 的路徑假設。`SourceStore(workspace_dir)` 管理 `SourceRecord` 與
owned paths。`snapshot_for_job(ref, revision, job_id)`
先把 normalized bytes 讀入、以該 bytes 驗證 record/expected hash，再用
`os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)`
寫 `.studio_job_<job>_<uuid>.md`；runner 只能收到此 snapshot path。`release_path()`、`close()`、
`cleanup_orphans()` 僅刪保留前綴且非 symlink 的普通檔。

- [ ] **Step 5: 實作 bounded body 與 parser 錯誤正規化**

`serve.py` 新增 `read_request_body(rfile, headers, max_bytes)`：先嚴格解析長度；超限立即回 413 並
`Connection: close`，不等待／drain 任意大的宣告 body；合法長度設定 read timeout 後讀滿，短 body丟
`BadRequest`。legacy `/jobs` 與 studio upload/JSON routes 全部共用。`parse_multipart()` 的
`IndexError/ValueError` 只轉安全 400，完整 exception 寫 server log，不回 client。

同檔以 `secrets.token_urlsafe(32)` 建 process-local CSRF token；`GET /api/studio/session` 回 token 與
`planner_modes`。`hmac.compare_digest` 驗 `X-Studio-CSRF`，若 Origin 存在則 hostname 只允許
`localhost/127.0.0.1/::1`。所有 mutation route 第一行先驗 token，legacy 前端也先取 session。

- [ ] **Step 6: 實作 ingest 上限**

在 `ingest.py` 定義並使用：`MAX_PPTX_MEMBERS=2000`、`MAX_PPTX_UNCOMPRESSED=50*1024*1024`、
`MAX_PPTX_SLIDES=500`、`MAX_NORMALIZED_BYTES=2*1024*1024`。zip member sum 與 count 在載入
`Presentation` 前檢查；抽取後以 UTF-8 bytes 檢查 normalized size。

- [ ] **Step 7: 實作 `POST /api/studio/sources`**

上傳使用 `.studio_source_<uuid><ext>`，成功回 `{source:{kind,ref,revision,original_name,original_size,preview_excerpt}}`。
preview 只取 normalized text 前 500 個 Unicode 字元。失敗移除 raw/normalized；正常 shutdown 呼叫
`SourceStore.close()`。此 endpoint 不探 TTS、不建立 job。SourceStore 限制最多 20 records、normalized
總量 50 MB，超限回 507；`DELETE /api/studio/sources/{ref}` 釋放 record 與 owned files。PlanStore 最多
100 plans，FIFO 淘汰最舊項目。

- [ ] **Step 8: 跑來源與既有回歸**

Run: `.venv/bin/python -m unittest tests.test_studio_sources tests.test_studio_api tests.test_ingest tests.test_serve -v`  
Expected: PASS。

- [ ] **Step 9: 建議 commit**

```bash
git add studio/sources.py video_engine/ingest.py serve.py tests/test_studio_sources.py tests/test_studio_api.py tests/test_ingest.py tests/test_serve.py
git commit -m "feat: 建立安全教材來源與上傳生命週期"
```

---

### Task 4: 建立 AI Planner 接口與 plan API

**Files:**
- Create: `studio/planner_backends.py`
- Create: `studio/planner.py`
- Modify: `serve.py`
- Create: `tests/test_studio_planner_backends.py`
- Create: `tests/test_studio_planner.py`
- Modify: `tests/test_studio_api.py`

- [ ] **Step 1: 寫 backend 例外與越權測試**

測試 `RulePlannerBackend`、注入 fake callable 的 `StructuredAiPlannerBackend`；後者必須覆蓋 timeout、
供應商 exception 含秘密／路徑、非 dict、偷換 source、未知欄位、未知 capability、超界 options。
對外只允許 `PlannerBackendError(code, safe_message)`，不得回原 exception。

- [ ] **Step 2: 寫 `/plans` source 與 PlanStore 測試**

`POST /api/studio/plans` 在 backend 前先 `SourceStore.resolve(ref, revision)`；不存在回 404 `source_missing`，
stale 回 409；planner 只 canonicalize 一次，再呼叫 `PlanStore.save_canonical()`；成功回
`{plan_id, plan}`，不建立 job、不探 TTS。快捷按鈕與自然語言走同一 endpoint。加入一條正向
整合測試，確認合法 ready request 真正回 opaque plan_id。

- [ ] **Step 3: 跑測試確認 modules/routes 缺少**

Run: `.venv/bin/python -m unittest tests.test_studio_planner_backends tests.test_studio_planner tests.test_studio_api -v`  
Expected: FAIL。

- [ ] **Step 4: 實作 provider-neutral backends**

```python
class PlannerBackendError(RuntimeError):
	def __init__(self, code, safe_message):
		super().__init__(safe_message); self.code = code; self.safe_message = safe_message

class StructuredAiPlannerBackend:
	def __init__(self, complete_json): self._complete_json = complete_json
	def plan(self, request, catalog, schema):
		try: raw = self._complete_json("受控教材規劃器", {"request": request, "catalog": catalog}, schema)
		except TimeoutError as exc: raise PlannerBackendError("planner_timeout", "AI 規劃服務逾時") from exc
		except Exception as exc: raise PlannerBackendError("planner_unavailable", "AI 規劃服務暫時無法使用") from exc
		if not isinstance(raw, dict):
			raise PlannerBackendError("invalid_planner_response", "AI 規劃回應格式錯誤")
		if raw.get("source") != request["source"]:
			raise PlannerBackendError("source_changed", "AI 規劃不得更換教材來源")
		return raw
```

`RulePlannerBackend` 只辨識單一媒體與 `N 秒`；多媒體、無命中、planned capability 回
`needs_clarification`。兩個 backend 都只回 draft，不直接 canonicalize 或執行。
runtime 未配置 AI transport 時 session 只回 `rule` available；配置後才回 `ai`，且標記
`cost_tier`，API key 永不出現在 session payload。

- [ ] **Step 5: 實作 planner orchestrator 與 route**

`plan_request(payload, backend)`：normalize request → backend.plan → source equality →
`canonicalize_plan()` → `PlanStore.save_canonical()`。route 先驗 source，再呼叫 orchestrator；錯誤使用
安全 code。此鏈只有 `canonicalize_plan()` 一處會把 draft 變成 canonical plan。

- [ ] **Step 6: 跑 planner 與 API 測試**

Run: `.venv/bin/python -m unittest tests.test_studio_planner_backends tests.test_studio_planner tests.test_studio_api -v`  
Expected: PASS。

- [ ] **Step 7: 建議 commit**

```bash
git add studio/planner_backends.py studio/planner.py serve.py tests/test_studio_planner_backends.py tests/test_studio_planner.py tests/test_studio_api.py
git commit -m "feat: 建立可替換 AI 規劃接口"
```

---

### Task 5: 共用 ExecutionSlot 與 VideoJobFacade

**Files:**
- Create: `studio/execution.py`
- Create: `studio/video_facade.py`
- Modify: `jobstate.py`
- Modify: `serve.py`
- Create: `tests/test_studio_execution.py`
- Create: `tests/test_studio_video_facade.py`
- Modify: `tests/test_studio_api.py`
- Modify: `tests/test_serve.py`
- Modify: `tests/test_jobstate.py`

- [ ] **Step 1: 寫 legacy/studio 同搶 execution slot 測試**

使用 `threading.Barrier` 讓 legacy 與 studio owner 同時 `claim()` 50 輪；每輪恰一個成功。非 owner
不能 release；owner release 後下一個才能 claim；terminal exception path 也必須 release。另逐一注入
TTS unavailable、snapshot failure、facade init failure、thread start failure，斷言 slot 釋放且無 snapshot；
concurrent loser 不得先建立 snapshot。

- [ ] **Step 2: 寫 facade 三條完整跨層測試**

以 fake legacy Job 實作 `start/claim/resume/status/events`：

1. 正常：start → awaiting_review → get_review → submit_review → done → 只建立一個 artifact。
2. timer/user race：兩方同時 submit/claim，只有一方 resume，facade status 始終讀 legacy status。
3. 重驗失敗：submit_review 回 errors，legacy 回 awaiting_review、新 deadline 生效、slot 不釋放。

另測 sync exception → legacy failed → slot release；`sync_events(after)` seq 單調；重複 sync 不重建 artifact。
加入 raw error fixture：`Bearer secret /home/user/file traceback`，snapshot、SSE、review response 全部只能
看到 `{code,safe_message}`。以 Barrier 同時 approve/reject 同一 artifact，只有一方成功，另一方 409。

- [ ] **Step 3: 跑測試確認 modules 缺少**

Run: `.venv/bin/python -m unittest tests.test_studio_execution tests.test_studio_video_facade -v`  
Expected: FAIL。

- [ ] **Step 4: 實作 ExecutionSlot**

```python
class ExecutionSlot:
	def __init__(self): self._owner = None; self._lock = threading.Lock()
	def claim(self, owner):
		with self._lock:
			if self._owner is not None: return False
			self._owner = owner; return True
	def release(self, owner):
		with self._lock:
			if self._owner != owner: raise RuntimeError("execution slot owner 不符")
			self._owner = None
	def owner(self):
		with self._lock: return self._owner
```

`serve.py` 的 legacy `/jobs` 與 studio `/api/studio/jobs` 都先 claim 同一個 `_execution_slot`。`_guard`
接受 owner，在 terminal/exception 的 `finally` release；awaiting_review 不 release，timer resume 完成後 release。

同一步修改 `Job(..., completion_check=None)`：`resume()` 在最後 `_pump()` 成功後先呼叫 check；check
回錯誤文字或丟例外時，Job 自己轉 `failed` 並保存安全內部診斷，只有通過才轉 `done`。既有 caller
不傳 callback，行為不變。facade 注入的 check 驗 MP4 path containment、regular、非 symlink、size > 0。

- [ ] **Step 5: 實作 VideoJobFacade 公開接口**

```text
start() -> None
snapshot() -> {job_id,status,pct,stage,error,source,plan_id,artifacts}
events_after(seq) -> [{seq,event,payload}]
get_review() -> {segments,deadline,slides:[{slide_id,preview_url}]}
submit_review(segments) -> {ok,errors,deadline,notice}
slide_path(slide_id) -> private path
finalize_artifact() -> public manifest exactly once
artifact_content(artifact_id) -> private path
review_artifact(artifact_id, approve|reject) -> manifest
```

`status/pct/stage/error` 每次從 wrapped `Job` 讀取；facade 只保存 event seq、artifact manifest/status、
plan/source public metadata與 private snapshot path。完成或失敗後釋放 snapshot；artifact 內容仍指向 MP4。
artifact 轉移只允許 `needs_review → approved|rejected`，rejected 不可原地改回 approved。

facade 以單一 `RLock` 保護 event cursor、artifact 建立與 review transition。`public_error(raw, stage)` 只依
已知 stage/error category 回安全 code/message；raw `Job.error`、tail、exception 只 `logger.exception()`，
不得進 snapshot 或 SSE。`finalize_artifact()` 先驗 private path 位於該 job reserved out directory、非
symlink regular file、size > 0，失敗時不建 artifact 並回安全 failed。manifest 的 `file_name` 由來源
顯示名產生；stream helper 分開接 `private_path` 與 `public_file_name`，Content-Disposition 不露內部 UUID。

facade registry 追蹤 reserved studio lesson/actions/out paths；正常 shutdown 清除。啟動時只清
`video_engine/examples/studio_job_*.(lesson|actions).json` 與 `video_engine/out/studio_job_*`，逐一驗證
basename 前綴與父目錄，不跟隨 symlink。這些產物是 Phase 1 暫存；使用者要保留 MP4 必須先下載。

- [ ] **Step 6: 新增精確 studio routes**

- `POST /api/studio/jobs` body 僅 `{plan_id}`；順序固定為：查 server plan → source resolve/rehash（尚未
  寫 snapshot）→ TTS readiness → claim slot → try 內建立 snapshot/facade/start thread。任何 thread 前
  失敗都 release snapshot＋slot；slot loser 從未建立 snapshot。
- `GET /api/studio/jobs/{id}` 回 facade snapshot。
- `GET /api/studio/jobs/{id}/events?after=N` 送 `id: seq`＋JSON；terminal 送最後 snapshot 後關閉。
- `GET/POST /api/studio/jobs/{id}/review` 對應 facade review。
- `GET /api/studio/jobs/{id}/slides/{slide_id}` 只讀 facade 私有 layout，拒絕 traversal。
- `GET /api/studio/jobs/{id}/artifacts` 回 public manifests。
- `GET /api/studio/artifacts/{id}/content?download=1` 由 registry 找 facade/private path，保留 Range。
- `POST /api/studio/artifacts/{id}/review` 只接受 approve/reject，不啟動 runner。

- [ ] **Step 7: 補 API 正反向測試**

測 plan/source/job/artifact 404、stale source 409、slot busy 409、錯狀態 review 409、artifact decision 400、
studio slide 不讀 global `_job`、content Range 200/206/416、負 start／零 suffix／multi-range／檔案消失。
所有 public error 不含 `/home/`、material path、token 或 traceback。

- [ ] **Step 8: 跑 facade、API 與 legacy 回歸**

Run: `.venv/bin/python -m unittest tests.test_studio_execution tests.test_studio_video_facade tests.test_studio_api tests.test_serve tests.test_jobstate -v`  
Expected: PASS。

- [ ] **Step 9: 建議 commit**

```bash
git add studio/execution.py studio/video_facade.py jobstate.py serve.py tests/test_studio_execution.py tests/test_studio_video_facade.py tests/test_studio_api.py tests/test_serve.py tests/test_jobstate.py
git commit -m "feat: 以共用執行權接通影片工作"
```

---

### Task 6: 拆分前端與安全靜態資源

**Files:**
- Modify: `web/index.html`
- Create: `web/styles.css`
- Create: `web/js/api.mjs`
- Create: `web/js/state.mjs`
- Create: `web/js/render.mjs`
- Create: `web/js/app.mjs`
- Modify: `serve.py`
- Modify: `tests/test_studio_api.py`

- [ ] **Step 1: 寫 exact-map static routes 測試**

驗證 `/assets/styles.css`、四個 JS URL 的 MIME/200；未列入 exact map 的 URL、encoded traversal、NUL、
副檔名變形均回 404。實作使用 `{url: (absolute_path, mime)}`，不接受任意相對路徑。

- [ ] **Step 2: 跑測試確認 routes 不存在**

Run: `.venv/bin/python -m unittest tests.test_studio_api -v`  
Expected: FAIL。

- [ ] **Step 3: 先做行為等價拆檔**

將既有 CSS 移到 `styles.css`；fetch/SSE 移到 `api.mjs`；純狀態移到 `state.mjs`；DOM 移到
`render.mjs`；啟動移到 `app.mjs`。此步不改版，`index.html` 只引用本機資源：

```html
<link rel="stylesheet" href="/assets/styles.css">
<script type="module" src="/assets/js/app.mjs"></script>
```

- [ ] **Step 4: 跑語法、static 與 legacy 測試**

Run: `node --check web/js/api.mjs && node --check web/js/state.mjs && node --check web/js/render.mjs && node --check web/js/app.mjs`  
Expected: exit 0。  
Run: `.venv/bin/python -m unittest tests.test_studio_api tests.test_serve -v`  
Expected: PASS。

- [ ] **Step 5: 建議 commit**

```bash
git add web serve.py tests/test_studio_api.py
git commit -m "refactor: 拆分教材工作台前端資源"
```

---

### Task 7: 建立工作台 UI 與不可漂移 state

**Files:**
- Modify: `web/index.html`
- Modify: `web/styles.css`
- Modify: `web/js/state.mjs`
- Modify: `web/js/render.mjs`
- Modify: `web/js/app.mjs`
- Create: `tests/web/state.test.mjs`

- [ ] **Step 1: 寫完整契約 reducer 測試**

state 分開 `uiPhase` 與 `job.status`。fixture 必須包含完整 source ref/revision 與 canonical plan。
測試：沒有 source 不可 plan；ready plan 且 source 完全相同才可 execute；source、instruction、capability
任一改變立即清除 `planRecord`；planned capability 不可執行；新 job 重設 lastSeq/artifacts；terminal 可重試。

- [ ] **Step 2: 跑 reducer 測試確認 exports 缺少**

Run: `node --test tests/web/state.test.mjs`  
Expected: FAIL。

- [ ] **Step 3: 實作 immutable reducer**

`initialState()`、`reduce(state, action)`、`canPlan(state)`、`canExecute(state)`；unknown action 必須丟錯。
`canExecute` 同時要求 `uiPhase==='plan_ready'`、plan ready、目前 source kind/ref/revision 等於 plan source、
plan capability available。不得用按鈕 disabled 狀態當授權。

- [ ] **Step 4: 建立三區工作台 shell**

左：上傳、來源 excerpt。中：自然語言 textarea、範例指令、plan preview、review、artifact tabs。
右：catalog cards 與 available/planned。底：job progress rail。所有 input 有 label，錯誤 `role=alert`，
進度 `aria-live=polite`，icon button 有 `aria-label`。
若 session 宣告 AI planner available，規劃按鈕明示「用 AI 規劃（會呼叫 API）」；規則 planner
保持免費選項。AI 不可用時不畫出可點的 AI 模式。

- [ ] **Step 5: 實作安全 rendering**

API/AI/source 字串只以 `textContent` 或 `document.createTextNode` 插入。`render.mjs` 不得出現
`innerHTML`。抽出 `setText(node, value) { node.textContent = String(value ?? '') }`，Node 測試用只有
`textContent` 屬性的 fake node 傳入 `<img src=x onerror=alert(1)>`，斷言只是原字串；不引入 jsdom。

- [ ] **Step 6: 套用視覺與 responsive 基準**

沿用暖色 tokens；焦點對比可見；狀態不只靠顏色；支援 reduced motion。1440/1024 三區，768 以下
單欄分頁，375 無橫向捲動；不載 CDN、字型或框架。

- [ ] **Step 7: 跑前端 state 與語法測試**

Run: `node --test tests/web/state.test.mjs`  
Expected: PASS。  
Run: `node --check web/js/state.mjs && node --check web/js/render.mjs && node --check web/js/app.mjs`  
Expected: exit 0。

- [ ] **Step 8: 建議 commit**

```bash
git add web tests/web/state.test.mjs
git commit -m "feat: 建立多模態教材工作台介面"
```

---

### Task 8: 接通 source、plan、SSE、審稿與產物核可

**Files:**
- Modify: `web/js/api.mjs`
- Modify: `web/js/state.mjs`
- Modify: `web/js/render.mjs`
- Modify: `web/js/app.mjs`
- Create: `tests/web/api.test.mjs`
- Modify: `tests/web/state.test.mjs`
- Modify: `tests/test_studio_api.py`

- [ ] **Step 1: 寫 API 與 SSE 純函式測試**

測 URL path segment encoding、安全錯誤正規化、source/plan/job/review payload builder。SSE parser 以 seq
去重；斷線後用最新 `after` 重建 EventSource；terminal event 關閉且不再重連。

- [ ] **Step 2: 寫 artifact approval 與 session recovery state tests**

測 approve/reject 更新 artifact；rejected 不可直接 approve；job review 不動 artifact；artifact review
不動 job status；`sessionStorage` job ID 重整後先 GET snapshot/events/artifacts，再恢復 UI。

- [ ] **Step 3: 跑前端測試確認失敗**

Run: `node --test tests/web/*.test.mjs`  
Expected: FAIL。

- [ ] **Step 4: 實作 API client 與 manual SSE reconnect**

每個 non-2xx 先讀 JSON 再轉安全 `Error`。EventSource `onerror` 先 close，使用 bounded backoff 以
`?after=<lastSeq>` 重建；收到 terminal snapshot 後永久關閉。server 同時寫 `id: <seq>`，方便偵錯與
未來支援 `Last-Event-ID`。

- [ ] **Step 5: 接通完整 UI 流程**

upload source → plan preview (`plan_id`) → 確認執行 → progress → script review（含 studio slide URLs）→
video artifact → Range 播放／下載 → approve/reject。來源或指令改變後舊 plan 執行按鈕立即失效。

- [ ] **Step 6: 實作 reload recovery 與清理**

只在 sessionStorage 保存目前 job ID，不保存 API key、material path 或 plan body。重新整理查 server；
server 已重啟導致 404 時清 session 並顯示「本機服務重啟，工作狀態已清除」。開始新工作前關閉舊
EventSource、timer、media src/object URL。

- [ ] **Step 7: 跑前後端整合測試**

Run: `node --test tests/web/*.test.mjs`  
Expected: PASS。  
Run: `.venv/bin/python -m unittest tests.test_studio_api tests.test_studio_video_facade tests.test_serve tests.test_jobstate -v`  
Expected: PASS。

- [ ] **Step 8: 建議 commit**

```bash
git add web tests/web tests/test_studio_api.py
git commit -m "feat: 接通工作台影片生成與雙層審核"
```

---

### Task 9: 免費回歸、手動驗收與文件交接

**Files:**
- Modify: `README.md`
- Modify: `docs/NEXT_STEPS.md`
- Modify: `docs/superpowers/specs/2026-09-23-multimodal-learning-studio-design.md`

- [ ] **Step 1: 跑全套免費驗證**

Run: `.venv/bin/python -m unittest discover -s tests -t .`  
Expected: 0 failures、0 errors。  
Run: `node --test tests/web/*.test.mjs`  
Expected: 0 failures。  
Run: `node --check web/js/api.mjs && node --check web/js/state.mjs && node --check web/js/render.mjs && node --check web/js/app.mjs`  
Expected: exit 0。  
Run: `rg -n 'innerHTML' web/js`  
Expected: 無輸出。  
Run: `git diff --check`  
Expected: 無輸出。

- [ ] **Step 2: 人工驗收免費路徑**

啟動 `.venv/bin/python serve.py 8899`，在 375/768/1024/1440 px 驗 catalog、planned cards、source
excerpt、plan clarification、錯誤保留輸入、鍵盤 focus、reduced motion。模擬 catalog 404、plan 400、
source stale、slot busy、SSE 中斷、server restart；每條可理解且可恢復。

- [ ] **Step 3: 經使用者明確同意才跑付費 E2E**

不得自行啟動 TTS 或設 `E2E=1`。取得同意後用小教材驗：upload → plan → job → script review →
video → Range → artifact approve/reject；同時由 legacy/studio 建 job，只能一個成功。

- [ ] **Step 4: 更新文件事實**

README 加啟動與 API；NEXT_STEPS 記錄完成能力、記憶體狀態限制、AI transport 尚待使用者 API；spec
狀態改為「Phase 1 已實作」只能在 Step 1–3 驗證證據成立後進行。下一份計畫為共用 deck schema＋
`slides.lesson_deck.v1`／`pptx.editable_deck.v1`。

- [ ] **Step 5: 建議 commit**

```bash
git add README.md docs/NEXT_STEPS.md docs/superpowers/specs/2026-09-23-multimodal-learning-studio-design.md
git commit -m "docs: 完成教材工作台 Phase 1 交接"
```

---

## 設計模糊點與執行前輸入

沒有阻擋前端骨架與規則 planner 的問題。真實 AI planner transport 尚需使用者提供：Base URL、認證
方式、model、request/response、structured output、timeout/rate-limit/error。資料提供後先更新本計畫的
transport 子任務與契約測試，再接網路；不得在實作中猜 OpenAI-compatible。

Phase 1 其他決策已鎖定：記憶體狀態、重啟不恢復、單 execution slot、影片唯一可執行、rejected
artifact 不原地翻回 approved、無單產物重生、原生前端、暖色設計。

## 自我審查對照

- Source：upload、lookup、plan 驗證、immutable job snapshot、cleanup、stale/TOCTOU 皆有 Task 3–5。
- Planner：template/review gate server canonicalization，AI 失敗安全化，plan identity 有 Task 1–4。
- 執行：legacy/studio 單 slot、唯一 Job 狀態、timer/user race、SSE terminal 有 Task 5／8。
- 審核：job script gate 與 artifact approval API/UI/測試分離，rejected 行為明確。
- 安全：bounded body、multipart、PPTX bomb、XSS、路徑錯誤、static exact map、Range 反向案例已列。
- 前端：source/plan 一致性、`uiPhase`/job status 分離、reload recovery、EventSource cleanup 已列。
- 未實作能力沒有假按鈕；以 `planned` 顯示且 server validator 禁止執行。
