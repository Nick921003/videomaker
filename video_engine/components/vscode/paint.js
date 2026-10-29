// VS Code 元件：狀態 → 繪圖指令清單。顏色只寫 vscode_dark.json 的鍵，由各皮膚對應成自己的顏色。
// 指令只有三種：rect、text（y 是垂直中線）、line（折線；圖示也用折線畫，鉛筆皮膚才畫得出來）。
(function (g) {
	'use strict';
	var M = typeof module !== 'undefined' ? require('./model.js') : g.VSCodeModel;
	var textW = M.textW;

	var KW = /^(int|void|char|float|double|long|short|unsigned|signed|const|struct|static|sizeof|typedef|enum)$/;
	var CTL = /^(return|if|else|for|while|do|break|continue|switch|case|default|goto)$/;

	// 簡化的 C 上色：夠像 Dark+ 就好，不做完整解析
	function tokens(line) {
		var out = [], re = /(#\s*\w+)|("(?:[^"\\]|\\.)*"?)|(<[\w.]+>)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)|(\s+)|(.)/g, m;
		while ((m = re.exec(line))) {
			var s = m[0], c = 'pl';
			if (m[1]) c = 'ctl';
			else if (m[2] || m[3]) c = 'str';
			else if (m[4]) c = 'num';
			else if (m[5]) c = CTL.test(s) ? 'ctl' : KW.test(s) ? 'kw' : /^\s*\(/.test(line.slice(re.lastIndex)) ? 'fn' : 'vr';
			out.push([s, c]);
		}
		return out;
	}

	// 放不下就截斷加「…」：寧可少字也不畫出框外
	function fit(str, size, mono, maxW) {
		str = String(str);
		if (textW(str, size, mono) <= maxW) return str;
		var a = Array.from(str);
		while (a.length && textW(a.join('') + '…', size, mono) > maxW) a.pop();
		return a.join('') + '…';
	}

	function bbox(pts) {
		var xs = pts.map(function (p) { return p[0]; }), ys = pts.map(function (p) { return p[1]; });
		var x = Math.min.apply(null, xs), y = Math.min.apply(null, ys);
		return { x: x, y: y, w: Math.max.apply(null, xs) - x, h: Math.max.apply(null, ys) - y };
	}

	function ops(desc, st, t, size) {
		var lay = M.layout(desc, size), m = lay.m, k = m.k, f = m.f, rg = lay.regions, W = lay.w, H = lay.h, out = [];
		var an = M.anchors(desc, st, size);
		var alpha = 1;
		function rect(x, y, w, h, o) { out.push(Object.assign({ op: 'rect', x: x, y: y, w: w, h: h }, o, alpha < 1 ? { alpha: alpha } : {})); }
		function text(str, x, y, sz, color, o) {
			o = o || {};
			var s = o.max ? fit(str, sz, o.mono, o.max) : String(str);
			out.push(Object.assign({ op: 'text', str: s, x: x, y: y, size: sz, color: color, w: textW(s, sz, o.mono) }, o.mono ? { mono: true } : {}, o.bold ? { bold: true } : {}, o.align ? { align: o.align } : {}, o.detail ? { detail: true } : {}, alpha < 1 ? { alpha: alpha } : {}));
			return textW(s, sz, o.mono);
		}
		function line(pts, color, width, o) { out.push(Object.assign({ op: 'line', pts: pts, color: color, width: width * k }, o, alpha < 1 ? { alpha: alpha } : {})); }
		function circle(cx, cy, r, color, width) {
			var pts = [];
			for (var i = 0; i <= 16; i++) { var a = i / 16 * Math.PI * 2; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); }
			line(pts, color, width);
		}

		// ---------- 底色 ----------
		rect(0, 0, W, H, { fill: 'edit' });
		rect(rg.title.x, rg.title.y, rg.title.w, rg.title.h, { fill: 'title' });
		rect(rg.activity.x, rg.activity.y, rg.activity.w, rg.activity.h, { fill: 'act' });
		rect(rg.explorer.x, rg.explorer.y, rg.explorer.w, rg.explorer.h, { fill: 'side' });
		rect(rg.tabs.x, rg.tabs.y, rg.tabs.w, rg.tabs.h, { fill: 'tabBar' });
		rect(rg.status.x, rg.status.y, rg.status.w, rg.status.h, { fill: 'status' });

		// ---------- 標題列 ----------
		var tcy = rg.title.h / 2;
		line([[22 * k, 18 * k], [32 * k, 12 * k], [28 * k, 24 * k], [38 * k, 22 * k], [20 * k, 36 * k], [24 * k, 26 * k], [16 * k, 28 * k], [22 * k, 18 * k]], 'accent', 2);
		var bw = Math.min(560 * k, W * 0.3), bx = (W - bw) / 2, bh = Math.min(rg.title.h - 8 * k, 34 * f);
		var mx = 48 * k;
		['檔案', '編輯', '選取項目', '檢視', '移至', '執行', '終端機', '說明'].forEach(function (s) {
			if (mx + textW(s, m.ui) <= bx - 16 * k) mx += text(s, mx, tcy, m.ui, 'fg') + 22 * f;
			else mx = Infinity;
		});
		rect(bx, tcy - bh / 2, bw, bh, { fill: 'titleBox', stroke: 'menuLine', rx: 6 * k });
		text(desc.folder || 'workspace', bx + 32 * k, tcy, 20 * f, 'dim', { max: bw - 44 * k });

		// ---------- 活動列 ----------
		var ax = rg.activity.w / 2, ay = rg.activity.y + 28 * k, ap = 56 * k;
		rect(0, rg.activity.y, 3 * k, 56 * k, { fill: 'actOn' });
		line([[ax - 12 * k, ay - 14 * k], [ax + 6 * k, ay - 14 * k], [ax + 12 * k, ay - 8 * k], [ax + 12 * k, ay + 14 * k], [ax - 12 * k, ay + 14 * k], [ax - 12 * k, ay - 14 * k]], 'actOn', 2.5);
		circle(ax - 3 * k, ay + ap - 3 * k, 8 * k, 'actOff', 2.5);
		line([[ax + 3 * k, ay + ap + 3 * k], [ax + 12 * k, ay + ap + 12 * k]], 'actOff', 2.5);
		line([[ax - 8 * k, ay + 2 * ap - 14 * k], [ax + 14 * k, ay + 2 * ap], [ax - 8 * k, ay + 2 * ap + 14 * k], [ax - 8 * k, ay + 2 * ap - 14 * k]], 'actOff', 2.5);
		[[-14, -14], [2, -14], [-14, 2], [4, 6]].forEach(function (o) {
			var x = ax + o[0] * k, y = ay + 3 * ap + o[1] * k, s = 12 * k;
			line([[x, y], [x + s, y], [x + s, y + s], [x, y + s], [x, y]], 'actOff', 2.5);
		});
		var gb = an.gear, gx = gb.x + gb.w / 2, gy = gb.y + gb.h / 2;
		circle(ax, gy - 80 * k, 14 * k, 'actOff', 2.5);
		var gear = [];
		for (var i = 0; i < 8; i++) {
			var a0 = i * Math.PI / 4, w1 = Math.PI / 8 * 0.5, w2 = Math.PI / 8 * 0.3;
			[[14, a0 - w1], [20, a0 - w2], [20, a0 + w2], [14, a0 + w1]].forEach(function (p) { gear.push([gx + Math.cos(p[1]) * p[0] * k, gy + Math.sin(p[1]) * p[0] * k]); });
		}
		gear.push(gear[0]);
		line(gear, st.menu ? 'actOn' : 'actOff', 2.5);
		circle(gx, gy, 7 * k, st.menu ? 'actOn' : 'actOff', 2.5);

		// ---------- 檔案總管 ----------
		var ex = rg.explorer;
		text('檔案總管', ex.x + 22 * f, ex.y + 26 * f, m.ui, 'fg');
		line([[ex.x + 24 * f, ex.y + 66 * f], [ex.x + 32 * f, ex.y + 74 * f], [ex.x + 40 * f, ex.y + 66 * f]], 'fg', 2);
		text(String(desc.folder || 'workspace').toUpperCase(), ex.x + 52 * f, ex.y + 70 * f, m.ui, 'fg', { bold: true, max: ex.w - 64 * f });
		var rows = M.explorerRows(desc, lay);
		Object.keys(rows).forEach(function (fn) {
			var r = rows[fn], cy = r.y + r.h / 2;
			if (fn === st.open) rect(r.x, r.y, r.w, r.h, { fill: 'sel' });
			if (/\.c$/.test(fn)) text('C', r.x + 34 * f, cy, m.ui, 'file', { bold: true });
			else line([[r.x + 34 * f, cy - 7 * f], [r.x + 52 * f, cy - 7 * f]], 'dim', 2), line([[r.x + 34 * f, cy], [r.x + 52 * f, cy]], 'dim', 2), line([[r.x + 34 * f, cy + 7 * f], [r.x + 46 * f, cy + 7 * f]], 'dim', 2);
			text(fn, r.x + 66 * f, cy, m.ui, 'fg', { max: r.w - 80 * f });
		});

		// ---------- 分頁與執行鈕 ----------
		var tabs = M.tabBoxes(desc, lay);
		Object.keys(tabs).forEach(function (fn) {
			var b = tabs[fn], on = fn === st.open, cy = b.y + b.h / 2;
			rect(b.x, b.y, b.w, b.h, { fill: on ? 'edit' : 'tabOff' });
			if (on) rect(b.x, b.y, b.w, 3 * f, { fill: 'accent' });
			text('C', b.x + 20 * f, cy, m.ui, 'file', { bold: true });
			text(fn, b.x + 52 * f, cy, m.ui, on ? 'actOn' : 'dim', { max: b.w - (on ? 100 : 62) * f });
			if (on) line([[b.x + b.w - 40 * f, cy - 8 * f], [b.x + b.w - 24 * f, cy + 8 * f]], 'fg', 2), line([[b.x + b.w - 24 * f, cy - 8 * f], [b.x + b.w - 40 * f, cy + 8 * f]], 'fg', 2);
		});
		var rb = an.run, rx = rb.x + rb.w / 2, ry = rb.y + rb.h / 2;
		if (st.panel.running) rect(rx - 13 * f, ry - 13 * f, 26 * f, 26 * f, { stroke: 'stop', rx: 2 * f, width: 3 * f });
		else line([[rx - 9 * f, ry - 13 * f], [rx + 12 * f, ry], [rx - 9 * f, ry + 13 * f], [rx - 9 * f, ry - 13 * f]], 'fg', 2.5);
		rect(W - 108 * f, ry - 13 * f, 26 * f, 26 * f, { stroke: 'fg', rx: 3 * f, width: 2 * f });
		line([[W - 95 * f, ry - 13 * f], [W - 95 * f, ry + 13 * f]], 'fg', 2);
		text('···', W - 44 * f, ry, m.ui, 'fg', { align: 'middle' });

		// ---------- 程式碼 ----------
		var src = desc.files[st.open], ed = rg.editor, hl = st.highlight;
		src.forEach(function (ln, i) {
			var b = an['L' + (i + 1)];
			if (!b.h) return;
			var cy = b.y + b.h / 2;
			if (hl && hl.file === st.open && hl.lines.indexOf(i + 1) >= 0) rect(b.x - 4 * f, b.y + 2 * f, (b.w + 8 * f) * hl.p, b.h - 4 * f, { fill: 'hl', rx: 4 * f });
			text(String(i + 1), ed.x + 66 * f, cy, m.code, 'lineNo', { mono: true, align: 'end' });
			var x = b.x, right = ed.x + ed.w - m.pad;
			tokens(ln.replace(/\t/g, '    ')).forEach(function (tk) {
				if (x >= right || /^\s+$/.test(tk[0])) { x += textW(tk[0], m.code, true); return; }
				x += text(tk[0], x, cy, m.code, tk[1], { mono: true, max: right - x });
			});
		});

		// ---------- 下方面板 ----------
		var p = rg.panel;
		rect(p.x, p.y, p.w, p.h, { fill: 'side' });
		rect(p.x, p.y, p.w, 1 * f, { fill: 'line' });
		var px = p.x + m.pad, pcy = p.y + m.ptabH / 2, on = st.panel.kind === 'terminal' ? '終端機' : '輸出';
		['問題', '輸出', '偵錯主控台', '終端機'].forEach(function (s) {
			var w = text(s, px, pcy, m.ui, s === on ? 'actOn' : 'dim');
			if (s === on) rect(px, p.y + m.ptabH - 4 * f, w, 3 * f, { fill: 'accent' });
			px += w + 44 * f;
		});
		var view = M.panelView(st, lay), maxW = p.w - 2 * m.pad - m.out;
		view.forEach(function (s, i) { text(s, p.x + m.pad, p.y + m.ptabH + 8 * f + (i + 0.5) * m.outPitch, m.out, 'fg', { mono: true, max: maxW }); });
		// 終端機才有游標（輸出面板唯讀，這正是 printf 片要講的差別）
		if (st.panel.kind === 'terminal' && Math.floor(t * 2) % 2 === 0) {
			var e = an['panel:end'];
			rect(e.x, e.y + 6 * f, m.out * 0.55, e.h - 12 * f, { fill: 'fg' });
		}

		// ---------- 狀態列 ----------
		// 細節：仿真版才畫，手帳的鉛筆版縮小後讀不到，略過
		text('Ln 1, Col 1    空格: 4    UTF-8    CRLF    C    Win32', W - 24 * f, rg.status.y + rg.status.h / 2, 16 * f, 'actOn', { align: 'end', detail: true });

		// ---------- 選單與頁面（疊在最上面）：被蓋住的字和線不畫，否則量測閘會當成互疊 ----------
		var cover = st.page ? M.pageParts(lay).box : st.menu ? M.menuBox(desc, lay, st.menu) : null;
		if (cover) out = out.filter(function (o) {
			if (o.op === 'rect') return true;
			var b = o.op === 'text' ? { x: o.x - (o.align === 'end' ? o.w : o.align === 'middle' ? o.w / 2 : 0), y: o.y - o.size / 2, w: o.w, h: o.size } : bbox(o.pts);
			return b.x + b.w <= cover.x || b.x >= cover.x + cover.w || b.y + b.h <= cover.y || b.y >= cover.y + cover.h;
		});
		if (st.menu) {
			alpha = st.fade;
			var mb = M.menuBox(desc, lay, st.menu);
			rect(mb.x, mb.y, mb.w, mb.h, { fill: 'menu', stroke: 'menuLine', rx: 6 * f });
			M.presetItems(desc, st.menu).forEach(function (it) {
				var b = an[it.id], cy = b.y + b.h / 2;
				text(it.text, b.x + 20 * f, cy, m.ui, 'fg', { max: b.w * 0.6 });
				if (it.key) text(it.key, b.x + b.w - 12 * f, cy, 20 * f, 'dim', { align: 'end' });
			});
			alpha = 1;
		}
		if (st.page) {
			alpha = st.fade;
			var parts = M.pageParts(lay), pb = parts.box, hd = parts.head, se = parts.search, preset = desc._presets[st.page];
			rect(pb.x, pb.y, pb.w, pb.h, { fill: 'win', stroke: 'menuLine', rx: 8 * f });
			rect(hd.x, hd.y, hd.w, hd.h, { fill: 'winTitle' });
			text(st.page === 'settings' ? '設定' : '延伸模組', hd.x + 28 * f, hd.y + hd.h / 2, m.ui, 'fg', { bold: true });
			line([[hd.x + hd.w - 40 * f, hd.y + 17 * f], [hd.x + hd.w - 24 * f, hd.y + 33 * f]], 'fg', 2);
			line([[hd.x + hd.w - 24 * f, hd.y + 17 * f], [hd.x + hd.w - 40 * f, hd.y + 33 * f]], 'fg', 2);
			rect(se.x, se.y, se.w, se.h, { fill: 'input', stroke: 'inputLine', rx: 4 * f });
			text(preset.search || '', se.x + 12 * f, se.y + se.h / 2, 20 * f, 'fg', { max: se.w * 0.6 });
			if (preset.found) text(preset.found, se.x + se.w - 12 * f, se.y + se.h / 2, 20 * f, 'dim', { align: 'end' });
			if (st.page === 'settings') {
				text('使用者', se.x, se.y + se.h + 32 * f, 20 * f, 'link');
				text('工作區', se.x + 90 * f, se.y + se.h + 32 * f, 20 * f, 'dim');
			}
			M.presetItems(desc, st.page).forEach(function (it) {
				var b = an[it.id], right = b.x + b.w;
				if (st.page === 'settings') {
					var w = text(it.group + ': ', b.x + 20 * f, b.y + 24 * f, 20 * f, 'link', { bold: true, max: b.w * 0.5 });
					text(it.title, b.x + 20 * f + w, b.y + 24 * f, 20 * f, 'fg', { bold: true, max: right - b.x - 32 * f - w });
					var dx = b.x + 20 * f;
					if (typeof it.check === 'boolean') {
						rect(dx, b.y + 46 * f, 22 * f, 22 * f, { fill: 'input', stroke: 'inputLine', rx: 3 * f });
						if (st.checks[it.id]) line([[dx + 5 * f, b.y + 57 * f], [dx + 10 * f, b.y + 63 * f], [dx + 20 * f, b.y + 50 * f]], 'fg', 2.5);
						dx += 36 * f;
						text(it.desc, dx, b.y + 57 * f, 20 * f, 'link', { max: right - dx - 20 * f });
					} else {
						text(it.desc, dx, b.y + 57 * f, 20 * f, 'fg', { max: right - dx - 20 * f });
						rect(dx, b.y + 74 * f, Math.min(300 * f, b.w - 32 * f), 28 * f, { fill: 'input', stroke: 'inputLine', rx: 3 * f });
						text(it.select || '', dx + 10 * f, b.y + 88 * f, 20 * f, 'fg');
					}
				} else {
					rect(b.x, b.y, 64 * f, 64 * f, { fill: 'act', rx: 6 * f });
					var nx = b.x + 84 * f;
					var nw = text(it.name, nx, b.y + 20 * f, 20 * f, 'fg', { bold: true, max: b.w * 0.5 });
					if (it.installed) text('已安裝', nx + nw + 20 * f, b.y + 20 * f, 20 * f, 'dim');
					text(it.desc, nx, b.y + 44 * f, 20 * f, 'dim', { max: right - nx - 20 * f });
					text(it.author, nx, b.y + 72 * f, 20 * f, 'fg', { max: right - nx - 20 * f });
				}
			});
			alpha = 1;
		}
		return out;
	}

	var X = { ops: ops, tokens: tokens, fit: fit };
	if (typeof module !== 'undefined') module.exports = X; else g.VSCodePaint = X;
})(this);
