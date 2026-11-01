// 測試用：在 node 裡載入粉筆圖示與文字皮膚，用假的 api 記下每個呼叫（tests/test_icon_component.py 呼叫）
'use strict';
const path = require('path');
const KIT = path.join(__dirname, '..', '..', 'video_engine', 'explainer', 'chalk', 'kit');
const CI = require(path.join(KIT, 'icon.chalk.js'));
const CN = require(path.join(KIT, 'note.chalk.js'));
const [cmd, file] = process.argv.slice(2);
const q = JSON.parse(require('fs').readFileSync(file, 'utf8'));
// 假量測：全形字寬＝字級，半形＝字級×0.55
const measure = (s, size) => Array.from(s).reduce((n, c) => n + (c.charCodeAt(0) > 255 ? size : size * 0.55), 0);
// 假 api：每個呼叫記成一筆，回傳的物件只帶 el 與 chars 讓皮膚能收集
function fake(log) {
	let n = 0;
	const mk = (kind, rest) => { const o = { id: kind + n++, chars: [] }; log.push(Object.assign({ kind, id: o.id }, rest)); return o; };
	return {
		S: (P, d, tone, w, t, dur, opt) => mk('S', { d, tone, w, t, dur, opt }),
		T: (P, x, y, size, segs, opt) => mk('T', { x, y, size, segs, opt }),
		seq: (P, x, y, size, parts, t0, cps, opt) => { const o = mk('seq', { x, y, size, parts, t0, cps }); o.end = t0 + 1; return o; },
		X: (P, els, rect, t0, dur) => mk('X', { n: els.length, rect, t0, dur }),
		K: { fade: (els, t0, dur, to, back) => mk('fade', { n: [].concat(els).length, t0, dur, to, back }), wlen: (s) => measure(s, 1) },
	};
}
if (cmd === 'paths') {
	const o = {};
	CI.NAMES.forEach((n) => { o[n] = CI.paths(n, n === 'keycap' ? { text: 'Ctrl' } : undefined, q.box); });
	process.stdout.write(JSON.stringify(o));
} else if (cmd === 'perform') {
	const log = [];
	const r = CI.perform(fake(log), {}, q.obj, q.box, q.acts, q.tone || 'ink');
	process.stdout.write(JSON.stringify({ log, els: r.els.length }));
} else if (cmd === 'layout') {
	let out;
	try { out = CN.layout(q.text, q.style, q.maxW, q.maxH, measure); } catch (e) { out = { error: String(e.message) }; }
	process.stdout.write(JSON.stringify(out));
} else if (cmd === 'consts') {
	process.stdout.write(JSON.stringify({ SIZE: CI.SIZE, STYLES: CN.STYLES, MIN: CN.MIN }));
} else if (cmd === 'note') {
	const log = [];
	const r = CN.perform(fake(log), {}, q.obj, q.box, q.acts);
	process.stdout.write(JSON.stringify({ log, els: r.els.length }));
} else throw new Error('未知指令 ' + cmd);
