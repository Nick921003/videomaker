'use strict';
(() => {
	const TITLE_H = 44, CALC_H = 52, NAME_H = 48, BOX_H = 112, HISTORY_H = 40, CHECK_H = 64;
	const GAP = 40, ROW_GAP = 24;
	const NAME = {size: 36, mono: true}, TYPE = {size: 28};
	const VALUE = {size: 64, weight: 600, mono: true}, HISTORY = {size: 28, mono: true};
	const CALC = {size: 36, mono: true}, CHECK = {size: 36, mono: true};
	const progress = (t, a, b) => b <= a ? (t >= b ? 1 : 0) : Board.clamp((t - a) / (b - a));
	const valueText = value => value === undefined ? '?' : String(value);
	const historyText = (values, count) => (count > 4 ? '… ' : '') + values.join(' ');
	const checkText = args => String(args.text) + (args.result === true ? ' → 成立 ✓' : args.result === false ? ' → 不成立 ✗' : '');
	const ownActions = (obj, acts) => acts.filter(a => a.obj === obj.id);
	const variableActions = (obj, variable, acts) => acts.filter(a => a.target === `${obj.id}:${variable.id}` && ['declare', 'set'].includes(a.act));

	function geometry(obj, api, acts) {
		const own = ownActions(obj, acts), checks = own.filter(a => a.act === 'check');
		const hasCalc = own.some(a => a.act === 'set' && a.args.calc !== undefined);
		const top = obj.title ? TITLE_H : 0, calcH = hasCalc ? CALC_H : 0;
		const rowH = calcH + NAME_H + BOX_H + HISTORY_H;
		const perRow = obj.vars.length > 4 ? 3 : obj.vars.length;
		const widths = obj.vars.map(variable => {
			const nameW = api.measure(variable.name, NAME).w + (variable.type ? api.measure(variable.type, TYPE).w + api.measure(' ', NAME).w : 0);
			let value = valueText(variable.value), count = 0, history = [];
			let w = Math.max(160, nameW, api.measure(value, VALUE).w + 48);
			// 逐次量測歷史視窗，不能只看最後一次 set 的結果
			for (const a of variableActions(obj, variable, own)) {
				if (a.act === 'set') {
					history = [...history, value].slice(-4);
					count++;
					w = Math.max(w, api.measure(historyText(history, count), HISTORY).w);
					if (a.args.calc !== undefined) w = Math.max(w, api.measure(a.args.calc, CALC).w + 24);
				}
				if (a.args.value !== undefined) value = valueText(a.args.value);
				w = Math.max(w, api.measure(value, VALUE).w + 48);
			}
			return w;
		});
		const rowWidths = [];
		for (let i = 0; i < widths.length; i += perRow) {
			const row = widths.slice(i, i + perRow);
			rowWidths.push(row.reduce((sum, w) => sum + w, 0) + (row.length - 1) * GAP);
		}
		const w = Math.max(...rowWidths, obj.title ? api.measure(obj.title, {size: 30}).w : 0, ...checks.map(a => api.measure(checkText(a.args), CHECK).w));
		const columns = [];
		rowWidths.forEach((rowW, row) => {
			let x = (w - rowW) / 2;
			const y = top + row * (rowH + ROW_GAP);
			for (let i = row * perRow; i < Math.min(widths.length, (row + 1) * perRow); i++) {
				columns.push({x, y: y + calcH + NAME_H, w: widths[i], h: BOX_H,
					calcY: y + calcH / 2, nameY: y + calcH + NAME_H / 2,
					historyY: y + calcH + NAME_H + BOX_H + HISTORY_H / 2});
				x += widths[i] + GAP;
			}
		});
		const contentH = top + rowWidths.length * rowH + (rowWidths.length - 1) * ROW_GAP;
		return {w, h: contentH + (checks.length ? CHECK_H : 0), columns,
			checkY: contentH + (checks.length ? CHECK_H / 2 : 0), hasCheck: checks.length > 0};
	}

	Board.register('vars', {
		measure(obj, api, acts) {
			const {w, h} = geometry(obj, api, acts);
			return {w, h};
		},
		state(obj, acts, t, api) {
			const own = ownActions(obj, acts), layout = geometry(obj, api, acts);
			const variables = obj.vars.map(variable => {
				const actions = variableActions(obj, variable, own);
				const declared = actions.some(a => a.act === 'declare');
				const v = {value: valueText(variable.value), known: variable.value !== undefined,
					alpha: declared ? 0 : 1, nameP: declared ? 0 : 1, history: [], count: 0, change: null};
				for (const a of actions) {
					if (t < a.t0) break;
					const p = progress(t, a.t0, a.t1);
					if (a.act === 'declare') {
						v.alpha = p;
						v.nameP = p;
						if (a.args.value !== undefined) {
							v.value = valueText(a.args.value);
							v.known = true;
						}
						v.change = null;
					} else if (t >= a.t1) {
						v.history = [...v.history, v.value].slice(-4);
						v.count++;
						v.value = valueText(a.args.value);
						v.known = true;
						v.change = null;
					} else {
						const hasCalc = a.args.calc !== undefined, start = hasCalc ? .6 : .4;
						v.change = {value: valueText(a.args.value), writing: p >= start,
							newP: progress(p, start, 1), strikeP: progress(p, hasCalc ? .4 : 0, start),
							calc: hasCalc ? String(a.args.calc) : null, calcP: progress(p, 0, .4),
							calcAlpha: 1 - progress(p, .6, 1)};
					}
				}
				return v;
			});
			const checks = own.filter(a => a.act === 'check');
			let check = null;
			for (let i = 0; i < checks.length; i++) {
				const a = checks[i];
				if (t < a.t0) break;
				const sceneEnd = api.sceneEnd(a.scene), next = checks[i + 1];
				const alpha = (1 - Board.phase(t, sceneEnd, sceneEnd + .4)) *
					(next ? 1 - Board.phase(t, next.t0, next.t0 + .4) : 1);
				// 舊條件先退場再寫新條件，兩段字不在同一列交疊
				const previous = checks[i - 1];
				const start = previous ? Math.max(a.t0, Math.min(a.t0 + .4, api.sceneEnd(previous.scene) + .4)) : a.t0;
				const p = progress(t, start, Math.max(start, a.t1));
				if (p > 0 && alpha > .004) check = {text: checkText(a.args), result: a.args.result, p, alpha};
			}
			const anchors = {};
			obj.vars.forEach((variable, i) => {
				const {x, y, w, h} = layout.columns[i];
				anchors[variable.id] = {x, y, w, h};
			});
			const checkW = check ? api.measure(check.text, CHECK).w : 0;
			const checkH = layout.hasCheck ? CHECK.size * 1.24 : 0;
			anchors.check = {x: (layout.w - checkW) / 2, y: layout.checkY - checkH / 2, w: checkW, h: checkH};
			return {layout, variables, check, anchors};
		},
		draw(api, obj, st) {
			const muted = api.color('text.muted'), pencil = api.color('effects.pencil');
			const accent = api.color('text.accent'), body = api.color('text.body');
			if (obj.title) api.text(obj.title, 0, TITLE_H / 2, {size: 30, color: muted, role: 'label'});
			obj.vars.forEach((variable, i) => {
				const v = st.variables[i], r = st.layout.columns[i], cx = r.x + r.w / 2;
				if (v.alpha <= .004) return;
				const seed = Board.seed(`${obj.id}:${variable.id}`);
				api.ctx.save(); api.ctx.globalAlpha *= v.alpha;
				const nameW = api.measure(variable.name, NAME).w;
				const typeW = variable.type ? api.measure(variable.type, TYPE).w + api.measure(' ', NAME).w : 0;
				const nameX = cx - (nameW + typeW) / 2;
				if (variable.type) api.write(variable.type, nameX, r.nameY, v.nameP, {...TYPE, color: muted, role: 'label'});
				api.write(variable.name, nameX + typeW, r.nameY, v.nameP, {...NAME, color: body, role: 'label'});
				api.rect(r.x, r.y, r.w, r.h, 1, {fill: api.color('card.fill'), color: api.color('card.edge'), seed, role: 'panel'});
				const change = v.change, writing = change && change.writing;
				if (!v.known && !writing) api.hatch(r.x, r.y, r.w, r.h, seed);
				const text = writing ? change.value : v.value, valueY = r.y + r.h / 2;
				api.write(text, cx, valueY, writing ? change.newP : 1, {...VALUE, color: body, align: 'center'});
				if (change) {
					if (!writing) {
						const half = api.measure(v.value, VALUE).w / 2;
						api.ink([[cx - half - 4, valueY], [cx + half + 4, valueY]], change.strikeP, {color: pencil, width: 3, seed});
					}
					if (change.calc !== null) api.write(change.calc, cx, r.calcY, change.calcP, {...CALC, color: accent, align: 'center', alpha: change.calcAlpha});
				}
				const history = historyText(v.history, v.count), space = api.measure(' ', HISTORY).w;
				let x = cx - api.measure(history, HISTORY).w / 2;
				if (v.count > 4) {
					api.text('…', x, r.historyY, {...HISTORY, color: muted});
					x += api.measure('…', HISTORY).w + space;
				}
				v.history.forEach((old, j) => {
					const w = api.text(old, x, r.historyY, {...HISTORY, color: muted});
					api.ink([[x, r.historyY], [x + w, r.historyY]], 1, {color: pencil, width: 2, seed: seed + j});
					x += w + space;
				});
				api.ctx.restore();
			});
			if (st.check) {
				const c = st.check, color = c.result === true ? accent : c.result === false ? muted : body;
				api.write(c.text, st.layout.w / 2, st.layout.checkY, c.p, {...CHECK, color, align: 'center', alpha: c.alpha});
			}
		},
		anchors(obj, st) { return st.anchors; },
	});
})();
