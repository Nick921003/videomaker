import { api } from '../api.mjs';
import { el, money } from '../ui.mjs';
import { go } from '../router.mjs';
import { button } from '../viewers/common.mjs';
import * as video from '../viewers/video.mjs';
import * as svg from '../viewers/svg.mjs';
import * as deck from '../viewers/deck.mjs';

export function warningBeats(warnings = []) {
	return [...new Set(warnings.filter(warning => warning.code === 'tts_missing')
		.map(warning => Number(warning.detail.match(/第\s*(\d+)\s*句/)?.[1])).filter(beat => Number.isSafeInteger(beat) && beat > 0))];
}

export function renderMakeProducts(unit, { query = {} } = {}) {
	const content = el('section', 'make-card make-products');
	const tabs = el('div', 'source-tabs product-tabs');
	tabs.setAttribute('role', 'tablist');
	tabs.setAttribute('aria-label', '成品形式');
	const bar = el('div', 'product-summary');
	const title = el('h2');
	const cost = el('p', 'section-note');
	const pagination = el('div', 'product-pagination');
	const previous = button('上一點');
	const next = button('下一點');
	const counter = el('span', 'section-note');
	pagination.append(previous, counter, next);
	bar.append(title, cost, pagination);
	const panel = el('section', 'product-panel');
	panel.setAttribute('role', 'tabpanel');
	const host = el('div', 'product-viewer');
	const notices = el('div', 'product-notices scroll-box');
	notices.setAttribute('aria-live', 'polite');
	panel.append(host, notices);
	content.append(tabs, bar, panel);
	const formats = ['video', 'highlight', 'mindmap', 'slides'];
	const viewers = { video, highlight: video, mindmap: svg, slides: deck };
	const ready = unit.items.filter(item => item.status === 'done' && Object.keys(item.files ?? {}).length);
	let active = formats.find(format => ready.some(item => item.format === format)) ?? 'video';
	let index = 0;
	let viewer;
	let controller;
	let revision = 0;
	let disposed = false;
	let mounted = false;
	let busy = false;
	const buttons = [];
	function selected() { return ready.filter(item => item.format === active)[index]; }
	function renderWarnings(item) {
		notices.replaceChildren();
		for (const beat of warningBeats(item.warnings)) {
			const notice = el('div', 'product-warning');
			const retry = button('重配這句');
			retry.disabled = busy;
			notice.append(el('p', '', `第 ${beat} 句可能漏唸（檢查也可能誤判，請聽一下）`), retry);
			retry.addEventListener('click', async () => {
				if (busy || disposed) return;
				busy = true;
				renderWarnings(item);
				try {
					const result = await api.post(`/units/${encodeURIComponent(unit.unit_id)}/items/${encodeURIComponent(item.item)}/renarrate`, { beats: [beat] });
					if (!disposed) go('make', 3, { unit: unit.unit_id, job: result.job_id, ...(query.state ? { state: query.state } : {}) });
				} catch (error) {
					if (!disposed) notices.append(el('p', 'product-error', `${error.reason ?? error.message} ${error.advice ?? ''}`));
				} finally {
					busy = false;
					for (const node of notices.querySelectorAll('button')) node.disabled = false;
				}
			});
			notices.append(notice);
		}
		for (const warning of item.warnings ?? []) if (warning.code !== 'tts_missing') notices.append(el('p', 'product-warning', warning.detail));
	}
	async function show(focus = false) {
		const version = ++revision;
		controller?.abort();
		viewer?.dispose();
		viewer = null;
		for (const [i, tab] of buttons.entries()) {
			const current = formats[i] === active;
			tab.setAttribute('aria-selected', String(current));
			tab.tabIndex = current ? 0 : -1;
			if (current) panel.setAttribute('aria-labelledby', tab.id);
		}
		const items = ready.filter(item => item.format === active);
		const item = selected();
		pagination.hidden = active !== 'video' || !items.length;
		previous.disabled = index === 0;
		next.disabled = index >= items.length - 1;
		counter.textContent = `${index + 1} / ${items.length}`;
		title.textContent = item?.label ?? '這個形式還沒生成。';
		cost.textContent = item ? `實際花費 · ${item.cost_usd === null ? '尚未取得' : money(item.cost_usd)}` : '';
		const slot = el('div', 'viewer-slot');
		host.replaceChildren(slot);
		notices.replaceChildren();
		if (!item) {
			const generate = button('去選要生成的 →', 'button-primary');
			generate.addEventListener('click', () => go('make', 3, { unit: unit.unit_id, ...(query.state ? { state: query.state } : {}) }));
			slot.append(el('p', 'section-note', '到③勾選這個形式，就能加入製作佇列。'), generate);
			return;
		}
		renderWarnings(item);
		if (!mounted) return;
		controller = new AbortController();
		try {
			const result = await viewers[active].mount(slot, { unit, item, files: item.files, signal: controller.signal });
			if (disposed || version !== revision) result.dispose();
			else { viewer = result; if (focus) viewer.focus?.(); }
		} catch (error) {
			if (!disposed && version === revision && error.name !== 'AbortError') slot.replaceChildren(el('p', 'product-error', error.reason ?? error.message));
		}
	}
	for (const [i, label] of ['每點影片', '重點片', '心智圖', '簡報'].entries()) {
		const tab = button(label, 'source-tab');
		tab.id = `product-tab-${formats[i]}`;
		tab.setAttribute('role', 'tab');
		tab.setAttribute('aria-controls', 'product-panel');
		tab.addEventListener('click', () => { active = formats[i]; index = 0; show(true); });
		tab.addEventListener('keydown', event => {
			if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
			event.preventDefault();
			event.stopPropagation();
			const target = event.key === 'Home' ? 0 : event.key === 'End' ? 3 : (i + (event.key === 'ArrowRight' ? 1 : 3)) % 4;
			active = formats[target]; index = 0; show(); buttons[target].focus();
		});
		buttons.push(tab);
		tabs.append(tab);
	}
	panel.id = 'product-panel';
	previous.addEventListener('click', () => { if (index > 0) { index--; show(); } });
	next.addEventListener('click', () => { if (index < ready.filter(item => item.format === active).length - 1) { index++; show(); } });
	show();
	content.mount = () => { if (!disposed && !mounted) { mounted = true; show(); } };
	content.dispose = () => { disposed = true; revision++; controller?.abort(); viewer?.dispose(); };
	return content;
}
