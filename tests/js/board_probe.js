// 測試用：在 node 裡載入黑板格子與通用轉接，排版、排程、用假的 api 畫一頁（tests/test_icon_component.py 呼叫）
'use strict';
const fs = require('fs');
const path = require('path');
const KIT = path.join(__dirname, '..', '..', 'video_engine', 'explainer', 'chalk', 'kit');
const [cmd, file] = process.argv.slice(2);
const q = JSON.parse(fs.readFileSync(file, 'utf8'));

function story(data) {
	const g = {};
	new Function('window', fs.readFileSync(path.join(KIT, '..', 'core', 'core.js'), 'utf8'))(g);
	return new g.ExplainerCore.Story(data);
}
// 假 api：每個呼叫記成一筆（同 chalk_probe.js），時間照真的 Story 算
function fake(st, area, log) {
	let n = 0;
	const mk = (kind, rest) => { const o = { id: kind + n++, chars: [] }; log.push(Object.assign({ kind, id: o.id }, rest)); return o; };
	const wlen = (s) => Array.from(s).reduce((m, c) => m + (c.charCodeAt(0) > 255 ? 1 : 0.55), 0);
	return {
		area: () => area,
		span: (l, s) => st.span(l, s),
		drawAt: (l) => st.line(l).start - (st.line(l).lead || 0),
		lineEnd: (l) => st.line(l).end,
		S: (P, d, tone, w, t, dur, opt) => mk('S', { d, tone, w, t, dur }),
		T: (P, x, y, size, segs, opt) => mk('T', { x, y, size, segs }),
		seq: (P, x, y, size, parts, t0, cps, opt) => { const o = mk('seq', { x, y, size, parts, t0, cps }); o.end = t0 + 1; return o; },
		X: (P, els, rect, t0, dur) => mk('X', { n: els.length, rect, t0, dur }),
		K: { fade: (els, t0, dur, to, back) => mk('fade', { n: [].concat(els).length, t0, dur, to, back }), wlen },
	};
}

let out;
if (cmd === 'tpl') {
	out = require(path.join(KIT, 'board_tpl.js')).tpl(q.area, q.kind);
} else if (cmd === 'printf_tpl') {
	// printf 片 index.html 原文裡的 api.tpl，換一個只會回 area 的假 API 來跑
	const f = new Function('API', 'return function (li, kind) {' + q.body + '};')({ area: () => q.area });
	out = f(1, q.kind);
} else if (cmd === 'place') {
	const CB = require(path.join(KIT, 'board.chalk.js'));
	try { out = CB.place(q.board, q.tpl, (o) => q.sizes[o.id]); } catch (e) { out = { error: String(e.message) }; }
} else if (cmd === 'checkSchedule') {
	const CB = require(path.join(KIT, 'board.chalk.js'));
	const st = story(q.story);
	out = CB.checkSchedule(q.boards, (l, s) => st.span(l, s));
} else if (cmd === 'mountAll') {
	const CB = require(path.join(KIT, 'board.chalk.js'));
	const log = [];
	const r = CB.mountAll(fake(story(q.story), q.area, log), q.boards);
	out = { log, problems: r.problems, render: typeof r.render };
} else throw new Error('未知指令 ' + cmd);
process.stdout.write(JSON.stringify(out));
