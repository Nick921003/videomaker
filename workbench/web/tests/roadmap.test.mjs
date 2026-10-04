import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { extractRoadmap, renderRoadmap } from '../js/pages/roadmap.mjs';

const mock = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));

test('路線圖提供外框使用的渲染入口', () => {
	assert.equal(typeof renderRoadmap, 'function');
});

test('路線圖正確篩選 planned 形式並按順位排序', async () => {
	const formats = await mock('formats');
	const planned = extractRoadmap(formats);

	assert.equal(planned.length, 5);
	assert.deepEqual(
		planned.map(f => f.id),
		['comic', 'podcast', 'interactive_text', 'worked_example', 'quiz'],
	);
	assert.deepEqual(
		planned.map(f => f.planned_note.order),
		[1, 2, 3, 4, 5],
	);
});

test('沒有規劃中形式時回傳空陣列', () => {
	assert.deepEqual(extractRoadmap({ formats: [] }), []);
	assert.deepEqual(extractRoadmap({ formats: [{ id: 'video', status: 'available' }] }), []);
});
