import { displayName } from './ui.mjs';

const W = 240;
const H = 112;
const DX = 296;
const DY = 176;
const drawings = new WeakMap();
let sequence = 0;

function node(id, label, sub, x, y, kind, data = {}) {
	return { ...data, id, label, sub, x, y, w: W, h: H, kind };
}

// 總圖由左到右：教材 → 整理 → 分析 → 各形式（直排一欄）→ 素材庫；圖可以比畫面大，靠縮放拖曳看。
const COL = W + 96;
const FAN = 200;
const PITCH = H + 36;
const GROUP_GAP = 44;

export function layoutMap(publicFormats = {}, { expanded = null } = {}) {
	const formats = Array.isArray(publicFormats) ? publicFormats : publicFormats.formats ?? [];
	const stages = publicFormats.stages ?? [];
	const ordered = [...formats.filter(format => format.status !== 'planned'), ...formats.filter(format => format.status === 'planned')];
	const formatX = 2 * COL + W + FAN;
	let y = 0;
	const rows = ordered.map((format, i) => {
		if (i && format.status === 'planned' && ordered[i - 1].status !== 'planned') y += GROUP_GAP;
		const row = { format, y };
		y += PITCH;
		return row;
	});
	const height = rows.length ? y - PITCH + H : H;
	const middle = (height - H) / 2;
	const nodes = [
		node('material', '教材', '從一份教材開始', 0, middle, 'source', { detail: '貼上文字，或匯入 md、txt、PDF、PPTX 教材。' }),
		node('ingest', '教材整理', '文字與閱讀順序', COL, middle, 'stage', stages.find(stage => stage.id === 'ingest')),
		node('analysis', '教材分析', '學生問題與概念', 2 * COL, middle, 'stage', stages.find(stage => stage.id === 'analysis')),
	];
	const edges = [{ from: 'material', to: 'ingest' }, { from: 'ingest', to: 'analysis' }];
	const groups = {};
	const tails = [];
	let right = formatX + W;
	for (const { format, y: rowY } of rows) {
		const planned = format.status === 'planned';
		const open = format.id === expanded && !planned && format.steps?.length;
		const entry = node(format.id, displayName(format), `${format.scope === 'point' ? '逐點' : '整份'} · ${planned ? '規劃中' : open ? '已展開' : '點開看步驟'}`,
			formatX, rowY, planned ? 'planned' : 'format', format);
		nodes.push(entry);
		edges.push({ from: 'analysis', to: entry.id, planned });
		let last = entry;
		if (open) {
			for (const [i, step] of format.steps.entries()) {
				const stepNode = node(`${format.id}:${step.id}`, step.name,
					`${String(i + 1).padStart(2, '0')} · ${step.paid ? '模型處理' : '本機處理'}`,
					formatX + (i + 1) * COL, rowY, 'step', { ...step, stepId: step.id, format: format.id });
				nodes.push(stepNode);
				edges.push({ from: last.id, to: stepNode.id });
				last = stepNode;
			}
		}
		right = Math.max(right, last.x + last.w);
		groups[entry.id] = { x: entry.x, y: entry.y, w: last.x + last.w - entry.x, h: H };
		tails.push({ id: last.id, planned });
	}
	const library = node('library', '素材庫', '完成的素材，共同收藏', right + FAN, middle, 'output',
		{ detail: '收錄完成的影片、心智圖、簡報與成品清單，讓學生用問題找到合適的教材。' });
	for (const tail of tails) edges.push({ from: tail.id, to: 'library', planned: tail.planned });
	if (!formats.length) edges.push({ from: 'analysis', to: 'library' });
	return { nodes: [...nodes, library], edges, groups };
}

export function layoutSteps(steps = []) {
	return steps.map((step, i) => node(step.id, step.name, `${String(i + 1).padStart(2, '0')} · ${step.paid ? '模型處理' : '本機處理'}`,
		(i % 4) * DX, Math.floor(i / 4) * DY, 'step', step));
}

function boundsOf(nodes) {
	if (!nodes.length) return { x: 0, y: 0, w: 1, h: 1 };
	const x = Math.min(...nodes.map(node => node.x));
	const y = Math.min(...nodes.map(node => node.y));
	return { x, y, w: Math.max(...nodes.map(node => node.x + node.w)) - x, h: Math.max(...nodes.map(node => node.y + node.h)) - y };
}

function svgElement(tag, attributes = {}, text = '') {
	const element = document.createElementNS('http://www.w3.org/2000/svg', tag);
	for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
	if (text) element.textContent = text;
	return element;
}

