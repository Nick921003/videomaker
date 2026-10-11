'use strict';
(() => {
	const TITLE_H = 44, STAGE_H = 96, GAP = 64, ITEM_H = 64, ITEM_GAP = 12, ITEM_PAD = 36;
	const NOTE_H = 52, PAD = 12, LIFT = 36;
	const LABEL = {size: 34, mono: true}, ITEM = {size: 30, mono: true}, NOTE = {size: 26};
	const key = (obj, target) => typeof target === 'string' && target.startsWith(`${obj.id}:`) ? target.slice(obj.id.length + 1) : target;
	const progress = (t, a, b) => b <= a ? (t >= b ? 1 : 0) : Board.clamp((t - a) / (b - a));
	const markAlpha = (api, a, t) => {
		const end = api.sceneEnd(a.scene);
		return 1 - Board.phase(t, end, end + .4);
	};

	function itemPlan(obj, acts) {
		const occupied = new Map(obj.stages.map(s => [s.id, new Map()])), initial = [], moves = [];
		const positions = new Map(), routes = new Map();
		let count = 2;
		const reserve = (id, at, slot) => {
			occupied.get(at).set(slot, id);
			count = Math.max(count, slot + 1);
		};
		const free = at => {
			let slot = 0;
			while (occupied.get(at).has(slot)) slot++;
			return slot;
		};
		for (const item of obj.items || []) {
			const position = {at: item.at, slot: free(item.at)};
			reserve(item.id, position.at, position.slot);
			positions.set(item.id, position);
			initial.push({...item, ...position, text: String(item.text)});
		}
		const events = acts.filter(a => a.act === 'move').flatMap(a => [
			{t: a.t0, start: true, a}, {t: a.t1, start: false, a}
		]).sort((a, b) => a.t - b.t || Number(a.start) - Number(b.start));
		// 移動期間起點與終點都留位，另一張卡不能搶走尚未離開的格子。
		for (const e of events) {
			const id = key(obj, e.a.target), at = key(obj, e.a.args.to);
			if (!positions.has(id) || !occupied.has(at)) continue;
			if (e.start) {
				const from = positions.get(id), to = {at, slot: at === from.at ? from.slot : free(at)};
				const route = {a: e.a, id, from: {...from}, to};
				reserve(id, at, to.slot);
				positions.set(id, to);
				routes.set(e.a, route);
				moves.push(route);
			} else {
				const route = routes.get(e.a);
				if (route && (route.from.at !== route.to.at || route.from.slot !== route.to.slot)) {
					const used = occupied.get(route.from.at);
					if (used.get(route.from.slot) === id) used.delete(route.from.slot);
				}
			}
		}
		return {initial, moves, count};
	}

	function geometry(obj, api, acts) {
		const plan = itemPlan(obj, acts), column = obj.direction === 'column';
		const steps = acts.filter(a => a.act === 'step'), rejects = acts.filter(a => a.act === 'reject');
		const texts = [...plan.initial.map(i => i.text), ...plan.moves.filter(m => m.a.args.text !== undefined).map(m => String(m.a.args.text))];
		const notes = [...obj.stages.map(s => s.note || ''), ...steps.map(a => a.args.note || '')];
		const itemW = Math.max(120, ...texts.map(s => api.measure(s, ITEM).w + 40));
		const noteW = Math.max(0, ...notes.map(s => api.measure(s, NOTE).w));
		const noteH = notes.some(Boolean) ? NOTE_H : 0;
		const itemH = plan.count * ITEM_H + (plan.count - 1) * ITEM_GAP;
		const widths = obj.stages.map(s => Math.max(180, api.measure(s.label, LABEL).w + 40));
		const slots = widths.map(w => Math.max(w, itemW, noteW));
		const titleW = obj.title ? api.measure(obj.title, {size: 30}).w : 0;
		const rejectW = Math.max(0, ...rejects.map(a => api.measure(a.args.text || '', NOTE).w));
		const top = PAD + (obj.title ? TITLE_H : 0);
		const rejectH = rejects.length ? column ? (rejectW ? NOTE_H : 0) : 100 : 0;
		const left = column && rejects.length ? GAP : 0;
		const laneW = Math.max(...widths, noteW), blockH = Math.max(STAGE_H, itemH);
		const contentW = column ? left + laneW + ITEM_PAD + itemW : slots.reduce((sum, w) => sum + w, 0) + (slots.length - 1) * GAP;
		const w = Math.max(contentW, titleW, rejectW) + PAD * 2;
		const h = top + rejectH + (column ? obj.stages.length * (blockH + noteH) + (obj.stages.length - 1) * GAP : STAGE_H + ITEM_PAD + itemH + noteH) + PAD;
		const stages = [], arrows = [];
		let x = (w - contentW) / 2;
		obj.stages.forEach((s, i) => {
			const y = top + rejectH + (column ? i * (blockH + noteH + GAP) : 0);
			const cx = column ? (w - contentW) / 2 + left + laneW / 2 : x + slots[i] / 2;
			const rect = {x: cx - widths[i] / 2, y, w: widths[i], h: STAGE_H};
			stages.push({id: s.id, rect, noteX: cx, noteY: y + (column ? blockH : STAGE_H + ITEM_PAD + itemH) + noteH / 2,
				itemX: column ? (w - contentW) / 2 + left + laneW + ITEM_PAD : cx - itemW / 2,
				itemY: column ? y : y + STAGE_H + ITEM_PAD});
			x += slots[i] + GAP;
		});
		for (let i = 1; i < stages.length; i++) {
			const a = stages[i - 1].rect, b = stages[i].rect;
			arrows.push(column ? [[a.x + a.w / 2, b.y - GAP + 8], [b.x + b.w / 2, b.y - 8]] :
				[[a.x + a.w + 8, a.y + a.h / 2], [b.x - 8, b.y + b.h / 2]]);
		}
		return {w, h, stages, arrows, plan, itemW, column, top, noteH};
	}

	function itemRect(layout, position) {
		const stage = layout.stages.find(s => s.id === position.at);
		return {x: stage.itemX, y: stage.itemY + position.slot * (ITEM_H + ITEM_GAP), w: layout.itemW, h: ITEM_H};
	}

	function rejectPath(layout, a, obj, api) {
		const from = layout.stages.find(s => s.id === key(obj, a.target)), to = layout.stages.find(s => s.id === key(obj, a.args.back_to));
		if (!from || !to) return null;
		const f = from.rect, r = to.rect, points = [];
		const start = layout.column ? [f.x - 6, f.y + f.h / 2] : [f.x + f.w / 2, f.y - 6];
		const end = layout.column ? [r.x - 6, r.y + r.h / 2] : [r.x + r.w / 2, r.y - 6];
		const bend = layout.column ? Math.min(f.x, r.x) - GAP : f.y - 110;
		for (let i = 0; i <= 24; i++) {
			const p = i / 24, q = 1 - p;
			points.push(layout.column ? [q * q * start[0] + 2 * q * p * bend + p * p * end[0], Board.mix(start[1], end[1], p)] :
				[Board.mix(start[0], end[0], p), q * q * start[1] + 2 * q * p * bend + p * p * end[1]]);
		}
		const text = String(a.args.text || ''), textW = api.measure(text, NOTE).w;
		return {points, text, x: Board.clamp((start[0] + end[0]) / 2, PAD + textW / 2, layout.w - PAD - textW / 2),
			y: layout.column ? layout.top + NOTE_H / 2 : f.y - 80};
	}

	function arrow(api, points, p, color, seed) {
		api.ink(points, p, {color, width: 3, seed});
		const end = points[points.length - 1], before = points[points.length - 2];
		const angle = Math.atan2(end[1] - before[1], end[0] - before[0]), length = 12;
		api.ink([[end[0] - length * Math.cos(angle - .5), end[1] - length * Math.sin(angle - .5)], end,
			[end[0] - length * Math.cos(angle + .5), end[1] - length * Math.sin(angle + .5)]], progress(p, .8, 1), {color, width: 3, seed: seed + 1});
	}

	Board.register('pipeline', {
		measure(obj, api, acts = []) {
			const {w, h} = geometry(obj, api, acts.filter(a => a.obj === obj.id));
			return {w, h};
		},
		state(obj, acts, t, api) {
			const own = acts.filter(a => a.obj === obj.id), layout = geometry(obj, api, own), anchors = {};
			const step = own.filter(a => a.act === 'step' && a.t0 <= t).pop();
			const current = step ? {id: key(obj, step.target), note: step.args.note, p: progress(t, step.t0, step.t1), alpha: markAlpha(api, step, t)} : null;
			for (const s of layout.stages) anchors[s.id] = {...s.rect};
			const items = layout.plan.initial.map(item => {
				let rect = itemRect(layout, item), text = item.text, flight = null, change = null;
				for (const m of layout.plan.moves.filter(m => m.id === item.id)) {
					const a = m.a;
					if (a.t0 > t) break;
					const from = itemRect(layout, m.from), to = itemRect(layout, m.to);
					const p = progress(t, a.t0, a.t1), travel = progress(p, 0, .7), q = Board.ease(travel);
					rect = {x: Board.mix(from.x, to.x, q), y: Board.mix(from.y, to.y, q) - Math.sin(q * Math.PI) * LIFT, w: layout.itemW, h: ITEM_H};
					flight = travel > 0 && travel < 1 ? {text, from, to, p: travel} : null;
					change = null;
					if (p >= 1) {
						if (a.args.text !== undefined) text = String(a.args.text);
					} else if (p > .7 && a.args.text !== undefined) {
						change = {text: String(a.args.text), p: progress(p, .7, 1)};
					}
				}
				anchors[item.id] = {...rect};
				return {id: item.id, rect, text, flight, change};
			});
			const rejects = own.filter(a => a.act === 'reject'), marks = [];
			rejects.forEach((a, i) => {
				if (a.t0 > t) return;
				const next = rejects[i + 1], previous = rejects[i - 1];
				const alpha = markAlpha(api, a, t) * (next ? 1 - Board.phase(t, next.t0, next.t0 + .4) : 1);
				const start = previous ? Math.max(a.t0, Math.min(a.t0 + .4, api.sceneEnd(previous.scene) + .4)) : a.t0;
				const p = progress(t, start, Math.max(start, a.t1));
				const path = rejectPath(layout, a, obj, api);
				if (path && alpha > .004 && p > 0) marks.push({...path, p, alpha, seed: Board.seed(`${obj.id}:reject:${i}`)});
			});
			return {layout, current, items, marks, anchors};
		},
		draw(api, obj, st) {
			const pencil = api.color('effects.pencil'), accent = api.color('text.accent'), muted = api.color('text.muted');
			if (obj.title) api.text(obj.title, PAD, PAD + TITLE_H / 2, {size: 30, color: muted, role: 'label'});
			st.layout.stages.forEach((s, i) => {
				const r = s.rect, seed = Board.seed(`${obj.id}:${s.id}`), active = st.current && st.current.id === s.id ? st.current : null;
				api.rect(r.x, r.y, r.w, r.h, 1, {fill: api.color('card.fill'), color: pencil, seed, role: 'panel'});
				if (active && active.alpha > .004) {
					api.ctx.save(); api.ctx.globalAlpha *= active.alpha;
					api.ctx.save(); api.ctx.globalAlpha *= .18 * active.p;
					api.ctx.fillStyle = api.color('effects.highlight'); api.ctx.fillRect(r.x, r.y, r.w, r.h);
					api.ctx.restore();
					api.rect(r.x, r.y, r.w, r.h, active.p, {color: accent, seed, role: null});
					api.ctx.restore();
				}
				api.text(obj.stages[i].label, r.x + r.w / 2, r.y + r.h / 2, {...LABEL, color: api.color('text.body'), align: 'center'});
				if (active && active.alpha > .004 && active.note !== undefined) {
					api.write(active.note, s.noteX, s.noteY, active.p, {...NOTE, color: muted, align: 'center', alpha: active.alpha});
				} else if (obj.stages[i].note) api.text(obj.stages[i].note, s.noteX, s.noteY, {...NOTE, color: muted, align: 'center'});
			});
			st.layout.arrows.forEach((points, i) => arrow(api, points, 1, pencil, Board.seed(`${obj.id}:arrow:${i}`)));
			for (const item of st.items) {
				const r = item.rect, cx = r.x + r.w / 2, cy = r.y + r.h / 2;
				api.rect(r.x, r.y, r.w, r.h, 1, {fill: api.color('card.fill'), color: pencil, seed: Board.seed(`${obj.id}:${item.id}`), role: 'panel'});
				if (item.flight) continue;
				if (item.change) {
					const c = item.change;
					api.text(item.text, cx, cy - 18 * c.p, {...ITEM, color: muted, align: 'center', alpha: 1 - c.p});
					api.write(c.text, cx, cy, c.p, {...ITEM, color: api.color('text.body'), align: 'center'});
				} else api.text(item.text, cx, cy, {...ITEM, color: api.color('text.body'), align: 'center'});
			}
			for (const m of st.marks) {
				api.ctx.save(); api.ctx.globalAlpha *= m.alpha;
				arrow(api, m.points, m.p, accent, m.seed);
				api.write(m.text, m.x, m.y, m.p, {...NOTE, color: accent, align: 'center'});
				api.ctx.restore();
			}
		},
		anchors(obj, st) { return st.anchors; },
		overlay(api, obj, st, t, world) {
			const pl = world.placement(obj.id);
			if (!pl) return;
			for (const item of st.items) {
				const f = item.flight;
				if (!f) continue;
				const center = r => ({x: pl.x + (r.x + r.w / 2) * pl.s, y: pl.y + (r.y + r.h / 2) * pl.s});
				api.fly(f.text, center(f.from), center(f.to), f.p, {...ITEM, size: ITEM.size * pl.s, lift: LIFT * pl.s, color: api.color('text.body')});
			}
		}
	});
})();
