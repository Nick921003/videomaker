'use strict';
(() => {
	function build(s_acts, t0) {
		const lines = [];
		let current_prompt = {kind: 'prompt', text: '', t0, type: null};
		lines.push(current_prompt);
		for (const a of s_acts) {
			if (a.act === 'restart') break;
			if (a.act === 'type') {
				if (!current_prompt) {
					current_prompt = {kind: 'prompt', text: '', t0: a.t0, type: null};
					lines.push(current_prompt);
				}
				current_prompt.type = a;
			} else if (a.act === 'print') {
				a.args.lines.forEach((l, i) => {
					lines.push({kind: 'print', text: l, style: a.args.style, t0: a.t0 + i * (a.t1 - a.t0) / a.n});
				});
				current_prompt = {kind: 'prompt', text: '', t0: a.t1, type: null};
				lines.push(current_prompt);
			} else if (a.act === 'input') {
				// print 留的空 prompt 不屬於程式輸入，游標接回最後的輸出行。
				if (current_prompt && !current_prompt.type && lines[lines.length - 1] === current_prompt) lines.pop();
				let line = lines[lines.length - 1];
				if (!line || line.kind === 'prompt') {
					line = {kind: 'print', text: '', t0: a.t0};
					lines.push(line);
				}
				if (!line.inputs) line.inputs = [];
				line.inputs.push(a);
				current_prompt = null;
			}
		}
		return lines;
	}

	Board.register('terminal', {
		measure(obj, api, acts) {
			const prompt = (obj.prompt || 'C:\\>') + ' ';
			const oNormal = { size: 34, mono: true };
			let maxW = 0, maxLines = 1;
			maxW = Math.max(maxW, api.measure(prompt, oNormal).w);

			const objActs = (acts || []).filter(a => a.obj === obj.id);
			let session = [];
			for (const a of objActs) {
				if (a.act === 'restart') {
					if (a.args.note) maxW = Math.max(maxW, api.measure(a.args.note, oNormal).w);
					session = [];
					continue;
				}
				session.push(a);
				const lines = build(session, 0);
				maxLines = Math.max(maxLines, lines.length);
				for (const l of lines) {
					const text = l.kind === 'prompt' ? prompt + (l.type ? l.type.args.text : '') : l.text + (l.inputs || []).map(a => a.args.text).join('');
					maxW = Math.max(maxW, api.measure(text, oNormal).w);
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

			const lines = is_restart_fade ? build(prev_acts, prev_start) : build(session_acts, s_start);
			
			const size = this.measure(obj, api, acts);
			let y = 56 + 36 + 25; 
			const lineBoxes = []; 
			let cmdAnchor = null;
			
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
					l.inputText = '';
					l.typing = false;
					l.inputCursor = false;
					for (const a of l.inputs || []) {
						if (t < a.t0) continue;
						const chars = Array.from(a.args.text);
						const wait = Math.min(.6, .3 * (a.t1 - a.t0)), start = a.t0 + wait;
						const p = t >= a.t1 ? 1 : api.clamp((t - start) / (a.t1 - start));
						l.inputText += chars.slice(0, Math.floor(p * chars.length)).join('');
						l.typing = t >= start && t < a.t1;
						l.inputCursor = true;
					}
					l.textW = api.measure(l.text + l.inputText, {size: 34, mono: true}).w;
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
					if (l.style === 'error' && l.inputText) {
						const printW = api.measure(l.text, {size: 34, mono: true}).w;
						api.text(l.text, 36, y, {size: 34, color: api.color(col), mono: true, alpha});
						api.text(l.inputText, 36 + printW, y, {size: 34, color: api.color('code.normal'), mono: true, alpha});
					} else {
						api.text(l.text + l.inputText, 36, y, {size: 34, color: api.color(col), mono: true, alpha});
					}
					if (l.inputCursor && i === st.lines.length - 1 && (l.typing || Math.floor(st.t * 2) % 2 === 0)) {
						api.ctx.fillStyle = api.color('code.normal');
						api.ctx.fillRect(36 + l.textW + 2, y - 17, 18, 34);
					}
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
