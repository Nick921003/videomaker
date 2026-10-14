import { api } from '../api.mjs';
import { el, money } from '../ui.mjs';
import { go } from '../router.mjs';
import { layoutSteps, render, setLive } from '../diagram.mjs';
import { button, viewerTools, panViewer } from '../viewers/common.mjs';
import { renderKeyPointBanner, REVIEW_REASON, NOTE_LIMIT } from './key-point-banner.mjs';

const STATUS = { none: '尚未生成', queued: '排隊中', running: '製作中', done: '已完成', failed: '失敗' };
const selectable = item => ['none', 'failed'].includes(item.status);
const NEEDS_KEY_POINTS = ['slides', 'mindmap'];
const KEY_POINTS_STALE_NOTE = '重點清單狀態暫時讀不到，稍後自動重試';

export async function renderMakeGenerate(initialUnit, { query = {}, onUnit } = {}) {
	const registry = await api.get('/formats');
	let unit = initialUnit;
	const content = el('section', 'make-generate');
	content.setAttribute('data-selection', 'expanded');
	const left = el('div', 'generate-left');
	left.id = 'generation-selection';
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
	left.append(selection);
	const right = el('section', 'make-card generate-live');
	const heading = el('div', 'generate-live-heading');
	const jobTitle = el('h2', '', '製作過程');
	const selectionToggle = button('收合選擇');
	selectionToggle.setAttribute('aria-controls', left.id);
	function collapseSelection(collapsed) {
		content.setAttribute('data-selection', collapsed ? 'collapsed' : 'expanded');
		left.hidden = collapsed;
		selectionToggle.textContent = collapsed ? '展開選擇' : '收合選擇';
		selectionToggle.setAttribute('aria-expanded', String(!collapsed));
		if (collapsed) actions.append(start);
		else footer.append(start);
		start.hidden = collapsed && start.disabled;
	}
	selectionToggle.addEventListener('click', () => collapseSelection(!left.hidden));
	collapseSelection(false);
	const products = button('查看成品 →');
	products.addEventListener('click', () => go('make', 4, { unit: unit.unit_id, ...(query.state ? { state: query.state } : {}) }));
	const actions = el('div', 'generate-actions');
	actions.append(selectionToggle, products);
	heading.append(jobTitle, actions);
	const idle = el('p', 'generation-idle', '開始生成後，這裡會顯示目前步驟與製作進度。');
	const diagram = el('section', 'generate-diagram');
	diagram.hidden = true;
	const toolbar = viewerTools(diagram);
	const viewport = el('div', 'pipeline-viewport');
	diagram.append(viewport);
	const feedback = el('div', 'generate-feedback scroll-box');
	const status = el('p', 'generation-message', '勾選左側項目，再按開始生成。');
	status.setAttribute('role', 'status');
	const failures = el('div', 'generate-failures');
	feedback.append(status, failures);
	right.append(heading, feedback, queueCard, idle, diagram);
	// 橫幅佔滿整列，放在選擇區與製作過程之前。
	const reviewSlot = el('div', 'key-point-review');
	reviewSlot.hidden = true;
	content.append(reviewSlot, left, right);
	const failedItems = unit.items.filter(item => item.status === 'failed' && item.job_id);
	const chosen = new Set((failedItems.length ? failedItems : unit.items.filter(selectable)).map(item => item.item));
	const watched = new Map();
	for (const item of unit.items) if (item.job_id && ['queued', 'running', 'failed'].includes(item.status)) watched.set(item.job_id, null);
	if (query.job) watched.set(query.job, null);
	collapseSelection(watched.size > 0);
	let disposed = false;
	let mounted = false;
	let submitting = false;
	let polling = false;
	let timer;
	let controls;
	let drawnJob;
	let queueSignature = '';
	let pinned;
	let review = null;
	let reviewBusy = false;
	let reviewMessage = '';
	let reviewNote = '';
	let reviewLoaded = false;
	let keyPointsStale = false;
	const suffix = api.MOCK && query.state ? `?${new URLSearchParams({ state: query.state })}` : '';
	const unitPath = `/units/${encodeURIComponent(unit.unit_id)}`;
	const blocked = item => review?.status === 'needs_review' && NEEDS_KEY_POINTS.includes(item.format);
	function refreshTotal() {
		const selected = unit.items.filter(item => selectable(item) && !blocked(item) && chosen.has(item.item));
		total.textContent = `預估總計 · ${money(selected.reduce((sum, item) => sum + item.estimate_usd, 0))}`;
		start.disabled = submitting || !selected.length;
		start.hidden = left.hidden && !selected.length;
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
				input.disabled = submitting || !selectable(item) || blocked(item);
				input.checked = selectable(item) && !blocked(item) && chosen.has(item.item);
				input.addEventListener('change', () => {
					if (input.checked) chosen.add(item.item);
					else chosen.delete(item.item);
					refreshTotal();
				});
				const copy = el('span', 'generate-choice-copy');
				copy.append(el('span', '', item.label), el('span', 'generate-item-status', STATUS[item.status]));
				if (blocked(item)) copy.append(el('span', 'generate-item-reason', REVIEW_REASON));
				row.append(input, copy, el('span', 'generate-estimate', money(item.estimate_usd)));
				checklist.append(row);
			}
		}
		refreshTotal();
	}
	function renderReview() {
		const pending = review?.status === 'needs_review';
		reviewSlot.hidden = !pending;
		if (!pending) { reviewSlot.replaceChildren(); return; }
		reviewSlot.replaceChildren(renderKeyPointBanner(review, {
			busy: reviewBusy, message: reviewMessage, note: reviewNote,
			onNote: value => { reviewNote = value; },
			onConfirm: () => reviewAction({ action: 'confirm', digest: review.digest }),
			onReextract: note => {
				reviewNote = note;
				if (note.length > NOTE_LIMIT) {
					reviewMessage = `備註最多 ${NOTE_LIMIT} 字，請縮短後再送出。`;
					renderReview();
					return;
				}
				reviewAction({ action: 'reextract', note });
			},
		}));
	}
	// 讀不到時不擋生成；伺服器仍會用 key_points_review 把關。
	async function loadKeyPoints() {
		let fresh = null;
		let failed = false;
		try { fresh = await api.get(`${unitPath}/key-points${suffix}`); } catch { failed = true; }
		if (disposed) return;
		// 讀取失敗就取消「已載入」，讓下一次輪詢重試；成功則清除暫時提示。
		if (failed) reviewLoaded = false;
		keyPointsStale = failed;
		const wasPending = review?.status === 'needs_review';
		review = fresh?.status ? fresh : null;
		renderReview();
		if (wasPending !== (review?.status === 'needs_review')) renderChecklist();
	}
	async function reviewAction(body) {
		if (reviewBusy || disposed) return;
		reviewBusy = true;
		reviewMessage = '';
		renderReview();
		try {
			await api.post(`${unitPath}/key-points${suffix}`, body);
			if (body.action === 'reextract') reviewNote = '';
		} catch (error) {
			reviewMessage = `${error.reason ?? error.message} ${error.advice ?? ''}`.trim();
		}
		reviewBusy = false;
		// 無論成敗都重讀，確保畫面與伺服器上的清單與 digest 一致。
		await loadKeyPoints();
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
		if (disposed) return;
		const format = [...registry.formats, ...registry.stages].find(entry => entry.id === job.format);
		if (!format) return;
		idle.hidden = true;
		diagram.hidden = false;
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
		const signature = JSON.stringify([submitting, [...rows.values()].map(job => [job.job_id, job.state, job.error, unit.items.find(item => item.item === job.item)?.label])]);
		if (signature !== queueSignature) {
			queueSignature = signature;
			const focusedKey = document.activeElement?.getAttribute('data-focus-key');
			const focusTargets = [];
			queueList.replaceChildren();
			for (const job of rows.values()) {
				const row = button('', `generate-queue-row status-${job.state}`);
				row.setAttribute('data-job-id', job.job_id);
				row.setAttribute('data-focus-key', `${job.job_id}:select`);
				focusTargets.push(row);
				row.addEventListener('click', () => { pinned = job.job_id; draw(job); });
				row.append(el('span', '', unit.items.find(item => item.item === job.item && job.unit_id === unit.unit_id)?.label ?? job.item),
					el('span', 'generate-item-status', STATUS[job.state]));
				queueList.append(row);
			}
			if (!rows.size) queueList.append(el('p', 'generation-message', '目前沒有排隊的工作。'));
			failures.replaceChildren();
			for (const job of [...watched.values()].filter(job => job?.state === 'failed')) {
				const panel = el('section', 'generate-failure');
				panel.setAttribute('role', 'alert');
				const reason = job.error?.reason ?? '這次工作沒有完成。';
				const planningContract = job.current === 'storyboard' && /簡報欄位不符合契約/.test(reason) && /run_teaching_plan\.py/.test(reason);
				panel.append(el('h3', '', unit.items.find(item => item.item === job.item)?.label ?? job.item),
					el('p', '', planningContract ? '教學規劃的回傳格式不符，尚未進入影片配音與出片。' : reason),
					el('p', 'section-note', job.error?.advice ?? ''));
				if (job.error?.code === 'key_points_review') panel.append(el('p', 'section-note', '請先在頁面上方檢查並確認重點清單，再重新生成。'));
				if (planningContract) {
					const detail = el('details', 'generate-error-detail');
					detail.append(el('summary', '', '查看錯誤紀錄'), el('pre', '', reason));
					panel.append(detail);
				}
				const inspect = button('查看失敗步驟');
				inspect.setAttribute('data-focus-key', `${job.job_id}:inspect`);
				focusTargets.push(inspect);
				inspect.addEventListener('click', () => { pinned = job.job_id; draw(job); diagram.scrollIntoView?.({ block: 'nearest' }); });
				panel.append(inspect);
				if (job.error?.retry) {
					const retry = button('重試');
					retry.setAttribute('data-focus-key', `${job.job_id}:retry`);
					focusTargets.push(retry);
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
			if (focusedKey) (focusTargets.find(node => node.getAttribute('data-focus-key') === focusedKey) ?? selectionToggle).focus();
		}
		const focus = pinned ? watched.get(pinned) : queue.running ?? watched.get(query.job)
			?? [...watched.values()].find(job => job?.state === 'failed') ?? [...watched.values()].filter(Boolean).at(-1);
		draw(focus);
		status.textContent = queue.running || queue.queued.length ? '工作會依序製作，你可以切到其他頁。'
			: [...watched.values()].some(job => job?.state === 'failed') ? '製作失敗，請查看下方原因；重試只會製作該項目。'
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
			if (!reviewLoaded) { reviewLoaded = true; await loadKeyPoints(); if (disposed || document.hidden) return; }
			for (const job of [queue.running, ...queue.queued].filter(Boolean)) {
				if (job.unit_id === unit.unit_id || job === queue.running) watched.set(job.job_id, job);
			}
			const ids = [...watched].filter(([, job]) => !job || ['queued', 'running'].includes(job.state)).map(([id]) => id);
			const results = await Promise.all(ids.map(async id => {
				try { return { id, job: await api.get(`/jobs/${encodeURIComponent(id)}`) }; }
				catch (error) { return { id, error }; }
			}));
			if (disposed || document.hidden) return;
			const errors = [];
			for (const { id, job, error } of results) {
				if (job) watched.set(id, job);
				else if (error.status === 404 || error.code === 'job_not_found') {
					watched.delete(id);
					if (pinned === id) pinned = null;
				} else errors.push(error.reason ?? error.message);
			}
			if (queue.running) queue.running = watched.get(queue.running.job_id) ?? queue.running;
			renderQueue(queue);
			await refreshUnit();
			if (!disposed && !document.hidden) {
				renderQueue(queue);
				if (errors.length) status.textContent = `部分工作進度暫時讀不到，稍後會再讀取。${errors.join('；')}`;
				if (keyPointsStale) status.textContent += ` ${KEY_POINTS_STALE_NOTE}`;
			}
		} catch (error) {
			if (!disposed) status.textContent = `${error.reason ?? error.message} ${error.advice ?? '稍後會再讀取。'}`;
		} finally { polling = false; schedule(); }
	}
	async function run(action) {
		if (submitting || disposed) return;
		submitting = true;
		let accepted = false;
		renderChecklist();
		try {
			await action();
			accepted = true;
			if (!disposed) { await refreshUnit(); await poll(); }
		} catch (error) {
			if (!disposed && error.code === 'key_points_review') loadKeyPoints();
			if (!disposed) status.textContent = accepted ? `工作已送出，暫時無法讀取最新進度。${error.reason ?? error.message}` : `${error.reason ?? error.message} ${error.advice ?? ''}`;
		} finally { submitting = false; if (!disposed) renderChecklist(); }
	}
	start.addEventListener('click', () => run(async () => {
		const items = unit.items.filter(item => selectable(item) && !blocked(item) && chosen.has(item.item)).map(item => item.item);
		const result = await api.post(`${unitPath}/generate${suffix}`, { items });
		if (disposed) return;
		for (const id of result.job_ids) watched.set(id, null);
		if (result.job_ids.length) {
			unit = { ...unit, items: unit.items.map(item => items.includes(item.item) ? { ...item, status: 'queued' } : item) };
			collapseSelection(true);
			selectionToggle.focus();
		}
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
