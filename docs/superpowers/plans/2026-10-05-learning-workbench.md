# Learning Workbench (new) Implementation Plan

> **For agentic workers:** Implementers are **Codex** (tasks M0, B1–B6, backend) and **AGY** (tasks F1–F5, frontend). Claude only reviews diffs and runs the gates.
> Per the user's instruction, this plan gives exact contracts, file paths, test cases and acceptance commands rather than full implementation code. Implementers write the code and tests. **Do not commit**: Claude commits after review.

**Goal:** Turn the board video studio into the multi-format learning workbench described in `docs/superpowers/specs/2026-10-05-learning-workbench-design.md`, ready to demo on 2026-10-14.

**Architecture:** `workbench/server.py` (moved from `video_engine/board/studio_server.py`) serves `/api/v1` and a zero-build frontend. A format registry (`workbench/formats/`) declares each material type: its steps, the subprocess commands that implement them, its outputs and its preview. One job queue runs subprocesses that report progress through `@step`/`@error`/`@unit` stdout markers. Each unit lives on disk under `video_engine/out/units/<unit_id>/`.

**Tech Stack:** Python 3 stdlib (http.server, threading, subprocess, unittest); existing modules in `video_engine/board/`, `studio/` and `video_engine/`; native HTML/CSS/ES modules; `node --test` (Node 22) for pure JS.

## Global Constraints

- Indent with **tabs** in every file (Python, JS, CSS, HTML). Comments in Chinese and sparse, matching the surrounding code.
- No new dependencies. No build tools, no CDN. The server uses the stdlib only.
- **Do not modify** the old workbench: `serve.py`, `web/`, `studio/*.py`. Importing from `studio/` and `video_engine/` is allowed.
- Tests must never call paid AI or the network. Python tests: `.venv/bin/python -m unittest discover -s tests -t .`. There is no pytest in `.venv`. JS tests: `node --test workbench/web/tests/`.
- The full suite must stay green (576 tests before this plan, 1 skipped).
- Production model: `MODEL = "google:gemini-3.8-flash"`. Mindmap and slides subprocesses get `VIDEO_ENGINE_LLM=google:gemini-3.8-flash` in their env. Per-unit budget is `--budget-usd 0.50`.
- UI copy is Traditional Chinese, colloquial. Palette: background `#ECE6DA`, card `#FFFDF7`, line/ink `#2E2622`, accent `#A04435`, soft text `#796F62`; light theme only.
- Every page fits 100vh. Long lists scroll inside their own box or paginate. Every diagram/image viewer has −, ＋, 符合視窗 (fit), 全螢幕 (fullscreen), wheel zoom and drag pan.
- No `git push`, `git merge`, `git reset --hard`, `rm -rf`. Deleting tracked files only where a task says so **and** Claude has confirmed with the user.

## File Map

```
workbench/__init__.py
workbench/server.py          HTTP routes, wiring (moved from video_engine/board/studio_server.py)
workbench/library.py         unit folders: ids, meta, plan, paths, manifest
workbench/jobs.py            queue, StepTracker, markers, error table
workbench/usage.py           read + summarize usage rows
workbench/uploads.py         multipart parsing, upload drafts
workbench/formats/__init__.py  registry: UnitView, Command, list/get/public/validate/item_format
workbench/formats/stages.py    ingest + analysis stage descriptions/commands
workbench/formats/{video,highlight,mindmap,slides,planned}.py
workbench/run_mindmap.py  run_slides.py  run_normalize.py
workbench/web/index.html  styles.css  js/{app,api,router}.mjs  js/pages/*.mjs  js/diagram.mjs  js/panzoom.mjs  js/viewers/{video,svg,deck}.mjs
workbench/web/mock/*.json     contract examples (M0)
workbench/web/tests/*.test.mjs
workbench/embed.html
tests/workbench_shapes.py     shared JSON shape contract (M0)
tests/test_workbench_{mock,server,formats,jobs,usage,runners}.py
```

Dependency order: **M0 first**. After that, Codex runs B1→B6 in sequence while AGY runs F1→F5 in parallel against the mocks.

---

### Task M0 (Codex): JSON contract — shapes + mocks

