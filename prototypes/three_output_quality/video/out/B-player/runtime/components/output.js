'use strict';
(() => {
	const FONT = {size: 80, weight: 600, mono: true}, LABEL = {size: 32}, LABEL_H = 46, BOX_H = 150;

	function events(obj, acts) {
		const result = [];
		for (const a of acts) {
			if (a.obj === obj.id && a.act === 'set') {
				result.push({t: a.t1, type: 'set', text: a.args.text});
			} else if (a.obj === obj.id && a.act === 'append') {
				const chars = Array.from(a.args.text), per = (a.t1 - a.t0) / chars.length;
				chars.forEach((char, k) => result.push({t: k === chars.length - 1 ? a.t1 : a.t0 + (k + 1) * per, type: 'append', text: char}));
			} else if (a.act === 'scan' && a.args.to && a.args.to.split(':')[0] === obj.id) {
				const per = (a.t1 - a.t0) / a.n;
				for (let k = 0; k < a.n; k++) result.push({t: a.t0 + (k + 1) * per, type: 'append', text: a.args.chars[k]});
			}
		}
		return result.sort((a, b) => a.t - b.t);
	}

	function geometry(obj, api, changes) {
		const texts = [obj._max_text || ''];
		let text = '';
		for (const e of changes) {
			text = e.type === 'set' ? e.text : text + e.text;
			texts.push(text);
		}
		// 字數最多未必最寬，換行數最多也可能出現在較早的 set。
		const rows = texts.map(text => String(text).split('\n'));
		const maxRows = Math.max(1, ...rows.map(r => r.length));
		const font = {...FONT, size: maxRows > 1 ? 56 : FONT.size}, lineH = font.size * 1.3;
		const maxTextW = Math.max(0, ...rows.flat().map(r => api.measure(r, font).w));
		const top = obj.label ? LABEL_H : 0;
		const boxH = maxRows > 1 ? Math.max(BOX_H, maxRows * lineH + 60) : BOX_H;
		const w = Math.max(440, maxTextW + 120, obj.label ? api.measure(obj.label, LABEL).w : 0);
		return {w, h: top + boxH, maxTextW, top, boxH, font, lineH,
			startX: (w - maxTextW) / 2, firstY: top + (boxH - maxRows * lineH) / 2 + lineH / 2};
	}

	function anchors(text, m, api) {
		const rows = String(text).split('\n'), widths = rows.map(row => api.measure(row, m.font).w);
		const height = m.font.size * 1.25, last = rows.length - 1;
		return {
			text: {x: m.startX, y: m.firstY - height / 2, w: Math.max(...widths), h: last * m.lineH + height},
			end: {x: m.startX + widths[last], y: m.firstY + last * m.lineH - height / 2, w: api.measure('X', m.font).w, h: height}
		};
	}

	Board.register('output', {
		measure(obj, api, acts = []) {
			return geometry(obj, api, events(obj, acts));
		},
		state(obj, acts, t, api) {
			const changes = events(obj, acts), layout = geometry(obj, api, changes);
			let text = '';
			for (const e of changes) {
				if (e.t > t) break;
				text = e.type === 'set' ? e.text : text + e.text;
			}
			return {text, layout, anchors: anchors(text, layout, api)};
		},
		draw(api, obj, st) {
			const m = st.layout;
			api.rect(0, m.top, m.w, m.boxH, 1, {fill: api.color('card.fill'), role: 'panel'});
			if (obj.label) api.text(obj.label, 0, LABEL_H / 2, {...LABEL, color: api.color('text.muted'), role: 'label'});
			String(st.text).split('\n').forEach((row, i) => {
				api.text(row, m.startX, m.firstY + i * m.lineH, {...m.font, color: api.color('text.body')});
			});
		},
		anchors(obj, st) { return st.anchors; }
	});
})();
