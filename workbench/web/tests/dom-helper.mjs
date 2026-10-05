export class Element extends EventTarget {
	constructor(tag, doc) {
		super();
		this.tagName = tag;
		this.ownerDocument = doc;
		this.children = [];
		this.attributes = new Map();
		this.className = '';
		this.hidden = false;
		this.style = {};
	}
	set textContent(value) { this.copy = String(value); this.children = []; }
	get textContent() { return (this.copy ?? '') + this.children.map(node => node.textContent).join(''); }
	append(...nodes) { for (const node of nodes) { node.parentElement = this; this.children.push(node); } }
	replaceChildren(...nodes) { this.copy = ''; this.children = []; this.append(...nodes); }
	setAttribute(key, value) { this.attributes.set(key, String(value)); }
	getAttribute(key) { return this.attributes.get(key) ?? null; }
	removeAttribute(key) { this.attributes.delete(key); }
	querySelectorAll(selector) {
		return descendants(this).slice(1).filter(node => selector.startsWith('[')
			? node.attributes.has(selector.slice(1, -1)) : node.tagName === selector);
	}
	querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
	getBoundingClientRect() { return { width: 800, height: 400, left: 0, top: 0 }; }
	focus() { this.ownerDocument.activeElement = this; }
	pause() { this.paused = true; }
	load() {}
}

export const descendants = node => [node, ...node.children.flatMap(descendants)];
export const settle = () => new Promise(resolve => setImmediate(resolve));
export const click = node => node.dispatchEvent(new Event('click'));

export async function withDOM(run) {
	const original = { document: globalThis.document, location: globalThis.location, fetch: globalThis.fetch };
	const doc = Object.assign(new EventTarget(), { hidden: false });
	doc.createElement = tag => new Element(tag, doc);
	doc.createElementNS = (namespace, tag) => Object.assign(new Element(tag, doc), { namespaceURI: namespace });
	globalThis.document = doc;
	globalThis.location = { search: '', hash: '' };
	try { await run(doc); }
	finally {
		for (const [key, value] of Object.entries(original)) {
			if (value === undefined) delete globalThis[key];
			else globalThis[key] = value;
		}
	}
}
