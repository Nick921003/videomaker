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
		for (const ev of TL.camera) {
			let target = L.defaultView(ev.scene);
			if (ev.kind === 'focus') {
				const r = anchorAt(ev.target, ev.t + Math.max(ev.dur, MOVE));
				if (r) target = L.focusView(r, ev.scene);
			}
			const start = cams.length ? cameraEval(cams.length - 1, ev.t) : target;
			cams.push({t: ev.t, dur: ev.dur, kind: ev.kind, start, target});
		}
		marks = TL.actions.filter(a => ['circle', 'underline', 'arrow'].includes(a.act)).map(a => ({...a, tEnd: nextEnter(a.scene)}));
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
	function drawMarks(t, world) {
		api.setOwner('mark');
		const accent = api.color('text.accent');
		for (const m of marks) {
			if (t < m.t0) continue;
			const a = world.alpha(m.obj) * (1 - phase(t, m.tEnd, m.tEnd + MARK_FADE));
			if (a < .004) continue;
			const r = world.anchor(m.target);
			if (!r) continue;
			const p = phase(t, m.t0, m.t1);
			ctx.save(); ctx.globalAlpha *= a;
			if (m.act === 'circle') api.ellipse(r.x + r.w / 2, r.y + r.h / 2, r.w / 2 + 22, r.h / 2 + 18, p, {seed: Board.seed(m.target)});
			else if (m.act === 'underline') api.ink([[r.x - 4, r.y + r.h + 10], [r.x + r.w + 4, r.y + r.h + 6]], p, {color: accent, width: 5, seed: Board.seed(m.target)});
			else if (m.act === 'arrow') {
				const b = world.anchor(m.args.to);
				if (b) {
					const ca = {x: r.x + r.w / 2, y: r.y + r.h / 2}, cb = {x: b.x + b.w / 2, y: b.y + b.h / 2};
					const s = edgePoint(r, cb, 16), e = edgePoint(b, ca, 16);
					const ang = Math.atan2(e.y - s.y, e.x - s.x), head = 22;
					api.ink([[s.x, s.y], [e.x, e.y]], p, {color: accent, width: 4, seed: 7});
					if (p >= .98) api.ink([[e.x - head * Math.cos(ang - .45), e.y - head * Math.sin(ang - .45)], [e.x, e.y], [e.x - head * Math.cos(ang + .45), e.y - head * Math.sin(ang + .45)]], 1, {color: accent, width: 4, seed: 8});
					if (m.args.label) api.text(m.args.label, (s.x + e.x) / 2, (s.y + e.y) / 2 - 30, {size: 30, color: accent, align: 'center', role: 'overlay', alpha: phase(t, m.t1 - .2, m.t1 + .2)});
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
		drawMarks(t, world);
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
