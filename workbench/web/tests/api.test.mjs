import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

async function withAPI(search, run) {
	const previousLocation = globalThis.location;
	const previousFetch = globalThis.fetch;
	const requests = [];
	globalThis.location = { search };
	globalThis.fetch = async (path, options) => {
		requests.push({ path, options });
		const data = JSON.parse(await readFile(new URL(`../${path}`, import.meta.url), 'utf8'));
		return { ok: true, json: async () => data };
	};
	try {
		const { api } = await import(`../js/api.mjs?test=${Math.random()}`);
		await run(api, requests);
	} finally {
		globalThis.fetch = previousFetch;
		if (previousLocation === undefined) delete globalThis.location;
		else globalThis.location = previousLocation;
	}
}

test('mock 固定映射讀取相對路徑，待機與忙碌佇列分開', async () => {
	await withAPI('?mock=1', async (api, requests) => {
		assert.equal(api.MOCK, true);
		assert.ok((await api.get('/formats')).formats.length > 0);
		assert.equal((await api.get('/api/v1/units'))[0].title, '迴圈');
		assert.deepEqual(await api.get('/queue'), { running: null, queued: [] });
		assert.ok(requests.every(({ path }) => path.startsWith('mock/')));
	});
	await withAPI('?mock=1&busy=1', async (api) => {
		const queue = await api.get('/queue');
		assert.equal(queue.running.state, 'running');
		assert.equal(queue.queued.length, 1);
	});
});

test('不同教材狀態與成品清單使用契約 mock', async () => {
	await withAPI('?mock=1', async (api) => {
		assert.equal((await api.get('/units/ff9e559208c9')).items.filter(item => item.status === 'done').length, 6);
		assert.equal((await api.get('/units/ff9e559208c9?state=new')).analysis, null);
		assert.equal((await api.get('/units/ff9e559208c9?state=analyzed')).analysis.points.length, 5);
		assert.equal((await api.get('/units/ff9e559208c9/manifest')).products.length, 6);
		assert.equal((await api.get('/usage')).totals.all, 0.287);
	});
});

test('busy=1 的佇列固定使用忙碌範例，未生成工作時不會自行變成閒置', async () => {
	await withAPI('?mock=1&busy=1', async (api) => {
		const fixture = JSON.parse(await readFile(new URL('../mock/queue-busy.json', import.meta.url), 'utf8'));
		const previousNow = Date.now;
		let now = 10000;
		Date.now = () => now;
		try {
			assert.deepEqual(await api.get('/queue'), fixture);
			now += 60000;
			assert.deepEqual(await api.get('/queue'), fixture);
		} finally {
			Date.now = previousNow;
		}
	});
});

test('生成略過已完成項目；工作每兩秒前進並依形式結束', async () => {
	await withAPI('?mock=1', async (api) => {
		const previousNow = Date.now;
		let now = 10000;
		Date.now = () => now;
		try {
			const { job_ids } = await api.post('/units/ff9e559208c9/generate', { items: ['q1', 'q5'] });
			assert.equal(job_ids.length, 1);
			let job = await api.get(`/jobs/${job_ids[0]}`);
			assert.equal(job.current, 'selftest');
			now += 1999;
			assert.equal((await api.get(`/jobs/${job_ids[0]}`)).current, 'selftest');
			now += 1;
			job = await api.get(`/jobs/${job_ids[0]}`);
			assert.equal(job.current, 'storyboard');
			assert.equal(job.steps[0].state, 'done');
			now += 10000;
			job = await api.get(`/jobs/${job_ids[0]}`);
			assert.equal(job.state, 'done');
			assert.equal(job.current, null);
			assert.ok(job.steps.every(step => step.state === 'done'));
		} finally {
			Date.now = previousNow;
		}
	});
});

