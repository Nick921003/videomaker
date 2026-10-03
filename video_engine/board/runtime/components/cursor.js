'use strict';
(() => {
	Board.register('cursor', {
		measure(obj, api, acts) { return {w: 0, h: 0}; },
		state(obj, acts, t, api) {
			const objActs = (acts || []).filter(a => a.obj === obj.id);
			let pos = null;
			let ripple = null;
			
			let firstT0 = Infinity;
			let firstTarget = null;
			for (const a of objActs) {
				if (a.t0 < firstT0) {
					firstT0 = a.t0;
					firstTarget = a.args.on || a.args.to;
				}
			}
			
			let lastTarget = null;
			for (const a of objActs) {
				if (t >= a.t0) {
					if (t >= a.t1) {
						lastTarget = a.args.on || a.args.to;
						pos = lastTarget;
					} else {
						const p = (t - a.t0) / (a.t1 - a.t0);
						const prev = lastTarget;
						if (a.act === 'click') {
							if (p < 0.65) {
								pos = { prev, next: a.args.on, p: p / 0.65 };
							} else {
								pos = a.args.on;
								ripple = { p: (p - 0.65) / 0.35 };
							}
						} else if (a.act === 'move') {
							pos = { prev, next: a.args.to, p };
						}
						break;
					}
				}
			}
			
			return { pos, ripple, firstT0, firstTarget, t };
		},
		draw(api, obj, st) {},
		anchors(obj, st, api) { return {}; },
		overlay(api, obj, st, t, world) {
			let x = 0, y = 0;
			let alpha = 1;

			function getCenter(id) {
				const a = world.anchor(id);
				if (a) return { x: a.x + a.w / 2, y: a.y + a.h / 2 };
				return { x: 0, y: 0 };
			}
			
			if (st.pos === null) {
				if (st.firstTarget) {
					const c = getCenter(st.firstTarget);
					const dt = st.firstT0 - t;
					if (dt > 0.5) alpha = 0;
					else if (dt < 0) {
						x = c.x + 140; y = c.y + 90;
					} else {
						alpha = 1 - dt / 0.5;
						const p = Board.ease(alpha);
						x = c.x + 140;
						y = c.y + 90;
						// Wait, it says "第一個動作開始前，游標從目標右下方（+140, +90）移入。"
						// So at dt=0.5 it's far away? Or does it just fade in AT +140, +90?
						// "移入" usually implies moving in from outside.
						// Let's just slide it from +140+30, +90+30 to +140, +90
						x += 40 * (1 - p);
						y += 40 * (1 - p);
					}
				} else {
					alpha = 0;
				}
			} else if (typeof st.pos === 'string') {
				const c = getCenter(st.pos);
				x = c.x; y = c.y;
			} else {
				const p1 = st.pos.prev ? getCenter(st.pos.prev) : {x:0, y:0};
				const p2 = getCenter(st.pos.next);
				if (!st.pos.prev && st.firstTarget) {
					const c = getCenter(st.firstTarget);
					p1.x = c.x + 140;
					p1.y = c.y + 90;
				}
				const p = Board.ease(st.pos.p);
				x = p1.x + (p2.x - p1.x) * p;
				y = p1.y + (p2.y - p1.y) * p;
			}

			if (alpha > 0.004) {
				api.ctx.save();
				api.ctx.globalAlpha *= alpha;
				
				if (st.ripple) {
					const r = 8 + 26 * st.ripple.p;
					const rAlpha = 1 - st.ripple.p;
					if (rAlpha > 0.004) {
						api.ctx.save();
						api.ctx.globalAlpha *= rAlpha;
						api.ctx.beginPath();
						api.ctx.arc(x, y, r, 0, Math.PI * 2);
						api.ctx.fillStyle = api.color('text.accent');
						api.ctx.fill();
						api.ctx.restore();
					}
				}

				api.ctx.translate(x, y);
				api.ctx.beginPath();
				const pts = [
					[0, 0], [16, 46], [23, 30], [38, 46], [47, 38], [31, 22], [48, 16], [0, 0]
				];
				api.ctx.moveTo(pts[0][0], pts[0][1]);
				for (let i = 1; i < pts.length; i++) api.ctx.lineTo(pts[i][0], pts[i][1]);
				api.ctx.closePath();
				
				api.ctx.fillStyle = api.color('card.fill');
				api.ctx.fill();
				api.ctx.strokeStyle = api.color('effects.pencil');
				api.ctx.lineWidth = 2.5;
				api.ctx.stroke();
				
				api.ctx.restore();
			}
		}
	});
})();