**Files:**
- Create: `tests/workbench_shapes.py`, `tests/test_workbench_mock.py`, and `workbench/web/mock/` with these files: `formats.json`, `units.json`, `unit-new.json`, `unit-analyzed.json`, `unit-done.json`, `job-running.json`, `job-failed.json`, `queue-idle.json`, `queue-busy.json`, `usage.json`, `manifest.json`, `ask-story.json`, `ask-out-of-scope.json`, `mindmap.svg`, `deck.json`.

**Interfaces:**
- Produces `tests/workbench_shapes.py`:
	- `SHAPES: dict[str, shape]`, keyed by `formats`, `unit_summary`, `unit`, `analysis`, `item`, `job`, `job_error`, `queue`, `usage`, `manifest`, `ask`, `api_error`.
	- A shape is `{key: type | shape | [shape]}`; `None` in a type tuple means nullable.
	- `assert_shape(value, shape, path="$")` raises `AssertionError` naming the first missing key or wrong type.
- Shapes follow spec §3.7 exactly:
	- `job.steps` items are `{"id", "state"}`; `state` is one of `pending|running|done|failed|skipped`.
	- `job_error` is `{"code", "reason", "advice", "retry"}`.
	- `api_error` is `{"error": {"code", "reason", "advice"}}`.
- Mock content:
	- Use the 「迴圈」 example with 5 points q1–q5. The questions are the ones in spec mockups: for 迴圈每一圈做了什麼？／為什麼我的迴圈多跑一次？／while 和 for 怎麼選？／迴圈為什麼停不下來？／巢狀迴圈怎麼數次數？.
	- `formats.json` lists video, highlight, mindmap and slides as available. It lists comic, podcast, interactive text, worked example and quiz as planned.
	- `job-running` is item q2 with `current: "repair"`; storyboard and validate are done.
	- `job-failed` has `error.code = "gemini_busy"`.
	- `deck.json` uses the real deck schema from `studio/deck_contracts.py`.
	- `mindmap.svg` must be the output of `studio.mindmap.render_mindmap_svg` on a canonical mindmap of the example.

- [ ] Write `tests/test_workbench_mock.py`. Every mock file must pass `assert_shape` with its shape, and every formats entry must have unique step ids. Include a negative test: a job with a step state `"weird"` must fail.
- [ ] Run `.venv/bin/python -m unittest tests.test_workbench_mock -v`. Expected: PASS.

### Task B1 (Codex): move server, extract library

**Files:**
- `git mv video_engine/board/studio_server.py workbench/server.py`
- `git mv tests/test_board_studio.py tests/test_workbench_server.py`
- Create: `workbench/__init__.py`, `workbench/library.py`, `tests/test_workbench_library.py`
- Modify: every reference found by `rtk proxy grep -rn "studio_server" --include=*.py --include=*.md --include=*.json .`. Do not change docs under `docs/superpowers/specs/` except paths.

**Interfaces (produces):**
- `library.unit_id(markdown: str) -> str`: sha256 of the markdown, first 12 hex chars. This is the existing behaviour.
- `library.read_json(path, default=None)`, `library.write_json(path, value)` (atomic write, kept from server), `library.safe_path(root, relative) -> Path` (raises `ValueError` on escape).
- `class Library(root: Path)` with these methods:
	- `create_unit(markdown, title=None, source_ref=None, source_kind="md") -> tuple[str, bool]`: writes `material.md` and `meta.json {"title", "created_at", "source_ref", "source_kind"}`. Returns `(id, created)`.
	- `exists(uid) -> bool`; `unit_dir(uid) -> Path` (raises `KeyError`); `unit_ids() -> list[str]` (newest first); `meta(uid) -> dict`; `plan(uid) -> dict | None`; `path(uid, relative) -> Path` (safe).
- `server.py` keeps current behaviour and routes in this task. It uses `Library` for every unit path. It runs with `.venv/bin/python -m workbench.server --port 8765`. CLI scripts resolve through `BOARD_DIR = <repo>/video_engine/board`.

- [ ] Test `create_unit`: same markdown twice gives the same id with `created=False`; `source_ref` round-trips; `safe_path("../x")` raises.
- [ ] Moved server tests pass unchanged except for imports.
- [ ] Run the full suite. Expected: all pass (count = 576 + new).
- [ ] Run `.venv/bin/python -m workbench.server --help`. Expected: usage text, exit 0.

