export const PRIMARY_SAMPLE = Object.freeze({
	id: 'coherent',
	title: '迴圈，是怎麼走回來的？',
	lesson: 'C 語言迴圈：一加到五',
	duration: 48,
	src: '/trials/coherent/out/coherent.mp4',
	chapters: Object.freeze([
		{ id: 'concept', label: '觀念', time: 0 },
		{ id: 'flow', label: '流程', time: 8.4 },
		{ id: 'trace', label: '回到條件', time: 18.3 },
		{ id: 'count', label: '操作次數', time: 31 },
	]),
});

export const COMPONENT_SAMPLES = Object.freeze([
	{ id: 'keynote', title: '一次 HTTP 請求，經過哪些角色？', lesson: 'HTTP 請求流程', style: 'Keynote 卡片' },
	{ id: 'chart', title: '多一層迴圈，操作次數差多少？', lesson: '巢狀迴圈', style: '數據圖表' },
	{ id: 'chalk', title: 'Hello 為什麼需要六格？', lesson: 'C 字串與 NUL', style: '黑板粉筆' },
	{ id: 'drafting', title: '索引如何對應記憶體位址？', lesson: '陣列位址', style: '工程藍圖' },
	{ id: 'formula', title: '位址公式，如何一步步代入？', lesson: '位址計算', style: '公式形變' },
	{ id: 'paper', title: '把同一位學生的資料放在一起', lesson: 'C 結構', style: '紙藝折起' },
].map(sample => Object.freeze({ ...sample, duration: 15, src: `/trials/out/${sample.id}.mp4` })));

export function classifyChatAction(value) {
	const text = String(value).trim();
	if (/^(請)?(重播|重新播放|從頭播放)/.test(text)) return { kind: 'replay', time: 0 };
	if (/(回到|跳到|定位到?).*(條件)|(條件).*(那一段|位置)/.test(text)) {
		return { kind: 'seek', chapter: 'trace', time: 18.3 };
	}
	if (/(另一種|換一種|不同).*(風格|版本)|(風格|版本).*(另一種|換一種|不同)/.test(text)) {
		return { kind: 'reinforce' };
	}
	return { kind: 'ask' };
}
