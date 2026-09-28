# Video Static Style Upgrade Specification

## Purpose

Improve readability and visual hierarchy of 1080p teaching slides while preserving the renderer's semantic content, measured geometry, and deterministic output. This is an opt-in style choice for future audience-specific video generation; `warm` remains the default until integration decides otherwise.

## Scope

- Add a complete `lecture` theme with a cool, high-contrast palette for the canvas, cards, text, code, figures, and video effects. Comparison figure headings use their own dark band and light text so a pale border can remain subtle without weakening label contrast.
- Add theme-selected font roles using the already installed Noto Sans CJK font collection. `lecture` uses TC regular body/subtitle/captions, TC bold title/callout/figure headings, and TC monospace regular code. Existing themes without a typography map retain their exact legacy font path, face index, sizes, and rendering.
- Fit the opt-in code font to the measured code panel width, preserving line-addressable boxes. If a line cannot fit at the 12px code floor, fail explicitly instead of overflowing.
- Keep all color values in theme JSON. The renderer may contain font paths and role mappings, but no new literal RGB values.

## Out of scope

Motion, narration, content rewriting, audience-level inputs, layout geometry rules, and paid lesson/actions/synth stages. No third-party dependencies.

## Invariants

- `HEADER_BOX`, `CONTENT_BOX`, and `CODE_BOX` do not move.
- Hidden elements use the same measured positions in base and full images.
- Every existing element and sub-element identifier retains a measured box.
- An element cannot draw outside its assigned region; long opt-in code lines must shrink or raise.
- Re-rendering the same lesson and theme produces byte-identical PNGs.
- Legacy `warm` and `dark` outputs remain byte-identical.

## Acceptance

1. A lesson with `"theme": "lecture"` renders with title, subtitle, body, callout, code, and figure roles in the selected font faces and theme colors.
2. The `lecture` body and code foreground/background pairs meet at least WCAG 4.5:1 contrast; title and subtitle meet at least 3:1.
3. A sufficiently long opt-in code line shrinks to fit; an impossible line raises a clear error. Measured line boxes stay inside `CODE_BOX`.
4. Two render runs of a representative lesson yield byte-identical PNGs. `warm` is still the default, and a warm representative retains its prior checksum.
5. A/B images of the same representative lesson are saved under `/tmp` for review; visual preference remains for the user to judge.
