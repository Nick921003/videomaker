'use strict';
(() => {
	Board.register('window', {
		measure(obj, api, acts) {
			const typedTexts = {};
			for (const a of acts) {
				if (a.act === 'input' && a.target && a.target.startsWith(obj.id + ':')) {
					typedTexts[a.target.split(':')[1]] = a.args.text;
				}
			}
			
			const getW = (str, size, mono=false) => api.measure(str || "", {size, mono}).w;
			let bodyW = 0, bodyH = 0;
			
			function measureBlock(b) {
				let w = 0, h = 0;
				if (b.field) {
					w = getW(typedTexts[b.field.id] || "", 26, true) + 20;
					h = 64;
				} else if (b.list) {
					let maxRowW = 0;
					for (const r of b.list.rows) {
						const text = typedTexts[r.id] !== undefined ? typedTexts[r.id] : r.text;
						maxRowW = Math.max(maxRowW, getW(text, 26, true) + 20);
					}
					const nRows = Math.max(b.list.rows.length, b.list.min_rows || 0);
					h = nRows * 52;
					let sideW = 0;
					if (b.list.side) {
						let maxBtnW = 0, sideH = 0;
						for (const group of b.list.side) {
							for (const btn of group) {
								maxBtnW = Math.max(maxBtnW, getW(btn.text, 26) + 52);
								sideH += 52 + 8;
							}
							sideH += 18;
						}
						sideH -= 26;
						sideW = maxBtnW + 20;
						h = Math.max(h, sideH);
					}
					w = maxRowW + sideW + 20;
				} else if (b.table) {
					let colsW = b.table.columns.map(c => getW(c, 24) + 20);
					for (const r of b.table.rows) {
						r.cells.forEach((c, i) => { colsW[i] = Math.max(colsW[i], getW(c, 26) + 20); });
					}
					w = colsW.reduce((a, x) => a + x, 0);
					h = 30 + b.table.rows.length * 46;
				} else if (b.buttons) {
					w = b.buttons.items.reduce((a, btn) => a + getW(btn.text, 26) + 52 + 10, 0) - 10;
					h = 52;
				} else if (b.group) {
					w = getW(b.group.title, 26) + 20;
					let innerW = 0, innerH = 0;
					for (const cb of b.group.body) {
						const cData = measureBlock(cb);
						innerW = Math.max(innerW, cData.w);
						innerH += cData.h + 18;
					}
					if (b.group.body.length > 0) innerH -= 18;
					w = Math.max(w, innerW) + 40;
					h = 30 + innerH + 20;
				}
				return {w, h};
			}

			if (obj.body) {
				for (const b of obj.body) {
					const cData = measureBlock(b);
					bodyW = Math.max(bodyW, cData.w);
					bodyH += cData.h + 18;
				}
				if (obj.body.length > 0) bodyH -= 18;
			}

			let maxW = bodyW;
			if (obj.title) maxW = Math.max(maxW, getW(obj.title, 32) + 60);
			if (obj.tabs) maxW = Math.max(maxW, obj.tabs.reduce((a, t) => a + getW(t.text, 26) + 30 + 10, 0) - 10);
			if (obj.footer) maxW = Math.max(maxW, obj.footer.reduce((a, b) => a + getW(b.text, 26) + 52 + 10, 0) - 10);

			let winW = maxW + 56;
			let winH = 56 + bodyH;
			if (obj.title) winH += 60;
			if (obj.tabs) winH += 50;
			if (obj.footer) winH += 52 + 20;

			return { w: winW, h: winH };
		},
		state(obj, acts, t, api) {
			const typedTexts = {};
			for (const a of acts) {
				if (a.act === 'input' && a.target && a.target.startsWith(obj.id + ':')) {
					typedTexts[a.target.split(':')[1]] = a.args.text;
				}
			}
			
			const getW = (str, size, mono=false) => api.measure(str || "", {size, mono}).w;
			const layout = {};
			const blocksData = [];
			
			function measureBlock(b) {
				let w = 0, h = 0, data = {};
				if (b.field) {
					w = getW(typedTexts[b.field.id] || "", 26, true) + 20;
					h = 64;
				} else if (b.list) {
					let maxRowW = 0;
					for (const r of b.list.rows) {
						const text = typedTexts[r.id] !== undefined ? typedTexts[r.id] : r.text;
						maxRowW = Math.max(maxRowW, getW(text, 26, true) + 30);
					}
					const nRows = Math.max(b.list.rows.length, b.list.min_rows || 0);
					data.rowW = maxRowW;
					h = nRows * 52;
					let sideW = 0;
					if (b.list.side) {
						let maxBtnW = 0, sideH = 0;
						for (const group of b.list.side) {
							for (const btn of group) {
								maxBtnW = Math.max(maxBtnW, getW(btn.text, 26) + 52);
								sideH += 52 + 8;
							}
							sideH += 18;
						}
						sideH -= 26;
						data.sideW = maxBtnW;
						sideW = maxBtnW + 20;
						h = Math.max(h, sideH);
					}
					w = maxRowW + sideW + 20;
				} else if (b.table) {
					let colsW = b.table.columns.map(c => getW(c, 24) + 20);
					for (const r of b.table.rows) {
						r.cells.forEach((c, i) => { colsW[i] = Math.max(colsW[i], getW(c, 26) + 20); });
					}
					data.colsW = colsW;
					w = colsW.reduce((a, x) => a + x, 0);
					h = 30 + b.table.rows.length * 46;
				} else if (b.buttons) {
					data.btnW = b.buttons.items.map(btn => getW(btn.text, 26) + 52);
					w = data.btnW.reduce((a, x) => a + x + 10, 0) - 10;
					h = 52;
				} else if (b.group) {
					w = getW(b.group.title, 26) + 20;
					let innerW = 0, innerH = 0;
					data.children = [];
					for (const cb of b.group.body) {
						const cData = measureBlock(cb);
						data.children.push(cData);
						innerW = Math.max(innerW, cData.w);
						innerH += cData.h + 18;
					}
					if (b.group.body.length > 0) innerH -= 18;
					w = Math.max(w, innerW) + 40;
					h = 30 + innerH + 20;
				}
				data.w = w; data.h = h;
				return data;
			}
			
			let bodyW = 0, bodyH = 0;
			if (obj.body) {
				for (const b of obj.body) {
					const cData = measureBlock(b);
					blocksData.push(cData);
					bodyW = Math.max(bodyW, cData.w);
					bodyH += cData.h + 18;
				}
				if (obj.body.length > 0) bodyH -= 18;
			}

			let maxW = bodyW;
			if (obj.title) maxW = Math.max(maxW, getW(obj.title, 32) + 60);
			let tabsData = [];
			if (obj.tabs) {
				let tabsW = 0;
				for (const tb of obj.tabs) {
					const tw = getW(tb.text, 26) + 30;
					tabsData.push(tw);
					tabsW += tw + 10;
				}
				maxW = Math.max(maxW, tabsW - 10);
			}
			let footerData = [];
			if (obj.footer) {
				let fw = 0;
				for (const b of obj.footer) {
					const bw = getW(b.text, 26) + 52;
					footerData.push(bw);
					fw += bw + 10;
				}
				maxW = Math.max(maxW, fw - 10);
			}

			const winW = maxW + 56;
			let winH = 56 + bodyH;
			if (obj.title) winH += 60;
			if (obj.tabs) winH += 50;
			if (obj.footer) winH += 52 + 20;
			
			let cy = 28;
			if (obj.title) cy += 60;
			if (obj.tabs) {
				let tx = 28;
				obj.tabs.forEach((tb, i) => {
					layout[tb.id] = {x: tx, y: cy, w: tabsData[i], h: 40};
					tx += tabsData[i] + 10;
				});
				cy += 50;
			}
			
			function placeBlock(b, bData, x, y, availW) {
				const out = {x, y, w: availW, h: bData.h, data: bData, block: b, children: []};
				if (b.field) {
					layout[b.field.id] = out;
				} else if (b.list) {
					let ry = y;
					b.list.rows.forEach(r => {
						layout[r.id] = {x, y: ry, w: availW - (bData.sideW ? bData.sideW + 20 : 0), h: 52};
						ry += 52;
					});
					if (b.list.side) {
						let rx = x + availW - bData.sideW;
						let cy2 = y;
						b.list.side.forEach(group => {
							group.forEach(btn => {
								layout[btn.id] = {x: rx, y: cy2, w: bData.sideW, h: 52};
								cy2 += 52 + 8;
							});
							cy2 += 26 - 8;
						});
					}
				} else if (b.table) {
					let ry = y + 30;
					b.table.rows.forEach(r => {
						layout[r.id] = {x, y: ry, w: availW, h: 46};
						ry += 46;
					});
				} else if (b.buttons) {
					let bx = (b.buttons.align === 'right') ? x + availW - bData.w : x;
					b.buttons.items.forEach((btn, i) => {
						layout[btn.id] = {x: bx, y, w: bData.btnW[i], h: 52};
						bx += bData.btnW[i] + 10;
					});
				} else if (b.group) {
					if (b.group.id) layout[b.group.id] = out;
					let innerY = y + 30;
					b.group.body.forEach((cb, i) => {
						out.children.push(placeBlock(cb, bData.children[i], x + 20, innerY, availW - 40));
						innerY += bData.children[i].h + 18;
					});
				}
				return out;
			}
			
			const topBlocksLayout = [];
			if (obj.body) {
				obj.body.forEach((b, i) => {
					topBlocksLayout.push(placeBlock(b, blocksData[i], 28, cy, maxW));
					cy += blocksData[i].h + 18;
				});
			}
			
			if (obj.footer) {
				cy += 2;
				let bx = 28 + maxW - footerData.reduce((a, v) => a + v + 10, 0) + 10;
				obj.footer.forEach((btn, i) => {
					layout[btn.id] = {x: bx, y: cy, w: footerData[i], h: 52};
					bx += footerData[i] + 10;
				});
			}

			// Interactive states
			let selections = {};
			let buttonFlashes = {};
			let currentTexts = {};
			let typings = {};
			
			let listRowToGroup = {};
			let groupLatestClick = {};
			let groupIdx = 0;
			function mapRowGroups(b) {
				if (b.list) {
					b.list.rows.forEach(r => listRowToGroup[r.id] = groupIdx);
					groupIdx++;
				} else if (b.table) {
					b.table.rows.forEach(r => listRowToGroup[r.id] = groupIdx);
					groupIdx++;
				} else if (b.group) {
					b.group.body.forEach(mapRowGroups);
				}
			}
			if (obj.body) obj.body.forEach(mapRowGroups);

			const objActs = (acts || []).filter(a => a.target ? a.target.startsWith(obj.id + ':') : (a.args && a.args.on && a.args.on.startsWith(obj.id + ':')));
			
			for (const a of acts) {
				if (a.act === 'input' && a.target && a.target.startsWith(obj.id + ':') && t >= a.t0) {
					const elId = a.target.split(':')[1];
					if (t >= a.t1) {
						currentTexts[elId] = a.args.text;
					} else {
						const p = (t - a.t0) / (a.t1 - a.t0);
						const n = Math.floor(p * a.args.text.length);
						currentTexts[elId] = a.args.text.slice(0, n);
						typings[elId] = true;
					}
				}
			}

			for (const a of acts) { // all acts in the scene, check if it targets this obj
				// click targets 'mouse' but has args.on
				if (a.act === 'click' && a.args.on && a.args.on.startsWith(obj.id + ':') && t >= a.t0) {
					const elId = a.args.on.split(':')[1];
					const gIdx = listRowToGroup[elId];
					if (gIdx !== undefined) {
						if (!groupLatestClick[gIdx] || groupLatestClick[gIdx].t0 < a.t0) {
							groupLatestClick[gIdx] = {elId, t0: a.t0, t1: a.t1};
						}
					}
					const p = (t - a.t0) / (a.t1 - a.t0);
					if (p >= 0.65 && t < a.t1) {
						buttonFlashes[elId] = true;
					}
				}
			}
			
			for (const gIdx in groupLatestClick) {
				const latest = groupLatestClick[gIdx];
				const p = (t - latest.t0) / (latest.t1 - latest.t0);
				if (p >= 0.65) selections[latest.elId] = true;
			}

			return { w: winW, h: winH, layout, topBlocksLayout, selections, buttonFlashes, currentTexts, typings, t };
		},
		draw(api, obj, st) {
			api.rect(0, 0, st.w, st.h, 1, {fill: api.color('card.fill'), color: api.color('effects.pencil'), role: 'panel'});
			if (obj.title) {
				api.text(obj.title, 28, 28 + 30, {size: 32});
				api.text('✕', st.w - 28 - 20, 28 + 30, {size: 32, color: api.color('text.muted')});
				api.ink([[28, 88], [st.w - 28, 88]], 1, {color: api.color('effects.pencil'), width: 2});
			}
			if (obj.tabs) {
				obj.tabs.forEach(tb => {
					const b = st.layout[tb.id];
					if (tb.active) {
						api.rect(b.x, b.y, b.w, b.h, 1, {color: api.color('effects.pencil'), role: 'panel'});
						api.text(tb.text, b.x + b.w / 2, b.y + b.h / 2 + 2, {size: 26, align: 'center'});
					} else {
						api.text(tb.text, b.x + b.w / 2, b.y + b.h / 2 + 2, {size: 26, align: 'center', color: api.color('text.muted')});
					}
				});
			}
			
			function drawBlock(b, bLayout) {
				const lx = bLayout.x, ly = bLayout.y, lw = bLayout.w, lh = bLayout.h;
				if (b.field) {
					const text = st.currentTexts[b.field.id] || "";
					const typing = st.typings[b.field.id];
					api.rect(lx, ly, lw, lh, 1, {color: api.color('effects.pencil'), role: 'panel'});
					const tw = api.measure(text, {size: 26, mono: true}).w;
					api.text(text, lx + 10, ly + lh / 2 + 2, {size: 26, mono: true});
					if (typing) {
						if (Math.floor(st.t * 2) % 2 === 0) {
							api.ctx.fillStyle = api.color('text.body');
							api.ctx.fillRect(lx + 10 + tw + 2, ly + lh / 2 - 13, 14, 26);
						}
					}
				} else if (b.list) {
					api.rect(lx, ly, bLayout.data.rowW, bLayout.data.h, 1, {color: api.color('effects.pencil'), role: 'panel'});
					b.list.rows.forEach(r => {
						const rb = st.layout[r.id];
						if (st.selections[r.id]) {
							api.ctx.fillStyle = api.color('effects.highlight');
							api.ctx.fillRect(rb.x, rb.y, rb.w, rb.h);
						}
						const text = st.currentTexts[r.id] !== undefined ? st.currentTexts[r.id] : r.text;
						const typing = st.typings[r.id];
						const tw = api.measure(text, {size: 26, mono: true}).w;
						api.text(text, rb.x + 10, rb.y + rb.h / 2 + 2, {size: 26, mono: true});
						if (typing) {
							if (Math.floor(st.t * 2) % 2 === 0) {
								api.ctx.fillStyle = api.color('text.body');
								api.ctx.fillRect(rb.x + 10 + tw + 2, rb.y + rb.h / 2 - 13, 14, 26);
							}
						}
					});
					if (b.list.side) {
						b.list.side.forEach(group => {
							group.forEach(btn => {
								const bb = st.layout[btn.id];
								if (st.buttonFlashes[btn.id]) {
									api.ctx.fillStyle = api.color('effects.highlight');
									api.ctx.fillRect(bb.x, bb.y, bb.w, bb.h);
								}
								api.rect(bb.x, bb.y, bb.w, bb.h, 1, {color: api.color('effects.pencil'), role: 'panel'});
								api.text(btn.text, bb.x + bb.w / 2, bb.y + bb.h / 2 + 2, {size: 26, align: 'center'});
							});
						});
					}
				} else if (b.table) {
					b.table.columns.forEach((c, i) => {
						let cx = lx;
						for(let j=0; j<i; j++) cx += bLayout.data.colsW[j];
						api.text(c, cx + 10, ly + 15, {size: 24, color: api.color('text.muted')});
					});
					b.table.rows.forEach(r => {
						const rb = st.layout[r.id];
						if (st.selections[r.id]) {
							api.ctx.fillStyle = api.color('effects.highlight');
							api.ctx.fillRect(rb.x, rb.y, rb.w, rb.h);
						}
						api.ink([[rb.x, rb.y], [rb.x + rb.w, rb.y]], 1, {color: api.color('canvas.grid'), width: 1});
						r.cells.forEach((c, i) => {
							let cx = rb.x;
							for(let j=0; j<i; j++) cx += bLayout.data.colsW[j];
							api.text(c, cx + 10, rb.y + rb.h / 2 + 2, {size: 26});
						});
					});
				} else if (b.buttons) {
					b.buttons.items.forEach(btn => {
						const bb = st.layout[btn.id];
						if (st.buttonFlashes[btn.id]) {
							api.ctx.fillStyle = api.color('effects.highlight');
							api.ctx.fillRect(bb.x, bb.y, bb.w, bb.h);
						}
						api.rect(bb.x, bb.y, bb.w, bb.h, 1, {color: api.color('effects.pencil'), role: 'panel'});
						api.text(btn.text, bb.x + bb.w / 2, bb.y + bb.h / 2 + 2, {size: 26, align: 'center'});
					});
				} else if (b.group) {
					api.rect(lx, ly, lw, lh, 1, {color: api.color('canvas.grid'), role: 'panel'});
					api.text(b.group.title, lx + 10, ly + 15, {size: 26, color: api.color('text.muted')});
					b.group.body.forEach((cb, i) => {
						drawBlock(cb, bLayout.children[i]);
					});
				}
			}
			
			if (obj.body) {
				obj.body.forEach((b, i) => {
					drawBlock(b, st.topBlocksLayout[i]);
				});
			}
			
			if (obj.footer) {
				obj.footer.forEach(btn => {
					const bb = st.layout[btn.id];
					if (st.buttonFlashes[btn.id]) {
						api.ctx.fillStyle = api.color('effects.highlight');
						api.ctx.fillRect(bb.x, bb.y, bb.w, bb.h);
					}
					api.rect(bb.x, bb.y, bb.w, bb.h, 1, {color: api.color('effects.pencil'), role: 'panel'});
					api.text(btn.text, bb.x + bb.w / 2, bb.y + bb.h / 2 + 2, {size: 26, align: 'center'});
				});
			}
		},
		anchors(obj, st, api) {
			return st.layout;
		}
	});
})();
