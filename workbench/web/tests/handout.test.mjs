import test from 'node:test';
import assert from 'node:assert/strict';
import { withDOM, click, descendants } from './dom-helper.mjs';
import { mount } from '../js/viewers/deck.mjs';

const handout = (overrides = {}) => ({
	contract_version: '1.3', title: '迴圈',
	slides: [
		{ slide_id: 'cover', kind: 'cover', title: '迴圈', objectives: ['說明迴圈用途', '寫出 while 迴圈'] },
		{ slide_id: 'p1', kind: 'point', question: '什麼時候該用迴圈？', title: '迴圈用途', explanation: '重複做同一件事就用迴圈。',
			example: { kind: 'code', content: 'while (i < 3) {\n\ti++;\n}', language: 'c' },
			misconceptions: [{ wrong: '迴圈一定要跑滿', why: '條件不成立就會停', correct: '條件決定是否繼續' }],
			sources: ['x'.repeat(80)] },
		{ slide_id: 'p2', kind: 'point', question: '公式怎麼寫？', title: '公式', explanation: '用公式表示。',
			example: { kind: 'formula', content: 'a = b + c', language: '' }, misconceptions: [], sources: [] },
		{ slide_id: 'mistakes', kind: 'mistakes', items: [{ point_title: '迴圈用途', wrong: '錯一', why: '因為一', correct: '對一' }] },
	],
	...overrides,
});

async function open(doc, deck) {
	globalThis.fetch = async () => ({ ok: true, json: async () => deck });
	const host = doc.createElement('div');
	const viewer = await mount(host, { unit: 'u', files: { deck: 'deck.json' } });
	return { host, viewer };
}
const heading = host => host.querySelector('.deck-slide-title')?.textContent;
const next = host => click(host.querySelector('.deck-next') ?? descendants(host).find(node => node.tagName === 'button' && node.textContent === '下一頁'));

test('1.3 講義一張投影片一頁，依封面、重點、常見錯誤排列，重點頁標題為問題', async () => {
	await withDOM(async doc => {
		const { host, viewer } = await open(doc, handout());
		try {
			assert.equal(host.querySelector('.deck-counter').textContent, '1 / 4');
			assert.equal(heading(host), '迴圈');
			assert.match(host.textContent, /學習目標/);
			assert.equal(host.querySelector('ol').children.length, 2);
			next(host);
			assert.equal(heading(host), '什麼時候該用迴圈？');
			assert.equal(host.querySelector('.deck-handout-subtitle').textContent, '迴圈用途');
			assert.equal(host.querySelector('.deck-handout-body').textContent, '重複做同一件事就用迴圈。');
			next(host); next(host);
			assert.equal(heading(host), '常見錯誤整理');
			assert.match(host.querySelector('.deck-handout-mistake').textContent, /【迴圈用途】/);
			assert.equal(host.querySelector('.viewer-deck').getAttribute('data-contract-version'), '1.3');
		} finally { viewer.dispose(); }
	});
});

test('1.3 重點頁顯示常見錯誤三欄與截斷的出處', async () => {
	await withDOM(async doc => {
		const { host, viewer } = await open(doc, handout());
		try {
			next(host);
			const text = host.querySelector('.deck-handout-misconceptions').textContent;
			assert.match(text, /常見錯誤/);
			assert.match(text, /錯：迴圈一定要跑滿/);
			assert.match(text, /為什麼：條件不成立就會停/);
			assert.match(text, /正確：條件決定是否繼續/);
			assert.equal(host.querySelector('.deck-handout-source').textContent, `出處：${'x'.repeat(60)}…`);
		} finally { viewer.dispose(); }
	});
});

test('1.3 example 為 code 時放進 pre，formula 則不用 pre', async () => {
	await withDOM(async doc => {
		const { host, viewer } = await open(doc, handout());
		try {
			next(host);
			const pre = host.querySelector('pre');
			assert.ok(pre, 'code 範例必須在 pre');
			assert.ok(pre.querySelector('code'));
			assert.equal(pre.textContent, 'while (i < 3) {\n\ti++;\n}');
			next(host);
			assert.equal(host.querySelector('pre'), null);
			assert.match(host.querySelector('.deck-handout-example').textContent, /a = b \+ c/);
		} finally { viewer.dispose(); }
	});
});

test('1.3 教材文字含 script 時以純文字顯示，不建立元素', async () => {
	await withDOM(async doc => {
		const evil = '<script>alert(1)</script>';
		const deck = handout();
		deck.slides[0].title = evil;
		deck.slides[0].objectives = [evil];
		deck.slides[1].question = evil;
		deck.slides[1].explanation = evil;
		deck.slides[1].example.content = evil;
		deck.slides[1].misconceptions[0].wrong = evil;
		deck.slides[3].items[0].point_title = evil;
		const { host, viewer } = await open(doc, deck);
		try {
			assert.equal(heading(host), evil);
			assert.equal(host.querySelector('script'), null);
			next(host);
			assert.equal(heading(host), evil);
			assert.equal(host.querySelector('script'), null);
			assert.match(host.querySelector('.deck-handout-body').textContent, /<script>/);
			next(host); next(host);
			assert.equal(host.querySelector('script'), null);
			assert.match(host.querySelector('.deck-handout-mistake').textContent, /<script>/);
		} finally { viewer.dispose(); }
	});
});

test('1.3 沒有常見錯誤頁與沒有出處時仍可顯示', async () => {
	await withDOM(async doc => {
		const deck = handout();
		deck.slides = deck.slides.slice(0, 3);
		const { host, viewer } = await open(doc, deck);
		try {
			assert.equal(host.querySelector('.deck-counter').textContent, '1 / 3');
			next(host); next(host);
			assert.equal(host.querySelector('.deck-handout-source'), null);
			assert.equal(host.querySelector('.deck-handout-misconceptions'), null);
		} finally { viewer.dispose(); }
	});
});

test('1.2 簡報維持原本版型，不套用講義版面', async () => {
	await withDOM(async doc => {
		const deck = { contract_version: '1.2', slides: [{ title: '條件', role: 'concept', question: '何時停止？', explanation: '條件不成立。',
			takeaway: '看條件。', blocks: [{ type: 'bullets', items: ['先檢查'] }] }] };
		const { host, viewer } = await open(doc, deck);
		try {
			assert.equal(host.querySelector('.deck-question').textContent, '何時停止？');
			assert.equal(host.querySelector('.deck-handout'), null);
			assert.equal(heading(host), '條件');
		} finally { viewer.dispose(); }
	});
});
