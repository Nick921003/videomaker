'use strict';
(() => {
	const LINE_W = 1100, TITLE_H = 44, TRAVEL = 36, PROBE_H = 82, MARK_H = 52, GAP = 20;
	const PROBE = {size: 30, mono: true}, TICK = {size: 28, mono: true};
	const LABEL = {size: 26}, MARK = {size: 28};
	const progress = (t, a, b) => b <= a ? (t >= b ? 1 : 0) : Board.clamp((t - a) / (b - a));
	const ownActions = (obj, acts) => acts.filter(a => a.obj === obj.id);
	const markAlpha = (api, a, t) => {
		const end = api.sceneEnd(a.scene);
		return 1 - Board.phase(t, end, end + .4);
	};
	const outside = (obj, value) => value < obj.min || value > obj.max;
	const overlapsTime = (a, b) => a.a.t0 < b.end && b.a.t0 < a.end;
	const textBox = (x, y, w, size) => ({x, y: y - size * .62, w, h: size * 1.24});

	function caption(obj, a, api, probe) {
		const opts = probe ? PROBE : MARK;
		const text = String(a.args.label ?? a.args.value), labelW = api.measure(text, opts).w;
		const result = probe ? a.args.result === 'pass' ? '✓' : a.args.result === 'fail' ? '✗' : '' : '';
		const resultW = result ? api.measure(result, PROBE).w + 10 : 0;
		const ellipsis = outside(obj, a.args.value), tailW = ellipsis ? api.measure('…', opts).w + 8 : 0;
		return {a, text, labelW, result, resultW, ellipsis, w: labelW + resultW + tailW, end: api.sceneEnd(a.scene) + .4};
	}

	// 整片先分配標籤位置；已消失的標記可以共用位置，播放時不重排。
	function placeLabels(items, w, rows) {
		const placed = [];
		for (let i = 0; i < items.length; i++) {
			const item = items[i];
			const occupied = placed.filter(other => overlapsTime(item, other));
			let best = null;
			for (let j = 0; j < rows; j++) {
				const row = (i + j) % rows, neighbors = occupied.filter(other => other.row === row);
				const desired = Board.clamp(item.at - item.w / 2, 8, w - item.w - 8);
				const candidates = [desired, 8, w - item.w - 8];
				for (const other of neighbors) candidates.push(other.x - GAP - item.w, other.x + other.w + GAP);
				for (const x of candidates) {
					if (x < 8 || x + item.w > w - 8) continue;
					if (neighbors.some(other => x < other.x + other.w + GAP && x + item.w + GAP > other.x)) continue;
					const distance = Math.abs(x - desired);
					if (!best || distance < best.distance) best = {x, row, distance};
				}
			}
			if (!best) return null;
			placed.push({...item, x: best.x, row: best.row});
		}
		return placed;
	}

	function geometry(obj, api, acts) {
		const own = ownActions(obj, acts);
		const probes = own.filter(a => a.act === 'probe').map(a => caption(obj, a, api, true));
		const marks = own.filter(a => a.act === 'mark').map(a => caption(obj, a, api, false));
		const zones = (obj.zones || []).map(z => ({...z, labelW: api.measure(z.label, LABEL).w}));
		const ticks = (obj.ticks || []).map(value => ({value, text: String(value), w: api.measure(String(value), TICK).w}));
		const concurrent = items => items.map(item => items.filter(other => other.a.t0 <= item.a.t0 && item.a.t0 < other.end));
		const groups = concurrent(probes), rows = groups.some(group => group.length > 1) ? 2 : 1;
		const widths = [...probes, ...marks, ...ticks, ...zones.map(z => ({w: z.labelW}))].map(item => item.w);
		const pad = Math.max(24, ...widths.map(w => w / 2 + 16));
		const rowWidth = items => items.reduce((sum, item) => sum + item.w + GAP, 0);
		let w = Math.max(LINE_W + pad * 2, obj.title ? api.measure(obj.title, {size: 30}).w + 16 : 0,
			obj.unit ? api.measure(obj.unit, TICK).w + 16 : 0,
			...groups.map(rowWidth), ...concurrent(marks).map(rowWidth), rowWidth(zones.map(z => ({w: z.labelW}))));
		let x0, probeLabels, markLabels, zoneLabels;
		const at = value => x0 + LINE_W * Board.clamp(obj.max === obj.min ? 0 : (value - obj.min) / (obj.max - obj.min));
		// 空隙被長標籤切碎時擴充兩側留白，數線本身仍固定 1100。
		for (;;) {
			x0 = (w - LINE_W) / 2;
			probeLabels = placeLabels(probes.map(p => ({...p, at: at(p.a.args.value)})), w, rows);
			markLabels = placeLabels(marks.map(m => ({...m, at: at(m.a.args.value)})), w, 1);
			zoneLabels = placeLabels(zones.map(z => ({w: z.labelW, at: (at(z.from) + at(z.to)) / 2,
				a: {t0: 0}, end: Infinity})), w, 1);
			if (probeLabels && markLabels && zoneLabels) break;
			w += Math.max(32, ...widths) + GAP;
		}
		const top = obj.title ? TITLE_H : 0, probeTop = top + TRAVEL;
		const labelY = probeTop + rows * PROBE_H + 42, lineY = labelY + 68;
		const markY = lineY + 44 + (obj.unit ? 40 : 0) + MARK_H / 2;
		const layout = {w, h: lineY + 44 + (obj.unit ? 40 : 0) + (marks.length ? MARK_H : 0), x0, lineY, labelY,
			unitY: lineY + 64, ticks: ticks.map(tick => ({...tick, x: at(tick.value)})),
			probes: probeLabels.map(p => ({...p,
				y: probeTop + (p.row + .5) * PROBE_H, tipY: probeTop + rows * PROBE_H + 2})),
			marks: markLabels.map(m => ({...m, y: markY}))};
		layout.zones = zones.map((z, i) => ({...z, labelX: zoneLabels[i].x,
			x: Math.min(at(z.from), at(z.to)), y: lineY - 28, w: Math.abs(at(z.to) - at(z.from)), h: 14}));
		return layout;
	}

	function drawCaption(api, item, opts, color, p) {
		api.write(item.text, item.x, item.y, p, {...opts, color});
		if (item.result) api.write(item.result, item.x + item.labelW + 10, item.y, p,
			{...PROBE, color: api.color(item.a.args.result === 'pass' ? 'text.accent' : 'text.muted')});
		if (item.ellipsis) api.write('…', item.x + item.labelW + item.resultW + 8, item.y, p, {...opts, color});
	}

	Board.register('scale', {
		measure(obj, api, acts = []) {
			const {w, h} = geometry(obj, api, acts);
			return {w, h};
		},
		state(obj, acts, t, api) {
			const own = ownActions(obj, acts), layout = geometry(obj, api, own), anchors = {};
			const selected = own.filter(a => a.act === 'zone' && a.t0 <= t).pop();
			const zones = layout.zones.map(z => {
				const active = selected && selected.target === `${obj.id}:${z.id}`;
				const p = active ? progress(t, selected.t0, selected.t1) : 0;
				const alpha = active ? markAlpha(api, selected, t) : 0;
				const extra = 14 * p * alpha;
				const rect = {x: z.x, y: z.y - extra / 2, w: z.w, h: z.h + extra};
				anchors[z.id] = rect;
				return {...z, rect, p, alpha};
			});
			const probes = layout.probes.map((p, i) => {
			anchors[`p${i}`] = textBox(p.x, p.y, p.w, PROBE.size);
				const q = progress(t, p.a.t0, p.a.t1);
				return {...p, p: q, tipY: p.tipY - TRAVEL * (1 - Board.ease(q)),
					alpha: t < p.a.t0 ? 0 : markAlpha(api, p.a, t)};
			});
			const marks = layout.marks.map(m => ({...m, p: progress(t, m.a.t0, m.a.t1),
				alpha: t < m.a.t0 ? 0 : markAlpha(api, m.a, t)}));
			return {layout, zones, probes, marks, anchors};
		},
		draw(api, obj, st) {
			const r = st.layout, pencil = api.color('effects.pencil'), muted = api.color('text.muted');
			const accent = api.color('text.accent'), seed = Board.seed(obj.id);
			if (obj.title) api.text(obj.title, 8, TITLE_H / 2, {size: 30, color: muted, role: 'label'});
			api.ink([[r.x0, r.lineY], [r.x0 + LINE_W, r.lineY]], 1, {color: pencil, seed});
			api.ink([[r.x0 + 12, r.lineY - 7], [r.x0, r.lineY], [r.x0 + 12, r.lineY + 7]], 1, {color: pencil, seed: seed + 1});
			api.ink([[r.x0 + LINE_W - 12, r.lineY - 7], [r.x0 + LINE_W, r.lineY], [r.x0 + LINE_W - 12, r.lineY + 7]], 1, {color: pencil, seed: seed + 2});
			for (const z of st.zones) {
				const band = z.rect, color = api.color(z.kind === 'bad' ? 'code.error' : z.kind === 'edge' ? 'effects.highlight' : 'canvas.grid');
				api.ctx.save(); api.ctx.globalAlpha *= z.kind === 'bad' ? .35 : 1;
				api.rect(band.x, band.y, band.w, band.h, 1, {fill: color, color, seed: Board.seed(`${obj.id}:${z.id}`)});
				api.ctx.restore();
				if (z.alpha > .004 && z.p > 0) {
					api.ctx.save(); api.ctx.globalAlpha *= z.alpha;
					api.rect(band.x, band.y, band.w, band.h, z.p, {color: accent, width: 3.4, seed: Board.seed(`${obj.id}:${z.id}:zone`)});
					api.ctx.restore();
				}
				api.text(z.label, z.labelX, r.labelY, {...LABEL, color: muted, role: 'label'});
			}
			for (const tick of r.ticks) {
				api.ink([[tick.x, r.lineY], [tick.x, r.lineY + 8]], 1, {color: pencil, width: 2, seed});
				api.text(tick.text, tick.x, r.lineY + 26, {...TICK, color: muted, align: 'center'});
			}
			if (obj.unit) api.text(obj.unit, r.w / 2, r.unitY, {...TICK, color: muted, align: 'center'});
			st.probes.forEach((p, i) => {
				if (p.alpha <= .004 || p.p <= 0) return;
				api.ctx.save(); api.ctx.globalAlpha *= p.alpha;
				const s = seed + i;
				api.ink([[p.at - 8, p.tipY - 14], [p.at + 8, p.tipY - 14], [p.at, p.tipY], [p.at - 8, p.tipY - 14]], 1, {color: accent, seed: s});
				const dot = [];
				for (let j = 0; j <= 12; j++) {
					const angle = j * Math.PI / 6;
					dot.push([p.at + 3 * Math.cos(angle), p.tipY + 9 + 3 * Math.sin(angle)]);
				}
				api.ink(dot, 1, {color: accent, width: 2, seed: s});
				drawCaption(api, p, PROBE, api.color('text.body'), progress(p.p, .4, 1));
				api.ctx.restore();
			});
			st.marks.forEach((m, i) => {
				if (m.alpha <= .004 || m.p <= 0) return;
				api.ctx.save(); api.ctx.globalAlpha *= m.alpha;
				api.ink([[m.at, r.lineY - 8], [m.at, r.lineY + 10]], m.p, {color: accent, width: 3.4, seed: seed + i});
				drawCaption(api, m, MARK, accent, m.p);
				api.ctx.restore();
			});
		},
		anchors(obj, st) { return st.anchors; },
	});
})();
