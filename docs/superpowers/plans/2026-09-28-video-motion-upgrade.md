# Video Motion Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make the first hook slide visibly enter and replace text-ghosting page fades with a sequential fade through a clean card surface, without changing slide PNG geometry or paid generation stages.

**Architecture:** The timeline compiler adds semantic intro metadata from the first hook slide and measured layout boxes. The video renderer composites the intro and page transition at frame time. Existing action JSON, slide PNGs, voice clips, and layout contracts remain the source of truth.

**Tech Stack:** Python 3.10, NumPy, Pillow, FFmpeg, unittest; existing project environment only.

**Spec:** `docs/superpowers/specs/2026-09-28-video-motion-upgrade.md`

---

## File responsibility map

| File | Responsibility |
| --- | --- |
| `video_engine/compile_timeline.py` | Add intro metadata for the first hook slide using measured boxes |
| `video_engine/render_video.py` | Composite title/subtitle entrance and surface transition |
| `video_engine/motion.py` | Keep intro and transition timing constants in one place |
| `tests/test_motion_upgrade.py` | Verify timeline metadata and actual frame pixels |
| `docs/MOTION_SPEC.md` | Record behavior, timing, limits, and why it is used |

## Task 1: First hook intro metadata

**Files:** Modify `video_engine/compile_timeline.py`; create `tests/test_motion_upgrade.py`.

- [x] **Step 1: Write the failing test.** Build a hook slide with title/subtitle IDs and measured boxes. Assert the first scene's intro has only those boxes and starts at scene start. A non-hook slide and a missing title box return no intro. Test the pure helper `intro_for(slide, boxes, start_ms)`.
- [x] **Step 2: Run** `.venv/bin/python -m unittest tests.test_motion_upgrade -v`. Expected: fail because `intro_for` does not exist.
- [x] **Step 3: Add `intro_for`** with this contract: it returns `None` unless role is hook and the title ID has a measured box. Otherwise return `{"start_ms": start_ms, "title": boxes[title_id], "subtitle": boxes.get(subtitle_id)}`. In `main`, call it only for the first slide and attach a nonempty result to `scene["intro"]`.
- [x] **Step 4: Run** `.venv/bin/python -m unittest tests.test_motion_upgrade tests.test_regression -v`. Expected: new test and existing timeline regression pass.

## Task 2: Pixel-safe title and subtitle entrance

**Files:** Modify `video_engine/render_video.py` and `video_engine/motion.py`; extend `tests/test_motion_upgrade.py`.

- [x] **Step 1: Write the failing pixel test.** Use a synthetic 160x100 RGB frame with dark title and subtitle rectangles over a light card. Assert `apply_intro(frame, full, intro, 0, card_rgb)` removes both ink regions, an intermediate frame differs from both endpoints, and at `INTRO_TOTAL_MS` it equals the original frame byte for byte. Assert pixels outside the two measured boxes plus the bounded upward movement are untouched.
- [x] **Step 2: Run** `.venv/bin/python -m unittest tests.test_motion_upgrade -v`. Expected: fail because `apply_intro` and the timing constants do not exist.
- [x] **Step 3: Add constants** `INTRO_TITLE_MS=480`, `INTRO_SUB_DELAY_MS=120`, `INTRO_SUB_MS=480`, and `INTRO_TOTAL_MS=600` in `motion.py`. Add `apply_intro` in `render_video.py`: blank the measured ink rectangles with `theme["card"]["fill"]`; blend cropped source ink from up to 16 px above the title and 10 px above the subtitle, clamped inside `HEADER_BOX`, using `ease_enter`. At `t >= INTRO_TOTAL_MS`, return the original frame unchanged. Invoke it for a scene intro after base/reveals and before spotlight effects.
- [x] **Step 4: Run** `.venv/bin/python -m unittest tests.test_motion_upgrade tests.test_render_video -v`. Expected: all tests pass.

## Task 3: Page transition without text ghosts or clipped words

**Files:** Modify `video_engine/render_video.py`; extend `tests/test_motion_upgrade.py`.

- [x] **Step 1: Try the original 32 px soft-edge wipe** and A/B render existing `fresh` material. At 22.60 s it clips right-side words and leaves old table stripes.
- [x] **Step 2: Compare vertical push and a sequential fade through a clean card surface.** The vertical push still slices horizontal rows in the content card. Select the surface transition.
- [x] **Step 3: Write a failing pixel test** asserting the transition begins at old, reaches the neutral card at midpoint, ends at new, and never directly blends old and new text.
- [x] **Step 4: Add `transition_surface(canvas, theme)` and `dip_to_surface(previous, current, surface, progress)`**; render the fixed card outlines from theme colors and keep `TRANS_MS=420`.
- [x] **Step 5: Run** `.venv/bin/python -m unittest tests.test_motion_upgrade tests.test_render_video -v`.

## Task 4: Existing-material A/B and documentation

**Files:** Modify `docs/MOTION_SPEC.md`; no generated media committed.

- [x] **Step 1: Update the motion spec** to name the hook entrance, its 480/120/600 ms timings, the two-phase clean-card transition, and the A/B evidence for replacing both full-frame crossfades and the initial soft wipe.
- [x] **Step 2: Run** `.venv/bin/python -m unittest discover -s tests -t .`; expected: zero failures and errors. Run `git diff --check`; expected: no output.
- [x] **Step 3: Using existing `fresh` lesson, actions, and saved durations/audio**, render to a temporary directory with the new compiler/renderer. Compare first 0.6 s and two page boundaries with the original MP4 using frame-change measurements; attempt AGY media review, then verify its claims against extracted frames; discard claims contradicted by pixels. Do not invoke lesson, actions, or synth.
- [x] **Step 4: Review the diff and spec coverage.** Confirm intro metadata is absent on non-hook/legacy timelines; base/full PNG bytes and measured layout boxes are unchanged. If a visual regression appears, revise the implementation and rerun the focused tests plus A/B.

## Self-review

- Scope: hook entrance and bounded transition cover this first motion slice; code focus is diagnostic-only until a real renderer mismatch is reproduced.
- Contracts: no coordinates in lesson/actions; all intro boxes come from layout; no new dependency or paid stage.
- Placeholder scan: no deferred implementation steps.

## Execution evidence

- Existing `fresh` lesson/actions/layout/audio rendered to `/tmp/video-motion-final-20260928/` at 80.4 s. The integrated `lecture` sample rendered to `/tmp/video-lecture-final-20260928/` using the same actions and voice clips. No lesson, action, or TTS generation ran.
- A/B frames at 0.0/0.3/0.6 s show the title absent, entering, then fully present. Frames near 22.6, 47.4, and 62.3 s show the old crossfade's overlapping page text and the new two-phase card transition. The selected transition does not cut words at the moving boundary.
- The code walkthrough timeline targets L5 at 47.66–53.50 s, L6 at 53.50–57.62 s, and L7 at 57.62 s. The previous subjective lag report does not establish a renderer fault, so code focus timing was not changed.
- Full test suite: 184 tests passed, 1 skipped. `git diff --check` produced no errors. The original slide PNGs were read for A/B; the motion pass does not modify them. Static-style tests cover byte-identical legacy PNGs and deterministic `lecture` PNGs.
- AGY media review was attempted twice. The second response described a hard cut and a dark title band, which contradict the extracted frames. It was not used as acceptance evidence.
