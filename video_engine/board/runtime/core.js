'use strict';
// 共用工具與繪製 API。所有函式只依賴參數與 t：不讀時鐘、不用亂數，所以 render(t) 可任意跳轉。
const Board = (() => {
	const W = 1920, H = 1080, HEADER = 96, FOOTER = 160;
	const VIEW = {x: 0, y: HEADER, w: W, h: H - HEADER - FOOTER};
	const SANS = '"Noto Sans CJK TC","Noto Sans TC","Microsoft JhengHei",sans-serif';
	const MONO = '"Noto Sans Mono CJK TC",Consolas,monospace';
	const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
	const mix = (a, b, p) => a + (b - a) * p;
	const ease = p => { p = clamp(p); return p * p * (3 - 2 * p); };
	const expo = p => p >= 1 ? 1 : 1 - Math.pow(2, -10 * clamp(p));
	const phase = (t, a, b, fn = ease) => b <= a ? (t >= b ? 1 : 0) : fn((t - a) / (b - a));
	function seed(str) {
		let h = 2166136261;
		for (const ch of String(str)) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619); }
		return (h >>> 0) % 997;
	}
	const components = {};
	function register(type, impl) {
		for (const key of ['measure', 'state', 'draw', 'anchors'])
			if (typeof impl[key] !== 'function') throw new Error(`元件 ${type} 缺 ${key}()`);
		components[type] = impl;
	}

	function makeApi(ctx, theme) {
		let drawT = 0, owner = null, boxes = [], sceneEnds = [];
		function color(path) {
			const v = path.split('.').reduce((o, k) => o && o[k], theme);
			if (typeof v !== 'string') throw new Error(`theme 缺 ${path}`);
			return v;
		}
		function font(o = {}) { return `${o.weight || 400} ${o.size || 40}px ${o.mono ? MONO : SANS}`; }
		function measure(str, o = {}) {
			ctx.save(); ctx.font = font(o); ctx.fontKerning = 'none';
			const w = ctx.measureText(String(str)).width;
			ctx.restore();
			return {w, h: (o.size || 40) * 1.25};
		}
		// 紀錄螢幕座標框，供量測閘檢查越界與重疊
		function record(x, y, w, h, role = 'text', extra = {}) {
			const m = ctx.getTransform();
			const a = new DOMPoint(x, y).matrixTransform(m), b = new DOMPoint(x + w, y + h).matrixTransform(m);
			boxes.push({owner, role, x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(b.x - a.x), h: Math.abs(b.y - a.y), alpha: ctx.globalAlpha, ...extra});
		}
		// 紀錄標記的筆畫路徑（螢幕座標）；skip 是它本來就該碰到的框（被圈的目標、箭頭兩端），量測閘不算穿過
		function recordPath(points, role = 'stroke', extra = {}) {
			const m = ctx.getTransform(), at = (x, y) => { const q = new DOMPoint(x, y).matrixTransform(m); return [q.x, q.y]; };
			const pts = points.map(([x, y]) => at(x, y));
			const skip = (extra.skip || []).map(r => { const [x0, y0] = at(r.x, r.y), [x1, y1] = at(r.x + r.w, r.y + r.h); return {x: x0, y: y0, w: x1 - x0, h: y1 - y0}; });
			const xs = pts.map(q => q[0]), ys = pts.map(q => q[1]), x = Math.min(...xs), y = Math.min(...ys);
			boxes.push({owner, role, x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y, alpha: ctx.globalAlpha, ...extra, pts, skip});
		}
		function text(str, x, y, o = {}) {
			str = String(str);
			if (!str || ctx.globalAlpha * (o.alpha ?? 1) < .004) return 0;
			ctx.save(); ctx.globalAlpha *= o.alpha ?? 1;
			ctx.font = font(o); ctx.fontKerning = 'none'; ctx.textAlign = o.align || 'left'; ctx.textBaseline = 'middle';
			ctx.fillStyle = o.color || color('text.body'); ctx.fillText(str, x, y);
			const w = ctx.measureText(str).width, size = o.size || 40;
			const x0 = x - (o.align === 'center' ? w / 2 : o.align === 'right' ? w : 0);
			record(x0, y - size * .62, w, size * 1.24, o.role || 'text', {value: str});
			ctx.restore();
			return w;
		}
		// 手寫揭露：由左往右裁切，以 0.1 為階讓筆畫有「一段一段寫出」的感覺
		function write(str, x, y, p, o = {}) {
			p = clamp(p);
			if (p <= 0) return;
			const {w} = measure(str, o), size = o.size || 40;
			const x0 = x - (o.align === 'center' ? w / 2 : o.align === 'right' ? w : 0);
			ctx.save(); ctx.beginPath();
			ctx.rect(x0 - 6, y - size, (p >= 1 ? 1 : Math.ceil(p * 10) / 10) * (w + 12), size * 2); ctx.clip();
			text(str, x, y, o); ctx.restore();
		}
		// 鉛筆筆觸：描線中帶微小抖動，描完（p=1）固定成 seed 決定的形狀，不再晃
		function ink(points, p = 1, o = {}) {
			p = clamp(p);
			if (p <= 0 || points.length < 2) return;
			const col = o.color || color('effects.pencil'), width = o.width || 3, s = o.seed || 0;
			const dense = [];
			for (let i = 1; i < points.length; i++)
				for (let j = 0; j < 8; j++) dense.push([mix(points[i - 1][0], points[i][0], j / 8), mix(points[i - 1][1], points[i][1], j / 8)]);
			dense.push(points[points.length - 1]);
			const variant = p < 1 ? Math.floor(drawT * 12) % 3 : s % 3;
			const count = Math.max(2, Math.floor(dense.length * p));
			ctx.save(); ctx.strokeStyle = col; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
			for (let pass = 0; pass < 2; pass++) {
				ctx.lineWidth = pass ? width * .5 : width; ctx.globalAlpha *= pass ? .25 : 1;
				ctx.beginPath();
				for (let i = 0; i < count; i++) {
					const [x, y] = dense[i];
					const jx = Math.sin(s * 3.17 + i * 1.91 + variant * 2.4) * 1.1, jy = Math.cos(s * 2.13 + i * 2.17 + variant * 1.8) * .8;
					if (i) ctx.lineTo(x + jx, y + jy); else ctx.moveTo(x + jx, y + jy);
				}
				ctx.stroke();
				if (pass) ctx.globalAlpha /= .25;
			}
			ctx.restore();
		}
		function rect(x, y, w, h, p = 1, o = {}) {
			if (o.fill) { ctx.save(); ctx.fillStyle = o.fill; ctx.globalAlpha *= clamp(p * 3); ctx.fillRect(x, y, w, h); ctx.restore(); }
			ink([[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]], p, {width: 2.7, ...o});
			if (o.role !== null) record(x, y, w, h, o.role || 'panel');
		}
		function ellipse(cx, cy, rx, ry, p = 1, o = {}) {
			const pts = [];
			for (let i = 0; i <= 40; i++) { const q = i / 40 * Math.PI * 2 - Math.PI / 2; pts.push([cx + Math.cos(q) * rx, cy + Math.sin(q) * ry]); }
			ink(pts, p, {color: color('text.accent'), width: 3.4, seed: 13, ...o});
		}
		// 未知內容：淡色斜線
		function hatch(x, y, w, h, s = 0) {
			for (let j = 1; j < 5; j++) ink([[x + 6, y + j * h / 5], [x + w - 6, y + j * h / 5 - h * .07]], 1, {color: color('canvas.grid'), width: 1.4, seed: s + j});
		}
		function pointer(x, y, size, p = 1) {
			ellipse(x, y, size * .22, size * .18, p, {seed: 19});
			ink([[x - size * .07, y + size * .2], [x, y + size * .32], [x + size * .07, y + size * .2]], p, {color: color('text.accent'), width: 3.4, seed: 29});
		}
		// 字元飛行：弧線，落點前減速
		function fly(str, from, to, p, o = {}) {
			p = clamp(p);
			if (p <= 0 || p >= 1) return;
			const q = ease(p), lift = o.lift ?? 60;
			text(str, mix(from.x, to.x, q), mix(from.y, to.y, q) - Math.sin(q * Math.PI) * lift, {role: 'overlay', align: 'center', mono: true, ...o});
		}
		return {
			ctx, color, font, measure, record, recordPath, text, write, ink, rect, ellipse, hatch, pointer, fly,
			clamp, mix, ease, expo, phase, seed,
			setTime(t) { drawT = t; }, setOwner(id) { owner = id; },
			// 元件動作留下的標記只活在該動作的場景：換場時刻起淡出
			setSceneEnds(ends) { sceneEnds = ends; }, sceneEnd(i) { return sceneEnds[i] ?? Infinity; },
			reset() { boxes = []; owner = null; }, boxes() { return boxes; },
		};
	}

	return {W, H, HEADER, FOOTER, VIEW, SANS, MONO, clamp, mix, ease, expo, phase, seed, register, components, makeApi};
})();
