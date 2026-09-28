# Video Static Style Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add an opt-in high-contrast teaching style with distinct text hierarchy and monospace code while preserving all renderer contracts.

**Architecture:** The new JSON theme supplies all colors plus font-role names. `render_slides.py` resolves those roles to installed Noto font faces, with a legacy fallback when typography is absent. Code lines in the new theme are fitted against the fixed code panel width before painting.

**Tech Stack:** Python 3, Pillow, fontTools, unittest, existing Noto Sans CJK TTC files.

---

## File map

- `video_engine/themes/lecture.json`: complete opt-in palette and typography role map.
- `video_engine/render_slides.py`: role-based font resolution and opt-in code-width fitting.
- `tests/test_static_style_upgrade.py`: rendered-image, geometry, contrast, legacy-compatibility, and determinism checks.
- This spec and plan: scope and review record.

## Task 1: Establish visual contract (TDD)

- [x] Write tests that load `lecture`, assert complete color groups, foreground contrast, role-to-font behavior, and unchanged `warm` default.
- [x] Run `.venv/bin/python -m unittest tests.test_static_style_upgrade -v`; observe expected failures because the theme/role functions do not exist.
- [x] Add `lecture.json` with these target colors: canvas `#EEF2F5`; card white with `#D6E1E7` edge; title `#162C3C`; subtitle `#426579`; body `#294454`; callout `#A74724`; code background `#13212B` with foreground `#F1F5F7`, keyword `#73D2C4`, preprocessor `#F0BF76`; other effect/figure colors in the same palette.
- [x] Add a small `font_for_role(theme, role)` resolver. Existing themes return `(CJK_FONT, 0)`; `lecture` maps roles through `regular-tc`, `bold-tc`, `mono-tc`. `fit_font` accepts a face index without changing legacy calls.
- [x] Run the focused test; expect pass.

## Task 2: Apply typography and protect code width (TDD)

- [x] Extend tests with an actual `lecture` lesson containing title, subtitle, body, callout, code, and figure, asserting all measured boxes exist and lie inside their fixed panels, plus a long code line that fits by shrinking and an impossible one that raises. A committed mixed slide exercises bullets, callouts, figures, code, and hidden reveal pixels.
- [x] Run focused tests; retain the initial missing-theme and missing-resolver failures as the red phase for this style contract.
- [x] Replace font creation at title, subtitle, bullet/callout, code, figure labels, and captions with the role resolver. Preserve current sizes for first pass, letting regular/bold and code mono create hierarchy without moving layout constants. For opt-in code, use the longest sanitized line, `CODE_BOX[2] - CODE_X - 40` width, 12px floor, and explicit failure if still too wide.
- [x] Run focused tests and existing `tests.test_render_slides`; expect all pass.

## Task 3: Render A/B and verify invariants

- [x] Render one committed representative lesson as default warm and as `lecture` using temporary lesson copies under `/tmp`; run no paid stages.
- [x] Compare full/base layout IDs and bounding boxes, inspect all recorded boxes for panel containment, and re-render `lecture` twice to compare PNG SHA-256 values.
- [x] Run `.venv/bin/python -m unittest discover -s tests -t .` and `git diff --check`. Record any unrelated failure and retain the A/B PNG paths.
- [x] Review spec coverage and report image paths, test evidence, and any residual visual limitations to the root agent. Do not commit.

## Self-review

The scope avoids motion and layout modules, provides a complete selectable palette, maps all text roles, and guards opt-in code width. Legacy themes route through their original font face and sizes. The rendered-image test, deterministic repeat, and measured-box inspection exercise the actual renderer output rather than only helper math.

## Execution evidence

- Initial focused run failed with five expected errors: `lecture` was absent and `font_for_role` did not exist.
- A/B inspection exposed a low-contrast comparison heading; a new contrast test failed with missing `heading_text`, then passed after theme-selected heading colors were added.
- Focused static-style and slide tests: 27 passed before the additional real-lesson test; the added test passed separately.
- All ten warm PNGs matched the pre-change render byte for byte. All ten dark PNGs matched the renderer at `HEAD` byte for byte.
- Ten lecture PNGs matched a second render byte for byte. All 52 boxes in the five-slide representative were inside their assigned panels.
- Review image: `/tmp/videomaker-style-ab/compare.jpg`. Full warm and lecture PNGs are in the adjacent folders.
