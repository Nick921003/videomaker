// 仿真皮膚：繪圖指令 → SVG 字串（黑板片的電腦畫面、文章配圖）。顏色從主題檔查，這裡不寫任何色碼。
(function (g) {
	'use strict';
	var SANS = "'Huninn', sans-serif";
	var MONO = "'JetBrains Mono', 'Huninn', monospace";

	function color(theme, key) {
		var v = key.split('.').reduce(function (o, k) { return o && o[k]; }, theme);
		if (typeof v !== 'string') throw new Error('vscode 主題缺 ' + key);
		return v;
	}
	var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); };
	var n = function (v) { return (Math.round(v * 10) / 10).toString(); };

	function render(ops, theme, size) {
		var out = ['<svg xmlns="http://www.w3.org/2000/svg" width="' + size[0] + '" height="' + size[1] + '" viewBox="0 0 ' + size[0] + ' ' + size[1] + '">'];
		ops.forEach(function (o) {
			var op = o.alpha != null && o.alpha < 1 ? ' opacity="' + n(Math.max(0, o.alpha)) + '"' : '';
			if (o.op === 'rect') {
				out.push('<rect x="' + n(o.x) + '" y="' + n(o.y) + '" width="' + n(o.w) + '" height="' + n(o.h) + '"' +
					(o.rx ? ' rx="' + n(o.rx) + '"' : '') +
					' fill="' + (o.fill ? color(theme, o.fill) : 'none') + '"' +
					(o.stroke ? ' stroke="' + color(theme, o.stroke) + '" stroke-width="' + n(o.width || 1) + '"' : '') + op + '/>');
			} else if (o.op === 'text') {
				var anchor = o.align === 'end' ? 'end' : o.align === 'middle' ? 'middle' : 'start';
				out.push('<text x="' + n(o.x) + '" y="' + n(o.y) + '" font-size="' + n(o.size) + '" font-family="' + (o.mono ? MONO : SANS) + '"' +
					(o.bold ? ' font-weight="600"' : '') + ' text-anchor="' + anchor + '" dominant-baseline="central" fill="' + color(theme, o.color) + '"' +
					' xml:space="preserve"' + op + '>' + esc(o.str) + '</text>');
			} else if (o.op === 'line') {
				var d = o.pts.map(function (p, i) { return (i ? 'L' : 'M') + n(p[0]) + ' ' + n(p[1]); }).join(' ');
				out.push('<path d="' + d + '" fill="none" stroke="' + color(theme, o.color) + '" stroke-width="' + n(o.width) + '" stroke-linecap="round" stroke-linejoin="round"' + op + '/>');
			}
		});
		out.push('</svg>');
		return out.join('');
	}

	var X = { render: render, SANS: SANS, MONO: MONO };
	if (typeof module !== 'undefined') module.exports = X; else g.VSCodeSVG = X;
})(this);
