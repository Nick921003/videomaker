'use strict';
(() => {
	Board.register('list', {
		measure(obj, api, acts) {
			const rows = [...(obj.rows || [])];
			const objActs = (acts || []).filter(a => a.obj === obj.id);
			for (const a of objActs) {
				if (a.act === 'append') rows.push(a.args.text);
			}
			
			let labelW = 0;
			for (const a of objActs) {
				if (a.act === 'walk') labelW = Math.max(labelW, api.measure(a.args.item, { size: 34, mono: true }).w + 24);
			}
			
			let cardW = 0;
			const oNormal = { size: 34, mono: true };
			for (const r of rows) {
				cardW = Math.max(cardW, api.measure(r, oNormal).w + 28 * 2 + 70);
			}
			
			let titleW = 0;
			if (obj.title) {
				titleW = api.measure(obj.title, { size: 34 }).w;
				cardW = Math.max(cardW, titleW);
			}
			
			const w = (labelW > 0 ? labelW + 20 : 0) + cardW;
			let h = 0;
			if (obj.title) h += 50;
			h += rows.length * (74 + 14);
			
			return { w, h };
		},
		state(obj, acts, t, api) {
			const objActs = (acts || []).filter(a => a.obj === obj.id);
			const rows = (obj.rows || []).map(r => ({ text: r, t0: 0, t1: 0 }));
			for (const a of objActs) {
				if (a.act === 'append') {
					rows.push({ text: a.args.text, t0: a.t0, t1: a.t1 });
				}
			}
			
			let results = new Array(rows.length).fill(null);
			let label = null;
			
			const walk_acts = objActs.filter(a => a.act === 'walk');
			let active_walk = null;
			for (const w of walk_acts) {
				if (t >= w.t0) active_walk = w;
			}
			
			if (active_walk) {
				const w = active_walk;
				const dur_per_item = (w.t1 - w.t0) / w.n;
				
				for (let i = 0; i < w.n; i++) {
					const i_t0 = w.t0 + i * dur_per_item;
					const t_reveal = i_t0 + dur_per_item * 0.35;
					
					if (t >= t_reveal) {
						if (w.args.found === i) {
							results[i] = '✓';
						} else {
							results[i] = '✗';
						}
					}
				}
				
				if (t < w.t1 + 0.5) {
					const p_walk = (t - w.t0) / (w.t1 - w.t0);
					const k = Math.min(w.n - 1, Math.max(0, Math.floor(p_walk * w.n)));
					const i_t0 = w.t0 + k * dur_per_item;
					const p_item = api.clamp((t - i_t0) / (dur_per_item * 0.35));
					
					let alpha = 1;
					if (t > w.t1) alpha = api.clamp(1 - (t - w.t1) / 0.3);
					else if (t < w.t0 + 0.15) alpha = api.clamp((t - w.t0) / 0.15);
					
					label = { text: w.args.item, k, p: p_item, alpha };
				}
			}
			
			const size = this.measure(obj, api, acts);
			let labelW = 0;
			for (const a of objActs) {
				if (a.act === 'walk') labelW = Math.max(labelW, api.measure(a.args.item, { size: 34, mono: true }).w + 24);
			}
			const cardX = labelW > 0 ? labelW + 20 : 0;
			const cardW = size.w - cardX;
			
			let y = 0;
			let titleBox = null;
			if (obj.title) {
				const titleW = api.measure(obj.title, { size: 34 }).w;
				titleBox = { x: cardX, y, w: titleW, h: 34 };
				y += 50;
			}
			
			const rowBoxes = [];
			const row_ys = [];
			rows.forEach((r, i) => {
				row_ys.push(y);
				rowBoxes[i] = { x: cardX, y, w: cardW, h: 74 };
				y += 74 + 14;
			});

			return { rows, results, label, t, size, cardX, cardW, titleBox, rowBoxes, row_ys };
		},
		draw(api, obj, st) {
			let y = 0;
			
			if (st.titleBox) {
				api.text(obj.title, st.titleBox.x, st.titleBox.y + 17, { size: 34, color: api.color('text.muted') });
			}
			
			st.rows.forEach((r, i) => {
				const box = st.rowBoxes[i];
				let p_append = 1;
				if (r.t1 > r.t0) {
					p_append = api.clamp((st.t - r.t0) / (r.t1 - r.t0));
				}
				
				if (p_append > 0) {
					api.rect(box.x, box.y, box.w, box.h, p_append, { fill: api.color('card.fill'), role: 'panel' });
					
					const is_muted = (st.results[i] === '✗');
					const col = is_muted ? 'text.muted' : 'text.body';
					
					api.write(r.text, box.x + 28, box.y + 37, p_append, { size: 34, mono: true, color: api.color(col) });
					
					if (st.results[i]) {
						const res = st.results[i];
						const resCol = res === '✓' ? 'text.accent' : 'text.muted';
						api.text(res, box.x + box.w - 35, box.y + 37, { size: 40, color: api.color(resCol), align: 'center' });
					}
				}
			});
			
			if (st.label && st.label.alpha > 0) {
				const k = st.label.k;
				const target_y = st.row_ys[k] + 37;
				let start_y = target_y;
				if (k === 0) {
					start_y = obj.title ? 25 : target_y - 88; 
				} else {
					start_y = st.row_ys[k - 1] + 37;
				}
				
				const ly = api.mix(start_y, target_y, api.ease(st.label.p));
				
				api.ctx.save();
				api.ctx.globalAlpha *= st.label.alpha;
				
				const lw = api.measure(st.label.text, { size: 34, mono: true }).w + 24;
				api.rect(0, ly - 25, lw, 50, 1, { color: api.color('text.accent'), role: null });
				api.text(st.label.text, lw / 2, ly, { size: 34, mono: true, color: api.color('text.accent'), align: 'center' });
				
				api.ctx.restore();
			}
		},
		anchors(obj, st, api) {
			const res = {};
			if (st.titleBox) res.title = st.titleBox;
			if (st.rowBoxes) {
				st.rowBoxes.forEach((b, i) => {
					if (b) res[`r${i}`] = b;
				});
			}
			return res;
		}
	});
})();