test('q4 在修正步驟失敗，保留 gemini_busy 的原因與重試建議', async () => {
	await withAPI('?mock=1', async (api) => {
		const previousNow = Date.now;
		let now = 10000;
		Date.now = () => now;
		try {
			const { job_ids } = await api.post('/units/ff9e559208c9/generate', { items: ['q4'] });
			now += 6000;
			const job = await api.get(`/jobs/${job_ids[0]}`);
			assert.equal(job.state, 'failed');
			assert.equal(job.current, 'repair');
			assert.equal(job.error.code, 'gemini_busy');
			assert.equal(job.error.retry, true);
			assert.equal(job.steps.find(step => step.id === 'repair').state, 'failed');
			assert.equal(job.steps.find(step => step.id === 'narrate').state, 'pending');
			const retry = await api.post(`/jobs/${job.job_id}/retry`);
			assert.notEqual(retry.job_id, job.job_id);
			assert.equal((await api.get(`/jobs/${retry.job_id}`)).state, 'running');
		} finally {
			Date.now = previousNow;
		}
	});
});

test('正式模式只呼叫 /api/v1 並保留結構化錯誤', async () => {
	await withAPI('?mock=0', async (api, requests) => {
		assert.equal(api.MOCK, false);
		globalThis.fetch = async (path, options) => {
			requests.push({ path, options });
			return { ok: true, json: async () => ({ job_ids: ['real-job'] }) };
		};
		assert.deepEqual(await api.post('/units/u1/generate', { items: ['q1'] }), { job_ids: ['real-job'] });
		assert.equal(requests[0].path, '/api/v1/units/u1/generate');
		assert.deepEqual(JSON.parse(requests[0].options.body), { items: ['q1'] });
		globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({
			error: { code: 'gemini_busy', reason: '暫時忙碌', advice: '稍後重試' },
		}) });
		await assert.rejects(api.get('/queue'), error => error.code === 'gemini_busy' && error.advice === '稍後重試');
	});
});

test('生成的工作出現在佇列，完成或失敗後接著跑下一個', async () => {
	await withAPI('?mock=1', async (api) => {
		const previousNow = Date.now;
		let now = 10000;
		Date.now = () => now;
		try {
			const { job_ids } = await api.post('/units/ff9e559208c9/generate', { items: ['q4', 'q5'] });
			let queue = await api.get('/queue');
			assert.equal(queue.running.job_id, job_ids[0]);
			assert.equal(queue.queued[0].job_id, job_ids[1]);
			now += 6000;
			queue = await api.get('/queue');
			assert.equal(queue.running.job_id, job_ids[1]);
			assert.equal(queue.queued.length, 0);
			now += 12000;
			assert.deepEqual(await api.get('/queue'), { running: null, queued: [] });
		} finally {
			Date.now = previousNow;
		}
	});
});

test('依心智圖與簡報自己的步驟前進，不套用影片步驟', async () => {
	await withAPI('?mock=1', async (api) => {
		const previousNow = Date.now;
		let now = 10000;
		Date.now = () => now;
		try {
			const { job_ids } = await api.post('/units/ff9e559208c9/generate?state=analyzed', { items: ['mindmap', 'slides'] });
			assert.equal(job_ids.length, 2);
			let job = await api.get(`/jobs/${job_ids[0]}`);
			assert.deepEqual(job.steps.map(step => step.id), ['generate', 'validate', 'render']);
			assert.equal(job.current, 'generate');
			now += 2000;
			assert.equal((await api.get(`/jobs/${job_ids[0]}`)).current, 'validate');
			now += 4000;
			job = await api.get(`/jobs/${job_ids[1]}`);
			assert.deepEqual(job.steps.map(step => step.id), ['generate', 'validate', 'export']);
			assert.equal(job.current, 'generate');
			now += 6000;
			assert.equal((await api.get(`/jobs/${job_ids[1]}`)).state, 'done');
		} finally {
			Date.now = previousNow;
		}
	});
});

test('重複送出略過已排隊工作；不能重試正在跑的工作', async () => {
	await withAPI('?mock=1', async (api) => {
		const { job_ids } = await api.post('/units/ff9e559208c9/generate', { items: ['q5'] });
		assert.deepEqual(await api.post('/units/ff9e559208c9/generate', { items: ['q5'] }), { job_ids: [] });
		await assert.rejects(api.post(`/jobs/${job_ids[0]}/retry`));
	});
});
