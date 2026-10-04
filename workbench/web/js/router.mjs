const pages = new Set(['overview', 'make', 'pipelines', 'library', 'usage', 'roadmap']);

export function parseRoute(hash = '') {
	const value = String(hash).replace(/^#/, '');
	const separator = value.indexOf('?');
	const path = separator < 0 ? value : value.slice(0, separator);
	const search = separator < 0 ? '' : value.slice(separator + 1);
	const parts = path.replace(/^\//, '').replace(/\/$/, '').split('/');
	const page = parts[0];
	const valid = pages.has(page) && (page === 'make'
		? parts.length <= 2 && (parts[1] === undefined || /^[1-4]$/.test(parts[1]))
		: parts.length === 1);
	if (!valid) return { page: 'overview', step: null, query: {} };
	return {
		page,
		step: page === 'make' ? Number(parts[1] ?? 1) : null,
		query: Object.fromEntries(new URLSearchParams(search)),
	};
}

export function go(page, step, query = {}) {
	const route = parseRoute(`#/${page}${page === 'make' ? `/${step ?? 1}` : ''}`);
	const params = new URLSearchParams();
	for (const [key, value] of Object.entries(query)) {
		if (value !== null && value !== undefined) params.set(key, String(value));
	}
	const search = params.toString();
	const hash = `#/${route.page}${route.step === null ? '' : `/${route.step}`}${search ? `?${search}` : ''}`;
	if (globalThis.location) globalThis.location.hash = hash;
	return hash;
}
