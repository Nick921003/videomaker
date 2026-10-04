import { parseRoute } from './router.mjs';
import { api } from './api.mjs';
import { el, icon, intro } from './ui.mjs';
import { renderOverview } from './pages/overview.mjs';
import { renderRoadmap } from './pages/roadmap.mjs';

const PAGE_NAMES = {
	overview: '總覽', make: '製作', pipelines: '流程架構',
	library: '素材庫', usage: '用量', roadmap: '路線圖',
};
const STEP_NAMES = ['教材', '分析結果', '生成', '成品'];
const PLACEHOLDERS = {
	make: '從教材開始，分析學生的問題，再選要做的素材。',
	pipelines: '看看教材從整理、分析到成品，會經過哪些步驟。',
	library: '把完成的素材收在一起，讓學生用問題找到答案。',
	usage: '看看每份教材、每件成品，實際花了多少。',
};
let renderVersion = 0;
let pollingQueue = false;

function placeholder(route) {
	const page = el('section', 'page placeholder-page');
	const title = route.page === 'make' ? `製作 · ${STEP_NAMES[route.step - 1]}` : PAGE_NAMES[route.page];
	page.append(intro('一份教材，慢慢做清楚', title, PLACEHOLDERS[route.page]));
	const region = el('div', 'placeholder-region scroll-box');
	const card = el('div', 'placeholder-card');
	const mark = el('div', 'placeholder-mark');
	mark.append(icon('planned'));
	card.append(mark, el('p', 'eyebrow', '準備中'), el('h2', '', '下一步實作'),
		el('p', 'placeholder-description', '這一頁還在準備。先看看可用的形式，或接下來想做的事。'));
	const actions = el('div', 'placeholder-actions');
	const overview = el('a', 'button button-primary', '回到總覽');
	overview.href = '#/overview';
	const roadmap = el('a', 'button', '看看路線圖');
	roadmap.href = '#/roadmap';
	actions.append(overview, roadmap);
	card.append(actions);
	region.append(card);
	page.append(region);
	return page;
}

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
			: route.page === 'roadmap' ? await renderRoadmap() : placeholder(route);
		// 舊頁請求晚回來時，保留使用者剛切換的頁面。
		if (version === renderVersion) host.replaceChildren(page);
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
	} catch {
		// 短暫斷線時沿用上次狀態，下次輪詢再更新。
	} finally {
		pollingQueue = false;
	}
}

function start() {
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