function labelLines(text, width) {
	const lines = [''];
	let used = 0;
	for (const char of String(text)) {
		const size = /[\u0020-\u007e]/.test(char) ? 0.58 : 1;
		if (used + size > width) { lines.push(''); used = 0; }
		lines[lines.length - 1] += char;
		used += size;
	}
	return lines;
}

function edgePath(from, to) {
	const x1 = from.x + from.w, y1 = from.y + from.h / 2, x2 = to.x, y2 = to.y + to.h / 2;
	if (Math.abs(y1 - y2) < 0.5) return `M ${x1} ${y1} H ${x2}`;
	// 平滑弧線：從右側中點出、從左側中點進，不繞路。
	const bend = Math.max(48, (x2 - x1) / 2);
	return `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
}

export function render(container, layout, { mode = 'explain', onNodeClick } = {}) {
	let drawing = drawings.get(container);
	if (!drawing) {
		const svg = svgElement('svg', { class: 'diagram-svg', width: '100%', height: '100%', tabindex: '0',
			role: 'group', 'aria-label': '流程圖，滾輪縮放、拖曳移動，按加減號縮放，按 0 符合視窗' });
		container.replaceChildren(svg);
		drawing = { svg, entries: new Map(), marker: `diagram-arrow-${++sequence}` };
		drawings.set(container, drawing);
	}
	const { svg, marker } = drawing;
	drawing.entries.clear();
	svg.setAttribute('data-mode', mode);
	svg.setAttribute('data-bounds', JSON.stringify(boundsOf(layout.nodes)));
	const defs = svgElement('defs');
	const arrow = svgElement('marker', { id: marker, viewBox: '0 0 10 10', refX: '9', refY: '5',
		markerWidth: '6', markerHeight: '6', orient: 'auto-start-reverse' });
	arrow.append(svgElement('path', { d: 'M 0 0 L 10 5 L 0 10 z', class: 'diagram-arrow' }));
	defs.append(arrow);
	const content = svgElement('g', { 'data-panzoom-content': '', class: 'diagram-content' });
	const transform = svg.querySelector?.('[data-panzoom-content]')?.getAttribute('transform');
	if (transform) content.setAttribute('transform', transform);
	const byId = new Map(layout.nodes.map(node => [node.id, node]));
	for (const edge of layout.edges ?? []) {
		const from = byId.get(edge.from);
		const to = byId.get(edge.to);
		if (!from || !to) continue;
		const planned = edge.planned || from.kind === 'planned' || to.kind === 'planned';
		content.append(svgElement('path', { d: edgePath(from, to), class: `diagram-edge${planned ? ' is-planned' : ''}`,
			'marker-end': `url(#${marker})`, 'aria-hidden': 'true' }));
	}
	for (const node of layout.nodes) {
		const group = svgElement('g', { class: `diagram-node kind-${node.kind}`, 'data-node-id': node.id, 'data-state': 'pending',
			transform: `translate(${node.x} ${node.y})`, tabindex: '0', role: 'button', 'aria-label': `${node.label}，${node.sub}` });
		group.append(svgElement('title', {}, node.label), svgElement('rect', { width: node.w, height: node.h, rx: '12' }));
		const lines = labelLines(node.label, (node.w - 40) / 24);
		const label = svgElement('text', { x: '20', y: lines.length > 1 ? '34' : '45', class: 'diagram-label' });
		for (const [i, line] of lines.slice(0, 2).entries()) label.append(svgElement('tspan', { x: '20', dy: i ? '29' : '0' },
			i === 1 && lines.length > 2 ? `${line.slice(0, -1)}…` : line));
		const sub = svgElement('text', { x: '20', y: String(node.h - 21), class: 'diagram-sub' }, node.sub);
		group.append(label, sub);
		group.addEventListener('click', event => {
			if (event.defaultPrevented) return;
			onNodeClick?.(node);
		});
		group.addEventListener('keydown', event => {
			if (event.key !== 'Enter' && event.key !== ' ') return;
			event.preventDefault();
			onNodeClick?.(node);
		});
		content.append(group);
		drawing.entries.set(node.id, { group, sub, node });
	}
	svg.replaceChildren(defs, content);
	return svg;
}

const stateNames = { pending: '等待中', running: '進行中', done: '已完成', failed: '失敗', skipped: '略過' };

export function setLive(container, stepStates = []) {
	const drawing = drawings.get(container);
	if (!drawing) return;
	const states = Array.isArray(stepStates) ? Object.fromEntries(stepStates.map(step => [step.id, step.state])) : stepStates;
	for (const [id, { group, sub, node }] of drawing.entries) {
		const state = Object.hasOwn(stateNames, states[id]) ? states[id] : 'pending';
		group.setAttribute('data-state', state);
		group.setAttribute('aria-label', `${node.label}，${stateNames[state]}`);
		sub.textContent = stateNames[state];
	}
}
