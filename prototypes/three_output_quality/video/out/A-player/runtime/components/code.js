'use strict';
(() => {
	const PAD = 56;
	const LINE_H = 63;
	const CAPTION_H = 60, FOOTER_H = 60;
	const GUTTER_W = 42;
	const gutter = obj => obj.diff ? GUTTER_W : 0;
	const lineY = obj => PAD + (obj.caption ? CAPTION_H : 0);

	function anchors(obj, api, size) {
		const res = {}, y = lineY(obj), x = PAD + gutter(obj), font = {size: 42, mono: true};
		const lines = obj.lines || [];
		lines.forEach((line, i) => {
			res[`L${i + 1}`] = {x: 0, y: y + i * LINE_H, w: size.w, h: LINE_H};
		});
		for (const mark of obj.marks || []) {
			const line = lines[mark.line - 1];
			if (line === undefined) continue;
			const index = line.indexOf(mark.text);
			if (index < 0) continue;
			res[mark.id] = {x: x + api.measure(line.slice(0, index), font).w,
				y: y + (mark.line - 1) * LINE_H + LINE_H / 2 - 42 * .62,
				w: api.measure(mark.text, font).w, h: 42 * 1.24};
		}
		return res;
	}

	Board.register('code', {
		measure(obj, api) {
			let maxW = 0;
			const lines = obj.lines || [];
			for (const l of lines) maxW = Math.max(maxW, gutter(obj) + api.measure(l, {size: 42, mono: true}).w);
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
		state(obj, acts, t, api) {
			const highlights = {};
			for (const a of acts) {
				if (a.obj === obj.id && a.act === 'highlight' && t >= a.t0) {
					const line = a.args.line;
					const p = Board.phase(t, a.t0, a.t1);
					highlights[line] = Math.max(highlights[line] || 0, p);
				}
			}
			const size = this.measure(obj, api);
			return {highlights, size, anchors: anchors(obj, api, size)};
		},
		draw(api, obj, st) {
			const m = st.size;
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
				const added = obj.diff && (obj.diff.add || []).includes(lineNum);
				const deleted = obj.diff && (obj.diff.del || []).includes(lineNum);
				if (added) {
					api.ctx.save();
					api.ctx.fillStyle = api.color('effects.highlight');
					api.ctx.globalAlpha *= .18;
					api.ctx.fillRect(0, ly, m.w, LINE_H);
					api.ctx.restore();
				}
				
				const hl = st.highlights[lineNum] || 0;
				if (hl > 0) {
					api.ctx.save();
					api.ctx.fillStyle = api.color('code.highlight');
					api.ctx.globalAlpha *= hl;
					api.ctx.fillRect(0, ly, m.w, LINE_H);
					api.ctx.restore();
				}
				
				if (added || deleted) api.text(deleted ? '−' : '+', PAD, ly + LINE_H / 2, {size: 42, mono: true, color: api.color(deleted ? 'code.muted' : 'code.normal')});
				const textX = PAD + gutter(obj);
				const textW = api.text(lines[i], textX, ly + LINE_H / 2, {size: 42, mono: true, color: api.color(deleted ? 'code.muted' : 'code.normal')});
				if (deleted) api.ink([[textX, ly + LINE_H / 2], [textX + textW, ly + LINE_H / 2]], 1, {color: api.color('code.muted'), width: 2, seed: Board.seed(`${obj.id}:del${lineNum}`)});
			}
			y += lines.length * LINE_H;
			
			if (obj.footer) {
				y += 10;
				api.text(obj.footer, PAD, y + 18, {size: 36, color: api.color('code.muted')});
			}
		},
		anchors(obj, st) { return st.anchors; }
	});
})();
