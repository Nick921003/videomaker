import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {buildTrace, stateAt} from './model.mjs';

const lesson = JSON.parse(await readFile(new URL('./lesson.json', import.meta.url)));
test('five additions finish at 15 and the sixth condition check exits', () => {
	const trace = buildTrace(lesson);
	assert.deepEqual(trace.filter(e => e.step === 'body').map(e => e.sum), [1,3,6,10,15]);
	assert.deepEqual(trace.filter(e => e.step === 'check').map(e => e.i), [1,2,3,4,5,6]);
	assert.equal(trace.filter(e => e.step === 'init').length, 1);
	for (const e of trace.filter(e => e.step === 'return')) assert.equal(e.next, 'check');
	assert.deepEqual(trace.at(-1), {at:29.65, step:'exit', i:6, sum:15, checks:6, bodies:5, next:null});
});
test('frames on either side of addition/update show truthful values', () => {
	assert.equal(stateAt(17.64, lesson).execution.sum, 0);
	assert.equal(stateAt(17.65, lesson).execution.sum, 1);
	assert.equal(stateAt(18.29, lesson).execution.i, 1);
	assert.equal(stateAt(18.3, lesson).execution.i, 2);
	assert.equal(stateAt(29, lesson).execution.next, 'exit');
});
test('a round keeps its number through addition, update, and return', () => {
	for(const t of [17,17.65,18.3,18.85]) assert.equal(stateAt(t,lesson).executionRound,1);
	for(const t of [19.4,20.05,20.7,21.25]) assert.equal(stateAt(t,lesson).executionRound,2);
	assert.equal(stateAt(29,lesson).executionRound,6);
});
test('seeking out of order changes no state and captions cover the last frame', () => {
	const times = [0,7.99,8,16,17.65,29,31,39,47.99];
	const expected = times.map(t => stateAt(t, lesson));
	for (const t of [...times].reverse()) assert.deepEqual(stateAt(t, lesson), expected[times.indexOf(t)]);
	assert.equal(stateAt(48, lesson).time, 48-1/24);
	assert.equal(stateAt(48, lesson).subtitle, lesson.subtitles.at(-1)[2]);
	assert.equal(stateAt(-1, lesson).time, 0);
	assert.throws(() => stateAt(NaN, lesson), /finite/);
});
test('all frame subtitles are continuous and readable', () => {
	let end = 0;
	for (const [a,b,text] of lesson.subtitles) {
		assert.equal(a,end); assert.ok(b>a); assert.ok([...text].length/(b-a)<=10);
		end=b;
	}
	assert.equal(end,48);
	for(let k=0;k<48*24;k++) assert.ok(stateAt(k/24,lesson).subtitle);
});
