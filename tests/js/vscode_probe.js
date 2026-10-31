// 測試用：在 node 裡載入 VS Code 元件的純函式，依指令吐 JSON（tests/test_vscode_component.py 呼叫）
'use strict';
const path = require('path');
const DIR = path.join(__dirname, '..', '..', 'video_engine', 'components', 'vscode');
const load = (name) => { try { return require(path.join(DIR, name)); } catch (e) { if (e.code === 'MODULE_NOT_FOUND') return null; throw e; } };
const M = load('model.js'), P = load('paint.js'), S = load('svg.js');
const CH = (() => { try { return require(path.join(__dirname, '..', '..', 'video_engine', 'explainer', 'chalk', 'kit', 'vscode.chalk.js')); } catch (e) { if (e.code === 'MODULE_NOT_FOUND') return null; throw e; } })();
const [cmd, file] = process.argv.slice(2);
const q = JSON.parse(require('fs').readFileSync(file, 'utf8'));
const size = q.size || undefined;
if (cmd === 'schedule') {
	// 假的逐字時間：spans = {句號: {字串: [起, 迄]}}，starts = {句號: 開始畫的時刻}
	const span = (l, s) => { const v = q.spans[l] && q.spans[l][s]; if (!v) throw new Error('沒有 ' + s); return { start: v[0], end: v[1] }; };
	process.stdout.write(JSON.stringify(CH.schedule(q.screen, span, (l) => q.starts[l])));
	return;
}
if (cmd === 'cursor' || cmd === 'check') {
	const span = (l, s) => ({ start: q.spans[l][s][0], end: q.spans[l][s][1] });
	if (cmd === 'check') { process.stdout.write(JSON.stringify(CH.check([q.screen], span, (l) => q.starts[l], M, size))); return; }
	const acts = CH.schedule(q.screen, span, (l) => q.starts[l]), id = q.screen.screen.id;
	const own = acts.filter((a) => a.obj === id), track = CH.cursorTrack(M, q.screen.screen, own, acts.filter((a) => a.obj === 'cursor'), [0, 0], size);
	process.stdout.write(JSON.stringify({ acts, pts: q.ts.map((t) => track(t)) }));
	return;
}
const out = (q.ts || [q.t]).map((t) => {
	const st = M.state(q.desc, q.acts || [], t, size);
	if (cmd === 'layout') return M.layout(q.desc, size);
	if (cmd === 'state') return st;
	if (cmd === 'anchors') return M.anchors(q.desc, st, size);
	if (cmd === 'ops') return P.ops(q.desc, st, t, size);
	if (cmd === 'svg') return S.render(P.ops(q.desc, st, t, size), q.theme, size || M.SIZE);
	throw new Error('未知指令 ' + cmd);
});
process.stdout.write(JSON.stringify(out));
