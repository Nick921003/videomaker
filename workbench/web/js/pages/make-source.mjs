import { api } from '../api.mjs';
import { el, money } from '../ui.mjs';
import { go } from '../router.mjs';
import { layoutSteps, render, setLive } from '../diagram.mjs';
import { attach } from '../panzoom.mjs';

export function paginateUnits(units, page = 0) {
	const pages = Math.max(1, Math.ceil(units.length / 6));
	page = Math.min(pages - 1, Math.max(0, Math.trunc(page) || 0));
	return { items: units.slice(page * 6, page * 6 + 6), page, pages };
}

export const ACCEPTED_KINDS = ['md', 'txt', 'pdf', 'pptx', 'docx', 'xlsx', 'csv', 'png', 'jpg', 'jpeg'];

export function sourceKind(name) {
	const extension = String(name).match(/\.([^.]+)$/)?.[1].toLowerCase();
	return ACCEPTED_KINDS.includes(extension) ? extension : null;
}

export function decodeUtf8(buffer) {
	try { return new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(buffer); }
	catch { throw new Error('文字編碼讀不到，請另存 UTF-8 後重新加入。'); }
}

function button(label, className = '') {
	const node = el('button', `button ${className}`.trim(), label);
	node.type = 'button';
	return node;
}

export async function renderMakeSource({ unit, query = {}, notice = '', onUnit }) {
	const [registry, library] = await Promise.all([api.get('/formats'), api.get('/units')]);
	const content = el('section', 'make-source');
	const inputCard = el('section', 'make-card source-input');
	const tabs = el('div', 'source-tabs');
	tabs.setAttribute('aria-label', '教材來源');
	const panels = [];
	const tabButtons = [];
	for (const [i, label] of ['上傳檔案', '貼上文字', '從素材庫挑'].entries()) {
		const tab = button(label, 'source-tab');
		tab.setAttribute('aria-pressed', String(i === 0));
		const panel = el('div', 'source-panel');
		panel.hidden = i !== 0;
		tab.addEventListener('click', () => {
			panels.forEach((node, index) => { node.hidden = index !== i; });
			tabButtons.forEach((node, index) => node.setAttribute('aria-pressed', String(index === i)));
		});
		tabs.append(tab);
		panels.push(panel);
		tabButtons.push(tab);
	}
	inputCard.append(tabs, ...panels);
	const fileLabel = el('label', 'source-file-label', '選一份教材');
	const fileInput = el('input', 'source-file');
	fileInput.type = 'file';
	fileInput.accept = '.md,.txt,.pdf,.pptx,.docx,.xlsx,.csv,.png,.jpg,.jpeg';
	fileLabel.append(fileInput);
	const uploadNote = el('p', 'section-note', 'MD、TXT 直接讀取；PDF、PPTX、DOCX、XLSX、CSV 與圖片先看摘要，再確認整理。');
	const preview = el('div', 'upload-preview scroll-box');
	preview.hidden = true;
	panels[0].append(fileLabel, uploadNote, preview);
	const titleLabel = el('label', 'source-label', '教材名稱（選填）');
	const titleInput = el('input', 'source-text-input');
	titleInput.type = 'text';
	titleInput.placeholder = '例如：迴圈';
	titleLabel.append(titleInput);
	const textLabel = el('label', 'source-label source-paste-label', '教材內容');
	const textarea = el('textarea', 'source-textarea scroll-box');
	textarea.placeholder = '把教材文字或 Markdown 貼在這裡⋯';
	textLabel.append(textarea);
	const save = button('使用這份教材', 'button-primary');
	panels[1].append(titleLabel, textLabel, save);
	const libraryList = el('div', 'source-library scroll-box');
	const pager = el('div', 'source-pager');
	const previous = button('上一頁');
	const next = button('下一頁');
	const pageNumber = el('span', 'section-note');
	pageNumber.setAttribute('role', 'status');
	pager.append(previous, pageNumber, next);
	panels[2].append(libraryList, pager);
	const selectedCard = el('section', 'make-card source-selected');
	const summary = el('div', 'source-summary');
	const analyze = button('開始分析（約 US$0.015）', 'button-primary');
	const review = button('核對教材', 'button-primary');
	review.hidden = true;
	const reviewPanel = el('section', 'source-review make-card');
	reviewPanel.hidden = true;
	const status = el('div', 'source-status scroll-box');
	status.setAttribute('role', 'status');
	status.setAttribute('aria-live', 'polite');
	const progress = el('section', 'source-progress');
	progress.hidden = true;
	const toolbar = el('div', 'source-diagram-controls');
	const minus = button('−');
	minus.setAttribute('aria-label', '縮小流程圖');
	const plus = button('＋');
	plus.setAttribute('aria-label', '放大流程圖');
	const fit = button('符合視窗');
	const fullscreen = button('全螢幕');
	toolbar.append(minus, plus, fit, fullscreen);
	const viewport = el('div', 'pipeline-viewport source-diagram');
	progress.append(toolbar, viewport);
	selectedCard.append(summary, analyze, review, reviewPanel, status, progress);
	content.append(inputCard, selectedCard);
	let selected = unit;
	let selectedQuery = { ...query };
	let disposed = false;
	let mounted = false;
	let busy = false;
	let timer;
	let reader;
	let controls;
	let svg;
	let pageIndex = 0;
	let drawnStage;
	let correctionSource = null;
	const inputs = [fileInput, titleInput, textarea, save, analyze, review, previous, next, ...tabButtons];
	function refresh() {
		summary.replaceChildren(el('p', 'eyebrow', '這次要做的教材'), el('h2', '', selected?.title ?? '先選一份教材'),
			el('p', 'section-note', selected ? selected.normalization_attention ? '先對照原檔核對內容，再開始分析。' : selected.analysis ? `已分析 · ${selected.analysis.points.length} 個問題，可以直接看分析結果。` : '教材準備好了，接著分析學生的問題。' : '上傳、貼上，或挑一份素材庫裡的教材。'));
		analyze.disabled = busy || !selected || Boolean(selected.normalization_attention);
		review.hidden = !selected?.normalization_attention;
		review.disabled = busy || !selected;
		analyze.textContent = selected?.analysis ? '查看分析結果 →' : '開始分析（約 US$0.015）';
	}
	function setBusy(value) {
		busy = value;
		for (const input of inputs) input.disabled = value;
		for (const card of libraryList.children) card.disabled = value;
		const pagination = paginateUnits(library, pageIndex);
		previous.disabled = value || pagination.page === 0;
		next.disabled = value || pagination.page === pagination.pages - 1;
		content.setAttribute('aria-busy', String(value));
		refresh();
	}
	function announce(text) {
		status.setAttribute('role', 'status');
		status.replaceChildren(el('p', '', text));
	}
	function clearJob() {
		delete selectedQuery.job;
		globalThis.history?.replaceState(null, '', goHash(1, selectedQuery));
	}
	function goHash(step, params) {
		const search = new URLSearchParams(params).toString();
		return `#/make/${step}${search ? `?${search}` : ''}`;
	}
	function showError(error, retryAction) {
		setBusy(false);
		status.setAttribute('role', 'alert');
		status.replaceChildren(el('p', '', error.reason ?? error.message ?? '教材暫時讀不到。'));
		if (error.advice) status.append(el('p', 'section-note', error.advice));
		if (retryAction) {
			const retry = button('重試');
			retry.addEventListener('click', () => run(retryAction));
			status.append(retry);
		}
	}
	async function run(action) {
		if (disposed || busy) return;
		setBusy(true);
		try { await action(); }
		catch (error) { if (!disposed) showError(error); }
		finally { if (!disposed && !selectedQuery.job) setBusy(false); }
	}
	async function choose(id, preserveState = false) {
		const suffix = preserveState && api.MOCK && selectedQuery.state ? `?${new URLSearchParams({ state: selectedQuery.state })}` : '';
		const nextUnit = await api.get(`/units/${encodeURIComponent(id)}${suffix}`);
		if (disposed) return;
		selected = nextUnit;
		reviewPanel.hidden = true;
		selectedQuery = onUnit(nextUnit, { preserveState });
		progress.hidden = true;
		refresh();
		announce('教材準備好了。');
	}
	async function saveMarkdown(markdown, title, kind = null) {
		if (!markdown.trim()) throw new Error('先放入教材文字。');
		announce('正在讀取教材⋯');
		const result = await api.post('/units', { markdown, ...(!kind && correctionSource ? { source_ref: correctionSource } : {}), ...(kind ? { source_kind: kind } : {}), ...(title.trim() ? { title: title.trim() } : {}) });
		if (!disposed) { await choose(result.unit_id); correctionSource = null; }
	}
	function mountDiagram() {
		if (!mounted || !svg || controls) return;
		controls = attach(svg, { fullscreenElement: progress });
		controls.fit();
	}
	function draw(stageId) {
		progress.hidden = false;
		if (drawnStage === stageId) return;
		const stage = registry.stages.find(entry => entry.id === stageId);
		if (!stage) throw new Error('這個教材流程暫時讀不到，請稍後重試。');
		const nodes = layoutSteps(stage.steps);
		svg = render(viewport, { nodes, edges: nodes.slice(1).map((node, i) => ({ from: nodes[i].id, to: node.id })) }, { mode: 'live' });
		mountDiagram();
		controls?.fit();
		drawnStage = stageId;
	}
	async function pollJob(jobId) {
		setBusy(true);
		try {
			const job = await api.get(`/jobs/${encodeURIComponent(jobId)}`);
			if (disposed) return;
			draw(job.format);
			setLive(viewport, job.steps);
			if (job.state === 'failed') {
				clearJob();
				showError(job.error ?? new Error('這次工作沒有完成。'), job.error?.retry ? async () => {
					const result = await api.post(`/jobs/${encodeURIComponent(job.job_id)}/retry`);
					if (!disposed) await watch(result.job_id);
				} : null);
				return;
			}
			if (job.state === 'done') {
				clearJob();
				if (!job.unit_id) throw new Error('整理已結束，但還沒有教材資料，請重新上傳。');
				await choose(job.unit_id);
				if (disposed) return;
				setBusy(false);
				if (job.format === 'analysis') {
					if (!selected.analysis?.points.length) throw new Error('分析結果還沒讀進來，請稍後再試。');
					go('make', 2, selectedQuery);
				} else announce('整理完成，可以開始分析了。');
				return;
			}
			const step = registry.stages.find(stage => stage.id === job.format)?.steps.find(entry => entry.id === job.current);
			announce(job.state === 'queued' ? '正在排隊，輪到這份教材就開始。' : `${job.format === 'ingest' ? '整理' : '分析'}中 · ${step?.name ?? '正在處理'}⋯`);
			timer = setTimeout(() => pollJob(jobId), 2000);
		} catch (error) {
			if (!disposed) showError(error, () => pollJob(jobId));
		}
	}
	async function watch(jobId) {
		if (!jobId) throw new Error('工作還沒建立，請稍後再試。');
		selectedQuery.job = jobId;
		globalThis.history?.replaceState(null, '', goHash(1, selectedQuery));
		await pollJob(jobId);
	}
	function renderLibrary() {
		const pagination = paginateUnits(library, pageIndex);
		pageIndex = pagination.page;
		libraryList.replaceChildren();
		for (const entry of pagination.items) {
			const card = button('', 'source-unit');
			card.append(el('strong', '', entry.title), el('span', 'section-note', entry.analyzed ? `已分析 · ${entry.points} 個問題` : '尚未分析'));
			card.addEventListener('click', () => run(() => choose(entry.unit_id)));
			libraryList.append(card);
		}
		if (!pagination.items.length) libraryList.append(el('p', 'section-note', '素材庫還沒有教材，先上傳或貼上文字。'));
		pageNumber.textContent = `${pageIndex + 1} / ${pagination.pages}`;
		setBusy(busy);
	}
	previous.addEventListener('click', () => { pageIndex--; renderLibrary(); });
	next.addEventListener('click', () => { pageIndex++; renderLibrary(); });
	save.addEventListener('click', () => run(() => saveMarkdown(textarea.value, titleInput.value)));
	fileInput.addEventListener('change', () => run(async () => {
		const file = fileInput.files?.[0];
		if (!file) return;
		preview.hidden = true;
		const kind = sourceKind(file.name);
		if (!kind) throw new Error('請選 PDF、PPTX、DOCX、XLSX、CSV、MD、TXT、PNG 或 JPEG 教材。');
		if (file.size > 5 * 1024 * 1024) throw Object.assign(new Error('檔案超過 5 MB。'), { advice: '拆小再上傳。' });
		if (kind === 'md' || kind === 'txt') {
			const markdown = typeof file.arrayBuffer === 'function'
				? decodeUtf8(await file.arrayBuffer())
				: await new Promise((resolve, reject) => {
				reader = new FileReader();
				reader.onload = () => resolve(String(reader.result));
				reader.onerror = () => reject(new Error('檔案讀不到，請重新選取。'));
				reader.onabort = () => reject(new Error('檔案讀取已取消。'));
				reader.readAsText(file);
			});
			if (!disposed) await saveMarkdown(markdown, file.name.replace(/\.[^.]+$/, ''), kind);
		} else {
			announce('正在抽取文字，先看看教材摘要⋯');
			const body = new FormData();
			body.append('file', file);
			const upload = await api.post('/uploads', body);
			if (disposed) return;
			preview.hidden = false;
			const confirm = button(`確認整理（約 ${money(upload.estimate_usd)}）`, 'button-primary');
			preview.replaceChildren(el('h3', '', file.name), el('p', 'section-note', `${upload.pages} 頁 · ${upload.chars.toLocaleString()} 字`),
				el('p', 'upload-excerpt', upload.excerpt), el('p', 'section-note', '確認後才會呼叫模型，費用依實際用量計算。'), confirm);
			confirm.addEventListener('click', () => run(async () => {
				confirm.disabled = true;
				try {
					const result = await api.post(`/uploads/${encodeURIComponent(upload.upload_id)}/normalize`);
					if (!disposed) await watch(result.job_id);
				} finally { confirm.disabled = false; }
			}));
			announce('摘要準備好了，確認整理後才會建立教材。');
		}
	}));
	review.addEventListener('click', () => run(async () => {
		const uid = selected.unit_id;
		const material = await api.get(`/units/${encodeURIComponent(uid)}/material`);
		if (disposed || selected?.unit_id !== uid) return;
		reviewPanel.hidden = false;
		const draft = el('textarea', 'source-textarea');
		draft.value = material.markdown;
		draft.readOnly = true;
		draft.setAttribute('aria-label', '待核對教材內容');
		const sources = el('div', 'source-review-files');
		for (const source of material.sources) {
			const link = el('a', 'button', `原檔 · ${source.name ?? source.kind.toUpperCase()}`);
			link.href = `/media/${encodeURIComponent(uid)}/${source.path.split('/').map(encodeURIComponent).join('/')}`;
			link.target = '_blank';
			link.rel = 'noopener';
			sources.append(link);
		}
		const label = el('label', 'source-review-confirm');
		const checked = el('input');
		checked.type = 'checkbox';
		label.append(checked, el('span', '', '已對照原檔確認內容'));
		const confirm = button('確認並繼續', 'button-primary');
		confirm.disabled = true;
		checked.addEventListener('change', () => { confirm.disabled = !checked.checked; });
		confirm.addEventListener('click', () => run(async () => {
			if (!checked.checked || selected?.unit_id !== uid) return;
			confirm.disabled = true;
			try {
				await api.post(`/units/${encodeURIComponent(uid)}/review`, { confirmed: true, content_version: material.content_version });
				if (disposed) return;
				reviewPanel.hidden = true;
				await choose(uid);
				announce('核對已保存，可以開始分析。');
			} finally { confirm.disabled = !checked.checked; }
		}));
		const correct = button('修改內容');
		correct.addEventListener('click', () => {
			textarea.value = material.markdown;
			correctionSource = { unit_id: uid, content_version: material.content_version };
			titleInput.value = selected.title;
			tabButtons[1].dispatchEvent(new Event('click'));
			textarea.focus();
		});
		reviewPanel.replaceChildren(el('h3', '', '核對教材'), sources, draft, label, confirm, correct);
	}));
	analyze.addEventListener('click', () => run(async () => {
		if (selected.analysis) { go('make', 2, selectedQuery); return; }
		const suffix = api.MOCK && selectedQuery.state ? `?${new URLSearchParams({ state: selectedQuery.state })}` : '';
		const result = await api.post(`/units/${encodeURIComponent(selected.unit_id)}/analyze${suffix}`);
		if (disposed) return;
		if (result.analyzed) {
			await choose(selected.unit_id);
			if (!disposed) go('make', 2, selectedQuery);
		} else await watch(result.job_id);
	}));
	minus.addEventListener('click', () => controls?.zoomOut());
	plus.addEventListener('click', () => controls?.zoomIn());
	fit.addEventListener('click', () => controls?.fit());
	fullscreen.addEventListener('click', async () => {
		try { await controls?.fullscreen(); }
		catch { if (!disposed) announce('瀏覽器目前無法開啟全螢幕。'); }
	});
	renderLibrary();
	refresh();
	if (notice) announce(notice);
	content.mount = () => {
		if (disposed || mounted) return;
		mounted = true;
		mountDiagram();
		if (query.job) pollJob(query.job);
	};
	content.dispose = () => {
		disposed = true;
		clearTimeout(timer);
		if (reader?.readyState === 1) reader.abort();
		controls?.destroy();
	};
	return content;
}
