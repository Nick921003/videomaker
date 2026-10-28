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

	// ==================== 簡化 VS Code：開場與後段兩個電腦畫面共用 ====================
	// opt.files：檔案總管 [檔名, 是不是 .c]；opt.sel：有選取底色的檔名；opt.tabs：分頁（第 0 頁是 score.c）
	function vscodeMock(scr, opt) {
		var P = scr.P, SW = scr.w, SH = scr.h;
		var tIn = scr.tIn;
		var pr = C.pr, E = C.E, lerp = C.lerp;

		var SANS = "'Huninn', sans-serif";
		var MONO = "'JetBrains Mono', 'Huninn', monospace";
		var VS = {
			title: "#3c3c3c", titleBox: "#2b2b2b", fg: "#cccccc", dim: "#a0a0a0", act: "#333333", actOn: "#ffffff", actOff: "#9e9e9e",
			side: "#252526", sel: "#37373d", edit: "#1e1e1e", tabBar: "#252526", tabOff: "#2d2d2d", line: "#3c3c3c", lineNo: "#9e9e9e",
			kw: "#569cd6", ctl: "#c586c0", fn: "#dcdcaa", str: "#ce9178", num: "#b5cea8", vr: "#9cdcfe", pl: "#d4d4d4",
			accent: "#0e7ad1", link: "#3794ff", file: "#519aba", menu: "#252526", menuLine: "#454545", hover: "#04395e",
			win: "#1f1f1f", winTitle: "#181818", input: "#313131", inputLine: "#454545", tip: "#f3f3f3", tipFg: "#1e1e1e",
			sub: "rgba(8,8,8,0.88)",
		};
		var ANN = { yellow: "rgba(255,214,10,0.45)", red: "#ff4b3e", green: "#35d07f" };

		var chalkEl = P.el.parentNode, world = chalkEl.parentNode;
		var layer = world.querySelector("svg.screen-layer");
		if (!layer) {
			layer = document.createElementNS(NS, "svg");
			layer.setAttribute("class", "screen-layer");
			layer.setAttribute("width", parseFloat(chalkEl.style.width));
			layer.setAttribute("height", parseFloat(chalkEl.style.height));
			layer.style.cssText = "position:absolute;left:0;top:0;overflow:visible;pointer-events:none";
			world.insertBefore(layer, chalkEl);
		}
		function svgEl(tag, attrs, parent) {
			var e = document.createElementNS(NS, tag);
			for (var k in attrs) e.setAttribute(k, attrs[k]);
			if (parent) parent.appendChild(e);
			return e;
		}
		var defs = svgEl("defs", {}, layer);
		var clip = svgEl("clipPath", { id: "scr-clip-" + scr.k }, defs);
		svgEl("rect", { x: 0, y: 0, width: SW, height: SH }, clip);
		var rootOuter = svgEl("g", { transform: "translate(" + (P.ox + scr.x) + "," + (P.oy + scr.y) + ")", "clip-path": "url(#scr-clip-" + scr.k + ")" }, layer);
		var root = svgEl("g", { opacity: 0 }, rootOuter);
		var ups = [];

		function rect(g, x, y, w, h, fill, o) {
			var a = { x: x, y: y, width: w, height: h, fill: fill };
			if (o) for (var k in o) a[k] = o[k];
			return svgEl("rect", a, g);
		}
		function text(g, x, y, size, fill, str, o) {
			o = o || {};
			var e = svgEl("text", { x: x, y: y, "font-size": size, fill: fill, "font-family": o.mono ? MONO : SANS, "font-weight": o.bold ? 600 : 400, "text-anchor": o.anchor || "start" }, g);
			e.style.whiteSpace = "pre";
			e.textContent = str;
			return e;
		}
		function path(g, d, stroke, sw, fill) {
			return svgEl("path", { d: d, stroke: stroke || "none", "stroke-width": sw || 0, fill: fill || "none", "stroke-linecap": "round", "stroke-linejoin": "round" }, g);
		}
		function tw(s, size, mono, bold) {
			var cjk = (s.match(/[\u3400-\u9fff]/g) || []).length;
			var em = mono ? 0.6 : 0.52;
			return Math.round(size * (cjk * 1.0 + (s.length - cjk) * em) * (bold ? 1.05 : 1.0));
		}
		function setOp(el, v) {
			var s = v <= 0.001 ? "0" : v >= 0.999 ? "1" : v.toFixed(3);
			if (el.__op !== s) { el.__op = s; el.setAttribute("opacity", s); }
		}
		function vis(el, tInAt, tOutAt, din, dout) {
			din = din || 0.15; dout = dout || 0.15;
			ups.push(function (t) {
				var a = pr(t, tInAt, din), b = tOutAt == null ? 1 : 1 - pr(t, tOutAt, dout);
				setOp(el, a * b);
			});
		}

		var L = {
			titleH: 48, actW: 68, expW: 320, tabH: 52, ptabH: 48, subH: 72,
			ui: 22, codeSize: 24, codePitch: 36, outSize: 24, outPitch: 38,
		};
		L.bodyY1 = SH - L.subH;
		L.panelH = Math.round(L.bodyY1 * 0.44);
		L.editX0 = L.actW + L.expW;
		L.panelY = L.bodyY1 - L.panelH;
		L.codeY0 = L.titleH + L.tabH + 14;
		L.outX = L.editX0 + 28;
		L.outBase = function (k) { return L.panelY + L.ptabH + 8 + 30 + k * L.outPitch; };
		var BOX = {};
		function box(name, x, y, w, h) { BOX[name] = { x: x, y: y, w: w, h: h, cx: x + w / 2, cy: y + h / 2 }; return BOX[name]; }

		var mock = svgEl("g", {}, root);

		// ---------- 標題列 ----------
		rect(mock, 0, 0, SW, L.titleH, VS.title);
		path(mock, "M 22 18 L 32 12 L 28 24 L 38 22 L 20 36 L 24 26 L 16 28 Z", VS.accent, 1, VS.accent);
		text(mock, 48, 32, L.ui, VS.fg, "檔案"); text(mock, 104, 32, L.ui, VS.fg, "編輯");
		text(mock, 160, 32, L.ui, VS.fg, "選取項目"); text(mock, 256, 32, L.ui, VS.fg, "檢視");
		text(mock, 312, 32, L.ui, VS.fg, "移至"); text(mock, 368, 32, L.ui, VS.fg, "執行");
		text(mock, 424, 32, L.ui, VS.fg, "終端機"); text(mock, 498, 32, L.ui, VS.fg, "說明");
		var tboxW = 560, tboxX = Math.round((SW - tboxW) / 2);
		rect(mock, tboxX, 7, tboxW, 34, VS.titleBox, { rx: 6, stroke: "#454545", "stroke-width": 1 });
		path(mock, "M " + (tboxX + 22) + " 20 A 4 4 0 1 1 " + (tboxX + 16) + " 24 L " + (tboxX + 12) + " 28", VS.dim, 2);
		text(mock, tboxX + 32, 30, 20, VS.dim, "c_homework");
		var wx = SW - 120;
		path(mock, "M " + wx + " 24 h 14", VS.fg, 2);
		rect(mock, wx + 36, 17, 14, 14, "none", { stroke: VS.fg, "stroke-width": 2 });
		path(mock, "M " + (wx + 72) + " 17 l 14 14 m 0 -14 l -14 14", VS.fg, 2);

		// ---------- 活動列 ----------
		rect(mock, 0, L.titleH, L.actW, SH - L.titleH, VS.act);
		rect(mock, 0, L.titleH, 3, 56, VS.actOn);
		var ax = L.actW / 2, ay0 = L.titleH + 28, apitch = 56;
		rect(mock, ax - 12, ay0 - 14, 24, 28, "none", { stroke: VS.actOn, "stroke-width": 3 });
		var y1 = ay0 + apitch;
		svgEl("circle", { cx: ax - 3, cy: y1 - 3, r: 8, fill: "none", stroke: VS.actOff, "stroke-width": 3 }, mock);
		path(mock, "M " + (ax + 3) + " " + (y1 + 3) + " L " + (ax + 12) + " " + (y1 + 12), VS.actOff, 3);
		var y2 = ay0 + apitch * 2;
		path(mock, "M " + (ax - 8) + " " + (y2 - 7) + " V " + (y2 + 7) + " M " + (ax + 10) + " " + (y2 + 1) + " Q " + (ax + 10) + " " + (y2 + 12) + " " + (ax - 3) + " " + (y2 + 12), VS.actOff, 3);
		var y3 = ay0 + apitch * 3;
		path(mock, "M " + (ax - 8) + " " + (y3 - 14) + " L " + (ax + 14) + " " + y3 + " L " + (ax - 8) + " " + (y3 + 14) + " Z", VS.actOff, 3);
		var y4 = ay0 + apitch * 4;
		[[-14, -14], [2, -14], [-14, 2], [4, 6]].forEach(function (o, i) { rect(mock, ax + o[0], y4 + o[1], i === 3 ? 12 : 12, 12, "none", { stroke: VS.actOff, "stroke-width": 3 }); });
		var gearY = L.bodyY1 - 50, gearX = ax;
		svgEl("circle", { cx: ax, cy: gearY - 80, r: 14, fill: "none", stroke: VS.actOff, "stroke-width": 3 }, mock);
		path(mock, "M " + (ax - 14) + " " + (gearY - 80 + 22) + " Q " + ax + " " + (gearY - 80 + 2) + " " + (ax + 14) + " " + (gearY - 80 + 22), VS.actOff, 3);
		var gearHot = rect(mock, gearX - 28, gearY - 28, 56, 56, "rgba(255,255,255,0.14)", { rx: 8 });
		function gearPath(cx, cy, ro, ri, n) {
			var d = "";
			for (var k = 0; k < n; k++) {
				var a0 = k * 2 * Math.PI / n, w1 = Math.PI / n * 0.5, w2 = Math.PI / n * 0.3;
				[[ri, a0 - w1], [ro, a0 - w2], [ro, a0 + w2], [ri, a0 + w1]].forEach(function (p, j) {
					d += (k === 0 && j === 0 ? "M " : " L ") + (cx + Math.cos(p[1]) * p[0]).toFixed(1) + " " + (cy + Math.sin(p[1]) * p[0]).toFixed(1);
				});
			}
			return d + " Z";
		}
		path(mock, gearPath(gearX, gearY, 20, 14, 8), VS.actOff, 3);
		svgEl("circle", { cx: gearX, cy: gearY, r: 7, fill: "none", stroke: VS.actOff, "stroke-width": 3 }, mock);
		box("gear", gearX - 28, gearY - 28, 56, 56);

		// ---------- 檔案總管 ----------
		rect(mock, L.actW, L.titleH, L.expW, SH - L.titleH, VS.side);
		text(mock, L.actW + 22, L.titleH + 40, L.ui, VS.fg, "檔案總管");
		text(mock, L.actW + L.expW - 28, L.titleH + 40, L.ui, VS.fg, "···", { anchor: "end" });
		var frow = L.titleH + 52;
		path(mock, "M " + (L.actW + 24) + " " + (frow + 18) + " L " + (L.actW + 32) + " " + (frow + 26) + " L " + (L.actW + 40) + " " + (frow + 18), VS.fg, 2.5);
		text(mock, L.actW + 52, frow + 31, L.ui, VS.fg, "c_homework", { bold: true });
		var files = opt.files, sel = {};
		var rp = 44, r0 = frow + 48;
		files.forEach(function (f, i) {
			var ry = r0 + i * rp;
			if (opt.sel.indexOf(f[0]) >= 0) sel[f[0]] = rect(mock, L.actW, ry, L.expW, rp, VS.sel);
			if (f[1]) text(mock, L.actW + 34, ry + 31, L.ui, VS.file, "C", { bold: true });
			else path(mock, "M " + (L.actW + 34) + " " + (ry + 15) + " h 18 M " + (L.actW + 34) + " " + (ry + 22) + " h 18 M " + (L.actW + 34) + " " + (ry + 29) + " h 12", VS.dim, 2.5);
			text(mock, L.actW + 66, ry + 31, L.ui, VS.fg, f[0]);
		});
		L.expBottom = r0 + files.length * rp;

		// ---------- 編輯區：分頁、程式碼 ----------
		rect(mock, L.editX0, L.titleH, SW - L.editX0, SH - L.titleH, VS.edit);
		rect(mock, L.editX0, L.titleH, SW - L.editX0, L.tabH, VS.tabBar);
		var tabNames = opt.tabs;
		function drawTabs(g, act) {
			var tabX = L.editX0;
			tabNames.forEach(function (nm, k) {
				var on = k === act, nameW = tw(nm, L.ui), w = 20 + 24 + 8 + nameW + (on ? 14 + 24 : 0) + 20;
				rect(g, tabX, L.titleH, w, L.tabH, on ? VS.edit : VS.tabOff);
				if (on) rect(g, tabX, L.titleH, w, 3, VS.accent);
				text(g, tabX + 20, L.titleH + 36, L.ui, VS.file, "C", { bold: true });
				text(g, tabX + 52, L.titleH + 36, L.ui, on ? VS.actOn : VS.dim, nm);
				if (on) path(g, "M " + (tabX + w - 40) + " " + (L.titleH + 19) + " l 16 16 m 0 -16 l -16 16", VS.fg, 2.5);
				if (act === 1 && k === 0) box("tabS1", tabX, L.titleH, w, L.tabH);
				tabX += w;
			});
		}
		var tabsS2 = svgEl("g", {}, mock), tabsS1 = svgEl("g", {}, mock);
		drawTabs(tabsS2, 1);
		drawTabs(tabsS1, 0);

		var runCx = SW - 150, runCy = L.titleH + L.tabH / 2;
		var playG = svgEl("g", {}, mock), stopG = svgEl("g", {}, mock);
		path(playG, "M " + (runCx - 9) + " " + (runCy - 13) + " L " + (runCx + 12) + " " + runCy + " L " + (runCx - 9) + " " + (runCy + 13) + " Z", VS.fg, 3);
		rect(stopG, runCx - 13, runCy - 13, 26, 26, "none", { stroke: "#f14c4c", "stroke-width": 3, rx: 2 });
		rect(mock, SW - 108, runCy - 13, 26, 26, "none", { stroke: VS.fg, "stroke-width": 2.5, rx: 3 });
		path(mock, "M " + (SW - 95) + " " + (runCy - 13) + " V " + (runCy + 13), VS.fg, 2.5);
		text(mock, SW - 44, runCy + 8, L.ui, VS.fg, "···", { anchor: "middle" });
		box("runBtn", runCx - 28, runCy - 26, 56, 52);
		box("stopBtn", runCx - 28, runCy - 26, 56, 52);

		var CODE = [
			[["#include", VS.ctl], [" <stdio.h>", VS.str]],
			[],
			[["int", VS.kw], [" ", VS.pl], ["main", VS.fn], ["(", VS.pl], ["void", VS.kw], [") {", VS.pl]],
			[["    ", VS.pl], ["int", VS.kw], [" ", VS.pl], ["score", VS.vr], [";", VS.pl]],
			[["    ", VS.pl], ["printf", VS.fn], ["(", VS.pl], ["\"請輸入成績: \"", VS.str], [");", VS.pl]],
			[["    ", VS.pl], ["fflush", VS.fn], ["(", VS.pl], ["stdout", VS.vr], [");", VS.pl]],
			[["    ", VS.pl], ["scanf", VS.fn], ["(", VS.pl], ["\"%d\"", VS.str], [", ", VS.pl], ["&", VS.pl], ["score", VS.vr], [");", VS.pl]],
			[["    ", VS.pl], ["printf", VS.fn], ["(", VS.pl], ["\"你的成績是 %d\\n\"", VS.str], [", ", VS.pl], ["score", VS.vr], [");", VS.pl]],
			[["    ", VS.pl], ["return", VS.ctl], [" ", VS.pl], ["0", VS.num], [";", VS.pl]],
			[["}", VS.pl]],
		];
		var CODE_S1 = CODE.filter(function (ln, i) { return i !== 5; });
		function drawCode(g, lines) {
			lines.forEach(function (ln, i) {
				var by = L.codeY0 + i * L.codePitch + 29;
				text(g, L.editX0 + 66, by, L.codeSize, VS.lineNo, String(i + 1), { mono: true, anchor: "end" });
				if (!ln.length) return;
				var e = svgEl("text", { x: L.editX0 + 100, y: by, "font-size": L.codeSize, "font-family": MONO }, g);
				e.style.whiteSpace = "pre";
				ln.forEach(function (tk) { var ts = svgEl("tspan", { fill: tk[1] }, e); ts.textContent = tk[0]; });
			});
		}
		var codeS2 = svgEl("g", {}, mock), codeS1 = svgEl("g", {}, mock);
		drawCode(codeS2, CODE);
		drawCode(codeS1, CODE_S1);

		// ---------- 下方面板 ----------
		rect(mock, L.editX0, L.panelY, SW - L.editX0, L.panelH, VS.side);
		rect(mock, L.editX0, L.panelY, SW - L.editX0, L.ptabH, VS.tabBar);
		var ptabs = [{ name: "問題", w: 60 }, { name: "輸出", w: 60 }, { name: "偵錯主控台", w: 120 }, { name: "終端機", w: 80 }];
		var px = L.outX;
		ptabs.forEach(function (pt) {
			var w = tw(pt.name, L.ui);
			pt.x = px; pt.w = w;
			px += w + 44;
		});
		var tabTxt = ptabs.map(function (pt, i) { return text(mock, pt.x, L.panelY + 36, L.ui, i === 1 ? VS.actOn : VS.dim, pt.name); });
		var tabLine = rect(mock, ptabs[1].x, L.panelY + L.ptabH - 4, ptabs[1].w, 3, VS.accent);
		box("ptabTerm", ptabs[3].x, L.panelY + 8, ptabs[3].w, 38);

		function typedText(e, full, times) {
			var chars = Array.from(full);
			ups.push(function (t) {
				var n = 0;
				for (var i = 0; i < times.length; i++) { if (times[i] <= t) n = i + 1; else break; }
				if (e.__n !== n) { e.__n = n; e.textContent = chars.slice(0, n).join(""); }
			});
		}

		// ---------- 標註 ----------
		var annG = svgEl("g", {}, root);
		function ringPath(cx, cy, rx, ry, seed, sq) {
			var n = 72, a0 = -2.3 + C.hash(seed) * 0.6, e = 2 / sq, d = "", k = Math.min(1, Math.min(rx, ry) / 60);
			for (var i = 0; i <= n; i++) {
				var a = a0 + (i / n) * 1.12 * Math.PI * 2, g = ((C.hash(seed + i * 1.7) - 0.5) * 5 + 9 * (i / n)) * k;
				var ca = Math.cos(a), sa = Math.sin(a);
				d += (i ? " L " : "M ") + (cx + (ca < 0 ? -1 : 1) * Math.pow(Math.abs(ca), e) * (rx + g)).toFixed(1) + " " + (cy + (sa < 0 ? -1 : 1) * Math.pow(Math.abs(sa), e) * (ry + g * 0.7)).toFixed(1);
			}
			return d;
		}
		function annRing(b, pad, seed, t0, t1, dur) {
			var el = path(annG, ringPath(b.cx, b.cy, b.w / 2 + pad, b.h / 2 + pad * 0.7, seed, b.w / b.h > 1.8 ? 4 : 2), ANN.red, 5.5);
			var len = el.getTotalLength();
			el.style.strokeDasharray = len + " " + len;
			ups.push(function (t) {
				el.style.strokeDashoffset = (len * (1 - E.o2(pr(t, t0, dur || 0.3)))).toFixed(1);
				setOp(el, t < t0 ? 0 : 1 - pr(t, t1, 0.3));
			});
			return el;
		}
		function annBand(b, t0, t1, dur, tOutAt) {
			var h = 16, el = rect(annG, b.x - 4, b.y + b.h - 10, b.w + 8, h, ANN.yellow, { rx: 8 });
			ups.push(function (t) {
				var u = E.io2(pr(t, t0, dur));
				el.setAttribute("width", Math.max(0.1, (b.w + 8) * u).toFixed(1));
				setOp(el, t < t0 ? 0 : 1 - pr(t, tOutAt, 0.3));
			});
			return el;
		}


		// 游標：moves 是 [出發, 到達, 目標點]，clicks 是按下的時刻；最後才建，疊在所有標註上面
		function cursor(moves, clicks, start) {
			function curAt(t) {
				var p = start;
				for (var i = 0; i < moves.length; i++) {
					var m = moves[i];
					if (t < m[0]) return p;
					if (t < m[1]) { var u = E.io2((t - m[0]) / (m[1] - m[0])); return [lerp(p[0], m[2][0], u), lerp(p[1], m[2][1], u)]; }
					p = m[2];
				}
				return p;
			}

			var ripG = svgEl("g", {}, root);
			var ripples = clicks.map(function (c) {
				var e = svgEl("circle", { r: 10, fill: "rgba(255,255,255,0.18)", stroke: "rgba(255,255,255,0.9)", "stroke-width": 4, opacity: 0 }, ripG);
				return { e: e, t: c };
			});
			var cur = svgEl("g", {}, root);
			path(cur, "M 0 0 L 0 32 L 8.5 24.5 L 14.5 38 L 20 35.5 L 14 22.5 L 25 22.5 Z", "#000000", 2, "#ffffff");
			ups.push(function (t) {
				var p = curAt(t), press = 1;
				for (var i = 0; i < clicks.length; i++) {
					var dt = t - clicks[i];
					if (dt >= 0 && dt < 0.16) { press = 0.88; break; }
				}
				cur.setAttribute("transform", "translate(" + p[0].toFixed(1) + "," + p[1].toFixed(1) + ") scale(" + press + ")");
				ripples.forEach(function (rp) {
					var u = pr(t, rp.t, 0.4);
					if (u <= 0 || u >= 1) { setOp(rp.e, 0); }
					else { rp.e.setAttribute("cx", p[0].toFixed(1)); rp.e.setAttribute("cy", p[1].toFixed(1)); rp.e.setAttribute("r", (10 + 36 * u).toFixed(1)); setOp(rp.e, (1 - u) * 0.9); }
				});
			});
		}

		// 粉筆外框與底座
		function frame() {
			var fx = scr.x - 10, fy = scr.y - 10, fw = scr.w + 20, fh = scr.h + 14;
			S(P, G.rect(fx, fy, fw, fh), "w", 6, tIn, 0.4, NOSP);
			var sx = scr.x + scr.w / 2, sy = scr.y + scr.h + 4;
			S(P, G.line(sx - 34, sy, sx - 48, sy + 8, 1) + " " + G.line(sx + 34, sy, sx + 48, sy + 8, 1) + " " + G.line(sx - 120, sy + 9, sx + 120, sy + 9, 1), "w", 5, tIn + 0.38, 0.17, NOSP);
			api.K.park(tIn + 0.58, P, 8, scr.y + scr.h + 6, "w");
		}

		return { P: P, SW: SW, SH: SH, tIn: tIn, pr: pr, E: E, lerp: lerp, VS: VS, ANN: ANN, svgEl: svgEl, rect: rect, text: text, path: path, tw: tw, setOp: setOp, vis: vis,
			L: L, BOX: BOX, box: box, mock: mock, root: root, ups: ups, tabsS1: tabsS1, tabsS2: tabsS2, codeS1: codeS1, codeS2: codeS2, sel: sel,
			playG: playG, stopG: stopG, tabTxt: tabTxt, tabLine: tabLine, ptabs: ptabs, gearHot: gearHot, typedText: typedText, annG: annG, annRing: annRing, annBand: annBand,
			cursor: cursor, frame: frame };
	}

	// ==================== 開場電腦畫面：第 1–4 句（先讓學生認出「這就是我遇到的」，原因再交給黑板） ====================
	var openBeat = (function () {
		var scr = api.screen && api.screen(0);
		if (!scr) return null;
		var M = vscodeMock(scr, { files: [["score.c", 1], ["hello.c", 1]], sel: ["score.c"], tabs: ["score.c", "hello.c"] });
		var L = M.L, BOX = M.BOX, D = api.drawAt, pr = M.pr, setOp = M.setOp, tw = M.tw;
		// 片頭第一格就在螢幕裡（index.html 的鏡頭）；鏡頭離開後收掉，之後路過這一格只剩粉筆螢幕框
		var last = scr.lines[scr.lines.length - 1], tGone = api.lineStart(last + 1);
		M.ups.push(function (t) { setOp(M.root, (scr.tIn + 0.4 <= 0 ? 1 : pr(t, scr.tIn + 0.4, 0.3)) * (t < tGone ? 1 : 0)); });
		// 只開 score.c：另一個分頁的程式藏起來
		setOp(M.tabsS2, 0); setOp(M.codeS2, 0);

		function codeBox(i, str) {
			var x = L.editX0 + 100 + tw("    ", L.codeSize, true), y = L.codeY0 + i * L.codePitch + 3, w = tw(str, L.codeSize, true);
			return { x: x, y: y, w: w, h: 36, cx: x + w / 2, cy: y + 18 };
		}
		// 第 1 句：「輸入成績」螢光筆 printf 那行，「印出來」螢光筆最後一行 printf（CODE_S1 第 4、6 行）
		var T1 = { prompt: api.span(1, "輸入成績").start, print: api.span(1, "印出來").start, out: api.lineEnd(1) + 0.3 };
		M.annBand(codeBox(4, "printf(\"請輸入成績: \");"), T1.prompt, 0, 0.4, T1.out);
		M.annBand(codeBox(6, "printf(\"你的成績是 %d\\n\", score);"), T1.print, 0, 0.4, T1.out);
		// 第 2 句：游標先到 ▶；「三角形」紅圈，「跑跑看」按下，▶ 換成紅色方塊（程式執行中）
		var T2 = { tri: api.span(2, "三角形").start, click: api.span(2, "跑跑看").start };
		M.annRing(BOX.runBtn, 8, 2.2, T2.tri, T2.click + 0.4, 0.28);
		M.ups.push(function (t) { var on = t >= T2.click + 0.05; setOp(M.stopG, on ? 1 : 0); setOp(M.playG, on ? 0 : 1); });
		// 第 3 句：輸出面板只有 [Running] 一行，提示字沒出來；「Running」紅圈留到第 4 句講完
		var T3 = { run: D(3) + 0.25, ring: api.span(3, "Running").start };
		var outG = M.svgEl("g", {}, M.mock);
		var runLine = "[Running] cd \"c:\\Users\\student\\c_homework\\\" && …";
		M.text(outG, L.outX, L.outBase(0), L.outSize, "#3794ff", "[Running]", { mono: true });
		M.text(outG, L.outX + tw("[Running] ", L.outSize, true), L.outBase(0), L.outSize, M.VS.ctl, runLine.slice(10), { mono: true });
		M.vis(outG, T3.run, null, 0.01);
		var runB = M.box("openRun", L.outX, L.outBase(0) - 28, tw("[Running]", L.outSize, true), 38);
		M.annRing(runB, 14, 3.3, T3.ring, api.lineEnd(last) + 0.3, 0.3);

		M.cursor([[D(2), D(2) + 0.8, [BOX.runBtn.cx, BOX.runBtn.cy]]], [T2.click], [L.editX0 + 760, L.titleH + L.tabH + 200]);
		M.frame();
		return function (t) { for (var i = 0; i < M.ups.length; i++) M.ups[i](t); };
	})();

	// ==================== 電腦畫面段：第 22–36 句 ====================
	var screenBeat = (function () {
		var scr = api.screen && api.screen(1);
		if (!scr) return null;
		var M = vscodeMock(scr, { files: [["score.c", 1], ["score.exe", 0], ["score_fflush.c", 1], ["score_fflush.exe", 0], ["hello.c", 1]], sel: ["score_fflush.c", "score.c"], tabs: ["score.c", "score_fflush.c", "hello.c"] });
		var P = M.P, SW = M.SW, SH = M.SH, tIn = M.tIn, pr = M.pr, E = M.E, lerp = M.lerp, VS = M.VS, ANN = M.ANN, svgEl = M.svgEl, rect = M.rect, text = M.text, path = M.path,
			tw = M.tw, setOp = M.setOp, vis = M.vis, L = M.L, BOX = M.BOX, box = M.box, mock = M.mock, root = M.root, ups = M.ups, tabsS1 = M.tabsS1, tabsS2 = M.tabsS2,
			codeS1 = M.codeS1, codeS2 = M.codeS2, selS2 = M.sel["score_fflush.c"], selS1 = M.sel["score.c"], playG = M.playG, stopG = M.stopG, tabTxt = M.tabTxt, tabLine = M.tabLine,
			ptabs = M.ptabs, gearHot = M.gearHot, typedText = M.typedText, annG = M.annG, annRing = M.annRing, annBand = M.annBand;

		// ---------- 時間點：先畫後講，動作都排在該句的 lead 裡，開口後只剩點名 ----------
		var D = api.drawAt;
		// 第 22 句：按 ▶、輸出面板出現 Running 與提示字
		var T22 = { click: D(22) + 0.5, prompt: D(22) + 0.85, shown: api.span(22, "提示字").start };
		// 第 23 句：游標到輸出面板、打字、跳出唯讀提示框；「唯讀」才圈
		var T23 = { click: D(23) + 0.3, key1: D(23) + 0.65, key2: D(23) + 0.85, bubble: D(23) + 0.95, ring: api.span(23, "唯讀").start };
		// 第 25 句：游標到紅色方塊、按下、程式停掉；「紅色方塊」才圈
		var T25 = { box: api.span(25, "紅色方塊").start, stop: D(25) + 0.9 };
		ups.push(function (t) { var on = t >= T22.click + 0.05 && t < T25.stop + 0.05; setOp(stopG, on ? 1 : 0); setOp(playG, on ? 0 : 1); });
		// 第 27 句：紅色小提醒，講到「失敗」時補上 ✗ 與 Permission denied
		var T27 = { no: api.span(27, "沒停掉").start, next: api.span(27, "下次編譯").start, fail: api.span(27, "失敗").start };
		// 第 29 句：終端機分頁螢光筆
		var T29 = { term: api.span(29, "終端機").start };
		// 第 30 句：點齒輪、選設定、設定視窗打開
		var T30 = { gear: D(30) + 0.65, set: D(30) + 1.3, ring: api.span(30, "齒輪").start };
		// 第 31 句：點搜尋框、打 run in terminal
		var T31 = { box: D(31) + 0.5, run: D(31) + 0.75, inn: D(31) + 1.05, term: D(31) + 1.25, termEnd: D(31) + 1.65, ring: api.span(31, "搜尋框").start };
		// 第 32 句：游標到勾選框、打勾
		var T32 = { check: D(32) + 0.9, hl0: api.at(32, "Code"), hl1: api.span(32, "Terminal").end, ring: api.span(32, "打勾").start };
		// 第 34 句：關設定視窗、點 s1 分頁、按 ▶
		var T34 = { close: D(34) + 0.5, tab: D(34) + 0.9, run: D(34) + 1.3 };
		// 第 35 句：終端機分頁打開、提示字出來
		var T35 = { sw: D(35) + 0.05, prompt: D(35) + 0.5, shown: api.span(35, "提示字").start };
		// 第 36 句：打 5、Enter、結果出來
		var T36 = { five: D(36) + 0.6, enter: D(36) + 1.1, result: D(36) + 1.3, done: api.span(36, "結果").start };

		var tScr = tIn + 0.4;
		ups.push(function (t) { setOp(root, pr(t, tScr, 0.3)); });

		// ---------- 輸出面板內容 ----------
		var outG = svgEl("g", {}, mock), termG = svgEl("g", {}, mock);
		var runLine = "[Running] cd \"c:\\Users\\student\\c_homework\\\" && …";
		text(outG, L.outX, L.outBase(0), L.outSize, "#3794ff", "[Running]", { mono: true });
		text(outG, L.outX + tw("[Running] ", L.outSize, true), L.outBase(0), L.outSize, VS.ctl, runLine.slice(10), { mono: true });
		var promptStr = "請輸入成績: ", promptW = tw(promptStr, L.outSize, true);
		var promptEl = text(outG, L.outX, L.outBase(2), L.outSize, "#3794ff", "", { mono: true });
		var promptTimes = Array.from(promptStr).map(function (c, i, a) { return T22.prompt + 0.45 * i / a.length; });
		box("outPrompt", L.outX, L.outBase(2) - 28, promptW, 38);
		var outCursor = rect(outG, L.outX + promptW + 2, L.outBase(2) - 26, 12, 34, "#3794ff");

		var tSwitch = T35.sw;
		vis(outG, T22.click, T34.run + 0.05, 0.01, 0.15);
		typedText(promptEl, promptStr, promptTimes);
		var blink = function (t) { return Math.floor(t * 2) % 2 === 0 ? 1 : 0; };
		ups.push(function (t) { setOp(outCursor, t >= promptTimes[promptTimes.length - 1] && t < T25.stop ? blink(t) : 0); });
		var doneSegs = [["[Done]", "#3794ff"], [" exited with code=1", "#f14c4c"], [" in 11.243 seconds", "#3794ff"]], doneAcc = "";
		var doneN = doneSegs.reduce(function (n, sg) { return n + Array.from(sg[0]).length; }, 0);
		doneSegs.forEach(function (sg, k) {
			var off = Array.from(doneAcc).length, el = text(outG, L.outX + tw(doneAcc, L.outSize, true), L.outBase(4), L.outSize, sg[1], "", { mono: true });
			typedText(el, sg[0], Array.from(sg[0]).map(function (c, i) { return T25.stop + 0.4 * (off + i) / doneN; }));
			doneAcc += sg[0];
		});

		// 提示框
		var tipText = "無法在唯讀編輯器中編輯", tipW = tw(tipText, 28) + 44, tipH = 48;
		var tipX = L.outX + promptW + 48, tipY = L.outBase(2) - 10 - tipH / 2;
		var tipG = svgEl("g", {}, outG);
		rect(tipG, tipX, tipY, tipW, tipH, VS.tip, { rx: 6, stroke: "#9a9a9a", "stroke-width": 1.5 });
		path(tipG, "M " + (tipX + 1) + " " + (tipY + tipH / 2 - 10) + " L " + (tipX - 16) + " " + (tipY + tipH / 2) + " L " + (tipX + 1) + " " + (tipY + tipH / 2 + 10) + " Z", "none", 0, VS.tip);
		text(tipG, tipX + 22, tipY + 33, 28, VS.tipFg, tipText);
		box("tip", tipX, tipY, tipW, tipH);
		var tipOut = D(25) + 0.3;
		vis(tipG, T23.bubble, tipOut, 0.12, 0.25);

		// 終端機內容
		var psStr = "PS C:\\Users\\student\\c_homework> ", psW = tw(psStr, L.outSize, true);
		var cmdEl = text(termG, L.outX, L.outBase(0), L.outSize, VS.fg, "", { mono: true });
		var cmdFull = psStr + "cd \"c:\\Users\\student\\…";
		var cmdTimes = Array.from(cmdFull).map(function (c, i, a) { return tSwitch + 0.05 + 0.3 * i / a.length; });
		typedText(cmdEl, cmdFull, cmdTimes);
		var tPromptEl = text(termG, L.outX, L.outBase(1), L.outSize, VS.fg, "", { mono: true });
		var tpTimes = Array.from(promptStr).map(function (c, i, a) { return T35.prompt + 0.4 * i / a.length; });
		typedText(tPromptEl, promptStr, tpTimes);
		var fiveEl = text(termG, L.outX + promptW, L.outBase(1), L.outSize, VS.fg, "85", { mono: true });
		var resStr = "你的成績是 85", resEl = text(termG, L.outX, L.outBase(2), L.outSize, VS.fg, "", { mono: true });
		typedText(resEl, resStr, Array.from(resStr).map(function (c, i, a) { return T36.result + 0.3 * i / a.length; }));
		var resW = tw(resStr, L.outSize, true);
		var ps2 = text(termG, L.outX, L.outBase(3), L.outSize, VS.fg, psStr, { mono: true });
		var tCur = rect(termG, L.outX + promptW + 2, L.outBase(1) - 26, 12, 34, "#ffffff");
		var tCur2 = rect(termG, L.outX + psW + 2, L.outBase(3) - 26, 12, 34, "#ffffff");
		ups.push(function (t) {
			setOp(fiveEl, t >= T36.five ? 1 : 0);
			setOp(ps2, t >= T36.result + 0.35 ? 1 : 0);
			var x1 = L.outX + promptW + 2 + (t >= T36.five ? tw("85", L.outSize, true) : 0);
			if (tCur.__x !== x1) { tCur.__x = x1; tCur.setAttribute("x", x1); }
			setOp(tCur, t >= tpTimes[tpTimes.length - 1] && t < T36.enter ? blink(t) : 0);
			setOp(tCur2, t >= T36.result + 0.35 ? blink(t) : 0);
		});
		box("termRes", L.outX, L.outBase(2) - 28, resW, 38);
		vis(termG, tSwitch, null, 0.01);

		// 分頁標籤切換
		ups.push(function (t) {
			var u = E.io2(pr(t, tSwitch, 0.25)), a = ptabs[1], b = ptabs[3];
			var x = lerp(a.x, b.x, u), w = lerp(a.w, b.w, u);
			tabLine.setAttribute("x", x.toFixed(1)); tabLine.setAttribute("width", w.toFixed(1));
			tabTxt[1].setAttribute("fill", u > 0.5 ? VS.dim : VS.actOn);
			tabTxt[3].setAttribute("fill", u > 0.5 ? VS.actOn : VS.dim);
		});

		// 換回 score.c
		[tabsS2, codeS2, selS2].forEach(function (g) { vis(g, 0, T34.tab, 0.01, 0.01); });
		[tabsS1, codeS1, selS1].forEach(function (g) { vis(g, T34.tab, null, 0.01); });

		// ---------- 齒輪選單 ----------
		var menuItems = [["命令選擇區...", "Ctrl+Shift+P"], ["設定檔", ""], ["設定", "Ctrl+,"], ["延伸模組", "Ctrl+Shift+X"], ["鍵盤快速鍵", "Ctrl+K Ctrl+S"], ["程式碼片段", ""], ["工作", ""]];
		var mRow = 46, mPad = 8, mSep = 12, mW = 470;
		var mH = menuItems.length * mRow + mSep + mPad * 2;
		var mX = L.actW + 6, mY = BOX.gear.y - 12 - mH;
		var menuG = svgEl("g", {}, mock);
		rect(menuG, mX, mY, mW, mH, VS.menu, { rx: 8, stroke: VS.menuLine, "stroke-width": 1.5 });
		var menuHot = rect(menuG, mX + 8, 0, mW - 16, mRow, VS.hover, { rx: 5 });
		menuItems.forEach(function (it, i) {
			var iy = mY + mPad + i * mRow + (i > 0 ? mSep : 0);
			if (i === 2) { menuHot.setAttribute("y", iy); box("menuSet", mX + 8, iy, mW - 16, mRow); }
			text(menuG, mX + 28, iy + 33, L.ui, VS.fg, it[0]);
			if (it[1]) text(menuG, mX + mW - 28, iy + 33, L.ui, VS.dim, it[1], { anchor: "end" });
			if (i === 0) rect(menuG, mX + 12, iy + mRow + mSep / 2 - 0.5, mW - 24, 1.5, VS.menuLine);
		});
		var tMenu = T30.gear + 0.05, tMenuOut = T30.set + 0.06;
		vis(menuG, tMenu, tMenuOut, 0.16, 0.1);
		vis(menuHot, T30.set - 0.14, null, 0.05);
		ups.push(function (t) { setOp(gearHot, pr(t, T30.gear - 0.1, 0.05) * (1 - pr(t, T30.set, 0.1))); });

		// ---------- 設定視窗 ----------
		var W = { x: 120, y: L.titleH + 40, w: SW - 240 };
		W.h = L.bodyY1 - W.y - 24;
		W.titleH = 58;
		var winG = svgEl("g", {}, mock);
		var winIn = svgEl("g", {}, winG);
		rect(winIn, W.x + 6, W.y + 8, W.w, W.h, "rgba(0,0,0,0.45)", { rx: 12 });
		rect(winIn, W.x, W.y, W.w, W.h, VS.win, { rx: 12, stroke: VS.menuLine, "stroke-width": 1.5 });
		path(winIn, "M " + W.x + " " + (W.y + W.titleH) + " V " + (W.y + 12) + " Q " + W.x + " " + W.y + " " + (W.x + 12) + " " + W.y + " H " + (W.x + W.w - 12) + " Q " + (W.x + W.w) + " " + W.y + " " + (W.x + W.w) + " " + (W.y + 12) + " V " + (W.y + W.titleH) + " Z", "none", 0, VS.winTitle);
		path(winIn, "M " + (W.x + 24) + " " + (W.y + 22) + " h 18 M " + (W.x + 24) + " " + (W.y + 36) + " h 18 M " + (W.x + 30) + " " + (W.y + 18) + " v 8 M " + (W.x + 36) + " " + (W.y + 32) + " v 8", VS.fg, 2.5);
		text(winIn, W.x + 58, W.y + 38, 28, VS.fg, "設定", { bold: true });
		var closeBox = box("closeX", W.x + W.w - 62, W.y + 8, 44, 44);
		path(winIn, "M " + (closeBox.cx - 9) + " " + (closeBox.cy - 9) + " l 18 18 m 0 -18 l -18 18", VS.fg, 3);

		// 搜尋框
		var SB = { x: W.x + 32, y: W.y + W.titleH + 22, w: W.w - 64, h: 62 };
		var sbBox = rect(winIn, SB.x, SB.y, SB.w, SB.h, VS.input, { rx: 6, stroke: VS.inputLine, "stroke-width": 2 });
		box("searchBox", SB.x, SB.y, SB.w, SB.h);
		var searchFull = "run in terminal", searchSize = 30, searchBase = SB.y + SB.h / 2 + 10;
		var holder = text(winIn, SB.x + 20, searchBase, searchSize, VS.dim, "搜尋設定");
		var searchEl = text(winIn, SB.x + 20, searchBase, searchSize, VS.fg, "");
		var caret = rect(winIn, SB.x + 20, SB.y + 12, 2.5, SB.h - 24, VS.fg);
		var sTimes = [];
		[["run ", T31.run, T31.inn], ["in ", T31.inn, T31.term], ["terminal", T31.term, T31.termEnd]].forEach(function (pt) {
			var n = Array.from(pt[0]).length;
			for (var i = 0; i < n; i++) sTimes.push(pt[1] + (pt[2] - pt[1]) * i / n);
		});
		var sW = [0];
		for (var si = 1; si <= searchFull.length; si++) sW.push(tw(searchFull.slice(0, si), searchSize));
		typedText(searchEl, searchFull, sTimes);
		var tRes = sTimes[2] + 0.12;
		var found = text(winIn, SB.x + SB.w - 24, searchBase - 2, L.ui, VS.dim, "找到 15 項設置", { anchor: "end" });
		ups.push(function (t) {
			var n = 0;
			for (var i = 0; i < sTimes.length; i++) { if (sTimes[i] <= t) n = i + 1; else break; }
			setOp(holder, n === 0 ? 1 : 0);
			var focus = t >= T31.box && t < T34.close;
			sbBox.setAttribute("stroke", focus ? VS.link : VS.inputLine);
			var cx = SB.x + 20 + sW[n];
			if (caret.__x !== cx) { caret.__x = cx; caret.setAttribute("x", cx.toFixed(1)); }
			setOp(caret, focus ? blink(t) : 0);
			setOp(found, pr(t, tRes, 0.12));
		});

		// 使用者 / 工作區
		var tabsY = SB.y + SB.h + 18;
		rect(winIn, SB.x, tabsY, 110, 44, VS.accent, { rx: 6 });
		text(winIn, SB.x + 55, tabsY + 31, L.ui, "#ffffff", "使用者", { anchor: "middle" });
		text(winIn, SB.x + 134, tabsY + 31, L.ui, VS.link, "工作區");
		var mainTop = tabsY + 44 + 24, treeW = 320;
		path(winIn, "M " + (SB.x + treeW + 20) + " " + mainTop + " V " + (W.y + W.h - 24), VS.link, 2);
		var main = { x: SB.x + treeW + 60, w: W.w - treeW - 130 };

		var preG = svgEl("g", {}, winIn), resG = svgEl("g", {}, winIn);
		["經常使用的", "文字編輯器", "工作台", "視窗", "聊天", "功能", "應用程式", "延伸模組"].forEach(function (nm, i) {
			text(preG, SB.x + (i ? 36 : 24), mainTop + 32 + i * 44, L.ui, i ? VS.link : VS.fg, (i ? "› " : "") + nm);
		});
		text(preG, main.x, mainTop + 48, 44, VS.fg, "經常使用的", { bold: true });
		var pi = mainTop + 120;
		text(preG, main.x, pi, 30, VS.link, "Editor:"); text(preG, main.x + tw("Editor: ", 30), pi, 30, VS.fg, "Font Size", { bold: true });
		text(preG, main.x + 40, pi + 40, L.ui, VS.link, "控制字型大小 (像素)。");
		rect(preG, main.x, pi + 60, 300, 52, VS.input, { rx: 5, stroke: VS.inputLine, "stroke-width": 2 });
		text(preG, main.x + 18, pi + 96, 30, VS.fg, "12");
		var pj = pi + 170;
		text(preG, main.x, pj, 30, VS.link, "Files:"); text(preG, main.x + tw("Files: ", 30), pj, 30, VS.fg, "Auto Save", { bold: true });
		text(preG, main.x + 40, pj + 40, L.ui, VS.link, "控制具有未儲存變更之編輯器的 自動儲存。");
		rect(preG, main.x, pj + 60, 420, 52, VS.input, { rx: 5, stroke: VS.inputLine, "stroke-width": 2 });
		text(preG, main.x + 18, pj + 96, 30, VS.fg, "afterDelay");

		[["聊天 (4)", 0], ["工具 (4)", 1], ["功能 (3)", 0], ["終端機 (3)", 1], ["延伸模組 (5)", 0]].forEach(function (nm, i) {
			text(resG, SB.x + 24 + nm[1] * 30, mainTop + 32 + i * 44, L.ui, VS.link, nm[0]);
		});
		var it1 = mainTop + 52, itPitch = 134;
		var rowSel = rect(resG, main.x - 18, it1 - 42, main.w + 18, 112, "#2a2d2e", { rx: 8 });
		var items = [["Code-runner:", " Run In Terminal"], ["Verilog:", " Run In Terminal"]];
		items.forEach(function (it, i) {
			var by = it1 + i * itPitch;
			text(resG, main.x, by, 30, VS.link, it[0]);
			text(resG, main.x + tw(it[0], 30), by, 30, VS.fg, it[1], { bold: true });
			rect(resG, main.x, by + 18, 32, 32, VS.input, { rx: 5, stroke: "#6b6b6b", "stroke-width": 2 });
			text(resG, main.x + 52, by + 45, L.ui, VS.link, "Whether to run code in Integrated Terminal.");
		});
		var titleW = tw(items[0][0], 30) + tw(items[0][1], 30, false, true);
		box("title1", main.x, it1 - 30, titleW, 40);
		var chkBox = box("chk", main.x, it1 + 18, 32, 32);
		var chkFill = rect(resG, chkBox.x, chkBox.y, 32, 32, VS.accent, { rx: 5 });
		var chkMark = path(resG, "M " + (chkBox.x + 7) + " " + (chkBox.y + 17) + " L " + (chkBox.x + 14) + " " + (chkBox.y + 24) + " L " + (chkBox.x + 26) + " " + (chkBox.y + 8), "#ffffff", 4);
		var chkLen = chkMark.getTotalLength();
		chkMark.style.strokeDasharray = chkLen + " " + chkLen;
		ups.push(function (t) {
			setOp(preG, 1 - pr(t, tRes, 0.05));
			setOp(resG, pr(t, tRes, 0.05));
			setOp(rowSel, pr(t, T32.check, 0.1));
			setOp(chkFill, t >= T32.check + 0.03 ? 1 : 0);
			chkMark.style.strokeDashoffset = (chkLen * (1 - pr(t, T32.check + 0.04, 0.16))).toFixed(1);
			setOp(chkMark, t >= T32.check + 0.04 ? 1 : 0);
		});

		var tWin = T30.set + 0.08, tWinOut = T34.close + 0.05;
		ups.push(function (t) {
			var a = pr(t, tWin, 0.22), b = 1 - pr(t, tWinOut, 0.16), u = E.o3(a), sc = 0.96 + 0.04 * u;
			winIn.setAttribute("transform", "translate(" + (W.x + W.w / 2) + " " + (W.y + W.h / 2) + ") scale(" + sc.toFixed(4) + ") translate(" + (-(W.x + W.w / 2)) + " " + (-(W.y + W.h / 2)) + ")");
			setOp(winG, a * b);
		});


		// 第 22 句：提示字螢光筆
		annBand(BOX.outPrompt, T22.shown, 0, 0.4, D(23) + 0.2);
		// 第 23 句：唯讀提示框紅圈
		annRing(BOX.tip, 26, 3.1, T23.ring, tipOut, 0.3);
		// 第 25 句：紅色方塊紅圈
		annRing(BOX.stopBtn, 8, 4.4, T25.box, api.lineEnd(25) + 0.4, 0.28);
		// 第 27 句：紅色小提醒與 Permission denied
		var noteStr = "沒停 → 下次編譯 Permission denied", noteSize = 26, noteW = Math.round(tw(noteStr, noteSize) * 0.95) + 96, noteX = SW - 30 - noteW, noteY = L.panelY + 132;
		var noteG = svgEl("g", {}, root), noteOut = api.lineEnd(29) + 0.1;
		rect(noteG, noteX, noteY, noteW, 72, "rgba(255,75,62,0.12)", { rx: 10, stroke: ANN.red, "stroke-width": 3 });
		var noteX0 = noteX + 28, noteY0 = noteY + 22;
		var noteCross = path(noteG, "M " + noteX0 + " " + noteY0 + " l 28 28 m 0 -28 l -28 28", ANN.red, 6);
		var ncl = noteCross.getTotalLength();
		noteCross.style.strokeDasharray = ncl + " " + ncl;
		var noteEl = text(noteG, noteX + 70, noteY + 46, noteSize, ANN.red, "");
		var notePart = [["沒停 → ", T27.no, T27.next - 0.05], ["下次編譯 ", T27.next, T27.fail - 0.05], ["Permission denied", T27.fail, api.lineEnd(27) - 0.1]];
		var noteTimes = [];
		notePart.forEach(function (pt) {
			var n = Array.from(pt[0]).length;
			for (var q = 0; q < n; q++) noteTimes.push(pt[1] + (pt[2] - pt[1]) * q / n);
		});
		typedText(noteEl, notePart.map(function (pt) { return pt[0]; }).join(""), noteTimes);
		ups.push(function (t) {
			noteCross.style.strokeDashoffset = (ncl * (1 - E.o2(pr(t, T27.fail, 0.25)))).toFixed(1);
			setOp(noteCross, t < T27.fail ? 0 : 1);
			setOp(noteG, pr(t, T27.no, 0.15) * (1 - pr(t, noteOut, 0.25)));
		});

		// 第 29 句：終端機分頁螢光筆
		annBand(BOX.ptabTerm, T29.term, 0, 0.3, api.lineEnd(29) + 0.2);
		// 第 30 句：齒輪紅圈
		annRing(BOX.gear, 4, 5.7, T30.ring, api.lineEnd(30) + 0.2, 0.28);
		// 第 31 句：搜尋框紅圈
		annRing(BOX.searchBox, 16, 7.3, T31.ring, api.lineEnd(31) + 0.3, 0.4);
		// 第 32 句：標題螢光筆底線從 Code Runner 掃到 Terminal，打勾處紅圈
		annBand(BOX.title1, T32.hl0, 0, T32.hl1 - T32.hl0, api.lineEnd(32) + 0.3);
		annRing(BOX.chk, 20, 9.9, T32.ring, api.lineEnd(32) + 0.3, 0.25);
		// 第 35–36 句：終端機提示字螢光筆、結果綠勾
		var tp = { x: L.outX, y: L.outBase(1) - 28, w: promptW, h: 38 };
		annBand(tp, T35.shown, 0, 0.4, T36.five);
		var gk = { x: BOX.termRes.x + resW + 44, y: L.outBase(2) - 34, s: 40 };
		var gchk = path(annG, "M " + gk.x + " " + (gk.y + gk.s * 0.5) + " L " + (gk.x + gk.s * 0.38) + " " + (gk.y + gk.s * 0.9) + " L " + (gk.x + gk.s) + " " + gk.y, ANN.green, 7);
		var gl = gchk.getTotalLength();
		gchk.style.strokeDasharray = gl + " " + gl;
		ups.push(function (t) { gchk.style.strokeDashoffset = (gl * (1 - E.o2(pr(t, T36.done, 0.3)))).toFixed(1); setOp(gchk, t < T36.done ? 0 : 1); });

		// ---------- 游標與點擊 ----------
		var outPt = [BOX.outPrompt.cx, BOX.outPrompt.cy];
		var moves = [
			[D(22), T22.click - 0.06, [BOX.runBtn.cx, BOX.runBtn.cy]],
			[D(23), T23.click - 0.06, outPt],
			[D(25), T25.stop - 0.06, [BOX.stopBtn.cx, BOX.stopBtn.cy]],
			[D(30), T30.gear - 0.06, [BOX.gear.cx, BOX.gear.cy]],
			[T30.gear + 0.14, T30.set - 0.05, [BOX.menuSet.x + 130, BOX.menuSet.cy]],
			[D(31), T31.box - 0.06, [SB.x + 170, SB.y + SB.h / 2]],
			[D(32), T32.check - 0.06, [BOX.chk.cx, BOX.chk.cy]],
			[D(34), T34.close - 0.05, [BOX.closeX.cx, BOX.closeX.cy]],
			[T34.close + 0.12, T34.tab - 0.05, [BOX.tabS1.cx, BOX.tabS1.cy]],
			[T34.tab + 0.15, T34.run - 0.05, [BOX.runBtn.cx, BOX.runBtn.cy]],
			[D(36), T36.five - 0.2, [SW - 260, L.panelY + 190]],
		];

		var clicks = [T22.click, T23.click, T25.stop, T30.gear, T30.set, T31.box, T32.check, T34.close, T34.tab, T34.run];
		[T23.key1, T23.key2].concat(sTimes, [T36.five, T36.enter]).forEach(function (k) { api.mark("key", k); });
		M.cursor(moves, clicks, [L.editX0 + 760, L.titleH + L.tabH + 200]);
		M.frame();

		return function (t) { for (var i = 0; i < ups.length; i++) ups[i](t); };
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
		render: function (t) {
			if (openBeat) openBeat(t);
			if (screenBeat) screenBeat(t);
		},
	};
};
