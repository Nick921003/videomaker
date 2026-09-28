---
name: video-design-workflow
description: Improve this repository's teaching-video motion, slide style, or pacing with source-based rules and rendered A/B evidence. Use for videomaker visual upgrades; skip ordinary pipeline bug fixes.
---

# Video design workflow

Use this skill for design changes to the teaching videos produced by this repository. Read `CLAUDE.md` first; its rendering invariants take priority over aesthetic preferences.

## Work sequence

1. **Reference.** Ask for 1–3 teaching or explainer videos if the user has not already chosen or delegated the choice. Select references relevant to the subject and audience level. Extract observable rules with timecodes: text hierarchy, palette, reveal or transition duration, emphasis, and speech-to-visual timing. Use media analysis when available. Check every claimed observation against actual frames; a fluent review with wrong visual facts is not evidence. Use references for rules, never copy their assets.
2. **Specify.** Split broad upgrades into motion, static style, and pacing. For each substantial slice, save a spec and an implementation plan under `docs/superpowers/`. State the intended audience, before/after behavior, measured acceptance criteria, and legacy behavior. Keep style preferences separate from correctness requirements.
3. **Implement in the current pipeline.** Theme colors belong in `video_engine/themes/*.json`; typography and measured slide geometry in `render_slides.py`/`layout.py`; motion timings and composition in `motion.py`, `compile_timeline.py`, `render_video.py`, and `docs/MOTION_SPEC.md`; editorial pacing checks in `validate.py`. Put deterministic checks in the validator instead of relying only on prompts. Calibrate advisory limits against real lessons before making them errors.
4. **Verify and present.** Use the same existing lesson, actions, layout, and audio for A/B whenever possible. Render slides, timeline, and video without invoking lesson generation, action generation, or TTS unless the user requests those stages. Inspect title entrance, at least two page changes, a code-focus beat, readability, and narration alignment. Show the A/B artifact and distinguish measured facts from visual preference. Recheck any external media review against extracted frames before citing it.

## Rendering contract

- `base` and `full` PNG geometry must match pixel for pixel; layout includes hidden elements.
- Every addressable element and sub-element has a measured box, and nothing leaves its assigned panel.
- `HEADER_BOX` and `CONTENT_BOX` outlines remain fixed across layouts; theme colors come only from theme JSON.
- Re-rendering the same lesson and seed yields byte-identical PNGs. Preserve the default theme unless a new theme is explicitly selected.
- Add no third-party dependency for a visual upgrade. Reuse the existing environment and `.venv/bin/python`.

Run focused pixel/geometry tests for the changed slice, then `.venv/bin/python -m unittest discover -s tests -t .` and `git diff --check`. A passing test suite does not replace viewing an actual rendered sample.
