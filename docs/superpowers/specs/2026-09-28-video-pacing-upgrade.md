# Video Pacing Upgrade — Validation Spec

## Goal

Give an editor actionable, deterministic signals about text density and narration-to-focus alignment before rendering. Support beginner, general, and advanced audiences without treating legitimate teaching variation as an error.

## Existing contract

`lesson.json` contains semantic elements and no geometry. `actions.json` is ordered and `speech` blocks time. `validate.py` already checks references, hidden elements eventually being revealed, action counts, and some narration hygiene. `generate_actions.py` imports `load_lesson` and `check_slide` directly, so their two-argument usage must continue to work. Paid lesson/actions/synth stages are outside this work.

## Rules

1. `load_lesson` indexes the visible wording of title, subtitle, bullet, callout, and figure labels/items. Code is excluded from whole-page text density because it is a distinct walk-through surface. Count Unicode characters consistently. For each slide, compare the total with the selected audience profile; emit a warning with measured and suggested values, never an error. Profiles are `beginner`, `general`, and `advanced`, default `general`; thresholds are advisory and should be calibrated against the committed five examples and the current `fresh` lesson.
2. Profile also controls the existing long-speech warning. Preserve the present general behavior at 70 characters. Beginner warns sooner; advanced permits a longer segment. No speech is rejected for length alone.
3. If a spotlight, laser, or forward camera points to a hidden element before its reveal, emit an error at that action. Eventual reveal is insufficient because the effect is invisible at the time used. A figure part inherits its parent visibility. A camera reset has no target and is exempt.
4. On code slides only, detect explicit spoken line numbers such as `第五行`, `第 5 行`, `第十行到第十三行`, and Arabic numerals. Compare those numbers with the union of code targets selected by spotlight, laser, and forward camera since the previous speech, plus a persistent spotlight from an earlier beat. A spoken number absent from these targeted ranges produces a warning that names the missing line(s). No warning when speech omits explicit line numbers, when there is no code-target effect, or when a sentence refers to multiple lines and all are covered. The rule cannot prove conceptual/semantic agreement; reviewers still assess paraphrases.
5. CLI accepts `--audience beginner|general|advanced` after the two required paths, with or without the historical optional target-seconds positional argument. Unknown audience names fail clearly. The public `check_slide(slide, idx)` call remains valid and uses `general`.

## Calibration and acceptance

- Run the free validator against the five committed lesson/action pairs and read-only `fresh` inputs. Existing samples must not gain new ERRORs unless the target is structurally invisible at that instant; any new warning should identify a plausible editorial review point rather than blanket every page.
- Unit tests cover profile thresholds, Unicode/figure aggregation, hidden focus order, explicit line matching/mismatch, range references, no false warning for paraphrase, and CLI option parsing.
- `validate.py` reports the selected profile and measured counts. No new dependencies or changes outside validator, its tests, and this subproject’s docs.

## Limits

The validator sees actions and lesson text, not measured boxes, WAV timing, or semantic understanding. A warning is a review cue. Visual judgments remain with the human viewer, and word-level narration alignment requires richer evidence than deterministic line references.

## Calibration observed on 2026-09-28

The five named C lessons plus `demo3` all pass validation with no new errors. At the default `general` profile, only `c_string` page 1 is warned (169 displayed characters). The read-only `fresh` inputs for the current sample video also pass and warn on page 1 (147 displayed characters). `beginner` produces 7 advisory warnings across the six committed lesson/action pairs; `advanced` produces none. These counts establish a starting policy, not a learning-science claim. Segment warnings are still present and vary by profile when their measured lengths cross the configured limit.
