# Video Effect Vocabulary Critique & Expansion

## a) Critique of Current 6 Effects (Warm Cream Theme)

- **1. Highlight Wipe (`#F2D9A0` tint, multiply blend, 380ms wipe)**
  - **Verdict:** Pulling weight (Keep / Core effect).
  - **Analysis:** Multiply blend on cream (`#F4EDE2` / `#FBF7F0`) darkens slightly while shifting hue warm; preserves high contrast for dark text (`#3B322A`). Feels like natural physical highlighter on paper.
- **2. Code Focus (Card dim 35%, target line bright, 6px accent bar)**
  - **Verdict:** Pulling weight (Keep / Core effect).
  - **Analysis:** Scoping dim strictly to the code card (`#EFE6D8`) solves the full-screen dark screen user complaint. Left accent bar (`#B85C38`) provides instant spatial orientation for line-by-line C walkthroughs.
- **3. Underline Wipe (5px `#B85C38` line, 1.2s lifespan, trailing dot)**
  - **Verdict:** Redundant / Risky.
  - **Analysis:** Competes directly with Highlight Wipe for the same semantic job ("look at this text"). Fixed 1.2s lifespan easily desyncs from TTS narration timing. Trailing circle (9px radius) adds unnecessary decorative noise.
- **4. Slide-in Reveal (Hidden bullet translates 26px + fade-in, 350ms)**
  - **Verdict:** Pulling weight (Keep / Core effect).
  - **Analysis:** Essential for progressive disclosure in lecture pacing. Subtle 26px offset prevents motion fatigue while clearly signaling newly introduced conceptual points.
- **5. Ken Burns (1.0 → 1.025 whole-page slow zoom across scene)**
  - **Verdict:** Risky / Harmful on technical slides.
  - **Analysis:** Continuous sub-pixel bilinear scaling on monospace C code and Chinese font hinting causes continuous resampling blur and shimmer. Degrades visual crispness without pedagogical benefit.
- **6. Camera Push (Crop & scale to bbox ≤1.4x, eased, explicit reset)**
  - **Verdict:** Pulling weight (Keep, use sparingly).
  - **Analysis:** Effective for isolating complex structs, pointer diagrams, or dense code blocks during detailed multi-sentence explanations, provided it resets cleanly at scene transitions.

---

## b) 5 Additional Implementable Effects (Numpy / Pillow Math)

### 1. Scope Bracket Enclosure
- **Pedagogical Purpose:** Groups multi-line code constructs (loops, conditionals, function bodies, structs) to communicate lexical and execution scope.
- **Math Sketch:**
  - Given line range $Y = [y_1, y_2]$ and left edge $x_0 = \text{box}.x - 10$:
  - Progressive stroke $p = \text{ease\_out}(\min(1, \Delta t / 300\text{ms}))$.
  - Pillow `ImageDraw.line` draws bracket backbone $(x_0, y_1) \to (x_0, y_1 + (y_2 - y_1) \cdot p)$ with top/bottom horizontal serif ticks $(x_0, y) \to (x_0 + 6, y)$ in accent `#B85C38` (2px stroke).
- **Duration:** 300ms draw animation.
- **Exit Condition:** Narration segment end (fades out 150ms).

### 2. Pointer / Flow Arrow Draw
- **Pedagogical Purpose:** Connects pointer variables to memory addresses, caller to callee, or text explanations to code tokens.
- **Math Sketch:**
  - Given source center $P_0(x_0, y_0)$ and target bbox edge $P_1(x_1, y_1)$:
  - Progress $p = \text{ease\_out}(\min(1, \Delta t / 320\text{ms}))$, current head $P(t) = P_0 + p \cdot (P_1 - P_0)$.
  - Pillow `ImageDraw.line([P_0, P(t)], fill=accent, width=3)`. When $p \ge 0.9$, draw triangular arrowhead polygon at $P(t)$ scaled by $(p - 0.9)/0.1$.
