import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { api } from '../js/api.mjs';
import { withDOM, descendants, click, settle } from './dom-helper.mjs';

const fixture = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));
const find = (host, label) => descendants(host).find(node => node.tagName === 'button' && node.textContent === label);

const keyPoints = (status = 'needs_review', digest = 'digest-1') => ({
	unit_id: 'u1', status, structure: status === 'missing' ? null : 'inferred', content_version: 'cv-1', digest,
	key_points: status === 'missing' ? null : {
		objectives: [{ id: 'o1', text: '寫出迴圈', inferred: true, sources: [] }, { id: 'o2', text: '避開差一錯誤', inferred: false, sources: [] }],
		points: [
			{ id: 'p1', title: '迴圈三要素', question: '分號隔成三段為什麼？', type: 'concept', objectives: ['o1'] },
			{ id: 'p2', title: '差一錯誤', question: '為什麼是小於等於？', type: 'mistake', objectives: [] },
		],
	},
});

// 建立頁面並回傳可控的 api 替身；current 決定 GET 回傳的重點清單狀態，failKeyPoints 指定前幾次重點清單 GET 會失敗。
async function setup(initial, { failKeyPoints = 0 } = {}) {
	const { renderMakeGenerate } = await import('../js/pages/make-generate.mjs');
	const unit = await fixture('unit-analyzed');
	const registry = await fixture('formats');
	const state = { current: initial, posts: [], gets: [], failKeyPoints };
	const original = { get: api.get, post: api.post };
	const kpPath = `/units/${unit.unit_id}/key-points`;
	api.get = async path => {
		state.gets.push(path);
		if (path === kpPath && state.failKeyPoints > 0) { state.failKeyPoints -= 1; throw new Error('network'); }
		return path === '/formats' ? registry : path === '/queue' ? { running: null, queued: [] }
			: path === kpPath ? structuredClone(state.current) : structuredClone(unit);
	};
	api.post = async (path, body) => {
		state.posts.push({ path, body });
		if (path === kpPath) return structuredClone(state.current);
		return { job_ids: [] };
	};
	const page = await renderMakeGenerate(unit);
	page.mount();
	await settle();
	return { page, state, unit, kpPath, restore() { page.dispose(); Object.assign(api, original); } };
}
const banner = page => descendants(page).find(node => node.className === 'key-point-banner');
const optionFor = (page, value) => descendants(page).find(node => node.tagName === 'input' && node.value === value);

test('needs_review 顯示橫幅，確認送出 GET 取得的 digest，並停用講義與心智圖選項', async () => {
	await withDOM(async () => {
		const ctx = await setup(keyPoints());
		try {
			const node = banner(ctx.page);
			assert.ok(node, '應顯示橫幅');
			assert.match(node.textContent, /這份教材的學習目標是 AI 推論的，請確認/);
			assert.match(node.textContent, /推論/);
			assert.match(node.textContent, /補充/);
			assert.match(node.textContent, /迴圈三要素/);
			assert.match(node.textContent, /concept/);
			for (const item of ['slides', 'mindmap']) {
				assert.equal(optionFor(ctx.page, item).disabled, true);
				assert.equal(optionFor(ctx.page, item).checked, false);
			}
			assert.equal(optionFor(ctx.page, 'q1').disabled, false);
			assert.match(ctx.page.textContent, /需要先確認/);
			ctx.state.current = keyPoints('ready', 'digest-2');
			click(find(ctx.page, '確認'));
			await settle();
			assert.deepEqual(ctx.state.posts, [{ path: ctx.kpPath, body: { action: 'confirm', digest: 'digest-1' } }]);
			assert.equal(banner(ctx.page), undefined, '確認後重新讀取，橫幅消失');
			assert.equal(optionFor(ctx.page, 'slides').disabled, false);
		} finally { ctx.restore(); }
	});
});

test('ready 或 missing 不顯示橫幅，選項不受影響', async () => {
	for (const status of ['ready', 'missing']) {
		await withDOM(async () => {
			const ctx = await setup(keyPoints(status));
			try {
				assert.ok(ctx.state.gets.includes(ctx.kpPath), `${status} 應請求重點清單`);
				assert.equal(banner(ctx.page), undefined, status);
				assert.equal(optionFor(ctx.page, 'slides').disabled, false);
				assert.equal(optionFor(ctx.page, 'mindmap').disabled, false);
			} finally { ctx.restore(); }
		});
	}
});

