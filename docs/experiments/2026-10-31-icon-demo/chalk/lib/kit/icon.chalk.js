// 黑板圖示：筆畫來自共用的 IconShapes，這裡只管縮放進框、依筆畫長度分配時間、交給粉筆的 S／T／X／fade。
(function (g) {
	'use strict';
	var IS = typeof module !== 'undefined' ? require('../../../components/icon/shapes.js') : g.IconShapes;
	// 黑板 1080p 面板上的像素，對照 KIT.md 的字級
	var SIZE = { s: 120, m: 180, l: 260 };
	var WIDTH = { main: 6, detail: 4.5 };
	// 語氣 → 粉筆的文字色類（筆畫直接收語氣，文字要色類）
	var CLS = { ink: 'cw', muted: 'cm', accent: 'cy', warn: 'cp', ok: 'cg', info: 'cb' };
	// 鍵帽面板在 100 格內的位置（見 shapes.js 的 keycap）
	var FACE = { cx: 50, cy: 45, w: 56, h: 46 };
	var TEXT_SHARE = 0.4;
	var BLINK_FADE = 0.02;
	var ERASE_DUR = 0.4;

	var f1 = function (v) { return (Math.round(v * 10) / 10).toString(); };
	function length(pts) {
		var n = 0;
		for (var i = 1; i < pts.length; i++) n += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
		return n;
	}

	// 100 格縮放進 box（取短邊、置中）；點都在 [8, 92]，所以一定在框內
	function place(name, opts, box) {
		var shape = IS.strokes(name, opts), k = Math.min(box.w, box.h) / 100;
		var ox = box.x + (box.w - 100 * k) / 2, oy = box.y + (box.h - 100 * k) / 2;
		return { shape: shape, k: k, ox: ox, oy: oy };
	}
	function paths(name, opts, box) {
		var p = place(name, opts, box);
		return p.shape.strokes.map(function (s) {
			var pts = s.pts.map(function (q) { return [p.ox + q[0] * p.k, p.oy + q[1] * p.k]; });
			var d = pts.map(function (q, i) { return (i ? 'L' : 'M') + f1(q[0]) + ' ' + f1(q[1]); }).join(' ');
			return { d: d, w: WIDTH[s.w], len: length(pts) };
		});
	}

	// 閃爍排成一段段 K.fade（照 printf 片 beats.js 的 blink）：套件的淡出彼此相乘，不直接改透明度
	function blink(api, els, t0, t1) {
		for (var k = Math.floor(t0 * 2) / 2; k < t1; k += 1) {
			var off = k + 0.5, on = Math.min(k + 1, t1);
			if (off >= t0 && off < t1) api.K.fade(els, off, BLINK_FADE, 0, on);
		}
	}

	function draw(api, P, obj, box, a, tone, els) {
		var ps = paths(obj.name, obj, box), p = place(obj.name, obj, box), text = p.shape.text;
		var total = ps.reduce(function (n, s) { return n + s.len; }, 0);
		// 有字的鍵帽把最後一段時間留給字
		var span = (a.t1 - a.t0) * (text ? 1 - TEXT_SHARE : 1), t = a.t0;
		ps.forEach(function (s) {
			var dur = span * s.len / total;
			els.push(api.S(P, s.d, tone, s.w, t, dur, { kind: 'draw' }));
			t += dur;
		});
		if (text) {
			var unit = api.K.wlen(text), size = Math.min(FACE.h * p.k * 0.8, FACE.w * p.k * 0.84 / unit);
			var x = p.ox + FACE.cx * p.k - unit * size / 2, y = p.oy + FACE.cy * p.k - size * 0.65;
			els.push(api.T(P, x, y, size, [[text, t, a.t1, CLS[tone] || 'cw']], { sprite: false }));
		}
	}

	// acts: [{act: draw|show|blink|erase, t0, t1}]；回傳畫出的筆畫與字，呼叫端可再拿去擦或閃
	function perform(api, P, obj, box, acts, tone) {
		var els = [];
		tone = tone || obj.tone || 'ink';
		acts.forEach(function (a) {
			if (a.act === 'draw' || a.act === 'show') draw(api, P, obj, box, a, tone, els);
			else if (a.act === 'blink') blink(api, els, a.t0, a.t1);
			else if (a.act === 'erase') api.X(P, els, [box.x, box.y, box.w, box.h], a.t0, ERASE_DUR);
		});
		return { els: els };
	}

	var X = { SIZE: SIZE, NAMES: IS.NAMES, WIDTH: WIDTH, paths: paths, perform: perform, blink: blink };
	if (typeof module !== 'undefined') module.exports = X; else g.ChalkIcon = X;
})(this);
