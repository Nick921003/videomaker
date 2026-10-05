import { el } from '../ui.mjs';
import { viewerTools, panViewer, readFile } from './common.mjs';

export function svgBounds(svg) {
	const parts = (svg.getAttribute('viewBox') ?? '').trim().split(/[\s,]+/).map(Number);
	if (parts.length === 4 && parts.every(Number.isFinite) && parts[2] > 0 && parts[3] > 0) {
		return { x: parts[0], y: parts[1], w: parts[2], h: parts[3] };
	}
	return { x: 0, y: 0, w: parseFloat(svg.getAttribute('width')) || 960, h: parseFloat(svg.getAttribute('height')) || 540 };
}

export async function mount(host, { unit, item, files, signal }) {
	const root = el('section', 'viewer viewer-svg');
	const toolbar = viewerTools(root);
	const viewport = el('div', 'viewer-viewport');
	root.append(viewport);
	host.replaceChildren(root);
	const source = await readFile(unit, files, 'svg', signal);
	signal?.throwIfAborted();
	const parsed = new DOMParser().parseFromString(source, 'image/svg+xml');
	const original = parsed.documentElement;
	if (original.localName !== 'svg' || parsed.querySelector('parsererror')) throw new Error('心智圖的格式讀不到。');
	// 只把靜態圖形帶進文件，不執行 SVG 中的程式或外部內容。
	for (const node of original.querySelectorAll('script, foreignObject, iframe, object, embed, style, animate, animateTransform, set')) node.remove();
	for (const node of [original, ...original.querySelectorAll('*')]) {
		for (const attribute of [...node.attributes]) {
			if (/^on/i.test(attribute.name) || /href$/i.test(attribute.name) && !attribute.value.startsWith('#')
				|| /url\(\s*['"]?(?!#)/i.test(attribute.value)) node.removeAttribute(attribute.name);
		}
	}
	const bounds = svgBounds(original);
	const svg = document.importNode(original, true);
	svg.removeAttribute('viewBox');
	svg.removeAttribute('aria-labelledby');
	svg.setAttribute('class', 'diagram-svg');
	svg.setAttribute('width', '100%');
	svg.setAttribute('height', '100%');
	svg.setAttribute('tabindex', '0');
	svg.setAttribute('role', 'img');
	svg.setAttribute('aria-label', `${typeof item === 'string' ? '心智圖' : item.label}，滾輪縮放、拖曳移動`);
	svg.setAttribute('data-bounds', JSON.stringify(bounds));
	const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
	group.setAttribute('data-panzoom-content', '');
	group.append(...svg.childNodes);
	svg.append(group);
	viewport.append(svg);
	const controls = panViewer(svg, root, toolbar);
	return { focus() { svg.focus(); }, dispose() { controls.destroy(); } };
}
