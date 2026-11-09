// 通用標註框：任何錨點旁掛一個圓角框加小三角。純幾何，不碰 DOM，繪製交給各風格。
// 尺寸照抄 vscode/model.js 的 tipBox（字 22 時：左右內距 22、框高 48、離錨點 48、三角 16），model.js 不動
(function (g) {
	'use strict';
	var PAD = 22, ARROW = 16, BASE = 22, H = 48, GAP = 48, HALF = 10, RADIUS = 6;
	var SIDES = ['right', 'left', 'top', 'bottom'];
	// 鏡頭動作不算「指向同一物件的下一個動作」，否則推近一下標註就收掉
	var CAMERA = { focus: 1, wide: 1 };

	function size(text, measure, style) {
		var f = ((style && style.size) || BASE) / BASE;
		return { w: measure(String(text), style).w + PAD * 2 * f, h: H * f, f: f };
	}

	function overlaps(a, b) {
		return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
	}
	function inside(outer, r) {
		return r.x >= outer.x && r.y >= outer.y && r.x + r.w <= outer.x + outer.w && r.y + r.h <= outer.y + outer.h;
	}

	function candidate(side, a, s) {
		var f = s.f || 1, gap = GAP * f, arrow = ARROW * f, cx = a.x + a.w / 2, cy = a.y + a.h / 2;
		if (side === 'right') { var x = a.x + a.w + gap; return { box: { x: x, y: cy - s.h / 2, w: s.w, h: s.h }, side: side, tip: [x - arrow, cy] }; }
		if (side === 'left') { var x2 = a.x - gap - s.w; return { box: { x: x2, y: cy - s.h / 2, w: s.w, h: s.h }, side: side, tip: [x2 + s.w + arrow, cy] }; }
		if (side === 'top') { var y = a.y - gap - s.h; return { box: { x: cx - s.w / 2, y: y, w: s.w, h: s.h }, side: side, tip: [cx, y + s.h + arrow] }; }
		var y2 = a.y + a.h + gap;
		return { box: { x: cx - s.w / 2, y: y2, w: s.w, h: s.h }, side: side, tip: [cx, y2 - arrow] };
	}

	// 錨點貼邊時框可以沿著邊滑進 bounds，只要三角仍落在框邊的直線段上
	function slide(c, bounds, f) {
		var b = c.box, keep = (RADIUS + HALF) * f;
		if (c.side === 'top' || c.side === 'bottom') {
			var x = Math.max(bounds.x, Math.min(b.x, bounds.x + bounds.w - b.w));
			if (c.tip[0] - x >= keep && x + b.w - c.tip[0] >= keep) b.x = x;
		} else {
			var y = Math.max(bounds.y, Math.min(b.y, bounds.y + bounds.h - b.h));
			if (c.tip[1] - y >= keep && y + b.h - c.tip[1] >= keep) b.y = y;
		}
		return c;
	}

	function place(anchor, s, bounds, obstacles) {
		for (var i = 0; i < SIDES.length; i++) {
			var c = slide(candidate(SIDES[i], anchor, s), bounds, s.f || 1);
			if (inside(bounds, c.box) && !(obstacles || []).some(function (o) { return overlaps(c.box, o); })) return c;
		}
		return null;
	}

	function endTime(acts, i, untilT, sceneEnd) {
		if (untilT != null) return Math.min(untilT, sceneEnd);
		var me = acts[i];
		for (var j = i + 1; j < acts.length; j++) {
			var a = acts[j];
			if (a.obj === me.obj && !CAMERA[a.act] && a.t0 > me.t0) return Math.min(a.t0, sceneEnd);
		}
		return sceneEnd;
	}

	// 三角的三個點：底邊貼在框上、尖端指向錨點
	function arrowPts(p) {
		var b = p.box, t = p.tip, h = HALF * (b.h / H);
		if (p.side === 'right') return [[b.x, t[1] - h], t, [b.x, t[1] + h]];
		if (p.side === 'left') return [[b.x + b.w, t[1] - h], t, [b.x + b.w, t[1] + h]];
		if (p.side === 'top') return [[t[0] - h, b.y + b.h], t, [t[0] + h, b.y + b.h]];
		return [[t[0] - h, b.y], t, [t[0] + h, b.y]];
	}

	var Callout = { PAD: PAD, ARROW: ARROW, RADIUS: RADIUS, size: size, place: place, endTime: endTime, arrowPts: arrowPts };
	if (typeof module !== 'undefined') module.exports = Callout; else g.Callout = Callout;
})(this);
