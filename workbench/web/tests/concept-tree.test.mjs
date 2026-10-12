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

import { withDOM, Element, click } from './dom-helper.mjs';
import { mountConceptTree } from '../js/viewers/concept-tree.mjs';

async function conceptDOM(run) {
 const previousObserver = globalThis.ResizeObserver;
 const additions = {
  offsetWidth: { configurable:true, get() {return parseFloat(this.style.width) || 300;} },
  offsetHeight: { configurable:true, get() {return this.className.includes('concept-card') ? 160 : 600;} },
  clientWidth: { configurable:true, get() {return 375;} },
  clientHeight: { configurable:true, get() {return 600;} },
  prepend: { configurable:true, value(...nodes) {this.children.unshift(...nodes);for(const node of nodes)node.parentElement=this;} },
 };
 const original = Object.fromEntries(Object.keys(additions).map(key => [key,Object.getOwnPropertyDescriptor(Element.prototype,key)]));
 Object.defineProperties(Element.prototype,additions);
 globalThis.ResizeObserver = class {observe() {} disconnect() {}};
 try {await withDOM(run);} finally {
  for(const [key,value] of Object.entries(original)) if(value)Object.defineProperty(Element.prototype,key,value);else delete Element.prototype[key];
  if(previousObserver)globalThis.ResizeObserver=previousObserver;else delete globalThis.ResizeObserver;
 }
}

function fixture(doc, version='1.1') {
 const svg=doc.createElement('svg');svg.setAttribute('data-root-id','root');svg.setAttribute('data-layout','progressive');svg.setAttribute('data-contract-version',version);
 for(const [id,kind,label,explanation] of [['root','concept','迴圈',''],['a','concept','條件','先判斷條件'],['b','concept','更新',''],['detail','meaning','條件為真才進入本文。','詳細的意思'],['example','example','i 小於三就執行。','']]) {
  const node=doc.createElement('g');node.setAttribute('data-node-id',id);node.setAttribute('data-node-kind',kind);
  const title=doc.createElement('title');title.setAttribute('data-node-label','');title.textContent=label;
  const desc=doc.createElement('desc');desc.setAttribute('data-node-explanation','');desc.textContent=explanation;
  node.append(title,desc);svg.append(node);
 }
 for(const [from,to] of [['root','a'],['root','b'],['a','detail'],['a','example']]) {
  const edge=doc.createElement('path');edge.setAttribute('data-from',from);edge.setAttribute('data-to',to);svg.append(edge);
 }
 return svg;
}

test('新版explicit分支不合成意思，展開保留根與兄弟位置且字級不縮小，連線從卡片邊緣出入', async () => {
 await conceptDOM(async doc => {
  const host=doc.createElement('div');const viewer=mountConceptTree(host,fixture(doc),{unit:'u',files:{svg:'map.svg'}});
  try {
   const positions=()=>new Map(host.querySelectorAll('.concept-card').map(card=>[card.getAttribute('data-concept-id'),[card.style.left,card.style.top]]));
   const before=positions();click(host.querySelector('[data-concept-id="a"]'));
   const after=positions();for(const [id,pos] of before)assert.deepEqual(after.get(id),pos,`${id} 的位置必須保留`);
   assert.deepEqual([...after.keys()].sort(),['root','a','b','detail','example'].sort());
   assert.equal(host.querySelector('[data-concept-id="detail"]').getAttribute('data-node-kind'),'meaning');
   const scale=Number(host.querySelector('.concept-canvas').style.transform.match(/scale\(([^)]+)\)/)[1]);
   assert.ok(scale>=.95,'展開不能縮字到不可讀');
   const a=host.querySelector('[data-concept-id="a"]');
   const path=host.querySelector('[data-child="detail"]').getAttribute('d');
   assert.ok(path.startsWith(`M${parseFloat(a.style.left)+a.offsetWidth},`),'右展開線從父卡右邊緣開始');
   assert.equal(host.querySelector('[data-concept-id="detail:meaning"]'),null);
   const back=host.querySelectorAll('button').find(node=>node.textContent==='返回上一層');click(back);
   assert.equal(host.querySelector('[data-concept-id="detail"]'),null);
   assert.ok(host.querySelector('[data-concept-id="b"]'));
  } finally {viewer.dispose();}
 });
});

test('舊版仍建立synthetic意思，根節點無法收合消失，Backspace可返回', async () => {
 await conceptDOM(async doc => {
  const host=doc.createElement('div');const viewer=mountConceptTree(host,fixture(doc,'1.0'),{unit:'u',files:{svg:'map.svg'}});
  try {
   click(host.querySelector('[data-concept-id="root"]'));assert.ok(host.querySelector('[data-concept-id="a"]'));
   click(host.querySelector('[data-concept-id="a"]'));assert.ok(host.querySelector('[data-concept-id="a:meaning"]'));
   const event=new Event('keydown',{cancelable:true});Object.defineProperty(event,'key',{value:'Backspace'});host.querySelector('.concept-viewport').dispatchEvent(event);
   assert.equal(host.querySelector('[data-concept-id="a:meaning"]'),null);
  } finally {viewer.dispose();}
 });
});

