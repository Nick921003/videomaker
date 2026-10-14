# 概念樹逐層展開（A1）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Concept tree contract 1.3: each key point grows meaning → (example group → example, pitfall group → pitfalls) as real tree nodes; workbench expands one level per click with no side panel.

**Architecture:** `studio/concept_tree.py` emits all nodes (pure function). `studio/mindmap.py` validates 1.3 and renders a fully expanded static SVG. The workbench viewer already expands one level per click and only builds the side panel for 1.2, so the frontend change is per-kind card styling plus tests.

**Tech Stack:** Python 3 stdlib + Pillow (text measuring), vanilla ES modules, `node --test`.

**Spec:** `docs/superpowers/specs/2026-10-14-concept-tree-progressive-design.md`

## Global Constraints

- Indent with **tabs**. Comments in **Chinese**, sparse, only "why". Match surrounding style (dense one-liners in `mindmap.py` and `concept-tree.mjs`).
- No new third-party dependencies.
- Contracts 1.0 / 1.1 / 1.2 behaviour and SVG bytes must not change.
- Determinism: same input → byte-identical SVG.
- Do NOT run paid stages, do NOT set `E2E=1`, do NOT call Gemini. Do NOT `git push`.
- Python: always `.venv/bin/python`. Full suite: `.venv/bin/python -m unittest discover -s tests -t .`. Frontend: `node --test workbench/web/tests`.
- Assert on produced artifacts (built tree / rendered SVG), not by comparing one formula against another.

---

### Task 1: Contract 1.3, builder and static SVG

**Files:**
- Modify: `studio/concept_tree.py`
- Modify: `studio/mindmap.py` (`canonical_mindmap` lines ~50–105, `render_mindmap_svg` dispatch line ~183, `_render_explorable_svg` lines ~238–290)
- Modify: `tests/test_concept_tree.py`

**Interfaces:**
- Produces: `build_concept_tree(key_points, material) -> dict` returning `contract_version: "1.3"`; node kinds `concept | meaning | group | example | pitfall`; derived ids `{pid}-meaning`, `{pid}-example-group`, `{pid}-example`, `{pid}-pitfall-group`, `{pid}-pitfall-{n}` (n from 1).
- SVG keeps the attributes the viewer reads: `g[data-node-id][data-node-kind]`, `title[data-node-label]`, `desc[data-node-explanation]`, `desc[data-node-quote]`, `path[data-from][data-to]`, root `svg[data-root-id][data-contract-version][data-layout]`; `data-handout-page` only on non-root concept nodes.

- [ ] **Step 1: Pin 1.2 SVG bytes before touching anything**

Compute the md5 of the current 1.2 output so the regression test can pin it:

```bash
.venv/bin/python - <<'EOF'
import hashlib
from studio.concept_tree import build_concept_tree
from studio.mindmap import render_mindmap_svg
from tests.fixtures.key_points import sample_key_points
from tests.fixtures.teaching_quality import MATERIAL
tree = build_concept_tree(sample_key_points(), MATERIAL)
print(tree['contract_version'], hashlib.md5(render_mindmap_svg(tree, MATERIAL)).hexdigest())
EOF
```

Keep a copy of this 1.2 tree as a JSON fixture `tests/fixtures/concept_tree_v12.json` (dump `tree` with `ensure_ascii=False, indent='\t'`), so the 1.2 path stays testable after the builder switches to 1.3.

- [ ] **Step 2: Write failing tests** — replace `tests/test_concept_tree.py` with:

