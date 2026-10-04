import { api } from '../api.mjs';
import { el, icon, money, displayName, intro } from '../ui.mjs';

export function summarizeOverview(formatsData = {}, units = [], unitDetails = []) {
	const available = (formatsData?.formats ?? []).filter(f => f.status === 'available').length;

	let products = 0;
	if (units && units.length > 0) {
		for (const u of units) {
			if (u.products) {
				for (const val of Object.values(u.products)) {
					if (typeof val === 'number') products += val;
					else if (val === true) products += 1;
				}
			}
		}
	} else if (unitDetails && unitDetails.length > 0) {
		for (const u of unitDetails) {
			if (u.items) {
				products += u.items.filter(i => i.status === 'done').length;
			}
		}
	}

	let videoTotalCost = 0;
	let finishedVideoCount = 0;
	for (const u of unitDetails ?? []) {
		for (const item of u.items ?? []) {
			if (item.format === 'video' && item.status === 'done' && typeof item.cost_usd === 'number') {
				videoTotalCost += item.cost_usd;
				finishedVideoCount += 1;
			}
		}
	}

	const averageVideoCost = finishedVideoCount > 0 ? (videoTotalCost / finishedVideoCount) : null;

	return {
		available,
		products,
		averageVideoCost,
	};
}

const descriptions = {
	video: '一個問題，一支影片。把卡住的地方慢慢演清楚。',
	highlight: '把整份教材的重點串起來，先看懂全貌。',
	mindmap: '把概念與關係攤開，一眼找到彼此的連結。',
	slides: '把教材變成可上課、可翻閱的簡報。',
};

function metric(label, value, note, className = '') {
	const card = el('div', `metric ${className}`.trim());
	card.append(el('p', 'metric-label', label), el('p', 'metric-value', value), el('p', 'metric-note', note));
	return card;
}

function formatCard(format, details) {
	const planned = format.status === 'planned';
	const card = el('a', `format-card${planned ? ' is-planned' : ''}`);
	card.href = `#/pipelines?${new URLSearchParams({ focus: format.id })}`;
	const top = el('div', 'format-top');
	top.append(icon(descriptions[format.id] ? format.id : 'planned', 'format-icon'),
		el('span', `badge${planned ? ' badge-soft' : ''}`, planned ? '規劃中' : '可用'));
	const heading = el('div', 'format-heading');
	heading.append(el('h3', '', displayName(format)), el('span', 'scope', format.scope === 'point' ? '逐點' : '整份'));
	const description = el('p', 'format-description', descriptions[format.id] ?? format.planned_note?.why ?? '換個方式，陪學生理解教材。');
	const model = el('p', 'format-model');
	const models = [...new Set(format.steps.filter(step => step.paid).map(step => step.model))];
	model.append(el('span', 'detail-label', '模型'), el('span', '', models.length
		? models.map(name => name.replace(/^google:gemini-/, 'Gemini ').replace(/-flash/, ' Flash').replace(/-tts/, ' TTS').replace(/（.*?）/g, '')).join(' ＋ ')
		: planned ? '待評估' : '本機'));
	const samples = details.flatMap(unit => unit.items).filter(item => item.format === format.id && item.status === 'done' && Number.isFinite(item.cost_usd));
	const estimates = details.flatMap(unit => unit.items).filter(item => item.format === format.id && Number.isFinite(item.estimate_usd) && item.estimate_usd > 0);
	const costs = samples.length ? samples.map(item => item.cost_usd) : estimates.map(item => item.estimate_usd);
	const unmeasured = format.steps.some(step => step.paid && step.cost === '試跑後填入');
	const cost = planned ? '待評估' : unmeasured ? '試跑後填入'
		: costs.length ? money(costs.reduce((sum, value) => sum + value, 0) / costs.length)
			: format.steps.find(step => step.paid)?.cost ?? '免費';
	const footer = el('div', 'format-footer');
	const price = el('div', 'format-price');
	price.append(el('span', 'detail-label', planned || unmeasured ? '單價' : samples.length ? '平均實際' : '預估單價'), el('strong', '', cost));
	footer.append(price, icon('arrow', 'card-arrow'));
	card.append(top, heading, description, model, footer);
	return card;
}

export async function renderOverview() {
	const [registry, units] = await Promise.all([api.get('/formats'), api.get('/units')]);
	const details = await Promise.all(units.map(unit => api.get(`/units/${encodeURIComponent(unit.unit_id)}`)));
	const summary = summarizeOverview(registry, units, details);
	const page = el('section', 'page overview-page');
	const header = intro('一份教材，多種學法', '看不懂？換個方式理解。', '把學生卡住的地方，變成看得懂的教材。');
	const action = el('a', 'button button-primary', '開始製作');
	action.href = '#/make/1';
	action.append(icon('arrow'));
	header.append(action);
	const metrics = el('section', 'metrics');
	metrics.setAttribute('aria-label', '工作台概況');
	metrics.append(
		metric('可用形式', String(summary.available), '同一份教材，不同理解方式'),
		metric('每支影片平均', summary.averageVideoCost === null ? '—' : money(summary.averageVideoCost), '已完成逐點影片的實際花費', 'metric-cost'),
		metric('素材庫成品', String(summary.products), '已完成，隨時可以教學'),
	);
	const section = el('section', 'formats-section');
	const sectionHeading = el('div', 'section-heading');
	const heading = el('div');
	heading.append(el('h2', '', '選一種理解方式'), el('p', 'section-note', '點卡片，看看教材怎麼做出來。'));
	sectionHeading.append(heading, el('span', 'section-count', `${registry.formats.length} 種形式`));
	const grid = el('div', 'format-grid scroll-box');
	grid.tabIndex = 0;
	grid.setAttribute('role', 'region');
	grid.setAttribute('aria-label', '教材形式');
	grid.append(...registry.formats.map(format => formatCard(format, details)));
	if (!registry.formats.length) grid.append(el('p', 'empty-note', '還沒有教材形式，稍後再來看看。'));
	section.append(sectionHeading, grid);
	page.append(header, metrics, section);
	return page;
}
