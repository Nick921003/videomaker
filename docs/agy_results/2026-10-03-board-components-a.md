# Board Components A+C Run

## Verification Output
```
/tmp/tmp.pXjUMQpRqb/tl.json：42.34s，21 個動作，0 個缺口，0 則警告
/tmp/tmp.pXjUMQpRqb/out/player.html
量測閘：取樣 75 格，通過
.........................
----------------------------------------------------------------------
Ran 25 tests in 0.007s

OK
```

## Frame Analysis

**t = 12.0**
- Texts visible: Cells row has no characters yet (hatching visible), tail text "其餘仍未知" is visible. Output/Metrics not visible.
- Flying characters: "A" flying between the top left "src" string and the first cell of "name".
- Clipped/Overlapping: None.
- Pointer: Not visible. Accent circle: None.

**t = 16.5**
- Texts visible: Cells row has "A", "l", "i", "c", "e", "\0". Output/Metrics not visible.
- Flying characters: None.
- Clipped/Overlapping: None.
- Pointer: Not visible. Accent circle: Around the "\0" cell (drawn by global mark).

**t = 21.0**
- Texts visible: Cells row has "A", "l", "i", "c", "e", "\0". Output box is empty. Metrics not visible.
- Flying characters: None.
- Clipped/Overlapping: None.
- Pointer: Visible above the "A" cell (index 0). Accent circle: Around the "\0" cell.

**t = 23.0**
- Texts visible: Cells row has "A", "l", "i", "c", "e", "\0". Output box has "Al". Metrics not visible.
- Flying characters: "i" flying between the 3rd cell and the output box.
- Clipped/Overlapping: None.
- Pointer: Visible above the "i" cell (index 2). Accent circle: Around the "\0" cell.

**t = 25.2**
- Texts visible: Cells row has "A", "l", "i", "c", "e", "\0", and "到這裡就停" text below "\0". Output box has "Alice". Metrics not visible.
- Flying characters: None.
- Clipped/Overlapping: None.
- Pointer: Visible above the "\0" cell (index 5). Accent circle: Around the "\0" cell.

**t = 28.5**
- Texts visible: Cells row has "A", "l", "i", "c", "e", "\0", and "到這裡就停". Output box has "Alice". Metrics not visible.
- Flying characters: None.
- Clipped/Overlapping: None.
- Pointer: Visible above the "\0" cell (index 5). Accent circle: Around the "\0" cell.

**t = 33.5**
- Texts visible: Cells row has "A", "l", "i", "c", "e", "\0". Output box not visible. Metrics columns have "容量" (32) and "長度" (5) with their notes.
- Flying characters: None.
- Clipped/Overlapping: None.
- Pointer: Visible above the "\0" cell (index 5). Accent circle: Around the "\0" cell.

**t = 41.0**
- Texts visible: Cells row has "A", "l", "i", "c", "e", "\0". Output box not visible. Metrics columns have "容量" (32), "長度" (5), "至少需要" (6) and their notes.
- Flying characters: None.
- Clipped/Overlapping: None.
- Pointer: Visible above the "\0" cell (index 5). Accent circle: Around the "\0" cell.

## Spec Ambiguities Resolved
1. **`fill` action fields**: Spec didn't mention whether to use `args.chars` or `args.values`. Checking `c_string.scene.json`, it uses `args.values`. Updated logic to fallback to `args.chars` if `args.values` is missing. The `args.start` was also missing from the JSON, so I defaulted it to `0`.
2. **`scan` and `brace` action bounds**: Spec mentioned `args.lo`, but the scene uses `args.range: [lo, hi]`. Updated the components to read `args.range[0]` and `args.range[1]`, falling back to `args.lo` and `args.hi`.
3. **Metrics text fading**: Spec mentioned "揭露前不畫" and using `api.write` for the value, but didn't specify how the label and note should appear. I applied `alpha: p` so they gracefully fade in as the value writes.
