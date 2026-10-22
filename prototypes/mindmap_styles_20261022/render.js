// 心智圖多風格原型算繪腳本 (render.js)

// 建立 DOM 元素輔助函式
function el(tag, className = '', text = '') {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text) node.textContent = text;
	return node;
}

// 方案描述資訊
const VARIANT_INFO = {
	'variant-a': {
		title: '方案 A：分支色彩 (Branch Color)',
		desc: '各第一層分支獲派獨立色系，子層級隨深度漸淡繼承，連線採用分支色，根節點為深色實心。',
	},
	'variant-b': {
		title: '方案 B：階層漸變 (Depth Gradient)',
		desc: '卡片採用精緻線性漸變，飽和度與尺寸隨深度遞減；畫布背景為深冷藍，卡片明亮立體對比鮮明。',
	},
	'variant-c': {
		title: '方案 C：大綱骨架 (Outline / XMind-like)',
		desc: '根節點為圓潤膠囊，概念節點具邊框卡片，其餘深層節點為直接座落於彩色分支底線上的文字（無外框）。',
	},
};

class MindMapViewer {
	constructor() {
		this.viewport = document.getElementById('mindmap-viewport');
		this.canvas = document.getElementById('mindmap-canvas');
		this.nodesContainer = document.getElementById('mindmap-nodes');
		this.connectorsSvg = document.getElementById('mindmap-connectors');
		this.dialog = document.getElementById('meaning-dialog');
		
		this.currentVariant = 'variant-a';
		this.data = null;
		this.nodesMap = new Map();
		this.childrenMap = new Map();
		this.parentMap = new Map();
		this.depthMap = new Map();
		this.branchMap = new Map();
		this.dims = new Map();
		this.positions = new Map();
		this.subtreeHeights = new Map();
		
		this.camera = { x: 40, y: 40, scale: 1 };
		this.isDragging = false;
		this.dragStart = { x: 0, y: 0, cx: 0, cy: 0, moved: false };
		this.gapX = 56;
		this.gapY = 26;
	}

	async init() {
		try {
			const res = await fetch('./data.json');
			if (!res.ok) throw new Error(`無法載入 data.json: ${res.status}`);
			this.data = await res.json();
			document.getElementById('mindmap-title').textContent = this.data.title || '心智圖視覺風格提案';
			this.buildTreeGraph();
			this.setupEventListeners();
			this.render(this.currentVariant, true);
		} catch (err) {
			console.error('初始化心智圖失敗:', err);
			this.viewport.innerHTML = `<div style="padding: 40px; color: #ef4444;">載入心智圖失敗：${err.message}</div>`;
		}
	}

	buildTreeGraph() {
		const rootId = this.data.root_id || 'root';
		for (const node of this.data.nodes) {
			this.nodesMap.set(node.id, node);
			this.childrenMap.set(node.id, []);
		}
		for (const edge of this.data.edges) {
			if (this.nodesMap.has(edge.from) && this.nodesMap.has(edge.to)) {
				this.childrenMap.get(edge.from).push(edge.to);
				this.parentMap.set(edge.to, edge.from);
			}
		}

		// 計算節點深度
		const assignDepth = (id, depth) => {
			this.depthMap.set(id, depth);
			for (const childId of this.childrenMap.get(id) || []) assignDepth(childId, depth + 1);
		};
		assignDepth(rootId, 0);

		// 分支色彩分配：5 個主要概念分支
		this.branchMap.set(rootId, null);
		const branchDefs = [
			{ id: 'for_structure', branch: 0 },
			{ id: 'loop_update', branch: 1 },
			{ id: 'loop_bounds', branch: 2 },
			{ id: 'read_n_data', branch: 3 },
			{ id: 'trace_and_test', branch: 4 },
		];
		const markBranch = (id, branchIndex) => {
			this.branchMap.set(id, branchIndex);
			for (const childId of this.childrenMap.get(id) || []) {
				if (branchDefs.some(b => b.id === childId && b.id !== 'for_structure')) continue;
				markBranch(childId, branchIndex);
			}
		};
		for (const { id, branch } of branchDefs) if (this.nodesMap.has(id)) markBranch(id, branch);
	}

