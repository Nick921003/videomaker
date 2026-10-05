import { el } from '../ui.mjs';

const STATUS = { none: '尚未生成', queued: '排隊中', running: '製作中', done: '已完成', failed: '失敗' };

export function pointStatus(unit, id) {
	return unit.items?.find(item => item.item === id && item.format === 'video')?.status ?? 'none';
}

export function highlightPoints(analysis) {
	return (analysis.highlight?.points ?? []).map(id => analysis.points.find(point => point.id === id)).filter(Boolean);
}

function chips(values, className = '') {
	const row = el('div', `make-chips ${className}`.trim());
	for (const value of values ?? []) row.append(el('span', 'make-chip', String(value)));
	return row;
}

function detail(title, content) {
	const section = el('section', 'point-section');
	section.append(el('h3', '', title), content);
	return section;
}

export function renderMakeAnalysis(unit, { next } = {}) {
	const analysis = unit.analysis;
	const content = el('section', 'make-analysis');
	const scope = el('div', 'make-scope scroll-box');
	scope.setAttribute('aria-label', '教材範圍');
	for (const [label, values, className] of [
		['涵蓋', analysis.scope.covers, ''], ['不涵蓋', analysis.scope.not_covers, 'scope-excluded'],
	]) {
		const row = el('div', 'scope-row');
		row.append(el('strong', '', label), chips(values, className));
		scope.append(row);
	}
	const columns = el('div', 'analysis-columns');
	const left = el('section', 'make-card point-panel');
	left.append(el('h2', 'make-card-heading', `學生會問的 ${analysis.points.length} 個問題`));
	const list = el('div', 'point-list scroll-box');
	list.setAttribute('aria-label', '分析點清單');
	const right = el('section', 'make-card point-detail scroll-box');
	right.setAttribute('aria-label', '選取問題的詳情');
	right.tabIndex = 0;
	const buttons = new Map();
	function select(point) {
		for (const [id, button] of buttons) button.setAttribute('aria-pressed', String(id === point.id));
		const top = el('div', 'section-heading');
		top.append(el('p', 'eyebrow', `第 ${analysis.points.indexOf(point) + 1} 點 · ${point.title}`), el('span', 'badge', `建議 ${point.sec} 秒`));
		const asks = el('ul', 'point-asks');
		for (const question of point.also_asks ?? []) asks.append(el('li', '', question));
		if (!asks.children.length) asks.append(el('li', '', '這一點沒有其他問法。'));
		const screens = chips((point.screens ?? []).map(screen => typeof screen === 'object' ? screen.title ?? screen.label ?? screen.id ?? JSON.stringify(screen) : screen));
		const show = el('div', 'point-show');
		show.append(el('p', '', point.show || '依教材內容安排示範。'), screens);
		const objectives = chips((point.objectives ?? []).map(objective => typeof objective === 'number' ? `目標 ${objective}` : objective));
		right.replaceChildren(top, el('h2', 'point-question', point.question), detail('也會這樣問', asks), detail('必演畫面', show), detail('學習目標', objectives));
		right.scrollTop = 0;
	}
	for (const [i, point] of analysis.points.entries()) {
		const button = el('button', 'point-choice');
		button.type = 'button';
		button.setAttribute('data-point-id', point.id);
		button.setAttribute('aria-pressed', 'false');
		const copy = el('span', 'point-choice-copy');
		copy.append(el('span', '', point.question), el('span', 'section-note', `${point.sec} 秒`));
		const status = pointStatus(unit, point.id);
		const dot = el('span', `point-status status-${status}`);
		dot.title = STATUS[status] ?? STATUS.none;
		dot.append(el('span', 'sr-only', dot.title));
		button.append(el('span', 'point-number', String(i + 1).padStart(2, '0')), copy, dot);
		button.addEventListener('click', () => select(point));
		buttons.set(point.id, button);
		list.append(button);
	}
	left.append(list);
	columns.append(left, right);
	if (analysis.points.length) select(analysis.points[0]);
	const footer = el('div', 'analysis-footer');
	const supporting = el('div', 'analysis-support scroll-box');
	const glossary = el('details', 'make-glossary');
	glossary.append(el('summary', '', `詞彙表 · ${analysis.glossary.length} 個詞`));
	const words = el('dl', 'glossary-list');
	for (const word of analysis.glossary) {
		const row = el('div');
		row.append(el('dt', '', word.term), el('dd', '', word.say_as));
		words.append(row);
	}
	glossary.append(words);
	const highlight = el('section', 'make-highlight');
	highlight.append(el('h3', '', `建議重點片 · ${analysis.highlight.total_sec} 秒`),
		chips(highlightPoints(analysis).map(point => `第 ${analysis.points.indexOf(point) + 1} 點 · ${point.title}`)), el('p', 'section-note', analysis.highlight.why));
	supporting.append(glossary, highlight);
	const nextLink = el('a', 'button button-primary', '下一步：選要生成的 →');
	nextLink.href = next;
	footer.append(supporting, nextLink);
	content.append(scope, columns, footer);
	return content;
}
