# Frontend Defect Fixes Report: web/index.html (2026-08-26)

## Changes per Fix

### Fix 1: Show Failure Diagnostics
- Added `white-space: pre-line` styling to `<div id="failed-reason">` to preserve multi-line traceback formatting from the backend `state.error` field.
- Updated `handleServerEvent` to retain stage status on `stage_fail` without terminating event stream prematurely.
- Enhanced `handleJobFailed(stage, errMsg)` to display the backend `error` string and ensure stage name is preserved in the title, with fallback summary text if `error` is empty or missing.

### Fix 2: Prevent Re-validation Bounce from Wiping Operator Edits
- Added `reviewLoaded: false` flag to `state` (reset on new job and restart).
- Updated `openReviewScreen(deadline)` to fetch `/jobs/{id}/script` and render segments only on initial entry for a job (`!state.reviewLoaded`).
- On subsequent `awaiting_review` SSE events (e.g. 400 revalidation bounce), `openReviewScreen` only updates the countdown timer deadline and leaves the existing DOM textareas, operator edits, and validation error banner untouched.

### Fix 3: Use Event, Not Clock, to Leave Review Screen
- In `handleServerEvent`, when `stage_start` arrives for stage `synth`, the review countdown timer is cleared unconditionally and `showScreen('screen-running')` is called immediately.
- Preserved existing client-side countdown timer as normal path; event serves as backstop for clock skew.

### Fix 4: Make Failed Approve Request Visible
- Added `id="review-error-title"` to the review validation box error header.
- Updated `submitApproval` `.catch()` block to render an inline error message ("網路連線異常，審查請求未送達，請重試") in `#review-validation-errors` and re-enable action buttons.
- Handled non-200/400/409 HTTP error responses in `submitApproval` by surfacing server error text in `#review-validation-errors`.

---

## Before / After: Review Screen Entry Logic

### Before
```javascript
/* 處理後端推播事件 */
function handleServerEvent(ev) {
	...
	} else if (ev.event === 'state') {
		state.status = ev.status;
		if (ev.status === 'awaiting_review') openReviewScreen(ev.deadline);
		...
	}
}

/* 載入講稿並開啟審稿畫面 */
function openReviewScreen(deadline) {
	showScreen('screen-review');
	fetch('/jobs/' + state.jobId + '/script')
		.then(function(res) {
			if (!res.ok) throw new Error('無法載入講稿');
			return res.json();
		})
		.then(function(data) {
			state.originalSegments = data.segments || [];
			renderScriptSegments(state.originalSegments);
			startReviewCountdown(data.deadline || deadline);
		})
		.catch(function(err) {
			console.error('拉取講稿失敗', err);
			startReviewCountdown(deadline);
		});
}
```

### After
```javascript
/* 處理後端推播事件 */
function handleServerEvent(ev) {
	...
	} else if (ev.event === 'state') {
		state.status = ev.status;
		if (ev.status === 'awaiting_review') openReviewScreen(ev.deadline);
		...
	}
}

/* 載入講稿並開啟審稿畫面 */
function openReviewScreen(deadline) {
	showScreen('screen-review');
	if (state.reviewLoaded) {
		if (deadline) startReviewCountdown(deadline);
		return;
	}
	state.reviewLoaded = true;
	const errBox = document.getElementById('review-validation-errors');
	if (errBox) errBox.classList.add('hidden');
	fetch('/jobs/' + state.jobId + '/script')
		.then(function(res) {
			if (!res.ok) throw new Error('無法載入講稿');
			return res.json();
		})
		.then(function(data) {
			state.originalSegments = data.segments || [];
			renderScriptSegments(state.originalSegments);
			startReviewCountdown(data.deadline || deadline);
		})
		.catch(function(err) {
			console.error('拉取講稿失敗', err);
			startReviewCountdown(deadline);
		});
}
```

---

## Verbatim Output of Acceptance Greps

### 1. `grep -ciE '#FFFFFF|#FFF\b|#000000|#000\b' web/index.html`
```
0
```
Status: TRUE (0 pure white/black matches)

### 2. `grep -ciE 'https?://|cdn|googleapis|unpkg|jsdelivr' web/index.html`
```
0
```
Status: TRUE (0 external resource URLs)

### 3. `grep -cP '^    ' web/index.html`
```
0
```
Status: TRUE (0 4-space indentations; tab indentation preserved)

### 4. `grep -c 'pre-line' web/index.html`
```
1
```
Status: TRUE (1 match)

### 5. `grep -c '倒數歸零就直接繼續，沒有人反對視同確認' web/index.html`
```
1
```
Status: TRUE (1 match)

### 6. `git status --short`
```
 M .superpowers/sdd/progress.md
 M web/index.html
?? docs/agy_results/2026-08-26-demo-frontend-fixes.md
```
Status: Note: `.superpowers/sdd/progress.md` was already modified prior to task dispatch by the orchestrator. `web/index.html` is the only code file modified by this task.

---

## Unverified Items
- Real pipeline execution with live paid LLM APIs and local TTS service (per prompt instruction: do not run live pipeline / paid APIs). Verified via code review, static assertions, and unit tests (`python -m unittest`).
