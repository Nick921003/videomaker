function parseXmlDoc(xml, doc) {
	const tagRe = /<(\/?)([a-zA-Z0-9_:-]+)((?:\s+[^=>\s/]+(?:=(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)\s*(\/?)>|([^<]+)/g;
	const attrRe = /([a-zA-Z0-9_:-]+)(?:=(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
	let root = null;
	const stack = [];
	let match;
	while ((match = tagRe.exec(xml)) !== null) {
		const [, isClose, tagName, attrStr, isSelfClose, text] = match;
		if (text) {
			const trimmed = text.trim();
			if (trimmed && stack.length) {
				const current = stack[stack.length - 1];
				current.textContent = (current.textContent || '') + trimmed;
			}
			continue;
		}
		if (!tagName || tagName.startsWith('?') || tagName.startsWith('!')) continue;
		if (isClose) {
			stack.pop();
			continue;
		}
		const node = doc.createElement(tagName);
		if (attrStr) {
			let a;
			while ((a = attrRe.exec(attrStr)) !== null) {
				const val = a[2] ?? a[3] ?? a[4] ?? '';
				node.setAttribute(a[1], val);
			}
		}
		if (!root) root = node;
		if (stack.length) stack[stack.length - 1].append(node);
		if (!isSelfClose) stack.push(node);
	}
	return { documentElement: root, querySelector: () => null };
}

export class Element extends EventTarget {
	constructor(tag, doc) {
		super();
		this.tagName = tag;
		this.localName = String(tag).toLowerCase();
		this.ownerDocument = doc;
		this.children = [];
		this.attributes = new Map();
		this.className = '';
		this.hidden = false;
		this.style = {
			setProperty: (key, value) => { this.style[key] = String(value); },
			getPropertyValue: key => this.style[key] ?? ''
		};
	}
	get childNodes() { return this.children; }
	set textContent(value) { this.copy = String(value); this.children = []; }
	get textContent() { return (this.copy ?? '') + this.children.map(node => node.textContent).join(''); }
	append(...nodes) { for (const node of nodes) {
		if (typeof node === 'string') {
			this.copy = (this.copy ?? '') + node;
			continue;
		}
		if (node.parentElement) node.parentElement.children = node.parentElement.children.filter(child => child !== node);
		node.parentElement = this; this.children.push(node);
	} }
	replaceChildren(...nodes) { this.copy = ''; this.children = []; this.append(...nodes); }
	setAttribute(key, value) {
		this.attributes.set(key, String(value));
		if (key === 'class') this.className = String(value);
	}
	getAttribute(key) { return this.attributes.get(key) ?? null; }
	removeAttribute(key) {
		this.attributes.delete(key);
		if (key === 'class') this.className = '';
	}
	remove() {
		if (this.parentElement) {
			this.parentElement.children = this.parentElement.children.filter(child => child !== this);
			this.parentElement = null;
		}
	}
	matches(selector) {
		if (!selector) return false;
		if (selector.includes(',')) {
			return selector.split(',').some(part => this.matches(part.trim()));
		}
		if (selector === '*') return true;
		if (selector.startsWith('.')) {
			const cls = selector.slice(1);
			return (this.className || '').split(/\s+/).includes(cls);
		}
		if (selector.startsWith('[')) {
			const match = selector.slice(1, -1).match(/^([a-zA-Z0-9_-]+)(?:=([^\s\]]+))?$/);
			if (!match) return this.attributes.has(selector.slice(1, -1));
			const [, key, val] = match;
			if (val === undefined) return this.attributes.has(key);
			return this.attributes.get(key) === val.replace(/^["']|["']$/g, '');
		}
		const tagAttr = selector.match(/^([a-zA-Z0-9_:-]+)\[([a-zA-Z0-9_-]+)(?:=([^\s\]]+))?\]$/);
		if (tagAttr) {
			const [, tag, key, val] = tagAttr;
			if (this.tagName !== tag) return false;
			if (val === undefined) return this.attributes.has(key);
			return this.attributes.get(key) === val.replace(/^["']|["']$/g, '');
		}
		return this.tagName === selector;
	}
	closest(selector) {
		let current = this;
		while (current) {
			if (current.matches?.(selector)) return current;
			current = current.parentElement;
		}
		return null;
	}
	querySelectorAll(selector) {
		return descendants(this).slice(1).filter(node => node.matches?.(selector));
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
	const original = {
		document: globalThis.document,
		location: globalThis.location,
		fetch: globalThis.fetch,
		DOMParser: globalThis.DOMParser
	};
	const doc = Object.assign(new EventTarget(), { hidden: false });
	doc.createElement = tag => new Element(tag, doc);
	doc.createElementNS = (namespace, tag) => Object.assign(new Element(tag, doc), { namespaceURI: namespace });
	doc.importNode = (node, deep) => {
		const clone = el => {
			const next = doc.createElement(el.tagName);
			next.className = el.className;
			next.copy = el.copy;
			for (const [k, v] of el.attributes) next.setAttribute(k, v);
			if (deep) {
				for (const child of el.children) next.append(clone(child));
			}
			return next;
		};
		return clone(node);
	};
	globalThis.document = doc;
	globalThis.location = { search: '', hash: '' };
	globalThis.DOMParser = class DOMParser {
		parseFromString(xml) {
			return parseXmlDoc(xml, doc);
		}
	};
	try { await run(doc); }
	finally {
		for (const [key, value] of Object.entries(original)) {
			if (value === undefined) delete globalThis[key];
			else globalThis[key] = value;
		}
	}
}