```python
"""概念樹 1.3：重點底下長出定義，定義底下分例子與常見錯誤；內容直接長在樹上。"""
import hashlib
import json
import re
import unittest
from copy import deepcopy
from pathlib import Path

from studio.concept_tree import build_concept_tree
from studio.mindmap import MindmapError, canonical_mindmap, render_mindmap_svg
from tests.fixtures.key_points import sample_key_points
from tests.fixtures.teaching_quality import MATERIAL

V12 = Path(__file__).resolve().parent / 'fixtures/concept_tree_v12.json'
V12_MD5 = '<md5 printed in Step 1>'


def children_of(tree):
	result = {node['id']: [] for node in tree['nodes']}
	for edge in tree['edges']:
		result[edge['from']].append(edge['to'])
	return result


class TestConceptTree13(unittest.TestCase):
	def setUp(self):
		self.points = sample_key_points()
		self.tree = build_concept_tree(self.points, MATERIAL)
		self.nodes = {node['id']: node for node in self.tree['nodes']}
		self.children = children_of(self.tree)

	def test_point_grows_meaning_first_then_child_points(self):
		self.assertEqual(self.tree['contract_version'], '1.3')
		self.assertEqual(self.children['three_parts'][0], 'three_parts-meaning')
		self.assertEqual(self.children['three_parts'][1:], ['choose'])
		meaning = self.nodes['three_parts-meaning']
		self.assertEqual(meaning['kind'], 'meaning')
		point = next(p for p in self.points['points'] if p['id'] == 'three_parts')
		self.assertEqual(meaning['label'], point['explanation'])

	def test_meaning_splits_into_example_then_pitfalls(self):
		for point in self.points['points']:
			pid, kids = point['id'], self.children[f"{point['id']}-meaning"]
			expected = []
			if point['example'] is not None and point['example']['kind'] != 'none':
				expected.append(f'{pid}-example-group')
				self.assertEqual(self.nodes[f'{pid}-example-group']['label'], '例子')
				self.assertEqual(self.children[f'{pid}-example-group'], [f'{pid}-example'])
				self.assertEqual(self.nodes[f'{pid}-example']['label'], point['example']['content'].strip('\n'))
			if point['misconceptions']:
				expected.append(f'{pid}-pitfall-group')
				self.assertEqual(self.nodes[f'{pid}-pitfall-group']['label'], '常見錯誤')
				self.assertEqual(self.children[f'{pid}-pitfall-group'],
					[f'{pid}-pitfall-{n}' for n in range(1, len(point['misconceptions']) + 1)])
				first = point['misconceptions'][0]
				self.assertEqual(self.nodes[f'{pid}-pitfall-1']['label'],
					f"錯：{first['wrong']}\n為什麼：{first['why']}\n正確：{first['correct']}")
			self.assertEqual(kids, expected, pid)

	def test_missing_example_or_pitfalls_grow_nothing(self):
		points = sample_key_points()
		points['points'][0]['example'] = None
		points['points'][0]['misconceptions'] = []
		tree = build_concept_tree(points, MATERIAL)
		pid = points['points'][0]['id']
		self.assertEqual(children_of(tree)[f'{pid}-meaning'], [])
		ids = {node['id'] for node in tree['nodes']}
		self.assertNotIn(f'{pid}-example-group', ids)
		self.assertNotIn(f'{pid}-pitfall-group', ids)

	def test_quotes_pages_and_explanations(self):
		for node in self.tree['nodes']:
			self.assertEqual(node['explanation'], '')
			if node['id'] == 'root':
				self.assertIsNone(node['handout_page'])
				continue
			self.assertIn(node['source_quote'], MATERIAL)
			if node['kind'] == 'concept':
				self.assertIsInstance(node['handout_page'], int)
			else:
				self.assertIsNone(node['handout_page'])

	def test_contract_rejects_bad_13_nodes(self):
		bad = deepcopy(self.tree); bad['nodes'][1]['handout_page'] = None
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		bad = deepcopy(self.tree); next(n for n in bad['nodes'] if n['kind'] == 'meaning')['handout_page'] = 2
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		bad = deepcopy(self.tree); next(n for n in bad['nodes'] if n['kind'] == 'group')['label'] = '一' * 9
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		bad = deepcopy(self.tree); next(n for n in bad['nodes'] if n['kind'] == 'meaning')['explanation'] = '多的'
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		bad = deepcopy(self.tree); bad['edges'][0]['label'] = '包含'
		with self.assertRaises(MindmapError): canonical_mindmap(bad)
		v12 = json.loads(V12.read_text(encoding='utf-8'))
		next(n for n in v12['nodes'] if n['id'] != 'root')['kind'] = 'group'
		with self.assertRaises(MindmapError): canonical_mindmap(v12)

	def test_svg_is_deterministic_inside_canvas_without_overlap(self):
		first = render_mindmap_svg(self.tree, MATERIAL)
		self.assertEqual(first, render_mindmap_svg(self.tree, MATERIAL))
		text = first.decode('utf-8')
		self.assertIn('data-contract-version="1.3"', text)
		self.assertIn('data-node-id="three_parts-example" data-node-kind="example"', text)
		self.assertIn('Noto Sans Mono CJK TC', text)
		width, height = map(float, re.search(r'<svg[^>]* width="([\d.]+)" height="([\d.]+)"', text).groups())
		boxes = [tuple(map(float, m)) for m in
			re.findall(r'<g data-node-id="[^"]+"[^>]*>.*?<rect x="([\d.-]+)" y="([\d.-]+)" width="([\d.]+)" height="([\d.]+)"', text)]
		self.assertEqual(len(boxes), len(self.tree['nodes']))
		for x, y, w, h in boxes:
			self.assertTrue(0 <= x and 0 <= y and x + w <= width and y + h <= height)
		for i, (x1, y1, w1, h1) in enumerate(boxes):
			for x2, y2, w2, h2 in boxes[i + 1:]:
				self.assertFalse(x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1)
		for node in self.tree['nodes']:
			if node['kind'] == 'example':
				lines = node['label'].count('\n') + 1
				block = re.search(rf'<g data-node-id="{re.escape(node["id"])}".*?</g>', text, re.S).group(0)
				self.assertGreaterEqual(block.count('<text '), lines)

	def test_v12_svg_bytes_unchanged(self):
		v12 = json.loads(V12.read_text(encoding='utf-8'))
		self.assertEqual(hashlib.md5(render_mindmap_svg(v12, MATERIAL)).hexdigest(), V12_MD5)


if __name__ == '__main__':
	unittest.main()
```

