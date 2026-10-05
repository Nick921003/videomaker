const params = new URLSearchParams(globalThis.location?.search ?? '');
export const MOCK = params.get('mock') === '1';
const BUSY = params.get('busy') === '1';
const UNIT = 'ff9e559208c9';
const files = new Map();
const jobs = new Map();
const units = new Map();
const uploads = new Map();
let serial = 0;

// 所有 mock 檔案都從頁面根目錄讀取，兩種伺服器路徑共用。
const mockFiles = Object.freeze({
	'/formats': 'formats.json',
	'/units': 'units.json',
	'/units/:id': 'unit-done.json',
	'/units/:id?state=new': 'unit-new.json',
	'/units/:id?state=analyzed': 'unit-analyzed.json',
	'/units/:id?state=analyzed12': 'unit-analyzed-12.json',
	'/uploads': 'upload.json',
	'/units/:id/manifest': 'manifest.json',
	'/jobs/:id': 'job-running.json',
	'/jobs/:id?failed': 'job-failed.json',
	'/jobs/:id?queued': 'queue-busy.json',
	'/queue': BUSY ? 'queue-busy.json' : 'queue-idle.json',
	'/usage': 'usage.json',
	'/ask': 'ask-story.json',
	'/ask?out_of_scope': 'ask-out-of-scope.json',
});

function failure(code, reason, advice = '') {
	return Object.assign(new Error(reason), { code, reason, advice });
}

async function readJSON(path, options) {
	const response = await fetch(path, options);
	let data;
	try {
		data = await response.json();
	} catch {
		throw failure('invalid_response', '資料讀不到', '請稍後重新整理。');
	}
	if (!response.ok) {
		const error = data?.error ?? { code: `http_${response.status}`, reason: '連線出了點問題', advice: '請稍後再試。' };
		throw Object.assign(failure(error.code, error.reason, error.advice), error, { status: response.status });
	}
	return data;
}

async function fixture(key) {
	const file = mockFiles[key];
	if (!file) throw failure('mock_not_found', '這個示範資料還沒準備好');
	if (!files.has(file)) files.set(file, readJSON(`mock/${file}`).catch(error => {
		files.delete(file);
		throw error;
	}));
	return structuredClone(await files.get(file));
}

function endpoint(path) {
	const relative = String(path).replace(/^\/api\/v1(?=\/|$)/, '');
	if (!relative.startsWith('/') || relative.startsWith('//') || relative.includes('://')) {
		throw failure('invalid_path', '請使用工作台的資料路徑');
	}
	return new URL(relative, 'http://workbench.local');
}

async function createJob(unitId, item, formatId) {
	const registry = await fixture('/formats');
	const format = [...registry.formats, ...registry.stages].find(entry => entry.id === formatId);
	if (!format?.steps.length) throw failure('unavailable_format', '這個形式還在規劃中');
	const id = `mock-${item}-${++serial}`;
	const now = Date.now();
	const start = Math.max(now, ...[...jobs.values()].map(job => job.end));
	const failAt = item === 'q4' ? format.steps.findIndex(step => step.id === 'repair') : -1;
	const template = await fixture(item === 'q4' ? '/jobs/:id?failed' : '/jobs/:id');
	jobs.set(id, {
		id, unitId, item, format, template, start, failAt,
		end: start + (failAt < 0 ? format.steps.length : failAt) * 2000,
	});
	return id;
}

function progress(job) {
	const elapsed = Date.now() - job.start;
	const index = Math.floor(Math.max(0, elapsed) / 2000);
	const failed = job.failAt >= 0 && index >= job.failAt && elapsed >= 0;
	const done = !failed && index >= job.format.steps.length;
	const currentIndex = failed ? job.failAt : index;
	const state = elapsed < 0 ? 'queued' : failed ? 'failed' : done ? 'done' : 'running';
	return {
		job_id: job.id,
		unit_id: done && job.resultUnit ? job.resultUnit.unit_id : job.unitId,
		item: job.item,
		format: job.format.id,
		state,
		steps: job.format.steps.map((step, i) => ({
			id: step.id,
			state: state === 'queued' ? 'pending' : i < currentIndex ? 'done'
				: i === currentIndex ? (failed ? 'failed' : 'running') : 'pending',
		})),
		current: state === 'queued' || done ? null : job.format.steps[currentIndex].id,
		log: state === 'queued' ? [] : [
			...job.format.steps.slice(0, currentIndex + 1).map(step => `@step ${step.id}`),
			...(failed ? ['@error gemini_busy 503 UNAVAILABLE'] : []),
		].slice(-40),
		spent_usd: failed ? job.template.spent_usd : 0,
		error: failed ? structuredClone(job.template.error) : null,
	};
}