### Task B2 (Codex): format registry

**Files:** create `workbench/formats/__init__.py`, `stages.py`, `video.py`, `highlight.py`, `mindmap.py`, `slides.py`, `planned.py`, and `tests/test_workbench_formats.py`.

**Interfaces (produces):**
- `@dataclass UnitView(id: str, dir: Path, plan: dict | None, tts_mode: str = "gemini")`.
- `@dataclass Command(step: str, argv: list[str], python: str = "project")`. `python` is `"project"` or `"playwright"`; the server resolves it to an executable. `argv[0]` is a script path.
- `FormatError(Exception)`.
- `list_formats() -> list[module]` returns available modules in order video, highlight, mindmap, slides. `get_format(fid) -> module` (raises `KeyError`).
- `public() -> {"stages": [STAGE dicts], "formats": [FORMAT dicts of available + planned.PLANNED]}`. It contains no callables and must be JSON-serializable.
- `validate(fmt: dict, module=None)`:
	- Required keys: `id`, `name`, `scope` (point|unit), `status` (available|planned), `preview` (video|svg|deck|none) and `steps`.
	- Each step needs `id`, `name`, `model`, `paid`, `cost` and `detail`, and step ids must be unique.
	- An available format needs a module with `estimate_usd`, `commands`, `outputs` and `is_done`. A planned one must not have commands, and needs `planned_note` with `order` (int) and `why` (str).
	- Called for every format at import. Failure raises `FormatError`.
- `item_format(plan: dict | None, item: str) -> str`: an id in `plan["stories"]` maps to `"video"`. `highlight`, `mindmap` and `slides` map to themselves. Anything else raises `KeyError`.
- Each available module provides `FORMAT`, `estimate_usd(unit, item) -> float`, `commands(unit, item) -> list[Command]`, `outputs(unit, item) -> dict[str, str]` (only existing files, relative to the unit dir) and `is_done(unit, item) -> bool`.
- `stages.py`:
	- `STAGES = [INGEST, ANALYSIS]` as FORMAT-like dicts, with ids `ingest` and `analysis`.
	- `analysis_commands(unit) -> [Command("selftest", [selftest.py, "--quick"]), Command("plan", [author.py, "plan", material, dir, "--model", MODEL, "--budget-usd", "0.50"])]`.
	- `ingest_commands(upload_dir, units_root) -> [Command("normalize", [run_normalize.py, upload_dir, units_root])]`.
- Step ids and costs:
	- video: `selftest, storyboard, validate, repair, narrate, render`.
	- highlight: `scenes, compose, narrate, render`.
	- mindmap: `generate, validate, render`.
	- slides: `generate, validate, export`.
	- Step names, models, costs and details come from `video_engine/board/studio/pipelines.json` and spec §3.2. Mindmap and slides paid steps use cost `"試跑後填入"`.
- Video commands for point `q`:
	1. If `q.scene.json` is missing, run `Command("storyboard", [author.py, "scene", material, dir, q, "--model", MODEL, "--budget-usd", "0.50"] + (["--resume"] if q.failed.json exists))`.
	2. Then `Command("narrate", [narrate.py, scene, voice, "--tts", tts_mode])`.
	3. Then run the render chain exactly as the current `_render` does: compile (`--timing`, `--gaps`), build (`--audio`), check (python=`"playwright"`) and export (python=`"playwright"`). All four use step `"render"`.
- Highlight commands: storyboard commands (step `"scenes"`) for each missing point scene in `plan["highlight"]["stories"]`, then `compose.py plan.json dir highlight.scene.json` (step `"compose"`), then narrate and the render chain into `highlight/`.
- Estimates:
	- video: `0.035 + sec * 0.0003`.
	- highlight: `0.03 * missing scenes + total_sec * 0.0003`.
	- mindmap and slides: `0.01`.
- `is_done`: a non-empty `<item>/video.mp4`, `mindmap/mindmap.svg` or `slides/deck.pptx`.

- [ ] Tests:
	- Every format validates.
	- A duplicate step id raises `FormatError`.
	- A planned format with `commands` raises.
	- `public()` passes `json.dumps` and `assert_shape(..., SHAPES["formats"])`.
	- Video commands add `--resume` only when the failed draft exists, and skip storyboard when the scene exists.
	- Highlight emits `compose.py`.
	- `item_format` covers point, unit and unknown items.
