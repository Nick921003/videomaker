# Video Pacing Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add configurable, evidence-based pacing diagnostics to the existing validator.

**Architecture:** Extend `load_lesson` with semantic display text while retaining its existing index keys. Add pure helpers in `validate.py` for profile lookup, spoken line parsing, and per-slide pacing diagnostics. Wire them into `check_slide` and the CLI without changing the producer contract or requiring model/TTS runs.

**Tech Stack:** Python standard library, unittest, existing JSON examples.

---

## File map

- `video_engine/validate.py`: audience profiles, display-density and focus-alignment diagnostics, backward-compatible `check_slide`, CLI argument parsing.
- `tests/test_pacing_validation.py`: focused behavioral and CLI tests.
- `docs/superpowers/specs/2026-09-28-video-pacing-upgrade.md`: rationale, contract, acceptance.
- `docs/superpowers/plans/2026-09-28-video-pacing-upgrade.md`: ordered implementation and verification.

### Task 1: Display density and speech profiles

- [x] Add failing tests that build a small lesson JSON, load its index, and assert figure labels contribute to displayed-character count while code does not.
- [x] Run `.venv/bin/python -m unittest tests.test_pacing_validation -v`; expect a failing assertion for the missing display index/profile warnings.
- [x] Add `PACING_PROFILES` with beginner/general/advanced advisory limits. General speech limit stays 70. `load_lesson` records display-character count; `check_slide(..., audience_level="general")` warns when count or speech length exceeds the chosen profile. Keep `check_slide(slide, idx)` valid.
- [x] Re-run the focused tests; expect pass.

### Task 2: Visible focus and line-reference alignment

- [x] Add tests for a hidden target focused before reveal (error), after reveal (no error), spoken code line inside a selected range (no warning), spoken line outside it (warning), and speech with no line reference (no warning).
- [x] Run the focused tests; expect failure on at least one behavior.
- [x] Track reveal order while scanning actions. Parse Chinese 1–99 and Arabic spoken line references. At each speech, compare explicit line mentions with code effect ranges in the current beat; preserve the last spotlight as context. Only warn when there is a code effect and a provable mismatch.
- [x] Re-run focused tests; expect pass.

### Task 3: CLI and real-material calibration

- [x] Add a CLI test that runs `validate.py lesson actions --audience beginner` and checks the selected profile appears; invalid audience returns code 2. Keep historical `target_seconds` positional invocation working.
- [x] Run the focused tests; expect failure; implement argument parsing and re-run.
- [x] Run `validate.py` on `c_loop`, `c_string`, `c_struct`, `c_struct_combo`, `c_struct_v3`, and read-only `fresh` inputs for each profile. Inspect warnings and adjust advisory thresholds only when evidence shows broad false positives. Never run paid stages.
- [x] Run `.venv/bin/python -m unittest tests.test_pacing_validation tests.test_regression -v` and `git diff --check`. Review changed files and report any limits.

No commit: the parent task will integrate worktree changes.