test('重點清單讀取失敗時顯示暫時提示，下一次輪詢重試並顯示橫幅', async () => {
	await withDOM(async () => {
		const ctx = await setup(keyPoints(), { failKeyPoints: 1 });
		try {
			assert.equal(banner(ctx.page), undefined, '讀取失敗時不顯示橫幅');
			assert.match(ctx.page.textContent, /稍後自動重試/);
			document.dispatchEvent(new Event('visibilitychange'));
			await settle();
			assert.equal(ctx.state.gets.filter(path => path === ctx.kpPath).length, 2, '下一次輪詢應重新讀取');
			assert.ok(banner(ctx.page), '重試成功後顯示橫幅');
			assert.doesNotMatch(ctx.page.textContent, /稍後自動重試/, '讀取成功後清除提示');
		} finally { ctx.restore(); }
	});
});

test('生成被 key_points_review（409）擋下時重新讀取重點清單並顯示橫幅', async () => {
	await withDOM(async () => {
		const ctx = await setup(keyPoints('ready'));
		try {
			assert.equal(banner(ctx.page), undefined);
			ctx.state.current = keyPoints();
			api.post = async (path, body) => {
				ctx.state.posts.push({ path, body });
				throw Object.assign(new Error('x'), { status: 409, code: 'key_points_review', reason: '這份教材的學習目標是 AI 推論的，需要先確認' });
			};
			const before = ctx.state.gets.filter(path => path === ctx.kpPath).length;
			click(find(ctx.page, '開始生成'));
			await settle();
			assert.equal(ctx.state.posts.length, 1);
			assert.match(ctx.state.posts[0].path, /\/generate$/);
			assert.equal(ctx.state.gets.filter(path => path === ctx.kpPath).length, before + 1, '409 後應重新讀取重點清單');
			assert.ok(banner(ctx.page), '重新讀取後顯示橫幅');
		} finally { ctx.restore(); }
	});
});

test('重新抽取送出去除前後空白的備註，超過 200 字在前端擋下', async () => {
	await withDOM(async () => {
		const ctx = await setup(keyPoints());
		try {
			const noteInput = () => descendants(ctx.page).find(node => node.tagName === 'input' && node.className === 'key-point-note');
			const note = noteInput();
			assert.ok(note);
			note.value = 'x'.repeat(201);
			click(find(ctx.page, '重新抽取'));
			await settle();
			assert.deepEqual(ctx.state.posts, []);
			assert.match(banner(ctx.page).textContent, /200/);
			noteInput().value = '  多抽一點重點  ';
			click(find(ctx.page, '重新抽取'));
			await settle();
			assert.deepEqual(ctx.state.posts, [{ path: ctx.kpPath, body: { action: 'reextract', note: '多抽一點重點' } }]);
			assert.ok(banner(ctx.page), '仍是 needs_review 時橫幅保留');
		} finally { ctx.restore(); }
	});
});

test('清單在畫面停留期間被改動時，確認失敗會顯示原因並重新讀取', async () => {
	await withDOM(async () => {
		const ctx = await setup(keyPoints());
		try {
			api.post = async () => { throw Object.assign(new Error('x'), { code: 'key_points_version', reason: '重點清單已改變，請重新讀取' }); };
			ctx.state.current = keyPoints('needs_review', 'digest-9');
			click(find(ctx.page, '確認'));
			await settle();
			assert.match(banner(ctx.page).textContent, /重點清單已改變/);
			api.post = async (path, body) => { ctx.state.posts.push({ path, body }); return ctx.state.current; };
			click(find(ctx.page, '確認'));
			await settle();
			assert.deepEqual(ctx.state.posts.at(-1).body, { action: 'confirm', digest: 'digest-9' });
		} finally { ctx.restore(); }
	});
});

test('key_points_review 失敗的工作不提供重試，並指向橫幅', async () => {
	await withDOM(async () => {
		const { renderMakeGenerate } = await import('../js/pages/make-generate.mjs');
		const unit = await fixture('unit-analyzed');
		const registry = await fixture('formats');
		const job = await fixture('job-failed');
		unit.items[0] = { ...unit.items[0], status: 'failed', job_id: job.job_id };
		job.item = unit.items[0].item; job.unit_id = unit.unit_id;
		job.error = { code: 'key_points_review', reason: '這份教材的學習目標是 AI 推論的，需要先確認', advice: '', retry: false };
		const original = { get: api.get };
		api.get = async path => path === '/formats' ? registry : path === '/queue' ? { running: null, queued: [] }
			: path.startsWith('/jobs/') ? job : path.endsWith('/key-points') ? keyPoints() : unit;
		const page = await renderMakeGenerate(unit);
		try {
			page.mount(); await settle();
			assert.equal(find(page, '重試'), undefined);
			assert.ok(banner(page));
			assert.match(page.textContent, /上方.*確認/);
		} finally { page.dispose(); Object.assign(api, original); }
	});
});
