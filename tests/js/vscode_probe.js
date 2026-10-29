// 測試用：在 node 裡載入 VS Code 元件的純函式，依指令吐 JSON（tests/test_vscode_component.py 呼叫）
'use strict';
const path = require('path');
const DIR = path.join(__dirname, '..', '..', 'video_engine', 'components', 'vscode');
const load = (name) => { try { return require(path.join(DIR, name)); } catch (e) { if (e.code === 'MODULE_NOT_FOUND') return null; throw e; } };
const M = load('model.js'), P = load('paint.js'), S = load('svg.js');
const [cmd, file] = process.argv.slice(2);
const q = JSON.parse(require('fs').readFileSync(file, 'utf8'));
const size = q.size || undefined;
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
