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

test('四個預留頁與製作每一步都顯示下一步實作', async () => {
	await withApp(async (app, ids) => {
		for (const route of ['make/1', 'make/2', 'make/3', 'make/4', 'pipelines?focus=video', 'library', 'usage']) {
			globalThis.location.hash = `#/${route}`;
			await app.loadRoute();
			assert.match(ids['page-host'].textContent, /下一步實作/);
		}
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
