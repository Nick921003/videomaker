import { mountConceptTree } from './concept-tree.mjs';
import { el } from '../ui.mjs';
import { fileURL, viewerTools, panViewer, readFile } from './common.mjs';

export function svgBounds(svg) {
	const parts = (svg.getAttribute('viewBox') ?? '').trim().split(/[\s,]+/).map(Number);
	if (parts.length === 4 && parts.every(Number.isFinite) && parts[2] > 0 && parts[3] > 0) {
		return { x: parts[0], y: parts[1], w: parts[2], h: parts[3] };
	}
	return { x: 0, y: 0, w: parseFloat(svg.getAttribute('width')) || 960, h: parseFloat(svg.getAttribute('height')) || 540 };
}

// 從 SVG 節點中提取安全文字 metadata；相容新 1.1 的 title/desc 與舊版無 metadata 的 SVG
export function extractNodeMetadata(node) {
	const titleEl = node.querySelector?.('title[data-node-label]');
	const label = titleEl?.getAttribute?.('data-node-label') || titleEl?.textContent?.trim()
		|| node.querySelector?.('title')?.textContent?.trim()
		|| [...node.querySelectorAll?.('text') ?? []].map(t => t.textContent.trim()).filter(Boolean).pop()
		|| node.getAttribute?.('data-node-id') || '';

	const expEl = node.querySelector?.('desc[data-node-explanation]');
	const explanation = expEl?.getAttribute?.('data-node-explanation') || expEl?.textContent?.trim() || '';

	const quoteEl = node.querySelector?.('desc[data-node-quote]');
	const quote = quoteEl?.getAttribute?.('data-node-quote') || quoteEl?.textContent?.trim() || '';

	return { label, explanation, quote };
}

// 渲染下方概念詳情面板：初始顯示總覽提示，選取節點後顯示解釋與折疊原文
function renderInspector(panel, meta, isSelected) {
	if (!isSelected || !meta) {
		panel.replaceChildren(el('p', 'svg-inspector-hint', '點選或以鍵盤選取心智圖節點，檢視概念解釋與教材來源。'));
		return;
	}
	const card = el('div', 'svg-inspector-card');
	card.append(el('h3', 'svg-inspector-title', meta.label));
	if (meta.explanation) {
		card.append(el('p', 'svg-inspector-explanation', meta.explanation));
	} else {
		card.append(el('p', 'svg-inspector-empty-note', '（此概念未提供延伸說明）'));
	}
	if (meta.quote) {
		const source = el('details', 'svg-inspector-quote');
		source.append(el('summary', '', '教材原文引用'), el('blockquote', '', meta.quote));
		card.append(source);
	}
	panel.replaceChildren(card);
}

export async function mount(host, { unit, item, files, signal }) {
	const root = el('section', 'viewer viewer-svg');
	const toolbar = viewerTools(root);
	if (files?.svg) {
		const download = el('a', 'button svg-download', '下載 SVG');
		download.href = fileURL(unit, files.svg, 'svg');
		download.download = 'mindmap.svg';
		toolbar.append(download);
	}
	const viewport = el('div', 'viewer-viewport svg-viewport');
	const panel = el('aside', 'svg-inspector scroll-box');
	panel.setAttribute('aria-live', 'polite');
	panel.setAttribute('aria-label', '概念詳情');
	renderInspector(panel, null, false);
	root.append(viewport, panel);
	host.replaceChildren(root);
	const source = await readFile(unit, files, 'svg', signal);
	signal?.throwIfAborted();
	const parsed = new DOMParser().parseFromString(source, 'image/svg+xml');
	const original = parsed.documentElement;
	if (original.localName !== 'svg' || parsed.querySelector('parsererror')) throw new Error('心智圖的格式讀不到。');
	// 只把靜態圖形帶進文件，不執行 SVG 中的程式或外部內容。
	for (const node of original.querySelectorAll('script, foreignObject, iframe, object, embed, style, animate, animateTransform, set')) node.remove();
	for (const node of [original, ...original.querySelectorAll('*')]) {
		for (const attribute of [...node.attributes]) {
			if (/^on/i.test(attribute.name) || /href$/i.test(attribute.name) && !attribute.value.startsWith('#')
				|| /url\(\s*['"]?(?!#)/i.test(attribute.value)) node.removeAttribute(attribute.name);
		}
	}
	if (original.getAttribute('data-root-id')) return mountConceptTree(host, original, { unit, files });
	const bounds = svgBounds(original);
	const svg = document.importNode(original, true);
	svg.removeAttribute('viewBox');
	svg.removeAttribute('aria-labelledby');
	svg.setAttribute('class', 'diagram-svg');
	svg.setAttribute('width', '100%');
	svg.setAttribute('height', '100%');
	svg.setAttribute('tabindex', '0');
	svg.setAttribute('role', 'img');
	svg.setAttribute('aria-label', `${typeof item === 'string' ? '心智圖' : item.label}，滾輪縮放、拖曳移動`);
	svg.setAttribute('data-bounds', JSON.stringify(bounds));
	const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
	group.setAttribute('data-panzoom-content', '');
	group.append(...svg.childNodes);
	svg.append(group);
	viewport.append(svg);

	const abort = new AbortController();
	const { signal: eventSignal } = abort;

	let selectedNode = null;
	function selectNode(target) {
		if (selectedNode === target) return;
		if (selectedNode) {
			selectedNode.removeAttribute('data-selected');
			selectedNode.setAttribute('aria-pressed', 'false');
		}
		selectedNode = target;
		if (target) {
			target.setAttribute('data-selected', 'true');
			target.setAttribute('aria-pressed', 'true');
			const meta = extractNodeMetadata(target);
			renderInspector(panel, meta, true);
		} else {
			renderInspector(panel, null, false);
		}
	}

	// 為所有概念節點設定無障礙焦點與鍵盤／點選互動能力
	const nodes = group.querySelectorAll('g[data-node-id]');
	for (const node of nodes) {
		node.setAttribute('tabindex', '0');
		node.setAttribute('role', 'button');
		node.setAttribute('aria-pressed', 'false');
		const meta = extractNodeMetadata(node);
		if (meta.label) node.setAttribute('aria-label', `概念：${meta.label}`);

		node.addEventListener('click', () => selectNode(node), { signal: eventSignal });
		node.addEventListener('keydown', event => {
			if (event.key === 'Enter' || event.key === ' ') {
				event.preventDefault();
				selectNode(node);
			}
		}, { signal: eventSignal });
	}

	const handleClick = event => {
		const target = event.target?.closest?.('g[data-node-id]');
		if (target) selectNode(target);
	};

	const handleKeyDown = event => {
		if (event.key !== 'Enter' && event.key !== ' ') return;
		const target = event.target?.closest?.('g[data-node-id]');
		if (target) {
			event.preventDefault();
			selectNode(target);
		}
	};

	svg.addEventListener('click', handleClick, { signal: eventSignal });
	svg.addEventListener('keydown', handleKeyDown, { signal: eventSignal });

	const controls = panViewer(svg, root, toolbar);
	return {
		focus() { svg.focus(); },
		dispose() {
			abort.abort();
			controls.destroy();
		}
	};
}
