# Video Explainer Redesign Plan

**Goal:** Repair text contrast and unify focus effects, then add a reusable full-canvas explainer mode while keeping legacy output stable.

**Stack:** existing Python 3.10, Pillow, NumPy, FFmpeg, unittest; no added dependency.

**Spec:** `docs/superpowers/specs/2026-09-29-video-explainer-redesign.md`

## 1. Contrast and common focus

**Files:** `video_engine/render_video.py`, `video_engine/themes/lecture.json`, `tests/test_render_video.py`, `docs/MOTION_SPEC.md`.

- [x] Add a pixel test with dark text on a light background: `spotlight` and `laser` must leave all glyph pixels unchanged while drawing the same focus accent outside the measured ink box. Check local contrast and endpoints.
- [x] Replace multiplicative text tint and underline with one `focus_mark` compositor. Preserve code dimming and target line brightness. Theme defines a focus color with sufficient contrast on light and dark surfaces.
- [x] Render an existing short segment to verify the text remains readable, including intro/highlight overlap.

## 2. Full-canvas scene renderer

**Files:** new `video_engine/render_explainer.py`, `video_engine/themes/explainer.json`, `video_engine/render_slides.py`, `tests/test_render_explainer.py`.

- [x] Write failing artifact tests for four semantic archetypes and unsupported fallback. Inspect actual PNG/layout output: all IDs and subitems measured, no overflow, hidden base/full geometry stable, deterministic output, no fixed card borders.
- [x] Implement `--visual-style explainer` dispatch. Render large semantic objects for compare, model, code trace, and pitfall; use role-based type sizes and shared safe margins. Retain default `cards` path byte for byte.
- [x] Confirm the new theme's text and focus contrast on all surfaces at native and reduced preview size.

## 3. Video composition and A/B

**Files:** `video_engine/compile_timeline.py`, `video_engine/render_video.py`, motion tests and docs.

- [x] Carry `visual_style` from layout into timeline. For explainer use a clean full-canvas transition, no card outlines; use measured boxes for camera/focus and a unified mark for both action names.
- [x] Reuse existing `fresh` layout inputs, actions and WAV durations. Render at least a 10–20 second segment and one full comparison sample without running lesson/actions/synth. Place a playable file under the Windows-accessible artifact directory.
- [x] Run focused tests and the complete suite; compare legacy PNG hashes, new PNG determinism, all measured boxes, and `git diff --check`. Record any editorial source mismatch rather than hiding it in visuals.

## Review criteria

Reject an implementation if it merely removes the old card borders while preserving a static centered slide, changes focus colors without fixing glyph compositing, silently drops addressable figure parts, or makes a source-content error look like a renderer fix.
