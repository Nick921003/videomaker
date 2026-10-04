'use strict';
(() => {
	const FONT = {size: 80, weight: 600, mono: true}, LABEL = {size: 30}, LABEL_H = 46, BOX_H = 150;
	Board.register('output', {
		measure(obj, api) {
			const maxTextW = api.measure(obj._max_text || '', FONT).w;
			// 小標放在框外上方：框內只放大字，字再長也不會蓋到小標
			const top = obj.label ? LABEL_H : 0;
			const w = Math.max(440, maxTextW + 120, obj.label ? api.measure(obj.label, LABEL).w : 0);
			return {w, h: top + BOX_H, maxTextW, top};
		},
		state(obj, acts, t, api) {
			let text = '';
			const events = [];
			for (const a of acts) {
				if (a.act === 'set' && a.obj === obj.id) {
					events.push({t: a.t1, type: 'set', text: a.args.text});
				} else if (a.act === 'scan') {
					const toObj = a.args.to ? a.args.to.split(':')[0] : null;
					if (toObj === obj.id) {
						const per = (a.t1 - a.t0) / a.n;
						for (let k = 0; k < a.n; k++) {
							events.push({t: a.t0 + (k + 1) * per, type: 'append', char: a.args.chars[k]});
						}
					}
				}
			}
			events.sort((a, b) => a.t - b.t);
			for (const e of events) {
				if (e.t <= t) {
					if (e.type === 'set') text = e.text;
					else text += e.char;
				}
			}
			return {text};
		},
		draw(api, obj, st, t) {
			const m = this.measure(obj, api);
			api.rect(0, m.top, m.w, BOX_H, 1, {fill: api.color('card.fill'), role: 'panel'});
			if (obj.label) {
				api.text(obj.label, 0, LABEL_H / 2, {...LABEL, color: api.color('text.muted'), role: 'label'});
			}
			const startX = (m.w - m.maxTextW) / 2;
			api.text(st.text, startX, m.top + BOX_H / 2, {...FONT, color: api.color('text.body')});
		},
		anchors(obj, st, api) {
			const m = this.measure(obj, api);
			const startX = (m.w - m.maxTextW) / 2;
			const curW = api.measure(st.text, FONT).w;
			const charW = api.measure('X', FONT).w;
			const cy = m.top + BOX_H / 2;
			return {
				text: {x: startX, y: cy - 50, w: curW, h: 100},
				end: {x: startX + curW, y: cy - 50, w: charW, h: 100}
			};
		}
	});
})();
