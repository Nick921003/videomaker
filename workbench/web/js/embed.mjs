import { api } from './api.mjs';
import { el, money } from './ui.mjs';
import * as video from './viewers/video.mjs';
import * as svg from './viewers/svg.mjs';
import * as deck from './viewers/deck.mjs';

export function parseEmbedPath(path) {
	const match = String(path).match(/^\/embed\/([^/]+)\/([^/]+)\/?$/);
	if (!match) return null;
	try { return { unit: decodeURIComponent(match[1]), item: decodeURIComponent(match[2]) }; }
	catch { return null; }
}

export async function mountEmbed(host, path = globalThis.location?.pathname) {
	const route = parseEmbedPath(path);
	if (!route) throw new Error('這個成品連結讀不到。');
	const manifest = await api.get(`/units/${encodeURIComponent(route.unit)}/manifest`);
	const product = manifest.products.find(item => item.item === route.item);
	if (!product) throw new Error('這份成品還沒準備好。');
	const viewer = { video, highlight: video, mindmap: svg, slides: deck }[product.format];
	if (!viewer) throw new Error('這種成品目前無法預覽。');
	document.title = `${product.label} · ${manifest.title}`;
	const heading = el('header', 'embed-heading');
	heading.append(el('h1', '', product.label), el('p', 'section-note', `實際花費 · ${product.cost_usd === null ? '尚未取得' : money(product.cost_usd)}`));
	const slot = el('div', 'viewer-slot');
	host.replaceChildren(heading, slot);
	return viewer.mount(slot, { unit: manifest.unit_id, item: product, files: product.files });
}

const host = globalThis.document?.getElementById?.('embed-host');
if (host) {
	let mounted;
	mountEmbed(host).then(viewer => { mounted = viewer; }).catch(error => {
		const notice = el('p', 'product-error', error.reason ?? error.message);
		notice.setAttribute('role', 'alert');
		host.replaceChildren(notice);
	});
	globalThis.addEventListener('pagehide', () => mounted?.dispose(), { once: true });
}
