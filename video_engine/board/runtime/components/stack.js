'use strict';
(() => {
	const TITLE_H = 44, HEADER_H = 52, CALC_H = 52, NAME_H = 40, BOX_H = 88, HISTORY_H = 32;
	const GAP = 40, ROW_GAP = 24, FRAME_GAP = 18, PAD = 24, BOTTOM = 8, TRAVEL = 40;
	const HEADER = {size: 34, mono: true}, NAME = {size: 32, mono: true}, TYPE = {size: 28};
	const VALUE = {size: 52, weight: 600, mono: true}, HISTORY = {size: 28, mono: true};
	const CALC = {size: 36, mono: true}, RETURN = {size: 30, mono: true};
	const progress = (t, a, b) => b <= a ? (t >= b ? 1 : 0) : Board.clamp((t - a) / (b - a));
	const valueText = value => value === undefined ? '?' : String(value);
	const historyText = (values, count) => (count > 3 ? '… ' : '') + values.join(' ');
	const key = (obj, target) => typeof target === 'string' && target.startsWith(`${obj.id}:`) ? target.slice(obj.id.length + 1) : target;
	const markAlpha = (api, a, t) => {
		const end = api.sceneEnd(a.scene);
		return 1 - Board.phase(t, end, end + .4);
	};
	const initialOrder = (obj, acts) => obj.frames.filter(f => !acts.some(a => a.act === 'push' && key(obj, a.target) === f.id)).map(f => f.id);

	function frameEvents(obj, acts) {
		const events = [];
		for (const a of acts) {
			if (a.act === 'push' || a.act === 'pop') events.push({t: a.t0, kind: a.act, id: key(obj, a.target), a});
			if (a.act === 'pop') events.push({t: a.t1, kind: 'remove', id: key(obj, a.target), a});
		}
		return events.sort((a, b) => a.t - b.t);
	}

	function valueEvents(obj, acts) {
		const events = [];
		for (const a of acts) {
			if (a.act === 'set') {
				const id = key(obj, a.target);
				events.push({t: a.t0, kind: 'change', id, a}, {t: a.t1, kind: 'value', id, a});
			} else if (a.act === 'pop' && a.args.to && a.args.value !== undefined) {
				events.push({t: a.t1, kind: 'value', id: key(obj, a.args.to), a});
			}
		}
		return events.sort((a, b) => a.t - b.t);
	}

	function geometry(obj, api, acts) {
		const updates = valueEvents(obj, acts), order = initialOrder(obj, acts);
		let maxCount = order.length;
		// pop 到 t1 才移除，進出中的框也算同時存在。
		for (const e of frameEvents(obj, acts)) {
			if (!obj.frames.some(f => f.id === e.id)) continue;
			const i = order.indexOf(e.id);
			if (e.kind === 'push' && i < 0) order.push(e.id);
			if (e.kind === 'remove' && i >= 0) order.splice(i, 1);
			maxCount = Math.max(maxCount, order.length);
		}
		const frames = obj.frames.map(frame => {
			const variables = frame.vars || [];
			const calcH = acts.some(a => a.act === 'set' && a.args.calc !== undefined && variables.some(v => key(obj, a.target) === v.id)) ? CALC_H : 0;
			const widths = variables.map(variable => {
				const nameW = api.measure(variable.name, NAME).w + (variable.type ? api.measure(variable.type, TYPE).w + api.measure(' ', NAME).w : 0);
				let value = valueText(variable.value), history = [], count = 0;
				let w = Math.max(160, nameW, api.measure(value, VALUE).w + 48);
				// 所有中途歷史視窗都要量，回傳寫入也會留下舊值。
				for (const e of updates.filter(e => e.id === variable.id)) {
					if (e.kind === 'change') {
						if (e.a.args.calc !== undefined) w = Math.max(w, api.measure(e.a.args.calc, CALC).w + 24);
						continue;
					}
					history = [...history, value].slice(-3);
					count++;
					value = valueText(e.a.args.value);
					w = Math.max(w, api.measure(value, VALUE).w + 48, api.measure(historyText(history, count), HISTORY).w);
				}
				return w;
			});
			const perRow = variables.length > 4 ? 3 : Math.max(1, variables.length), rowWidths = [];
			for (let i = 0; i < widths.length; i += perRow) {
				const row = widths.slice(i, i + perRow);
				rowWidths.push(row.reduce((sum, w) => sum + w, 0) + (row.length - 1) * GAP);
			}
			const returns = acts.filter(a => a.act === 'pop' && key(obj, a.target) === frame.id && a.args.value !== undefined);
			const returnW = Math.max(0, ...returns.map(a => api.measure(`return ${valueText(a.args.value)}`, RETURN).w));
			const headerW = api.measure(frame.name, HEADER).w + (returns.length ? GAP + returnW : 0);
			const rowH = calcH + NAME_H + BOX_H + HISTORY_H;
			return {widths, perRow, rowWidths, calcH, rowH,
				w: Math.max(160, headerW, ...rowWidths) + PAD * 2,
				h: HEADER_H + rowWidths.length * rowH + Math.max(0, rowWidths.length - 1) * ROW_GAP + BOTTOM};
		});
		const w = Math.max(160, obj.title ? api.measure(obj.title, {size: 30}).w : 0, ...frames.map(f => f.w));
		const frameH = Math.max(HEADER_H + BOTTOM, ...frames.map(f => f.h));
		for (const f of frames) {
			f.columns = [];
			f.rowWidths.forEach((rowW, row) => {
				let x = (w - rowW) / 2;
				const y = HEADER_H + row * (f.rowH + ROW_GAP);
				for (let i = row * f.perRow; i < Math.min(f.widths.length, (row + 1) * f.perRow); i++) {
					f.columns.push({x, y: y + f.calcH + NAME_H, w: f.widths[i], h: BOX_H,
						calcY: y + f.calcH / 2, nameY: y + f.calcH + NAME_H / 2,
						historyY: y + f.calcH + NAME_H + BOX_H + HISTORY_H / 2});
					x += f.widths[i] + GAP;
				}
			});
		}
		return {w, h: (obj.title ? TITLE_H : 0) + TRAVEL + maxCount * frameH + Math.max(0, maxCount - 1) * FRAME_GAP,
			frameH, maxCount, frames};
	}

	function drawVariable(api, obj, variable, v, r) {
		const muted = api.color('text.muted'), pencil = api.color('effects.pencil'), body = api.color('text.body');
		const seed = Board.seed(`${obj.id}:${variable.id}`), cx = r.x + r.w / 2;
		const nameW = api.measure(variable.name, NAME).w;
		const typeW = variable.type ? api.measure(variable.type, TYPE).w + api.measure(' ', NAME).w : 0;
		const nameX = cx - (nameW + typeW) / 2;
		if (variable.type) api.text(variable.type, nameX, r.nameY, {...TYPE, color: muted, role: 'label'});
		api.text(variable.name, nameX + typeW, r.nameY, {...NAME, color: body, role: 'label'});
		api.rect(r.x, r.y, r.w, r.h, 1, {fill: api.color('card.fill'), color: api.color('card.edge'), seed, role: 'panel'});
		const change = v.change, writing = change && change.writing;
		if (!v.known && !writing) api.hatch(r.x, r.y, r.w, r.h, seed);
		const valueY = r.y + r.h / 2;
		api.write(writing ? change.value : v.value, cx, valueY, writing ? change.newP : 1, {...VALUE, color: body, align: 'center'});
		if (change) {
			if (!writing) {
				const half = api.measure(v.value, VALUE).w / 2;
				api.ink([[cx - half - 4, valueY], [cx + half + 4, valueY]], change.strikeP, {color: pencil, width: 3, seed});
			}
			if (change.calc !== null) api.write(change.calc, cx, r.calcY, change.calcP, {...CALC, color: api.color('text.accent'), align: 'center', alpha: change.calcAlpha});
		}
		const history = historyText(v.history, v.count), space = api.measure(' ', HISTORY).w;
		let x = cx - api.measure(history, HISTORY).w / 2;
		if (v.count > 3) {
			api.text('…', x, r.historyY, {...HISTORY, color: muted});
			x += api.measure('…', HISTORY).w + space;
		}
		v.history.forEach((old, j) => {
			const w = api.text(old, x, r.historyY, {...HISTORY, color: muted});
			api.ink([[x, r.historyY], [x + w, r.historyY]], 1, {color: pencil, width: 2, seed: seed + j});
			x += w + space;
		});
	}

	Board.register('stack', {
		measure(obj, api, acts = []) {
			const {w, h} = geometry(obj, api, acts.filter(a => a.obj === obj.id));
			return {w, h};
		},
		state(obj, acts, t, api) {
			const own = acts.filter(a => a.obj === obj.id), layout = geometry(obj, api, own);
			const order = initialOrder(obj, own), variables = {};
			const frames = obj.frames.map((frame, i) => {
				for (const v of frame.vars || []) variables[v.id] = {value: valueText(v.value), known: v.value !== undefined, history: [], count: 0, change: null};
				return {id: frame.id, visible: order.includes(frame.id), slot: Math.min(i, Math.max(0, layout.maxCount - 1)), transition: null};
			});
			for (const e of frameEvents(obj, own)) {
				if (e.t > t) break;
				const f = frames.find(f => f.id === e.id);
				if (!f) continue;
				const i = order.indexOf(e.id);
				if (e.kind === 'push') {
					if (i < 0) order.push(e.id);
					f.visible = true;
					f.transition = e.a;
				} else if (i >= 0) {
					f.slot = i;
					if (e.kind === 'pop') f.transition = e.a;
					else { order.splice(i, 1); f.visible = false; }
				}
			}
			for (const e of valueEvents(obj, own)) {
				if (e.t > t) break;
				const v = variables[e.id];
				if (!v) continue;
				if (e.kind === 'change') v.change = e.a;
				else {
					v.history = [...v.history, v.value].slice(-3);
					v.count++;
					v.value = valueText(e.a.args.value);
					v.known = true;
					if (e.a.act === 'pop' || v.change === e.a) v.change = null;
				}
			}
			for (const v of Object.values(variables)) {
				if (!v.change) continue;
				const a = v.change, p = progress(t, a.t0, a.t1), hasCalc = a.args.calc !== undefined, start = hasCalc ? .6 : .4;
				v.change = {value: valueText(a.args.value), writing: p >= start,
					newP: progress(p, start, 1), strikeP: progress(p, hasCalc ? .4 : 0, start),
					calc: hasCalc ? String(a.args.calc) : null, calcP: progress(p, 0, .4),
					calcAlpha: (1 - progress(p, .6, 1)) * markAlpha(api, a, t)};
			}
			const anchors = {}, flights = [], active = order[order.length - 1];
			frames.forEach((f, i) => {
				if (f.visible) f.slot = order.indexOf(f.id);
				const a = f.transition, p = a ? progress(t, a.t0, a.t1) : 1;
				const moving = a && a.act === 'pop' ? Board.ease(progress(p, .5, 1)) : 1 - Board.ease(p);
				f.alpha = f.visible ? a && a.act === 'pop' ? 1 - moving : Board.ease(p) : 0;
				f.rect = {x: 0, y: layout.h - (f.slot + 1) * layout.frameH - f.slot * FRAME_GAP - TRAVEL * moving, w: layout.w, h: layout.frameH};
				f.active = f.id === active;
				anchors[f.id] = {...f.rect};
				f.columns = layout.frames[i].columns.map(r => ({...r, y: r.y + f.rect.y,
					calcY: r.calcY + f.rect.y, nameY: r.nameY + f.rect.y, historyY: r.historyY + f.rect.y}));
				(obj.frames[i].vars || []).forEach((v, j) => {
					const {x, y, w, h} = f.columns[j];
					anchors[v.id] = {x, y, w, h};
				});
				if (a && a.act === 'pop' && f.visible && t < a.t1 && a.args.value !== undefined) {
					const alpha = markAlpha(api, a, t), text = `return ${valueText(a.args.value)}`;
					f.return = {text, p: progress(p, 0, .5), alpha};
					if (a.args.to && p > .5 && alpha > .004) flights.push({value: valueText(a.args.value), to: `${obj.id}:${key(obj, a.args.to)}`,
						from: {x: layout.w - PAD - api.measure(text, RETURN).w / 2, y: f.rect.y + HEADER_H / 2},
						p: progress(p, .5, 1), alpha});
				}
			});
			anchors.top = active ? {...anchors[active]} : {x: layout.w / 2, y: layout.h, w: 0, h: 0};
			return {layout, frames, variables, anchors, flights};
		},
		draw(api, obj, st) {
			const muted = api.color('text.muted'), accent = api.color('text.accent'), pencil = api.color('effects.pencil');
			if (obj.title) api.text(obj.title, 0, TITLE_H / 2, {size: 30, color: muted, role: 'label'});
			st.frames.forEach((f, i) => {
				if (f.alpha <= .004) return;
				const r = f.rect, frame = obj.frames[i];
				api.ctx.save(); api.ctx.globalAlpha *= f.alpha;
				api.rect(r.x, r.y, r.w, r.h, 1, {fill: api.color('card.fill'), color: f.active ? accent : pencil, seed: Board.seed(`${obj.id}:${f.id}`), role: 'panel'});
				api.text(frame.name, PAD, r.y + HEADER_H / 2, {...HEADER, color: f.active ? accent : muted});
				(frame.vars || []).forEach((v, j) => drawVariable(api, obj, v, st.variables[v.id], f.columns[j]));
				if (f.return) api.write(f.return.text, st.layout.w - PAD, r.y + HEADER_H / 2, f.return.p, {...RETURN, color: accent, align: 'right', alpha: f.return.alpha});
				api.ctx.restore();
			});
		},
		anchors(obj, st) { return st.anchors; },
		overlay(api, obj, st, t, world) {
			const pl = world.placement(obj.id);
			if (!pl) return;
			for (const f of st.flights) {
				const to = world.anchor(f.to);
				if (!to) continue;
				// 飛行用世界座標，字級和弧線高度一起乘版面縮放。
				const from = {x: pl.x + f.from.x * pl.s, y: pl.y + f.from.y * pl.s};
				api.ctx.save(); api.ctx.globalAlpha *= f.alpha;
				api.fly(f.value, from, {x: to.x + to.w / 2, y: to.y + to.h / 2}, f.p, {...VALUE, size: VALUE.size * pl.s, lift: 60 * pl.s, color: api.color('text.accent')});
				api.ctx.restore();
			}
		}
	});
})();
