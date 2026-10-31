// 測試用：在 node 裡載入通用標註框，依指令吐 JSON（tests/test_icon_component.py 呼叫）
'use strict';
const path = require('path');
const C = require(path.join(__dirname, '..', '..', 'video_engine', 'components', 'callout', 'callout.js'));
const [cmd, file] = process.argv.slice(2);
const q = JSON.parse(require('fs').readFileSync(file, 'utf8'));
if (cmd === 'consts') process.stdout.write(JSON.stringify({PAD: C.PAD, ARROW: C.ARROW}));
else if (cmd === 'size') process.stdout.write(JSON.stringify(C.size(q.text, (s) => ({ w: s.length * q.charW }), q.style)));
else if (cmd === 'place') process.stdout.write(JSON.stringify(C.place(q.anchor, q.size, q.bounds, q.obstacles)));
else if (cmd === 'endTime') process.stdout.write(JSON.stringify(C.endTime(q.acts, q.i, q.untilT, q.sceneEnd)));
else throw new Error('未知指令 ' + cmd);
