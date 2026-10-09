import { el } from '../ui.mjs';
import { fileURL } from './common.mjs';

export function visibleTree(root, children, expanded) {
 const rows = []; let next = 0;
 function walk(id, depth) {
  const kids = expanded.has(id) ? children.get(id) ?? [] : [];
  const row = { id, depth, y: 0 }; rows.push(row);
  const positions = kids.map(child => walk(child, depth + 1));
  row.y = positions.length ? (positions[0] + positions.at(-1)) / 2 : next++;
  return row.y;
 }
 walk(root, 0); return rows;
}

export function mountConceptTree(host, svg, { unit, files }) {
 const rootId = svg.getAttribute('data-root-id');
 const nodes = new Map(), children = new Map(), relations = new Map();
 for (const node of svg.querySelectorAll('g[data-node-id]')) {
  const id = node.getAttribute('data-node-id');
  nodes.set(id, { label: node.querySelector('title[data-node-label]')?.textContent ?? id,
   explanation: node.querySelector('desc[data-node-explanation]')?.textContent ?? '',
   quote: node.querySelector('desc[data-node-quote]')?.textContent ?? '' });
  children.set(id, []);
 }
 for (const edge of svg.querySelectorAll('path[data-from]')) {
  const from = edge.getAttribute('data-from'), to = edge.getAttribute('data-to');
  if (nodes.has(from) && nodes.has(to)) { children.get(from).push(to); relations.set(to, edge.getAttribute('data-relation') ?? ''); }
 }
 if (!nodes.has(rootId)) throw new Error('心智圖缺少起點');
 // 解釋另成分支；大分類本身只顯示名稱。
 for (const [id, node] of [...nodes]) if (node.explanation && id !== rootId) {
  const detail = `${id}:meaning`;
  nodes.set(detail, { label: node.explanation, detail: true });
  children.set(detail, []);children.get(id).unshift(detail);
 }
 const root = el('section', 'viewer concept-reader');
 const tools = el('div', 'concept-tools');
 const reset = el('button', 'button', '回到起點');reset.type = 'button';
 const download = el('a', 'button', '下載 SVG');download.href = fileURL(unit, files.svg, 'svg');download.download = 'mindmap.svg';
 const smaller = el('button', 'button', '−'), larger = el('button', 'button', '＋');
 smaller.type = larger.type = 'button';smaller.setAttribute('aria-label', '縮小');larger.setAttribute('aria-label', '放大');
 const back = el('button', 'button', '返回上一層');back.type = 'button';
 const fullscreen = el('button', 'button', '全螢幕');fullscreen.type = 'button';
 const layout = el('select', 'concept-layout');layout.setAttribute('aria-label', '心智圖布局');
 for (const [value, text] of [['radial', '發散'], ['progressive', '漸進']]) {
  const option = el('option', '', text);option.value = value;layout.append(option);
 }
 layout.value = svg.getAttribute('data-layout') === 'progressive' ? 'progressive' : 'radial';
 tools.append(back, reset, layout, smaller, larger, fullscreen, download);
 const viewport = el('div', 'concept-viewport');viewport.setAttribute('aria-label', '心智圖，點選概念展開分支');
 const canvas = el('div', 'concept-canvas');viewport.append(canvas);root.append(tools, viewport);host.replaceChildren(root);
 let current = rootId, trail = [], positions = new Map();
 const expanded = new Set([rootId]);
 let camera = { x: 0, y: 0, scale: 1 };
 const events = new AbortController();
 function apply() { canvas.style.transform = `translate(${camera.x}px, ${camera.y}px) scale(${camera.scale})`; }
 function fit() {
  const group = new Set([current, ...(children.get(current) ?? [])]);
  const cards = [...canvas.querySelectorAll('.concept-card')].filter(card => group.has(card.getAttribute('data-concept-id')));if (!cards.length) return;
  const left = Math.min(...cards.map(card => parseFloat(card.style.left)));
  const top = Math.min(...cards.map(card => parseFloat(card.style.top)));
  const right = Math.max(...cards.map(card => parseFloat(card.style.left) + card.offsetWidth));
  const bottom = Math.max(...cards.map(card => parseFloat(card.style.top) + card.offsetHeight));
  const scale = Math.min(1.15, Math.max(.25, Math.min((viewport.clientWidth - 48) / (right-left), (viewport.clientHeight - 48) / (bottom-top))));
  camera = { scale, x: viewport.clientWidth/2 - (left+right)/2*scale, y: viewport.clientHeight/2 - (top+bottom)/2*scale };
  canvas.style.transition = 'transform 260ms ease';apply();
 }
 function center(id) {
  const card = [...canvas.querySelectorAll('.concept-card')].find(node => node.getAttribute('data-concept-id') === id);
  if (!card) return;
  camera.scale = Math.min(1.2, (viewport.clientWidth-40)/card.offsetWidth);
  camera.x = viewport.clientWidth/2 - (parseFloat(card.style.left)+card.offsetWidth/2)*camera.scale;
  camera.y = viewport.clientHeight/2 - (parseFloat(card.style.top)+card.offsetHeight/2)*camera.scale;apply();
 }
 function activate(id) {
  if (!children.get(id)?.length) { center(id);return; }
  if (expanded.has(id)) expanded.delete(id);
  else { expanded.add(id);trail.push(id); }
  current = id;
  render();
 }
 viewport.addEventListener('wheel', event => {
  event.preventDefault();canvas.style.transition = 'none';
  const box = viewport.getBoundingClientRect(), px = event.clientX - box.left, py = event.clientY - box.top;
  const scale = Math.max(.4, Math.min(2.5, camera.scale * Math.exp(-event.deltaY * .0015)));
  camera.x = px - (px - camera.x) * scale / camera.scale;
  camera.y = py - (py - camera.y) * scale / camera.scale;camera.scale = scale;apply();
 }, { passive: false, signal: events.signal });
 let drag = null;
 viewport.addEventListener('pointerdown', event => {
  if (event.target.closest('.concept-card, button, a, summary, details')) return;
  drag = { x: event.clientX, y: event.clientY, cx: camera.x, cy: camera.y };
  viewport.setPointerCapture(event.pointerId);canvas.style.transition = 'none';
 }, { signal: events.signal });
 viewport.addEventListener('pointermove', event => {
  if (!drag) return;camera.x = drag.cx + event.clientX - drag.x;camera.y = drag.cy + event.clientY - drag.y;apply();
 }, { signal: events.signal });
 viewport.addEventListener('pointerup', () => { drag = null; }, { signal: events.signal });
 viewport.addEventListener('pointercancel', () => { drag = null; }, { signal: events.signal });
 function render() {
  canvas.replaceChildren();back.disabled = !trail.length;
  const cardWidth = viewport.clientWidth < 650 ? 260 : 300;
  const rows = visibleTree(rootId, children, expanded);
  const signs = new Map([[rootId, 0]]);
  const rootKids = children.get(rootId) ?? [];
  function direction(id, sign) { signs.set(id, sign);for (const kid of children.get(id) ?? []) direction(kid, sign); }
  rootKids.forEach((id,index) => direction(id, layout.value === 'progressive' ? 1 : index%2 ? 1 : -1));
  const maxDepth = Math.max(...rows.map(row => row.depth));
  for (const row of rows) { row.x = 30 + (layout.value === 'progressive' ? row.depth : maxDepth + row.depth * (signs.get(row.id) ?? 1)) * 390;row.y = 30+row.y*260; }
  positions = new Map(rows.map(row => [row.id, row]));
  for (const row of rows) {
   const data = nodes.get(row.id), card = el('section', 'concept-card');card.setAttribute('data-concept-id', row.id);
   card.style.width = `${cardWidth}px`;card.style.left = `${row.x}px`;card.style.top = `${row.y}px`;
   const hasChildren = children.get(row.id)?.length > 0;
   const control = el('button', 'concept-toggle', data.label);
   control.type = 'button';control.setAttribute('aria-label', hasChildren ? `${data.label}，${expanded.has(row.id) ? '收合' : '展開'}` : `${data.label}，聚焦`);
   if (hasChildren) control.setAttribute('aria-expanded', String(expanded.has(row.id)));
   card.addEventListener('click', () => activate(row.id));card.append(control);canvas.append(card);
  }
  // 同一欄依實際高度避開重疊，原始根節點及其他分支仍保留。
  for (const x of new Set(rows.map(row => row.x))) {
   let bottom = 0;
   const column = [...canvas.querySelectorAll('.concept-card')].filter(card => parseFloat(card.style.left) === x).sort((a,b) => parseFloat(a.style.top)-parseFloat(b.style.top));
   for (const card of column) { const y = Math.max(parseFloat(card.style.top), bottom);card.style.top = `${y}px`;bottom = y+card.offsetHeight+50; }
  }
  const cards = [...canvas.querySelectorAll('.concept-card')];
  canvas.style.width = `${Math.max(...cards.map(card => parseFloat(card.style.left)+card.offsetWidth))+30}px`;
  canvas.style.height = `${Math.max(...cards.map(card => parseFloat(card.style.top)+card.offsetHeight))+30}px`;
  const ns = 'http://www.w3.org/2000/svg', lines = document.createElementNS(ns, 'svg');lines.setAttribute('class', 'concept-connectors');lines.setAttribute('width','100%');lines.setAttribute('height','100%');
  const cardById = new Map(cards.map(card => [card.getAttribute('data-concept-id'), card]));
  for (const [parentId,kids] of children) if (expanded.has(parentId)) for (const childId of kids) {
   const parent = cardById.get(parentId), card = cardById.get(childId);if (!parent || !card) continue;
   const line = document.createElementNS(ns,'path');line.setAttribute('data-parent', parentId);line.setAttribute('data-child', childId);
   const x1 = parseFloat(parent.style.left)+parent.offsetWidth/2, y1 = parseFloat(parent.style.top)+parent.offsetHeight/2;
   const x2 = parseFloat(card.style.left)+card.offsetWidth/2, y2 = parseFloat(card.style.top)+card.offsetHeight/2;
   line.setAttribute('d', `M${x1},${y1} C${(x1+x2)/2},${y1} ${(x1+x2)/2},${y2} ${x2},${y2}`);lines.append(line);
  }
  canvas.prepend(lines);fit();
 }
 back.addEventListener('click', () => { if (trail.length) { expanded.delete(trail.pop());current = trail.at(-1) ?? rootId;render(); } });
 reset.addEventListener('click', () => { current = rootId;trail = [];expanded.clear();expanded.add(rootId);render(); });
 layout.addEventListener('change', render);
 function syncFullscreen() {
  const active = root.classList.contains('concept-fullscreen') || document.fullscreenElement === root;
  fullscreen.textContent = active ? '退出全螢幕' : '全螢幕';requestAnimationFrame(fit);
 }
 fullscreen.addEventListener('click', async () => {
  if (document.fullscreenElement === root) { await document.exitFullscreen();root.classList.remove('concept-fullscreen'); }
  else if (root.classList.contains('concept-fullscreen')) root.classList.remove('concept-fullscreen');
  else { root.classList.add('concept-fullscreen');try { await root.requestFullscreen?.(); } catch {} }
  syncFullscreen();
 });
 document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement) root.classList.remove('concept-fullscreen');syncFullscreen(); }, { signal: events.signal });
 document.addEventListener('keydown', event => { if (event.key === 'Escape' && root.classList.contains('concept-fullscreen')) { root.classList.remove('concept-fullscreen');syncFullscreen(); } }, { signal: events.signal });
 const resize = new ResizeObserver(fit);resize.observe(viewport);
 function zoomBy(factor) {
  const scale = Math.max(.4, Math.min(2.5, camera.scale * factor)), px = viewport.clientWidth / 2, py = viewport.clientHeight / 2;
  camera.x = px - (px - camera.x) * scale / camera.scale;camera.y = py - (py - camera.y) * scale / camera.scale;camera.scale = scale;apply();
 }
 smaller.addEventListener('click', () => zoomBy(.85));larger.addEventListener('click', () => zoomBy(1.15));
 render();return { focus() { viewport.focus(); }, dispose() { events.abort();resize.disconnect();root.remove(); } };
}