async function settleStages() {
	for (const job of jobs.values()) {
		if (job.applied || progress(job).state !== 'done') continue;
		if (job.format.id === 'ingest') units.set(job.resultUnit.unit_id, job.resultUnit);
		if (job.format.id === 'analysis') {
			const analyzed = await fixture('/units/:id?state=analyzed');
			const original = units.get(job.unitId);
			units.set(job.unitId, { ...analyzed, unit_id: job.unitId, title: original.title, source_ref: original.source_ref,
				analysis: { ...analyzed.analysis, unit_title: original.title } });
		}
		job.applied = true;
	}
}

async function mockGet(url) {
	await settleStages();
	const path = url.pathname;
	if (path === '/units') {
		const summaries = await fixture('/units');
		for (const unit of units.values()) {
			const index = summaries.findIndex(entry => entry.unit_id === unit.unit_id);
			const summary = { unit_id: unit.unit_id, title: unit.title, created_at: new Date().toISOString(),
				analyzed: Boolean(unit.analysis), points: unit.analysis?.points.length ?? 0,
				products: { video: 0, highlight: false, mindmap: false, slides: false }, spent_usd: unit.spent_usd, source_ref: unit.source_ref };
			if (index < 0) summaries.unshift(summary);
			else summaries[index] = summary;
		}
		return summaries;
	}
	if (path === '/queue') {
		const current = [...jobs.values()].map(progress);
		const running = current.find(job => job.state === 'running') ?? null;
		const queued = current.filter(job => job.state === 'queued');
		return running || queued.length ? { running, queued } : fixture('/queue');
	}
	if (Object.hasOwn(mockFiles, path)) return fixture(path);
	if (/^\/units\/[^/]+\/manifest$/.test(path)) return fixture('/units/:id/manifest');
	if (/^\/units\/[^/]+$/.test(path)) {
		const state = url.searchParams.get('state');
		if (['new', 'analyzed', 'analyzed12'].includes(state)) return fixture(`/units/:id?state=${state}`);
		const id = decodeURIComponent(path.split('/')[2]);
		return units.has(id) ? structuredClone(units.get(id)) : fixture('/units/:id');
	}
	const match = path.match(/^\/jobs\/([^/]+)$/);
	if (match) {
		const id = match[1];
		if (jobs.has(id)) return progress(jobs.get(id));
		if (id === 'mock-q4-failed') return fixture('/jobs/:id?failed');
		if (id === 'mock-q3-queued') return (await fixture('/jobs/:id?queued')).queued[0];
		if (id === 'mock-q2-running') {
			const template = await fixture('/jobs/:id');
			await createJob(template.unit_id, template.item, template.format);
			const job = jobs.get(`mock-${template.item}-${serial}`);
			jobs.delete(job.id);
			job.id = id;
			job.start = Date.now() - template.steps.findIndex(step => step.id === template.current) * 2000;
			job.end = job.start + job.format.steps.length * 2000;
			jobs.set(id, job);
			return progress(job);
		}
	}
	throw failure('mock_not_found', '這個示範資料還沒準備好');
}

