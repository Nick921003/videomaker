import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// 只替代 DOM，不替代頁面或 API，讓測試走過實際模組接線。
class Element extends EventTarget {
	constructor(tagName) {
		super();
		this.tagName = tagName;
		this.children = [];
		this.attributes = new Map();
		this.className = '';
		this.hidden = false;
		this.classList = { toggle: (name, active) => {
			const names = new Set(this.className.split(' ').filter(Boolean));
			if (active) names.add(name);
			else names.delete(name);
			this.className = [...names].join(' ');
		} };
	}
	set textContent(value) { this.copy = value; this.children = []; }
	get textContent() { return (this.copy ?? '') + this.children.map(node => node.textContent).join(''); }
	append(...nodes) { this.children.push(...nodes); }
	replaceChildren(...nodes) { this.copy = ''; this.children = nodes; }
	setAttribute(key, value) { this.attributes.set(key, String(value)); }
	getAttribute(key) { return this.attributes.get(key) ?? null; }
	removeAttribute(key) { this.attributes.delete(key); }
}

async function withApp(run) {
	const previous = { document: globalThis.document, location: globalThis.location, fetch: globalThis.fetch };
	const ids = Object.fromEntries(['page-host', 'rail-queue-dot', 'queue-status', 'brand-mock-badge'].map(id => [id, new Element('div')]));
	const links = ['overview', 'make', 'pipelines', 'library', 'usage', 'roadmap'].map(page => {
		const link = new Element('a');
		link.setAttribute('data-page', page);
		return link;
	});
	globalThis.document = Object.assign(new EventTarget(), {
		readyState: 'loading',
		createElement: tag => new Element(tag),
		createElementNS: (namespace, tag) => Object.assign(new Element(tag), { namespaceURI: namespace }),
		getElementById: id => ids[id],
		querySelectorAll: () => links,
	});
	globalThis.location = { hash: '#/overview', search: '' };
	globalThis.fetch = async path => {
		const file = path === '/api/v1/formats' ? 'formats' : path === '/api/v1/units' ? 'units'
			: path === '/api/v1/queue' ? 'queue-idle' : 'unit-done';
		return { ok: true, json: async () => JSON.parse(await readFile(new URL(`../mock/${file}.json`, import.meta.url), 'utf8')) };
	};
	try {
		const app = await import('../js/app.mjs');
		await run(app, ids, links);
	} finally {
		for (const [key, value] of Object.entries(previous)) {
			if (value === undefined) delete globalThis[key];
			else globalThis[key] = value;
		}
	}
}

function descendants(node) {
	return [node, ...node.children.flatMap(descendants)];
}

test('外框實際載入總覽與路線圖，形式卡片能帶上焦點', async () => {
	await withApp(async (app, ids, links) => {
		assert.equal(typeof app.loadRoute, 'function');
		await app.loadRoute();
		assert.match(ids['page-host'].textContent, /看不懂？換個方式理解。/);
		assert.match(ids['page-host'].textContent, /US\$0\.053/);
		assert.match(ids['page-host'].textContent, /試跑後填入/);
		const cards = descendants(ids['page-host']).filter(node => node.className.includes('format-card'));
		assert.equal(cards.length, 9);
		assert.equal(cards.find(card => card.href.includes('focus=mindmap')).href, '#/pipelines?focus=mindmap');
		assert.equal(links[0].getAttribute('aria-current'), 'page');
		globalThis.location.hash = '#/roadmap';
		await app.loadRoute();
		assert.match(ids['page-host'].textContent, /BridgeAI 平台/);
		assert.match(ids['page-host'].textContent, /BridgeAI Learn 部落格/);
		assert.match(ids['page-host'].textContent, /先用對話與情境拆解學生常見的誤解/);
		assert.equal(links[5].getAttribute('aria-current'), 'page');
		assert.equal(links[0].getAttribute('aria-current'), null);
	});
});

test('素材庫、用量仍為預留頁', async () => {
	await withApp(async (app, ids) => {
		for (const route of ['library', 'usage']) {
			globalThis.location.hash = `#/${route}`;
			await app.loadRoute();
			assert.match(ids['page-host'].textContent, /下一步實作/);
		}
	});
});

