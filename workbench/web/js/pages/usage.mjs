import { api } from '../api.mjs';
import { el, intro, money } from '../ui.mjs';
import { button } from '../viewers/common.mjs';

function callTable(calls) {
	const box = el('div', 'usage-calls scroll-box');
	const table = el('table');
	const head = el('thead');
	const headings = el('tr');
	for (const label of ['時間', '步驟', '模型', '輸入', '輸出', '花費']) {
		const cell = el('th', '', label);
		cell.setAttribute('scope', 'col');
		headings.append(cell);
	}
	head.append(headings);
	const body = el('tbody');
	for (const call of calls) {
		const row = el('tr');
		const date = new Date(call.at);
		const time = el('time', '', Number.isNaN(date.getTime()) ? call.at : date.toLocaleString('zh-TW', { hour12: false }));
		time.dateTime = call.at;
		const cell = el('td');
		cell.append(time);
		row.append(cell, ...[call.step, call.model, call.in, call.out, call.cost_unknown ? '未知' : money(call.usd)].map(value => el('td', '', String(value))));
		body.append(row);
	}
	table.append(head, body);
	box.append(table);
	if (!calls.length) box.append(el('p', 'section-note', '還沒有呼叫紀錄。'));
	return box;
}

export async function renderUsage() {
	let data = await api.get('/usage');
	const page = el('section', 'page usage-page');
	page.append(intro('每一筆花費，都看得見', '用量', '看看每份教材、每件成品，實際花了多少。'));
	const totals = el('section', 'metrics usage-totals');
	totals.setAttribute('aria-label', '用量總計');
	const section = el('section', 'usage-section');
	const heading = el('div', 'section-heading');
	heading.append(el('h2', '', '依教材查看'));
	const status = el('p', 'section-note usage-status');
	status.setAttribute('role', 'status');
	const retry = button('再讀取');
	retry.hidden = true;
	heading.append(status, retry);
	const list = el('div', 'usage-list scroll-box');
	list.tabIndex = 0;
	list.setAttribute('aria-label', '教材用量');
	const pager = el('nav', 'list-pager');
	pager.setAttribute('aria-label', '用量分頁');
	const previous = button('上一頁');
	const next = button('下一頁');
	const counter = el('span', 'section-count');
	counter.setAttribute('aria-live', 'polite');
	pager.append(previous, counter, next);
	section.append(heading, list, pager);
	page.append(totals, section);
	const expanded = new Set();
	const summaries = new Map();
	let listSignature;
	let index = 0;
	let timer;
	let mounted = false;
	let disposed = false;
	let polling = false;
	let busy = false;
	function renderTotals() {
		totals.replaceChildren();
		for (const [label, value] of [['今天', data.totals.today], ['全部', data.totals.all]]) {
			const metric = el('div', 'metric metric-cost');
			metric.append(el('p', 'metric-label', label), el('p', 'metric-value', money(value)));
			const unknown = label === '今天' ? data.totals.unknown_today : data.totals.unknown_calls;
			if (unknown) metric.append(el('p', 'section-note', `已知小計，另有 ${unknown} 筆金額未知`));
			totals.append(metric);
		}
		const models = el('div', 'metric usage-models');
		const bars = el('div', 'usage-model-bars scroll-box');
		const entries = Object.entries(data.totals.by_model);
		const all = entries.reduce((sum, [, usd]) => sum + usd, 0);
		for (const [model, usd] of entries) {
			const row = el('div', 'usage-model');
			const label = el('div', 'usage-model-label');
			label.append(el('span', '', model), el('span', '', money(usd)));
			if (data.totals.unknown_calls) label.append(el('span', 'section-note', '已知小計'));
			const meter = el('meter');
			meter.min = 0;
			meter.max = all || 1;
			meter.value = usd;
			meter.setAttribute('aria-label', `${model} 花費占比`);
			row.append(label, meter);
			bars.append(row);
		}
		if (!entries.length) bars.append(el('p', 'section-note', '還沒有模型用量'));
		models.append(el('p', 'metric-label', '依模型'), bars);
		totals.append(models);
	}
	function renderList() {
		index = Math.min(index, Math.max(0, Math.ceil(data.units.length / 10) - 1));
		const pageUnits = data.units.slice(index * 10, (index + 1) * 10);
		const signature = JSON.stringify([index, data.units.length, pageUnits]);
		if (signature === listSignature) return;
		listSignature = signature;
		const focused = [...summaries].find(([, node]) => node === document.activeElement)?.[0];
		summaries.clear();
		const scroll = list.scrollTop;
		const groups = pageUnits.map(unit => {
			const group = el('section', 'usage-unit make-card');
			group.setAttribute('data-unit-id', unit.unit_id);
			const title = el('div', 'usage-unit-heading');
			title.append(el('h3', '', unit.title), el('strong', '', money(unit.usd)));
			if (unit.unknown_calls) title.append(el('span', 'section-note', `已知小計，另有 ${unit.unknown_calls} 筆金額未知`));
			group.append(title);
			for (const item of unit.items) {
				const key = JSON.stringify([unit.unit_id, item.item]);
				const details = el('details', 'usage-item');
				details.open = expanded.has(key);
				const summary = el('summary');
				summaries.set(key, summary);
				summary.append(el('span', '', item.label), el('span', 'usage-item-cost', money(item.usd)), el('span', 'section-count', `${item.calls.length} 筆呼叫`));
				if (item.unknown_calls) summary.append(el('span', 'section-note', `已知小計，另有 ${item.unknown_calls} 筆金額未知`));
				details.append(summary, callTable(item.calls));
				details.addEventListener('toggle', () => { if (details.open) expanded.add(key); else expanded.delete(key); });
				group.append(details);
			}
			return group;
		});
		list.replaceChildren(...groups);
		if (!groups.length) list.append(el('p', 'empty-note', '還沒有用量，製作教材後會顯示在這裡。'));
		list.scrollTop = scroll;
		previous.disabled = index === 0;
		next.disabled = (index + 1) * 10 >= data.units.length;
		counter.textContent = `${index + 1} / ${Math.max(1, Math.ceil(data.units.length / 10))} · ${data.units.length} 份教材`;
		if (focused) summaries.get(focused)?.focus({ preventScroll: true });
	}
	const visible = () => mounted && !disposed && !document.hidden;
	function schedule() {
		clearTimeout(timer);
		if (visible() && busy) timer = setTimeout(poll, 2000);
	}
	async function poll(force = false) {
		if (!visible() || polling) return;
		polling = true;
		retry.disabled = true;
		try {
			const queue = await api.get('/queue');
			if (!visible()) return;
			const wasBusy = busy;
			busy = Boolean(queue.running || queue.queued.length);
			// 工作剛結束時補讀最後一筆，再停止用量輪詢。
			if (busy || wasBusy || force) {
				const refreshed = await api.get('/usage');
				if (!visible()) return;
				data = refreshed;
				renderTotals();
				renderList();
			}
			retry.hidden = true;
			status.textContent = busy ? '製作中，每 2 秒更新' : '點項目展開呼叫紀錄';
		} catch (error) {
			if (visible()) {
				status.textContent = `${error.reason ?? error.message} ${error.advice ?? '稍後再試。'}`;
				retry.hidden = false;
			}
		} finally { polling = false; retry.disabled = false; schedule(); }
	}
	const visibility = () => { clearTimeout(timer); if (visible()) poll(); };
	const queueChanged = event => {
		if (visible() && Boolean(event.detail.running || event.detail.queued.length) !== busy) poll();
	};
	retry.addEventListener('click', () => poll(true));
	previous.addEventListener('click', () => { if (index > 0) { index--; renderList(); list.scrollTop = 0; } });
	next.addEventListener('click', () => { if ((index + 1) * 10 < data.units.length) { index++; renderList(); list.scrollTop = 0; } });
	renderTotals();
	renderList();
	status.textContent = '點項目展開呼叫紀錄';
	page.mount = () => {
		if (mounted || disposed) return;
		mounted = true;
		document.addEventListener('visibilitychange', visibility);
		document.addEventListener('workbench:queue', queueChanged);
		poll();
	};
	page.dispose = () => {
		disposed = true;
		clearTimeout(timer);
		document.removeEventListener('visibilitychange', visibility);
		document.removeEventListener('workbench:queue', queueChanged);
	};
	return page;
}
