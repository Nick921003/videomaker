import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { api } from '../js/api.mjs';
import { withDOM, descendants, settle, click } from './dom-helper.mjs';
import { classifyChatAction, PRIMARY_SAMPLE } from '../js/pages/chat-data.mjs';

const fixture = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));
const find = (page, predicate) => descendants(page).find(predicate);
const all = (page, predicate) => descendants(page).filter(predicate);
const button = (page, text) => find(page, node => node.tagName === 'button' && node.textContent === text);

async function withChat(run, units = null) {
	await withDOM(async () => {
		const previous = { get: api.get, post: api.post };
		api.get = async path => {
			assert.equal(path, '/units');
			return units ?? fixture('units');
		};
		const { renderChat } = await import('../js/pages/chat.mjs');
		let page;
		try {
			page = await renderChat();
			page.mount?.();
			await run(page);
		} finally {
			page?.dispose?.();
			Object.assign(api, previous);
		}
	});
}

test('保守分類只對明確播放指令與風格需求採取本機動作', () => {
	assert.deepEqual(classifyChatAction('回到條件那一段'), { kind: 'seek', chapter: 'trace', time: 18.3 });
	assert.deepEqual(classifyChatAction('請重播這支影片'), { kind: 'replay', time: 0 });
	assert.deepEqual(classifyChatAction('我想要另一種風格的同主題版本'), { kind: 'reinforce' });
	assert.deepEqual(classifyChatAction('為什麼條件會多判斷一次？'), { kind: 'ask' });
});

test('初始即顯示既有 48 秒影片，定位、重播與 ended 提示不假裝生成', async () => {
	await withChat(async page => {
		const video = find(page, node => node.tagName === 'video');
		assert.equal(video.src, PRIMARY_SAMPLE.src);
		assert.equal(video.controls, true);
		assert.match(page.textContent, /48 秒.*現有樣片/);
		assert.doesNotMatch(page.textContent, /正在生成|生成完成/);

		click(button(page, '回到條件'));
		assert.equal(video.currentTime, 18.3);
		video.currentTime = 31;
		click(button(page, '重播'));
		assert.equal(video.currentTime, 0);

		video.dispatchEvent(new Event('ended'));
		video.dispatchEvent(new Event('ended'));
		assert.equal(all(page, node => /看完了。你可以問我/.test(node.copy ?? '')).length, 1);
	});
});

test('提問送出選定教材；空白、重複送出與晚回覆都有邊界', async () => {
	await withChat(async page => {
		const posts = [];
		let resolve;
		api.post = (path, body) => new Promise(done => { posts.push({ path, body }); resolve = done; });
		const form = find(page, node => node.tagName === 'form');
		const input = find(page, node => node.tagName === 'textarea');
		const send = button(page, '送出');
		input.value = '   ';
		form.dispatchEvent(new Event('submit', { cancelable: true }));
		assert.equal(posts.length, 0);

		input.value = '這段為什麼多跑一次？';
		form.dispatchEvent(new Event('submit', { cancelable: true }));
		form.dispatchEvent(new Event('submit', { cancelable: true }));
		assert.equal(posts.length, 1);
		assert.deepEqual(posts[0], {
			path: '/ask',
			body: { unit_id: 'ff9e559208c9', question: '這段為什麼多跑一次？' },
		});
		assert.equal(send.disabled, true);
		page.dispose();
		resolve(await fixture('ask-story'));
		await settle();
		assert.doesNotMatch(page.textContent, /找到教材中的對應段落/);
	});
});

test('風格需求只記錄補強；API 失敗可重試，no_match 只追問定位問題', async () => {
	await withChat(async page => {
		const form = find(page, node => node.tagName === 'form');
		const input = find(page, node => node.tagName === 'textarea');
		let calls = 0;
		api.post = async () => { calls += 1; throw { reason: '暫時連不上', advice: '稍後再試' }; };

		input.value = '請做成另一種風格';
		form.dispatchEvent(new Event('submit', { cancelable: true }));
		await settle();
		assert.equal(calls, 0);
		assert.match(page.textContent, /已記錄補強需求.*尚未開始生成/);

		input.value = '解釋這一段';
		form.dispatchEvent(new Event('submit', { cancelable: true }));
		await settle();
		assert.match(page.textContent, /暫時連不上.*稍後再試/);
		const retry = button(page, '再試一次');
		api.post = async () => ({ kind: 'no_match', story: null, video: null });
		click(retry);
		await settle();
		assert.match(page.textContent, /你想找的是觀念、流程，還是操作次數/);
	});
});
