import { api } from '../api.mjs';
import { el, intro } from '../ui.mjs';
import { layoutMap, layoutSteps, render } from '../diagram.mjs';
import { attach } from '../panzoom.mjs';

function branchLayout(format) {
	if (!format.steps?.length) return { nodes: [format], edges: [], groups: {} };
	const steps = layoutSteps(format.steps);
	const width = Math.max(...steps.map(step => step.x + step.w));
	const center = format.x + format.w / 2;
	const nodes = steps.map(step => ({ ...step, x: step.x + center - width / 2, y: step.y + format.y + format.h + 64 }));
	const bottom = Math.max(...nodes.map(node => node.y + node.h));
	const library = { id: 'library', label: '素材庫', sub: '完成後收進素材庫', x: format.x, y: bottom + 64,
		w: format.w, h: format.h, kind: 'output', detail: '完成的素材與成品清單，會一起收進素材庫。' };
	const edges = [{ from: format.id, to: nodes[0].id },
		...nodes.slice(1).map((node, i) => ({ from: nodes[i].id, to: node.id })),
		{ from: nodes.at(-1).id, to: 'library' }];
	return { nodes: [format, ...nodes, library], edges, groups: {} };
}

function field(label, value) {
	const row = el('div', 'pipeline-field');
	row.append(el('dt', 'detail-label', label), el('dd', '', value));
	return row;
}

export async function renderPipelines(query = {}) {
	const registry = await api.get('/formats');
	const map = layoutMap(registry);
	const page = el('section', 'page pipelines-page');
	page.append(intro('從教材，到不同的理解方式', '教材怎麼變成素材？', '點一種形式，展開它的步驟；點節點，看看模型、花費與檢查細節。'));
	const workbench = el('section', 'pipeline-workbench');
	workbench.setAttribute('aria-label', '教材流程架構');
	const toolbar = el('div', 'pipeline-toolbar');
	const back = el('button', 'button pipeline-back', '返回全圖');
	back.type = 'button';
	back.disabled = true;
	const context = el('span', 'pipeline-context', '所有形式');
	context.setAttribute('role', 'status');
	const buttons = el('div', 'pipeline-controls');
	const zoomValue = el('output', 'pipeline-zoom', '100%');
	zoomValue.setAttribute('aria-label', '縮放倍率');
	const makeButton = (label, name) => {
		const button = el('button', 'button pipeline-control', label);
		button.type = 'button';
		button.setAttribute('aria-label', name);
		button.title = name;
		buttons.append(button);
		return button;
	};
	const minus = makeButton('−', '縮小（-）');
	const plus = makeButton('＋', '放大（+）');
	const fit = makeButton('符合視窗', '符合視窗（0）');
	const fullscreen = makeButton('全螢幕', '切換全螢幕');
	buttons.append(zoomValue);
	toolbar.append(back, context, buttons);
	const body = el('div', 'pipeline-body');
	const viewport = el('div', 'pipeline-viewport');
	const panel = el('aside', 'pipeline-panel scroll-box');
	panel.hidden = true;
	panel.setAttribute('aria-label', '節點詳情');
	const footer = el('div', 'pipeline-footer');
	footer.append(el('span', '', '滾輪縮放 · 拖曳移動 · + / − / 0'), el('span', 'pipeline-legend', '虛線：規劃中'));
	const notice = el('span', 'sr-only');
	notice.setAttribute('role', 'status');
	body.append(viewport, panel);
	workbench.append(toolbar, body, footer, notice);
	page.append(workbench);
	let controls;
	let activeFormat = null;
	let current = map;
	let selected = null;
	let disposed = false;

	function refocus(animateMs = 350) {
		const bounds = JSON.parse(svg.getAttribute('data-bounds'));
		controls?.focus(bounds, animateMs);
	}

	function closePanel() {
		panel.hidden = true;
		body.classList.toggle('has-panel', false);
		svg.focus?.();
		refocus();
	}

	function showPanel(node) {
		selected = node;
		panel.hidden = false;
		body.classList.toggle('has-panel', true);
		const top = el('div', 'pipeline-panel-heading');
		const heading = el('h2', '', node.label);
		const close = el('button', 'button pipeline-control', '關閉');
		close.type = 'button';
		close.setAttribute('aria-label', '關閉節點詳情');
		close.addEventListener('click', closePanel);
		top.append(heading, close);
		const fields = el('dl', 'pipeline-fields');
		const planned = node.kind === 'planned';
		if (node.steps?.length) {
			fields.append(field('模型', [...new Set(node.steps.map(step => step.model))].join(' ＋ ')));
		} else fields.append(field('模型', node.model ?? (planned ? '待評估' : '本機')));
		const details = el('div', 'pipeline-details');
		details.append(el('h3', '', '檢查與細節'));
		if (node.steps?.length) {
			fields.append(field('花費', '各步驟分開計費，費用見下方'));
			for (const step of node.steps) {
				const item = el('article', 'pipeline-step-detail');
				item.append(el('h3', '', step.name), el('p', 'pipeline-step-model', step.model),
					el('p', 'pipeline-step-cost', step.cost), el('p', '', step.detail));
				details.append(item);
			}
		} else {
			fields.append(field('花費', node.cost ?? (planned ? '待評估' : '免費')));
			details.append(el('p', '', node.detail ?? node.planned_note?.why ?? '這個形式還在規劃中，步驟與費用待評估。'));
		}
		panel.replaceChildren(top, fields, details);
		panel.scrollTop = 0;
		for (const group of svg.querySelectorAll?.('[data-node-id]') ?? []) {
			group.setAttribute('aria-pressed', String(group.getAttribute('data-node-id') === selected.id));
		}
	}

	function selectNode(node) {
		if (node.kind === 'format' || node.kind === 'planned') {
			if (activeFormat !== node.id) {
				activeFormat = node.id;
				current = branchLayout(node);
				render(viewport, current, { mode: 'explain', onNodeClick: selectNode });
				context.textContent = node.kind === 'planned' ? `${node.label} · 規劃中` : `${node.label} · ${node.steps.length} 個步驟`;
				back.disabled = false;
				svg.focus?.();
			}
		}
		showPanel(node);
		refocus();
	}

	const svg = render(viewport, current, { mode: 'explain', onNodeClick: selectNode });
	back.addEventListener('click', () => {
		activeFormat = null;
		selected = null;
		current = map;
		panel.hidden = true;
		body.classList.toggle('has-panel', false);
		context.textContent = '所有形式';
		back.disabled = true;
		render(viewport, map, { mode: 'explain', onNodeClick: selectNode });
		refocus();
		svg.focus?.();
	});
	page.mount = () => {
		if (disposed || controls) return;
		controls = attach(svg, { fullscreenElement: workbench, onChange: view => { zoomValue.textContent = `${Math.round(view.scale * 100)}%`; } });
		minus.addEventListener('click', controls.zoomOut);
		plus.addEventListener('click', controls.zoomIn);
		fit.addEventListener('click', controls.fit);
		fullscreen.addEventListener('click', async () => {
			try { await controls.fullscreen(); }
			catch { notice.textContent = '瀏覽器目前無法開啟全螢幕。'; }
		});
		controls.fit();
		const format = map.nodes.find(node => Object.hasOwn(map.groups, node.id) && node.id === query.focus);
		if (format) selectNode(format);
	};
	page.dispose = () => { disposed = true; controls?.destroy(); };
	return page;
}
