/* beats.js — V8 黑板報演繹腳本 (vscode_printf_chalk)
 *
 * 先畫後講：每句開口前有 lead 秒（api.drawAt），新畫的東西都落在這段；開口後只做點名（圈、底線、打叉、擦）。
 * 黑板頁（5–21、37–40）：依 storyboard 的 template（center / two-col）在 api.tpl 格子內作畫。
 * 螢幕段（1–4 開場、22–36）：粉筆畫螢幕外框，框內是不套粉筆雜訊的獨立 SVG 層（簡化 VS Code、游標、標註）；游標先動、畫面先變，旁白才講。
 * 純函數 t 驅動，不使用隨機數、系統時間或外部請求。
 */
window.Beats = function (api) {
	"use strict";
	var story = api.story;
	var G = api.G, S = api.S, T = api.T, X = api.X, wlen = api.wlen, C = api.C;
	var NS = "http://www.w3.org/2000/svg";
	var NOSP = { sprite: false };
	var blinkers = []; // 黑板上會閃的提示符號：{ el, t0, t1 }
	// 閃爍排成一段段 K.fade（暗下去再亮回來）：套件的淡出彼此相乘，換頁板擦照樣擦得掉；
	// 自己寫 style.opacity 會被套件的快取蓋掉，寫 visibility 又會放出還沒畫到的筆畫
	function blink(b) {
		for (var k = Math.floor(b.t0 * 2) / 2; k < b.t1; k += 1) {
			var off = k + 0.5, on = Math.min(k + 1, b.t1);
			if (off >= b.t0 && off < b.t1) api.K.fade(b.el, off, 0.02, 0, on);
		}
	}

	// ---------------- 黑板幾何輔助 ----------------
	// 直線箭頭封裝 (G.arrow 需 6-7 個參數: x1, y1, cx, cy, x2, y2, head)
	function arrow(x1, y1, x2, y2, head) {
		var cx = Math.round((x1 + x2) / 2);
		var cy = Math.round((y1 + y2) / 2);
		return G.arrow(x1, y1, cx, cy, x2, y2, head || 22);
	}

	// 程式碼字（Patrick Hand 拉丁、Long Cang 中文）的實測寬度比 wlen 估的窄，置中與底線長度用這個
	function codeW(str, size) {
		var cjk = (str.match(/[\u3400-\u9fff]/g) || []).length;
		return Math.round(size * (cjk * 0.95 + (str.length - cjk) * 0.37));
	}

	// 在目標上畫粉筆橢圓 (8 個參數：P, c, rx, ry, tone, width, t, dur)
	function ring(P, c, rx, ry, tone, width, t, dur) {
		return S(P, G.circ(Math.round(c[0]), Math.round(c[1]), Math.round(rx), Math.round(ry)), tone, width, t, dur || 0.22, NOSP);
	}

	// 沙漏：蝴蝶結形的身體加上下兩條橫槓，(x, y) 是左上角
	function hourglass(x, y, w, h) {
		var m = Math.round(w * 0.08);
		return "M " + (x + m) + " " + y + " L " + (x + w - m) + " " + y + " L " + (x + Math.round(w * 0.58)) + " " + (y + Math.round(h / 2)) +
			" L " + (x + w - m) + " " + (y + h) + " L " + (x + m) + " " + (y + h) + " L " + (x + Math.round(w * 0.42)) + " " + (y + Math.round(h / 2)) + " Z";
	}

	// 先畫後講：每句開口前有 lead 秒，所有新畫的東西都落在 [a, b]；開口後只做「點名」（圈、底線、打叉、擦）
	function win(l) {
		var a = api.drawAt(l), b = api.lineStart(l) - 0.06;
		return { a: a, b: b, at: function (f) { return a + (b - a) * f; } };
	}

	// 掛鎖：鎖身加半圓鎖環，(x, y) 是左上角；回傳畫出的筆畫 (8 個參數)
	function drawLock(P, x, y, w, h, tone, t, dur) {
		var r = Math.round(w * 0.3), sy = y + Math.round(h * 0.42);
		var shackle = "M " + (x + Math.round(w * 0.2)) + " " + sy + " V " + (y + r) + " A " + r + " " + r + " 0 0 1 " + (x + Math.round(w * 0.8)) + " " + (y + r) + " V " + sy;
		var hole = G.line(x + Math.round(w / 2), sy + Math.round(h * 0.18), x + Math.round(w / 2), sy + Math.round(h * 0.38), 1);
		return [
			S(P, G.rect(x, sy, w, y + h - sy), tone, 4.4, t, dur * 0.6, NOSP),
			S(P, shackle, tone, 4.4, t + dur * 0.5, dur * 0.5, NOSP),
			S(P, hole, tone, 4.4, t + dur * 0.8, dur * 0.2, NOSP),
		];
	}

	// 鍵盤塗鴉：外框、兩排鍵、空白鍵 (7 個參數)
	function drawKeyboard(P, kx, ky, kw, kh, t, d) {
		S(P, G.rect(kx, ky, kw, kh), "w", 3.8, t, d * 0.35, NOSP);
		S(P, G.line(kx + 15, ky + kh * 0.32, kx + kw - 15, ky + kh * 0.32, 2), "m", 2.2, t + d * 0.3, d * 0.2, NOSP);
		S(P, G.line(kx + 15, ky + kh * 0.64, kx + kw - 15, ky + kh * 0.64, 2), "m", 2.2, t + d * 0.4, d * 0.2, NOSP);
		for (var k = 1; k < 6; k++) {
			S(P, G.line(kx + k * (kw / 6), ky + 15, kx + k * (kw / 6), ky + kh * 0.64, 2), "m", 2.0, t + d * 0.35 + k * d * 0.04, d * 0.1, NOSP);
		}
		S(P, G.rect(kx + kw * 0.22, ky + kh * 0.72, kw * 0.56, kh * 0.2), "m", 2.4, t + d * 0.7, d * 0.3, NOSP);
	}

	// ==================== 第 1 頁（第 5–6 句）：症狀 左程式卡、右輸出面板 ====================
	// 開場先在電腦畫面重現（第 1–4 句），這頁才把同一支程式畫到黑板上對照
	var T5_6 = api.tpl(5, "two-col");
	var P5_6 = T5_6.P, L5_6 = T5_6.left, R5_6 = T5_6.right;
	var cardH5 = 560, cardY5 = L5_6.y + Math.round((L5_6.h - cardH5) / 2);

	// 第 5 句：左欄順序圖「① 印提示字 → ② 等你打字」；講到「請輸入成績」圈第一框、「等你打字」圈第二框
	// 黑板只畫原理，程式碼留在電腦畫面（使用者 2026-10-28）
	(function () {
		var w = win(5);
		var lab = "照順序", labSize = 44;
		T(P5_6, L5_6.cx - Math.round(codeW(lab, labSize) / 2), cardY5, labSize, [[lab, w.at(0), w.at(0.15), "cm"]], NOSP);
		var bw = 520, bh = 140, bx = L5_6.cx - Math.round(bw / 2), size = 56;
		var steps = [["① 印提示字", cardY5 + 90], ["② 等你打字", cardY5 + 360]];
		steps.forEach(function (st, k) {
			var t0 = w.at(0.15 + k * 0.45);
			S(P5_6, G.rect(bx, st[1], bw, bh), "w", 4.2, t0, 0.25, NOSP);
			T(P5_6, L5_6.cx - Math.round(codeW(st[0], size) / 2), st[1] + Math.round((bh - size * 1.1) / 2), size, [[st[0], t0 + 0.15, t0 + 0.4, "cw"]], NOSP);
		});
		S(P5_6, arrow(L5_6.cx, cardY5 + 90 + bh + 14, L5_6.cx, cardY5 + 360 - 14, 22), "y", 4.2, w.at(0.5), 0.2, NOSP);

		var spPrompt = api.span(5, "請輸入成績"), spWait = api.span(5, "等你打字");
		ring(P5_6, [L5_6.cx, cardY5 + 90 + bh / 2], bw / 2 + 40, bh / 2 + 30, "y", 4.2, spPrompt.start, 0.3);
		ring(P5_6, [L5_6.cx, cardY5 + 360 + bh / 2], bw / 2 + 40, bh / 2 + 30, "b", 4.2, spWait.start, 0.3);
		api.mark("pop", spPrompt.start);
		api.mark("pop", spWait.start);
	})();

	// 第 6 句：右欄輸出面板（[Running]、淡色提示字該在的位置、沙漏）；「空的」劃掉提示字，「一直」圈沙漏並閃（沙漏是符號，旁白不念）
	(function () {
		var w = win(6);
		var bx = R5_6.x, by = cardY5, bw = R5_6.w, bh = cardH5;
		S(P5_6, G.rect(bx, by, bw, bh), "w", 4.2, w.at(0), 0.25, NOSP);
		T(P5_6, bx + 36, by + 28, 46, [["輸出面板", w.at(0.12), w.at(0.3), "cw"]], NOSP);
		T(P5_6, bx + 50, by + 150, 52, [["[Running]", w.at(0.3), w.at(0.5), "lat cb"]], NOSP);
		var px = bx + 50, py = by + 280, psize = 56;
		T(P5_6, px, py, psize, [["請輸入成績:", w.at(0.5), w.at(0.7), "cm"]], NOSP);

		var hw = 110, hh = 160, hx = bx + bw - hw - 80, hy = by + bh - hh - 60;
		var hg = [
			S(P5_6, hourglass(hx, hy, hw, hh), "p", 5, w.at(0.7), 0.2, NOSP),
			S(P5_6, G.line(hx - 16, hy - 12, hx + hw + 16, hy - 12, 2.5) + " " + G.line(hx - 16, hy + hh + 12, hx + hw + 16, hy + hh + 12, 2.5), "p", 5, w.at(0.88), 0.1, NOSP),
		];
		api.mark("bell", w.at(0.7));

		var spEmpty = api.span(6, "空的"), spSand = api.span(6, "一直");
		var pw = codeW("請輸入成績:", psize);
		S(P5_6, G.line(px - 10, py + 54, px + pw + 20, py + 14, 4.5), "p", 5.5, spEmpty.start, 0.2, NOSP);
		S(P5_6, G.cross(px + pw + 70, py - 10, 90), "p", 7.5, spEmpty.start + 0.12, 0.2, { sprite: false, kind: "tap" });
		api.mark("thump", spEmpty.start);
		ring(P5_6, [hx + hw / 2, hy + hh / 2], hw / 2 + 34, hh / 2 + 30, "p", 4.2, spSand.start, 0.25);
		blinkers.push({ el: hg[0].el, t0: spSand.start, t1: api.lineEnd(6) + 0.05 });
		blinkers.push({ el: hg[1].el, t0: spSand.start, t1: api.lineEnd(6) + 0.05 });
	})();

	// ==================== 第 2 頁（第 7–9 句）：原因 printf 卡片與緩衝區 ====================
	var T7_9 = api.tpl(7, "center");
	var P7_9 = T7_9.P;
	// 中層 printf 卡片寬度約為置中框 70%（1256 * 0.70 = 879）
	var pcardW7 = Math.round(T7_9.w * 0.70), pcardH7 = 110;
	var qRx7 = 60, qRy7 = 68, qGap7 = 45;
	var pcardX7 = T7_9.x + Math.round((T7_9.w - (pcardW7 + qGap7 + 2 * qRx7)) / 2);
	var pcardY7 = 340;
	var qx7 = pcardX7 + pcardW7 + qGap7 + qRx7, qy7 = pcardY7 + Math.round(pcardH7 / 2);
	var defText8 = null, outBox8 = null;
	var bufLabel9 = null;

	// 第 7 句：上方提示字框（printf 要印的字），旁邊大問號
	(function () {
		var w = win(7);
		S(P7_9, G.rect(pcardX7, pcardY7, pcardW7, pcardH7), "w", 4.0, w.at(0), 0.25, NOSP);
		// 框裡是 printf 要印的字，不抄整行程式（黑板只畫原理）
		var lead = "printf 要印 ", body = "「請輸入成績:」", codeSize = 48;
		var codeX = pcardX7 + Math.round((pcardW7 - codeW(lead + body, codeSize)) / 2);
		var codeY = pcardY7 + Math.round((pcardH7 - codeSize * 1.1) / 2);
		T(P7_9, codeX, codeY, codeSize, [[lead, w.at(0.2), w.at(0.4), "cm"], [body, w.at(0.4), w.at(0.6), "cw"]], NOSP);

		var qSize = 80;
		var qTextX = qx7 - Math.round(codeW("?", qSize) / 2);
		var qTextY = qy7 - Math.round(qSize * 1.1 / 2);
		T(P7_9, qTextX, qTextY, qSize, [["?", w.at(0.6), w.at(0.85), "cy"]], NOSP);
		ring(P7_9, [qx7, qy7], qRx7, qRy7, "y", 4.2, w.at(0.8), 0.25);
		api.mark("bell", w.at(0.6));
	})();

	// 第 8 句：卡片上方一列：「Code Runner」→ 箭頭（箭頭上黃字「預設」）→「輸出面板」框
	(function () {
		var w = win(8);
		var topSize = 44;
		var crW = codeW("Code Runner", topSize) + 2 * 28;
		var crH = Math.round(topSize * 1.6);
		var obW = codeW("輸出面板", topSize) + 2 * 28;
		var obH = Math.round(topSize * 1.6);
		var boxY = 190;

		var crX = T7_9.cx - 160 - crW;
		S(P7_9, G.rect(crX, boxY, crW, crH), "w", 3.6, w.at(0), 0.2, NOSP);
		var crTextX = crX + 28, crTextY = boxY + Math.round((crH - topSize * 1.1) / 2);
		T(P7_9, crTextX, crTextY, topSize, [["Code Runner", w.at(0.1), w.at(0.35), "lat cw"]], NOSP);

		var obX = T7_9.cx + 160;
		outBox8 = { x: obX, y: boxY, w: obW, h: obH };
		S(P7_9, G.rect(obX, boxY, obW, obH), "w", 3.6, w.at(0.35), 0.2, NOSP);
		var obTextX = obX + 28, obTextY = boxY + Math.round((obH - topSize * 1.1) / 2);
		T(P7_9, obTextX, obTextY, topSize, [["輸出面板", w.at(0.45), w.at(0.7), "cw"]], NOSP);

		var arrY = boxY + Math.round(crH / 2);
		S(P7_9, arrow(crX + crW + 14, arrY, obX - 14, arrY, 20), "y", 4.0, w.at(0.25), 0.2, NOSP);
		var defSize = 38;
		var defW = codeW("預設", defSize);
		var defTextX = Math.round(T7_9.cx - defW / 2);
		var defTextY = arrY - 56;
		defText8 = T(P7_9, defTextX, defTextY, defSize, [["預設", w.at(0.3), w.at(0.55), "kl cy"]], NOSP);

		var spDef = api.span(8, "沒改設定"), spOut = api.span(8, "輸出面板");
		api.K.underline(P7_9, defText8.chars, "y", spDef.start, 0.25, { sprite: false, width: 4.5 });
		var rxOb = Math.round(obW / 2 + 50), ryOb = Math.round(obH / 2 + 32);
		ring(P7_9, [obX + obW / 2, boxY + obH / 2], rxOb, ryOb, "y", 4.2, spOut.start, 0.25);
		api.mark("pop", spOut.start);
	})();

	// 第 9 句：printf 卡片下方箭頭，一排空格子，標籤「緩衝區」；字落進格子
	(function () {
		var w = win(9);
		var bufW = 960, bufH = 195, bufX = T7_9.cx - Math.round(bufW / 2), bufY = 520;
		var arrX = T7_9.cx;
		S(P7_9, arrow(arrX, pcardY7 + pcardH7 + 8, arrX, bufY - 8, 22), "y", 4.0, w.at(0), 0.2, NOSP);

		S(P7_9, G.rect(bufX, bufY, bufW, bufH), "y", 4.0, w.at(0.15), 0.25, NOSP);
		var bufLblSize = 44;
		bufLabel9 = T(P7_9, bufX + 36, bufY + 16, bufLblSize, [["緩衝區", w.at(0.25), w.at(0.45), "kl cy"]], NOSP);

		var count = 5, cellW = 100, cellH = 100, gap = 20;
		var totalCellW = count * cellW + (count - 1) * gap;
		var cellX0 = T7_9.cx - Math.round(totalCellW / 2), cellY = bufY + 76;
		for (var i = 0; i < count; i++) {
			var curX = cellX0 + i * (cellW + gap);
			S(P7_9, G.rect(curX, cellY, cellW, cellH), "w", 3.0, w.at(0.4 + i * 0.08), 0.1, NOSP);
		}

		var spDrop = api.span(9, "放進"), spBuf = api.span(9, "緩衝區");
		var chars = ["請", "輸", "入", "成", "績"];
		var charSize = 60;
		chars.forEach(function (ch, i) {
			var curX = cellX0 + i * (cellW + gap);
			var chX = curX + Math.round((cellW - codeW(ch, charSize)) / 2);
			var chY = cellY + Math.round((cellH - charSize * 1.1) / 2);
			T(P7_9, chX, chY, charSize, [[ch, spDrop.start + i * 0.08, spDrop.start + (i + 1) * 0.08, "cy"]], NOSP);
		});
		api.mark("light", spDrop.start);
		api.K.underline(P7_9, bufLabel9.chars, "y", spBuf.start, 0.25, { sprite: false, width: 4.5 });
	})();

	// ==================== 第 3 頁（第 10–12 句）：輸出面板與終端機對比 ====================
	var T10_12 = api.tpl(10, "two-col");
	var P10_12 = T10_12.P, L10_12 = T10_12.left, R10_12 = T10_12.right;
	var bw10_12 = 660, bh10_12 = 190;
	var lbx10 = L10_12.cx - Math.round(bw10_12 / 2), lby10 = L10_12.y + 85;
	var lay1_10 = lby10 + bh10_12 + 14, lay2_10 = lay1_10 + 76;
	var lpx10 = lbx10, lpy10 = lay2_10 + 14;
	var wall10 = [];
	var bufWordsL10 = null, outWordsL11 = null, termTitle12 = null;

	// 第 10 句：左欄上方標題「輸出面板」，緩衝區（裝著提示字）→ 中間粉紅牆 → 空的輸出面板框
	(function () {
		var w = win(10);
		T(P10_12, L10_12.cx - Math.round(codeW("輸出面板", 52) / 2), L10_12.y + 20, 52, [["輸出面板", w.at(0), w.at(0.2), "cw"]], NOSP);

		S(P10_12, G.rect(lbx10, lby10, bw10_12, bh10_12), "y", 3.8, w.at(0.12), 0.22, NOSP);
		T(P10_12, lbx10 + 30, lby10 + 24, 44, [["緩衝區", w.at(0.2), w.at(0.35), "kl cy"]], NOSP);
		bufWordsL10 = T(P10_12, lbx10 + 45, lby10 + 115, 54, [["請輸入成績", w.at(0.35), w.at(0.6), "cw"]], NOSP);

		S(P10_12, arrow(L10_12.cx, lay1_10, L10_12.cx, lay2_10, 20), "y", 4.0, w.at(0.55), 0.18, NOSP);
		var wallY = Math.round((lay1_10 + lay2_10) / 2);
		wall10.push(S(P10_12, G.line(L10_12.cx - 95, wallY, L10_12.cx + 95, wallY, 3), "p", 6.5, w.at(0.65), 0.18, NOSP));
		wall10.push(S(P10_12, G.cross(L10_12.cx - 24, wallY - 24, 48), "p", 5.0, w.at(0.78), 0.15, { sprite: false, kind: "tap" }));
		api.mark("thump", w.at(0.65));

		S(P10_12, G.rect(lpx10, lpy10, bw10_12, bh10_12), "w", 3.8, w.at(0.2), 0.22, NOSP);
		T(P10_12, lpx10 + 30, lpy10 + 24, 44, [["輸出面板", w.at(0.32), w.at(0.48), "cw"]], NOSP);

		var spNotYet = api.span(10, "不會馬上");
		api.K.ring(P10_12, bufWordsL10.chars, "p", spNotYet.start, 0.3, { sprite: false, pad: 24, padY: 8 });
		api.mark("pop", spNotYet.start);
	})();

	// 第 11 句：等整支程式跑完，板擦擦掉牆，字才在左欄輸出面板框裡出來
	(function () {
		var spDone = api.span(11, "跑完"), spOut = api.span(11, "一起出來");
		var wallY = Math.round((lay1_10 + lay2_10) / 2);
		X(P10_12, wall10, [L10_12.cx - 110, wallY - 35, 220, 70], spDone.start, 0.35);

		outWordsL11 = T(P10_12, lpx10 + 45, lpy10 + 115, 54, [["請輸入成績", spOut.start, spOut.start + 0.2, "cg"]], NOSP);
		api.K.ring(P10_12, outWordsL11.chars, "g", spOut.start + 0.2, 0.25, { sprite: false, pad: 24, padY: 8 });
		api.mark("pop", spOut.start + 0.2);
	})();

	// 第 12 句：右欄上方標題「終端機」，緩衝區 → 箭頭（無牆）→ 終端機框，提示字直接出來
	(function () {
		var w = win(12);
		var rbx12 = R10_12.cx - Math.round(bw10_12 / 2), rby12 = lby10;
		var rpx12 = rbx12, rpy12 = lpy10;

		termTitle12 = T(P10_12, R10_12.cx - Math.round(codeW("終端機", 52) / 2), R10_12.y + 20, 52, [["終端機", w.at(0), w.at(0.2), "kl cw"]], NOSP);

		S(P10_12, G.rect(rbx12, rby12, bw10_12, bh10_12), "y", 3.8, w.at(0.12), 0.22, NOSP);
		T(P10_12, rbx12 + 30, rby12 + 24, 44, [["緩衝區", w.at(0.2), w.at(0.35), "kl cy"]], NOSP);
		T(P10_12, rbx12 + 45, rby12 + 115, 54, [["請輸入成績", w.at(0.35), w.at(0.6), "cw"]], NOSP);

		S(P10_12, arrow(R10_12.cx, lay1_10, R10_12.cx, lay2_10, 20), "g", 4.2, w.at(0.6), 0.2, NOSP);

		S(P10_12, G.rect(rpx12, rpy12, bw10_12, bh10_12), "w", 3.8, w.at(0.25), 0.22, NOSP);
		T(P10_12, rpx12 + 30, rpy12 + 24, 44, [["終端機", w.at(0.35), w.at(0.5), "cw"]], NOSP);
		T(P10_12, rpx12 + 45, rpy12 + 115, 54, [["> 請輸入成績", w.at(0.65), w.b, "lat cg"]], NOSP);

		var spTerm = api.span(12, "終端機"), spShow = api.span(12, "顯示出來");
		api.K.ring(P10_12, termTitle12.chars, "y", spTerm.start, 0.25, { sprite: false, pad: 24, padY: 8 });
		api.mark("pop", spTerm.start);

		S(P10_12, G.check(rpx12 + bw10_12 - 100, rpy12 + 95, 68), "g", 5.5, spShow.start, 0.2, { sprite: false, kind: "tap" });
		api.mark("bell", spShow.start);
	})();

	// ==================== 第 4 頁（第 13–15 句）：解法 加 fflush ====================
	var T13_15 = api.tpl(13, "two-col");
	var P13_15 = T13_15.P, L13_15 = T13_15.left, R13_15 = T13_15.right;
	var cw13 = 680, ch13 = 460;
	var cx13 = L13_15.cx - Math.round(cw13 / 2), cy13 = 208;
	var bw14 = 680, bh14 = 240;
	var bx14 = R13_15.cx - Math.round(bw14 / 2), by14 = 208;
	var gy13 = cy13 + 240;
	var tagW13 = 400, tagH13 = 140, tagX13 = L13_15.cx - Math.round(tagW13 / 2), tagY13 = gy13 + 18 - Math.round(tagH13 / 2);
	var fl13 = null, arrowDown14 = null;

	// 第 13 句：左欄 fflush 名牌，上方小字「加在 printf 後面」；程式長相留到電腦畫面（第 22 句）
	(function () {
		var w = win(13);
		var cap = "加在 printf 後面", capSize = 44;
		T(P13_15, L13_15.cx - Math.round(codeW(cap, capSize) / 2), tagY13 - 100, capSize, [[cap, w.at(0), w.at(0.3), "cm"]], NOSP);
		S(P13_15, G.rect(tagX13, tagY13, tagW13, tagH13), "g", 4.6, w.at(0.3), 0.25, NOSP);
		fl13 = T(P13_15, L13_15.cx - Math.round(codeW("fflush", 76) / 2), tagY13 + Math.round((tagH13 - 76 * 1.1) / 2), 76, [["fflush", w.at(0.5), w.b, "lat cg"]], NOSP);
		api.mark("light", w.at(0.5));

		var spFlush = api.span(13, "fflush");
		api.K.ring(P13_15, fl13.chars, "y", spFlush.start, 0.3, { sprite: false, pad: 24, padY: 8 });
		api.mark("pop", spFlush.start);
	})();

	// 第 14 句：從 fflush 名牌推向緩衝區的箭頭，右欄緩衝區下方往下的箭頭
	(function () {
		var w = win(14);
		S(P13_15, arrow(tagX13 + tagW13 + 20, gy13 + 18, bx14 - 15, gy13 + 18, 24), "y", 4.2, w.at(0), 0.25, NOSP);
		S(P13_15, G.rect(bx14, by14, bw14, bh14), "y", 3.8, w.at(0.2), 0.25, NOSP);
		T(P13_15, bx14 + 36, by14 + 30, 48, [["緩衝區", w.at(0.35), w.at(0.55), "cy"]], NOSP);
		T(P13_15, bx14 + 45, by14 + 130, 58, [["請輸入成績", w.at(0.55), w.at(0.8), "cw"]], NOSP);

		var ay_down_start = by14 + bh14 + 15, ay_down_end = ay_down_start + 65, ax_down = R13_15.cx;
		arrowDown14 = S(P13_15, arrow(ax_down, ay_down_start, ax_down, ay_down_end, 24), "y", 4.5, w.at(0.8), 0.2, NOSP);

		var spPush = api.span(14, "推出去");
		blinkers.push({ el: arrowDown14.el, t0: spPush.start, t1: spPush.start + 0.6 });
		api.mark("pop", spPush.start);
	})();

	// 第 15 句：緩衝區下方寫出綠色提示字（排在緩衝區下方，不超出右欄）
	(function () {
		var w = win(15);
		var outW = codeW("請輸入成績:", 58);
		var outX = Math.round(R13_15.cx - outW / 2);
		var outY = by14 + bh14 + 115;
		var prompt15 = T(P13_15, outX, outY, 58, [["請輸入成績:", w.at(0), w.b, "cg"]], NOSP);

		var spOut = api.span(15, "出來了");
		api.K.ring(P13_15, prompt15.chars, "g", spOut.start, 0.25, { sprite: false, pad: 26, padY: 10 });
		api.mark("pop", spOut.start);
	})();

	// ==================== 第 5 頁（第 16–21 句）：scanf 還是不行，兩欄對照（左面板與鍵盤、右大沙漏） ====================
	var T16_21 = api.tpl(16, "two-col");
	var P16_21 = T16_21.P, L16_21 = T16_21.left, R16_21 = T16_21.right;
	// 左欄：輸出面板外框與鍵盤（合計佔滿左欄高度 ≥ 80 %）
	var bw16 = 680, bh16 = 350;
	var bx16 = L16_21.cx - Math.round(bw16 / 2), by16 = 160;
	var kw18 = 520, kh18 = 136;
	var kx18 = L16_21.cx - Math.round(kw18 / 2), ky18 = 570;
	// 面板右上角掛鎖（內部預留尺寸）
	var lkW17 = 90, lkH17 = 120;
	var lkX17 = bx16 + bw16 - lkW17 - 36, lkY17 = by16 + 24;
	var cx_lk17 = lkX17 + Math.round(lkW17 / 2), cy_lk17 = lkY17 + Math.round(lkH17 / 2);
	var rx_lk17 = Math.round(lkW17 / 2) + 24, ry_lk17 = Math.round(lkH17 / 2) + 24;
	// 右欄：大沙漏佔欄高 60–70 %（420 / 668 = 62.9 %）
	var hw16 = 260, hh16 = 420;
	var hx16 = R16_21.cx - Math.round(hw16 / 2), hy16 = 180;
	var cx_hg16 = R16_21.cx, cy_hg16 = hy16 + Math.round(hh16 / 2);
	var rx_hg16 = Math.round(hw16 / 2) + 40, ry_hg16 = Math.round(hh16 / 2) + 30;
	var scLine16 = null, roTag17 = null, hgScanf16 = [];

	// 第 16 句：左欄畫輸出面板（含提示字、scanf）、右欄畫大沙漏與「整個程式在等」
	(function () {
		var w = win(16);
		// 左欄：輸出面板外框、標題、亮色提示字與 scanf 行
		S(P16_21, G.rect(bx16, by16, bw16, bh16), "w", 4, w.at(0), 0.25, NOSP);
		T(P16_21, bx16 + 40, by16 + 24, 46, [["輸出面板", w.at(0.1), w.at(0.28), "cw"]], NOSP);
		T(P16_21, bx16 + 50, by16 + 120, 50, [["請輸入成績:", w.at(0.25), w.at(0.5), "cg"]], NOSP);

		// scanf 在等輸入：畫一個空的輸入格，不抄 scanf 那行程式（黑板只畫原理）
		scLine16 = T(P16_21, bx16 + 50, by16 + 220, 54, [["＿ 等你輸入", w.at(0.45), w.at(0.72), "cy"]], NOSP);

		// 右欄：中央大沙漏與上下蓋板、下方寫「整個程式在等」
		hgScanf16.push(S(P16_21, hourglass(hx16, hy16, hw16, hh16), "p", 5.2, w.at(0.35), 0.28, NOSP));
		var caps = G.line(hx16 - 24, hy16 - 12, hx16 + hw16 + 24, hy16 - 12, 3) + " " + G.line(hx16 - 24, hy16 + hh16 + 12, hx16 + hw16 + 24, hy16 + hh16 + 12, 3);
		hgScanf16.push(S(P16_21, caps, "p", 5.0, w.at(0.6), 0.18, NOSP));
		api.mark("bell", w.at(0.35));

		var tw16 = codeW("整個程式在等", 46);
		var tx16 = R16_21.cx - Math.round(tw16 / 2), ty16 = hy16 + hh16 + 48;
		T(P16_21, tx16, ty16, 46, [["整個程式在等", w.at(0.7), w.b, "cw"]], NOSP);

		// 開口後點名：講到「scanf」圈 scanf 那行
		var spScanf = api.span(16, "scanf");
		api.K.ring(P16_21, scLine16.chars, "y", spScanf.start, 0.25, { sprite: false, pad: 22, padY: 8 });
		api.mark("pop", spScanf.start);
	})();

	// 第 17 句：講到「唯讀」寫出標籤並底線；講到「不能打字」於右上角畫掛鎖並圈起（鎖是符號，旁白不念）
	(function () {
		var spReadOnly = api.span(17, "唯讀");
		var roX = bx16 + 40 + codeW("輸出面板", 46) + 18, roY = by16 + 24;
		roTag17 = T(P16_21, roX, roY, 46, [["唯讀", spReadOnly.start, spReadOnly.start + 0.2, "cy"]], NOSP);
		api.K.underline(P16_21, roTag17.chars, "y", spReadOnly.start + 0.15, 0.22, { sprite: false, width: 4.5 });
		api.mark("pop", spReadOnly.start);

		var spLock = api.span(17, "不能打字");
		drawLock(P16_21, lkX17, lkY17, lkW17, lkH17, "y", spLock.start, 0.28);
		ring(P16_21, [cx_lk17, cy_lk17], rx_lk17, ry_lk17, "y", 4.2, spLock.start + 0.2, 0.25);
		api.mark("bell", spLock.start + 0.2);
	})();

	// 第 18 句：先畫鍵盤與被擋住的向上箭頭 ✗；講到「一直等」圈右欄大沙漏並保持閃爍
	(function () {
		var w = win(18);
		drawKeyboard(P16_21, kx18, ky18, kw18, kh18, w.at(0), 0.35);
		var ax = L16_21.cx;
		S(P16_21, arrow(ax, ky18 - 6, ax, by16 + bh16 + 10, 18), "p", 4, w.at(0.4), 0.25, NOSP);
		S(P16_21, G.cross(ax - 22, by16 + bh16 - 2, 44), "p", 6.5, w.at(0.65), 0.2, { sprite: false, kind: "tap" });
		api.mark("thump", w.at(0.65));

		var spWait = api.span(18, "一直等");
		ring(P16_21, [cx_hg16, cy_hg16], rx_hg16, ry_hg16, "p", 4.2, spWait.start, 0.25);
		blinkers.push({ el: hgScanf16[0].el, t0: spWait.start, t1: api.lineEnd(21) + 0.05 });
		blinkers.push({ el: hgScanf16[1].el, t0: spWait.start, t1: api.lineEnd(21) + 0.05 });
	})();

	// 第 19 句：底線 scanf 那行
	(function () {
		var spScanf = api.span(19, "scanf");
		api.K.underline(P16_21, scLine16.chars, "y", spScanf.start, 0.25, { sprite: false, width: 5 });
	})();

	// 第 20–21 句：fflush 幫不上忙，改在終端機跑，直接到電腦上做一次（過渡到電腦畫面，保持靜止）
	(function () {
		// hold still
	})();

	// ==================== 第 6 頁（第 37–40 句）：在終端機卡住怎麼停 ====================
	var T37_40 = api.tpl(37, "two-col");
	var P37_40 = T37_40.P, L37_40 = T37_40.left, R37_40 = T37_40.right;
	var bw37 = 710, bh37 = 520;
	var bx37 = L37_40.cx - Math.round(bw37 / 2), by37 = 438 - Math.round(bh37 / 2);
	var hw37 = 80, hh37 = 115;
	var cx_hg37 = bx37 + bw37 - 94, cy_hg37 = by37 + 102;
	var hx37 = cx_hg37 - Math.round(hw37 / 2), hy37 = cy_hg37 - Math.round(hh37 / 2);
	var rx_hg37 = 64, ry_hg37 = 78;
	var tLabel37 = null, hg37 = [];
	var kh40 = 240, keyY40 = 438 - Math.round(kh40 / 2);
	var kwCtrl40 = 290, kwC40 = 230, keySize40 = 92;
	var ck0_40 = R37_40.cx - Math.round((kwCtrl40 + 70 + kwC40) / 2);

	// 第 37 句：左欄終端機框（標籤「終端機」），裡面提示字與閃爍游標，右上沙漏
	(function () {
		var w = win(37);
		S(P37_40, G.rect(bx37, by37, bw37, bh37), "w", 4, w.at(0), 0.3, NOSP);
		tLabel37 = T(P37_40, bx37 + 40, by37 + 34, 52, [["終端機", w.at(0.2), w.at(0.4), "kl cw"]], NOSP);
		var gt37 = T(P37_40, bx37 + 40, by37 + 230, 64, [["> ", w.at(0.45), w.at(0.55), "lat cy"]], NOSP);
		blinkers.push({ el: gt37.div, t0: api.lineStart(37), t1: api.lineEnd(40) + 0.05 });
		T(P37_40, bx37 + 120, by37 + 230, 58, [["請輸入成績:", w.at(0.55), w.at(0.85), "cw"]], NOSP);

		hg37.push(S(P37_40, hourglass(hx37, hy37, hw37, hh37), "p", 5, w.at(0.55), 0.3, NOSP));
		hg37.push(S(P37_40, G.line(hx37 - 10, hy37 - 8, hx37 + hw37 + 10, hy37 - 8, 2.5) + " " + G.line(hx37 - 10, hy37 + hh37 + 8, hx37 + hw37 + 10, hy37 + hh37 + 8, 2.5), "p", 5, w.at(0.8), 0.15, NOSP));
		api.mark("thump", w.at(0.55));
	})();

	// 第 38 句：程式一樣停在等輸入
	(function () {
		var spStuck = api.span(38, "停在");
		var r = ring(P37_40, [cx_hg37, cy_hg37], rx_hg37, ry_hg37, "y", 4.2, spStuck.start, 0.25);
		if (r) hg37.push(r);
		api.mark("thump", spStuck.start);
	})();

	// 第 39 句：滑鼠游標移到終端機框內點一下（點擊波紋），圈「終端機」
	(function () {
		var w = win(39);
		var tx = bx37 + 340, ty = by37 + 340;
		S(P37_40, "M " + tx + " " + ty + " L " + tx + " " + (ty + 54) + " L " + (tx + 15) + " " + (ty + 41) + " L " + (tx + 26) + " " + (ty + 66) + " L " + (tx + 36) + " " + (ty + 61) + " L " + (tx + 25) + " " + (ty + 37) + " L " + (tx + 42) + " " + (ty + 37) + " Z", "w", 4, w.at(0), 0.25, NOSP);
		S(P37_40, G.circ(tx, ty, 44, 44, 0.8), "y", 4, w.at(0.25), 0.2, { sprite: false, kind: "tap" });
		api.mark("pop", w.at(0.25));

		var spTerm = api.span(39, "終端機");
		api.K.ring(P37_40, tLabel37.chars, "y", spTerm.start, 0.25, { sprite: false, pad: 24, padY: 8 });
		api.mark("pop", spTerm.start);
	})();

	// 第 40 句：右欄按 Ctrl + C，沙漏與圈一同擦掉，程式停了
	(function () {
		var w = win(40);
		var keys = [["Ctrl", ck0_40, kwCtrl40, 0.1], ["C", ck0_40 + kwCtrl40 + 70, kwC40, 0.5]];
		keys.forEach(function (c) {
			var kx = c[1], kw = c[2], t = w.at(c[3]);
			S(P37_40, G.rect(kx, keyY40, kw, kh40), "y", 5, t, 0.14, { sprite: false, kind: "tap" });
			S(P37_40, G.rect(kx + 12, keyY40 + 12, kw - 24, kh40 - 36), "w", 3, t + 0.04, 0.12, NOSP);
			T(P37_40, Math.round(kx + (kw - codeW(c[0], keySize40) * 1.05) / 2), keyY40 + 58, keySize40, [[c[0], t + 0.06, t + 0.24, "lat cy"]], NOSP);
			api.mark("pop", t);
		});
		T(P37_40, ck0_40 + kwCtrl40 + 35 - Math.round(wlen("+") * 76 / 2), keyY40 + 76, 76, [["+", w.at(0.35), w.at(0.48), "cw"]], NOSP);

		var tCtrl = api.at(40, "Ctrl"), tC = api.at(40, "C"), spStop = api.span(40, "停了");
		ring(P37_40, [ck0_40 + kwCtrl40 / 2, keyY40 + kh40 / 2], kwCtrl40 / 2 + 36, kh40 / 2 + 32, "g", 4.2, tCtrl, 0.25);
		ring(P37_40, [ck0_40 + kwCtrl40 + 70 + kwC40 / 2, keyY40 + kh40 / 2], kwC40 / 2 + 36, kh40 / 2 + 32, "g", 4.2, tC, 0.25);
		api.mark("pop", tCtrl);
		// 擦除沙漏時將第 38 句的黃圈一併抹除，不留殘留橢圓
		X(P37_40, hg37, [cx_hg37 - rx_hg37 - 14, cy_hg37 - ry_hg37 - 14, 2 * rx_hg37 + 28, 2 * ry_hg37 + 28], spStop.start, 0.35);
	})();

	blinkers.forEach(blink);
	return {
		// 電腦畫面由 index.html 依分鏡的 screen 描述接上共用 VS Code 元件，這裡不用畫
		render: function () {},
	};
};
