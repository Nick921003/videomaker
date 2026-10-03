import {test} from 'node:test';
import assert from 'node:assert/strict';
import {renderUsage} from '../../web/js/render.mjs';

function node() {
  return {textContent:'',children:[],append(...children) {this.children.push(...children);},
    replaceChildren() {this.children=[];}, set innerHTML(_) {throw Error('unsafe HTML');}};
}
const text = item => [item.textContent,...item.children.map(text)].join(' ');
test('usage shows generation and reused normalization separately and marks estimates', () => {
  const old = globalThis.document;
  globalThis.document = {createElement:node};
  try {
    const container=node();
    const usage={total_tokens:13837,input_tokens:5742,output_tokens:8095,thinking_tokens:513,
      call_count:3,complete:true,estimated_cost_usd:.16091875,calls:[{model:'<img src=x>',stage:'deck',total_tokens:13837}]};
    renderUsage(container,usage,{...usage,total_tokens:2097});
    assert.match(text(container),/13,837/);
    assert.match(text(container),/2,097/);
    assert.match(text(container),/0.1609/);
    assert.match(text(container),/估算/);
    assert.match(text(container),/共用素材/);
    assert.match(text(container),/<img src=x>/);
  } finally {globalThis.document=old;}
});
test('missing or partial usage never looks like zero or a complete total', () => {
  const old = globalThis.document;
  globalThis.document = {createElement:node};
  try {
    const container=node();
    renderUsage(container,null,null);
    assert.match(text(container),/未取得/);
    renderUsage(container,{total_tokens:42,call_count:2,complete:false,calls:[]},null);
    assert.match(text(container),/至少 42/);
    assert.match(text(container),/未回報/);
    assert.doesNotMatch(text(container),/US\$0\.0000/);
  } finally {globalThis.document=old;}
});