test('鍵盤focus聚焦可達分支，避免Tab落在視窗外而無法閱讀', async () => {
 await conceptDOM(async doc => {
  const host=doc.createElement('div');const viewer=mountConceptTree(host,fixture(doc),{unit:'u',files:{svg:'map.svg'}});
  try {
   const canvas=host.querySelector('.concept-canvas');const before=canvas.style.transform;
   const control=host.querySelector('[data-concept-id="b"]').querySelector('button');
   control.dispatchEvent(new Event('focus'));
   assert.notEqual(canvas.style.transform,before);
  } finally {viewer.dispose();}
 });
});

test('展開保留所選父概念的視角，不跳到解說葉節點', async () => {
 await conceptDOM(async doc => {
  const host=doc.createElement('div');const viewer=mountConceptTree(host,fixture(doc),{unit:'u',files:{svg:'map.svg'}});
  try {
   const parent=host.querySelector('[data-concept-id="a"]');
   parent.querySelector('button').dispatchEvent(new Event('focus'));
   const before=host.querySelector('.concept-canvas').style.transform;
   click(parent);
   assert.equal(host.querySelector('.concept-canvas').style.transform,before);
   assert.ok(host.querySelector('[data-concept-id="detail"]'));
  } finally {viewer.dispose();}
 });
});

test('拖曳長節點本身移動畫布而不誤觸展開', async () => {
 await conceptDOM(async doc => {
  const host=doc.createElement('div');const viewer=mountConceptTree(host,fixture(doc),{unit:'u',files:{svg:'map.svg'}});
  try {
   const viewport=host.querySelector('.concept-viewport');viewport.setPointerCapture=()=>{};
   const canvas=host.querySelector('.concept-canvas');const before=canvas.style.transform;
   const target=host.querySelector('[data-concept-id="a"]').querySelector('button');
   const pointer=(type,y)=>{const event=new Event(type,{cancelable:true});for(const [key,value]of Object.entries({target,button:0,clientX:100,clientY:y,pointerId:1}))Object.defineProperty(event,key,{value});viewport.dispatchEvent(event);};
   pointer('pointerdown',200);pointer('pointermove',120);pointer('pointerup',120);
   assert.notEqual(canvas.style.transform,before);
   const clickEvent=new Event('click',{cancelable:true});Object.defineProperty(clickEvent,'detail',{value:1});viewport.dispatchEvent(clickEvent);
   assert.equal(clickEvent.defaultPrevented,true);
   assert.equal(host.querySelector('[data-concept-id="detail"]'),null);
  } finally {viewer.dispose();}
 });
});

test('收合父分支清理子孫展開歷史，Backspace後Enter重新展開可見父節點', async () => {
 await conceptDOM(async doc => {
  const svg=fixture(doc);
  for(const edge of svg.querySelectorAll('path[data-from]')) {
   if(edge.getAttribute('data-to')==='b'||edge.getAttribute('data-to')==='detail')edge.remove();
  }
  for(const [from,to]of [['a','b'],['b','detail']]) {
   const edge=doc.createElement('path');edge.setAttribute('data-from',from);edge.setAttribute('data-to',to);svg.append(edge);
  }
  const host=doc.createElement('div');const viewer=mountConceptTree(host,svg,{unit:'u',files:{svg:'map.svg'}});
  try {
   const back=host.querySelectorAll('button').find(node=>node.textContent==='返回上一層');
   click(host.querySelector('[data-concept-id="a"]'));
   click(host.querySelector('[data-concept-id="b"]'));
   assert.ok(host.querySelector('[data-concept-id="detail"]'));
   click(host.querySelector('[data-concept-id="a"]'));
   assert.equal(host.querySelector('[data-concept-id="b"]'),null);
   assert.equal(back.disabled,true,'父分支收合後不得留下隱藏子孫的返回歷史');
   const viewport=host.querySelector('.concept-viewport');
   for(const key of ['Backspace','Enter']) {
    const event=new Event('keydown',{cancelable:true});Object.defineProperty(event,'key',{value:key});viewport.dispatchEvent(event);
   }
   assert.ok(host.querySelector('[data-concept-id="b"]'),'Enter必須重新展開可見父節點');
   assert.equal(host.querySelector('[data-concept-id="detail"]'),null,'已收合子孫不得自動重新展開');
   assert.equal(host.querySelector('[data-concept-id="b"]').querySelector('button').getAttribute('aria-expanded'),'false');
  } finally {viewer.dispose();}
 });
});