If `sample_key_points()` has no point with a code example and no point with misconceptions, the first two tests would pass vacuously — check the fixture and add assertions `self.assertTrue(any(...))` that at least one point has each, before relying on them.

- [ ] **Step 3: Run and confirm failure**

Run: `.venv/bin/python -m unittest tests.test_concept_tree -v`
Expected: FAIL (`contract_version` is `'1.2'`).

- [ ] **Step 4: Builder** — replace the body of `studio/concept_tree.py`:

```python
"""重點清單 → 概念樹；重點底下長出定義，定義底下再分例子與常見錯誤，內容直接是節點。"""
from studio.handout import page_numbers
from studio.key_points import canonical_key_points
from studio.mindmap import canonical_mindmap


def _pitfall(mistake):
	return f"錯：{mistake['wrong']}\n為什麼：{mistake['why']}\n正確：{mistake['correct']}"


def build_concept_tree(key_points, material):
	value = canonical_key_points(key_points, material)
	pages = page_numbers(value)
	nodes = [{'id': 'root', 'label': value['title'], 'kind': 'concept', 'explanation': '',
		'source_quote': '', 'handout_page': None}]
	edges = []
	def add(node_id, parent, label, kind, quote, page=None):
		nodes.append({'id': node_id, 'label': label, 'kind': kind, 'explanation': '',
			'source_quote': quote, 'handout_page': page})
		edges.append({'from': parent, 'to': node_id, 'label': '', 'source_quote': ''})
	for point in value['points']:
		pid, quote = point['id'], point['sources'][0]
		add(pid, point['parent_id'] or 'root', point['title'], 'concept', quote, pages[pid])
		# 定義先加，子重點的邊排在後面，展開時定義永遠是第一個分支。
		meaning = f'{pid}-meaning'
		add(meaning, pid, point['explanation'], 'meaning', quote)
		example = point['example']
		if example is not None and example['kind'] != 'none':
			add(f'{pid}-example-group', meaning, '例子', 'group', quote)
			add(f'{pid}-example', f'{pid}-example-group', example['content'].strip('\n'), 'example', quote)
		if point['misconceptions']:
			add(f'{pid}-pitfall-group', meaning, '常見錯誤', 'group', quote)
			for number, mistake in enumerate(point['misconceptions'], start=1):
				add(f'{pid}-pitfall-{number}', f'{pid}-pitfall-group', _pitfall(mistake), 'pitfall', quote)
	return canonical_mindmap({'contract_version': '1.3', 'title': value['title'], 'layout': 'progressive',
		'root_id': 'root', 'nodes': nodes, 'edges': edges})
```

`first_sentences` is removed; grep for other importers (`grep -rn first_sentences --include=*.py .`) and remove/adjust them.

