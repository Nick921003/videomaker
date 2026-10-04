export function el(tag, className = '', text = '') {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text) node.textContent = text;
	return node;
}

export function icon(name, className = '') {
	const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
	svg.setAttribute('class', `icon ${className}`.trim());
	svg.setAttribute('aria-hidden', 'true');
	svg.setAttribute('viewBox', '0 0 24 24');
	svg.setAttribute('fill', 'none');
	svg.setAttribute('stroke', 'currentColor');
	svg.setAttribute('stroke-width', '1.5');
	svg.setAttribute('stroke-linecap', 'round');
	svg.setAttribute('stroke-linejoin', 'round');
	const paths = {
		video: 'M4 5h16v14H4z M10 9l5 3-5 3z',
		highlight: 'M4 5h16v14H4z M9 5v14 M4 10h5 M4 14h5 M14 9l3 3-3 3',
		mindmap: 'M12 10V4 M12 14v6 M10 12H4 M14 12h6 M10 10h4v4h-4z M10 2h4v2h-4z M2 10h2v4H2z M20 10h2v4h-2z M10 20h4v2h-4z',
		slides: 'M3 4h18v13H3z M12 17v4 M8 21h8 M7 9h10 M7 12h6',
		arrow: 'M5 12h14 M14 7l5 5-5 5',
		library: 'M4 5h4v15H4z M10 5h4v15h-4z M17 5l4 14-3 1-4-14z',
		pipelines: 'M4 4h6v5H4z M14 15h6v5h-6z M7 9v9h7',
		overview: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
		planned: 'M5 4h14v16H5z M9 9h6 M9 13h6 M9 17h3',
	};
	const path = document.createElementNS(svg.namespaceURI, 'path');
	path.setAttribute('d', paths[name] ?? paths.planned);
	svg.append(path);
	return svg;
}

export const money = value => `US$${value.toFixed(3)}`;
export const displayName = format => format.name.replace(/podcast/i, '對談');

export function intro(kicker, title, description) {
	const node = el('header', 'page-intro');
	const copy = el('div', 'intro-copy');
	copy.append(el('p', 'eyebrow', kicker), el('h1', '', title), el('p', 'intro-description', description));
	node.append(copy);
	return node;
}
