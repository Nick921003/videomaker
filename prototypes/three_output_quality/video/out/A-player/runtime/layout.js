'use strict';
// 版面樹與鏡頭。純函式：輸入尺寸與樹，輸出世界座標；不讀 DOM、不畫圖。
Board.layout = (() => {
	const {W, VIEW, clamp} = Board;
	const REGION_GAP = 220;
	const PAD = {l: 170, r: 170, t: 120, b: 56};
	const GAP = {stack: 60, row: 96};
	const SCALE_MAX = 1.25, SCALE_MIN = .55, ZOOM_MAX = 1.5;

	function region(i) { return {x: 0, y: i * (VIEW.h + REGION_GAP), w: W, h: VIEW.h}; }
	function content(i) {
		const r = region(i);
		return {x: r.x + PAD.l, y: r.y + PAD.t, w: r.w - PAD.l - PAD.r, h: r.h - PAD.t - PAD.b};
	}
	function sizeOf(node, sizes) {
		if (typeof node === 'string') return sizes[node];
		const [kind, kids] = Object.entries(node)[0];
		const ss = kids.map(k => sizeOf(k, sizes)), gap = GAP[kind] * (kids.length - 1);
		return kind === 'stack'
			? {w: Math.max(...ss.map(s => s.w)), h: ss.reduce((a, s) => a + s.h, 0) + gap}
			: {w: ss.reduce((a, s) => a + s.w, 0) + gap, h: Math.max(...ss.map(s => s.h))};
	}
	// 節點盒子左上角在 (x,y)、整體縮放 s；子節點在交叉軸置中
	function place(node, x, y, s, sizes, out) {
		const size = sizeOf(node, sizes);
		if (typeof node === 'string') { out[node] = {x, y, w: size.w * s, h: size.h * s, s}; return; }
		const [kind, kids] = Object.entries(node)[0];
		let cursor = kind === 'stack' ? y : x;
		for (const k of kids) {
			const ks = sizeOf(k, sizes);
			if (kind === 'stack') { place(k, x + (size.w - ks.w) * s / 2, cursor, s, sizes, out); cursor += (ks.h + GAP.stack) * s; }
			else { place(k, cursor, y + (size.h - ks.h) * s / 2, s, sizes, out); cursor += (ks.w + GAP.row) * s; }
		}
	}
	function solve(tree, sizes, regionIndex) {
		if (!tree) return {scale: 1, rects: {}};
		const c = content(regionIndex), size = sizeOf(tree, sizes);
		// 放不下就縮；縮到下限以下照樣縮（不准出界），由量測閘回報失敗
		const s = Math.min(SCALE_MAX, c.w / size.w, c.h / size.h);
		const rects = {};
		place(tree, c.x + (c.w - size.w * s) / 2, c.y + (c.h - size.h * s) / 2, s, sizes, rects);
		return {scale: s, rects};
	}
	function defaultView(i) { const r = region(i); return {cx: r.x + r.w / 2, cy: r.y + r.h / 2, z: 1}; }
	function focusView(rect, i) {
		const r = region(i);
		const z = clamp(Math.min(VIEW.w * .55 / rect.w, VIEW.h * .55 / rect.h), 1, ZOOM_MAX);
		const hw = VIEW.w / 2 / z, hh = VIEW.h / 2 / z;
		return {
			cx: clamp(rect.x + rect.w / 2, r.x + hw, r.x + r.w - hw),
			cy: clamp(rect.y + rect.h / 2, r.y + hh, r.y + r.h - hh), z,
		};
	}
	function mixView(a, b, p) {
		// 縮放在對數空間插值，推近拉遠的速度才均勻
		const z = Math.exp(Board.mix(Math.log(a.z), Math.log(b.z), p));
		return {cx: Board.mix(a.cx, b.cx, p), cy: Board.mix(a.cy, b.cy, p), z};
	}
	function applyView(ctx, v) {
		ctx.translate(VIEW.x + VIEW.w / 2, VIEW.y + VIEW.h / 2);
		ctx.scale(v.z, v.z);
		ctx.translate(-v.cx, -v.cy);
	}
	return {REGION_GAP, PAD, SCALE_MIN, region, content, sizeOf, solve, defaultView, focusView, mixView, applyView};
})();
