import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { stepAvailability, makeHash } from '../js/pages/make.mjs';
import { paginateUnits, sourceKind } from '../js/pages/make-source.mjs';
import { pointStatus, highlightPoints } from '../js/pages/make-analysis.mjs';

const fixture = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));

test('步驟以教材、分析點和實際成品解鎖；排隊或失敗不算成品', async () => {
	assert.deepEqual(stepAvailability(null), [true, false, false, false]);
	assert.deepEqual(stepAvailability(await fixture('unit-new')), [true, false, false, false]);
	assert.deepEqual(stepAvailability(await fixture('unit-analyzed')), [true, true, true, false]);
	assert.deepEqual(stepAvailability(await fixture('unit-done')), [true, true, true, true]);
	assert.deepEqual(stepAvailability({ analysis: { points: [] }, items: [] }), [true, false, false, false]);
	const analyzed = await fixture('unit-analyzed');
	analyzed.items[0].status = 'failed';
	analyzed.items[1].status = 'running';
	assert.equal(stepAvailability(analyzed)[3], false);
});

test('製作連結保留教材與 mock 情境，用 URLSearchParams 編碼', () => {
	assert.equal(makeHash(2, { unit: 'a&b', state: 'analyzed' }), '#/make/2?unit=a%26b&state=analyzed');
	assert.equal(makeHash(1, {}), '#/make/1');
});

test('素材庫每頁六份，空清單和越界頁數保持可用且不修改輸入', () => {
	const units = Array.from({ length: 14 }, (_, i) => ({ unit_id: `u${i}` }));
	assert.deepEqual(paginateUnits(units, 1).items, units.slice(6, 12));
	assert.equal(paginateUnits(units, 999).page, 2);
	assert.equal(paginateUnits(units, -1).page, 0);
	assert.equal(paginateUnits(units).pages, 3);
	assert.deepEqual(paginateUnits([], 1), { items: [], page: 0, pages: 1 });
	assert.equal(units.length, 14);
});

test('教材格式只接受四種副檔名，不因大小寫或多個點拒收', () => {
	for (const kind of ['md', 'txt', 'pdf', 'pptx']) assert.equal(sourceKind(`lesson.v2.${kind.toUpperCase()}`), kind);
	assert.equal(sourceKind('lesson.docx'), null);
	assert.equal(sourceKind('pdf'), null);
});

test('點的狀態只讀對應影片；重點片按建議順序取出問題', async () => {
	const unit = await fixture('unit-done');
	assert.equal(pointStatus(unit, 'q1'), 'done');
	assert.equal(pointStatus(unit, 'missing'), 'none');
	assert.deepEqual(highlightPoints(unit.analysis).map(point => point.id), ['q1', 'q2', 'q3']);
	assert.deepEqual(highlightPoints({ points: [], highlight: { points: ['missing'] } }), []);
});
