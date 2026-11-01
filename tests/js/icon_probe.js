// 測試用：在 node 裡載入圖示形狀，依指令吐 JSON（tests/test_icon_component.py 呼叫）
'use strict';
const path = require('path');
const S = require(path.join(__dirname, '..', '..', 'video_engine', 'components', 'icon', 'shapes.js'));
const [cmd, file] = process.argv.slice(2);
const q = JSON.parse(require('fs').readFileSync(file, 'utf8'));
if (cmd === 'names') process.stdout.write(JSON.stringify(S.NAMES));
else if (cmd === 'strokes') process.stdout.write(JSON.stringify(S.strokes(q.name, q.opts)));
else if (cmd === 'count') process.stdout.write(JSON.stringify(S.count(q.name, q.opts)));
else if (cmd === 'svg') process.stdout.write(JSON.stringify(require(path.join(__dirname, '..', '..', 'video_engine', 'components', 'icon', 'svg.js')).render(q.name, q.opts, q.color, q.px)));
else if (cmd === 'all') {
	const o = {};
	S.NAMES.forEach((n) => { o[n] = S.strokes(n, n === 'keycap' ? { text: 'Ctrl' } : undefined); });
	process.stdout.write(JSON.stringify(o));
} else throw new Error('未知指令 ' + cmd);
