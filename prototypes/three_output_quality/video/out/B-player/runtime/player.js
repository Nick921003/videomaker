'use strict';
// 載入時量字、排版、預算鏡頭；之後 render(t) 只查表與插值，不依賴上一格。
(() => {
	const {W, H, VIEW, clamp, mix, ease, phase} = Board;
	const L = Board.layout;
	const D = window.BOARD_DATA, TL = D.timeline;
	const canvas = document.getElementById('board'), ctx = canvas.getContext('2d');
	const api = Board.makeApi(ctx, D.theme);
	const MOVE = .7, FADE = .4, MARK_FADE = .4;
	const objects = TL.objects, ids = Object.keys(objects);
	const errors = [];
	window.addEventListener('error', e => errors.push(String(e.message)));

	const anchorArgs = act => {
		const g = D.catalog.generic_actions[act.act];
		if (g) return g.anchor_args || [];
		const t = D.catalog.types[objects[act.obj].type];
		return (t.actions[act.act] || {}).anchor_args || [];
	};
	const split = target => { const i = target.indexOf(':'); return i < 0 ? [target, ''] : [target.slice(0, i), target.slice(i + 1)]; };
	const acts = Object.fromEntries(ids.map(id => [id, []]));
	for (const a of TL.actions) {
		if (!a.obj) continue;
		const refs = new Set([a.obj, ...anchorArgs(a).filter(k => a.args[k]).map(k => split(a.args[k])[0])]);
		for (const id of refs) acts[id].push(a);
	}
	const comp = id => {
		const c = Board.components[objects[id].type];
		if (!c) throw new Error(`沒有註冊元件 ${objects[id].type}`);
		return c;
	};
	const sceneEnter = TL.scenes.map(s => s.t_enter);
	const nextEnter = si => si + 1 < sceneEnter.length ? sceneEnter[si + 1] : Infinity;
	api.setSceneEnds(sceneEnter.map((_, si) => nextEnter(si)));

	let sizes, plan, cams, marks;

	function prepare() {
		sizes = Object.fromEntries(ids.map(id => [id, comp(id).measure(objects[id], api, acts[id])]));
		plan = [];
		let carried = {};
		TL.epochs.forEach((ep, k) => {
			const {scale, rects} = L.solve(ep.tree, sizes, ep.scene);
			const from = {};
			if (k > 0) for (const id of ids) { const p = placementIn(k - 1, id, ep.t); if (p) from[id] = p; }
			// 不在本時段版面裡但仍可見的物件，留在上次的位置（紙上的歷史）
			const to = {...carried, ...rects};
			carried = to;
			plan.push({t: ep.t, scene: ep.scene, scale, from, to, members: Object.keys(rects)});
		});
		cams = [];
		const pushCam = (ev, rect) => {
			let target = L.defaultView(ev.scene);
			if (ev.kind === 'focus') {
				rect = rect || anchorAt(ev.target, ev.t + Math.max(ev.dur, MOVE));
				if (!rect) {
					// 目標還沒出現（例：focus 寫在 show 之前）：等它在本場第一次出現再推近，不要退回全景
					const on = (TL.visibility[split(ev.target)[0]] || []).map(v => v[0]).find(t0 => t0 >= ev.t - 1e-6 && t0 < nextEnter(ev.scene));
					if (on != null) rect = anchorAt(ev.target, on + MOVE + .05);
				}
				if (rect) target = L.focusView(rect, ev.scene);
			}
			const start = cams.length ? cameraEval(cams.length - 1, ev.t) : target;
			cams.push({t: ev.t, dur: ev.dur, kind: ev.kind, scene: ev.scene, start, target, rect});
		};
		// 鏡頭跟著動作走：推近之後，下一個動作若發生在畫面外（例如推近「新增」鈕後在左邊清單打字），
		// 自動移過去；兩處框得下就一起框住。分鏡漏寫 focus 也不會讓學生看不到正在發生的事
		const follow = p => {
			const c = cams[cams.length - 1];
			if (!c || c.kind !== 'focus' || c.scene !== p.scene || !c.rect) return;
			const r = anchorAt(p.target, p.t + .05);
			if (!r) return;
			const v = c.target, hw = VIEW.w / 2 / v.z, hh = VIEW.h / 2 / v.z;
			if (r.x >= v.cx - hw && r.x + r.w <= v.cx + hw && r.y >= v.cy - hh && r.y + r.h <= v.cy + hh) return;
			const x = Math.min(c.rect.x, r.x), y = Math.min(c.rect.y, r.y);
			const both = {x, y, w: Math.max(c.rect.x + c.rect.w, r.x + r.w) - x, h: Math.max(c.rect.y + c.rect.h, r.y + r.h) - y};
			// 一起框住要能放大到 1.2 倍以上才值得；否則等於拉回全景、字又變小，改成只框新目標
			const zBoth = Math.min(VIEW.w * .55 / both.w, VIEW.h * .55 / both.h);
			pushCam({t: Math.max(p.t - .3, c.t), dur: MOVE, kind: 'focus', target: p.target, scene: p.scene}, zBoth >= 1.2 ? both : r);
		};
		const skip = new Set(['focus', 'wide', 'show', 'hide']);
		const pending = [];
		for (const a of TL.actions) {
			if (skip.has(a.act) || !a.obj) continue;
			const own = a.target && !D.catalog.types[objects[a.obj].type].floating ? [a.target] : [];
			for (const g of own.concat(anchorArgs(a).map(k => a.args[k]).filter(v => typeof v === 'string')))
				pending.push({t: a.t0, target: g, scene: a.scene});
		}
		pending.sort((p, q) => p.t - q.t);
		let pi = 0;
		for (const ev of TL.camera) {
			while (pi < pending.length && pending[pi].t < ev.t) follow(pending[pi++]);
			pushCam(ev);
		}
		while (pi < pending.length) follow(pending[pi++]);
		// 同一物件同一場只留最新的圈：下一個圈出現時舊的淡出（逐列圈清單時像指標往下走，不會疊成一串）
		const circles = TL.actions.map((a, i) => ({a, i})).filter(({a}) => a.act === 'circle').sort((p, q) => p.a.t0 - q.a.t0 || p.i - q.i);
		marks = TL.actions.filter(a => ['circle', 'underline', 'arrow'].includes(a.act)).map(a => {
			let tEnd = nextEnter(a.scene);
			if (a.act === 'circle') {
				// 依（開始時間, 動作順序）找同物件同場的下一個圈；同時開始的也只留最後一個
				const k = circles.findIndex(c => c.a === a);
				const next = circles.slice(k + 1).find(c => c.a.obj === a.obj && c.a.scene === a.scene);
				if (next) tEnd = Math.min(tEnd, next.a.t0);
			}
			return {...a, tEnd};
		});
	}

	function epochIndex(t) { let k = 0; while (k + 1 < plan.length && plan[k + 1].t <= t) k++; return k; }
	function placementIn(k, id, t) {
		const e = plan[k], to = e.to[id];
		if (!to) return null;
		const from = e.from[id];
		if (!from) return to;
		const p = ease((t - e.t) / MOVE);
		if (p >= 1) return to;
		return {x: mix(from.x, to.x, p), y: mix(from.y, to.y, p), w: mix(from.w, to.w, p), h: mix(from.h, to.h, p), s: mix(from.s, to.s, p)};
	}
	const placementAt = (id, t) => placementIn(epochIndex(t), id, t);
	function alphaAt(id, t) {
		let a = 0;
		for (const [on, off] of TL.visibility[id] || []) {
			const v = phase(t, on, on + FADE) * (off == null ? 1 : 1 - phase(t, off - FADE, off));
			a = Math.max(a, v);
		}
		return a;
	}
	function cameraEval(k, t) { const c = cams[k]; return L.mixView(c.start, c.target, ease((t - c.t) / c.dur)); }
	function cameraAt(t) {
		let k = 0;
		while (k + 1 < cams.length && cams[k + 1].t <= t) k++;
		return {view: cameraEval(k, t), kind: cams[k].kind, settled: t >= cams[k].t + cams[k].dur};
	}
	function anchorAt(target, t, states) {
		if (typeof target !== 'string' || !target) return null;
		const [id, name] = split(target);
		const pl = placementAt(id, t);
		if (!pl) return null;
		const c = comp(id), o = objects[id];
		let r = {x: 0, y: 0, w: sizes[id].w, h: sizes[id].h};
		if (name) {
			const st = states && id in states ? states[id] : c.state(o, acts[id], t, api);
			r = c.anchors(o, st, api)[name];
			if (!r) return null;
		}
		return {x: pl.x + r.x * pl.s, y: pl.y + r.y * pl.s, w: r.w * pl.s, h: r.h * pl.s};
	}

	// ── 繪製 ──

	function drawPaper(t, v) {
		const hw = VIEW.w / 2 / v.z, hh = VIEW.h / 2 / v.z;
		const x0 = v.cx - hw, x1 = v.cx + hw, y0 = v.cy - hh, y1 = v.cy + hh;
		ctx.save(); ctx.strokeStyle = api.color('canvas.grid');
		for (const [step, alpha, width] of [[40, .23, .65], [200, .5, 1]]) {
			ctx.globalAlpha = alpha; ctx.lineWidth = width; ctx.beginPath();
			for (let x = Math.floor(x0 / step) * step; x <= x1; x += step) { ctx.moveTo(x, y0); ctx.lineTo(x, y1); }
			for (let y = Math.floor(y0 / step) * step; y <= y1; y += step) { ctx.moveTo(x0, y); ctx.lineTo(x1, y); }
			ctx.stroke();
		}
		ctx.restore();
		// 左緣鉛筆進度線：整張紙只有一條，隨片長往下畫
		const top = L.region(0).y + 40, bottom = L.region(TL.scenes.length - 1).y + VIEW.h - 40;
		const pts = [];
		for (let i = 0; i <= 24; i++) pts.push([110 + Math.sin(i * 1.7) * 6, mix(top, bottom, i / 24)]);
		api.setOwner('paper');
		api.ink(pts, t / TL.duration, {color: api.color('canvas.margin'), width: 2, seed: 61});
	}
	function drawLabels(t) {
		api.setOwner('label');
		TL.scenes.forEach((s, i) => {
			if (!s.label || t < s.t_enter) return;
			const r = L.region(i), x = L.PAD.l, y = r.y + 62;
			const w = api.text(s.label, x, y, {size: 34, color: api.color('text.muted'), role: 'label'});
			api.ink([[x, y + 30], [x + w, y + 30]], phase(t, s.t_enter, s.t_enter + .9), {color: api.color('text.accent'), width: 3, seed: 100 + i});
		});
	}
	function edgePoint(r, toward, pad) {
		const cx = r.x + r.w / 2, cy = r.y + r.h / 2, dx = toward.x - cx, dy = toward.y - cy;
		const k = Math.min(Math.abs((r.w / 2 + pad) / (dx || 1e-9)), Math.abs((r.h / 2 + pad) / (dy || 1e-9)));
		return {x: cx + dx * k, y: cy + dy * k};
	}

	// ── 標記的避讓幾何（世界座標；只依賴版面與 state，同一時段內穩定，不會畫到一半跳位） ──

	const center = r => ({x: r.x + r.w / 2, y: r.y + r.h / 2});
	const overlaps = (a, b, pad = 0) => a.x - pad < b.x + b.w && b.x - pad < a.x + a.w && a.y - pad < b.y + b.h && b.y - pad < a.y + a.h;
	const contains = (outer, r) => r.x >= outer.x && r.y >= outer.y && r.x + r.w <= outer.x + outer.w && r.y + r.h <= outer.y + outer.h;
	// 標記能用的紙面：左緣進度線右側、紙上小標下方
	function markBounds(si) { const r = L.region(si); return {x: r.x + 130, y: r.y + 96, w: r.w - 150, h: r.h - 108}; }
	function memberRects(t) {
		const out = [];
		for (const id of plan[epochIndex(t)].members) {
			const pl = placementAt(id, t);
			if (pl) out.push({x: pl.x, y: pl.y, w: pl.w, h: pl.h, id});
		}
		return out;
	}
	// 這一格畫出來的字與框（轉回世界座標）：端點物件內部要閃的東西以實際畫面為準
	function drawnBoxes() {
		const inv = ctx.getTransform().inverse();
		return api.boxes().filter(b => objects[b.owner] && ['text', 'label', 'panel'].includes(b.role)).map(b => {
			const p = new DOMPoint(b.x, b.y).matrixTransform(inv), q = new DOMPoint(b.x + b.w, b.y + b.h).matrixTransform(inv);
			return {x: p.x, y: p.y, w: q.x - p.x, h: q.y - p.y, id: b.owner, role: b.role};
		});
	}
	// 屬於端點本身的框：中心落在端點裡，或把端點整個包住（外框）。相鄰列只是貼邊，不算
	const ownedBy = (b, e) => { const c = center(b); return (c.x >= e.x - 2 && c.x <= e.x + e.w + 2 && c.y >= e.y - 2 && c.y <= e.y + e.h + 2) || contains(b, e); };
	// 要閃開的東西：其他物件的整框，加上端點所屬物件裡不屬於端點的錨點與畫面上的字、框（例：同一張清單的其他列）
	function obstaclesFor(ends, t, states, drawn) {
		const endIds = new Set(ends.map(e => e.id));
		const out = [];
		for (const m of memberRects(t)) {
			if (!endIds.has(m.id)) { out.push(m); continue; }
			const pl = placementAt(m.id, t);
			const local = Object.values(comp(m.id).anchors(objects[m.id], states[m.id], api)).map(r => ({x: pl.x + r.x * pl.s, y: pl.y + r.y * pl.s, w: r.w * pl.s, h: r.h * pl.s, id: m.id}));
			for (const w of local.concat(drawn.filter(b => b.id === m.id)))
				if (!ends.some(e => ownedBy(w, e.rect))) out.push(w);
		}
		return out;
	}
	function samples(pts, step = 5) {
		const out = [];
		for (let i = 1; i < pts.length; i++) {
			const [x0, y0] = pts[i - 1], [x1, y1] = pts[i], n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / step));
			for (let j = 0; j <= n; j++) out.push([mix(x0, x1, j / n), mix(y0, y1, j / n)]);
		}
		return out;
	}
	const hitBox = (pts, r, pad = 6) => samples(pts).some(([x, y]) => x > r.x - pad && x < r.x + r.w + pad && y > r.y - pad && y < r.y + r.h + pad);
	const gapBetween = (a, b) => Math.max(a.x - b.x - b.w, b.x - a.x - a.w, a.y - b.y - b.h, b.y - a.y - a.h, 0);
	function cost(pts, obs, bounds, ends = []) {
		// 頭尾 18px 是端點的出入口：只有緊貼端點的鄰居（例如清單相鄰列）在這段可以碰，其他障礙物整條都要閃
		const [sx, sy] = pts[0], [ex, ey] = pts[pts.length - 1], all = samples(pts);
		const body = all.filter(([x, y]) => Math.hypot(x - sx, y - sy) > 18 && Math.hypot(x - ex, y - ey) > 18);
		let n = obs.filter(o => (ends.some(e => gapBetween(o, e) < 20) ? body : all).some(([x, y]) => x > o.x - 6 && x < o.x + o.w + 6 && y > o.y - 6 && y < o.y + o.h + 6)).length;
		if (!samples(pts, 20).every(([x, y]) => x >= bounds.x && x <= bounds.x + bounds.w && y >= bounds.y && y <= bounds.y + bounds.h)) n += 1;
		return n;
	}
	// 轉角改成小圓弧，像手畫的折線
	function bend(pts, rad = 22) {
		const out = [pts[0]];
		for (let i = 1; i < pts.length - 1; i++) {
			const [px, py] = pts[i - 1], [x, y] = pts[i], [nx, ny] = pts[i + 1];
			const d1 = Math.hypot(x - px, y - py) || 1, d2 = Math.hypot(nx - x, ny - y) || 1, k = Math.min(rad, d1 / 2, d2 / 2);
			const a = [x + (px - x) / d1 * k, y + (py - y) / d1 * k], b = [x + (nx - x) / d2 * k, y + (ny - y) / d2 * k];
			for (let j = 0; j <= 4; j++) {
				const q = j / 4;
				out.push([mix(mix(a[0], x, q), mix(x, b[0], q), q), mix(mix(a[1], y, q), mix(y, b[1], q), q)]);
			}
		}
		out.push(pts[pts.length - 1]);
		return out;
	}
	// 繞道：從擋路物件的外側繞過去；hull 含端點物件整框，從框內的錨點出發時會先橫（或直）著走出框外
	function detour(ra, rb, side, obs) {
		const ca = center(ra), cb = center(rb), GAP = 40, OUT = 12;
		if (side === 'right' || side === 'left') {
			const lo = Math.min(ca.y, cb.y), hi = Math.max(ca.y, cb.y), span = o => o.y < hi && o.y + o.h > lo;
			if (side === 'right') {
				const X = Math.max(ra.x + ra.w, rb.x + rb.w, ...obs.filter(span).map(o => o.x + o.w)) + GAP;
				return bend([[ra.x + ra.w + OUT, ca.y], [X, ca.y], [X, cb.y], [rb.x + rb.w + OUT, cb.y]]);
			}
			const X = Math.min(ra.x, rb.x, ...obs.filter(span).map(o => o.x)) - GAP;
			return bend([[ra.x - OUT, ca.y], [X, ca.y], [X, cb.y], [rb.x - OUT, cb.y]]);
		}
		const lo = Math.min(ca.x, cb.x), hi = Math.max(ca.x, cb.x), span = o => o.x < hi && o.x + o.w > lo;
		if (side === 'up') {
			const Y = Math.min(ra.y, rb.y, ...obs.filter(span).map(o => o.y)) - GAP;
			return bend([[ca.x, ra.y - OUT], [ca.x, Y], [cb.x, Y], [cb.x, rb.y - OUT]]);
		}
		const Y = Math.max(ra.y + ra.h, rb.y + rb.h, ...obs.filter(span).map(o => o.y + o.h)) + GAP;
		return bend([[ca.x, ra.y + ra.h + OUT], [ca.x, Y], [cb.x, Y], [cb.x, rb.y + rb.h + OUT]]);
	}
	// 折線：兩個物件左右（或上下）分開時，轉折那一段走兩者中間的空隙，像流程圖的連接線
	function elbow(ra, rb, A, B) {
		const ca = center(ra), cb = center(rb), OUT = 12;
		if (B.x >= A.x + A.w || A.x >= B.x + B.w) {
			const right = B.x >= A.x + A.w, xm = right ? (A.x + A.w + B.x) / 2 : (B.x + B.w + A.x) / 2;
			return bend([[right ? ra.x + ra.w + OUT : ra.x - OUT, ca.y], [xm, ca.y], [xm, cb.y], [right ? rb.x - OUT : rb.x + rb.w + OUT, cb.y]]);
		}
		if (B.y >= A.y + A.h || A.y >= B.y + B.h) {
			const down = B.y >= A.y + A.h, ym = down ? (A.y + A.h + B.y) / 2 : (B.y + B.h + A.y) / 2;
			return bend([[ca.x, down ? ra.y + ra.h + OUT : ra.y - OUT], [ca.x, ym], [cb.x, ym], [cb.x, down ? rb.y - OUT : rb.y + rb.h + OUT]]);
		}
		return null;
	}
	function routeArrow(ra, rb, obs, hull, bounds, A, B) {
		const ca = center(ra), cb = center(rb), s = edgePoint(ra, cb, 16), e = edgePoint(rb, ca, 16);
		let best = {pts: [[s.x, s.y], [e.x, e.y]]};
		best.n = cost(best.pts, obs, bounds, [ra, rb]);
		if (!best.n) return best.pts;
		// 四個方向都試，取擋最少的；同分時直向箭頭先走右側、橫向先走上方
		const sides = Math.abs(cb.y - ca.y) >= Math.abs(cb.x - ca.x) ? ['right', 'left', 'up', 'down'] : ['up', 'down', 'right', 'left'];
		const tries = [A && B && elbow(ra, rb, A, B), ...sides.map(side => detour(ra, rb, side, hull))].filter(Boolean);
		for (const pts of tries) {
			const n = cost(pts, obs, bounds, [ra, rb]);
			if (n < best.n) best = {pts, n};
			if (!n) break;
		}
		return best.pts;
	}
	// 標籤沿路徑找空位：先中段、再往兩端；每個點試路徑兩側，閃開物件、別的標籤與自己的線
	function placeLabel(text, pts, obs, taken, bounds) {
		const o = {size: 30}, w = api.measure(text, o).w, h = o.size * 1.24;
		const segs = [];
		let total = 0;
		for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); segs.push(d); total += d; }
		for (const f of [.5, .38, .62, .26, .74]) {
			let left = total * f, i = 0;
			while (i < segs.length - 1 && left > segs[i]) left -= segs[i++];
			const [x0, y0] = pts[i], [x1, y1] = pts[i + 1], d = segs[i] || 1;
			const x = mix(x0, x1, left / d), y = mix(y0, y1, left / d), dx = (x1 - x0) / d, dy = (y1 - y0) / d;
			for (const sgn of [-1, 1]) {
				const nx = -dy * sgn, ny = dx * sgn, off = Math.abs(nx) * (w / 2 + 16) + Math.abs(ny) * (h / 2 + 10);
				const box = {x: x + nx * off - w / 2, y: y + ny * off - h / 2, w, h};
				if (contains(bounds, box) && !obs.some(r => overlaps(box, r, 4)) && !taken.some(r => overlaps(box, r, 4)) && !hitBox(pts, box, 4)) return box;
			}
		}
		// 找不到空位就不畫標籤（旁白會講），不硬疊在字上
		return null;
	}
	function ellipsePts(cx, cy, rx, ry) {
		const pts = [];
		for (let i = 0; i <= 40; i++) { const q = i / 40 * Math.PI * 2 - Math.PI / 2; pts.push([cx + Math.cos(q) * rx, cy + Math.sin(q) * ry]); }
		return pts;
	}
	function capsulePts(x, y, w, h, rad) {
		const pts = [[x + w / 2, y]];
		const arc = (cx, cy, a0) => { for (let i = 0; i <= 6; i++) { const q = a0 + i / 6 * Math.PI / 2; pts.push([cx + Math.cos(q) * rad, cy + Math.sin(q) * rad]); } };
		arc(x + w - rad, y + rad, -Math.PI / 2); arc(x + w - rad, y + h - rad, 0); arc(x + rad, y + h - rad, Math.PI / 2); arc(x + rad, y + rad, Math.PI);
		pts.push([x + w / 2, y]);
		return pts;
	}
	// 圈只往外撐到鄰居前，太擠時可往內縮到目標自己的字邊；扁長的目標（清單列）改用膠囊形，橢圓會切過自己的框角
	function ringPts(r, obs, content) {
		const room = {l: Infinity, r: Infinity, t: Infinity, b: Infinity};
		for (const o of obs) {
			if (o.y < r.y + r.h && o.y + o.h > r.y) {
				if (o.x + o.w <= r.x + 1) room.l = Math.min(room.l, r.x - o.x - o.w);
				if (o.x >= r.x + r.w - 1) room.r = Math.min(room.r, o.x - r.x - r.w);
			}
			if (o.x < r.x + r.w && o.x + o.w > r.x) {
				if (o.y + o.h <= r.y + 1) room.t = Math.min(room.t, r.y - o.y - o.h);
				if (o.y >= r.y + r.h - 1) room.b = Math.min(room.b, o.y - r.y - r.h);
			}
		}
		const inX = Math.max(0, Math.min(content.x - r.x, r.x + r.w - content.x - content.w)), inY = Math.max(0, Math.min(content.y - r.y, r.y + r.h - content.y - content.h));
		// 圈離鄰居至少留空隙的四成（筆畫有粗細，太貼看起來像黏在鄰居的框上）
		const fit = gap => Number.isFinite(gap) ? gap - Math.max(5, gap * .4) : Infinity;
		const px = clamp(fit(Math.min(room.l, room.r)), 2 - inX, 22), py = clamp(fit(Math.min(room.t, room.b)), 2 - inY, 18);
		if (r.w > r.h * 2.6) return capsulePts(r.x - px, r.y - py, r.w + px * 2, r.h + py * 2, Math.min(r.h / 2 + py, 36));
		return ellipsePts(r.x + r.w / 2, r.y + r.h / 2, r.w / 2 + px, r.h / 2 + py);
	}
	function drawMarks(t, world, states) {
		api.setOwner('mark');
		const accent = api.color('text.accent');
		const taken = [], drawn = drawnBoxes();
		for (const m of marks) {
			if (t < m.t0) continue;
			const a = world.alpha(m.obj) * (1 - phase(t, m.tEnd, m.tEnd + MARK_FADE));
			if (a < .004) continue;
			const r = world.anchor(m.target);
			if (!r) continue;
			const p = phase(t, m.t0, m.t1), done = p >= .98;
			const bounds = markBounds(m.scene);
			ctx.save(); ctx.globalAlpha *= a;
			// 目標裡實際畫出來的字（錨點常比字大，例如整行寬的程式碼列）
			const own = drawn.filter(b => b.id === m.obj && b.role === 'text' && ownedBy(b, r) && !contains(b, r));
			const content = own.length ? own.reduce((u, b) => { const x = Math.min(u.x, b.x), y = Math.min(u.y, b.y); return {x, y, w: Math.max(u.x + u.w, b.x + b.w) - x, h: Math.max(u.y + u.h, b.y + b.h) - y}; }) : r;
			if (m.act === 'circle') {
				const pts = ringPts(r, obstaclesFor([{id: m.obj, rect: r}], t, states, drawn), content);
				api.ink(pts, p, {color: accent, width: 3.4, seed: Board.seed(m.target)});
				if (done) api.recordPath(pts, 'stroke', {kind: '圈', target: m.target, skip: [r]});
			} else if (m.act === 'underline') {
				// 畫在字底下、下方鄰居（例如下一行程式碼）之前；行距很緊時貼著字底
				const obs = obstaclesFor([{id: m.obj, rect: r}], t, states, drawn);
				const below = Math.min(Infinity, ...obs.filter(o => o.x < content.x + content.w && o.x + o.w > content.x && o.y >= content.y + content.h - 1).map(o => o.y));
				const y = Math.max(content.y + content.h + 2, Math.min(r.y + r.h + 8, below - 5));
				const pts = [[content.x - 4, y + 2], [content.x + content.w + 4, y - 2]];
				api.ink(pts, p, {color: accent, width: 5, seed: Board.seed(m.target)});
				if (done) api.recordPath(pts, 'stroke', {kind: '底線', target: m.target, skip: [r]});
			} else if (m.act === 'arrow') {
				const b = world.anchor(m.args.to);
				if (b) {
					const ends = [{id: m.obj, rect: r}, {id: split(m.args.to)[0], rect: b}];
					const obs = obstaclesFor(ends, t, states, drawn);
					const own = memberRects(t).filter(o => ends.some(e => e.id === o.id));
					const A = own.find(o => o.id === ends[0].id), B = ends[0].id === ends[1].id ? null : own.find(o => o.id === ends[1].id);
					const pts = routeArrow(r, b, obs, obs.concat(own), bounds, A, B);
					const [ex, ey] = pts[pts.length - 1], [qx, qy] = pts[pts.length - 2];
					const ang = Math.atan2(ey - qy, ex - qx), head = 22;
					api.ink(pts, p, {color: accent, width: 4, seed: 7});
					const tip = [[ex - head * Math.cos(ang - .45), ey - head * Math.sin(ang - .45)], [ex, ey], [ex - head * Math.cos(ang + .45), ey - head * Math.sin(ang + .45)]];
					if (p >= .98) api.ink(tip, 1, {color: accent, width: 4, seed: 8});
					if (done) {
						api.recordPath(pts, 'stroke', {kind: '箭頭', target: `${m.target}→${m.args.to}`, skip: [r, b]});
						api.recordPath(tip, 'stroke', {kind: '箭頭尖端', target: `${m.target}→${m.args.to}`, skip: [r, b]});
					}
					const box = m.args.label ? placeLabel(m.args.label, pts, memberRects(t), taken, bounds) : null;
					if (box) {
						taken.push(box);
						api.text(m.args.label, box.x + box.w / 2, box.y + box.h / 2, {size: 30, color: accent, align: 'center', role: 'mark-label', alpha: phase(t, m.t1 - .2, m.t1 + .2)});
					}
				}
			}
			ctx.restore();
		}
	}
	function wrap(str, width, o) {
		const rows = [];
		let line = '';
		for (const ch of str) {
			if (line && api.measure(line + ch, o).w > width) { rows.push(line); line = ch; } else line += ch;
		}
		if (line) rows.push(line);
		return rows;
	}
	function drawChrome(t) {
		ctx.setTransform(1, 0, 0, 1, 0, 0);
		api.setOwner('chrome');
		let si = 0;
		while (si + 1 < TL.scenes.length && TL.scenes[si + 1].t_enter <= t) si++;
		const s = TL.scenes[si], fade = si > 0 ? phase(t, s.t_enter, s.t_enter + .35) : 1;
		if (fade < 1 && si > 0) api.text(TL.scenes[si - 1].title, 64, 50, {size: 40, weight: 500, color: api.color('text.title'), alpha: 1 - fade, role: 'header'});
		api.text(s.title, 64, 50, {size: 40, weight: 500, color: api.color('text.title'), alpha: fade, role: 'header'});
		if (TL.tag) api.text(TL.tag, W - 64, 50, {size: 28, color: api.color('text.muted'), align: 'right', role: 'header'});
		const sub = TL.subtitles.find(c => c.t0 <= t && t < c.t1) || (t >= TL.duration ? TL.subtitles[TL.subtitles.length - 1] : null);
		if (sub) {
			const o = {size: 40, color: api.color('text.body'), align: 'center', role: 'subtitle'};
			wrap(sub.text, 1560, o).forEach((row, i) => api.text(row, W / 2, VIEW.y + VIEW.h + 48 + i * 54, o));
		}
		if (TL.corner_note) api.text(TL.corner_note, 48, H - 36, {size: 22, color: api.color('text.muted'), role: 'header'});
		ctx.fillStyle = api.color('canvas.grid'); ctx.fillRect(48, H - 12, W - 96, 4);
		ctx.fillStyle = api.color('text.accent'); ctx.fillRect(48, H - 12, (W - 96) * clamp(t / TL.duration), 4);
	}

	function render(t) {
		t = clamp(Number(t) || 0, 0, TL.duration);
		api.reset(); api.setTime(t);
		ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
		ctx.fillStyle = api.color('canvas.bg'); ctx.fillRect(0, 0, W, H);
		const cam = cameraAt(t), k = epochIndex(t);
		const states = {}, alpha = {};
		for (const id of ids) { alpha[id] = alphaAt(id, t); states[id] = comp(id).state(objects[id], acts[id], t, api); }
		ctx.save(); ctx.beginPath(); ctx.rect(VIEW.x, VIEW.y, VIEW.w, VIEW.h); ctx.clip();
		L.applyView(ctx, cam.view);
		drawPaper(t, cam.view);
		drawLabels(t);
		const placed = {};
		for (const id of ids) {
			if (alpha[id] < .004 || D.catalog.types[objects[id].type].floating) continue;
			const pl = placementAt(id, t);
			if (!pl) continue;
			placed[id] = pl;
			api.setOwner(id);
			ctx.save(); ctx.globalAlpha = alpha[id]; ctx.translate(pl.x, pl.y); ctx.scale(pl.s, pl.s);
			comp(id).draw(api, objects[id], states[id], t);
			ctx.restore();
		}
		const world = {anchor: target => anchorAt(target, t, states), alpha: id => alpha[id] ?? 0, placement: id => placed[id] || null};
		const floating = id => D.catalog.types[objects[id].type].floating;
		const overlay = id => {
			api.setOwner(id);
			ctx.save(); ctx.globalAlpha = alpha[id]; comp(id).overlay(api, objects[id], states[id], t, world); ctx.restore();
		};
		for (const id of ids) if (comp(id).overlay && placed[id] && !floating(id)) overlay(id);
		drawMarks(t, world, states);
		// 浮動物件（游標）沒有版位，最後畫，永遠在最上層
		for (const id of ids) if (comp(id).overlay && floating(id) && alpha[id] >= .004) overlay(id);
		ctx.restore();
		drawChrome(t);
		return {
			t, boxes: api.boxes(), scene: plan[k].scene, scale: plan[k].scale, members: plan[k].members,
			moving: k > 0 && t < plan[k].t + MOVE, camera: {kind: cam.kind, settled: cam.settled, z: cam.view.z},
			alpha, placed, errors: errors.slice(),
		};
	}

	// ── 播放器 UI（匯出模式不啟用；UI 讀時鐘，但 render 本身不讀） ──

	function ui() {
		const audio = document.getElementById('voice'), play = document.getElementById('play');
		const seek = document.getElementById('seek'), clock = document.getElementById('clock');
		seek.max = TL.duration;
		let playing = false, clockT = 0, last = 0;
		if (D.audio) audio.src = D.audio;
		const now = () => D.audio ? audio.currentTime : clockT;
		const show = () => { const t = now(); render(t); seek.value = t; clock.textContent = `${t.toFixed(1)} / ${TL.duration.toFixed(1)} 秒`; };
		play.onclick = () => {
			playing = !playing;
			play.textContent = playing ? '暫停' : '播放';
			if (D.audio) playing ? audio.play() : audio.pause();
		};
		seek.oninput = () => { if (D.audio) audio.currentTime = Number(seek.value); else clockT = Number(seek.value); show(); };
		function tick(ms) {
			if (playing && !D.audio) { clockT = Math.min(TL.duration, clockT + (last ? (ms - last) / 1000 : 0)); if (clockT >= TL.duration) playing = false; }
			last = ms;
			if (playing) show();
			requestAnimationFrame(tick);
		}
		const hash = new URLSearchParams(location.hash.slice(1));
		if (hash.has('t')) { clockT = Number(hash.get('t')); if (D.audio) audio.currentTime = clockT; }
		show();
		requestAnimationFrame(tick);
	}

	async function boot() {
		await Promise.all(['400 40px "Noto Sans CJK TC"', '500 40px "Noto Sans CJK TC"', '700 40px "Noto Sans CJK TC"', '400 40px "Noto Sans Mono CJK TC"']
			.map(f => document.fonts.load(f).catch(() => null)));
		await document.fonts.ready;
		document.body.style.background = api.color('canvas.bg');
		prepare();
		const exportMode = new URLSearchParams(location.search).has('export');
		document.body.classList.toggle('export', exportMode);
		window.board = {
			duration: TL.duration, seek: render, types: Object.keys(Board.components),
			scales: () => plan.map(p => ({t: p.t, scene: p.scene, scale: p.scale, members: p.members})),
			anchor: (target, t) => anchorAt(target, t), errors: () => errors.slice(),
		};
		if (!exportMode) ui(); else render(0);
		window.boardReady = true;
	}
	boot().catch(e => { errors.push(String(e && e.stack || e)); window.boardReady = true; window.boardFailed = String(e && e.stack || e); });
})();
