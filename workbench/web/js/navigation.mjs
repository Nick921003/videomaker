const KEY = 'workbench:rail-collapsed';

export function initRail(doc = document, storage) {
	const layout = doc.getElementById('app-layout');
	const toggle = doc.getElementById('rail-toggle');
	if (!layout || !toggle) return;
	let collapsed = false;
	try {
		storage ??= globalThis.localStorage;
		collapsed = storage?.getItem(KEY) === 'true';
	} catch { /* 私密模式仍可使用導覽。 */ }
	for (const link of doc.querySelectorAll('.rail-nav-item')) {
		const name = link.getAttribute('aria-label') || link.textContent.trim();
		link.setAttribute('aria-label', name);
		link.setAttribute('title', name);
	}
	function apply() {
		layout.setAttribute('data-rail', collapsed ? 'collapsed' : 'expanded');
		const name = collapsed ? '展開導覽' : '收合導覽';
		toggle.setAttribute('aria-expanded', String(!collapsed));
		toggle.setAttribute('aria-label', name);
		toggle.title = name;
		const label = doc.getElementById('rail-toggle-label');
		if (label) label.textContent = name;
	}
	toggle.addEventListener('click', () => {
		collapsed = !collapsed;
		apply();
		try { storage?.setItem(KEY, String(collapsed)); } catch { /* 偏好儲存失敗不阻擋操作。 */ }
	});
	apply();
}