- [ ] **Step 5: Contract** — in `canonical_mindmap`:
  - Accept `'1.3'` in the version check; `explorable` includes `'1.3'`; `handout` (needs `handout_page`, unlabeled edges) is true for `'1.2'` and `'1.3'`.
  - Allowed kinds: 1.3 → `('concept','meaning','group','example','pitfall')`; 1.1/1.2 unchanged (no `group`).
  - 1.3 label maximum by kind: root 120, `concept` 24, `group` 8, `meaning` 150, `example` 400, `pitfall` 260.
  - 1.3 `explanation` must be exactly `''` on every node; `source_quote` required (≤1000) on every non-root node, `''` on root.
  - 1.3 `handout_page`: non-root `concept` → `int >= 2`; every other node → `None`.
  - Node count limit stays 80.
  - Keep every 1.0/1.1/1.2 branch byte-for-byte equivalent in behaviour.

- [ ] **Step 6: SVG** — dispatch `'1.3'` to `_render_explorable_svg`, adding kind-specific rendering **only when `contract_version == '1.3'`** (1.1/1.2 output must keep the pinned md5):
  - `example`: measure with Noto Sans Mono CJK TC (`NotoSansCJK-Regular.ttc`, `index=8`, size 18), split on `\n` first then wrap at 260px, line height 24, `font-family="Noto Sans Mono CJK TC,monospace"`, `font-size="18"`, `xml:space="preserve"` on each `<text>` so leading spaces of code survive.
  - `group`: rect height 48 (fixed), `rx="24"`, fill `#fffaf2`.
  - `concept` fill `#f5e2cf`; `meaning`/`example`/`pitfall` fill `#fffdf7` (existing colours only).
  - Pitfall labels contain `\n`; the existing measure already breaks on `\n`.
  - Layout (vertical stacking via measured spans) is the existing algorithm; nodes must not overlap and must stay inside the canvas — the test enforces it.

- [ ] **Step 7: Run tests**

Run: `.venv/bin/python -m unittest tests.test_concept_tree tests.test_studio_mindmap tests.test_studio_mindmap_facade -v`
Expected: PASS. Then the full suite: `.venv/bin/python -m unittest discover -s tests -t .` → OK. Fix any other test that asserted the 1.2 builder output (update it to 1.3 semantics; never weaken a 1.0/1.1/1.2 assertion).

- [ ] **Step 8: Commit**

```bash
git add studio/concept_tree.py studio/mindmap.py tests/test_concept_tree.py tests/fixtures/concept_tree_v12.json
git commit -m "feat(mindmap): grow meaning, examples and pitfalls as concept tree nodes"
```

---

### Task 2: Workbench viewer for 1.3

**Files:**
- Modify: `workbench/web/js/viewers/concept-tree.mjs` (only if needed; panel is already 1.2-only at line ~64)
- Modify: `workbench/web/styles.css` (append after the `.concept-card:hover` rule, ~line 3120)
- Modify: `workbench/web/tests/concept-tree.test.mjs`

**Interfaces:**
- Consumes: SVG attributes from Task 1 (`data-contract-version="1.3"`, `data-node-kind` values `concept|meaning|group|example|pitfall`).
- Viewer already sets `data-node-kind` on each `.concept-card` and uses `white-space: pre-wrap` on `.concept-toggle`.

- [ ] **Step 1: Failing tests** — add to `concept-tree.test.mjs`, reusing the file's existing helpers (`conceptDOM`, `click`, and the fixture builders; write a `v13Fixture(doc)` alongside `v12Fixture` that builds an SVG with: root → `a` (concept, page 2) → `a-meaning` (meaning) → `a-example-group` (group "例子") → `a-example` (example, label `"for (i = 0;\n     i < 5; i++)"`) and `a-meaning` → `a-pitfall-group` (group "常見錯誤") → `a-pitfall-1` (pitfall)):

