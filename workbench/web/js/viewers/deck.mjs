import { el } from '../ui.mjs';
import { button, fileURL, readFile, viewerTools, panViewer } from './common.mjs';

function list(items, ordered = false, className = '') {
	const node = el(ordered ? 'ol' : 'ul', className);
	for (const item of items ?? []) node.append(el('li', '', String(item)));
	return node;
}

export function renderSlide(slide) {
	const role = ['hook', 'concept', 'example', 'pitfall', 'summary'].includes(slide.role) ? slide.role : 'concept';
	const card = el('article', `deck-slide deck-role-${role}`);
	card.append(el('h2', 'deck-slide-title', slide.title));
	const content = el('div', 'deck-slide-content');
	const block = slide.blocks?.[0];
	if (block?.type === 'code') content.append(el('pre', 'deck-code', block.lines.join('\n')));
	else if (block?.type === 'compare') {
		const columns = el('div', 'deck-compare');
		for (const side of [block.left, block.right]) {
			const column = el('section');
			column.append(el('h3', '', side.title), list(side.items));
			columns.append(column);
		}
		content.append(columns);
	} else if (block?.type === 'concept') {
		const diagram = el('div', 'deck-concept');
		const branches = el('ul', 'deck-concept-branches');
		for (const item of block.items) {
			const branch = el('li');
			branch.append(el('h3', '', item.title), el('p', '', item.text));
			branches.append(branch);
		}
		diagram.append(el('strong', 'deck-concept-center', block.center), branches);
		content.append(diagram);
	} else if (block) {
		content.append(list(block.items, block.type === 'steps', block.type === 'steps' ? 'deck-step-grid' : 'deck-point-grid'));
		if (block.type === 'steps') content.append(el('p', 'deck-flow-direction', '流程方向：依序 01 → 02 → …'));
	}
	card.append(content);
	if (slide.takeaway) card.append(el('p', 'deck-takeaway', slide.takeaway));
	return card;
}

export function fitSlide(card, version = '1.1') {
	const content = card.querySelector('.deck-slide-content');
	if (!card.clientHeight || !content?.clientHeight) return;
	// 區分版本：舊 1.0 保留最多 40 次縮字；新 1.1 禁止無限縮字，限制最多 2 次且下限 0.82
	const isV11 = version !== '1.0';
	const maxPasses = isV11 ? 2 : 40;
	const minScale = isV11 ? 0.82 : 0.01;
	let scale = 1;
	for (let pass = 0; pass < maxPasses; pass++) {
		if (card.scrollHeight <= card.clientHeight + 1 && card.scrollWidth <= card.clientWidth + 1
			&& content.scrollHeight <= content.clientHeight + 1 && content.scrollWidth <= content.clientWidth + 1) break;
		if (scale * 0.9 < minScale) break;
		scale *= 0.9;
		card.style.setProperty('--deck-scale', String(scale));
	}
	if (isV11) {
		// 檢查在足夠字級下是否仍超量：若超量則明示可讀捲動處理，不隱藏內容
		const isOverflowing = card.scrollHeight > card.clientHeight + 1 || content.scrollHeight > content.clientHeight + 1;
		if (isOverflowing) {
			card.setAttribute('data-overflow', 'true');
			if (!card.querySelector('.deck-overflow-notice')) {
				const notice = el('p', 'deck-overflow-notice', '內容較多 · 可向下捲動閱讀完整內容');
				notice.setAttribute('role', 'note');
				card.append(notice);
			}
		} else {
			card.removeAttribute('data-overflow');
			card.querySelector('.deck-overflow-notice')?.remove();
		}
	}
}

export async function mount(host, { unit, files, signal }) {
	const root = el('section', 'viewer viewer-deck');
	const toolbar = viewerTools(root);
	const previous = button('上一頁');
	const next = button('下一頁');
	const counter = el('span', 'deck-counter');
	counter.setAttribute('role', 'status');
	const jump = el('select', 'deck-jump');
	jump.setAttribute('aria-label', '選擇投影片');
	toolbar.append(jump, previous, counter, next);
	if (files.pptx) {
		const download = el('a', 'button deck-download', '下載 PPTX');
		download.href = fileURL(unit, files.pptx, 'pptx');
		download.download = 'deck.pptx';
		toolbar.append(download);
	}
	const viewport = el('div', 'viewer-viewport deck-viewport');
	viewport.tabIndex = 0;
	viewport.setAttribute('aria-label', '簡報，左右鍵翻頁、滾輪縮放、拖曳移動');
	viewport.setAttribute('data-bounds', JSON.stringify({ x: 0, y: 0, w: 960, h: 540 }));
	const canvas = el('div', 'deck-canvas');
	viewport.append(canvas);
	const notes = el('details', 'deck-notes scroll-box');
	notes.append(el('summary', '', '講者筆記與教材原文'));
	const notesText = el('p');
	const quote = el('blockquote');
	notes.append(notesText, quote);
	root.append(viewport, notes);
	host.replaceChildren(root);
	const deck = await readFile(unit, files, 'deck', signal);
	signal?.throwIfAborted();
	root.setAttribute('data-contract-version', deck.contract_version ?? '1.0');
	if (!deck.slides?.length) throw new Error('這份簡報還沒有投影片。');
	for (const [i, slide] of deck.slides.entries()) {
		const option = el('option', '', `${i + 1}. ${slide.title}`);
		option.value = String(i);
		jump.append(option);
	}
	jump.addEventListener('change', () => show(Number(jump.value)));
	let page = 0;
	function show(index) {
		page = Math.max(0, Math.min(deck.slides.length - 1, index));
		jump.value = String(page);
		const card = renderSlide(deck.slides[page]);
		canvas.replaceChildren(card);
		fitSlide(card, deck.contract_version ?? '1.0');
		counter.textContent = `${page + 1} / ${deck.slides.length}`;
		previous.disabled = page === 0;
		next.disabled = page === deck.slides.length - 1;
		notesText.textContent = deck.slides[page].speaker_notes ?? '';
		quote.textContent = deck.slides[page].source_quote ?? '';
	}
	previous.addEventListener('click', () => show(page - 1));
	next.addEventListener('click', () => show(page + 1));
	const doc = host.ownerDocument ?? document;
	const keydown = event => {
		if (event.ctrlKey || event.metaKey || event.altKey || event.target?.closest?.('input, textarea, select, [contenteditable="true"]')) return;
		if (!['ArrowLeft', 'ArrowRight', ' '].includes(event.key) || event.repeat) return;
		if (event.key === ' ' && event.target?.closest?.('button, a, summary')) return;
		event.preventDefault();
		show(page + (event.key === 'ArrowRight' || event.key === ' ' && !event.shiftKey ? 1 : -1));
	};
	doc.addEventListener('keydown', keydown);
	const controls = panViewer(viewport, root, toolbar, { onChange(view) {
		canvas.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
	} });
	show(0);
	return { focus() { viewport.focus(); }, dispose() { doc.removeEventListener('keydown', keydown); controls.destroy(); } };
}