- [ ] Run the full suite. Expected: PASS.

### Task B3 (Codex): job runner, markers, error table, CLI markers

**Files:**
- Create: `workbench/jobs.py`, `tests/test_workbench_jobs.py`.
- Modify: `workbench/server.py` (use `JobQueue`), `video_engine/board/author.py`, `video_engine/board/narrate.py`, `video_engine/board/selftest.py` (print markers only), and their existing tests if needed.

**Interfaces (produces):**
- `parse_marker(line) -> tuple | None` recognises:
	- `@step <id>` → `("step", id)`
	- `@error <code> <detail…>` → `("error", code, detail)`
	- `@unit <uid>` → `("unit", uid)`
- `ERRORS: dict[str, dict]` covers exactly the codes in spec §3.4: `gemini_busy, repair_exhausted, quote_mismatch, tts_missing, budget, selftest, too_large, interrupted, unknown`. Each value is `{"reason": str (may contain "{detail}"), "advice": str, "retry": bool}`, with text copied from the spec table.
- `classify(code, detail, log_tail) -> {"code", "reason", "advice", "retry"}`:
	- Without a code, it searches the log tail with regex `429|503|UNAVAILABLE|RESOURCE_EXHAUSTED|[Tt]ime ?out|timed out` and returns `gemini_busy` on a match.
	- Otherwise it returns `unknown`, whose reason includes the last 3 log lines.
- `class StepTracker(step_ids)` has `enter(sid)`, `finish(ok: bool)`, `states() -> [{"id", "state"}]` and `current`. Rules:
	- Entering step k: the running step becomes `done`, and pending steps before k become `skipped`.
	- Re-entering an earlier step sets it back to `running`.
	- `finish(True)` turns remaining pending steps into `skipped`.
	- `finish(False)` marks the current step `failed`.
- `class JobQueue(library, runner, formats_mod)`:
	- `enqueue(uid, item) -> job_id`, `enqueue_stage(uid_or_None, stage_id, commands) -> job_id` (analysis/ingest), `get(job_id) -> dict` (SHAPES["job"]), `retry(job_id) -> job_id` (raises `ValueError` if not failed or not retryable), `queue() -> SHAPES["queue"]`, `close()`.
	- Runs one job at a time.
	- `runner(argv, on_line) -> int` is injectable. The default uses `subprocess` with env `VIDEO_ENGINE_LLM=google:gemini-3.8-flash` plus the current env.
	- Each command calls `enter(cmd.step)` before it runs.
	- Lines go to `log` (keep the last 40) and markers update the tracker, error and unit_id.
	- A non-zero exit runs `classify` and sets state `failed`.
	- Jobs persist to `<unit>/jobs/<id>.json` (stage jobs without a unit go to `<root>/../jobs/`). On construct, restored `queued`/`running` jobs become `failed` with `interrupted`.
	- `spent_usd` is the unit usage delta during the job.
- CLI markers (print to stdout with `flush=True`; no other behaviour changes):
	- `author.py`:
		- plan prints `@step plan`.
		- scene prints `@step selftest` before its self-check, `@step storyboard` before the first model call, `@step validate` before each validation pass, and `@step repair` before each repair call.
		- When it gives up it prints `@error repair_exhausted <first two problems joined by ；>`.
		- `BudgetExceeded` prints `@error budget <msg>`, and a self-check failure prints `@error selftest <msg>`.
	- `narrate.py`: when words are still missing after the last round, print `@error tts_missing 第 N 句`.
	- `selftest.py`: on failure, print `@error selftest <first failure>`.

- [ ] Tests:
	- `parse_marker` table.
	- `classify`: each code, fallback 429, unknown with tail.
	- StepTracker: validate→narrate skips repair; validate→repair→validate→narrate; failure marks current failed.
	- JobQueue with a fake runner emitting markers and exit codes: steps end in the expected states, a failed job has a classified error, retry creates a new job, and a restored running job is `interrupted`.
	- An author scene run with the existing fake model prints `@step storyboard` and `@step validate` (follow the fakes in `tests/test_board_author.py`).
