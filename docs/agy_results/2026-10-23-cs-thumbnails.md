# CS Zone Article Cover Thumbnails Report

## Summary Table

| Article / Subject | Final File Path | Pixel Dimensions | File Size | Title Rendered Exactly |
| :--- | :--- | :--- | :--- | :--- |
| **Cover 1**: printf 沒出來？ | `/home/pjw92/projects/BridgeAI/BridgeAI_Blog/public/images/cs/vscode-run-code-printf-thumb.webp` | 1600x900 | 63.8 KB | **yes** |
| **Cover 2**: 中文變亂碼？ | `/home/pjw92/projects/BridgeAI/BridgeAI_Blog/public/images/cs/vscode-terminal-chinese-garbled-thumb.webp` | 1600x900 | 46.2 KB | **no** |

---

## Detailed Inspection & Typography Audit

### Cover 1: `vscode-run-code-printf-thumb.webp`
- **Target Path**: `/home/pjw92/projects/BridgeAI/BridgeAI_Blog/public/images/cs/vscode-run-code-printf-thumb.webp`
- **Target Title**: 「printf 沒出來？」
- **Dimensions**: 1600x900 (WebP)
- **File Size**: 63.77 KB (well under the 450 KB constraint)
- **Title Rendered Exactly**: **yes**
- **Audit Findings**:
  - Latin text `printf` rendered cleanly in bold dark-emerald sans-serif with a crisp white silhouette outline.
  - Traditional Chinese characters 「沒出來？」 rendered with 100% stroke accuracy (`沒`: 氵+殳; `出`: 山+山; `來`: Traditional 來; fullwidth question mark `？`).
  - Scene elements faithfully match specification: simplified code editor with bottom output showing `[Running]` followed by blank space, a translucent 3D box labeled "Buffer" holding a text document "請輸入...", and the puzzled student boy in the signature green hoodie with backpack.

### Cover 2: `vscode-terminal-chinese-garbled-thumb.webp`
- **Target Path**: `/home/pjw92/projects/BridgeAI/BridgeAI_Blog/public/images/cs/vscode-terminal-chinese-garbled-thumb.webp`
- **Target Title**: 「中文變亂碼？」
- **Dimensions**: 1600x900 (WebP)
- **File Size**: 46.24 KB (well under the 450 KB constraint)
- **Title Rendered Exactly**: **no**
- **Audit & Regeneration Log**:
  - **Try 1**: Produced title where 「亂」 was rendered in green while the other glyphs were navy; internal strokes of 「亂」 and 「變」 exhibited partial stroke mutations.
  - **Try 2**: Unified color to navy across all characters, but the left radical 𤔔 of 「亂」 remained structurally malformed.
  - **Try 3**: Evaluated under magnification; the character 「亂」 still failed Traditional Chinese typographic standards (left component distorted rather than standard Kangxi 𤔔).
  - **Fallback Execution (Per Constraint Rule)**: As the image model could not produce an exact, uncorrupted Traditional Chinese title within 3 tries, rendered the final illustration **WITHOUT title**, preserving a clean, empty rounded top card area. This allows exact Traditional Chinese typography (e.g. Noto Sans TC / 微軟正黑體) to be cleanly overlaid downstream.