- **Duration:** 320ms draw animation.
- **Exit Condition:** Fades out when the relational thought unit ends.

### 3. Inline Evaluation Badge Pop (Runtime Value Callout)
- **Pedagogical Purpose:** Displays runtime evaluation, return value, or stdout output immediately beside an active expression (e.g. `sum += i` $\to$ `[sum = 15]`).
- **Math Sketch:**
  - Measured target line right edge $(x_{\text{right}} + 12, y_{\text{center}})$.
  - Scale factor $s(t) = 1.0 + 0.12 \cdot (1 - p) \cdot \sin(p \cdot \pi)$ (spring pop over 250ms), alpha $\alpha(t) = \text{clamp}(t / 150\text{ms}, 0, 1)$.
  - Pillow creates small rounded rectangle card (`fill=#FBF7F0`, `outline=#B85C38`, `text=#B85C38`), scaled by $s(t)$ via bilinear resize, then alpha-blended over frame slice: $\text{frame} = (1 - \alpha)\text{frame} + \alpha \cdot \text{badge}$.
- **Duration:** 250ms pop-in.
- **Exit Condition:** Clears when advancing to next code line.

### 4. Code Token Pulse Box (Variable Callout / Definition)
- **Pedagogical Purpose:** Highlights a single token (e.g. variable name, keyword, type specifier) during precise sentence-level mentions without dimming surrounding lines.
- **Math Sketch:**
  - Box $B = [x-3, y-2, w+6, h+4]$.
  - Draw rounded rectangle with 2px stroke in `#B85C38` and soft interior tint `#F2D9A0` at opacity $\alpha(t) = 0.25 \cdot \text{ease\_out}(\min(1, \Delta t / 200\text{ms}))$.
  - Numpy slice multiply: $\text{frame}[y:y+h, x:x+w] = \text{frame} \cdot (1 - \alpha \cdot (1 - \text{tint}/255))$.
- **Duration:** 200ms ease-in, holds steady.
- **Exit Condition:** Narration segment end (150ms alpha decay).

### 5. In-Place State Cross-Fade (Code Mutation / Refactor Diff)
- **Pedagogical Purpose:** Demonstrates before/after state transitions (e.g., pointer reassignment, variable mutation, bug correction) directly in place.
- **Math Sketch:**
  - Pre-rendered state $A$ (before) and state $B$ (after) patch for target bbox.
  - Blend progress $p = \text{ease\_in\_out}(\min(1, \Delta t / 350\text{ms}))$.
  - Patch blend: $\text{patch}(t) = (1 - p) \cdot A[\text{box}] + p \cdot B[\text{box}]$.
  - Flash accent overlay: add $0.15 \cdot \sin(p \cdot \pi) \cdot \text{highlight\_rgb}$ to reinforce the mutation event.
- **Duration:** 350ms transition.
- **Exit Condition:** Permanent until slide change.

---

## c) Pacing Rule of Thumb (24s Slide / 4 Narration Segments)

- **Density Cap:** Exactly **1 primary visual beat per narration segment** (total: **3 to 4 distinct visual beats per 24-second slide**).
- **Temporal Rhythm:**
  - **0.0s – 0.4s:** Effect entry (fast ease-out, 200–380ms).
  - **0.4s – 5.5s:** Visual freeze / stable dwell (viewer listens to TTS and parses text with zero moving pixels).
  - **5.5s – 6.0s:** Micro-exit / reset (150ms) or direct cut into segment 2 effect.
- **Noise Threshold:** Any scene exceeding **5 simultaneous or overlapping motion events** creates cognitive overload and degrades comprehension.

---

## d) The One Thing to Cut

- **Cut Ken Burns (Continuous ambient zoom on static slides).**
  - **Reason:** Continuous sub-pixel scaling ruins font rasterization and hinting for Chinese typography and monospace code, creating constant shimmering/blurring artifacts. Technical teaching demands rock-solid visual stability.
