import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { api } from '../js/api.mjs';
import { withDOM, descendants, settle, click } from './dom-helper.mjs';

const fixture = async () => JSON.parse(await readFile(new URL('../mock/usage.json', import.meta.url), 'utf8'));
const idle = { running: null, queued: [] };
const active = { running: { job_id: 'running' }, queued: [] };
const find = (page, predicate) => descendants(page).find(predicate);

test('未回報金額顯示未知與已知小計，不顯示為免費', async () => {
	const data = await fixture();
	data.totals.unknown_calls = 1;
	data.totals.unknown_today = 1;
	data.units[0].unknown_calls = 1;
	data.units[0].items[0].unknown_calls = 1;
	data.units[0].items[0].calls[0].cost_unknown = true;
	await withUsage(data, async ({ page }) => {
		assert.match(page.textContent, /已知小計，另有 1 筆金額未知/);
		const unknownCells = descendants(page).filter(node => node.tagName === 'td' && node.textContent === '未知');
		assert.equal(unknownCells.length, 1);
	});
});

async function withUsage(data, run) {
	await withDOM(async doc => {
		const original = { get: api.get, setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout };
		const requests = [];
		const timers = new Map();
		let serial = 0;
		let queue = idle;
		api.get = async path => { requests.push(path); return path === '/queue' ? queue : structuredClone(data); };
		globalThis.setTimeout = (callback, delay) => { const id = ++serial; timers.set(id, { callback, delay }); return id; };
		globalThis.clearTimeout = id => timers.delete(id);
		let page;
		try {
			const { renderUsage } = await import('../js/pages/usage.mjs');
			page = await renderUsage();
			await run({ page, doc, requests, timers, setQueue(value) { queue = value; },
				async tick() { const [id, timer] = timers.entries().next().value; timers.delete(id); await timer.callback(); await settle(); } });
		} finally {
			page?.dispose();
			api.get = original.get;
			globalThis.setTimeout = original.setTimeout;
			globalThis.clearTimeout = original.clearTimeout;
		}
	});
}

test('用量顯示真實總計、模型比例、每項花費與呼叫六欄', async () => {
	await withUsage(await fixture(), async ({ page }) => {
		assert.match(page.textContent, /今天.*US\$0\.219.*全部.*US\$0\.287.*依模型/);
		const meters = descendants(page).filter(node => node.tagName === 'meter');
		assert.equal(meters.length, 2);
		assert.equal(meters[0].value, 0.167);
		assert.ok(Math.abs(meters[0].max - 0.287) < 1e-10);
		assert.match(page.textContent, /教材分析.*US\$0\.015/);
		const item = find(page, node => node.tagName === 'details');
		assert.equal(item.open, false);
		assert.match(item.textContent, /時間.*步驟.*模型.*輸入.*輸出.*花費/);
		assert.match(item.textContent, /plan.*google:gemini-3\.8-flash.*2100.*900.*US\$0\.015/);
	});
});

test('用量每頁十個單元，第二頁不重複且展開狀態切頁後保留', async () => {
	const data = await fixture();
	data.units = Array.from({ length: 11 }, (_, i) => ({ ...data.units[0], unit_id: `unit-${i}`, title: `教材 ${i}` }));
	await withUsage(data, async ({ page }) => {
		const units = () => descendants(page).filter(node => node.getAttribute('data-unit-id'));
		assert.equal(units().length, 10);
		const details = find(page, node => node.tagName === 'details');
		details.open = true;
		details.dispatchEvent(new Event('toggle'));
		click(find(page, node => node.tagName === 'button' && node.textContent === '下一頁'));
		assert.equal(units().length, 1);
		assert.equal(units()[0].getAttribute('data-unit-id'), 'unit-10');
		click(find(page, node => node.tagName === 'button' && node.textContent === '上一頁'));
		assert.equal(find(page, node => node.tagName === 'details').open, true);
	});
});

test('只有可見且 queue 忙碌每兩秒更新，背景與離頁停止，完成後只補最後一次', async () => {
	await withUsage(await fixture(), async ({ page, doc, requests, timers, setQueue, tick }) => {
		assert.deepEqual(requests, ['/usage']);
		setQueue(active);
		page.mount();
		await settle();
		assert.equal(timers.size, 1);
		assert.equal([...timers.values()][0].delay, 2000);
		const details = find(page, node => node.tagName === 'details');
		details.open = true;
		details.dispatchEvent(new Event('toggle'));
		await tick();
		assert.equal(requests.filter(path => path === '/usage').length, 3);
		assert.equal(find(page, node => node.tagName === 'details').open, true);
		doc.hidden = true;
		doc.dispatchEvent(new Event('visibilitychange'));
		assert.equal(timers.size, 0);
		const count = requests.length;
		doc.dispatchEvent(new CustomEvent('workbench:queue', { detail: active }));
		await settle();
		assert.equal(requests.length, count);
		doc.hidden = false;
		doc.dispatchEvent(new Event('visibilitychange'));
		await settle();
		assert.equal(timers.size, 1);
		setQueue(idle);
		await tick();
		assert.equal(timers.size, 0);
		const finalCount = requests.length;
		page.dispose();
		doc.dispatchEvent(new CustomEvent('workbench:queue', { detail: active }));
		doc.dispatchEvent(new Event('visibilitychange'));
		await settle();
		assert.equal(requests.length, finalCount);
	});
});

