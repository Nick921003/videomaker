'use strict';
(() => {
	const PAD = 56;
	const LINE_H = 63;
	const CAPTION_H = 60, FOOTER_H = 60;

	Board.register('code', {
		measure(obj, api) {
			let maxW = 0;
			const lines = obj.lines || [];
			for (const l of lines) maxW = Math.max(maxW, api.measure(l, {size: 42, mono: true}).w);
			if (obj.caption) maxW = Math.max(maxW, api.measure(obj.caption, {size: 36}).w);
			if (obj.footer) maxW = Math.max(maxW, api.measure(obj.footer, {size: 36}).w);
			const w = maxW + PAD * 2;
			
			let h = PAD;
			if (obj.caption) h += CAPTION_H;
			h += lines.length * LINE_H;
			if (obj.footer) h += FOOTER_H;
			h += PAD - 20;
			return {w, h};
		},
		state(obj, acts, t) {
			const highlights = {};
			for (const a of acts) {
				if (a.obj === obj.id && a.act === 'highlight' && t >= a.t0) {
					const line = a.args.line;
					const p = Board.phase(t, a.t0, a.t1);
					highlights[line] = Math.max(highlights[line] || 0, p);
				}
			}
			return {highlights};
		},
		draw(api, obj, st) {
			const m = this.measure(obj, api);
			api.rect(0, 0, m.w, m.h, 1, {fill: api.color('code.bg'), color: api.color('code.bg'), role: 'panel'});
			
			let y = PAD;
			if (obj.caption) {
				api.text(obj.caption, PAD, y + 18, {size: 36, color: api.color('code.muted')});
				y += CAPTION_H;
			}
			
			const lines = obj.lines || [];
			for (let i = 0; i < lines.length; i++) {
				const lineNum = i + 1;
				const ly = y + i * LINE_H;
				
				const hl = st.highlights[lineNum] || 0;
				if (hl > 0) {
					api.ctx.save();
					api.ctx.fillStyle = api.color('code.highlight');
					api.ctx.globalAlpha *= hl;
					api.ctx.fillRect(0, ly, m.w, LINE_H);
					api.ctx.restore();
				}
				
				api.text(lines[i], PAD, ly + LINE_H / 2, {size: 42, mono: true, color: api.color('code.normal')});
			}
			y += lines.length * LINE_H;
			
			if (obj.footer) {
				y += 10;
				api.text(obj.footer, PAD, y + 18, {size: 36, color: api.color('code.muted')});
			}
		},
		anchors(obj, st, api) {
			const m = this.measure(obj, api);
			const res = {};
			let y = PAD;
			if (obj.caption) y += CAPTION_H;
			const lines = obj.lines || [];
			for (let i = 0; i < lines.length; i++) {
				const lineNum = i + 1;
				res[`L${lineNum}`] = {x: 0, y: y + i * LINE_H, w: m.w, h: LINE_H};
			}
			return res;
		}
	});
})();
