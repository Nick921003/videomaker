// VS Code 元件：描述＋動作＋t → 版面、狀態、錨點。純函式，不碰畫布，手帳、黑板、配圖共用。
// 版面比例取自 printf 黑板片的 vscodeMock（已對過實機截圖），以高 1000 為基準等比縮放。
(function (g) {
	'use strict';
	var SIZE = [1600, 1000];

	// fs 是字級倍率：手帳畫面縮得小，字和跟字有關的行高一起放大，外框尺寸不變
	function metrics(size, fs) {
		var k = size[1] / 1000, f = k * (fs || 1);
		return {
			k: k, f: f, titleH: 48 * f, actW: 68 * k, expW: Math.min(320 * Math.max(k, f * 0.8), size[0] * 0.24), tabH: 52 * f, ptabH: 48 * f, statusH: 26 * f,
			ui: 22 * f, code: 24 * f, pitch: 36 * f, out: 24 * f, outPitch: 38 * f, gutter: 100 * f, pad: 28 * k,
		};
	}

	// 估字寬：中日韓 1em，其餘等寬 0.6em、比例字 0.52em（與 vscodeMock 的 tw 相同）
	function textW(str, size, mono) {
		var n = 0, s = String(str);
		for (var i = 0; i < s.length; i++) {
			var c = s.charCodeAt(i);
			n += c >= 0x2e80 && c <= 0xffef ? 1 : c === 9 ? (mono ? 2.4 : 2.08) : mono ? 0.6 : 0.52;
		}
		return n * size;
	}

	var R = function (x, y, w, h) { return { x: Math.round(x), y: Math.round(y), w: Math.max(0, Math.round(w)), h: Math.max(0, Math.round(h)) }; };
	var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };

	function layout(desc, size) {
		size = size || SIZE;
		var W = size[0], H = size[1], m = metrics(size, desc._text);
		var bodyY = m.titleH, bodyH = H - m.titleH - m.statusH, editX = m.actW + m.expW;
		var panelH = Math.round(bodyH * 0.44), panelY = bodyY + bodyH - panelH;
		return {
			w: W, h: H, m: m,
			regions: {
				title: R(0, 0, W, m.titleH),
				activity: R(0, bodyY, m.actW, bodyH),
				explorer: R(m.actW, bodyY, m.expW, bodyH),
				tabs: R(editX, bodyY, W - editX, m.tabH),
				editor: R(editX, bodyY + m.tabH, W - editX, panelY - bodyY - m.tabH),
				panel: R(editX, panelY, W - editX, panelH),
				status: R(0, H - m.statusH, W, m.statusH),
			},
		};
	}

	// 預設檔的項目，統一成 [{id, ...}]；齒輪選單沿用手帳 window 元件的表格格式
	function presetItems(desc, name) {
		var p = (desc._presets || {})[name];
		if (!p) return [];
		if (p.items) return p.items;
		var rows = [];
		(function walk(n) {
			if (Array.isArray(n)) n.forEach(walk);
			else if (n && typeof n === 'object') {
				if (n.table) n.table.rows.forEach(function (r) { rows.push({ id: r.id, text: r.cells[0], key: r.cells[1] || '' }); });
				else Object.keys(n).forEach(function (k) { walk(n[k]); });
			}
		})(p.body || p);
		return rows;
	}

	function seqCount(a, t) {
		if (t < a.t0) return 0;
		var n = a.n || 1, per = (a.t1 - a.t0) / n;
		return per <= 0 ? n : Math.min(n, Math.floor((t - a.t0) / per) + 1);
	}
	var prog = function (a, t) { return a.t1 > a.t0 ? clamp((t - a.t0) / (a.t1 - a.t0), 0, 1) : 1; };

	function codeRows(lay) {
		var m = lay.m, ed = lay.regions.editor;
		return Math.max(1, Math.floor((ed.h - 14 * m.f) / m.pitch));
	}

	function state(desc, acts, t, size) {
		var lay = layout(desc, size);
		// 輸出面板與終端機各有自己的內容，切換分頁時互不影響
		var panels = { output: [], terminal: [] }, kind = desc.panel || 'output';
		var st = { open: desc.open, highlight: null, scrollTop: 0, panel: { kind: kind, lines: panels[kind], running: false }, menu: null, page: null, fade: 1, checks: {},
			tip: null, search: '', searchTyped: acts.some(function (a) { return a.obj === desc.id && a.act === 'type'; }) };
		presetItems(desc, 'settings').forEach(function (it) { if (typeof it.check === 'boolean') st.checks[it.id] = it.check; });
		var own = acts.filter(function (a) { return a.obj === desc.id; }).slice().sort(function (a, b) { return a.t0 - b.t0; });
		var MARK = { circle: 1, underline: 1, arrow: 1, show: 1, hide: 1, focus: 1 };
		own.forEach(function (a) {
			if (t < a.t0) return;
			var x = a.args || {}, lines = st.panel.lines;
			// 提示框到下一個操作就收（標記、鏡頭不算操作）
			if (!MARK[a.act]) st.tip = null;
			switch (a.act) {
				case 'open': st.open = x.file; st.highlight = null; break;
				case 'highlight':
					st.open = x.file || st.open;
					st.highlight = { file: st.open, lines: x.lines, p: prog(a, t) };
					break;
				case 'run':
					st.panel.running = true;
					// 輸出面板每次執行會清掉；終端機往下接
					if (st.panel.kind === 'output') lines.length = 0;
					(x.output || []).forEach(function (s) { lines.push(s); });
					break;
				case 'print': x.lines.slice(0, seqCount(a, t)).forEach(function (s) { lines.push(s); }); break;
				case 'input':
					if (!lines.length) lines.push('');
					lines[lines.length - 1] += Array.from(x.text).slice(0, seqCount(a, t)).join('');
					break;
				case 'stop': st.panel.running = false; break;
				case 'panel': st.panel.kind = x.name; st.panel.lines = panels[x.name]; break;
				case 'tip': st.tip = x.text; break;
				case 'type': st.search += Array.from(x.text).slice(0, seqCount(a, t)).join(''); break;
				case 'menu': st.menu = x.name; st.page = null; st.fade = prog(a, t); break;
				case 'page': st.page = x.name; st.menu = null; st.fade = prog(a, t); st.search = ''; break;
				case 'close': st.menu = null; st.page = null; break;
				case 'check': var id = a.target.split(':')[1]; st.checks[id] = !st.checks[id]; break;
			}
		});
		if (st.highlight) {
			var V = codeRows(lay), last = Math.max.apply(null, st.highlight.lines), n = desc.files[st.open].length;
			// 高亮行在可見範圍外就捲過去，下面多留一行
			if (last > V - 1) st.scrollTop = clamp(last - V + 1, 0, Math.max(0, n - V));
		}
		return st;
	}

	function tabBoxes(desc, lay) {
		var m = lay.m, tb = lay.regions.tabs, names = Object.keys(desc.files);
		var ws = names.map(function (nm) { return (20 + 24 + 8 + 38 + 20) * m.f + textW(nm, m.ui); });
		var room = tb.w - 200 * m.k, sum = ws.reduce(function (s, w) { return s + w; }, 0), f = sum > room ? room / sum : 1;
		var x = tb.x, out = {};
		names.forEach(function (nm, i) { out[nm] = R(x, tb.y, ws[i] * f, tb.h); x += ws[i] * f; });
		return out;
	}

	function explorerRows(desc, lay) {
		var m = lay.m, ex = lay.regions.explorer, names = desc.explorer || Object.keys(desc.files);
		var top = ex.y + 100 * m.f, rp = Math.min(44 * m.f, (ex.h - 100 * m.f - 120 * m.k) / Math.max(1, names.length));
		var out = {};
		names.forEach(function (nm, i) { out[nm] = R(ex.x, top + i * rp, ex.w, rp); });
		return out;
	}

	function menuBox(desc, lay, name) {
		var m = lay.m, act = lay.regions.activity, rows = presetItems(desc, name).length;
		var h = rows * 40 * m.f + 16 * m.k, bottom = act.y + act.h - 30 * m.k;
		return R(act.x + act.w + 6 * m.k, bottom - h, 460 * m.f, h);
	}

	function pageBox(lay) {
		var m = lay.m;
		return R(m.actW + 40 * m.k, m.titleH + 30 * m.k, lay.w - m.actW - 80 * m.k, lay.h - m.titleH - m.statusH - 60 * m.k);
	}

	function pageParts(lay) {
		var m = lay.m, pg = pageBox(lay);
		var search = R(pg.x + 36 * m.k, pg.y + 70 * m.f, pg.w - 72 * m.k, 40 * m.f);
		return { box: pg, head: R(pg.x, pg.y, pg.w, 50 * m.f), search: search, listX: pg.x + 340 * m.k, listY: search.y + search.h + 70 * m.f };
	}

	function panelRows(lay) {
		var m = lay.m, p = lay.regions.panel;
		return Math.max(1, Math.floor((p.h - m.ptabH - 16 * m.f) / m.outPitch));
	}

	// 面板裡看得到的行：太多就只留最後幾行（終端機往上捲）
	function panelView(st, lay) {
		var lines = st.panel.lines, V = panelRows(lay);
		return lines.slice(Math.max(0, lines.length - V));
	}

	function panelTabs(lay) {
		var m = lay.m, p = lay.regions.panel, x = p.x + m.pad, out = {};
		[['problems', '問題'], ['output', '輸出'], ['debug', '偵錯主控台'], ['terminal', '終端機']].forEach(function (tb) {
			var w = textW(tb[1], m.ui);
			out[tb[0]] = { label: tb[1], box: R(x, p.y + 8 * m.f, w, m.ptabH - 12 * m.f) };
			x += w + 44 * m.f;
		});
		return out;
	}

	function tipBox(st, lay, end) {
		var m = lay.m, p = lay.regions.panel, w = textW(st.tip, m.ui) + 44 * m.f, h = 48 * m.f;
		var x = Math.min(end.x + 48 * m.f, p.x + p.w - m.pad - w);
		return R(x, end.y + end.h / 2 - h / 2, w, h);
	}

	function anchors(desc, st, size) {
		var lay = layout(desc, size), m = lay.m, rg = lay.regions, out = {};
		var W = lay.w;
		// 離右側的分割、··· 鈕留一個圈的空間，畫圈才不會壓到它們
		var runCx = W - 200 * m.k, runCy = rg.tabs.y + rg.tabs.h / 2;
		out.run = R(runCx - 28 * m.k, runCy - 26 * m.k, 56 * m.k, 52 * m.k);
		var gcy = rg.activity.y + rg.activity.h - 50 * m.k;
		out.gear = R(rg.activity.w / 2 - 28 * m.k, gcy - 28 * m.k, 56 * m.k, 56 * m.k);
		out.explorer = rg.explorer; out.editor = rg.editor; out.panel = rg.panel;

		var ed = rg.editor, top = ed.y + 14 * m.f, V = codeRows(lay), right = ed.x + ed.w - m.pad;
		desc.files[st.open].forEach(function (ln, i) {
			var row = i - st.scrollTop, x = ed.x + m.gutter;
			var w = Math.min(Math.max(textW(ln, m.code, true), m.code), right - x);
			if (row < 0) out['L' + (i + 1)] = R(x, ed.y, w, 0);
			else if (row >= V) out['L' + (i + 1)] = R(x, ed.y + ed.h, w, 0);
			else out['L' + (i + 1)] = R(x, top + row * m.pitch, w, m.pitch);
		});

		var tabs = tabBoxes(desc, lay);
		Object.keys(tabs).forEach(function (f) { out['tab:' + f] = tabs[f]; });
		var rows = explorerRows(desc, lay);
		Object.keys(rows).forEach(function (f) { out['file:' + f] = rows[f]; });

		var p = rg.panel, view = panelView(st, lay), k = Math.max(0, view.length - 1);
		var px = p.x + m.pad, maxX = p.x + p.w - m.pad - m.out;
		var endX = Math.min(px + textW(view[k] || '', m.out, true), maxX);
		out['panel:end'] = R(endX, p.y + m.ptabH + 8 * m.f + k * m.outPitch, m.out, m.outPitch);
		// P{n} 是面板的第 n 行（絕對行號），不是看得到的第 n 行：可見行數隨字級倍率不同，用可見序號會讓同一份描述在各風格圈到不同行。
		// 捲出畫面的行與 L{n} 一樣給零高的框
		var lines = st.panel.lines, first = lines.length - view.length, py = p.y + m.ptabH + 8 * m.f;
		lines.forEach(function (s, i) {
			var row = i - first, w = Math.min(Math.max(textW(s, m.out, true), m.out), maxX + m.out - px);
			out['P' + (i + 1)] = row < 0 ? R(px, py, w, 0) : R(px, py + row * m.outPitch, w, m.outPitch);
		});
		var pt = panelTabs(lay);
		out['ptab:output'] = pt.output.box; out['ptab:terminal'] = pt.terminal.box;
		if (st.tip) out.tip = tipBox(st, lay, out['panel:end']);

		var parts = pageParts(lay);
		out['settings:search'] = parts.search;
		if (st.menu) {
			var mb = menuBox(desc, lay, st.menu);
			presetItems(desc, st.menu).forEach(function (it, i) { out[it.id] = R(mb.x + 8 * m.k, mb.y + 8 * m.k + i * 40 * m.f, mb.w - 16 * m.k, 40 * m.f); });
		}
		if (st.page) {
			var pitch = st.page === 'settings' ? 120 * m.f : 110 * m.f;
			var x0 = st.page === 'settings' ? parts.listX : parts.search.x;
			var y0 = st.page === 'settings' ? parts.listY : parts.search.y + parts.search.h + 24 * m.f;
			presetItems(desc, st.page).forEach(function (it, i) {
				out[it.id] = R(x0, Math.min(y0 + i * pitch, parts.box.y + parts.box.h - pitch), parts.box.x + parts.box.w - 36 * m.k - x0, pitch - 10 * m.f);
			});
		}
		return out;
	}

	var X = { SIZE: SIZE, metrics: metrics, textW: textW, layout: layout, state: state, anchors: anchors,
		presetItems: presetItems, codeRows: codeRows, panelView: panelView, tabBoxes: tabBoxes, explorerRows: explorerRows,
		menuBox: menuBox, pageParts: pageParts, panelTabs: panelTabs, tipBox: tipBox };
	if (typeof module !== 'undefined') module.exports = X; else g.VSCodeModel = X;
})(this);
