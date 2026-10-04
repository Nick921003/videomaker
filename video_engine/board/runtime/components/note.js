'use strict';
// 文字：問句、提示、字面值。也是所有缺口的退化目標，所以不能依賴任何其他元件。
(() => {
	const STYLES = {
		headline: {size: 80, weight: 600, color: 'text.title'},
		body: {size: 48, weight: 400, color: 'text.body'},
		accent: {size: 54, weight: 500, color: 'text.accent', underline: true},
		code: {size: 76, weight: 400, color: 'text.body', mono: true},
		small: {size: 32, weight: 400, color: 'text.muted'},
	};
	const style = obj => STYLES[obj.style] || STYLES.body;
	const lines = obj => String(obj.text).split('\n');
	const LINE = 1.3, PAD_X = 12, UNDER = 30;

	Board.register('note', {
		measure(obj, api) {
			const s = style(obj), rows = lines(obj);
			const w = Math.max(...rows.map(r => api.measure(r, s).w)) + PAD_X * 2;
			return {w, h: rows.length * s.size * LINE + (s.underline ? UNDER : 0)};
		},
		state(obj, acts, t) {
			const writes = acts.filter(a => a.act === 'write' && a.obj === obj.id);
			if (!writes.length) return {p: 1, under: 1};
			// 尚未開始寫時取第一次書寫，進度為負即不畫
			const write = writes.filter(a => a.t0 <= t).pop() || writes[0];
			return {p: (t - write.t0) / (write.t1 - write.t0), under: Board.phase(t, write.t1 - .2, write.t1 + .6)};
		},
		draw(api, obj, st) {
			const s = style(obj), rows = lines(obj), size = this.measure(obj, api);
			const o = {...s, color: api.color(s.color), align: 'center'};
			rows.forEach((row, i) => {
				const y = s.size * LINE * (i + .5);
				// 多行時逐行寫出：每行分到等長的進度
				const p = api.clamp(st.p * rows.length - i);
				api.write(row, size.w / 2, y, p, o);
			});
			if (s.underline) {
				const y = rows.length * s.size * LINE + UNDER / 2;
				api.ink([[PAD_X, y], [size.w - PAD_X, y - 3]], st.under, {color: api.color('text.accent'), width: 6, seed: Board.seed(obj.id)});
			}
		},
		anchors() { return {}; },
	});
})();
