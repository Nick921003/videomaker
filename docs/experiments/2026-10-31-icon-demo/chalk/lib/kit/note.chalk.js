// 黑板文字：在框內斷行、放不下就縮字級，再放不下明確報錯；寫出來走套件的 seq 逐字寫。
(function (g) {
	'use strict';
	var STYLES = { headline: 60, body: 46, accent: 46, code: 46, small: 38 };
	var MIN = 30, STEP = 4, LEADING = 1.3, CPS = 8;
	var CLS = { ink: 'cw', muted: 'cm', accent: 'cy', warn: 'cp', ok: 'cg', info: 'cb' };

	var wide = function (c) { return c.charCodeAt(0) > 255; };

	// 中文逐字斷，英數以詞為單位；整個詞比行還寬時退成逐字
	function tokens(text, maxW, size, measure) {
		var out = [], run = '';
		var flush = function () {
			if (!run) return;
			if (measure(run, size) > maxW) Array.from(run).forEach(function (c) { out.push(c); });
			else out.push(run);
			run = '';
		};
		Array.from(text).forEach(function (c) {
			if (wide(c)) { flush(); out.push(c); }
			else if (/\s/.test(c)) { flush(); out.push(' '); }
			else run += c;
		});
		flush();
		return out;
	}
	function wrap(text, maxW, size, measure) {
		var lines = [], line = '';
		tokens(text, maxW, size, measure).forEach(function (tk) {
			if (tk === ' ' && !line) return;
			if (line && measure(line + tk, size) > maxW) {
				lines.push(line.replace(/\s+$/, ''));
				line = '';
				if (tk === ' ') return;
			}
			line += tk;
		});
		if (line) lines.push(line.replace(/\s+$/, ''));
		return lines;
	}

	// measure(text, size) → 寬，由呼叫端傳入；高度＝行數 × 字級 × 1.3
	function layout(text, style, maxW, maxH, measure) {
		var size = STYLES[style];
		if (!size) throw new Error('未知的文字樣式 ' + style);
		for (;;) {
			var lines = wrap(text, maxW, size, measure);
			var fits = lines.length * size * LEADING <= maxH && lines.every(function (l) { return measure(l, size) <= maxW; });
			if (fits) return { size: size, lines: lines };
			if (size <= MIN) throw new Error('文字放不下 ' + maxW + '×' + maxH + '（字級已縮到 ' + MIN + '）：' + text);
			size = Math.max(MIN, size - STEP);
		}
	}

	function problem(msg) {
		if (g.__boardProblems && g.__boardProblems.push) g.__boardProblems.push(msg);
	}

	// obj: {text, style, tone}；acts: [{act: write|show|erase, t0, t1}]
	function perform(api, P, obj, box, acts) {
		var style = obj.style || 'body', els = [];
		var tone = obj.tone || (style === 'accent' ? 'accent' : 'ink');
		var measure = api.measure || function (s, size) { return api.K.wlen(s) * size; };
		var lay;
		try { lay = layout(obj.text, style, box.w, box.h, measure); } catch (e) { problem(e.message); throw e; }
		var cls = (CLS[tone] || 'cw') + (style === 'code' ? ' lat' : '');
		acts.forEach(function (a) {
			if (a.act === 'write' || a.act === 'show') {
				var chars = lay.lines.reduce(function (n, l) { return n + Array.from(l).length; }, 0);
				var cps = Math.max(CPS, chars / Math.max(0.01, a.t1 - a.t0)), t = a.t0;
				lay.lines.forEach(function (l, i) {
					var r = api.seq(P, box.x, box.y + i * lay.size * LEADING, lay.size, [[l, cls]], t, cps);
					els.push(r);
					t = r.end;
				});
			} else if (a.act === 'erase') api.X(P, els, [box.x, box.y, box.w, box.h], a.t0, 0.4);
		});
		return { els: els, size: lay.size, lines: lay.lines };
	}

	var X = { STYLES: STYLES, MIN: MIN, LEADING: LEADING, layout: layout, perform: perform };
	if (typeof module !== 'undefined') module.exports = X; else g.ChalkNote = X;
})(this);