```js
test('1.3 版沒有詳情面板，點一下只長直屬下一層', async () => {
 await conceptDOM(async doc => {
  const host=doc.createElement('div');const viewer=mountConceptTree(host,v13Fixture(doc),{unit:'u',files:{svg:'map.svg'}});
  const ids=()=>host.querySelectorAll('.concept-card').map(card=>card.getAttribute('data-concept-id')).sort();
  try {
   assert.equal(host.querySelector('.concept-detail'),null);
   assert.deepEqual(ids(),['a','root']);
   click(host.querySelector('[data-concept-id="a"]'));
   assert.deepEqual(ids(),['a','a-meaning','root']);
   click(host.querySelector('[data-concept-id="a-meaning"]'));
   assert.deepEqual(ids(),['a','a-example-group','a-meaning','a-pitfall-group','root']);
   click(host.querySelector('[data-concept-id="a-example-group"]'));
   assert.deepEqual(ids(),['a','a-example','a-example-group','a-meaning','a-pitfall-group','root']);
   assert.equal(host.querySelector('.concept-detail'),null);
  } finally {viewer.dispose();}
 });
});

test('1.3 版卡片帶節點類型，程式例子保留換行與縮排', async () => {
 await conceptDOM(async doc => {
  const host=doc.createElement('div');const viewer=mountConceptTree(host,v13Fixture(doc),{unit:'u',files:{svg:'map.svg'}});
  try {
   for (const id of ['a','a-meaning','a-example-group']) click(host.querySelector(`[data-concept-id="${id}"]`));
   assert.equal(host.querySelector('[data-concept-id="a-example-group"]').getAttribute('data-node-kind'),'group');
   const example=host.querySelector('[data-concept-id="a-example"]');
   assert.equal(example.getAttribute('data-node-kind'),'example');
   assert.equal(example.querySelector('.concept-toggle').textContent,'for (i = 0;\n     i < 5; i++)');
  } finally {viewer.dispose();}
 });
});
```

Adapt helper names to what the file actually defines (e.g. if `querySelectorAll` returns a NodeList in the fake DOM, keep the file's existing pattern).

- [ ] **Step 2: Run, confirm failure**

Run: `node --test workbench/web/tests`
Expected: the new tests fail (fixture/assertions), existing tests pass.

- [ ] **Step 3: Implement** — if the viewer already satisfies the tests, no JS change. If `textContent` of `<title>` loses newlines or leading spaces, fix the reading path only for 1.3. Then append CSS (existing colours only):

```css
/* 概念樹 1.3：依節點類型區分，內容直接長在樹上。 */
.concept-card[data-node-kind="concept"] { background: #f5e2cf; border-color: #c69373; }
.concept-card[data-node-kind="meaning"] .concept-toggle, .concept-card[data-node-kind="pitfall"] .concept-toggle { font-size: 17px; font-weight: 400; line-height: 1.65; }
.concept-card[data-node-kind="group"] { width: auto !important; min-width: 120px; padding: 8px 18px; border-radius: 999px; }
.concept-card[data-node-kind="group"] .concept-toggle { font-size: 16px; font-weight: 700; text-align: center; }
.concept-card[data-node-kind="example"] .concept-toggle { font-family: "Noto Sans Mono CJK TC", ui-monospace, monospace; font-size: 15px; font-weight: 400; line-height: 1.55; white-space: pre-wrap; tab-size: 4; }
```

If `width: auto` on group cards breaks connector/position math (positions use `card.offsetWidth`), drop the width override and keep only padding/radius.

- [ ] **Step 4: Run tests**

Run: `node --test workbench/web/tests` → all pass.

- [ ] **Step 5: Commit**

```bash
git add workbench/web/js/viewers/concept-tree.mjs workbench/web/styles.css workbench/web/tests/concept-tree.test.mjs
git commit -m "feat(web): expand concept tree one level per click for contract 1.3"
```

---

### Task 3: Regenerate real units and hand over (controller, not the implementer)

- [ ] Rebuild mindmaps from cached key points (free; must not call Gemini — verify `usage.jsonl` line count unchanged):

```bash
for uid in c4ddf43c2259 68abcb139acd 4f2ef7bf2785; do
	wc -l < video_engine/out/units/$uid/usage.jsonl
	.venv/bin/python workbench/run_mindmap.py video_engine/out/units/$uid --quality keypoints --budget-usd 0.01
	wc -l < video_engine/out/units/$uid/usage.jsonl
	grep -o 'data-contract-version="[^"]*"' video_engine/out/units/$uid/mindmap/mindmap.svg
done
```

- [ ] Full Python suite + `node --test workbench/web/tests` green on a clean tree.
- [ ] Restart workbench on 8876 and hand to the user: `for 迴圈` concept tree.
- [ ] Update spec status line, HANDOFF_NOTES, memory; commit.