test('外框已接上製作③生成與④成品並取代預留頁', async () => {
	await withApp(async (app, ids) => {
		globalThis.location.hash = '#/make/3?unit=ff9e559208c9';
		await app.loadRoute();
		assert.match(ids['page-host'].textContent, /這次要生成哪些？/);
		assert.match(ids['page-host'].textContent, /製作佇列/);
		assert.doesNotMatch(ids['page-host'].textContent, /下一步實作/);
		globalThis.location.hash = '#/make/4?unit=ff9e559208c9';
		await app.loadRoute();
		assert.match(ids['page-host'].textContent, /每點影片.*重點片.*心智圖.*簡報/);
		assert.equal(descendants(ids['page-host']).filter(node => node.tagName === 'video').length, 1);
		assert.doesNotMatch(ids['page-host'].textContent, /下一步實作/);
		globalThis.location.hash = '#/usage';
		await app.loadRoute();
	});
});

test('製作接上教材輸入與分析詳情，未選教材時不能跳過第一步', async () => {
	await withApp(async (app, ids) => {
		globalThis.location.hash = '#/make/1';
		await app.loadRoute();
		assert.match(ids['page-host'].textContent, /從素材庫挑/);
		assert.match(ids['page-host'].textContent, /開始分析（約 US\$0\.015）/);
		globalThis.location.hash = '#/make/2?unit=ff9e559208c9';
		await app.loadRoute();
		const host = ids['page-host'];
		assert.match(host.textContent, /for 迴圈每一圈做了什麼？/);
		assert.match(host.textContent, /必演畫面/);
		assert.match(host.textContent, /建議重點片/);
		const point = descendants(host).find(node => node.getAttribute('data-point-id') === 'q2');
		point.dispatchEvent(new Event('click'));
		assert.match(host.textContent, /並排演出 i < 3 與 i <= 3/);
		const next = descendants(host).find(node => node.textContent === '下一步：選要生成的 →');
		assert.equal(next.href, '#/make/3?unit=ff9e559208c9');
		globalThis.location.hash = '#/make/2';
		await app.loadRoute();
		assert.match(ids['page-host'].textContent, /先選一份教材/);
		assert.doesNotMatch(ids['page-host'].textContent, /必演畫面/);
	});
});

test('整理需確認；工作中鎖住輸入，連續整理仍顯示 live 圖，離頁釋放輪詢', async () => {
	await withApp(async (app, ids) => {
		const { api } = await import('../js/api.mjs');
		const original = { get: api.get, post: api.post, setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout };
		const registry = JSON.parse(await readFile(new URL('../mock/formats.json', import.meta.url), 'utf8'));
		const unit = JSON.parse(await readFile(new URL('../mock/unit-new.json', import.meta.url), 'utf8'));
		const calls = [];
		const timers = new Map();
		let jobNumber = 0;
		let done = false;
		const settle = () => new Promise(resolve => setImmediate(resolve));
		api.get = async path => path === '/formats' ? registry : path === '/units' ? [] : path.startsWith('/units/') ? unit : {
			job_id: `job-${jobNumber}`, unit_id: done ? unit.unit_id : null, format: 'ingest', state: done ? 'done' : 'running',
			steps: [{ id: 'normalize', state: done ? 'done' : 'running' }], current: done ? null : 'normalize',
		};
		api.post = async path => {
			calls.push(path);
			if (path === '/uploads') return { upload_id: 'upload', excerpt: '教材摘要', pages: 2, chars: 100, estimate_usd: 0.01 };
			return { job_id: `job-${++jobNumber}` };
		};
		globalThis.setTimeout = callback => { const id = timers.size + 1; timers.set(id, callback); return id; };
		globalThis.clearTimeout = id => timers.delete(id);
		try {
			globalThis.location.hash = '#/make/1';
			await app.loadRoute();
			const find = predicate => descendants(ids['page-host']).find(predicate);
			const file = find(node => node.tagName === 'input' && node.type === 'file');
			file.files = [new File(['mock'], '教材.pdf', { type: 'application/pdf' })];
			file.dispatchEvent(new Event('change'));
			await settle();
			assert.deepEqual(calls, ['/uploads']);
			assert.match(ids['page-host'].textContent, /教材摘要/);
			const confirm = () => find(node => node.tagName === 'button' && node.textContent.startsWith('確認整理'));
			confirm().dispatchEvent(new Event('click'));
			await settle();
			assert.deepEqual(calls, ['/uploads', '/uploads/upload/normalize']);
			assert.equal(file.disabled, true);
			assert.equal(find(node => node.className === 'source-progress').hidden, false);
			assert.equal(find(node => node.getAttribute('aria-current') === 'step').tagName, 'span');
			done = true;
			const tick = [...timers.values()][0];
			timers.clear();
			await tick();
			await settle();
			assert.equal(file.disabled, false);
			assert.match(ids['page-host'].textContent, /整理完成/);
			done = false;
			file.dispatchEvent(new Event('change'));
			await settle();
			confirm().dispatchEvent(new Event('click'));
			await settle();
			assert.equal(find(node => node.className === 'source-progress').hidden, false);
			assert.equal(timers.size, 1);
			globalThis.location.hash = '#/usage';
			await app.loadRoute();
			assert.equal(timers.size, 0);
			assert.match(ids['page-host'].textContent, /用量/);
		} finally {
			api.get = original.get;
			api.post = original.post;
			globalThis.setTimeout = original.setTimeout;
			globalThis.clearTimeout = original.clearTimeout;
		}
	});
});

