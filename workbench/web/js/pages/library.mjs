import { api } from '../api.mjs';
import { el, icon, intro, money } from '../ui.mjs';
import { go } from '../router.mjs';
import { button } from '../viewers/common.mjs';
import { mount as mountVideo } from '../viewers/video.mjs';

function unitCard(unit) {
	const card = el('a', 'library-unit make-card');
	card.href = `#/make/4?${new URLSearchParams({ unit: unit.unit_id })}`;
	card.setAttribute('data-unit-id', unit.unit_id);
	card.append(el('h3', '', unit.title), el('p', 'section-note', `${unit.points} 個重點${unit.analyzed ? '' : ' · 尚未分析'}`));
	const products = el('div', 'library-products');
	for (const [format, label] of [['video', `${unit.products.video} 支影片`], ['highlight', '重點片'], ['mindmap', '心智圖'], ['slides', '簡報']]) {
		if (!unit.products[format]) continue;
		const product = el('span', 'library-product');
		product.append(icon(format), el('span', '', label));
		products.append(product);
	}
	if (!products.children.length) products.append(el('span', 'section-note', '還沒有成品'));
	card.append(products, el('p', 'library-spent', unit.unknown_calls
		? `已知小計 · ${money(unit.spent_usd)}，另有 ${unit.unknown_calls} 筆金額未知`
		: `實際花費 · ${money(unit.spent_usd)}`));
	return card;
}

