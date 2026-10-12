import { el } from '../ui.mjs';
import { fileURL } from './common.mjs';

export function visibleTree(root, children, expanded) {
	const rows = []; let next = 0;
	function walk(id, depth) {
		const kids = expanded.has(id) ? children.get(id) ?? [] : [];
		const row = { id, depth, y: 0 }; rows.push(row);
		const positions = kids.map(child => walk(child, depth + 1));
		row.y = positions.length ? (positions[0] + positions.at(-1)) / 2 : next++;
		return row.y;
	}
	walk(root, 0); return rows;
}

export function mountConceptTree(host, svg, { unit, files }) {
	const rootId = svg.getAttribute('data-root-id');
	const version = svg.getAttribute('data-contract-version') ?? '1.0';
	const nodes = new Map(), children = new Map(), parents = new Map();
	for (const node of svg.querySelectorAll('g[data-node-id]')) {
		const id = node.getAttribute('data-node-id');
		nodes.set(id, {
			label: node.querySelector('title[data-node-label]')?.textContent ?? id,
			kind: node.getAttribute('data-node-kind') ?? 'concept',
			explanation: node.querySelector('desc[data-node-explanation]')?.textContent ?? '',
			quote: node.querySelector('desc[data-node-quote]')?.textContent ?? '',
		});
		children.set(id, []);
	}
	for (const edge of svg.querySelectorAll('path[data-from]')) {
		const from = edge.getAttribute('data-from'), to = edge.getAttribute('data-to');
		if (nodes.has(from) && nodes.has(to)) { children.get(from).push(to);parents.set(to, from); }
	}
	if (!nodes.has(rootId)) throw new Error('心智圖缺少起點');
	// 新版已包含有來源的解說節點；只有舊版需要從 explanation 補出意思。
	if (version === '1.0') for (const [id, node] of [...nodes]) if (node.explanation && id !== rootId) {
		const detail = `${id}:meaning`;
		nodes.set(detail, { label: node.explanation, kind: 'meaning', quote: node.quote });
		children.set(detail, []);children.get(id).unshift(detail);parents.set(detail, id);
	}
	const root = el('section', 'viewer concept-reader');
	root.setAttribute('data-contract-version', version);
	const tools = el('div', 'concept-tools');
	function control(text, label) {
		const node = el('button', 'button', text);node.type = 'button';
		if (label) node.setAttribute('aria-label', label);return node;
	}
	const reset = control('回到起點');
	const download = el('a', 'button', '下載 SVG');
	download.href = fileURL(unit, files.svg, 'svg');download.download = 'mindmap.svg';
	const smaller = control('−', '縮小'), larger = control('＋', '放大');
	const back = control('返回上一層'), fullscreen = control('全螢幕');
	const layout = el('select', 'concept-layout');layout.setAttribute('aria-label', '心智圖布局');
	for (const [value, text] of [['radial', '發散'], ['progressive', '漸進']]) {
		const option = el('option', '', text);option.value = value;layout.append(option);
	}
	layout.value = svg.getAttribute('data-layout') === 'progressive' ? 'progressive' : 'radial';
	tools.append(back, reset, layout, smaller, larger, fullscreen, download);
	const viewport = el('div', 'concept-viewport');viewport.tabIndex = 0;
	viewport.setAttribute('aria-label', '心智圖，點選或 Enter 展開概念，Backspace 返回，方向鍵移動畫布');
	const canvas = el('div', 'concept-canvas');viewport.append(canvas);root.append(tools, viewport);host.replaceChildren(root);
	let current = rootId, trail = [], positions = new Map(), lastWidth = 0, restoringFocus = false;
	const expanded = new Set([rootId]);
	let camera = { x: 0, y: 0, scale: 1 };
	const events = new AbortController();
	const animate = () => { canvas.style.transition = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'none' : 'transform 220ms ease'; };
	function apply() { canvas.style.transform = `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})`; }
	function cardFor(id) { return [...canvas.querySelectorAll('.concept-card')].find(card => card.getAttribute('data-concept-id') === id); }
	function center(id) {
		const card = cardFor(id);if (!card) return;
		const width = card.offsetWidth, height = card.offsetHeight;
		camera.scale = Math.min(1.1, Math.max(.95, (viewport.clientWidth - 32) / width));
		camera.x = viewport.clientWidth / 2 - (parseFloat(card.style.left) + width / 2) * camera.scale;
		camera.y = height * camera.scale > viewport.clientHeight - 48 ? 24 - parseFloat(card.style.top) * camera.scale
			: viewport.clientHeight / 2 - (parseFloat(card.style.top) + height / 2) * camera.scale;
		animate();apply();
	}
	function activate(id) {
		current = id;
		if (id === rootId || !children.get(id)?.length) { center(id);return; }
		if (expanded.has(id)) { collapse(id);render(id); }
		else { expanded.add(id);trail.push(id);render(id); }
	}
	function collapse(id) {
		const closed = new Set();
		function collect(nodeId) {
			closed.add(nodeId);
			for (const child of children.get(nodeId) ?? []) collect(child);
		}
		collect(id);
		for (const nodeId of closed) expanded.delete(nodeId);
		trail = trail.filter(nodeId => !closed.has(nodeId));
	}
	function goBack() {
		if (!trail.length) return;
		const id = trail.at(-1);collapse(id);current = id;render(id);
	}
	viewport.addEventListener('wheel', event => {
		event.preventDefault();canvas.style.transition = 'none';
		const box = viewport.getBoundingClientRect(), px = event.clientX - box.left, py = event.clientY - box.top;
		const scale = Math.max(.4, Math.min(2.5, camera.scale * Math.exp(-event.deltaY * .0015)));
		camera.x = px - (px - camera.x) * scale / camera.scale;
		camera.y = py - (py - camera.y) * scale / camera.scale;camera.scale = scale;apply();
	}, { passive: false, signal: events.signal });
	let drag = null, suppressClick = false;
	viewport.addEventListener('pointerdown', event => {
		if (event.button !== 0 || event.target.closest('a, summary, details')) return;
		suppressClick = false;
		drag = { x: event.clientX, y: event.clientY, cx: camera.x, cy: camera.y, moved: false };
	}, { signal: events.signal });
	viewport.addEventListener('pointermove', event => {
		if (!drag) return;
		const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
		if (!drag.moved && Math.hypot(dx, dy) < 6) return;
		if (!drag.moved) { viewport.setPointerCapture(event.pointerId);drag.moved = true; }
		suppressClick = true;canvas.style.transition = 'none';
		camera.x = drag.cx + dx;camera.y = drag.cy + dy;apply();
	}, { signal: events.signal });
	viewport.addEventListener('pointerup', () => { drag = null; }, { signal: events.signal });
	viewport.addEventListener('pointercancel', () => { drag = null;suppressClick = false; }, { signal: events.signal });
	viewport.addEventListener('click', event => {
		if (!suppressClick || event.detail === 0) return;
		suppressClick = false;event.preventDefault();event.stopPropagation();
	}, { capture: true, signal: events.signal });
	viewport.addEventListener('keydown', event => {
		if (event.ctrlKey || event.metaKey || event.altKey || event.target?.closest?.('select, input, textarea')) return;
		if (event.key === 'Backspace' || event.key === 'Escape') { event.preventDefault();goBack();return; }
		if (event.target === viewport && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault();activate(current);return; }
		const delta = { ArrowLeft: [80, 0], ArrowRight: [-80, 0], ArrowUp: [0, 80], ArrowDown: [0, -80] }[event.key];
		if (delta) { event.preventDefault();camera.x += delta[0];camera.y += delta[1];apply(); }
	}, { signal: events.signal });
	function render(focusId = current, clear = false) {
		const focused = document.activeElement?.closest?.('.concept-card')?.getAttribute('data-concept-id');
		canvas.replaceChildren();back.disabled = !trail.length;
		if (clear) positions.clear();
		const cardWidth = Math.min(270, Math.max(200, viewport.clientWidth - 40));
		const rows = visibleTree(rootId, children, expanded);
		const visible = new Set(rows.map(row => row.id));
		if (!visible.has(current)) current = rootId;
		if (!visible.has(focusId)) focusId = current;
		const signs = new Map([[rootId, 0]]);
		function direction(id, sign) { signs.set(id, sign);for (const kid of children.get(id) ?? []) direction(kid, sign); }
		(children.get(rootId) ?? []).forEach((id, index) => direction(id, layout.value === 'progressive' ? 1 : index % 2 ? 1 : -1));
		for (const row of rows) {
			const data = nodes.get(row.id), card = el('section', 'concept-card');
			card.setAttribute('data-concept-id', row.id);card.setAttribute('data-node-kind', data.kind);
			card.style.width = `${cardWidth}px`;
			const hasChildren = children.get(row.id)?.length > 0;
			const toggle = el('button', 'concept-toggle', data.label);toggle.type = 'button';
			toggle.addEventListener('focus', () => { if (!restoringFocus) { current = row.id;center(row.id); } });
			toggle.setAttribute('aria-label', hasChildren ? `${data.label}，${row.id === rootId ? '回到起點' : expanded.has(row.id) ? '收合' : '展開'}` : `${data.label}，聚焦`);
			if (hasChildren) toggle.setAttribute('aria-expanded', String(expanded.has(row.id)));
			card.addEventListener('click', () => activate(row.id));card.append(toggle);canvas.append(card);
			let position = positions.get(row.id);
			if (!position) {
				const x = row.depth * (cardWidth + 72) * (signs.get(row.id) ?? 1);
				let y = positions.get(parents.get(row.id))?.y ?? 0;
				const height = card.offsetHeight;
				// 只安置新節點；已展開的根與兄弟保留實測位置。
				const peers = [...positions.values()].filter(other => other.x === x).sort((a, b) => a.y - b.y);
				for (const peer of peers) if (y + height + 40 > peer.y && y < peer.y + peer.height + 40) y = peer.y + peer.height + 40;
				position = { x, y, height };positions.set(row.id, position);
			}
			card.style.left = `${position.x}px`;card.style.top = `${position.y}px`;
		}
		const cards = [...canvas.querySelectorAll('.concept-card')];
		const left = Math.min(...cards.map(card => parseFloat(card.style.left))) - 24;
		const top = Math.min(...cards.map(card => parseFloat(card.style.top))) - 24;
		const right = Math.max(...cards.map(card => parseFloat(card.style.left) + card.offsetWidth)) + 24;
		const bottom = Math.max(...cards.map(card => parseFloat(card.style.top) + card.offsetHeight)) + 24;
		canvas.style.width = `${right - left}px`;canvas.style.height = `${bottom - top}px`;
		const ns = 'http://www.w3.org/2000/svg', lines = document.createElementNS(ns, 'svg');
		lines.setAttribute('class', 'concept-connectors');lines.setAttribute('width', String(right - left));lines.setAttribute('height', String(bottom - top));
		lines.setAttribute('viewBox', `${left} ${top} ${right - left} ${bottom - top}`);lines.style.left = `${left}px`;lines.style.top = `${top}px`;
		const cardById = new Map(cards.map(card => [card.getAttribute('data-concept-id'), card]));
		for (const [parentId, kids] of children) if (expanded.has(parentId)) for (const childId of kids) {
			const parent = cardById.get(parentId), child = cardById.get(childId);if (!parent || !child) continue;
			const line = document.createElementNS(ns, 'path');line.setAttribute('data-parent', parentId);line.setAttribute('data-child', childId);
			const rightward = parseFloat(child.style.left) > parseFloat(parent.style.left);
			const x1 = parseFloat(parent.style.left) + (rightward ? parent.offsetWidth : 0), y1 = parseFloat(parent.style.top) + parent.offsetHeight / 2;
			const x2 = parseFloat(child.style.left) + (rightward ? 0 : child.offsetWidth), y2 = parseFloat(child.style.top) + child.offsetHeight / 2;
			line.setAttribute('d', `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`);lines.append(line);
		}
		canvas.prepend(lines);center(focusId);
		if (focused) {
			restoringFocus = true;
			(cardFor(focused) ?? cardFor(current))?.querySelector('button')?.focus({ preventScroll: true });
			restoringFocus = false;
		}
	}
	back.addEventListener('click', goBack);
	reset.addEventListener('click', () => { current = rootId;trail = [];expanded.clear();expanded.add(rootId);render(rootId, true); });
	layout.addEventListener('change', () => render(current, true));
	function syncFullscreen() {
		const active = root.classList.contains('concept-fullscreen') || document.fullscreenElement === root;
		fullscreen.textContent = active ? '退出全螢幕' : '全螢幕';requestAnimationFrame(() => center(current));
	}
	fullscreen.addEventListener('click', async () => {
		if (document.fullscreenElement === root) { await document.exitFullscreen();root.classList.remove('concept-fullscreen'); }
		else if (root.classList.contains('concept-fullscreen')) root.classList.remove('concept-fullscreen');
		else { root.classList.add('concept-fullscreen');try { await root.requestFullscreen?.(); } catch {} }
		syncFullscreen();
	});
	document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) root.classList.remove('concept-fullscreen');syncFullscreen(); }, { signal: events.signal });
	document.addEventListener('keydown', event => { if (event.key === 'Escape' && root.classList.contains('concept-fullscreen')) { root.classList.remove('concept-fullscreen');syncFullscreen(); } }, { signal: events.signal });
	const resize = new ResizeObserver(() => {
		if (viewport.clientWidth !== lastWidth) { lastWidth = viewport.clientWidth;render(current, true); }
		else center(current);
	});resize.observe(viewport);
	function zoomBy(factor) {
		const scale = Math.max(.4, Math.min(2.5, camera.scale * factor)), px = viewport.clientWidth / 2, py = viewport.clientHeight / 2;
		camera.x = px - (px - camera.x) * scale / camera.scale;camera.y = py - (py - camera.y) * scale / camera.scale;camera.scale = scale;apply();
	}
	smaller.addEventListener('click', () => zoomBy(.85));larger.addEventListener('click', () => zoomBy(1.15));
	lastWidth = viewport.clientWidth;render();
	return { focus() { viewport.focus(); }, dispose() { events.abort();resize.disconnect();root.remove(); } };
}
