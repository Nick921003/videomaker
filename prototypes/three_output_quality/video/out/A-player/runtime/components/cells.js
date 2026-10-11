'use strict';
(() => {
	const CELL_W = 150, CELL_GAP = 26, CELL_H = CELL_W * 1.09;
	const PTR_H = CELL_W * 0.55;
	const LABEL_H = 50, STOP_H = 50, BRACE_H = 76;
	const ADDR_H = 36, CONSUME_H = 36;
	const TAIL_W = CELL_W * 1.65;

	function cellRect(i) {
		const x = i * (CELL_W + CELL_GAP);
		return {x, w: CELL_W};
	}

	Board.register('cells', {
		measure(obj, api, acts) {
			const count = obj.count || 0;
			let w = count * CELL_W + Math.max(0, count - 1) * CELL_GAP;
			if (obj.tail) w += CELL_GAP + TAIL_W;
			if (obj.label) {
				const labelW = api.measure(obj.label, {size: 36}).w;
				w = Math.max(w, labelW);
			}
			const hasStopNote = acts.some(a => a.act === 'stop' && a.args && a.args.note && a.obj === obj.id);
			const braces = acts.filter(a => a.act === 'brace' && a.obj === obj.id).length;
			let h = LABEL_H + PTR_H + CELL_H;
			if (obj.addrs && obj.addrs.length) h += ADDR_H;
			if (acts.some(a => a.obj === obj.id && a.act === 'consume')) h += CONSUME_H;
			if (hasStopNote) h += STOP_H;
			h += braces * BRACE_H;
			return {w, h};
		},
		state(obj, acts, t, api) {
			const st = {
				values: [...(obj.values || [])],
				pointer: null,
				pointerP: 0,
				stops: [],
				braces: [],
				fills: [],
				scans: [],
				swaps: [],
				consumes: [],
				consumed: {},
				moving: [],
				consumeH: acts.some(a => a.obj === obj.id && a.act === 'consume') ? CONSUME_H : 0
			};
			const count = obj.count || 0;
			for (let i = st.values.length; i < count; i++) st.values.push(null);
			
			for (const a of acts) {
				if (a.t0 > t) continue;
				if (a.obj === obj.id && a.act === 'fill') {
					const per = (a.t1 - a.t0) / a.n;
					const start = a.args.start || 0;
					const chars = a.args.values || a.args.chars || [];
					for (let k = 0; k < a.n; k++) {
						const k_t0 = a.t0 + k * per;
						const k_t1 = k_t0 + per;
						// from 可省略：沒有起點就直接寫進格子，不畫飛行
						if (t >= (a.args.from ? k_t1 : k_t0)) {
							st.values[start + k] = chars[k];
							delete st.consumed[start + k];
						} else if (t >= k_t0) {
							st.fills.push({
								from: a.args.from,
								toIndex: start + k,
								char: chars[k],
								p: (t - k_t0) / per
							});
						}
					}
				} else if (a.obj === obj.id && a.act === 'swap') {
					const i = a.args.a, j = a.args.b;
					if (t >= a.t1) {
						[st.values[i], st.values[j]] = [st.values[j], st.values[i]];
						if (st.values[i] != null) delete st.consumed[i];
						if (st.values[j] != null) delete st.consumed[j];
					} else {
						const p = api.clamp((t - a.t0) / (a.t1 - a.t0));
						const end = api.sceneEnd(a.scene), alpha = 1 - Board.phase(t, end, end + .4);
						[[i, j, 60], [j, i, -60]].forEach(([fromIndex, toIndex, lift]) => {
							if (st.values[fromIndex] == null) return;
							st.moving.push(fromIndex);
							st.swaps.push({fromIndex, toIndex, char: st.values[fromIndex], p, lift, alpha});
						});
					}
				} else if (a.obj === obj.id && a.act === 'consume') {
					// 只取仍有值的格子，空洞和剩餘值都不向左搬。
					const indices = st.values.map((v, i) => v == null ? -1 : i).filter(i => i >= 0).slice(0, a.args.count);
					const per = (a.t1 - a.t0) / indices.length;
					const end = api.sceneEnd(a.scene), alpha = 1 - Board.phase(t, end, end + .4);
					indices.forEach((i, k) => {
						const start = a.t0 + k * per, finish = k === indices.length - 1 ? a.t1 : start + per;
						if (t >= finish) {
							st.values[i] = null;
							st.consumed[i] = {alpha};
						} else if (a.args.to && t >= start) {
							st.moving.push(i);
							st.consumes.push({fromIndex: i, char: st.values[i], to: a.args.to, p: (t - start) / per, alpha});
						}
					});
				}
			}

			let ptrPos = null;
			let firstPtrT = Infinity;
			const ptrActs = acts.filter(a => a.obj === obj.id && ['point', 'scan', 'stop'].includes(a.act));
			for (const a of ptrActs) {
				if (a.t0 < firstPtrT) firstPtrT = a.t0;
			}
			
			if (t >= firstPtrT) {
				let lastIdx = null;
				for (const a of ptrActs) {
					if (a.t0 > t) break;
					if (a.act === 'point' || a.act === 'stop') {
						if (t >= a.t1) {
							lastIdx = a.args.index;
						} else if (t >= a.t0) {
							const p = (t - a.t0) / (a.t1 - a.t0);
							ptrPos = lastIdx !== null ? Board.mix(lastIdx, a.args.index, Board.ease(p)) : a.args.index;
							break;
						}
					} else if (a.act === 'scan') {
						const per = (a.t1 - a.t0) / a.n;
						let handled = false;
						const lo = a.args.range ? a.args.range[0] : (a.args.lo || 0);
						for (let k = 0; k < a.n; k++) {
							const k_t0 = a.t0 + k * per;
							const k_t1 = k_t0 + per;
							const idx = lo + k;
							if (t >= k_t1) {
								lastIdx = idx;
							} else if (t >= k_t0) {
								const localP = (t - k_t0) / per;
								if (localP <= 0.4) {
									const p = localP / 0.4;
									ptrPos = lastIdx !== null ? Board.mix(lastIdx, idx, Board.ease(p)) : idx;
								} else {
									ptrPos = idx;
									st.scans.push({
										char: a.args.chars[k],
										fromIndex: idx,
										to: a.args.to,
										p: (localP - 0.4) / 0.6
									});
								}
								handled = true;
								break;
							}
						}
						if (handled) break;
					}
				}
				if (ptrPos === null) ptrPos = lastIdx;
				st.pointer = ptrPos;
				const lastPtr = ptrActs.filter(a => a.t0 <= t).pop();
				const fadeAt = lastPtr ? api.sceneEnd(lastPtr.scene) : Infinity;
				st.pointerP = Board.phase(t, firstPtrT, firstPtrT + 0.3);
				st.pointerAlpha = 1 - Board.phase(t, fadeAt, fadeAt + 0.4);
			}

			for (const a of acts) {
				if (a.obj === obj.id && a.act === 'stop' && t >= a.t0) {
					const end = api.sceneEnd(a.scene);
					if (t < end + 0.4) st.stops.push({
						index: a.args.index,
						note: a.args.note,
						p: Board.phase(t, a.t0, a.t1),
						alpha: 1 - Board.phase(t, end, end + 0.4)
					});
				}
			}

			let braceIdx = 0;
			for (const a of acts) {
				if (a.obj === obj.id && a.act === 'brace' && t >= a.t0) {
					st.braces.push({
						lo: a.args.range ? a.args.range[0] : a.args.lo,
						hi: a.args.range ? a.args.range[1] : a.args.hi,
						label: a.args.label,
						p: Board.phase(t, a.t0, a.t1),
						row: braceIdx++
					});
				}
			}
			
			st.hasStopNote = acts.some(a => a.act === 'stop' && a.args && a.args.note && a.obj === obj.id);

			return st;
		},
		draw(api, obj, st, t) {
			const accentColor = api.color('text.accent');
			let y = 0;
			
			if (obj.label) {
				api.text(obj.label, 0, y + LABEL_H / 2, {size: 36, color: api.color('text.muted'), role: 'label'});
			}
			y += LABEL_H;
			
			const pointerY = y;
			y += PTR_H;
			y += st.consumeH;
			const cellY = y;
			
			if (st.pointer !== null && st.pointerAlpha > 0.004) {
				const px = cellRect(st.pointer).x + CELL_W / 2;
				// 尺寸照 A＋C：指標以格寬為基準
				api.ctx.save(); api.ctx.globalAlpha *= st.pointerAlpha;
				api.pointer(px, pointerY + PTR_H * .42, CELL_W, st.pointerP);
				api.ctx.restore();
			}

			const count = obj.count || 0;
			const accentSet = new Set(obj.accent || []);
			for (let i = 0; i < count; i++) {
				const rect = cellRect(i);
				const cx = rect.x + CELL_W / 2;
				
				const val = st.values[i];
				if (val !== null && val !== undefined) {
					api.rect(rect.x, cellY, CELL_W, CELL_H, 1, {fill: api.color('card.fill'), role: 'panel'});
					const color = accentSet.has(val) ? accentColor : api.color('text.body');
					if (!st.moving.includes(i)) api.text(val, cx, cellY + CELL_H / 2, {size: 64, weight: 600, mono: true, align: 'center', color});
				} else {
					api.hatch(rect.x, cellY, CELL_W, CELL_H, Board.seed(`${obj.id}_${i}`));
					api.rect(rect.x, cellY, CELL_W, CELL_H, 1, {role: 'panel'});
				}
				const consumed = st.consumed[i];
				if (consumed && consumed.alpha > .004) api.text('已讀走', cx, cellY - CONSUME_H / 2, {size: 24, color: api.color('text.muted'), align: 'center', alpha: consumed.alpha});
				
				for (const stop of st.stops) {
					if (stop.index === i) {
						api.ctx.save(); api.ctx.globalAlpha *= stop.alpha;
						api.ellipse(cx, cellY + CELL_H / 2, CELL_W / 2 + 8, CELL_H / 2 + 8, stop.p);
						api.ctx.restore();
					}
				}
			}
			
			if (obj.tail) {
				const lastRect = cellRect(count - 1);
				const startX = lastRect.x + CELL_W;
				const connY = cellY + CELL_H / 2;
				api.ink([[startX, connY], [startX + CELL_GAP, connY]], 1, {width: 2});
				const tailX = startX + CELL_GAP;
				// 未知區用淡色框，跟已知格的實心卡片區分開
				api.rect(tailX, cellY, TAIL_W, CELL_H, 1, {color: api.color('canvas.grid'), role: 'panel'});
				// 跟 A＋C 一樣：「…」在上，說明小字在下
				api.text('…', tailX + TAIL_W / 2, cellY + CELL_H * .38, {size: 64, color: api.color('text.muted'), align: 'center'});
				api.text(obj.tail, tailX + TAIL_W / 2, cellY + CELL_H * .76, {size: 28, color: api.color('text.muted'), align: 'center'});
			}

			y += CELL_H;
			if (obj.addrs && obj.addrs.length) {
				obj.addrs.slice(0, count).forEach((addr, i) => {
					api.text(addr, cellRect(i).x + CELL_W / 2, y + ADDR_H / 2, {size: 24, mono: true, color: api.color('text.muted'), align: 'center'});
				});
				y += ADDR_H;
			}
			
			if (st.hasStopNote) {
				for (const stop of st.stops) {
					if (stop.note) {
						const cx = cellRect(stop.index).x + CELL_W / 2;
						api.write(stop.note, cx, y + STOP_H / 2, stop.p, {size: 40, color: accentColor, align: 'center', alpha: stop.alpha});
					}
				}
				y += STOP_H;
			}
			
			for (const b of st.braces) {
				const rx0 = cellRect(b.lo).x;
				const rx1 = cellRect(b.hi).x + CELL_W;
				const by = y + 20;
				const isFirst = b.row === 0;
				api.ink([[rx0, by], [rx1, by]], b.p, {color: isFirst ? accentColor : api.color('effects.pencil'), width: 4});
				if (b.label) {
					api.write(b.label, (rx0 + rx1) / 2, by + 36, b.p, {size: 34, color: isFirst ? accentColor : api.color('text.muted'), align: 'center'});
				}
				y += BRACE_H;
			}
		},
		anchors(obj, st, api) {
			const res = {};
			if (obj.label) {
				res.label = {x: 0, y: 0, w: api.measure(obj.label, {size: 36}).w, h: LABEL_H};
			}
			const y = LABEL_H + PTR_H + st.consumeH;
			const count = obj.count || 0;
			for (let i = 0; i < count; i++) {
				const rx = cellRect(i).x;
				res[`i${i}`] = {x: rx, y, w: CELL_W, h: CELL_H};
			}
			return res;
		},
		overlay(api, obj, st, t, world) {
			const accentColor = api.color('text.accent');
			for (const f of st.fills) {
				const from = world.anchor(f.from);
				if (!from) continue;
				const cell = this.anchors(obj, st, api)[`i${f.toIndex}`];
				const myPl = world.placement(obj.id);
				const to = {x: myPl.x + (cell.x + cell.w / 2) * myPl.s, y: myPl.y + (cell.y + cell.h / 2) * myPl.s};
				// overlay 在世界座標，字級要乘上版面縮放，落地時才不會跳一下
				api.fly(f.char, {x: from.x + from.w / 2, y: from.y + from.h / 2}, to, f.p, {size: 64 * myPl.s, weight: 600, lift: 60 * myPl.s, color: api.color('text.body')});
			}
			for (const s of st.scans) {
				const to = world.anchor(s.to);
				if (!to) continue;
				const cell = this.anchors(obj, st, api)[`i${s.fromIndex}`];
				const myPl = world.placement(obj.id);
				const from = {x: myPl.x + (cell.x + cell.w / 2) * myPl.s, y: myPl.y + (cell.y + cell.h / 2) * myPl.s};
				api.fly(s.char, from, {x: to.x + to.w / 2, y: to.y + to.h / 2}, s.p, {size: Board.mix(64, 80, s.p) * myPl.s, weight: 600, lift: 60 * myPl.s, color: accentColor});
			}
			const pl = world.placement(obj.id);
			if (!pl) return;
			const cells = this.anchors(obj, st, api);
			const center = r => ({x: pl.x + (r.x + r.w / 2) * pl.s, y: pl.y + (r.y + r.h / 2) * pl.s});
			for (const f of [...st.swaps, ...st.consumes]) {
				const target = f.to ? world.anchor(f.to) : cells[`i${f.toIndex}`];
				if (!target || f.alpha <= .004) continue;
				const to = f.to ? {x: target.x + target.w / 2, y: target.y + target.h / 2} : center(target);
				api.ctx.save(); api.ctx.globalAlpha *= f.alpha;
				api.fly(f.char, center(cells[`i${f.fromIndex}`]), to, f.p, {size: 64 * pl.s, weight: 600, lift: (f.lift ?? 60) * pl.s, color: f.to ? accentColor : api.color('text.body')});
				api.ctx.restore();
			}
		}
	});
})();
