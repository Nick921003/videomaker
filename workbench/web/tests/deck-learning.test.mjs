import test from 'node:test';
import assert from 'node:assert/strict';
import { withDOM, click } from './dom-helper.mjs';
import { renderSlide, mount } from '../js/viewers/deck.mjs';

const walkthrough = {
 title: '條件如何讓迴圈停止？', role: 'example', takeaway: '条件不成立就離開迴圈。',
 question: 'i = 3 時還會輸出嗎？', explanation: '先檢查條件，再決定是否執行本文。',
 speaker_notes: '先觀察變數。', source_quote: '舊引用', source_quotes: ['第一段來源', '第二段來源'],
 blocks: [{ type: 'walkthrough', language: 'c', lines: ['int i = 0;', 'while (i < 3) {', '  printf("%d", i++);', '}'], states: [
  { label: '初始化', line: 1, vars: [{ name: 'i', value: '0' }], output: '', explanation: '從零開始。' },
  { label: '輸出', line: 3, vars: [{ name: 'i', value: '1' }], output: '0', explanation: '印出零，然後遞增。' },
 ] }],
};

test('流程元件沿用階段資料，前後步驟還原高亮且文字不成為HTML', async () => {
 await withDOM(async () => {
  const stages=[{id:'input',label:'输入',note:'<script>教材文字</script>'},
   {id:'check',label:'檢查',note:'核對來源'}, {id:'output',label:'輸出',note:'發佈結果'}];
  const card=renderSlide({title:'處理流程',blocks:[{type:'pipeline',stages}]},{progressive:true});
  const items=card.querySelectorAll('.deck-pipeline-stage');
  assert.equal(items.length,3);
  assert.equal(items[0].getAttribute('aria-current'),'step');
  assert.equal(card.querySelectorAll('.deck-pipeline-arrow').length,2);
  assert.equal(card.querySelector('script'),null);
  assert.match(items[0].textContent,/<script>/);
  click(card.querySelector('.deck-step-next'));
  assert.equal(items[0].getAttribute('aria-current'),null);
  assert.equal(items[1].getAttribute('aria-current'),'step');
  click(card.querySelector('.deck-step-previous'));
  assert.equal(items[0].getAttribute('aria-current'),'step');
  assert.equal(card.querySelectorAll('[data-reveal-hidden="true"]').length,0);
 });
});

test('走讀同步顯示問題、解釋、重點、執行行、變數與輸出，前後步驟可還原', async () => {
 await withDOM(async () => {
  const card = renderSlide(walkthrough);
  assert.equal(card.querySelector('.deck-question')?.textContent, walkthrough.question);
  assert.equal(card.querySelector('.deck-explanation')?.textContent, walkthrough.explanation);
  assert.equal(card.querySelector('.deck-takeaway')?.textContent, walkthrough.takeaway);
  assert.equal(card.querySelector('[data-active="true"]')?.getAttribute('data-line'), '1');
  assert.match(card.querySelector('.deck-vars')?.textContent ?? '', /i0/);
  const next = card.querySelector('.deck-step-next');
  assert.ok(next, '走讀應有下一步');click(next);
  assert.equal(card.querySelector('[data-active="true"]')?.getAttribute('data-line'), '3');
  assert.match(card.querySelector('.deck-vars').textContent, /i1/);
  assert.equal(card.querySelector('.deck-output').textContent, '0');
  assert.equal(card.querySelector('.deck-state-explanation').textContent, '印出零，然後遞增。');
  assert.equal(next.disabled, true);
  click(card.querySelector('.deck-step-previous'));
  assert.equal(card.querySelector('[data-active="true"]')?.getAttribute('data-line'), '1');
 });
});

test('Deck 1.2 筆記完整保留多段引用，鍵盤先走讀再翻頁', async () => {
 await withDOM(async doc => {
  globalThis.fetch = async () => ({ ok: true, json: async () => ({ contract_version: '1.2', slides: [walkthrough, {...walkthrough, title: '回顧'}] }) });
  const host = doc.createElement('div');
  const viewer = await mount(host, { unit: 'u', files: { deck: 'deck.json' } });
  try {
   const quotes = host.querySelector('.deck-notes').querySelectorAll('blockquote');
   assert.deepEqual(quotes.map(q => q.textContent), walkthrough.source_quotes);
   const key = () => { const event = new Event('keydown', {cancelable:true});Object.defineProperty(event,'key',{value:'ArrowRight'});doc.dispatchEvent(event); };
   key();assert.equal(host.querySelector('.deck-counter').textContent, '1 / 2');
   assert.equal(host.querySelector('[data-active="true"]').getAttribute('data-line'), '3');
   key();assert.equal(host.querySelector('.deck-counter').textContent, '2 / 2');
  } finally { viewer.dispose(); }
 });
});

test('新版概念頁逐步揭示保留版位，最終解釋可讀且不覆蓋takeaway', async () => {
 await withDOM(async () => {
  const card = renderSlide({title:'三要素',question:'每一部分做什麼？',explanation:'它們合作完成重複。',takeaway:'三者缺一不可。',blocks:[{type:'concept',center:'迴圈',items:[{title:'初始化',text:'起點'},{title:'條件',text:'是否繼續'}]}]}, {progressive:true});
  assert.equal(card.querySelectorAll('[data-reveal-hidden="true"]').length, 2);
  click(card.querySelector('.deck-step-next'));
  assert.equal(card.querySelectorAll('[data-reveal-hidden="true"]').length, 1);
  click(card.querySelector('.deck-step-next'));
  assert.equal(card.querySelectorAll('[data-reveal-hidden="true"]').length, 0);
  assert.equal(card.querySelector('.deck-explanation').textContent,'它們合作完成重複。');
 });
});

test('相同的explanation與takeaway只呈現一次，仍保存重點語意', async () => {
 await withDOM(async () => {
  const card=renderSlide({title:'回顧',question:'何時停止？',explanation:'條件不成立就停止。',takeaway:'條件不成立就停止。',blocks:[{type:'bullets',items:['先檢查條件']}]});
  assert.equal(card.textContent.split('條件不成立就停止。').length-1,1);
  assert.equal(card.querySelector('.deck-takeaway').textContent,'條件不成立就停止。');
 });
});

test('Deck1.2保留原生捲動，工具列縮放調整閱讀字級而不攔截滾輪', async () => {
 await withDOM(async doc => {
  globalThis.fetch=async()=>({ok:true,json:async()=>({contract_version:'1.2',slides:[walkthrough]})});
  const host=doc.createElement('div');const viewer=await mount(host,{unit:'u',files:{deck:'deck.json'}});
  try {
   const viewport=host.querySelector('.deck-viewport');
   const wheel=new Event('wheel',{cancelable:true});Object.defineProperty(wheel,'deltaY',{value:100});viewport.dispatchEvent(wheel);
   assert.equal(wheel.defaultPrevented,false,'新版閱讀頁必須能以滾輪捲動');
   click(host.querySelector('[data-viewer-action="zoomIn"]'));
   assert.equal(host.querySelector('.viewer-deck').style.getPropertyValue('--deck-reading-scale'),'1.1');
   click(host.querySelector('[data-viewer-action="fit"]'));
   assert.equal(host.querySelector('.viewer-deck').style.getPropertyValue('--deck-reading-scale'),'1');
  } finally {viewer.dispose();}
 });
});
