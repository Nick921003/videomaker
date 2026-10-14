import {test} from 'node:test';
import assert from 'node:assert/strict';
import {setText} from '../../web/js/render.mjs';
test('untrusted strings remain text', () => {
  const node = {textContent:''};
  setText(node, '<img src=x onerror=alert(1)>');
  assert.equal(node.textContent, '<img src=x onerror=alert(1)>');
});
test('deck preview renders hostile source text as text nodes', async () => {
  const {renderDeck} = await import('../../web/js/render.mjs');
  const oldDocument = globalThis.document;
  const nodes = new Map();
  const makeNode = () => ({textContent:'', className:'', disabled:false, children:[],
    append(...children) {this.children.push(...children);},
    replaceChildren() {this.children = [];},
    set innerHTML(_) {throw new Error('HTML injection');}});
  globalThis.document = {createElement: () => makeNode(), getElementById: id => {
    if (!nodes.has(id)) nodes.set(id, makeNode());
    return nodes.get(id);
  }};
  try {
    renderDeck({title:'<img onerror=alert(1)>', slides:[{title:'<script>bad</script>',
      speaker_notes:'<svg onload=bad()>', source_quote:'<b>原文</b>', blocks:[{type:'bullets', items:['<img src=x>']}]}]}, 0);
    assert.equal(nodes.get('deck-counter').textContent, '<img onerror=alert(1)>');
    assert.equal(nodes.get('deck-slide-title').textContent, '<script>bad</script>');
    assert.equal(nodes.get('deck-slide-content').children[0].children[0].textContent, '<img src=x>');
    assert.equal(nodes.get('deck-source-quote').textContent, '<b>原文</b>');
  } finally {globalThis.document = oldDocument;}
});
test('self study concept and takeaway render hostile text safely and old pages clear it', async () => {
  const {renderDeck} = await import('../../web/js/render.mjs');
  const oldDocument = globalThis.document;
  const nodes = new Map();
  const makeNode = () => ({textContent:'', className:'', disabled:false, children:[],
    append(...children) {this.children.push(...children);},
    replaceChildren() {this.children = [];},
    set innerHTML(_) {throw new Error('HTML injection');}});
  globalThis.document = {createElement: () => makeNode(), getElementById: id => {
    if (!nodes.has(id)) nodes.set(id, makeNode());
    return nodes.get(id);
  }};
  const allText = node => [node.textContent, ...node.children.flatMap(allText)].filter(Boolean);
  try {
    const takeaway = '<script>自讀結論</script>';
    const block = {type:'concept', center:'<svg onload=bad()>', items:[
      {title:'<img src=x>', text:'<b>分支說明</b>'}, {title:'更新', text:'趨向停止'}]};
    renderDeck({title:'教材', slides:[{title:'概念', takeaway, blocks:[block]}]}, 0);
    const text = allText(nodes.get('deck-slide-content'));
    for (const value of [takeaway, block.center, ...block.items.flatMap(item => [item.title, item.text])]) {
      assert.ok(text.includes(value));
    }
    assert.equal(nodes.get('deck-slide-content').children[0].className, 'deck-concept');
    renderDeck({title:'舊教材', slides:[{title:'舊頁', blocks:[{type:'steps', items:['先做','再做']}]}]}, 0);
    assert.ok(!allText(nodes.get('deck-slide-content')).includes(takeaway));
    assert.ok(allText(nodes.get('deck-slide-content')).some(text => text.includes('→')));
  } finally {globalThis.document = oldDocument;}
});
test('mind map evidence renders hostile labels and quotes as text', async () => {
  const {renderMindmap} = await import('../../web/js/render.mjs');
  const oldDocument = globalThis.document;
  const nodes = new Map();
  const makeNode = () => ({textContent:'', children:[],
    append(...children) {this.children.push(...children);},
    replaceChildren() {this.children = [];},
    addEventListener(type, fn) {this['on'+type] = fn;},
    set innerHTML(_) {throw new Error('HTML injection');}});
  globalThis.document = {createElement: () => makeNode(), getElementById: id => {
    if (!nodes.has(id)) nodes.set(id, makeNode());
    return nodes.get(id);
  }};
  try {
    renderMindmap({nodes:[{label:'<script>bad</script>', explanation:'說明', source_quote:'<img src=x>'}], edges:[]});
    const evidence = nodes.get('mindmap-evidence');
    assert.equal(evidence.children[0].children[0].textContent, '<script>bad</script>');
    assert.equal(evidence.children[0].children[2].textContent, '<img src=x>');
  } finally {globalThis.document = oldDocument;}
});
test('a late citation opens and highlights its context in the full material', async () => {
  const {renderMindmap} = await import('../../web/js/render.mjs');
  const oldDocument = globalThis.document;
  const nodes = new Map();
  const makeNode = () => ({textContent:'', children:[], open:false, disabled:false,
    append(...children) {this.children.push(...children);},
    replaceChildren() {this.children = [];},
    addEventListener(type, fn) {this['on'+type] = fn;},
    set innerHTML(_) {throw new Error('HTML injection');}});
  globalThis.document = {createElement: () => makeNode(), getElementById: id => {
    if (!nodes.has(id)) nodes.set(id, makeNode());
    return nodes.get(id);
  }};
  try {
    const quote = '<safe>教材後段的定義';
    const source = {revision:'sha256:x', text:'前'.repeat(600)+quote+'。更多上下文'};
    renderMindmap({title:'圖', nodes:[{id:'n', label:'概念', explanation:'說明', source_quote:quote}], edges:[]}, source);
    const button = nodes.get('mindmap-evidence').children[0].children[3];
    assert.equal(button.disabled, false);
    button.onclick();
    const spans = nodes.get('mindmap-source-text').children;
    assert.equal(spans[0].textContent.length, 600);
    assert.equal(spans[1].textContent, quote);
    assert.equal(spans[2].textContent, '。更多上下文');
    assert.equal(nodes.get('mindmap-source-details').open, true);
  } finally {globalThis.document = oldDocument;}
});