- [ ] Run the full suite. Expected: PASS.

### Task B4 (Codex): usage tagging + summary

**Files:**
- Create: `workbench/usage.py`, `tests/test_workbench_usage.py`.
- Modify: `video_engine/board/author.py` (`Budget.record` writes `item`).

**Interfaces (produces):**
- `author.py`: `Budget(path, cap, item=None)`; `record()` adds `"item"`. The CLI passes `item="analysis"` for plan and the segment id for scene.
- `usage.read_unit(unit_dir) -> list[row]`. Rows are `{"at", "item", "step", "model", "in", "out", "usd"}`.
	- Legacy mapping for `usage.jsonl` rows without `item`: `stage=="plan"` → item `analysis`, step `plan`; `stage=="scene"` → item `video`, step `storyboard`.
	- `<item>/voice/tts_usage.jsonl` → item `<item>`, step `narrate`, `at` = file mtime ISO when missing.
- `usage.item_label(item, plan) -> str`:
	- A point gives `第 {n} 點影片：{story title}`.
	- Fixed labels: `highlight` 重點片, `mindmap` 心智圖, `slides` 簡報, `analysis` 教材分析, `ingest` 教材整理, `video` 影片（未標點）.
- `usage.summarize(units: list[tuple[uid, title, plan, rows]], today: date) -> SHAPES["usage"]` dict. `by_model` sums usd per model. Calls are sorted newest first.
- `usage.unit_spent(unit_dir) -> float`. It replaces the server's `spent_usd`.

- [ ] Tests: legacy rows map correctly; TTS rows infer the item from the folder; totals for today and all; `by_model`; labels; the summary passes `assert_shape`.
- [ ] Run the full suite. Expected: PASS.

### Task B5 (Codex): mindmap / slides / normalize subprocesses

**Files:** create `workbench/run_mindmap.py`, `workbench/run_slides.py`, `workbench/run_normalize.py` and `tests/test_workbench_runners.py`.

**Interfaces (produces):**
- `run_mindmap.main(argv, complete_json=None) -> int`, with argv `[unit_dir]`. It prints `@step generate`, `@step validate` and `@step render`.
	- It calls `studio.mindmap.build_mindmap(material, "整理這份教材的概念與關係", complete_json)`.
	- The default `complete_json` is `video_engine.llm.complete_json` bound to `stage="mindmap"`, wrapped with `video_engine.usage.capture_call` / `UsageLedger` so every call is appended to `<unit>/usage.jsonl` as an item `mindmap`, step `generate` row.
	- It writes `mindmap/mindmap.json` and `mindmap/mindmap.svg` (`render_mindmap_svg(mindmap, material)`).
	- A `studio.mindmap.MindmapError` whose message is about quotes or source evidence prints `@error quote_mismatch <msg>` and returns 1.
- `run_slides.main(argv, complete_json=None) -> int` does the same with `studio.deck_builder.build_deck(material, "把這份教材做成線上簡報", cj)`. Its steps are generate, validate and export.
	- It writes `slides/deck.json` and `slides/deck.pptx` (from `studio.pptx_export.export_pptx(deck)`, which returns bytes; check the actual return type).
	- A quote-related `studio.deck_contracts.DeckError` maps to `quote_mismatch`.
- `run_normalize.main(argv, runner=None) -> int`, with argv `[upload_dir, units_root]`. It prints `@step normalize`.
	- It reads `upload_dir/upload.json` (`{"filename", "kind", "title"}`, written by B6) and the original file.
	- It calls `studio.material_normalizer.normalize_material(record, runner)` (read its record format first).
	- It creates the unit with `Library(units_root).create_unit(markdown, title, source_kind=kind)` and appends usage rows as item `ingest`.
	- It prints `@unit <uid>`.
- All three call `os.environ.setdefault("VIDEO_ENGINE_LLM", "google:gemini-3.8-flash")` before importing `video_engine.llm`.

- [ ] Tests (fake `complete_json`/runner returning canned valid outputs; reuse fixtures from the existing mindmap/deck/normalizer tests):
	- Output files exist and the SVG starts with `<svg`.
	- `usage.jsonl` rows carry the right item.
	- A bad quote prints `@error quote_mismatch`.
	- normalize prints `@unit` and creates `meta.json` with the right `source_kind`.
