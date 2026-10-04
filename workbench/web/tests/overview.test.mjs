import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { summarizeOverview, renderOverview } from '../js/pages/overview.mjs';

const mock = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));

test('總覽提供外框使用的渲染入口', () => {
	assert.equal(typeof renderOverview, 'function');
});

test('總覽只計算可用形式、完成影片成本與素材庫成品', async () => {
	const summary = summarizeOverview(await mock('formats'), await mock('units'), [await mock('unit-done')]);
	assert.equal(summary.available, 4);
	assert.equal(summary.products, 6);
	assert.ok(Math.abs(summary.averageVideoCost - 0.16 / 3) < 1e-10);
});

test('沒有成品時保留零筆，平均費用不假裝為免費', () => {
	assert.deepEqual(summarizeOverview({ formats: [] }, [], []), {
		available: 0, products: 0, averageVideoCost: null,
	});
});
