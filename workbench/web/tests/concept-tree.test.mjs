import test from 'node:test';
import assert from 'node:assert/strict';
import { visibleTree } from '../js/viewers/concept-tree.mjs';
test('心智圖展開只顯示可達分支，收合隱藏整個子樹並重新排列', () => {
 const children = new Map([['root',['condition','update']],['condition',['meaning','example']],['update',[]],['meaning',[]],['example',[]]]);
 const closed = visibleTree('root', children, new Set(['root']));
 assert.deepEqual(closed.map(row => row.id), ['root','condition','update']);
 const opened = visibleTree('root', children, new Set(['root','condition']));
 assert.deepEqual(opened.map(row => row.id), ['root','condition','meaning','example','update']);
 assert.equal(opened.find(row => row.id==='update').y, 2);
 assert.equal(closed.find(row => row.id==='update').y, 1);
});