	// 建立節點 DOM 結構
	createNodeElement(node) {
		const id = node.id, depth = this.depthMap.get(id) ?? 0, branch = this.branchMap.get(id);
		const card = el('div', 'mindmap-node');
		card.setAttribute('data-id', id);
		card.setAttribute('data-kind', node.kind);
		card.setAttribute('data-depth', String(depth));
		if (branch !== null && branch !== undefined) card.setAttribute('data-branch', String(branch));

		const content = el('div', 'node-content');
		if (node.kind === 'concept') {
			const titleRow = el('div', 'node-title-row');
			titleRow.append(el('span', 'node-title', node.label));
			if (node.handout_page) titleRow.append(el('span', 'node-page-tag', `P.${node.handout_page}`));
			content.append(titleRow);
		} else if (node.kind === 'meaning') {
			// 單行省略 + 看說明晶片
			const box = el('div', 'node-meaning-box');
			const text = el('span', 'node-truncated-text', node.label);
			text.title = node.label;
			const chip = el('button', 'node-chip-explain', '看說明');
			chip.type = 'button';
			chip.setAttribute('data-node-id', id);
			chip.addEventListener('click', (e) => { e.stopPropagation(); this.openDetailDialog(id); });
			box.append(text, chip);
			content.append(box);
		} else if (node.kind === 'group') {
			content.append(el('span', 'node-title', node.label));
		} else if (node.kind === 'example') {
			const pre = el('pre', 'node-code-block'), code = el('code', '', node.label);
			pre.append(code);
			content.append(pre);
		} else if (node.kind === 'pitfall') {
			const list = el('div', 'pitfall-list');
			for (const line of node.label.split('\n')) {
				const row = el('div', 'pitfall-row');
				let badgeClass = 'pitfall-badge', badgeText = '•', bodyText = line;
				if (line.startsWith('錯：')) { badgeClass += ' pitfall-badge-bad'; badgeText = '錯'; bodyText = line.slice(2); }
				else if (line.startsWith('為什麼：')) { badgeClass += ' pitfall-badge-why'; badgeText = '原因'; bodyText = line.slice(4); }
				else if (line.startsWith('正確：')) { badgeClass += ' pitfall-badge-good'; badgeText = '正確'; bodyText = line.slice(3); }
				row.append(el('span', badgeClass, badgeText), el('span', 'pitfall-text', bodyText));
				list.append(row);
			}
			content.append(list);
		}
		card.append(content);
		return card;
	}

	// 執行算繪與雙階段版面配置
	render(variant = this.currentVariant, initialFit = false) {
		this.currentVariant = variant;
		document.body.className = variant;

		// 更新橫幅與頁籤狀態
		const info = VARIANT_INFO[variant] || VARIANT_INFO['variant-a'];
		document.getElementById('variant-banner-title').textContent = info.title;
		document.getElementById('variant-banner-desc').textContent = info.desc;
		for (const tab of document.querySelectorAll('.tab-button')) {
			const active = tab.getAttribute('data-variant') === variant;
			tab.classList.toggle('active', active);
			tab.setAttribute('aria-selected', String(active));
		}

		// 第一階段：實測未縮放自然尺寸 (Unscaled)
		this.canvas.style.transform = 'none';
		this.nodesContainer.replaceChildren();
		const rootId = this.data.root_id || 'root';
		for (const node of this.data.nodes) {
			const nodeEl = this.createNodeElement(node);
			nodeEl.style.left = '0px';
			nodeEl.style.top = '0px';
			this.nodesContainer.append(nodeEl);
		}

		this.dims.clear();
		for (const nodeEl of this.nodesContainer.querySelectorAll('.mindmap-node')) {
			const id = nodeEl.getAttribute('data-id');
			this.dims.set(id, { w: nodeEl.offsetWidth, h: nodeEl.offsetHeight });
		}

		// 第二階段：後序周遊計算子樹高度
		this.subtreeHeights.clear();
		const calcHeight = (id) => {
			const kids = this.childrenMap.get(id) || [];
			const myH = this.dims.get(id).h;
			if (!kids.length) { this.subtreeHeights.set(id, myH); return myH; }
			let kidsTotal = 0;
			for (let i = 0; i < kids.length; i++) kidsTotal += calcHeight(kids[i]);
			kidsTotal += (kids.length - 1) * this.gapY;
			const subH = Math.max(myH, kidsTotal);
			this.subtreeHeights.set(id, subH);
			return subH;
		};
		calcHeight(rootId);

		// 前序周遊精準安置座標（保證零重疊）
		this.positions.clear();
		const placeNode = (id, x, yStart) => {
			const { w, h } = this.dims.get(id);
			const subH = this.subtreeHeights.get(id);
			const myY = yStart + (subH - h) / 2;
			this.positions.set(id, { x, y: myY, w, h });

			const kids = this.childrenMap.get(id) || [];
			if (kids.length) {
				let totalKids = 0;
				for (const k of kids) totalKids += this.subtreeHeights.get(k);
				totalKids += (kids.length - 1) * this.gapY;
				let curY = yStart + (subH - totalKids) / 2;
				for (const k of kids) {
					placeNode(k, x + w + this.gapX, curY);
					curY += this.subtreeHeights.get(k) + this.gapY;
				}
			}
		};
		placeNode(rootId, 40, 40);

		// 套用實體位置
		for (const nodeEl of this.nodesContainer.querySelectorAll('.mindmap-node')) {
			const pos = this.positions.get(nodeEl.getAttribute('data-id'));
			if (pos) { nodeEl.style.left = `${pos.x}px`; nodeEl.style.top = `${pos.y}px`; }
		}

		this.renderConnectors();
		if (initialFit) this.fitView(); else this.applyCamera();
	}

