import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { api } from '../js/api.mjs';
import { withDOM, descendants, settle, click } from './dom-helper.mjs';

const fixture = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));
const find = (page, predicate) => descendants(page).find(predicate);
const named = (page, text) => find(page, node => node.tagName === 'button' && node.textContent === text);

async function withLibrary(units, run) {
	await withDOM(async doc => {
		const previous = { get: api.get, post: api.post };
		api.get = async path => { assert.equal(path, '/units'); return units; };
		const { renderLibrary } = await import('../js/pages/library.mjs');
		let page;
		try {
			page = await renderLibrary();
			page.mount?.();
			await run(page, doc);
		} finally { page?.dispose?.(); Object.assign(api, previous); }
	});
}

test('素材庫每頁六張，顯示點數、成品與花費，卡片連到指定單元成品', async () => {
	const sample = (await fixture('units'))[0];
	const units = Array.from({ length: 7 }, (_, i) => ({ ...sample, unit_id: `unit-${i}`, title: `教材 ${i}` }));
	await withLibrary(units, async page => {
		const cards = () => descendants(page).filter(node => node.getAttribute('data-unit-id'));
		assert.equal(cards().length, 6);
		assert.equal(cards()[0].href, '#/make/4?unit=unit-0');
		assert.match(cards()[0].textContent, /5 個重點.*3 支影片.*重點片.*心智圖.*簡報.*US\$0\.287/);
		assert.equal(named(page, '上一頁').disabled, true);
		click(named(page, '下一頁'));
		assert.equal(cards().length, 1);
		assert.equal(cards()[0].href, '#/make/4?unit=unit-6');
		assert.equal(named(page, '下一頁').disabled, true);
		click(named(page, '上一頁'));
		assert.equal(cards().length, 6);
	});
});

test('學生提問用選定單元送出，影片使用共用播放器且換教材或離頁會停止', async () => {
	const sample = (await fixture('units'))[0];
	const story = await fixture('ask-story');
	await withLibrary([sample, { ...sample, unit_id: 'other' }], async page => {
		const posts = [];
		api.post = async (path, body) => { posts.push({ path, body }); return structuredClone(story); };
		const question = find(page, node => node.tagName === 'textarea');
		question.value = '迴圈為什麼多跑一次？';
		find(page, node => node.tagName === 'form').dispatchEvent(new Event('submit', { cancelable: true }));
		await settle();
		assert.deepEqual(posts, [{ path: '/ask', body: { unit_id: sample.unit_id, question: question.value } }]);
		let video = find(page, node => node.tagName === 'video');
		assert.equal(video.src, `/media/${sample.unit_id}/q2/video.mp4`);
		assert.equal(video.controls, true);
		const select = find(page, node => node.tagName === 'select');
		select.value = 'other';
		select.dispatchEvent(new Event('change'));
		assert.equal(video.paused, true);
		assert.equal(find(page, node => node.tagName === 'video'), undefined);
		api.post = async () => ({ ...story, video: '/media/other/q2/video.mp4' });
		find(page, node => node.tagName === 'form').dispatchEvent(new Event('submit'));
		await settle();
		video = find(page, node => node.tagName === 'video');
		assert.equal(video.src, '/media/other/q2/video.mp4');
		page.dispose();
		assert.equal(video.paused, true);
	});
});

test('超出範圍顯示鎖與固定文案，no_match 顯示找不到段落', async () => {
	const scope = await fixture('ask-out-of-scope');
	await withLibrary(await fixture('units'), async page => {
		const question = find(page, node => node.tagName === 'textarea');
		const form = find(page, node => node.tagName === 'form');
		question.value = '遞迴怎麼寫？';
		api.post = async () => structuredClone(scope);
		form.dispatchEvent(new Event('submit'));
		await settle();
		assert.match(page.textContent, /這份教材沒有教這個/);
		assert.ok(find(page, node => node.getAttribute('data-icon') === 'lock'));
		assert.equal(named(page, '生成這段'), undefined);
		api.post = async () => ({ kind: 'no_match', story: null, video: null });
		form.dispatchEvent(new Event('submit'));
		await settle();
		assert.match(page.textContent, /找不到對應的段落/);
	});
});

