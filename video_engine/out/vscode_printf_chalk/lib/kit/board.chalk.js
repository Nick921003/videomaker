// 黑板通用轉接：分鏡寫好的置中／雙欄頁（objects.json 併成 story.boards）照模板排進格子、照逐字時間畫，不用寫 beats.js。
// 排程直接用 vscode.chalk.js 的 schedule，畫交給 icon.chalk.js／note.chalk.js，標註框的擺放用共用的 Callout。
(function (g) {
	'use strict';
	var node = typeof module !== 'undefined';
	var BT = node ? require('./board_tpl.js') : g.BoardTpl;
	var CV = node ? require('./vscode.chalk.js') : g.ChalkVSCode;
	var CI = node ? require('./icon.chalk.js') : g.ChalkIcon;
	var CN = node ? require('./note.chalk.js') : g.ChalkNote;
	var CO = node ? require('../../../components/callout/callout.js') : g.Callout;

	var GAP = 40, MIN_SCALE = 0.6;
	// 黑板會畫的動作；其他動作（circle、arrow…）還沒有粉筆畫法，要報出來，不能安靜略過
	var ACTS = { icon: { draw: 1, show: 1, blink: 1, erase: 1 }, note: { write: 1, show: 1, erase: 1 } };
	var CLS = { ink: 'cw', muted: 'cm', accent: 'cy', warn: 'cp', ok: 'cg', info: 'cb' };
	var CALLOUT_SIZE = 38, CALLOUT_W = 3, CALLOUT_CPS = 12, CALLOUT_FADE = 0.3;

	var where = function (bd) { return '第 ' + bd.lines.join('、') + ' 句的黑板頁'; };

	// 物件由上而下排，間距固定 40；整組太高（或太寬）就把物件等比縮小，縮到 0.6 還放不下就報錯
	function place(board, tpl, sizeOf) {
		var cols;
		if (board.template === 'center') cols = [{ box: tpl, objs: board.objects }];
		else if (board.template === 'two-col') {
			cols = ['left', 'right'].map(function (side) {
				return { box: tpl[side], objs: board.objects.filter(function (o) { return o.col === side; }) };
			});
			board.objects.forEach(function (o) {
				if (o.col !== 'left' && o.col !== 'right') throw new Error(where(board) + '：雙欄頁的 ' + o.id + ' 沒寫 col');
			});
		} else throw new Error(where(board) + '：黑板還不會排 ' + board.template + ' 模板');
		var k = 1;
		cols.forEach(function (c) {
			c.sizes = c.objs.map(function (o) { return sizeOf(o, c.box); });
			if (!c.objs.length) return;
			var sumH = c.sizes.reduce(function (n, s) { return n + s.h; }, 0), maxW = Math.max.apply(null, c.sizes.map(function (s) { return s.w; }));
			k = Math.min(k, (c.box.h - GAP * (c.objs.length - 1)) / sumH, c.box.w / maxW);
		});
		if (k < MIN_SCALE) throw new Error(where(board) + '放不下：要縮到 ' + Math.max(0, k).toFixed(2) + ' 倍（下限 ' + MIN_SCALE + '），請減少物件或改小尺寸');
		var out = {};
		cols.forEach(function (c) {
			var sz = c.sizes.map(function (s) { return { w: Math.floor(s.w * k + 1e-6), h: Math.floor(s.h * k + 1e-6) }; });
			var total = sz.reduce(function (n, s) { return n + s.h; }, 0) + GAP * Math.max(0, sz.length - 1);
			var y = c.box.y + Math.floor((c.box.h - total) / 2);
			c.objs.forEach(function (o, i) {
				out[o.id] = { x: c.box.x + Math.floor((c.box.w - sz[i].w) / 2), y: y, w: sz[i].w, h: sz[i].h };
				y += sz[i].h + GAP;
			});
		});
		return out;
	}

	// 寫字的寬度用套件的估算；高度＝行數 × 字級 × 行距。往上取整，縮放前排進去的框不會比字窄
	function sizeOf(api, o, box) {
		if (o.type === 'icon') { var s = CI.SIZE[o.size || 'm']; return { w: s, h: s }; }
		if (o.type === 'note') {
			var measure = function (s, size) { return api.K.wlen(s) * size; };
			var lay = CN.layout(o.text, o.style || 'body', box.w, box.h, measure);
			var w = Math.max.apply(null, lay.lines.map(function (l) { return measure(l, lay.size); }));
			return { w: Math.ceil(w), h: Math.ceil(lay.lines.length * lay.size * CN.LEADING) };
		}
		throw new Error('黑板還沒有 ' + o.type + ' 的粉筆皮膚（' + o.id + '）');
	}

	var untilOf = function (a, span) { return a.args && a.args.until != null ? span(a.args.until_line, a.args.until).start : null; };

	// schedule 照 cue／drawAt 排出 t0；dur 為 null（until 類）的動作 t1 換成 until 那幾個字開口的時刻，沒寫 until 就到這頁最後一句講完
	function timed(api, bd) {
		var src = [];
		bd.lines.forEach(function (li) { (bd.do[String(li)] || []).forEach(function (a) { src.push(a); }); });
		var end = api.lineEnd(bd.lines[bd.lines.length - 1]);
		return CV.schedule(bd, api.span, api.drawAt).map(function (x, i) {
			x.untilT = untilOf(src[i], api.span);
			if (src[i].dur == null) x.t1 = x.untilT != null ? x.untilT : end;
			return x;
		});
	}

	function roundRect(b, r) {
		var x0 = b.x, y0 = b.y, x1 = b.x + b.w, y1 = b.y + b.h, f = function (v) { return (Math.round(v * 10) / 10).toString(); };
		var p = function (x, y) { return f(x) + ' ' + f(y); };
		return 'M ' + p(x0 + r, y0) + ' L ' + p(x1 - r, y0) + ' Q ' + p(x1, y0) + ' ' + p(x1, y0 + r) + ' L ' + p(x1, y1 - r) + ' Q ' + p(x1, y1) + ' ' + p(x1 - r, y1) +
			' L ' + p(x0 + r, y1) + ' Q ' + p(x0, y1) + ' ' + p(x0, y1 - r) + ' L ' + p(x0, y0 + r) + ' Q ' + p(x0, y0) + ' ' + p(x0 + r, y0);
	}

	// 標註框：框與三角在動作時間內畫完，字隨後以穩定手速寫上，到 until（或同物件下一個動作、這頁講完）擦淡
	function callout(api, P, p, size, a, tone, tEnd) {
		var b = p.box, f = size.f, half = (a.t1 - a.t0) / 2, fs = CALLOUT_SIZE;
		var tri = CO.arrowPts(p).map(function (q, i) { return (i ? 'L ' : 'M ') + q[0].toFixed(1) + ' ' + q[1].toFixed(1); }).join(' ');
		var els = [api.S(P, roundRect(b, CO.RADIUS * f), tone, CALLOUT_W, a.t0, half, { sprite: false }), api.S(P, tri, tone, CALLOUT_W, a.t0 + half, half, { sprite: false })];
		els.push(api.seq(P, Math.round(b.x + CO.PAD * f), Math.round(b.y + b.h / 2 - fs * 0.65), fs, [[a.args.text, CLS[tone] || 'cw']], a.t1, CALLOUT_CPS, { sprite: false }));
		api.K.fade(els, tEnd, CALLOUT_FADE, 0);
		return els;
	}

	function mount(api, bd, report) {
		var first = bd.lines[0], last = bd.lines[bd.lines.length - 1], here = where(bd);
		var A = api.area(first);
		if (!A) throw new Error(here + '：這頁不在粉筆區（找不到圖區）');
		var tpl = BT.tpl(A, bd.template);
		var boxes = place(bd, tpl, function (o, box) { return sizeOf(api, o, box); });
		var acts = timed(api, bd), end = api.lineEnd(last);
		bd.objects.forEach(function (o) {
			if (o.caption) report(here + '：' + o.id + ' 的 caption 黑板還不畫');
			var own = acts.filter(function (a) { return a.obj === o.id && a.act !== 'callout'; });
			var ok = own.filter(function (a) { return ACTS[o.type] && ACTS[o.type][a.act]; });
			own.filter(function (a) { return ok.indexOf(a) < 0; }).forEach(function (a) { report(here + '：' + o.id + ' 的 ' + a.act + ' 黑板還不會畫'); });
			try {
				if (o.type === 'icon') CI.perform(api, tpl.P, o, boxes[o.id], ok, o.tone);
				else CN.perform(api, tpl.P, o, boxes[o.id], ok);
			} catch (e) { report(here + '：' + e.message); }
		});
		var taken = [];
		acts.forEach(function (a, i) {
			if (a.act !== 'callout') return;
			var anchor = boxes[a.target];
			if (!anchor) { report(here + '：callout 指到 ' + a.target + '，黑板量不到這個位置'); return; }
			var tone = (a.args && a.args.tone) || 'ink';
			var size = CO.size(a.args.text, function (s, st) { return { w: api.K.wlen(s) * st.size }; }, { size: CALLOUT_SIZE });
			var obstacles = Object.keys(boxes).filter(function (id) { return id !== a.target; }).map(function (id) { return boxes[id]; }).concat(taken);
			var p = CO.place(anchor, size, A, obstacles);
			if (!p) { report(here + '：' + a.obj + ' 的 callout 四邊都放不下：' + a.args.text); return; }
			taken.push(p.box);
			callout(api, tpl.P, p, size, a, tone, CO.endTime(acts, i, a.untilT, end));
		});
	}

	// 一頁出錯（放不下、排不到時間）收進 problems，其他頁照畫；starter 把它掛成 window.__boardProblems 給 board_check.py 讀
	function mountAll(api, boards) {
		var problems = [];
		var report = function (msg) { if (problems.indexOf(msg) < 0) problems.push(msg); };
		(boards || []).forEach(function (bd) {
			try { mount(api, bd, report); } catch (e) { report(e.message); }
		});
		// 筆畫、字、淡出都已登記給 Kit.render，每格不用另外畫
		return { problems: problems, render: function () {} };
	}

	// 純排程檢查（node 跑，不必開瀏覽器）：do 的句號都在這頁、cue 都在那句話裡、until 都換算得到時間
	function checkSchedule(boards, span) {
		var out = [];
		(boards || []).forEach(function (bd) {
			Object.keys(bd.do || {}).forEach(function (k) {
				if (bd.lines.indexOf(+k) < 0) out.push(where(bd) + '：do 寫到第 ' + k + ' 句，不在這頁');
			});
			bd.lines.forEach(function (li) {
				((bd.do || {})[String(li)] || []).forEach(function (a) {
					if (a.cue) {
						try { span(li, a.cue); } catch (e) { out.push('第 ' + li + ' 句 ' + a.act + ' 的 cue「' + a.cue + '」不在句子裡'); }
					}
					var u = a.args && a.args.until;
					if (u == null) return;
					if (a.args.until_line == null) { out.push('第 ' + li + ' 句 ' + a.act + ' 的 until「' + u + '」沒有 until_line'); return; }
					try { span(a.args.until_line, u); } catch (e) { out.push('第 ' + li + ' 句 ' + a.act + ' 的 until「' + u + '」不在第 ' + a.args.until_line + ' 句裡'); }
				});
			});
		});
		return out;
	}

	var X = { GAP: GAP, MIN_SCALE: MIN_SCALE, place: place, mountAll: mountAll, checkSchedule: checkSchedule };
	if (typeof module !== 'undefined') module.exports = X; else g.ChalkBoard = X;
})(this);
