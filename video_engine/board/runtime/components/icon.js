'use strict';
// 圖示：純繪製、沒有自己的動作；目前只有齒輪（對應 VS Code 左下角的設定入口）
(() => {
	const SIZE = 140, TEETH = 8, R_TIP = 64, R_ROOT = 48, R_HUB = 20;
	const CAP = {size: 32, gap: 8};
	const capH = CAP.size * 1.3;

	// 齒輪外形：每齒四個頂點（齒根左、齒尖左、齒尖右、齒根右），最後回到起點封閉
	function gearOutline(cx, cy) {
		const pts = [], step = Math.PI * 2 / TEETH, rad = d => d * Math.PI / 180;
		const at = (r, a) => [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
		for (let k = 0; k < TEETH; k++) {
			const c = k * step - Math.PI / 2;
			pts.push(at(R_ROOT, c - rad(14)), at(R_TIP, c - rad(9)), at(R_TIP, c + rad(9)), at(R_ROOT, c + rad(14)));
		}
		pts.push(pts[0]);
		return pts;
	}
	function circle(cx, cy, r) {
		const pts = [];
		for (let i = 0; i <= 24; i++) { const q = i / 24 * Math.PI * 2; pts.push([cx + Math.cos(q) * r, cy + Math.sin(q) * r]); }
		return pts;
	}
	const capStyle = api => ({size: CAP.size, weight: 400, color: api.color('text.muted'), align: 'center'});

	Board.register('icon', {
		measure(obj, api) {
			if (!obj.caption) return {w: SIZE, h: SIZE};
			return {w: Math.max(SIZE, api.measure(obj.caption, capStyle(api)).w + 24), h: SIZE + CAP.gap + capH};
		},
		state() { return {}; },
		draw(api, obj) {
			const w = this.measure(obj, api).w, cx = w / 2, cy = SIZE / 2, seed = Board.seed(obj.id);
			const ink = {color: api.color('text.body'), width: 5, seed};
			api.ink(gearOutline(cx, cy), 1, ink);
			api.ink(circle(cx, cy, R_HUB), 1, {...ink, seed: seed + 1});
			api.record(cx - SIZE / 2, 0, SIZE, SIZE, 'panel');
			if (obj.caption) api.write(obj.caption, cx, SIZE + CAP.gap + capH / 2, 1, capStyle(api));
		},
		anchors() { return {}; },
	});
})();
