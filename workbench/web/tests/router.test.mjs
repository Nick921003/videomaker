import test from 'node:test';
import assert from 'node:assert/strict';
import { parseRoute, go } from '../js/router.mjs';

test('空路由與未知頁面回到總覽', () => {
	for (const hash of ['', '#', '#/', '#/missing', '#/overview/extra']) {
		assert.deepEqual(parseRoute(hash), { page: 'overview', step: null, query: {} });
	}
});

test('六個頁面與製作四步都能解析', () => {
	for (const page of ['overview', 'pipelines', 'library', 'usage', 'roadmap']) {
		assert.deepEqual(parseRoute(`#/${page}`), { page, step: null, query: {} });
	}
	assert.deepEqual(parseRoute('#/make'), { page: 'make', step: 1, query: {} });
	for (let step = 1; step <= 4; step++) {
		assert.deepEqual(parseRoute(`#/make/${step}`), { page: 'make', step, query: {} });
	}
});

test('製作步驟不接受範圍外或部分數字', () => {
	for (const step of ['0', '5', '-1', '2x', '1/extra']) {
		assert.equal(parseRoute(`#/make/${step}`).page, 'overview');
	}
});

test('保留流程焦點、教材與編碼過的查詢值', () => {
	assert.deepEqual(parseRoute('#/pipelines?focus=mindmap'), {
		page: 'pipelines', step: null, query: { focus: 'mindmap' },
	});
	assert.deepEqual(parseRoute('#/make/2?unit=ff9e559208c9&title=%E8%BF%B4%E5%9C%88+%26+%E5%8F%83%E6%95%B8'), {
		page: 'make', step: 2, query: { unit: 'ff9e559208c9', title: '迴圈 & 參數' },
	});
});

test('解析是純函式，不修改輸入或讀取瀏覽器', () => {
	const hash = '#/roadmap?focus=quiz';
	assert.deepEqual(parseRoute(hash), parseRoute(hash));
	assert.equal(hash, '#/roadmap?focus=quiz');
});

test('查詢值包含問號時仍完整保留', () => {
	assert.deepEqual(parseRoute('#/library?question=為什麼?&unit=loops'), {
		page: 'library', step: null, query: { question: '為什麼?', unit: 'loops' },
	});
});

test('導覽會更新 hash 並編碼查詢參數', () => {
	const previous = globalThis.location;
	globalThis.location = { hash: '' };
	try {
		const hash = go('make', 3, { unit: '迴圈 & 範例', empty: null });
		assert.equal(globalThis.location.hash, hash);
		assert.deepEqual(parseRoute(hash), {
			page: 'make', step: 3, query: { unit: '迴圈 & 範例' },
		});
		assert.equal(go('pipelines', null, { focus: 'slides' }), '#/pipelines?focus=slides');
		assert.equal(go('make'), '#/make/1');
	} finally {
		if (previous === undefined) delete globalThis.location;
		else globalThis.location = previous;
	}
});
