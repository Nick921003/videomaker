// 黑板轉接：分鏡寫好的 VS Code 畫面（screens.json 的 screen／do）照逐字時間排好，畫成仿真畫面放進電腦畫面區。
// 版面、狀態、繪圖指令都在 video_engine/components/vscode/（sync_film.py 複製到 lib/components/），這裡只管時間、游標與標記。
(function (g) {
	'use strict';
	var NS = 'http://www.w3.org/2000/svg';
	var MARKS = { circle: 1, underline: 1, arrow: 1 };

	// 有 cue 的動作從那幾個字開口時開始；沒有的從這句開始畫的時刻起跑，會擋路的動作（blocks）一個接一個
	function schedule(screen, span, drawAt) {
		var out = [];
		screen.lines.forEach(function (li) {
			var free = drawAt(li);
			(screen.do[String(li)] || []).forEach(function (a) {
				var t0 = a.cue ? span(li, a.cue).start : free;
				var x = { act: a.act, target: a.target, obj: a.obj, args: a.args, n: a.n, t0: t0, t1: t0 + a.dur, line: li };
				if (a.blocks && !a.cue) free = x.t1;
				out.push(x);
			});
		});
		return out;
	}

	var clamp = function (v) { return v < 0 ? 0 : v > 1 ? 1 : v; };
	var io2 = function (u) { return u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2; };
	var f1 = function (v) { return (Math.round(v * 10) / 10).toString(); };
	var center = function (b) { return [b.x + b.w / 2, b.y + b.h / 2]; };

	// 手描的圈：起筆略過頭，扁長目標用接近方形的圈；形狀由 seed 決定，每格一樣
	function ringPts(b, seed) {
		var n = 64, sq = b.w / Math.max(1, b.h) > 1.8 ? 4 : 2, e = 2 / sq, pad = 10;
		var rx = b.w / 2 + pad, ry = b.h / 2 + pad * 0.7, c = center(b), a0 = -2.3 + (seed % 7) * 0.09, pts = [];
		for (var i = 0; i <= n; i++) {
			var a = a0 + (i / n) * 1.12 * Math.PI * 2, gr = 9 * (i / n) * Math.min(1, Math.min(rx, ry) / 60), ca = Math.cos(a), sa = Math.sin(a);
			pts.push([c[0] + (ca < 0 ? -1 : 1) * Math.pow(Math.abs(ca), e) * (rx + gr), c[1] + (sa < 0 ? -1 : 1) * Math.pow(Math.abs(sa), e) * (ry + gr * 0.7)]);
		}
		return pts;
	}
	function pathD(pts, p) {
		var k = Math.max(2, Math.ceil(pts.length * clamp(p)));
		return pts.slice(0, k).map(function (q, i) { return (i ? 'L' : 'M') + f1(q[0]) + ' ' + f1(q[1]); }).join(' ');
	}
	var seedOf = function (s) { var h = 0; for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 9973; return h; };

	function el(tag, attrs, parent) {
		var e = document.createElementNS(NS, tag);
		for (var k in attrs) e.setAttribute(k, attrs[k]);
		if (parent) parent.appendChild(e);
		return e;
	}

	function mount(scr, data, api) {
		var M = g.VSCodeModel, P = g.VSCodePaint, S = g.VSCodeSVG, theme = g.VSCODE_THEME, tones = g.TONES.vscode;
		var col = function (key) { return key.split('.').reduce(function (o, k) { return o && o[k]; }, theme); };
		var desc = data.screen, size = [scr.w, scr.h];
		var acts = schedule(data, api.span, api.drawAt);
		var own = acts.filter(function (a) { return a.obj === desc.id; });
		var cur = acts.filter(function (a) { return a.obj === 'cursor'; });
		var marks = acts.filter(function (a) { return MARKS[a.act]; });

		var chalkEl = scr.P.el.parentNode, world = chalkEl.parentNode;
		var layer = world.querySelector('svg.screen-layer');
		if (!layer) {
			layer = el('svg', { 'class': 'screen-layer', width: parseFloat(chalkEl.style.width), height: parseFloat(chalkEl.style.height) });
			layer.style.cssText = 'position:absolute;left:0;top:0;overflow:visible;pointer-events:none';
			world.insertBefore(layer, chalkEl);
		}
		var defs = el('defs', {}, layer), clip = el('clipPath', { id: 'vs-clip-' + scr.k }, defs);
		el('rect', { x: 0, y: 0, width: scr.w, height: scr.h }, clip);
		var outer = el('g', { transform: 'translate(' + (scr.P.ox + scr.x) + ',' + (scr.P.oy + scr.y) + ')', 'clip-path': 'url(#vs-clip-' + scr.k + ')' }, layer);
		var root = el('g', { opacity: 0 }, outer), pic = el('g', {}, root), markG = el('g', {}, root), curG = el('g', {}, root);
		var curPath = el('path', { d: 'M 0 0 L 0 32 L 8.5 24.5 L 14.5 38 L 20 35.5 L 14 22.5 L 25 22.5 Z', fill: col('actOn'), stroke: col('winTitle'), 'stroke-width': 2 }, curG);
		var ripple = el('circle', { r: 10, fill: 'none', stroke: col('actOn'), 'stroke-width': 4, opacity: 0 }, curG);
		var markEls = marks.map(function (m) { return el('path', { fill: 'none', stroke: col(tones[(m.args && m.args.tone) || 'accent']), 'stroke-width': m.act === 'circle' ? 5.5 : 5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', opacity: 0 }, markG); });

		// 粉筆畫的螢幕外框與底座（鏡頭推進來之前先畫好）
		var NOSP = { sprite: false }, G = api.G, tIn = scr.tIn;
		var fx = scr.x - 10, fy = scr.y - 10, fw = scr.w + 20, fh = scr.h + 14;
		api.S(scr.P, G.rect(fx, fy, fw, fh), 'w', 6, tIn, 0.4, NOSP);
		var sx = scr.x + scr.w / 2, sy = scr.y + scr.h + 4;
		api.S(scr.P, G.line(sx - 34, sy, sx - 48, sy + 8, 1) + ' ' + G.line(sx + 34, sy, sx + 48, sy + 8, 1) + ' ' + G.line(sx - 120, sy + 9, sx + 120, sy + 9, 1), 'w', 5, tIn + 0.38, 0.17, NOSP);
		api.K.park(tIn + 0.58, scr.P, 8, scr.y + scr.h + 6, 'w');

		// 鏡頭離開（下一句開始）就收掉，之後路過只剩粉筆框
		var last = scr.lines[scr.lines.length - 1], tGone = api.lineStart(last + 1), tShow = tIn + 0.4;
		var lastSvg = null, lastOp = null;
		var start = [scr.w * 0.62, scr.h * 0.62];

		function cursorAt(t, an) {
			var p = start, clickT = null;
			for (var i = 0; i < cur.length; i++) {
				var a = cur[i], to = an[(a.args.on || a.args.to).split(':').slice(1).join(':')];
				if (!to || t < a.t0) break;
				// 游標已經在目標上（前面先 move 過去）就直接按，不再空等移動時間
				var q = center(to), near = Math.abs(q[0] - p[0]) + Math.abs(q[1] - p[1]) < 4;
				var arrive = near ? a.t0 : a.t0 + (a.t1 - a.t0) * 0.6;
				if (t < arrive) { var u = io2((t - a.t0) / (arrive - a.t0)); return { p: [p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u], click: null }; }
				p = q;
				if (a.act === 'click') clickT = arrive;
			}
			return { p: p, click: clickT };
		}

		return function (t) {
			var op = t < tGone ? (tShow <= 0 ? 1 : clamp((t - tShow) / 0.3)) : 0;
			if (op !== lastOp) { root.setAttribute('opacity', f1(op)); lastOp = op; }
			if (op <= 0) return;
			var st = M.state(desc, own, t, size), an = M.anchors(desc, st, size);
			var svg = S.render(P.ops(desc, st, t, size), theme, size);
			if (svg !== lastSvg) { pic.innerHTML = svg; lastSvg = svg; }
			marks.forEach(function (m, i) {
				var e = markEls[i], b = an[m.target.split(':').slice(1).join(':')] || (m.target === desc.id ? { x: 0, y: 0, w: scr.w, h: scr.h } : null);
				// 標記留到這句講完再淡出
				var fade = 1 - clamp((t - (api.lineEnd(m.line) + 0.3)) / 0.3);
				if (!b || t < m.t0 || fade <= 0) { e.setAttribute('opacity', 0); return; }
				var p = clamp((t - m.t0) / Math.max(0.05, m.t1 - m.t0)), d;
				if (m.act === 'circle') d = pathD(ringPts(b, seedOf(m.target)), io2(p));
				else if (m.act === 'underline') d = pathD([[b.x - 4, b.y + b.h + 4], [b.x - 4 + (b.w + 8) * io2(p), b.y + b.h + 2]], 1);
				else {
					var tb = an[(m.args.to || '').split(':').slice(1).join(':')];
					if (!tb) { e.setAttribute('opacity', 0); return; }
					var a0 = center(b), a1 = center(tb), u = io2(p), ex = a0[0] + (a1[0] - a0[0]) * u, ey = a0[1] + (a1[1] - a0[1]) * u, ang = Math.atan2(a1[1] - a0[1], a1[0] - a0[0]);
					d = 'M' + f1(a0[0]) + ' ' + f1(a0[1]) + ' L' + f1(ex) + ' ' + f1(ey) + (p >= 1 ? ' M' + f1(ex - 22 * Math.cos(ang - 0.45)) + ' ' + f1(ey - 22 * Math.sin(ang - 0.45)) + ' L' + f1(ex) + ' ' + f1(ey) + ' L' + f1(ex - 22 * Math.cos(ang + 0.45)) + ' ' + f1(ey - 22 * Math.sin(ang + 0.45)) : '');
				}
				e.setAttribute('d', d);
				e.setAttribute('opacity', f1(fade));
			});
			if (cur.length) {
				var c = cursorAt(t, an), press = c.click != null && t - c.click >= 0 && t - c.click < 0.16 ? 0.88 : 1;
				curG.setAttribute('opacity', 1);
				curPath.setAttribute('transform', 'translate(' + f1(c.p[0]) + ',' + f1(c.p[1]) + ') scale(' + press + ')');
				var u = c.click == null ? -1 : (t - c.click) / 0.4;
				if (u > 0 && u < 1) { ripple.setAttribute('cx', f1(c.p[0])); ripple.setAttribute('cy', f1(c.p[1])); ripple.setAttribute('r', f1(10 + 36 * u)); ripple.setAttribute('opacity', f1((1 - u) * 0.9)); }
				else ripple.setAttribute('opacity', 0);
			} else curG.setAttribute('opacity', 0);
		};
	}

	// 片子裡所有寫了 screen 描述的電腦畫面都接上；回傳每格要呼叫的 render(t)
	function mountAll(api, screensData) {
		var fns = [];
		(api.screens || []).forEach(function (scr, k) {
			var data = screensData && screensData[k];
			if (scr && data && data.screen) fns.push(mount(scr, data, api));
		});
		return function (t) { for (var i = 0; i < fns.length; i++) fns[i](t); };
	}

	var X = { schedule: schedule, mount: mount, mountAll: mountAll };
	if (typeof module !== 'undefined') module.exports = X; else g.ChalkVSCode = X;
})(this);
