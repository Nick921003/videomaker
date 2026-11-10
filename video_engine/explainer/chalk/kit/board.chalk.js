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

	var GAP = 60, ROW_GAP = 120, MIN_SCALE = 0.6;
	// 圖示放大：整組最多佔格子寬高的 90%，單一圖示最多放大到 1.85 倍
	var FILL_W = 0.9, FILL_H = 0.9, GROW_MAX = 1.85;
	// 置中頁用黑板自己的大格子（圖區的 90%×96%）；BoardTpl 的 72%×86% 是 printf 片定稿的數值，不動它
	var CENTER_W = 0.9, CENTER_H = 0.96;
	// 標註框放不下時，圖示放大倍率每次收小成 0.85 倍再試
	var GROW_BACK = 0.85;
	// 黑板會畫的動作；其他動作（arrow、focus…）還沒有粉筆畫法，要報出來，不能安靜略過
	var ACTS = { icon: { draw: 1, show: 1, blink: 1, erase: 1 }, note: { write: 1, show: 1, erase: 1 } };
	var MARKS = { circle: 1, underline: 1 };
	var CLS = { ink: 'cw', muted: 'cm', accent: 'cy', warn: 'cp', ok: 'cg', info: 'cb' };
	var CALLOUT_SIZE = 57, CALLOUT_W = 4.5, CALLOUT_CPS = 12, CALLOUT_FADE = 0.3;
	// 圈與底線的粗細、留白：printf 片手寫的 ring／underline 乘 1.5，跟放大後的圖示與字相稱
	var MARK_W = 6.75, RING_PAD = 33, RING_TURN = 1.12, RING_GROW = 0.05, UNDER_GAP = 18, UNDER_AMP = 7.5, UNDER_PER = 45, MARK_FADE = 0.4;

	var where = function (bd) { return '第 ' + bd.lines.join('、') + ' 句的黑板頁'; };

	// 物件由上而下排（間距 60），置中頁寫 dir: row 時左右並排（間距 120）。
	// 圖示少的頁先把圖示放大（黑板自己的風格：粉筆畫要大才看得清楚，文字不跟著放大）；
	// 整組太高或太寬就把物件等比縮小，縮到 0.6 還放不下就報錯
	function place(board, tpl, sizeOf, growMax) {
		var cols, row = board.dir === 'row';
		if (board.dir != null && (!row || board.template !== 'center')) throw new Error(where(board) + '：dir 只能在置中頁寫 row');
		if (board.template === 'center') cols = [{ box: tpl, objs: board.objects }];
		else if (board.template === 'two-col') {
			cols = ['left', 'right'].map(function (side) {
				return { box: tpl[side], objs: board.objects.filter(function (o) { return o.col === side; }) };
			});
			board.objects.forEach(function (o) {
				if (o.col !== 'left' && o.col !== 'right') throw new Error(where(board) + '：雙欄頁的 ' + o.id + ' 沒寫 col');
			});
		} else throw new Error(where(board) + '：黑板還不會排 ' + board.template + ' 模板');
		// 主軸＝排列方向：直排是高、橫排是寬
		var main = row ? 'w' : 'h', cross = row ? 'h' : 'w', gap = row ? ROW_GAP : GAP;
		var fill = { w: FILL_W, h: FILL_H };
		var sum = function (list, key) { return list.reduce(function (n, s) { return n + s[key]; }, 0); };
		var most = function (list, key) { return Math.max.apply(null, list.map(function (s) { return s[key]; })); };
		var g = growMax == null ? GROW_MAX : growMax;
		cols.forEach(function (c) {
			c.sizes = c.objs.map(function (o) { return sizeOf(o, c.box); });
			var big = c.sizes.filter(function (s) { return s.grow; }), rest = c.sizes.filter(function (s) { return !s.grow; });
			if (!big.length) return;
			g = Math.min(g, (c.box[main] * fill[main] - gap * (c.sizes.length - 1) - sum(rest, main)) / sum(big, main), c.box[cross] * fill[cross] / most(big, cross));
		});
		g = Math.max(1, g);
		var k = 1;
		cols.forEach(function (c) {
			// 整頁用同一個放大倍率，左右兩欄的圖示才一樣大
			c.sizes = c.sizes.map(function (s) { return s.grow ? { w: Math.floor(s.w * g + 1e-6), h: Math.floor(s.h * g + 1e-6) } : s; });
			if (!c.objs.length) return;
			k = Math.min(k, (c.box[main] - gap * (c.objs.length - 1)) / sum(c.sizes, main), c.box[cross] / most(c.sizes, cross));
		});
		if (k < MIN_SCALE) throw new Error(where(board) + '放不下：要縮到 ' + Math.max(0, k).toFixed(2) + ' 倍（下限 ' + MIN_SCALE + '），請減少物件或改小尺寸');
		var out = {};
		cols.forEach(function (c) {
			var sz = c.sizes.map(function (s) { return { w: Math.floor(s.w * k + 1e-6), h: Math.floor(s.h * k + 1e-6) }; });
			var total = sum(sz, main) + gap * Math.max(0, sz.length - 1);
			var at = c.box[row ? 'x' : 'y'] + Math.floor((c.box[main] - total) / 2);
			c.objs.forEach(function (o, n) {
				var mid = c.box[row ? 'y' : 'x'] + Math.floor((c.box[cross] - sz[n][cross]) / 2);
				out[o.id] = row ? { x: at, y: mid, w: sz[n].w, h: sz[n].h } : { x: mid, y: at, w: sz[n].w, h: sz[n].h };
				at += sz[n][main] + gap;
			});
		});
		return out;
	}

	// 黑板頁的格子：雙欄照 BoardTpl，置中頁放寬成黑板自己的大格子
	function grid(A, kind) {
		var t = BT.tpl(A, kind);
		if (kind !== 'center' || !t) return t;
		var w = Math.round(A.w * CENTER_W), h = Math.round(A.h * CENTER_H);
		var x = Math.round(A.x + (A.w - w) / 2), y = Math.round(A.y + (A.h - h) / 2);
		return { P: A.P, x: x, y: y, w: w, h: h, cx: Math.round(x + w / 2), cy: Math.round(y + h / 2) };
	}

	// 寫字的寬度用套件的估算；高度＝行數 × 字級 × 行距。往上取整，縮放前排進去的框不會比字窄
	function sizeOf(api, o, box) {
		if (o.type === 'icon') { var s = CI.sizeOf(o); return { w: s.w, h: s.h, grow: true }; }
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

	var f1 = function (v) { return (Math.round(v * 10) / 10).toString(); };

	// 繞框一圈多一點、半徑微微變大的手畫圈；碰到頁面邊就收小，不畫出這頁
	function ringPath(b, A) {
		var cx = b.x + b.w / 2, cy = b.y + b.h / 2, k = 1 + RING_GROW;
		var rx = Math.min(b.w / 2 + RING_PAD, (cx - A.x) / k, (A.x + A.w - cx) / k);
		var ry = Math.min(b.h / 2 + RING_PAD, (cy - A.y) / k, (A.y + A.h - cy) / k);
		var n = 44, a0 = -Math.PI * 0.6, d = '';
		for (var i = 0; i <= n; i++) {
			var a = a0 + (i / n) * RING_TURN * Math.PI * 2, r = 1 + RING_GROW * (i / n);
			d += (i ? ' L ' : 'M ') + f1(cx + Math.cos(a) * rx * r) + ' ' + f1(cy + Math.sin(a) * ry * r);
		}
		return d;
	}

	// 框底下一條波浪線；框貼著頁底時往上收，不畫出這頁
	function underPath(b, A) {
		var y = Math.min(b.y + b.h + UNDER_GAP, A.y + A.h - UNDER_AMP), x1 = b.x + b.w, d = 'M ' + f1(b.x) + ' ' + f1(y);
		for (var x = b.x + UNDER_PER / 2, j = 1; x <= x1 + 0.1; x += UNDER_PER / 2, j++) {
			d += ' Q ' + f1(x - UNDER_PER / 4) + ' ' + f1(y + (j % 2 ? -UNDER_AMP : UNDER_AMP)) + ' ' + f1(x) + ' ' + f1(y);
		}
		return d;
	}

	// 圈與底線留到這頁換掉；目標之後被擦掉的話跟著淡出，不留一個圈著空白的圈
	function mark(api, P, A, box, a, acts) {
		var el = api.S(P, a.act === 'circle' ? ringPath(box, A) : underPath(box, A), (a.args && a.args.tone) || 'accent', MARK_W, a.t0, a.t1 - a.t0, { sprite: false });
		var er = acts.filter(function (b) { return b.obj === a.obj && b.act === 'erase' && b.t0 >= a.t0; })[0];
		if (er) api.K.fade([el], er.t0, MARK_FADE, 0);
		return el;
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
		var tpl = grid(A, bd.template);
		var acts = timed(api, bd), end = api.lineEnd(last);
		// 圖示放到最大時標註框可能四邊都沒位置：先把放大倍率一步步收小讓出空間，收到不放大還放不下才報錯
		var boxes, plan, grow = GROW_MAX;
		for (;;) {
			boxes = place(bd, tpl, function (o, box) { return sizeOf(api, o, box); }, grow);
			plan = callouts(api, A, boxes, acts);
			if (!plan.fails.length || grow <= 1) break;
			grow = Math.max(1, grow * GROW_BACK);
		}
		bd.objects.forEach(function (o) {
			if (o.caption) report(here + '：' + o.id + ' 的 caption 黑板還不畫');
			var own = acts.filter(function (a) { return a.obj === o.id && a.act !== 'callout' && !MARKS[a.act]; });
			var ok = own.filter(function (a) { return ACTS[o.type] && ACTS[o.type][a.act]; });
			own.filter(function (a) { return ok.indexOf(a) < 0; }).forEach(function (a) { report(here + '：' + o.id + ' 的 ' + a.act + ' 黑板還不會畫'); });
			try {
				if (o.type === 'icon') CI.perform(api, tpl.P, o, boxes[o.id], ok, o.tone);
				else CN.perform(api, tpl.P, o, boxes[o.id], ok);
			} catch (e) { report(here + '：' + e.message); }
		});
		acts.forEach(function (a) {
			if (MARKS[a.act]) mark(api, tpl.P, A, boxes[a.obj], a, acts);
		});
		plan.fails.forEach(function (m) { report(here + '：' + m); });
		plan.ok.forEach(function (c) {
			callout(api, tpl.P, c.p, c.size, c.a, (c.a.args && c.a.args.tone) || 'ink', CO.endTime(acts, c.i, c.a.untilT, end));
		});
	}

	// 只算標註框的位置，不畫：回傳放得下的（ok）與放不下的訊息（fails）
	function callouts(api, A, boxes, acts) {
		var taken = [], ok = [], fails = [];
		acts.forEach(function (a, i) {
			if (a.act !== 'callout') return;
			var anchor = boxes[a.target];
			if (!anchor) { fails.push('callout 指到 ' + a.target + '，黑板量不到這個位置'); return; }
			var size = CO.size(a.args.text, function (s, st) { return { w: api.K.wlen(s) * st.size }; }, { size: CALLOUT_SIZE });
			var obstacles = Object.keys(boxes).filter(function (id) { return id !== a.target; }).map(function (id) { return boxes[id]; }).concat(taken);
			var p = CO.place(anchor, size, A, obstacles);
			if (!p) { fails.push(a.obj + ' 的 callout 四邊都放不下：' + a.args.text); return; }
			taken.push(p.box);
			ok.push({ a: a, i: i, p: p, size: size });
		});
		return { ok: ok, fails: fails };
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

	var X = { GAP: GAP, MIN_SCALE: MIN_SCALE, grid: grid, place: place, mountAll: mountAll, checkSchedule: checkSchedule };
	if (typeof module !== 'undefined') module.exports = X; else g.ChalkBoard = X;
})(this);
