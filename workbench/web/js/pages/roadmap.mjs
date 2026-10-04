import { api } from '../api.mjs';
import { el, icon, displayName, intro } from '../ui.mjs';

export function extractRoadmap(formatsData = {}) {
	const formats = formatsData?.formats ?? [];
	const planned = formats
		.filter(fmt => fmt.status === 'planned')
		.sort((a, b) => (a.planned_note?.order ?? 99) - (b.planned_note?.order ?? 99));

	return planned;
}

function connection(title, subtitle, paragraphs, iconName) {
	const card = el('article', 'connection-card');
	const heading = el('div', 'connection-heading');
	heading.append(icon(iconName), el('h3', '', title));
	card.append(heading, el('p', 'connection-subtitle', subtitle));
	for (const text of paragraphs) card.append(el('p', '', text));
	return card;
}

export async function renderRoadmap() {
	const registry = await api.get('/formats');
	const planned = extractRoadmap(registry);
	const page = el('section', 'page roadmap-page');
	page.append(intro('讓理解再多一點可能', '接下來，想做這些。', '先做好每種教材，再串起教學現場。'));
	const columns = el('div', 'roadmap-columns');
	const formats = el('section', 'roadmap-panel');
	const heading = el('div', 'section-heading');
	heading.append(el('h2', '', '教材形式'), el('span', 'section-count', '建議順序'));
	const list = el('ol', 'roadmap-list scroll-box');
	list.tabIndex = 0;
	list.setAttribute('aria-label', '規劃中的教材形式');
	for (const [index, format] of planned.entries()) {
		const item = el('li', 'roadmap-item');
		const number = el('span', 'roadmap-number', String(format.planned_note?.order ?? index + 1).padStart(2, '0'));
		number.setAttribute('aria-hidden', 'true');
		const copy = el('div', 'roadmap-copy');
		copy.append(el('h3', '', displayName(format)), el('p', '', format.planned_note?.why ?? '再一起想想，怎麼幫學生理解。'));
		item.append(number, copy);
		list.append(item);
	}
	if (!planned.length) list.append(el('li', 'empty-note', '目前沒有待做的形式。'));
	formats.append(heading, list);
	const integrations = el('section', 'roadmap-panel');
	const integrationHeading = el('div', 'section-heading');
	integrationHeading.append(el('h2', '', '接回教學現場'), el('span', 'section-count', '接口計畫'));
	const connections = el('div', 'connections scroll-box');
	connections.tabIndex = 0;
	connections.setAttribute('role', 'region');
	connections.setAttribute('aria-label', '平台與部落格接入計畫');
	const source = el('div', 'source-note');
	source.append(icon('library'), el('p', '', '素材庫是共同來源。平台與部落格，都從這裡讀取或發布。'));
	connections.append(source,
		connection('BridgeAI 平台', '讓教材回到課程裡', [
			'平台沿用同一套接口。帶上課程與教材來源，再讀取成品清單，把影片、心智圖和簡報嵌回課程。',
			'同一份教材沿用同一份素材。身分、權限與額度交給平台處理。',
		], 'pipelines'),
		connection('BridgeAI Learn 部落格', '先找答案，沒有再生成', [
			'希望所有影片與多元素材都找得到。學生先搜尋，沒有合適的內容才生成，再放上部落格。',
			'靜態部落格更新要重新部署，影片也很占空間。影片可放影音平台或物件儲存，部落格只放連結；要不要改成動態站，之後再決定。',
		], 'overview'),
		connection('接入時再補上', '先留好擴充空間', [
			'完成通知、存取金鑰、可嵌入的網域與匯出目的地，都已預留，之後再實作。',
		], 'planned'),
	);
	integrations.append(integrationHeading, connections);
	columns.append(formats, integrations);
	page.append(columns);
	return page;
}
