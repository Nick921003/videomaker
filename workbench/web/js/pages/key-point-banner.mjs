import { el } from '../ui.mjs';
import { button } from '../viewers/common.mjs';

export const REVIEW_REASON = '這份教材的學習目標是 AI 推論的，需要先確認';
export const NOTE_LIMIT = 200;

function row(cells, tag = 'td') {
	const tr = el('tr');
	for (const cell of cells) tr.append(el(tag, '', String(cell ?? '')));
	return tr;
}

function table(headers, rows) {
	const node = el('table', 'key-point-table');
	const head = el('thead');
	head.append(row(headers, 'th'));
	const body = el('tbody');
	for (const cells of rows) body.append(row(cells));
	node.append(head, body);
	return node;
}

// 橫幅只負責呈現與收集操作；請求與重新讀取由頁面決定，避免兩邊各管一份狀態。
export function renderKeyPointBanner(data, { busy, message, note, onNote, onConfirm, onReextract }) {
	const banner = el('section', 'key-point-banner');
	banner.setAttribute('role', 'region');
	banner.setAttribute('aria-label', '重點清單檢查');
	const list = data.key_points ?? {};
	const objectives = list.objectives ?? [];
	const points = list.points ?? [];
	banner.append(el('p', 'key-point-banner-message', '這份教材的學習目標是 AI 推論的，請確認'));
	const details = el('details', 'key-point-details');
	details.append(el('summary', '', `檢視重點清單（${objectives.length} 個學習目標、${points.length} 個重點）`));
	details.append(
		table(['學習目標', '來源'], objectives.map(item => [item.text, item.inferred ? '推論' : '教材'])),
		table(['重點', '問題', '對應目標', '類型'], points.map(point => [point.title, point.question,
			point.objectives?.length ? point.objectives.join('、') : '補充', point.type])),
	);
	const controls = el('div', 'key-point-actions');
	const confirm = button('確認', 'button-primary');
	confirm.disabled = busy;
	confirm.addEventListener('click', onConfirm);
	const field = el('label', 'key-point-note-field', '重新抽取備註（選填）');
	const input = el('input', 'key-point-note');
	input.type = 'text';
	input.value = note;
	input.disabled = busy;
	input.setAttribute('aria-label', '重新抽取備註');
	input.addEventListener('input', () => onNote(input.value));
	field.append(input);
	const reextract = button('重新抽取');
	reextract.disabled = busy;
	reextract.addEventListener('click', () => onReextract(input.value.trim()));
	controls.append(confirm, field, reextract);
	const status = el('p', 'key-point-message', message);
	status.setAttribute('role', 'status');
	banner.append(details, controls, status);
	return banner;
}