test('尚未生成的段落只送選定 story，失敗可重試，成功才跳③', async () => {
	const sample = (await fixture('units'))[0];
	await withLibrary([sample], async page => {
		api.post = async () => ({ kind: 'story', story: 'q5', video: null });
		find(page, node => node.tagName === 'textarea').value = '尚未生成';
		find(page, node => node.tagName === 'form').dispatchEvent(new Event('submit'));
		await settle();
		const generate = named(page, '生成這段');
		api.post = async () => { throw { reason: '暫時忙碌', advice: '稍後重試' }; };
		click(generate);
		await settle();
		assert.match(page.textContent, /暫時忙碌.*稍後重試/);
		assert.equal(generate.disabled, false);
		assert.equal(globalThis.location.hash, '');
		const posts = [];
		api.post = async (path, body) => { posts.push({ path, body }); return { job_ids: ['job-q5'] }; };
		click(generate);
		await settle();
		assert.deepEqual(posts, [{ path: `/units/${sample.unit_id}/generate`, body: { items: ['q5'] } }]);
		assert.equal(globalThis.location.hash, `#/make/3?unit=${sample.unit_id}`);
	});
});

test('空素材庫不能提問；舊提問回覆在換教材或離頁後不再出現', async () => {
	await withLibrary([], async page => {
		assert.match(page.textContent, /還沒有教材/);
		assert.equal(named(page, '找段落').disabled, true);
	});
	const sample = (await fixture('units'))[0];
	await withLibrary([sample, { ...sample, unit_id: 'other' }], async page => {
		let resolve;
		api.post = () => new Promise(done => { resolve = done; });
		const form = find(page, node => node.tagName === 'form');
		find(page, node => node.tagName === 'textarea').value = '問題';
		form.dispatchEvent(new Event('submit'));
		const select = find(page, node => node.tagName === 'select');
		select.value = 'other';
		select.dispatchEvent(new Event('change'));
		resolve(await fixture('ask-story'));
		await settle();
		assert.equal(find(page, node => node.tagName === 'video'), undefined);
		form.dispatchEvent(new Event('submit'));
		page.dispose();
		resolve(await fixture('ask-story'));
		await settle();
		assert.equal(find(page, node => node.tagName === 'video'), undefined);
	});
});

test('匹配結果提供教材名稱、對應重點與狀態，教材詳情失敗仍保留可觀看結果', async () => {
 const sample = (await fixture('units'))[0];
 const unit = await fixture('unit-analyzed');
 const story = await fixture('ask-story');
 await withLibrary([sample], async page => {
  api.get = async path => { assert.equal(path, `/units/${sample.unit_id}`); return unit; };
  api.post = async () => structuredClone(story);
  find(page, node => node.tagName === 'textarea').value = '多跑一次？';
  find(page, node => node.tagName === 'form').dispatchEvent(new Event('submit'));
  await settle();
  const result = find(page, node => node.getAttribute('aria-label') === '提問結果');
  assert.match(result.textContent, /對應教材/);
  assert.match(result.textContent, /多跑一次的原因/);
  assert.match(result.textContent, /可直接觀看/);
  assert.ok(find(result, node => node.tagName === 'a' && node.textContent === '查看教材重點'));
  api.get = async () => { throw new Error('offline'); };
  find(page, node => node.tagName === 'form').dispatchEvent(new Event('submit'));
  await settle();
  assert.ok(find(page, node => node.tagName === 'video'));
 });
});

test('問答的教材詳情晚回來時，不覆蓋使用者正在輸入的新問題', async () => {
 const sample = (await fixture('units'))[0];
 const unit = await fixture('unit-analyzed');
 const story = await fixture('ask-story');
 await withLibrary([sample], async page => {
  let release;
  api.get = () => new Promise(resolve => { release = () => resolve(unit); });
  api.post = async () => structuredClone(story);
  const question = find(page, node => node.tagName === 'textarea');
  question.value = '多跑一次？';
  find(page, node => node.tagName === 'form').dispatchEvent(new Event('submit'));
  await settle();
  question.value = '改問下一題'; question.dispatchEvent(new Event('input'));
  release(); await settle();
  assert.equal(find(page, node => node.tagName === 'video'), undefined);
  assert.doesNotMatch(find(page, node => node.getAttribute('aria-label') === '提問結果').textContent, /多跑一次的原因/);
  assert.equal(named(page, '找段落').disabled, false);
 });
});
