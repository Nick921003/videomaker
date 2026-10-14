import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { withDOM, descendants, click } from './dom-helper.mjs';
import { renderMakeAnalysis } from '../js/pages/make-analysis.mjs';

const fixture = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));

test('重點搜尋涵蓋標題與其他問法，空結果不顯示舊詳情，清除後可重新選取', async () => {
 await withDOM(async () => {
  const unit = await fixture('unit-analyzed');
  const page = renderMakeAnalysis(unit, { next: '#/make/3' });
  assert.doesNotMatch(page.textContent, /不涵蓋|指標與動態記憶體配置/);
  const search = descendants(page).find(node => node.getAttribute('aria-label') === '搜尋教材重點');
  assert.ok(search, '應可快速搜尋重點');
  const choices = () => descendants(page).filter(node => node.getAttribute('data-point-id'));
  search.value = '小於跟小於等於';
  search.dispatchEvent(new Event('input'));
  assert.equal(choices().filter(node => !node.hidden).length, 1);
  const selected = choices().find(node => node.getAttribute('aria-pressed') === 'true');
  assert.equal(selected.getAttribute('data-point-id'), 'q2');
  assert.match(page.textContent, /並排演出 i < 3 與 i <= 3/);
  search.value = '完全無匹配'; search.dispatchEvent(new Event('input'));
  assert.equal(choices().filter(node => !node.hidden).length, 0);
  assert.doesNotMatch(descendants(page).find(node => node.getAttribute('aria-label') === '選取問題的詳情').textContent, /並排演出/);
  search.value = ''; search.dispatchEvent(new Event('input'));
  assert.equal(choices().filter(node => !node.hidden).length, unit.analysis.points.length);
  click(choices()[4]);
  assert.equal(choices()[4].getAttribute('aria-pressed'), 'true');
 });
});

test('導覽收合偏好跨初始化保存，儲存不可用仍可切換，入口有可辨識名稱', async () => {
 await withDOM(async doc => {
  const { initRail } = await import('../js/navigation.mjs');
  const layout = doc.createElement('div');
  const toggle = doc.createElement('button');
  const label = doc.createElement('span'); toggle.append(label);
  const link = doc.createElement('a'); link.textContent = '素材庫';
  doc.getElementById = id => ({ 'app-layout': layout, 'rail-toggle': toggle, 'rail-toggle-label': label }[id]);
  doc.querySelectorAll = () => [link];
  const values = new Map();
  const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
  initRail(doc, storage);
  assert.equal(toggle.getAttribute('aria-expanded'), 'true');
  click(toggle);
  assert.equal(layout.getAttribute('data-rail'), 'collapsed');
  assert.equal(toggle.getAttribute('aria-label'), '展開導覽');
  assert.equal(link.getAttribute('aria-label'), '素材庫');
  const second = doc.createElement('button');
  doc.getElementById = id => ({ 'app-layout': layout, 'rail-toggle': second, 'rail-toggle-label': label }[id]);
  initRail(doc, storage);
  assert.equal(second.getAttribute('aria-expanded'), 'false');
  click(second);
  assert.equal(layout.getAttribute('data-rail'), 'expanded');
  const third = doc.createElement('button');
  doc.getElementById = id => ({ 'app-layout': layout, 'rail-toggle': third, 'rail-toggle-label': label }[id]);
  initRail(doc, { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } });
  click(third);
  assert.equal(layout.getAttribute('data-rail'), 'collapsed');
 });
});
