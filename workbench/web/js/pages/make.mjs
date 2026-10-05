import { api } from '../api.mjs';
import { el, intro } from '../ui.mjs';
import { renderMakeSource } from './make-source.mjs';
import { renderMakeAnalysis } from './make-analysis.mjs';

const STEPS = ['① 教材', '② 分析結果', '③ 生成', '④ 成品'];

export function stepAvailability(unit) {
	const analyzed = Boolean(unit?.analysis?.points?.length);
	return [true, analyzed, analyzed, Boolean(unit?.items?.some(item => item.status === 'done' && Object.keys(item.files ?? {}).length))];
}

export function makeHash(step, query = {}) {
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(query)) if (value !== null && value !== undefined) params.set(key, String(value));
	return `#/make/${step}${params.size ? `?${params}` : ''}`;
}

export async function renderMake(route) {
	let query = { ...route.query };
	const unit = query.unit ? await api.get(`/units/${encodeURIComponent(query.unit)}${api.MOCK && query.state ? `?${new URLSearchParams({ state: query.state })}` : ''}`) : null;
	const available = stepAvailability(unit);
	const step = available[route.step - 1] ? route.step : 1;
	const page = el('section', 'page make-page');
	const heading = intro('一份教材，換個方式理解', '製作教材', unit?.title ?? '先放入教材，再看看學生會問什麼。');
	const bar = el('nav', 'make-steps');
	bar.setAttribute('aria-label', '製作步驟');
	function updateSteps(selectedUnit) {
		const enabled = stepAvailability(selectedUnit);
		const links = STEPS.map((label, i) => {
			const navigable = enabled[i] && step !== i + 1;
			const link = el(navigable ? 'a' : 'span', `make-step${step === i + 1 ? ' active' : ''}`, label);
			if (navigable) link.href = makeHash(i + 1, { unit: query.unit, state: query.state });
			if (!enabled[i]) link.setAttribute('aria-disabled', 'true');
			if (step === i + 1) link.setAttribute('aria-current', 'step');
			return link;
		});
		bar.replaceChildren(...links);
	}
	updateSteps(unit);
	page.append(heading, bar);
	let content;
	if (step === 1) {
		content = await renderMakeSource({ unit, query, notice: step !== route.step ? '先選一份教材並完成分析，再繼續下一步。' : '',
			onUnit(selectedUnit, options = {}) {
				query = { unit: selectedUnit.unit_id, ...(options.preserveState && query.state ? { state: query.state } : {}) };
				updateSteps(selectedUnit);
				const description = heading.children[0].children[2];
				description.textContent = selectedUnit.title;
				globalThis.history?.replaceState(null, '', makeHash(1, query));
				return query;
			} });
	} else if (step === 2) content = renderMakeAnalysis(unit, { next: makeHash(3, { unit: query.unit, state: query.state }) });
	else {
		content = el('div', 'placeholder-region scroll-box');
		const card = el('div', 'placeholder-card');
		card.append(el('p', 'eyebrow', STEPS[step - 1]), el('h2', '', '下一步實作'),
			el('p', 'placeholder-description', '這一步還在準備，教材與分析結果已經留好了。'));
		const back = el('a', 'button', '回到分析結果');
		back.href = makeHash(2, { unit: query.unit, state: query.state });
		card.append(back);
		content.append(card);
	}
	page.append(content);
	page.mount = () => content.mount?.();
	page.dispose = () => content.dispose?.();
	return page;
}
