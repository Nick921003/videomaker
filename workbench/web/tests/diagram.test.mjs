import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { layoutMap, layoutSteps, render, setLive } from '../js/diagram.mjs';

const registry = JSON.parse(await readFile(new URL('../mock/formats.json', import.meta.url), 'utf8'));
const overlaps = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;

test('總圖從教材經整理與分析，分流各形式，再收進素材庫', () => {
	const snapshot = structuredClone(registry);
	const map = layoutMap(registry);
	const ids = new Set(map.nodes.map(node => node.id));
	assert.equal(ids.size, registry.formats.length + 4);
	for (const edge of map.edges) {
		assert.ok(ids.has(edge.from), edge.from);
		assert.ok(ids.has(edge.to), edge.to);
	}
	for (const [from, to] of [['material', 'ingest'], ['ingest', 'analysis'],
		...registry.formats.flatMap(format => [['analysis', format.id], [format.id, 'library']])]) {
		assert.ok(map.edges.some(edge => edge.from === from && edge.to === to), `${from} → ${to}`);
	}
	for (const format of registry.formats) {
		const node = map.nodes.find(node => node.id === format.id);
		assert.equal(node.kind, format.status === 'planned' ? 'planned' : 'format');
		const bounds = map.groups[format.id];
		assert.ok(bounds.x <= node.x && bounds.x + bounds.w >= node.x + node.w);
		assert.ok(bounds.y <= node.y && bounds.y + bounds.h >= node.y + node.h);
	}
	assert.deepEqual(registry, snapshot);
	assert.deepEqual(map, layoutMap(registry));
});

test('mock 總圖節點不重疊，節點足夠大且空登記表仍保留前置流程', () => {
	const { nodes } = layoutMap(registry);
	for (const [i, node] of nodes.entries()) {
		assert.ok(node.w >= 200 && node.h >= 88);
		for (const other of nodes.slice(i + 1)) assert.equal(overlaps(node, other), false, `${node.id} / ${other.id}`);
	}
	assert.deepEqual(layoutMap({ formats: [], stages: [] }).edges.map(edge => [edge.from, edge.to]),
		[['material', 'ingest'], ['ingest', 'analysis'], ['analysis', 'library']]);
});

test('步驟保留順序與模型資料，每四個換一列且不重疊', () => {
	const steps = registry.formats[0].steps;
	const nodes = layoutSteps(steps);
	assert.deepEqual(nodes.map(node => node.id), steps.map(step => step.id));
	assert.equal(nodes[0].y, nodes[3].y);
	assert.ok(nodes[4].y > nodes[3].y);
	assert.equal(nodes[4].x, nodes[0].x);
	assert.equal(nodes[1].model, steps[1].model);
	assert.equal(nodes[1].detail, steps[1].detail);
	for (const [i, node] of nodes.entries()) {
		for (const other of nodes.slice(i + 1)) assert.equal(overlaps(node, other), false);
	}
	assert.deepEqual(layoutSteps([]), []);
});

class Element extends EventTarget {
	constructor(tag) { super(); this.tagName = tag; this.children = []; this.attributes = new Map(); }
	append(...nodes) { this.children.push(...nodes); }
	replaceChildren(...nodes) { this.children = nodes; }
	setAttribute(key, value) { this.attributes.set(key, String(value)); }
	getAttribute(key) { return this.attributes.get(key) ?? null; }
	set textContent(value) { this.copy = value; this.children = []; }
	get textContent() { return (this.copy ?? '') + this.children.map(node => node.textContent).join(''); }
}

test('SVG 可點選與鍵盤操作；live 狀態按 id 更新，保留不同狀態的文字', () => {
	const previous = globalThis.document;
	globalThis.document = { createElementNS: (ns, tag) => new Element(tag) };
	try {
		const container = new Element('div');
		const nodes = layoutSteps(registry.formats[0].steps);
		let selected;
		const svg = render(container, { nodes, edges: [], groups: {} }, { mode: 'live', onNodeClick: node => { selected = node; } });
		const all = node => [node, ...node.children.flatMap(all)];
		const buttons = all(svg).filter(node => node.getAttribute('data-node-id'));
		assert.equal(buttons.length, nodes.length);
		buttons[1].dispatchEvent(new Event('click'));
		assert.equal(selected.id, 'storyboard');
		buttons[2].dispatchEvent(Object.assign(new Event('keydown'), { key: 'Enter' }));
		assert.equal(selected.id, 'validate');
		const states = ['running', 'done', 'failed', 'skipped'];
		setLive(container, states.map((state, i) => ({ id: nodes[i].id, state })));
		for (const [i, state] of states.entries()) assert.equal(buttons[i].getAttribute('data-state'), state);
		assert.match(svg.textContent, /進行中/);
		assert.match(svg.textContent, /已完成/);
		assert.match(svg.textContent, /失敗/);
		assert.match(svg.textContent, /略過/);
		setLive(container, { selftest: 'done' });
		assert.equal(buttons[0].getAttribute('data-state'), 'done');
		assert.equal(buttons[1].getAttribute('data-state'), 'pending');
		assert.equal(render(container, { nodes: [], edges: [] }, {}), svg);
	} finally {
		if (previous === undefined) delete globalThis.document;
		else globalThis.document = previous;
	}
});
