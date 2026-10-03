'use strict';
(() => {
	const FONT = {size: 80, weight: 600, mono: true};
	Board.register('output', {
		measure(obj, api) {
			const maxTextW = api.measure(obj._max_text || '', FONT).w;
			const w = Math.max(440, maxTextW + 120);
			return {w, h: 150, maxTextW};
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
			api.rect(0, 0, m.w, m.h, 1, {fill: api.color('card.fill'), role: 'panel'});
			if (obj.label) {
				api.text(obj.label, 20, 30, {size: 30, color: api.color('text.muted'), role: 'label'});
			}
			const startX = (m.w - m.maxTextW) / 2;
			api.text(st.text, startX, m.h / 2, {...FONT, color: api.color('text.body')});
		},
		anchors(obj, st, api) {
			const m = this.measure(obj, api);
			const startX = (m.w - m.maxTextW) / 2;
			const curW = api.measure(st.text, FONT).w;
			const charW = api.measure('X', FONT).w;
			return {
				text: {x: startX, y: m.h / 2 - 50, w: curW, h: 100},
				end: {x: startX + curW, y: m.h / 2 - 50, w: charW, h: 100}
			};
		}
	});
})();