- [ ] Run the full suite. Expected: PASS.

### Task B6 (Codex): `/api/v1`, manifest, embed, static

**Files:**
- Modify: `workbench/server.py`, `workbench/library.py` (manifest).
- Create: `workbench/uploads.py`, `workbench/embed.html` (placeholder until F4), `workbench/web/index.html` (placeholder until F1).
- Rewrite `tests/test_workbench_server.py` for v1.

**Interfaces (produces):** every endpoint in spec §3.7, with exactly those JSON shapes. Real responses must pass `assert_shape` with `tests/workbench_shapes.py`.
- Errors return `{"error": {"code", "reason", "advice"}}`. API codes are `not_found` (404), `bad_request` (400), `conflict` (409) and `too_large` (413).
- `POST /api/v1/uploads` accepts multipart `file` only, for pdf or pptx, with a 5 MB limit.
	- It saves to `video_engine/out/uploads/<upload_id>/` with `upload.json`, then extracts with `video_engine.ingest.extract_text`.
	- It checks `studio.material_normalizer.check_normalization_limits`.
	- It returns `{"upload_id", "kind", "excerpt" (first 400 chars), "pages", "chars", "estimate_usd"}`.
- `POST /api/v1/uploads/<id>/normalize` enqueues stage `ingest`. When the job finishes, it carries `unit_id` from the `@unit` marker.
- `POST /api/v1/units/<id>/analyze`: 409 `conflict` while an analysis job for that unit is queued or running.
- `POST /api/v1/units/<id>/generate`:
	- Expands items in order: points in the given order, then highlight, mindmap, slides.
	- Skips items that are done or already queued.
	- Returns 400 for an unknown item or a planned format, and 409 if the unit isn't analyzed.
- `GET /api/v1/units/<id>`: `items` lists every point plus highlight, mindmap and slides. Each item has status from the jobs and `is_done`, `estimate_usd`, `cost_usd` (from usage rows of that item), `duration` (ffprobe-free: read `timeline.json` total if present, else null), `files` (from `outputs`) and `job_id` (latest).
- `Library.write_manifest(uid, items)` runs after each successful job. `GET .../manifest` builds it fresh if missing. Each product's `embed_url` is `/embed/<uid>/<item>`.
- Static routes:
	- `GET /` → `workbench/web/index.html`.
	- `GET /web/<path>` → files under `workbench/web/` (safe path).
	- `GET /embed/<uid>/<item>` → `workbench/embed.html`.
	- `GET /media/<uid>/<path>` keeps Range support.
- **Remove** old routes `/api/units*`, `/api/pipelines`, `/api/jobs/*` (non-v1) and `/studio/*`. Removing the directory `video_engine/board/studio/` (including `pipelines.json`) waits until Claude confirms with the user. Until then, leave the files and only stop serving them.

- [ ] Tests (fake runner, temp dirs):
	- Every endpoint's happy path passes `assert_shape`.
	- Upload limit and `too_large`.
	- Normalize sets `unit_id`.
	- Generate ordering and skipping; 409 before analysis; 400 for a planned format.
	- Retry; queue.
	- Usage endpoint; manifest after a fake successful video job; embed returns 200 HTML; Range request returns 206.
	- A path traversal attempt on `/web/../server.py` returns 404.
- [ ] Run the full suite. Expected: PASS.
- [ ] Manual smoke (Claude): `.venv/bin/python -m workbench.server --port 8765`, then `curl -s localhost:8765/api/v1/formats | head -c 300`.

---

### Task F1 (AGY): shell, router, api, overview, roadmap

**Files:** create `workbench/web/index.html`, `styles.css`, `js/app.mjs`, `js/router.mjs`, `js/api.mjs`, `js/pages/overview.mjs`, `js/pages/roadmap.mjs`, `tests/router.test.mjs`.

**Interfaces (produces):**
- `api.mjs`:
	- `api.get(path)` and `api.post(path, body)` against `/api/v1`. With `?mock=1` they read `web/mock/*.json` instead, using a fixed table from endpoint to file.
	- In mock mode, `POST /generate` returns ids and `GET /jobs/<id>` simulates progress: the current step advances every 2 s through the format's steps, and a job for item `q4` fails with `gemini_busy`.
	- `api.MOCK` is a boolean.
