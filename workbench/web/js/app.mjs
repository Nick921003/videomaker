import { parseRoute } from './router.mjs';
import { api } from './api.mjs';
import { el } from './ui.mjs';
import { initRail } from './navigation.mjs';
import { renderOverview } from './pages/overview.mjs';
import { renderRoadmap } from './pages/roadmap.mjs';
import { renderPipelines } from './pages/pipelines.mjs';
import { renderMake } from './pages/make.mjs';
import { renderLibrary } from './pages/library.mjs';
import { renderUsage } from './pages/usage.mjs';

const PAGE_NAMES = {
	overview: '總覽', make: '製作', pipelines: '流程架構',
	library: '素材庫', usage: '用量', roadmap: '路線圖',
};
let renderVersion = 0;
let pollingQueue = false;
let activePage = null;

function message(title, text, advice = '') {
	const panel = el('section', 'message-panel scroll-box');
	panel.append(el('p', 'eyebrow', '多元教材工作台'), el('h1', '', title), el('p', '', text));
	if (advice) panel.append(el('p', 'message-advice', advice));
	return panel;
}

export async function loadRoute() {
	const host = document.getElementById('page-host');
	if (!host) return;
	const version = ++renderVersion;
	activePage?.dispose?.();
	activePage = null;
	const route = parseRoute(globalThis.location.hash);
	for (const link of document.querySelectorAll('.rail-nav-item')) {
		const active = link.getAttribute('data-page') === route.page;
		link.classList.toggle('active', active);
		if (active) link.setAttribute('aria-current', 'page');
		else link.removeAttribute('aria-current');
	}
	document.title = `${PAGE_NAMES[route.page]} · 多元教材工作台`;
	host.setAttribute('aria-busy', 'true');
	const loading = message('讀取中', '等一下，教材馬上就來。');
	loading.setAttribute('role', 'status');
	host.replaceChildren(loading);
	try {
		const page = route.page === 'overview' ? await renderOverview()
			: route.page === 'roadmap' ? await renderRoadmap()
				: route.page === 'pipelines' ? await renderPipelines(route.query)
					: route.page === 'make' ? await renderMake(route)
						: route.page === 'library' ? await renderLibrary() : await renderUsage();
		// 舊頁請求晚回來時，保留使用者剛切換的頁面。
		if (version === renderVersion) {
			host.replaceChildren(page);
			activePage = page;
			page.mount?.();
		} else page.dispose?.();
	} catch (error) {
		if (version !== renderVersion) return;
		const panel = message('資料還沒讀進來', error.reason ?? '暫時連不上工作台。', error.advice ?? '請稍後再試。');
		panel.setAttribute('role', 'alert');
		const retry = el('button', 'button button-primary', '再試一次');
		retry.type = 'button';
		retry.addEventListener('click', loadRoute);
		panel.append(retry);
		host.replaceChildren(panel);
	} finally {
		if (version === renderVersion) host.setAttribute('aria-busy', 'false');
	}
}

export async function pollQueueDot() {
	const dot = document.getElementById('rail-queue-dot');
	if (!dot || pollingQueue) return;
	pollingQueue = true;
	try {
		const queue = await api.get('/queue');
		const busy = Boolean(queue.running || queue.queued.length);
		dot.hidden = !busy;
		const status = document.getElementById('queue-status');
		if (status) status.textContent = busy ? '有工作正在製作或排隊' : '';
		document.dispatchEvent(new CustomEvent('workbench:queue', { detail: queue }));
	} catch {
		// 短暫斷線時沿用上次狀態，下次輪詢再更新。
	} finally {
		pollingQueue = false;
	}
}

function start() {
	initRail();
	document.getElementById('brand-mock-badge').hidden = !api.MOCK;
	document.getElementById('skip-link').addEventListener('click', event => {
		event.preventDefault();
		document.getElementById('main-viewport').focus();
	});
	globalThis.addEventListener('hashchange', loadRoute);
	loadRoute();
	pollQueueDot();
	let timer = setInterval(pollQueueDot, 3000);
	globalThis.addEventListener('pagehide', () => clearInterval(timer));
	globalThis.addEventListener('pageshow', event => {
		if (event.persisted) {
			loadRoute();
			pollQueueDot();
			timer = setInterval(pollQueueDot, 3000);
		}
	});
}

if (globalThis.document) {
	if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
	else start();
}
