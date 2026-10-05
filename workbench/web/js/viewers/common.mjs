import { api } from '../api.mjs';
import { el } from '../ui.mjs';
import { attach } from '../panzoom.mjs';

export function button(label, className = '') {
	const node = el('button', `button ${className}`.trim(), label);
	node.type = 'button';
	return node;
}

export function fileURL(unit, path, kind) {
	if (!path) throw new Error('這份成品的檔案還沒準備好。');
	if (api.MOCK && ['svg', 'deck', 'video', 'pptx'].includes(kind)) {
		return new URL(`../../mock/${{ svg: 'mindmap.svg', deck: 'deck.json', video: 'preview.mp4', pptx: 'preview.pptx' }[kind]}`, import.meta.url).href;
	}
	const id = typeof unit === 'string' ? unit : unit.unit_id;
	return `/media/${encodeURIComponent(id)}/${String(path).split('/').map(encodeURIComponent).join('/')}`;
}

export async function readFile(unit, files, kind, signal) {
	const response = await fetch(fileURL(unit, files[kind], kind), { signal });
	if (!response.ok) throw new Error('成品暫時讀不到，請稍後再試。');
	return kind === 'deck' ? response.json() : response.text();
}

export function viewerTools(root) {
	const toolbar = el('div', 'source-diagram-controls viewer-tools');
	for (const [label, action, name] of [['−', 'zoomOut', '縮小'], ['＋', 'zoomIn', '放大'], ['符合視窗', 'fit'], ['全螢幕', 'fullscreen']]) {
		const control = button(label);
		control.setAttribute('data-viewer-action', action);
		if (name) control.setAttribute('aria-label', name);
		toolbar.append(control);
	}
	root.append(toolbar);
	return toolbar;
}

export function panViewer(viewport, root, toolbar, options = {}) {
	const controls = attach(viewport, { ...options, fullscreenElement: root });
	const handlers = [];
	for (const control of toolbar.children) {
		const action = control.getAttribute('data-viewer-action');
		if (!action) continue;
		const handler = async () => {
			try { await controls[action](); }
			catch { root.setAttribute('aria-label', '瀏覽器目前無法開啟全螢幕。'); }
		};
		control.addEventListener('click', handler);
		handlers.push(() => control.removeEventListener('click', handler));
	}
	controls.fit();
	return { ...controls, destroy() { handlers.forEach(remove => remove()); controls.destroy(); } };
}