- `router.mjs`: hash routes `#/overview` (default), `#/make/1`…`#/make/4`, `#/pipelines`, `#/library`, `#/usage`, `#/roadmap`. It exports `parseRoute(hash) -> {page, step}` (pure) and `go(page, step)`.
- Left rail: 6 items with icons and Chinese labels 總覽／製作／流程架構／素材庫／用量／路線圖. While `/api/v1/queue` reports running or queued jobs (polled every 3 s), a small dot shows next to 製作. On narrow screens the rail becomes a top bar.
- Overview:
	- A one-line goal: 「看不懂？換個方式理解。」
	- Three numbers: the number of available formats, average cost per finished video item, and the number of finished products.
	- Format cards: scope 逐點／整份, status, model, unit cost. Clicking a card goes to `#/pipelines?focus=<id>`.
- Roadmap: the planned formats sorted by `planned_note.order`, each with its `why`, plus the integration plan (platform / blog), with text taken from spec §2.

- [ ] `node --test workbench/web/tests/`: `parseRoute` cases pass.
- [ ] Serve the mocks with `cd workbench/web && python3 -m http.server 8790` and open `http://localhost:8790/?mock=1`. The user verifies visually.

### Task F2 (AGY): diagram + pan/zoom + pipelines page

**Files:** create `js/diagram.mjs`, `js/panzoom.mjs`, `js/pages/pipelines.mjs`, `tests/diagram.test.mjs`, `tests/panzoom.test.mjs`.

**Interfaces (produces):**
- `panzoom.mjs` (pure):
	- `zoomAt(view, factor, point) -> view` and `fit(bounds, viewport, pad=24) -> view`. Here `view = {x, y, scale}`.
	- `clampScale(s, min=0.2, max=4)`.
	- `attach(svgOrEl, {onChange})` binds wheel, drag (pointer events), keys `+`, `-`, `0` (fit) and buttons, and returns `{zoomIn, zoomOut, fit, focus(bounds, animateMs=350), fullscreen}`.
- `diagram.mjs`:
	- `layoutMap(publicFormats) -> {nodes:[{id,label,sub,x,y,w,h,kind}], edges:[{from,to}], groups:{<formatId>: bounds}}`. The map is 教材 → 教材整理 → 教材分析 → each format → 素材庫; planned formats get `kind:"planned"` (dashed).
	- `layoutSteps(steps) -> nodes` lays steps out in one row and wraps after 4.
	- `render(container, layout, {mode: "explain"|"live", onNodeClick})`.
	- `setLive(container, stepStates)`: running gets the accent fill, done green, failed red, skipped grey.
- Pipelines page:
	- Shows the total map. Clicking a format group smoothly focuses that branch, which reveals its steps. A 返回全圖 button sits top-left.
	- Clicking a node opens a side panel with model, cost and detail.
	- Controls: − ＋ 符合視窗 全螢幕. `?focus=<id>` focuses on load.

- [ ] Node tests:
	- `zoomAt` keeps the point under the cursor fixed.
	- `fit` centers the bounds and stays within the scale clamp.
	- `layoutMap` has no overlapping nodes for the mock formats, and every edge refers to existing nodes.
	- `layoutSteps` wraps after 4.
- [ ] Mock mode: the user verifies zooming, dragging and branch focus.

### Task F3 (AGY): 製作 ① 教材, ② 分析結果

**Files:** create `js/pages/make.mjs` (step shell + step bar) and `js/pages/make-source.mjs`, `js/pages/make-analysis.mjs`.

**Behaviour:**
- Step bar ①教材 ②分析結果 ③生成 ④成品. Step links are enabled only when their data exists. The selected unit id lives in the hash query (`#/make/2?unit=<id>`).
- ① 教材:
	- File input accepts `.md`, `.txt`, `.pdf` and `.pptx`.
	- md/txt are read with `FileReader` and sent to `POST /units`.
	- pdf/pptx go to `POST /uploads`. The page shows excerpt, pages and estimate, and calls `POST /uploads/<id>/normalize` only after the user clicks 確認整理, then polls the job.
	- There is also a paste textarea and a 「從素材庫挑」 list of 6 cards per page.
	- Then 「開始分析（約 US$0.015）」 → `POST /analyze` → poll the job, showing a small live diagram (`diagram.layoutSteps` of the analysis stage) → go to ②.
