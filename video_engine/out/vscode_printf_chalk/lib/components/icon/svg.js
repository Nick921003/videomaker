// 圖示（仿真皮膚）：strokes → SVG 字串，文章配圖用。等粗線、圓頭圓角，顏色由呼叫端傳入。
// 純字串運算，不碰 DOM；字型留給頁面決定。
(function (g) {
	'use strict';
	var STROKE = 4;
	// 鍵帽內面板（見 shapes.js 的 keycap）：字塞進去，寬度用字元數估
	var FACE = { cx: 50, cy: 45, w: 56, h: 46 };

	function esc(s) {
		return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
	}
	// 一個全形字算 1em，其餘約 0.6em
	function em(text) {
		var w = 0;
		for (var ch of String(text)) w += ch.codePointAt(0) > 0x2e80 ? 1 : 0.6;
		return w;
	}
	function render(name, opts, color, px) {
		var shapes = g.IconShapes || require('./shapes.js'), shape = shapes.strokes(name, opts), body = shape.strokes.map(function (s) {
			var pts = s.pts.map(function (p) { return p[0] + ',' + p[1]; }).join(' ');
			return '<polyline points="' + pts + '"/>';
		}).join('');
		if (shape.text) {
			var size = Math.min(FACE.h * 0.6, FACE.w * 0.84 / em(shape.text));
			body += '<text x="' + FACE.cx + '" y="' + FACE.cy + '" font-size="' + Math.round(size * 100) / 100 +
				'" text-anchor="middle" dominant-baseline="central" stroke="none" fill="' + esc(color) + '">' + esc(shape.text) + '</text>';
		}
		return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="' + px + '" height="' + px +
			'" fill="none" stroke="' + esc(color) + '" stroke-width="' + STROKE + '" stroke-linecap="round" stroke-linejoin="round">' + body + '</svg>';
	}

	var X = { render: render };
	if (typeof module !== 'undefined') module.exports = X; else g.IconSVG = X;
})(this);
