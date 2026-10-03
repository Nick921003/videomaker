'use strict';
(() => {
	Board.register('terminal', {
		measure(obj, api, acts) {
			const prompt = (obj.prompt || 'C:\\>') + ' ';
			const oNormal = { size: 34, mono: true };
			let maxW = 0, maxLines = 1;
			let currentLines = 1;
			maxW = Math.max(maxW, api.measure(prompt, oNormal).w);

			const objActs = (acts || []).filter(a => a.obj === obj.id);
			for (const a of objActs) {
				if (a.act === 'type') {
					maxW = Math.max(maxW, api.measure(prompt + a.args.text, oNormal).w);
				} else if (a.act === 'print') {
					for (const l of a.args.lines) {
						maxW = Math.max(maxW, api.measure(l, oNormal).w);
					}
					currentLines += a.args.lines.length + 1;
					maxLines = Math.max(maxLines, currentLines);
				} else if (a.act === 'restart') {
					if (a.args.note) maxW = Math.max(maxW, api.measure(a.args.note, oNormal).w);
					currentLines = 1;
				}
			}
			const w = Math.max(760, maxW + 36 * 2);
			const h = 56 + maxLines * 50 + 36 * 2;
			return { w, h };
		},
		state(obj, acts, t, api) {
			const objActs = (acts || []).filter(a => a.obj === obj.id);
			const pText = (obj.prompt || 'C:\\>') + ' ';
			let session_acts = [], prev_acts = [];
			let s_start = 0, prev_start = 0;
			let restart_act = null;

			for (const a of objActs) {
				if (a.act === 'restart' && a.t0 <= t) {
					prev_acts = session_acts;
					prev_start = s_start;
					restart_act = a;
					s_start = a.t0 + (a.t1 - a.t0) * 0.7;
					session_acts = [];
				} else if (a.t0 <= t || a.act === 'restart') {
					session_acts.push(a);
				}
			}

			let opacity = 1;
			let note = null;
			let is_restart_fade = false;

			if (restart_act && t < restart_act.t1) {
				const p = api.clamp((t - restart_act.t0) / (restart_act.t1 - restart_act.t0));
				if (p < 0.4) {
					opacity = 1 - p / 0.4;
					is_restart_fade = true;
				} else if (p < 0.7) {
					opacity = 1;
					note = restart_act.args.note;
				} else {
					opacity = (p - 0.7) / 0.3;
				}
			}

			function build(s_acts, t0) {
				const lines = [];
				let current_prompt = { kind: 'prompt', text: '', t0, type: null };
				lines.push(current_prompt);
				for (const a of s_acts) {
					if (a.act === 'restart') break;
					if (a.act === 'type') {
						current_prompt.type = a;
					} else if (a.act === 'print') {
						a.args.lines.forEach((l, i) => {
							lines.push({
								kind: 'print', text: l, style: a.args.style,
								t0: a.t0 + i * (a.t1 - a.t0) / a.n
							});
						});
						current_prompt = { kind: 'prompt', text: '', t0: a.t1, type: null };
						lines.push(current_prompt);
					}
				}
				return lines;
			}

			const lines = is_restart_fade ? build(prev_acts, prev_start) : build(session_acts, s_start);
			
			const size = this.measure(obj, api, acts);
			let y = 56 + 36 + 25; 
			const lineBoxes = []; 
			let cmdAnchor = null;
			
			// Compute anchors data during state
			lines.forEach((l, i) => {
				if (t < l.t0) return;
				
				if (l.kind === 'prompt') {
					let typeText = "";
					let typing = false;
					if (l.type) {
						const a = l.type;
						if (t >= a.t0) {
							if (t >= a.t1) {
								typeText = a.args.text;
							} else {
								const p = (t - a.t0) / (a.t1 - a.t0);
								const n = Math.floor(p * a.n);
								typeText = a.args.text.slice(0, n);
								typing = true;
							}
						}
					}
					
					l.typeText = typeText;
					l.typing = typing;
					
					const promptW = api.measure(pText, { size: 34, mono: true }).w;
					const textW = api.measure(typeText, { size: 34, mono: true }).w;
					
					l.promptW = promptW;
					l.textW = textW;
					
					lineBoxes[i] = { y: y - 25, h: 50 };
					if (l.type) {
						cmdAnchor = { x: 36 + promptW, y: y - 25, w: textW, h: 50 };
					} else {
						cmdAnchor = { x: 36 + promptW + textW, y: y - 25, w: 0, h: 50 };
					}
				} else if (l.kind === 'print') {
					lineBoxes[i] = { y: y - 25, h: 50 };
				}
				y += 50;
			});
			
			if (!cmdAnchor) {
				const w = api.measure(pText, { size: 34, mono: true }).w;
				cmdAnchor = { x: 36 + w, y: 56 + 36, w: 0, h: 50 };
			}
			
			return { lines, opacity, note, pText, t, size, lineBoxes, cmdAnchor };
		},
		draw(api, obj, st) {
			const size = st.size;
			api.rect(0, 0, size.w, size.h, 1, { fill: api.color('code.bg'), color: api.color('code.bg'), role: 'panel' });
			api.text(obj.title || '終端機', size.w / 2, 28, { size: 30, color: api.color('code.muted'), align: 'center', role: 'text' });
			
			api.ctx.save();
			api.ctx.beginPath();
			api.ctx.rect(0, 56, size.w, size.h - 56);
			api.ctx.clip();
			
			if (st.note) {
				api.text(st.note, size.w / 2, 56 + (size.h - 56) / 2, { size: 34, color: api.color('code.muted'), align: 'center', mono: true });
			}
			
			api.ctx.globalAlpha *= st.opacity;
			
			let y = 56 + 36 + 25; 
			
			st.lines.forEach((l, i) => {
				if (st.t < l.t0) return;
				
				if (l.kind === 'prompt') {
					api.text(st.pText, 36, y, { size: 34, color: api.color('code.muted'), mono: true });
					api.text(l.typeText, 36 + l.promptW, y, { size: 34, color: api.color('code.normal'), mono: true });
					
					const is_last = (i === st.lines.length - 1);
					if (is_last) {
						const blink = Math.floor(st.t * 2) % 2 === 0;
						if (l.typing || blink) {
							api.ctx.fillStyle = api.color('code.normal');
							api.ctx.fillRect(36 + l.promptW + l.textW + 2, y - 17, 18, 34);
						}
					}
				} else if (l.kind === 'print') {
					const alpha = api.clamp((st.t - l.t0) / 0.15);
					const col = l.style === 'error' ? 'code.error' : 'code.normal';
					api.text(l.text, 36, y, { size: 34, color: api.color(col), mono: true, alpha });
				}
				y += 50;
			});
			
			api.ctx.restore();
		},
		anchors(obj, st, api) {
			const result = {};
			if (st.cmdAnchor) {
				result.cmd = { ...st.cmdAnchor };
			}
			
			if (st.lineBoxes) {
				st.lineBoxes.forEach((b, i) => {
					if (b) {
						result[`line${i}`] = { x: 0, y: b.y, w: st.size.w, h: b.h };
					}
				});
			}
			return result;
		}
	});
})();