- ② 分析結果:
	- Scope chips: 涵蓋 normal, 不涵蓋 struck through.
	- Left: the point list (number, question, sec, status dot). Right: details for the selected point (question, 也會這樣問, 必演畫面 chips, sec, objectives).
	- 詞彙表 sits in a collapsible box. 建議重點片 shows its points, total length and why.
	- A 「下一步：選要生成的 →」 button.

- [ ] Mock mode: the user verifies both steps fit one screen with 5 points, and with 12 points (the list scrolls inside its box).

### Task F4 (AGY): 製作 ③ 生成, ④ 成品, viewers, embed

**Files:** create `js/pages/make-generate.mjs`, `js/pages/make-products.mjs`, `js/viewers/video.mjs`, `js/viewers/svg.mjs`, `js/viewers/deck.mjs`; replace `workbench/embed.html`.

**Behaviour:**
- ③ 生成:
	- A checklist of points plus 整份: 重點片／心智圖／簡報, each with `estimate_usd`, and a total. Done items show 已完成.
	- 開始生成 calls `POST /generate`.
	- Left: the queue (from `/queue`). Right: the live diagram of the running job (`layoutSteps` of its format + `setLive`), polling `/jobs/<id>` every 2 s while visible.
	- On failure: the failed step is red and a panel shows `error.reason` and `error.advice`, with a 重試 button (`POST /jobs/<id>/retry`) only if `error.retry`.
- ④ 成品:
	- Tabs 每點影片／重點片／心智圖／簡報.
	- The video tab plays one video at a time with 上一點／下一點.
	- The mindmap tab uses an SVG viewer built on panzoom.
	- The deck viewer flips pages with ← → keys and buttons; render the `deck.json` layouts the same way `web/js/render.mjs` does for the old deck preview. It has a 下載 PPTX link.
	- Each product shows `cost_usd`.
- Viewers export `mount(el, {unit, item, files})`.
- `embed.html` reads `/embed/<uid>/<item>` from `location.pathname`, fetches the manifest and mounts the right viewer full-window, with no rail.

- [ ] Mock mode: the user verifies that the live diagram advances and that the q4 failure shows its reason and a retry button.
- [ ] Viewer pan and zoom work, and the deck flips with the keyboard.

### Task F5 (AGY): 素材庫, 用量

**Files:** create `js/pages/library.mjs` and `js/pages/usage.mjs`.

**Behaviour:**
- 素材庫:
	- The top box is 學生提問: a unit select plus a question box, submitted to `POST /ask`.
	- Results by `kind`:
		- story with video: play inline.
		- story without video: a 「生成這段」 button that calls `POST /generate {items:[story]}`.
		- `out_of_scope`: a lock icon and 「這份教材沒有教這個」.
		- `no_match`: 「找不到對應的段落」.
	- Below are unit cards, 6 per page with pager. Each shows title, points, product icons and spent; clicking goes to `#/make/4?unit=<id>`.
- 用量:
	- Totals: 今天, 全部, 依模型 (small bars).
	- Grouped list: unit → item (label, usd), expandable to calls (time, step, model, in, out, usd), paged at 10 units.
	- Auto-refresh every 2 s only while this page is visible **and** `/queue` is busy.

- [ ] Mock mode: the user verifies both pages fit one screen.

---

### Task V (Claude + user): integrate, trial, rehearse

- [ ] With B6 and F1–F5 done, run the real server: `.venv/bin/python -m workbench.server --port 8765`.
- [ ] Click through every page without `?mock=1`. Claude checks that the API calls match shapes; the user checks the visuals.
- [ ] **Paid trial (only with the user's OK)**: one unit, with analysis, 2 points, mindmap and slides, about US$0.10–0.15.
- [ ] Record the mindmap and slides real costs into the registry `cost` fields, replacing 試跑後填入.
- [ ] Note the Gemini quote stability in the spec status section.
- [ ] Run sync-docs, then commit per task group. Remind the user about push. Ask about rerunning `/graphify`.
- [ ] Rehearsal on 10/13: full demo flow, with timings noted.
