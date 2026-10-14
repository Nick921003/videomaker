import { api } from '../api.mjs';
import { el, money } from '../ui.mjs';
import { go } from '../router.mjs';
import { button } from '../viewers/common.mjs';
import * as video from '../viewers/video.mjs';
import * as svg from '../viewers/svg.mjs';
import * as deck from '../viewers/deck.mjs';

export function warningBeats(warnings = []) {
	return [...new Set(warnings.filter(warning => ['tts_missing','tts_repeat'].includes(warning.code))
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
	bar.append(title, cost);
	const picker = el('nav', 'product-picker');
	picker.setAttribute('aria-label', '直接選擇成品');
	const panel = el('section', 'product-panel');
	panel.setAttribute('role', 'tabpanel');
	const host = el('div', 'product-viewer');
	const notices = el('div', 'product-notices scroll-box');
	notices.setAttribute('aria-live', 'polite');
	panel.append(host, notices);
	const workspace = el('div', 'product-workspace');
	const main = el('div', 'product-main');
	main.append(bar, panel);
	workspace.append(picker, main);
	content.append(tabs, workspace);
	const formats = ['video', 'highlight', 'mindmap', 'slides'];
	const viewers = { video, highlight: video, mindmap: svg, slides: deck };
	const isReady = item => item?.status === 'done' && Object.keys(item.files ?? {}).length;
	const ready = unit.items.filter(isReady);
	const states = { none: '尚未製作', queued: '排隊中', running: '製作中', failed: '製作失敗', done: '可觀看' };
	let active = formats.find(format => ready.some(item => item.format === format)) ?? 'video';
	let index = Math.max(0, unit.items.filter(item => item.format === active).findIndex(isReady));
	let viewer;
	let controller;
	let revision = 0;
	let disposed = false;
	let mounted = false;
	let busy = false;
	const buttons = [];
	function selected() { return unit.items.filter(item => item.format === active)[index]; }
	function firstReady(format) { return Math.max(0, unit.items.filter(item => item.format === format).findIndex(isReady)); }
	function renderWarnings(item) {
		notices.replaceChildren();
		for (const beat of warningBeats(item.warnings)) {
			const notice = el('div', 'product-warning');
			const retry = button('重配這句');
			retry.disabled = busy;
			const repeat = (item.warnings ?? []).some(warning => warning.code === 'tts_repeat' && warningBeats([warning]).includes(beat));
			notice.append(el('p', '', `第 ${beat} 句可能${repeat ? '重複唸' : '漏唸'}（檢查也可能誤判，請聽一下）`), retry);
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
		for (const warning of item.warnings ?? []) if (!['tts_missing','tts_repeat'].includes(warning.code)) notices.append(el('p', 'product-warning', warning.detail));
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
		workspace.setAttribute("data-active-format", active);
		const items = unit.items.filter(item => item.format === active);
		const item = selected();
		picker.replaceChildren(el('h3', 'product-picker-heading', active === 'video' ? '選擇重點' : '選擇成品'));
		for (const [i, candidate] of items.entries()) {
			const choice = button('', 'product-choice');
			choice.setAttribute('data-product-id', candidate.item);
			choice.setAttribute('aria-pressed', String(i === index));
			const point = unit.analysis?.points?.find(point => point.id === candidate.item);
			choice.append(el('strong', '', point?.title ?? candidate.label), el('span', 'product-choice-state', isReady(candidate) ? '已完成' : states[candidate.status] ?? '尚未製作'));
			choice.addEventListener('click', () => { if (index === i) return; index = i; show('choice'); });
			picker.append(choice);
			if (focus === 'choice' && i === index) choice.focus();
		}
		title.textContent = item?.label ?? '這個形式還沒生成。';
		cost.textContent = isReady(item) ? `實際花費 · ${item.cost_usd === null ? '尚未取得' : money(item.cost_usd)}` : '';
		const slot = el('div', 'viewer-slot');
		host.replaceChildren(slot);
		notices.replaceChildren();
		if (!isReady(item)) {
			const generate = button('去選要生成的 →', 'button-primary');
			generate.addEventListener('click', () => go('make', 3, { unit: unit.unit_id, ...(query.state ? { state: query.state } : {}) }));
			slot.append(el('h3', 'product-empty-title', item ? states[item.status] ?? '尚未製作' : '這個形式還沒生成。'), el('p', 'product-empty-note', '到③選擇要製作的項目。完成後會出現在這裡。'), generate);
			return;
		}
		renderWarnings(item);
		if (!mounted) return;
		controller = new AbortController();
		try {
			const result = await viewers[active].mount(slot, { unit, item, files: item.files, signal: controller.signal });
			if (disposed || version !== revision) result.dispose();
			else { viewer = result; if (focus === true) viewer.focus?.(); }
		} catch (error) {
			if (!disposed && version === revision && error.name !== 'AbortError') slot.replaceChildren(el('p', 'product-error', error.reason ?? error.message));
		}
	}
	for (const [i, label] of ['每點影片', '重點片', '心智圖', '簡報'].entries()) {
		const tab = button(label, 'source-tab');
		tab.id = `product-tab-${formats[i]}`;
		tab.setAttribute('role', 'tab');
		tab.setAttribute('aria-controls', 'product-panel');
		tab.addEventListener('click', () => { active = formats[i]; index = firstReady(active); show(true); });
		tab.addEventListener('keydown', event => {
			if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
			event.preventDefault();
			event.stopPropagation();
			const target = event.key === 'Home' ? 0 : event.key === 'End' ? 3 : (i + (event.key === 'ArrowRight' ? 1 : 3)) % 4;
			active = formats[target]; index = firstReady(active); show(); buttons[target].focus();
		});
		buttons.push(tab);
		tabs.append(tab);
	}
	panel.id = 'product-panel';
	show();
	content.mount = () => { if (!disposed && !mounted) { mounted = true; show(); } };
	content.dispose = () => { disposed = true; revision++; controller?.abort(); viewer?.dispose(); };
	return content;
}
