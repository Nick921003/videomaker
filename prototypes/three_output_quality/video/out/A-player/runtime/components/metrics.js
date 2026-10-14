'use strict';
(() => {
	// 三行依字高堆疊（api.text 的框高＝字級 × 1.24），行距不寫死，量測閘才不會判互疊
	const SIZES = {label: 36, value: 118, note: 30}, GAP = 6;
	const ROW = Object.fromEntries(Object.entries(SIZES).map(([k, v]) => [k, v * 1.24]));
	const Y = {label: ROW.label / 2, value: ROW.label + GAP + ROW.value / 2, note: ROW.label + ROW.value + GAP * 2 + ROW.note / 2};
	const HEIGHT = ROW.label + ROW.value + ROW.note + GAP * 2;

	Board.register('metrics', {
		measure(obj, api) {
			let maxW = 0;
			const items = obj.items || [];
			for (const item of items) {
				const wL = api.measure(item.label || '', {size: 36}).w;
				const wV = api.measure(item.value || '', {size: 118, weight: 600}).w;
				const wN = api.measure(item.note || '', {size: 30}).w;
				maxW = Math.max(maxW, wL, wV, wN);
			}
			const colW = maxW + 80;
			return {w: items.length * colW, h: HEIGHT, colW};
		},
		state(obj, acts, t) {
			const items = obj.items || [];
			const reveals = new Array(items.length).fill(0);
			for (const a of acts) {
				if (a.obj === obj.id && a.act === 'reveal' && t >= a.t0) {
					if (a.args && a.args.index !== undefined) {
						reveals[a.args.index] = Math.max(reveals[a.args.index], Board.phase(t, a.t0, a.t1));
					} else {
						const per = (a.t1 - a.t0) / a.n;
						for (let k = 0; k < a.n; k++) {
							if (k < reveals.length) {
								reveals[k] = Math.max(reveals[k], Board.phase(t, a.t0 + k * per, a.t0 + (k + 1) * per));
							}
						}
					}
				}
			}
			return {reveals};
		},
		draw(api, obj, st) {
			const m = this.measure(obj, api);
			const items = obj.items || [];
			for (let i = 0; i < items.length; i++) {
				const item = items[i];
				const cx = i * m.colW + m.colW / 2;
				const p = st.reveals[i];
				if (p > 0) {
					if (item.label) api.text(item.label, cx, Y.label, {size: SIZES.label, color: api.color('text.muted'), align: 'center', alpha: p});
					if (item.value) api.write(item.value, cx, Y.value, p, {size: SIZES.value, weight: 600, color: api.color('text.body'), align: 'center'});
					if (item.note) api.text(item.note, cx, Y.note, {size: SIZES.note, color: api.color('text.muted'), align: 'center', alpha: p});
				}
			}
		},
		anchors(obj, st, api) {
			const m = this.measure(obj, api);
			const res = {};
			const items = obj.items || [];
			for (let i = 0; i < items.length; i++) {
				res[`m${i}`] = {x: i * m.colW, y: 0, w: m.colW, h: m.h};
			}
			return res;
		}
	});
})();
