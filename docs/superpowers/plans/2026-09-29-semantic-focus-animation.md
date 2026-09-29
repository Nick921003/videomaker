# Semantic Focus Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use test-driven-development for each behavior. Execute inline in this already isolated worktree; the user has authorized continuing the video work.

**Goal:** Keep the current explainer palette and legibility while selecting a focus mark by the narrated target: code rail, text underline, figure outline.

**Architecture:** `compile_timeline.py` derives `focus_shape` from lesson element semantics and the action target, without adding coordinates to lesson/actions. `render_video.py` draws each mark from the resolved measured box. Legacy `cards` output keeps its current focus behavior; explainer selects the semantic mark. Both `spotlight` and `laser` use the same shape for the same target; only lifetime differs.

**Tech Stack:** Python 3.10, NumPy, Pillow, FFmpeg, unittest. No new dependency or paid generation stage.

---

### Task 1: Compile semantic focus shapes

**Files:** `video_engine/compile_timeline.py`, `tests/test_visual_style_pipeline.py`.

- [x] Add a failing test that compiles actions against a lesson containing a code element, text element, figure item, and figure caption. Assert code -> `rail`, text/caption -> `underline`, figure item/root -> `outline`; spotlight and laser agree.
- [x] Run `.venv/bin/python -m unittest tests.test_visual_style_pipeline` and confirm the new test fails for missing `focus_shape`.
- [x] Add a small resolver using element type plus target suffix. Pass semantic hints from the lesson page into `compile_slide`; emit `focus_shape` only for explainer so cards stay compatible.
- [x] Re-run the focused test and confirm it passes.

### Task 2: Draw underline and outline from measured boxes

**Files:** `video_engine/render_video.py`, `tests/test_render_video.py`, `docs/MOTION_SPEC.md`.

- [x] Add failing pixel tests: underline stays below the target ink box, outline stays outside the target box, both leave glyph pixels intact, outside pixels change, and both animate from partial to complete.
- [x] Run `.venv/bin/python -m unittest tests.test_render_video` and confirm expected failures.
- [x] Implement bounded, progressive underline and outline drawing using the theme's existing focus color. Dispatch on `focus_shape` for explainer; keep code dimming and cards behavior.
- [x] Re-run focused tests; update the motion spec with target-to-mark rules.

### Task 3: Inspect real video and deliver it playably

**Files:** existing `fresh` lesson/actions/WAV in the main workspace, isolated worktree output, Windows-accessible artifact directory.

- [x] Re-render the existing lesson without `generate_lesson`, `generate_actions`, or `synth`; inspect code, text, and figure frames at full and reduced size.
- [x] Run the complete suite with `.venv/bin/python -m unittest discover -s tests -t .`, then `git diff --check`.
- [x] Export an MP4 plus a small inline GIF and a Windows file path. Codex's built-in MP4 preview was unable to play this user's local file, so do not rely on it.
- [x] Record remaining editorial mismatches separately from renderer defects.
