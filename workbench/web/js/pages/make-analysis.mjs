import { el } from '../ui.mjs';

const STATUS = { none: '尚未生成', queued: '排隊中', running: '製作中', done: '已完成', failed: '失敗' };
export function pointStatus(unit, id) {
	return unit.items?.find(item => item.item === id && item.format === 'video')?.status ?? 'none';
}
export function highlightPoints(analysis) {
	return (analysis.highlight?.points ?? []).map(id => analysis.points.find(point => point.id === id)).filter(Boolean);
}
function chips(values) {
	const row = el('div', 'make-chips');
	for (const value of values ?? []) row.append(el('span', 'make-chip', String(value)));
	return row;
}
function disclosure(title, ...nodes) {
	const section = el('details', 'analysis-disclosure');
	section.append(el('summary', '', title), ...nodes);
	return section;
}

export function renderMakeAnalysis(unit, { next } = {}) {
	const analysis = unit.analysis;
	const content = el('section', 'make-analysis');
	const overview = el('header', 'analysis-overview');
	const copy = el('div');
	copy.append(el('h2', '', '教材重點'), el('p', '', `${analysis.points.length} 個重點，選一個查看教學內容。`));
	const nextLink = el('a', 'button button-primary', '下一步：選要生成的 →');
	nextLink.href = next;
	overview.append(copy, nextLink);
	const columns = el('div', 'analysis-columns');
	const left = el('section', 'make-card point-panel');
	const tools = el('div', 'point-tools');
	const search = el('input', 'point-search');
	search.type = 'search';
	search.placeholder = '搜尋重點或學生問題';
	search.setAttribute('aria-label', '搜尋教材重點');
	const count = el('p', 'point-count');
	count.setAttribute('role', 'status');
	tools.append(search, count);
	const list = el('div', 'point-list');
	list.setAttribute('aria-label', '分析點清單');
	const empty = el('p', 'empty-note', '找不到符合的重點，試試其他關鍵字。');
	empty.hidden = true;
	const right = el('section', 'make-card point-detail');
	right.id = 'selected-point-detail';
	right.setAttribute('aria-label', '選取問題的詳情');
	const buttons = new Map();
	let selected = null;
	function select(point) {
		selected = point.id;
		for (const [id, button] of buttons) button.setAttribute('aria-pressed', String(id === point.id));
		const top = el('div', 'point-detail-heading');
		top.append(el('p', 'eyebrow', `重點 ${String(analysis.points.indexOf(point) + 1).padStart(2, '0')}`), el('h2', '', point.title));
		const question = el('section', 'point-question-block');
		question.append(el('h3', '', '學生會問'), el('p', 'point-question', point.question));
		const show = el('section', 'point-teaching');
		show.append(el('h3', '', '教學呈現'), el('p', '', point.show || '依教材內容安排示範。'));
		const asks = el('ul', 'point-asks');
		for (const q of point.also_asks ?? []) asks.append(el('li', '', q));
		const extras = el('div', 'point-extras');
		if (asks.children.length) extras.append(disclosure('其他問法', asks));
		const details = el('div', 'point-production');
		details.append(el('p', '', `建議影片長度 ${point.sec} 秒`));
		const screens = (point.screens ?? []).map(screen => typeof screen === 'object' ? screen.title ?? screen.label ?? screen.id ?? '' : screen).filter(Boolean);
		if (screens.length) details.append(chips(screens));
		const objectives = (point.objectives ?? []).filter(objective => typeof objective === 'string');
		if (objectives.length) details.append(chips(objectives));
		extras.append(disclosure('製作細節', details));
		right.replaceChildren(top, question, show, extras);
	}
	for (const [i, point] of analysis.points.entries()) {
		const button = el('button', 'point-choice');
		button.type = 'button';
		button.setAttribute('data-point-id', point.id);
		button.setAttribute('aria-pressed', 'false');
		button.setAttribute('aria-controls', right.id);
		const text = el('span', 'point-choice-copy');
		text.append(el('strong', 'point-choice-title', point.title), el('span', 'point-choice-question', point.question));
		const status = pointStatus(unit, point.id);
		text.append(el('span', `point-status-label status-label-${status}`, `影片 · ${STATUS[status] ?? STATUS.none}`));
		button.append(el('span', 'point-number', String(i + 1).padStart(2, '0')), text);
		button.addEventListener('click', () => {
			select(point);
			right.scrollIntoView?.({ block: 'nearest' });
		});
		buttons.set(point.id, button);
		list.append(button);
	}
	function filter() {
		const query = (search.value ?? '').trim().toLocaleLowerCase();
		const visible = analysis.points.filter(point => [point.title, point.question, ...(point.also_asks ?? [])].join(' ').toLocaleLowerCase().includes(query));
		const ids = new Set(visible.map(point => point.id));
		for (const [id, button] of buttons) button.hidden = !ids.has(id);
		count.textContent = query ? `${visible.length} / ${analysis.points.length} 個重點` : `全部 ${analysis.points.length} 個重點`;
		empty.hidden = Boolean(visible.length);
		if (!visible.length) {
			selected = null;
			for (const button of buttons.values()) button.setAttribute('aria-pressed', 'false');
			right.replaceChildren(el('p', 'empty-note', '搜尋到重點後，這裡會顯示教學內容。'));
		} else if (!ids.has(selected)) select(visible[0]);
	}
	search.addEventListener('input', filter);
	filter();
	left.append(tools, list, empty);
	columns.append(left, right);
	const supporting = el('div', 'analysis-support');
	if (analysis.scope?.covers?.length) supporting.append(disclosure('教材主題', chips(analysis.scope.covers)));
	const words = el('dl', 'glossary-list');
	for (const word of analysis.glossary ?? []) {
		const row = el('div'); row.append(el('dt', '', word.term), el('dd', '', word.say_as)); words.append(row);
	}
	if (words.children.length) supporting.append(disclosure(`詞彙表 · ${words.children.length} 個詞`, words));
	if (analysis.highlight) supporting.append(disclosure('建議重點片', chips(highlightPoints(analysis).map(point => point.title)), el('p', '', analysis.highlight.why), el('p', '', `建議長度 ${analysis.highlight.total_sec} 秒`)));
	content.append(overview, columns, supporting);
	return content;
}