async function mockPost(url, body) {
	if (url.pathname === '/units') {
		if (typeof body.markdown !== 'string' || !body.markdown.trim()) throw failure('bad_request', '先放入教材文字。');
		const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(body.markdown));
		const unitId = [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('').slice(0, 12);
		if (units.has(unitId)) return { unit_id: unitId, created: false };
		units.set(unitId, { ...await fixture('/units/:id?state=new'), unit_id: unitId,
			title: body.title?.trim() || '未命名教材', source_ref: body.source_ref ?? null });
		return { unit_id: unitId, created: true };
	}
	if (url.pathname === '/uploads') {
		const file = body.get?.('file');
		const kind = file?.name?.split('.').pop().toLowerCase();
		if (!['pdf', 'pptx'].includes(kind)) throw failure('bad_request', '請上傳 PDF 或 PPTX。');
		if (file.size > 5 * 1024 * 1024) throw failure('too_large', '檔案超過 5 MB。', '拆小再上傳。');
		const upload = { ...await fixture('/uploads'), upload_id: `mock-upload-${++serial}`, kind };
		uploads.set(upload.upload_id, { upload, title: file.name.replace(/\.[^.]+$/, '') });
		return upload;
	}
	const normalize = url.pathname.match(/^\/uploads\/([^/]+)\/normalize$/);
	if (normalize) {
		const draft = uploads.get(normalize[1]);
		if (!draft) throw failure('not_found', '找不到這份上傳教材。', '請重新上傳。');
		if (draft.jobId) return { job_id: draft.jobId };
		const jobId = await createJob(null, 'ingest', 'ingest');
		jobs.get(jobId).resultUnit = { ...await fixture('/units/:id?state=new'),
			unit_id: `mock-unit-${++serial}`, title: draft.title, source_ref: null };
		draft.jobId = jobId;
		return { job_id: jobId };
	}
	const analyze = url.pathname.match(/^\/units\/([^/]+)\/analyze$/);
	if (analyze) {
		const unitId = decodeURIComponent(analyze[1]);
		const unit = await mockGet(endpoint(`/units/${analyze[1]}${url.search}`));
		if (unit.analysis) return { job_id: null, analyzed: true };
		const existing = [...jobs.values()].find(job => job.unitId === unitId && job.format.id === 'analysis'
			&& ['queued', 'running'].includes(progress(job).state));
		if (existing) return { job_id: existing.id };
		units.set(unitId, { ...unit, unit_id: unitId });
		return { job_id: await createJob(unitId, 'analysis', 'analysis') };
	}
	const generate = url.pathname.match(/^\/units\/([^/]+)\/generate$/);
	if (generate || url.pathname === '/generate') {
		const unitId = generate?.[1] ?? body.unit_id ?? UNIT;
		const unit = await mockGet(endpoint(`/units/${unitId}${url.search}`));
		if (!Array.isArray(body.items)) throw failure('bad_request', '請先選要生成的教材');
		const requested = [...new Set(body.items ?? [])];
		if (requested.some(itemId => !unit.items.some(item => item.item === itemId))) {
			throw failure('bad_request', '找不到這個教材項目');
		}
		const jobIds = [];
		for (const itemId of requested) {
			const item = unit.items.find(entry => entry.item === itemId);
			const existing = [...jobs.values()].map(progress).some(job => job.unit_id === unitId && job.item === itemId
				&& ['queued', 'running', 'done'].includes(job.state));
			if (item.status !== 'done' && !existing) jobIds.push(await createJob(unitId, itemId, item.format));
		}
		return { job_ids: jobIds };
	}
	const retry = url.pathname.match(/^\/jobs\/([^/]+)\/retry$/);
	if (retry) {
		const job = await mockGet(endpoint(`/jobs/${retry[1]}`));
		if (job.state !== 'failed' || !job.error?.retry) throw failure('bad_request', '這個工作目前不能重試');
		return { job_id: await createJob(job.unit_id, job.item, job.format) };
	}
	if (url.pathname === '/ask') {
		return fixture(body.out_of_scope ? '/ask?out_of_scope' : '/ask');
	}
	throw failure('mock_not_found', '這個示範操作還沒準備好');
}

export const api = {
	MOCK,
	async get(path) {
		const url = endpoint(path);
		return MOCK ? mockGet(url) : readJSON(`/api/v1${url.pathname}${url.search}`);
	},
	async post(path, body = {}) {
		const url = endpoint(path);
		if (MOCK) return mockPost(url, body);
		const multipart = typeof FormData !== 'undefined' && body instanceof FormData;
		return readJSON(`/api/v1${url.pathname}${url.search}`, {
			method: 'POST',
			...(multipart ? {} : { headers: { 'Content-Type': 'application/json' } }),
			body: multipart ? body : JSON.stringify(body),
		});
	},
};