test('流程頁接上總圖與 focus 路由，節點側欄讀取登記表，返回後收合步驟', async () => {
	await withApp(async (app, ids) => {
		globalThis.location.hash = '#/pipelines?focus=mindmap';
		await app.loadRoute();
		const host = ids['page-host'];
		assert.doesNotMatch(host.textContent, /下一步實作/);
		assert.match(host.textContent, /概念與關係生成/);
		assert.match(host.textContent, /試跑後填入/);
		const find = id => descendants(host).find(node => node.getAttribute('data-node-id') === id);
		find('mindmap:validate').dispatchEvent(new Event('click'));
		assert.match(host.textContent, /樹狀結構、無循環/);
		assert.match(host.textContent, /免費/);
		const back = descendants(host).find(node => node.tagName === 'button' && node.textContent === '返回全圖');
		back.dispatchEvent(new Event('click'));
		assert.ok(find('ingest'));
		assert.ok(find('analysis'));
		assert.ok(find('comic'));
		assert.equal(find('mindmap:validate'), undefined);
		find('comic').dispatchEvent(new Event('click'));
		assert.match(host.textContent, /先用對話與情境拆解學生常見的誤解/);
		assert.doesNotMatch(host.textContent, /概念與關係生成/);
	});
});

test('未知的 focus 安全回到總圖', async () => {
	await withApp(async (app, ids) => {
		globalThis.location.hash = '#/pipelines?focus=missing';
		await app.loadRoute();
		assert.match(ids['page-host'].textContent, /教材整理/);
		assert.match(ids['page-host'].textContent, /教材分析/);
		assert.match(ids['page-host'].textContent, /素材庫/);
		assert.doesNotMatch(ids['page-host'].textContent, /下一步實作/);
	});
});

test('切頁後較慢的舊請求不會蓋掉目前頁面', async () => {
	await withApp(async (app, ids) => {
		const fetch = globalThis.fetch;
		let release;
		globalThis.fetch = path => path === '/api/v1/formats'
			? new Promise(resolve => { release = () => resolve(fetch(path)); }) : fetch(path);
		const pending = app.loadRoute();
		globalThis.location.hash = '#/usage';
		await app.loadRoute();
		release();
		await pending;
		assert.match(ids['page-host'].textContent, /用量/);
		assert.doesNotMatch(ids['page-host'].textContent, /看不懂？/);
	});
});

test('載入失敗能看到原因與建議，提供重試', async () => {
	await withApp(async (app, ids) => {
		globalThis.fetch = async () => ({ ok: false, status: 503, json: async () => ({
			error: { code: 'unavailable', reason: '暫時連不上', advice: '稍後再試' },
		}) });
		await app.loadRoute();
		assert.match(ids['page-host'].textContent, /暫時連不上/);
		assert.match(ids['page-host'].textContent, /稍後再試/);
		assert.ok(descendants(ids['page-host']).some(node => node.tagName === 'button' && node.textContent === '再試一次'));
	});
});

test('導覽列忙碌圓點同時涵蓋執行與排隊，閒置時隱藏', async () => {
	await withApp(async (app, ids) => {
		for (const [queue, busy] of [
			[{ running: null, queued: [] }, false],
			[{ running: { job_id: 'running' }, queued: [] }, true],
			[{ running: null, queued: [{ job_id: 'queued' }] }, true],
		]) {
			globalThis.fetch = async () => ({ ok: true, json: async () => queue });
			await app.pollQueueDot();
			assert.equal(ids['rail-queue-dot'].hidden, !busy);
		}
	});
});
