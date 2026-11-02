#!/usr/bin/env node
// 電腦畫面的錨點閘：照片子的逐字時間排好 screens 的動作，逐一確認標記與游標指到的位置量得到。
// 有置中／雙欄黑板頁（story.boards）時也查它們的排程：cue 在句子裡、until 換算得到時間（版面要開瀏覽器，見 board_check.py）。
// 用法：node video_engine/explainer/chalk/screen_check.js <影片專案>（讀 lib/story.js、lib/core.js、lib/components/）
'use strict';
const fs = require('fs');
const path = require('path');

const root = path.resolve(process.argv[2] || '.');
// lib/ 底下是給瀏覽器的檔（片子資料夾是 ESM，不能 require），借一個 window 載進來；查的是片子真正會用的那份
global.window = global;
for (const f of ['core.js', 'story.js', 'components/vscode/model.js']) new Function('window', fs.readFileSync(path.join(root, 'lib', f), 'utf8'))(global);
const M = window.VSCodeModel;
const CH = require(path.join(__dirname, 'kit', 'vscode.chalk.js'));
// 黑板轉接連同它用到的圖示形狀（components/icon/shapes.js）、標註框（components/callout/callout.js）一起載入
require(path.join(__dirname, 'kit', 'icon.chalk.js'));
require(path.join(__dirname, 'kit', 'note.chalk.js'));
const CB = require(path.join(__dirname, 'kit', 'board.chalk.js'));

const story = new window.ExplainerCore.Story(window.STORY);
// 與 index.html 的 drawAt 相同：這句的圖從開口前 lead 秒開始畫
const drawAt = (l) => { const L = story.line(l); return L.start - (L.lead || 0); };
const screens = (window.STORY.screens || []).filter((s) => s.screen);
const bad = CH.check(screens, (l, s) => story.span(l, s), drawAt, M);
console.log(`電腦畫面錨點閘：${screens.length} 段畫面，${bad.length ? bad.length + ' 個量不到' : '全部量得到'}`);
bad.forEach((b) => console.log('  ' + b));
const boards = window.STORY.boards || [];
const late = CB.checkSchedule(boards, (l, s) => story.span(l, s));
// 沒有黑板頁的片子輸出與以前相同
if (boards.length) console.log(`黑板頁排程閘：${boards.length} 頁，${late.length ? late.length + ' 個問題' : '全部排得到'}`);
late.forEach((b) => console.log('  ' + b));
process.exit(bad.length || late.length ? 1 : 0);
