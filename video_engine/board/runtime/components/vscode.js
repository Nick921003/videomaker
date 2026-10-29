'use strict';
// 手帳轉接：VS Code 元件的版面、狀態、繪圖指令都在 video_engine/components/vscode/，這裡只把指令畫成鉛筆筆觸。
(() => {
	const M = window.VSCodeModel, P = window.VSCodePaint;
	const MAP = window.BOARD_DATA.tones.vscode_to_board;
	const ALIGN = {middle: 'center', end: 'right'};
	// 手帳把整個畫面縮進半頁，字要放大才過得了量測閘的最小字級
	const TEXT = 1.6;
	const big = obj => Object.assign({}, obj, {_text: TEXT});

	Board.register('vscode', {
		measure() { return {w: M.SIZE[0], h: M.SIZE[1]}; },
		state(obj, acts, t) { return M.state(big(obj), acts, t); },
		anchors(obj, st) { return M.anchors(big(obj), st); },
		draw(api, obj, st, t) {
			const col = key => api.color(MAP[key]);
			P.ops(big(obj), st, t).forEach((o, i) => {
				const seed = Board.seed(obj.id + i);
				if (o.op === 'rect') {
					const edge = o.stroke ? col(o.stroke) : col(o.fill);
					// 只有最外層底色算元件框，其餘色塊不進量測閘（框內本來就層層相疊）
					api.rect(o.x, o.y, o.w, o.h, 1, {fill: o.fill ? col(o.fill) : null, color: edge, width: o.stroke ? (o.width || 2) : 1, seed, role: i === 0 ? 'panel' : null});
				} else if (o.op === 'text') {
					if (o.detail) return;
					api.text(o.str, o.x, o.y, {size: o.size, mono: o.mono, weight: o.bold ? 600 : 400, color: col(o.color), align: ALIGN[o.align], alpha: o.alpha});
				} else if (o.op === 'line') {
					api.ink(o.pts, 1, {color: col(o.color), width: o.width, seed});
				}
			});
		},
	});
})();