test('閒置不設用量計時器；製作導覽列的 queue 更新會啟動排隊工作的刷新', async () => {
	await withUsage(await fixture(), async ({ page, doc, requests, timers, setQueue }) => {
		page.mount();
		await settle();
		assert.equal(timers.size, 0);
		assert.deepEqual(requests, ['/usage', '/queue']);
		const queued = { running: null, queued: [{ job_id: 'queued' }] };
		setQueue(queued);
		doc.dispatchEvent(new CustomEvent('workbench:queue', { detail: queued }));
		await settle();
		assert.equal(timers.size, 1);
		assert.equal(requests.filter(path => path === '/usage').length, 2);
	});
});

test('背景開啟不發輪詢請求；延遲回覆在離頁後不改畫面或重設計時器', async () => {
	await withUsage(await fixture(), async ({ page, doc, requests, timers }) => {
		doc.hidden = true;
		page.mount();
		await settle();
		assert.deepEqual(requests, ['/usage']);
		let resolve;
		api.get = () => new Promise(done => { resolve = done; });
		doc.hidden = false;
		doc.dispatchEvent(new Event('visibilitychange'));
		page.dispose();
		resolve(active);
		await settle();
		assert.equal(timers.size, 0);
	});
});

test('零用量不造出模型比例或呼叫；刷新失敗保留上次數字並可再讀取', async () => {
	await withUsage({ totals: { today: 0, all: 0, by_model: {} }, units: [] }, async ({ page }) => {
		assert.match(page.textContent, /還沒有用量/);
		assert.equal(find(page, node => node.tagName === 'meter'), undefined);
	});
	await withUsage(await fixture(), async ({ page, timers, tick, setQueue }) => {
		setQueue(active);
		page.mount();
		await settle();
		const originalGet = api.get;
		api.get = async path => { if (path === '/usage') throw { reason: '暫時連不上', advice: '稍後再試' }; return active; };
		await tick();
		assert.match(page.textContent, /暫時連不上.*稍後再試/);
		assert.match(page.textContent, /US\$0\.287/);
		assert.equal(timers.size, 1);
		api.get = originalGet;
		await tick();
		assert.doesNotMatch(page.textContent, /暫時連不上/);
	});
});

test('忙碌刷新保留 summary 焦點，相同資料不重建，呼叫更新後仍可用鍵盤展開', async () => {
	const data = await fixture();
	await withUsage(data, async ({ page, doc, setQueue, tick }) => {
		setQueue(active);
		page.mount();
		await settle();
		const summary = find(page, node => node.tagName === 'summary');
		summary.focus();
		await tick();
		assert.ok(find(page, node => node.tagName === 'summary') === summary, '相同資料保留原節點');
		assert.ok(doc.activeElement === summary, '保留聚焦項目');
		data.units[0].items[0].usd = 0.016;
		await tick();
		assert.ok(doc.activeElement === find(page, node => node.tagName === 'summary'), '資料更新後恢復聚焦項目');
		assert.match(doc.activeElement.textContent, /US\$0\.016/);
	});
});

test('工作結束後最後一筆讀取失敗仍可手動重讀，閒置不重啟自動計時器', async () => {
	await withUsage(await fixture(), async ({ page, timers, requests, setQueue, tick }) => {
		setQueue(active);
		page.mount();
		await settle();
		setQueue(idle);
		const originalGet = api.get;
		api.get = async path => { if (path === '/usage') throw { reason: '暫時連不上' }; return idle; };
		await tick();
		assert.equal(timers.size, 0);
		const retry = find(page, node => node.tagName === 'button' && node.textContent === '再讀取');
		assert.ok(retry);
		assert.equal(retry.hidden, false);
		api.get = originalGet;
		const before = requests.filter(path => path === '/usage').length;
		click(retry);
		await settle();
		assert.equal(requests.filter(path => path === '/usage').length, before + 1);
		assert.equal(timers.size, 0);
		assert.equal(retry.hidden, true);
		assert.doesNotMatch(page.textContent, /暫時連不上/);
	});
});
