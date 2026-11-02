// 黑板頁的版面格子：從 printf 片 index.html 的 api.tpl 搬出來的純函式，數值逐字照抄。
// printf 片自己的 index.html 不改（它的畫面已定稿），新片從 starter 開，改呼叫這裡。
(function (g) {
	'use strict';

	// area：一頁標題下的整塊圖區（api.area 的回傳）；center 取 72%×86% 置中，two-col 左右各留 40、兩欄中間 140
	function tpl(A, kind) {
		if (!A) return null;
		if (kind === 'center') {
			var w = Math.round(A.w * 0.72), h = Math.round(A.h * 0.86);
			var x = Math.round(A.x + (A.w - w) / 2), y = Math.round(A.y + (A.h - h) / 2);
			return { P: A.P, x: x, y: y, w: w, h: h, cx: Math.round(x + w / 2), cy: Math.round(y + h / 2) };
		}
		if (kind === 'two-col') {
			var colW = Math.round((A.w - 80 - 140) / 2);
			var lx = A.x + 40, ly = A.y, lh = A.h;
			var rx = lx + colW + 140, ry = A.y, rh = A.h;
			return {
				P: A.P,
				left: { x: lx, y: ly, w: colW, h: lh, cx: Math.round(lx + colW / 2), cy: Math.round(ly + lh / 2) },
				right: { x: rx, y: ry, w: colW, h: rh, cx: Math.round(rx + colW / 2), cy: Math.round(ry + rh / 2) },
				mid: { x: Math.round(lx + colW + 70), y: Math.round(A.y + A.h / 2) }
			};
		}
		return A;
	}

	var X = { tpl: tpl };
	if (typeof module !== 'undefined') module.exports = X; else g.BoardTpl = X;
})(this);