	// 繪製貝茲曲線連接線
	renderConnectors() {
		let maxX = 0, maxY = 0;
		for (const pos of this.positions.values()) {
			maxX = Math.max(maxX, pos.x + pos.w + 60);
			maxY = Math.max(maxY, pos.y + pos.h + 60);
		}
		this.canvas.style.width = `${maxX}px`;
		this.canvas.style.height = `${maxY}px`;
		this.connectorsSvg.setAttribute('width', String(maxX));
		this.connectorsSvg.setAttribute('height', String(maxY));
		this.connectorsSvg.replaceChildren();

		const isVariantC = this.currentVariant === 'variant-c';
		for (const [parentId, kids] of this.childrenMap.entries()) {
			const pPos = this.positions.get(parentId), pNode = this.nodesMap.get(parentId);
			if (!pPos) continue;
			for (const childId of kids) {
				const cPos = this.positions.get(childId), cNode = this.nodesMap.get(childId);
				if (!cPos) continue;
				const branch = this.branchMap.get(childId);
				let x1 = pPos.x + pPos.w, y1 = pPos.y + pPos.h / 2;
				let x2 = cPos.x, y2 = cPos.y + cPos.h / 2;

				if (isVariantC) {
					if (cNode.kind !== 'concept') y2 = cPos.y + cPos.h - 1.25;
					if (pNode.kind !== 'concept') y1 = pPos.y + pPos.h - 1.25;
				}

				const dx = x2 - x1, cx1 = x1 + dx * 0.45, cx2 = x2 - dx * 0.45;
				const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
				path.setAttribute('d', `M ${x1} ${y1} C ${cx1} ${y1}, ${cx2} ${y2}, ${x2} ${y2}`);
				path.setAttribute('data-from', parentId);
				path.setAttribute('data-to', childId);
				if (branch !== null && branch !== undefined) path.setAttribute('data-branch', String(branch));
				this.connectorsSvg.append(path);
			}
		}
	}

	// 鏡頭控制
	applyCamera(animate = false) {
		if (animate) {
			this.canvas.classList.add('smooth-transition');
			setTimeout(() => this.canvas.classList.remove('smooth-transition'), 250);
		} else {
			this.canvas.classList.remove('smooth-transition');
		}
		this.canvas.style.transform = `translate(${this.camera.x}px, ${this.camera.y}px) scale(${this.camera.scale})`;
	}

	fitView() {
		let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
		for (const pos of this.positions.values()) {
			minX = Math.min(minX, pos.x); minY = Math.min(minY, pos.y);
			maxX = Math.max(maxX, pos.x + pos.w); maxY = Math.max(maxY, pos.y + pos.h);
		}
		const pad = 48, treeW = (maxX - minX) + pad * 2, treeH = (maxY - minY) + pad * 2;
		const viewW = this.viewport.clientWidth || 1200, viewH = this.viewport.clientHeight || 800;
		const targetScale = Math.min(1.0, Math.max(0.45, Math.min(viewW / treeW, viewH / treeH)));

		this.camera.scale = targetScale;
		this.camera.x = Math.max(20, (viewW - treeW * targetScale) / 2 + pad * targetScale);
		this.camera.y = Math.max(20, (viewH - treeH * targetScale) / 2 + pad * targetScale);
		this.applyCamera(true);
	}

	resetView() {
		this.camera.scale = 1.0; this.camera.x = 40; this.camera.y = 40;
		this.applyCamera(true);
	}

