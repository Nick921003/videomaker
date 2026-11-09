// 圖示形狀：31 個圖示的筆畫，純函式、不碰畫布，手帳、黑板、文章配圖三種皮膚共用。
// 座標在 100×100 格子內，四周留邊 8（所有點落在 [8, 92]）；只畫線不填色。
// 陣列順序就是筆順：先外框、後細節。w 是相對粗細等級，不是像素；弧線已取樣成點。
(function (g) {
	'use strict';
	var NAMES = ['keyboard', 'cross', 'checklist', 'branch', 'bulb', 'warning', 'scale', 'pencil', 'loop', 'question',
		'check', 'play', 'stop', 'return', 'file', 'chat', 'clock', 'person', 'hourglass', 'tangle', 'magnifier',
		'lock', 'gear', 'keycap', 'mic', 'headphones', 'wave', 'quote', 'heart', 'coin', 'phone'];

	var STEP = 4, MAXSEG = 5.5;
	var r2 = function (v) { return Math.round(v * 100) / 100; };
	var rad = function (d) { return d * Math.PI / 180; };

	// 角度用度，螢幕座標（y 向下），角度增加是順時針；a1 < a0 就逆時針
	function arc(cx, cy, r, a0, a1) {
		var n = Math.max(2, Math.ceil(Math.abs(a1 - a0) * Math.PI / 180 * r / STEP)), pts = [];
		for (var i = 0; i <= n; i++) {
			var a = rad(a0 + (a1 - a0) * i / n);
			pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
		}
		return pts;
	}
	function join() { return Array.prototype.concat.apply([], arguments); }
	function rrect(x0, y0, x1, y1, r) {
		return join([[x0 + r, y0], [x1 - r, y0]], arc(x1 - r, y0 + r, r, 270, 360), [[x1, y1 - r]],
			arc(x1 - r, y1 - r, r, 0, 90), [[x0 + r, y1]], arc(x0 + r, y1 - r, r, 90, 180), [[x0, y0 + r]],
			arc(x0 + r, y0 + r, r, 180, 270));
	}
	// 沿曲線取樣的參數式：f(t) → [x, y]
	function curve(f, t0, t1, n) {
		var pts = [];
		for (var i = 0; i <= n; i++) pts.push(f(t0 + (t1 - t0) * i / n));
		return pts;
	}
	// 在 (x, y) 畫箭頭尖，朝 (dx, dy) 方向
	function head(x, y, dx, dy, len) {
		var a = Math.atan2(dy, dx), s = rad(35);
		return [[x - Math.cos(a - s) * len, y - Math.sin(a - s) * len], [x, y], [x - Math.cos(a + s) * len, y - Math.sin(a + s) * len]];
	}
	function line(x0, y0, x1, y1) { return [[x0, y0], [x1, y1]]; }

	// 取樣過的筆畫：去掉連續重複點，弧線筆畫的直線段補點，讓相鄰點距離都不超過 MAXSEG
	function stroke(part, pts, w, isArc) {
		var out = [];
		pts.forEach(function (p) {
			var q = [r2(p[0]), r2(p[1])], l = out[out.length - 1];
			if (l && l[0] === q[0] && l[1] === q[1]) return;
			if (isArc && l) {
				var d = Math.hypot(q[0] - l[0], q[1] - l[1]), k = Math.ceil(d / MAXSEG);
				for (var i = 1; i < k; i++) out.push([r2(l[0] + (q[0] - l[0]) * i / k), r2(l[1] + (q[1] - l[1]) * i / k)]);
			}
			out.push(q);
		});
		return { pts: out, w: w, arc: !!isArc, part: part };
	}
	var M = function (part, pts, isArc) { return stroke(part, pts, 'main', isArc); };
	var D = function (part, pts, isArc) { return stroke(part, pts, 'detail', isArc); };

	// 鉛筆沿斜線：u 沿筆身（從筆尖算起）、v 垂直筆身
	function pencilAt(u, v) { var k = Math.SQRT1_2; return [12 + k * (u + v), 88 + k * (v - u)]; }

	function gearOutline() {
		// 齒形取自黑板的 icon.js（8 齒、齒尖 64、齒根 48，原尺寸 140），縮放到齒尖 42 才不超出留邊
		var k = 42 / 64, pts = [], step = Math.PI * 2 / 8;
		var at = function (r, a) { return [50 + Math.cos(a) * r * k, 50 + Math.sin(a) * r * k]; };
		for (var i = 0; i < 8; i++) {
			var c = i * step - Math.PI / 2;
			pts.push(at(48, c - rad(14)), at(64, c - rad(9)), at(64, c + rad(9)), at(48, c + rad(14)));
		}
		pts.push(pts[0]);
		return pts;
	}

	// 三葉結、愛心這類封閉曲線：依邊界框等比縮放到 [lo, hi] 並置中
	function fit(pts, lo, hi) {
		var xs = pts.map(function (p) { return p[0]; }), ys = pts.map(function (p) { return p[1]; });
		var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
		var s = (hi - lo) / Math.max(x1 - x0, y1 - y0), cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
		return pts.map(function (p) { return [50 + (p[0] - cx) * s, 50 + (p[1] - cy) * s]; });
	}
	var trefoil = function (t) { return [Math.sin(t) + 2 * Math.sin(2 * t), Math.cos(t) - 2 * Math.cos(2 * t)]; };
	var heartAt = function (t) {
		var s = Math.sin(t);
		return [16 * s * s * s, -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t))];
	};

	var DRAW = {
		keyboard: function () {
			return [M('outline', rrect(8, 26, 92, 74, 5), true),
				D('row1-a', line(22, 40, 32, 40)), D('row1-b', line(44, 40, 56, 40)), D('row1-c', line(68, 40, 78, 40)),
				D('row2-a', line(22, 52, 32, 52)), D('row2-b', line(44, 52, 56, 52)), D('row2-c', line(68, 52, 78, 52)),
				D('space', line(30, 64, 70, 64))];
		},
		cross: function () {
			return [M('stroke-1', line(24, 24, 76, 76)), M('stroke-2', line(76, 24, 24, 76))];
		},
		checklist: function () {
			return [M('outline', rrect(20, 12, 80, 88, 6), true),
				D('tick-1', [[30, 34], [34, 38], [42, 29]]), D('line-1', line(50, 34, 70, 34)),
				D('tick-2', [[30, 60], [34, 64], [42, 55]]), D('line-2', line(50, 60, 70, 60))];
		},
		branch: function () {
			return [M('diamond', [[50, 12], [72, 34], [50, 56], [28, 34], [50, 12]]),
				M('trunk', line(50, 56, 50, 70)), M('fork', [[22, 88], [22, 70], [78, 70], [78, 88]]),
				D('arrow-l', head(22, 88, 0, 1, 8)), D('arrow-r', head(78, 88, 0, 1, 8))];
		},
		bulb: function () {
			return [M('glass', join(arc(50, 38, 24, 125, 415), [[60, 68], [40, 68], [36.2, 57.7]]), true),
				M('base', line(42, 77, 58, 77)), D('base-2', line(45, 85, 55, 85)),
				D('filament', [[43, 44], [50, 52], [57, 44]]), D('stem', line(50, 52, 50, 68))];
		},
		warning: function () {
			return [M('triangle', [[50, 12], [90, 86], [10, 86], [50, 12]]),
				D('bar', line(50, 38, 50, 62)), D('dot', line(50, 73, 50, 74))];
		},
		scale: function () {
			return [M('pole', line(50, 16, 50, 82)), M('beam', line(18, 30, 82, 30)), M('base', line(30, 88, 70, 88)),
				D('pan-l', arc(24, 58, 14, 0, 180), true), D('pan-r', arc(76, 58, 14, 0, 180), true),
				D('string-l', [[10, 58], [18, 30], [38, 58]]), D('string-r', [[62, 58], [82, 30], [90, 58]])];
		},
		pencil: function () {
			var P = pencilAt;
			return [M('outline', [P(0, 0), P(18, -9), P(100, -9), P(100, 9), P(18, 9), P(0, 0)]),
				D('tip', [P(18, -9), P(18, 9)]), D('eraser', [P(84, -9), P(84, 9)])];
		},
		loop: function () {
			var a = arc(50, 50, 30, 30, 320), e = a[a.length - 1];
			return [M('circle', a, true), M('head', head(e[0], e[1], -Math.sin(rad(320)), Math.cos(rad(320)), 11))];
		},
		question: function () {
			return [M('hook', join(arc(50, 34, 18, 180, 400), [[50, 54], [50, 62]]), true), D('dot', line(50, 78, 50, 79))];
		},
		check: function () {
			return [M('ring', arc(50, 50, 40, 0, 360), true), M('tick', [[32, 52], [45, 65], [69, 37]])];
		},
		play: function () {
			return [M('ring', arc(50, 50, 40, 0, 360), true), M('triangle', [[40, 30], [72, 50], [40, 70], [40, 30]])];
		},
		stop: function () {
			var o = [];
			for (var i = 0; i <= 8; i++) o.push([50 + Math.cos(rad(22.5 + 45 * i)) * 41, 50 + Math.sin(rad(22.5 + 45 * i)) * 41]);
			return [M('octagon', o), D('bar', line(32, 50, 68, 50))];
		},
		'return': function () {
			return [M('path', [[78, 22], [78, 58], [26, 58]]), D('head', head(26, 58, -1, 0, 16))];
		},
		file: function () {
			return [M('outline', [[24, 10], [58, 10], [78, 30], [78, 88], [24, 88], [24, 10]]),
				D('fold', [[58, 10], [58, 30], [78, 30]]), D('line-1', line(34, 50, 68, 50)),
				D('line-2', line(34, 62, 68, 62)), D('line-3', line(34, 74, 56, 74))];
		},
		chat: function () {
			var p = join([[20, 16], [80, 16]], arc(80, 26, 10, 270, 360), [[90, 56]], arc(80, 56, 10, 0, 90),
				[[80, 66], [44, 66], [28, 82], [28, 66], [20, 66]], arc(20, 56, 10, 90, 180), [[10, 26]], arc(20, 26, 10, 180, 270));
			return [M('bubble', p, true), D('line-1', line(26, 36, 74, 36)), D('line-2', line(26, 48, 58, 48))];
		},
		clock: function () {
			return [M('face', arc(50, 50, 40, 0, 360), true), D('hands', [[50, 26], [50, 50], [68, 60]]), D('tick', line(50, 14, 50, 19))];
		},
		person: function () {
			return [M('head', arc(50, 32, 14, 0, 360), true), M('body', join(arc(50, 88, 30, 180, 360), [[20, 88]]), true)];
		},
		hourglass: function () {
			return [M('glass-l', [[32, 12], [32, 26], [50, 50], [32, 74], [32, 88]]),
				M('glass-r', [[68, 12], [68, 26], [50, 50], [68, 74], [68, 88]]),
				M('top', line(24, 12, 76, 12)), M('bottom', line(24, 88, 76, 88)),
				D('sand-top', line(40, 30, 60, 30)), D('stream', line(50, 50, 50, 70)), D('pile', [[38, 82], [50, 70], [62, 82]])];
		},
		tangle: function () {
			var all = fit(curve(trefoil, 0, 2 * Math.PI, 100), 10, 90);
			return [M('knot-a', all.slice(0, 51), true), M('knot-b', all.slice(50), true)];
		},
		magnifier: function () {
			return [M('lens', arc(42, 42, 26, 0, 360), true), M('handle', line(61, 61, 86, 86)), D('glint', arc(42, 42, 17, 190, 260), true)];
		},
		lock: function () {
			return [M('body', rrect(20, 44, 80, 88, 6), true),
				M('shackle', join([[32, 44]], arc(50, 32, 18, 180, 360), [[68, 44]]), true),
				D('keyhole', arc(50, 62, 5, 0, 360), true), D('slot', line(50, 67, 50, 76))];
		},
		gear: function () {
			return [M('outline', gearOutline()), D('hub', arc(50, 50, 42 / 64 * 20, 0, 360), true)];
		},
		keycap: function () {
			return [M('outline', rrect(12, 14, 88, 86, 10), true), D('face', rrect(22, 22, 78, 68, 6), true)];
		},
		mic: function () {
			return [M('capsule', rrect(38, 10, 62, 56, 12), true), M('holder', arc(50, 46, 26, 0, 180), true),
				M('stem', line(50, 72, 50, 88)), M('base', line(36, 88, 64, 88))];
		},
		headphones: function () {
			return [M('band', arc(50, 50, 36, 180, 360), true), M('cup-l', rrect(14, 50, 30, 80, 5), true), M('cup-r', rrect(70, 50, 86, 80, 5), true)];
		},
		wave: function () {
			var h = [12, 28, 38, 22, 8];
			return h.map(function (v, i) { return M('bar-' + (i + 1), line(18 + 16 * i, 50 - v, 18 + 16 * i, 50 + v)); });
		},
		quote: function () {
			var mark = function (cx) { return join(arc(cx, 38, 11, 0, 360), [[cx + 10, 50], [cx + 4, 64], [cx - 6, 72]]); };
			return [M('mark-l', mark(32), true), M('mark-r', mark(68), true)];
		},
		heart: function () {
			var all = fit(curve(heartAt, 0, 2 * Math.PI, 120), 10, 90);
			return [M('right-half', all.slice(0, 61), true), M('left-half', all.slice(60), true)];
		},
		coin: function () {
			return [M('rim', arc(50, 50, 40, 0, 360), true), D('inner', arc(50, 50, 32, 0, 360), true),
				D('mark', join(arc(50, 41, 9, 330, 90), arc(50, 59, 9, 270, 510)), true)];
		},
		phone: function () {
			return [M('body', rrect(28, 10, 72, 90, 8), true), D('speaker', line(44, 20, 56, 20)), D('home', line(44, 80, 56, 80))];
		}
	};

	function strokes(name, opts) {
		if (!Object.prototype.hasOwnProperty.call(DRAW, name)) throw new Error('不認得的圖示：' + name);
		var out = { strokes: DRAW[name]() };
		if (name === 'keycap') {
			if (!opts || typeof opts.text !== 'string' || !opts.text) throw new Error('keycap 必須帶 opts.text（非空字串）');
			out.text = opts.text;
		}
		return out;
	}
	// keycap 的筆畫與字無關，沒給字也能數筆數
	function count(name, opts) {
		return strokes(name, name === 'keycap' && !opts ? { text: '?' } : opts).strokes.length;
	}

	var X = { NAMES: NAMES, strokes: strokes, count: count };
	if (typeof module !== 'undefined') module.exports = X; else g.IconShapes = X;
})(this);
