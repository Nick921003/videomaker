import { api } from '../api.mjs';
import { el, money } from '../ui.mjs';
import { go } from '../router.mjs';
import { layoutSteps, render, setLive } from '../diagram.mjs';
import { button, viewerTools, panViewer } from '../viewers/common.mjs';

const STATUS = { none: '尚未生成', queued: '排隊中', running: '製作中', done: '已完成', failed: '失敗' };
const selectable = item => ['none', 'failed'].includes(item.status);

export async function renderMakeGenerate(initialUnit, { query = {}, onUnit } = {}) {
	const registry = await api.get('/formats');
	let unit = initialUnit;
	const content = el('section', 'make-generate');
	const left = el('div', 'generate-left');
	const selection = el('section', 'make-card generate-selection');
	selection.append(el('h2', 'make-card-heading', '這次要生成哪些？'));
	const checklist = el('div', 'generate-checklist scroll-box');
	const footer = el('div', 'generate-total');
	const total = el('p');
	const start = button('開始生成', 'button-primary');
	footer.append(total, start);
	selection.append(checklist, footer);
	const queueCard = el('section', 'make-card generate-queue');
	queueCard.append(el('h2', 'make-card-heading', '製作佇列'));
	const queueList = el('div', 'generate-queue-list scroll-box');
	queueList.setAttribute('aria-label', '執行與排隊的工作');
	queueCard.append(queueList);
	left.append(selection, queueCard);
	const right = el('section', 'make-card generate-live');
	const heading = el('div', 'generate-live-heading');
	const jobTitle = el('h2', '', '選好項目，就可以開始。');
	const products = button('查看成品 →');
	products.addEventListener('click', () => go('make', 4, { unit: unit.unit_id, ...(query.state ? { state: query.state } : {}) }));
	heading.append(jobTitle, products);
	const diagram = el('section', 'generate-diagram');
	const toolbar = viewerTools(diagram);
	const viewport = el('div', 'pipeline-viewport');
	diagram.append(viewport);
	const feedback = el('div', 'generate-feedback scroll-box');
	const status = el('p', 'section-note');
	status.setAttribute('role', 'status');
	const failures = el('div', 'generate-failures');
	feedback.append(status, failures);
	right.append(heading, diagram, feedback);
	content.append(left, right);
	const chosen = new Set(unit.items.filter(selectable).map(item => item.item));
	const watched = new Map();
	for (const item of unit.items) if (item.job_id && ['queued', 'running', 'failed'].includes(item.status)) watched.set(item.job_id, null);
	if (query.job) watched.set(query.job, null);
	let disposed = false;
	let mounted = false;
	let submitting = false;
	let polling = false;
	let timer;
	let controls;
	let drawnJob;
	let pinned;
	const suffix = api.MOCK && query.state ? `?${new URLSearchParams({ state: query.state })}` : '';
	const unitPath = `/units/${encodeURIComponent(unit.unit_id)}`;
	function refreshTotal() {
		const selected = unit.items.filter(item => selectable(item) && chosen.has(item.item));
		total.textContent = `預估總計 · ${money(selected.reduce((sum, item) => sum + item.estimate_usd, 0))}`;
		start.disabled = submitting || !selected.length;
		products.disabled = !unit.items.some(item => item.status === 'done' && Object.keys(item.files ?? {}).length);
	}
	function renderChecklist() {
		checklist.replaceChildren();
		for (const [label, items] of [['每點影片', unit.items.filter(item => item.format === 'video')], ['整份', unit.items.filter(item => item.format !== 'video')]]) {
			checklist.append(el('h3', 'generate-group-label', label));
			for (const item of items) {
				const row = el('label', 'generate-choice');
				const input = el('input');
				input.type = 'checkbox';
				input.value = item.item;
				input.disabled = submitting || !selectable(item);
				input.checked = selectable(item) && chosen.has(item.item);
				input.addEventListener('change', () => {
					if (input.checked) chosen.add(item.item);
					else chosen.delete(item.item);
					refreshTotal();
				});
				const copy = el('span', 'generate-choice-copy');
				copy.append(el('span', '', item.label), el('span', 'section-note', STATUS[item.status]));
				row.append(input, copy, el('span', 'generate-estimate', money(item.estimate_usd)));
				checklist.append(row);
			}
		}
		refreshTotal();
	}
	async function refreshUnit() {
		const fresh = await api.get(`${unitPath}${suffix}`);
		if (disposed) return;
		const changed = JSON.stringify(unit.items) !== JSON.stringify(fresh.items);
		unit = fresh;
		for (const [id, job] of watched) {
			const latest = job?.unit_id === unit.unit_id ? unit.items.find(item => item.item === job.item)?.job_id : null;
			if (latest && latest !== id) {
				watched.delete(id);
				if (pinned === id) pinned = null;
			}
		}
		if (changed) { onUnit?.(unit); renderChecklist(); }
	}
	function draw(job) {
		if (!job) return;
		const format = [...registry.formats, ...registry.stages].find(entry => entry.id === job.format);
		if (!format) return;
		jobTitle.textContent = `${unit.items.find(item => item.item === job.item)?.label ?? job.item} · ${STATUS[job.state]}`;
		if (drawnJob !== job.job_id) {
			controls?.destroy();
			const nodes = layoutSteps(format.steps);
			const svg = render(viewport, { nodes, edges: nodes.slice(1).map((node, i) => ({ from: nodes[i].id, to: node.id })) }, { mode: 'live' });
			if (mounted) controls = panViewer(svg, diagram, toolbar);
			drawnJob = job.job_id;
		}
		setLive(viewport, job.steps);
	}
	function renderQueue(queue) {
		const rows = new Map([...[queue.running, ...queue.queued].filter(Boolean), ...[...watched.values()].filter(Boolean)].map(job => [job.job_id, job]));
		queueList.replaceChildren();
		for (const job of rows.values()) {
			const row = el('div', `generate-queue-row status-${job.state}`);
			row.append(el('span', '', unit.items.find(item => item.item === job.item && job.unit_id === unit.unit_id)?.label ?? job.item),
				el('span', 'section-note', STATUS[job.state]));
			queueList.append(row);
		}
		if (!rows.size) queueList.append(el('p', 'section-note', '目前沒有排隊的工作。'));
		failures.replaceChildren();
		for (const job of [...watched.values()].filter(job => job?.state === 'failed')) {
			const panel = el('section', 'generate-failure');
			panel.setAttribute('role', 'alert');
			panel.append(el('h3', '', unit.items.find(item => item.item === job.item)?.label ?? job.item),
				el('p', '', job.error?.reason ?? '這次工作沒有完成。'), el('p', 'section-note', job.error?.advice ?? ''));
			const inspect = button('查看失敗步驟');
			inspect.addEventListener('click', () => { pinned = job.job_id; draw(job); });
			panel.append(inspect);
			if (job.error?.retry) {
				const retry = button('重試');
				retry.disabled = submitting;
				retry.addEventListener('click', () => run(async () => {
					const result = await api.post(`/jobs/${encodeURIComponent(job.job_id)}/retry`);
					if (disposed) return;
					watched.delete(job.job_id);
					watched.set(result.job_id, null);
					pinned = null;
				}));
				panel.append(retry);
			}
			failures.append(panel);
		}
		const focus = pinned ? watched.get(pinned) : queue.running ?? watched.get(query.job)
			?? [...watched.values()].find(job => job?.state === 'failed') ?? [...watched.values()].filter(Boolean).at(-1);
		draw(focus);
		status.textContent = queue.running || queue.queued.length ? '工作會依序製作，你可以切到其他頁。'
			: [...watched.values()].some(job => job?.state === 'done') ? '製作完成，可以查看成品。' : '選取項目後，費用依實際用量計算。';
	}
	function schedule() {
		clearTimeout(timer);
		if (mounted && !disposed && !document.hidden) timer = setTimeout(poll, 2000);
	}
	async function poll() {
		if (disposed || !mounted || document.hidden || polling) return;
		polling = true;
		try {
			const queue = await api.get('/queue');
			if (disposed || document.hidden) return;
			for (const job of [queue.running, ...queue.queued].filter(Boolean)) {
				if (job.unit_id === unit.unit_id || job === queue.running) watched.set(job.job_id, job);
			}
			const ids = [...watched].filter(([, job]) => !job || ['queued', 'running'].includes(job.state)).map(([id]) => id);
			const results = await Promise.all(ids.map(async id => [id, await api.get(`/jobs/${encodeURIComponent(id)}`)]));
			if (disposed || document.hidden) return;
			for (const [id, job] of results) watched.set(id, job);
			if (queue.running) queue.running = watched.get(queue.running.job_id) ?? queue.running;
			await refreshUnit();
			if (!disposed && !document.hidden) renderQueue(queue);
		} catch (error) {
			if (!disposed) status.textContent = `${error.reason ?? error.message} ${error.advice ?? '稍後會再讀取。'}`;
		} finally { polling = false; schedule(); }
	}
	async function run(action) {
		if (submitting || disposed) return;
		submitting = true;
		renderChecklist();
		try {
			await action();
			if (!disposed) { await refreshUnit(); await poll(); }
		} catch (error) {
			if (!disposed) status.textContent = `${error.reason ?? error.message} ${error.advice ?? ''}`;
		} finally { submitting = false; if (!disposed) renderChecklist(); }
	}
	start.addEventListener('click', () => run(async () => {
		const items = unit.items.filter(item => selectable(item) && chosen.has(item.item)).map(item => item.item);
		const result = await api.post(`${unitPath}/generate${suffix}`, { items });
		if (disposed) return;
		for (const id of result.job_ids) watched.set(id, null);
		pinned = null;
		status.textContent = result.job_ids.length ? '已加入佇列。' : '選取項目已完成或正在製作。';
	}));
	const visibility = () => { clearTimeout(timer); if (!document.hidden) poll(); };
	renderChecklist();
	content.mount = () => {
		if (mounted || disposed) return;
		mounted = true;
		document.addEventListener('visibilitychange', visibility);
		poll();
	};
	content.dispose = () => {
		disposed = true;
		clearTimeout(timer);
		document.removeEventListener('visibilitychange', visibility);
		controls?.destroy();
	};
	return content;
}