	zoomBy(factor) {
		const newScale = Math.max(0.35, Math.min(2.0, this.camera.scale * factor));
		const cx = this.viewport.clientWidth / 2, cy = this.viewport.clientHeight / 2;
		this.camera.x = cx - (cx - this.camera.x) * (newScale / this.camera.scale);
		this.camera.y = cy - (cy - this.camera.y) * (newScale / this.camera.scale);
		this.camera.scale = newScale;
		this.applyCamera(true);
	}

	// 概念詳情對話框操作
	openDetailDialog(nodeId) {
		const node = this.nodesMap.get(nodeId);
		if (!node) return;
		const kindMap = { concept: '概念重點', meaning: '概念詳細說明', group: '群組分類', example: '範例程式碼', pitfall: '常見錯誤叮嚀' };
		document.getElementById('dialog-kind').textContent = kindMap[node.kind] || '詳細解說';
		document.getElementById('dialog-title').textContent = this.parentMap.has(nodeId) ? this.nodesMap.get(this.parentMap.get(nodeId)).label : node.label;
		document.getElementById('dialog-text').textContent = node.label;

		const quoteSec = document.getElementById('dialog-quote-section');
		if (node.source_quote) {
			document.getElementById('dialog-quote').textContent = node.source_quote;
			quoteSec.hidden = false;
		} else quoteSec.hidden = true;

		const pageMeta = document.getElementById('dialog-page-meta');
		if (node.handout_page) {
			document.getElementById('dialog-page-tag').textContent = `講義第 ${node.handout_page} 頁`;
			pageMeta.hidden = false;
		} else pageMeta.hidden = true;

		this.dialog.showModal();
	}

	setupEventListeners() {
		for (const tab of document.querySelectorAll('.tab-button')) {
			tab.addEventListener('click', () => this.render(tab.getAttribute('data-variant'), false));
		}
		document.getElementById('btn-fit').addEventListener('click', () => this.fitView());
		document.getElementById('btn-reset').addEventListener('click', () => this.resetView());
		document.getElementById('btn-zoom-in').addEventListener('click', () => this.zoomBy(1.2));
		document.getElementById('btn-zoom-out').addEventListener('click', () => this.zoomBy(0.8));
		document.getElementById('dialog-close').addEventListener('click', () => this.dialog.close());
		this.dialog.addEventListener('click', (e) => { if (e.target === this.dialog) this.dialog.close(); });

		// 畫布拖曳平移
		this.viewport.addEventListener('pointerdown', (e) => {
			if (e.button !== 0 || e.target.closest('button, dialog')) return;
			this.isDragging = true;
			this.viewport.setPointerCapture(e.pointerId);
			this.dragStart = { x: e.clientX, y: e.clientY, cx: this.camera.x, cy: this.camera.y, moved: false };
		});
		this.viewport.addEventListener('pointermove', (e) => {
			if (!this.isDragging) return;
			const dx = e.clientX - this.dragStart.x, dy = e.clientY - this.dragStart.y;
			if (!this.dragStart.moved && Math.hypot(dx, dy) > 4) this.dragStart.moved = true;
			if (this.dragStart.moved) {
				this.camera.x = this.dragStart.cx + dx;
				this.camera.y = this.dragStart.cy + dy;
				this.applyCamera(false);
			}
		});
		const stopDrag = () => { this.isDragging = false; };
		this.viewport.addEventListener('pointerup', stopDrag);
		this.viewport.addEventListener('pointercancel', stopDrag);

		// 滾輪平滑縮放
		this.viewport.addEventListener('wheel', (e) => {
			e.preventDefault();
			const rect = this.viewport.getBoundingClientRect();
			const mx = e.clientX - rect.left, my = e.clientY - rect.top;
			const factor = Math.exp(-e.deltaY * 0.0018);
			const newScale = Math.max(0.35, Math.min(2.2, this.camera.scale * factor));
			this.camera.x = mx - (mx - this.camera.x) * (newScale / this.camera.scale);
			this.camera.y = my - (my - this.camera.y) * (newScale / this.camera.scale);
			this.camera.scale = newScale;
			this.applyCamera(false);
		}, { passive: false });

		let resizeTimer = null;
		window.addEventListener('resize', () => {
			clearTimeout(resizeTimer);
			resizeTimer = setTimeout(() => this.render(this.currentVariant, false), 150);
		});
	}
}

window.addEventListener('DOMContentLoaded', () => {
	const viewer = new MindMapViewer();
	viewer.init();
	window.__mindMapViewer = viewer;
});
