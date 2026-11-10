'use strict';
// 圖示（鉛筆皮膚）：筆畫來自共用的 IconShapes，這裡只負責縮放、分配進度、交給 api.ink。
// draw／show 照筆順畫出，blink 亮暗交替，erase 把筆畫倒著收回去。
(() => {
	const S = window.IconShapes;
	const SIZES = {s: 96, m: 140, l: 200};
	const CAP = {size: 32, gap: 8};
	const capH = CAP.size * 1.3;
	// 筆寬以 m（140）為基準，隨圖示大小等比
	const WIDTH = {main: 5, detail: 3.5};
	const DIM = .25;
	// 鍵帽面板在 100 格內的位置（見 shapes.js 的 keycap）
	const FACE = {cx: 50, cy: 45, w: 56, h: 46};

	const px = obj => SIZES[obj.size || 'm'];
	// 組合鍵（Ctrl+C）的格子比 100 寬，圖示跟著變寬；其餘都是正方形
	const shapeOf = obj => S.strokes(obj.name, {text: obj.text});
	const pxW = obj => Math.round(px(obj) * (shapeOf(obj).w || 100) / 100);
	const capStyle = api => ({size: CAP.size, weight: 400, color: api.color('text.muted'), align: 'center'});
	const toneColor = (obj, api) => api.color(window.BOARD_DATA.tones.board[obj.tone || 'ink']);
	const dist = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);
	const length = pts => pts.slice(1).reduce((n, q, i) => n + dist(pts[i], q), 0);
	const period = () => window.BOARD_DATA.catalog.types.icon.actions.blink.period;

	Board.register('icon', {
		measure(obj, api) {
			const size = px(obj), iw = pxW(obj);
			if (!obj.caption) return {w: iw, h: size};
			return {w: Math.max(iw, api.measure(obj.caption, capStyle(api)).w + 24), h: size + CAP.gap + capH};
		},
		state(obj, acts, t) {
			const own = acts.filter(a => a.obj === obj.id);
			// 手帳的 show 當成 draw 來畫；完全沒有畫出類動作的圖示（只被別的動作指到）直接畫完
			const steps = own.filter(a => a.act === 'draw' || a.act === 'show' || a.act === 'erase').sort((a, b) => a.t0 - b.t0);
			let p = steps.length ? 0 : 1, erased = false;
			for (const a of steps) {
				if (a.t0 > t) break;
				const q = Board.clamp((t - a.t0) / Math.max(a.t1 - a.t0, 1e-6));
				p = a.act === 'erase' ? 1 - q : q;
				erased = a.act === 'erase' && q >= 1;
			}
			let blinkOn = true;
			for (const a of own) {
				if (a.act === 'blink' && t >= a.t0 && t < a.t1) blinkOn = Math.floor((t - a.t0) / (period() / 2)) % 2 === 0;
			}
			return {p, blinkOn, erased};
		},
		draw(api, obj, st) {
			const size = px(obj), iw = pxW(obj), w = this.measure(obj, api).w, ox = (w - iw) / 2, k = size / 100, ctx = api.ctx;
			// 框一律記：擦掉之後版位還在，量測也要看得到
			api.record(ox, 0, iw, size, 'panel');
			if (obj.caption) api.write(obj.caption, w / 2, size + CAP.gap + capH / 2, 1, capStyle(api));
			if (st.erased || st.p <= 0) return;
			const shape = shapeOf(obj), color = toneColor(obj, api), seed = Board.seed(obj.id);
			const lens = shape.strokes.map(s => length(s.pts)), total = lens.reduce((a, b) => a + b, 0);
			ctx.save();
			if (!st.blinkOn) ctx.globalAlpha *= DIM;
			let done = 0;
			shape.strokes.forEach((s, i) => {
				// p 到 1 就整筆畫完，不靠浮點相減，免得最後一筆停在 0.9999 而一直抖
				const pi = st.p >= 1 ? 1 : api.clamp((st.p * total - done) / lens[i]);
				done += lens[i];
				api.ink(s.pts.map(([x, y]) => [ox + x * k, y * k]), pi, {color, width: WIDTH[s.w] * size / 140, seed: seed + i});
			});
			const texts = shape.texts || (shape.text ? [{text: shape.text, cx: FACE.cx}] : []);
			if (texts.length) {
				// 字要塞進鍵帽內面板；字太長縮不下的由量測閘的最小字級擋。組合鍵用最長那顆的字級，幾顆字才一樣大
				const unit = Math.max(...texts.map(x => api.measure(x.text, {size: 100, weight: 500}).w / 100));
				const fs = Math.min(FACE.h * k * .8 / 1.25, FACE.w * k * .84 / unit);
				for (const x of texts) api.write(x.text, ox + x.cx * k, FACE.cy * k, api.clamp((st.p - .6) / .4), {size: fs, weight: 500, color, align: 'center'});
			}
			ctx.restore();
		},
		anchors(obj, st, api) {
			if (!obj.caption) return {};
			const size = px(obj), w = this.measure(obj, api).w, cw = api.measure(obj.caption, capStyle(api)).w;
			return {caption: {x: (w - cw) / 2, y: size + CAP.gap, w: cw, h: capH}};
		},
	});
})();