export async function renderLibrary() {
	const units = await api.get('/units');
	const page = el('section', 'page library-page');
	page.append(intro('從學生的問題開始', '素材庫', '把完成的素材收在一起，找到卡住的那一段。'));
	const ask = el('section', 'make-card library-ask');
	ask.append(el('h2', '', '學生提問'));
	const body = el('div', 'library-ask-body');
	const form = el('form', 'library-question');
	const unitLabel = el('label', 'ask-field');
	const select = el('select');
	select.setAttribute('aria-label', '選教材');
	for (const unit of units) {
		const option = el('option', '', `${unit.title}${unit.analyzed ? '' : '（尚未分析）'}`);
		option.value = unit.unit_id;
		option.disabled = !unit.analyzed;
		select.append(option);
	}
	select.value = units.find(unit => unit.analyzed)?.unit_id ?? '';
	select.disabled = !select.value;
	if (!units.length) select.append(el('option', '', '還沒有教材'));
	unitLabel.append(el('span', '', '選教材'), select);
	const questionLabel = el('label', 'ask-field ask-question-field');
	const question = el('textarea');
	question.rows = 2;
	question.value = '';
	question.placeholder = '例如：迴圈為什麼多跑一次？';
	question.setAttribute('aria-label', '學生問題');
	question.disabled = select.disabled;
	questionLabel.append(el('span', '', '學生問題'), question);
	const submit = button('找段落', 'button-primary');
	submit.type = 'submit';
	form.append(unitLabel, questionLabel, submit);
	const result = el('section', 'library-answer scroll-box');
	result.setAttribute('aria-label', '提問結果');
	result.setAttribute('aria-live', 'polite');
	result.tabIndex = 0;
	body.append(form, result);
	ask.append(body);
	const section = el('section', 'library-section');
	const heading = el('div', 'section-heading');
	heading.append(el('h2', '', '我的教材'), el('span', 'section-count', `${units.length} 份教材`));
	const grid = el('div', 'library-grid scroll-box');
	grid.tabIndex = 0;
	grid.setAttribute('aria-label', '教材清單');
	const pager = el('nav', 'list-pager');
	pager.setAttribute('aria-label', '教材分頁');
	const previous = button('上一頁');
	const next = button('下一頁');
	const counter = el('span', 'section-count');
	counter.setAttribute('aria-live', 'polite');
	pager.append(previous, counter, next);
	section.append(heading, grid, pager);
	page.append(ask, section);
	let index = 0;
	let revision = 0;
	let disposed = false;
	let busy = false;
	let viewer;
	function renderCards() {
		grid.replaceChildren(...units.slice(index * 6, (index + 1) * 6).map(unitCard));
		if (!units.length) {
			const create = el('a', 'button', '放入第一份教材 →');
			create.href = '#/make/1';
			grid.append(el('p', 'empty-note', '還沒有教材，先放入一份再來提問。'), create);
		}
		previous.disabled = index === 0;
		next.disabled = (index + 1) * 6 >= units.length;
		counter.textContent = `${index + 1} / ${Math.max(1, Math.ceil(units.length / 6))}`;
	}
	function updateSubmit() { submit.disabled = busy || !select.value || !question.value.trim(); }
	function resetAnswer() {
		revision++;
		busy = false;
		viewer?.dispose();
		viewer = null;
		result.replaceChildren(el('p', 'section-note', select.disabled ? '先完成一份教材的分析，就能找對應段落。' : '選好教材，說說卡住的地方。'));
		result.setAttribute('aria-busy', 'false');
		updateSubmit();
	}
	async function showAnswer(answer, unitId, version) {
		let detail;
		if (answer.kind === 'story' || answer.kind === 'highlight') {
			try { detail = await api.get(`/units/${encodeURIComponent(unitId)}`); } catch { /* 仍可顯示匹配與影片。 */ }
		}
		if (disposed || version !== revision) return;
		result.replaceChildren();
		if (answer.kind === 'out_of_scope') {
			const lock = icon('lock');
			lock.setAttribute('data-icon', 'lock');
			result.append(lock, el('h3', 'answer-message', '這份教材沒有教這個'), el('p', '', '換個問題，或選擇另一份教材。'));
			return;
		}
		if (answer.kind === 'no_match') {
			result.append(el('h3', 'answer-message', '找不到對應的段落'), el('p', '', '試著描述你卡住的概念，或先查看這份教材的重點。'));
			const browse = el('a', 'button', '查看教材重點');
			browse.href = `#/make/2?${new URLSearchParams({ unit: unitId })}`;
			result.append(browse);
			return;
		}
		const item = answer.kind === 'highlight' ? 'highlight' : answer.story;
		const matched = detail?.analysis?.points?.find(point => point.id === item);
		const heading = el('div', 'answer-heading');
		heading.append(el('span', 'badge', answer.video ? '可直接觀看' : '尚未製作影片'), el('p', 'answer-source', `對應教材 · ${detail?.title ?? units.find(unit => unit.unit_id === unitId)?.title ?? '目前教材'}`));
		result.append(heading, el('h3', 'answer-message', matched?.title ?? (answer.kind === 'highlight' ? '找到單元重點片' : '找到對應的段落')));
		if (matched?.question) result.append(el('p', 'answer-question', matched.question));
		const actions = el('div', 'answer-actions');
		const browse = el('a', 'button', '查看教材重點');
		browse.href = `#/make/2?${new URLSearchParams({ unit: unitId })}`;
		actions.append(browse);
		result.append(actions);
		if (answer.reason) {
			const why = el('details', 'answer-reason');
			why.append(el('summary', '', '為什麼找到這段'), el('p', '', answer.reason));
			result.append(why);
		}
		if (answer.video) {
			// API 回的是媒體網址；共用播放器接收單元內的相對路徑。
			const prefix = `/media/${encodeURIComponent(unitId)}/`;
			const path = answer.video.startsWith(prefix) ? answer.video.slice(prefix.length).split('/').map(decodeURIComponent).join('/') : answer.video;
			const host = el('div', 'library-video');
			result.append(host);
			viewer = mountVideo(host, { unit: unitId, item, files: { video: path } });
		} else if (item) {
			const generate = button('生成這段', 'button-primary');
			const errorNotice = el('p', 'product-error');
			errorNotice.setAttribute('role', 'alert');
			actions.append(generate);
			result.append(errorNotice);
			generate.addEventListener('click', async () => {
				if (generate.disabled || disposed || version !== revision) return;
				generate.disabled = true;
				errorNotice.textContent = '';
				try {
					await api.post(`/units/${encodeURIComponent(unitId)}/generate`, { items: [item] });
					if (!disposed && version === revision) go('make', 3, { unit: unitId });
				} catch (error) {
					if (!disposed && version === revision) errorNotice.textContent = `${error.reason ?? error.message} ${error.advice ?? ''}`;
				} finally { generate.disabled = false; }
			});
		}
	}
	form.addEventListener('submit', async event => {
		event.preventDefault();
		if (busy || disposed || !select.value || !question.value.trim()) return;
		resetAnswer();
		const version = revision;
		const unitId = select.value;
		busy = true;
		updateSubmit();
		result.setAttribute('aria-busy', 'true');
		result.replaceChildren(el('p', 'section-note', '正在找對應段落…'));
		try {
			const answer = await api.post('/ask', { unit_id: unitId, question: question.value.trim() });
			if (!disposed && version === revision) await showAnswer(answer, unitId, version);
		} catch (error) {
			if (!disposed && version === revision) result.replaceChildren(el('p', 'product-error', `${error.reason ?? error.message} ${error.advice ?? ''}`));
		} finally {
			if (!disposed && version === revision) { busy = false; result.setAttribute('aria-busy', 'false'); updateSubmit(); }
		}
	});
	select.addEventListener('change', resetAnswer);
	question.addEventListener('input', resetAnswer);
	previous.addEventListener('click', () => { if (index > 0) { index--; renderCards(); } });
	next.addEventListener('click', () => { if ((index + 1) * 6 < units.length) { index++; renderCards(); } });
	resetAnswer();
	renderCards();
	page.dispose = () => { disposed = true; revision++; viewer?.dispose(); };
	return page;
}
