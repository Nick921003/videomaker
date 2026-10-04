export function clampScale(s, min = 0.2, max = 4) {
	return Math.min(max, Math.max(min, s));
}

export function zoomAt(view, factor, point) {
	const scale = clampScale(view.scale * factor);
	const ratio = scale / view.scale;
	return { x: point.x - (point.x - view.x) * ratio, y: point.y - (point.y - view.y) * ratio, scale };
}

export function fit(bounds, viewport, pad = 24) {
	const scale = clampScale(Math.min(Math.max(0, viewport.w - pad * 2) / Math.max(1, bounds.w),
		Math.max(0, viewport.h - pad * 2) / Math.max(1, bounds.h)));
	return { x: viewport.w / 2 - (bounds.x + bounds.w / 2) * scale,
		y: viewport.h / 2 - (bounds.y + bounds.h / 2) * scale, scale };
}

export function attach(svgOrEl, { onChange, fullscreenElement = svgOrEl } = {}) {
	let view = { x: 0, y: 0, scale: 1 };
	let drag = null;
	let suppressClick = false;
	let frame = null;
	let finishAnimation = null;
	let targetBounds = null;
	const listeners = [];
	const viewport = () => {
		const rect = svgOrEl.getBoundingClientRect?.();
		return { w: rect?.width ?? svgOrEl.clientWidth ?? 0, h: rect?.height ?? svgOrEl.clientHeight ?? 0 };
	};
	const bounds = () => JSON.parse(svgOrEl.getAttribute('data-bounds') ?? '{"x":0,"y":0,"w":1,"h":1}');
	const publish = next => {
		view = { ...next };
		const content = svgOrEl.querySelector?.('[data-panzoom-content]');
		if (content) content.setAttribute('transform', `translate(${view.x} ${view.y}) scale(${view.scale})`);
		onChange?.({ ...view });
	};
	const stopAnimation = () => {
		if (frame !== null) globalThis.cancelAnimationFrame?.(frame);
		frame = null;
		finishAnimation?.();
		finishAnimation = null;
	};
	const focus = (area, animateMs = 350) => {
		stopAnimation();
		targetBounds = area;
		const next = fit(area, viewport());
		const reduced = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
		if (!animateMs || reduced || !globalThis.requestAnimationFrame) { publish(next); return Promise.resolve(); }
		const start = { ...view };
		return new Promise(resolve => {
			finishAnimation = resolve;
			let started;
			const tick = time => {
				started ??= time;
				const progress = Math.min(1, (time - started) / animateMs);
				const eased = 1 - (1 - progress) ** 3;
				publish(Object.fromEntries(['x', 'y', 'scale'].map(key => [key, start[key] + (next[key] - start[key]) * eased])));
				if (progress < 1) frame = requestAnimationFrame(tick);
				else { frame = null; finishAnimation = null; resolve(); }
			};
			frame = requestAnimationFrame(tick);
		});
	};
	const fitView = () => focus(bounds(), 0);
	const zoom = (factor, point) => {
		stopAnimation();
		targetBounds = null;
		const { w, h } = viewport();
		publish(zoomAt(view, factor, point ?? { x: w / 2, y: h / 2 }));
	};
	const zoomIn = () => zoom(1.2);
	const zoomOut = () => zoom(1 / 1.2);
	const fullscreen = async () => {
		const doc = fullscreenElement.ownerDocument ?? globalThis.document;
		if (doc?.fullscreenElement === fullscreenElement) await doc.exitFullscreen?.();
		else await fullscreenElement.requestFullscreen?.();
	};
	const listen = (target, type, handler, options) => {
		target?.addEventListener(type, handler, options);
		listeners.push(() => target?.removeEventListener(type, handler, options));
	};
	listen(svgOrEl, 'wheel', event => {
		event.preventDefault();
		const rect = svgOrEl.getBoundingClientRect();
		const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.height : 1);
		zoom(Math.exp(-Math.max(-500, Math.min(500, delta)) * 0.002), { x: event.clientX - rect.left, y: event.clientY - rect.top });
	}, { passive: false });
	listen(svgOrEl, 'pointerdown', event => {
		if (event.button !== 0 || drag) return;
		stopAnimation();
		suppressClick = false;
		drag = { id: event.pointerId, x: event.clientX, y: event.clientY, view: { ...view }, moved: false };
	});
	listen(svgOrEl, 'pointermove', event => {
		if (!drag || drag.id !== event.pointerId) return;
		if (event.buttons === 0) { endDrag(event); return; }
		const dx = event.clientX - drag.x;
		const dy = event.clientY - drag.y;
		if (!drag.moved && Math.hypot(dx, dy) < 5) return;
		drag.moved = true;
		suppressClick = true;
		targetBounds = null;
		svgOrEl.setPointerCapture?.(event.pointerId);
		svgOrEl.setAttribute('data-dragging', 'true');
		publish({ ...drag.view, x: drag.view.x + dx, y: drag.view.y + dy });
	});
	const endDrag = event => {
		if (!drag || drag.id !== event.pointerId) return;
		if (svgOrEl.hasPointerCapture?.(event.pointerId)) svgOrEl.releasePointerCapture(event.pointerId);
		drag = null;
		svgOrEl.setAttribute('data-dragging', 'false');
	};
	for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) listen(svgOrEl, event, endDrag);
	for (const event of ['pointerup', 'pointercancel']) listen(svgOrEl.ownerDocument, event, endDrag, true);
	listen(svgOrEl, 'click', event => {
		if (!suppressClick || event.detail === 0) return;
		event.preventDefault();
		event.stopPropagation();
		suppressClick = false;
	}, true);
	listen(svgOrEl, 'keydown', event => {
		if (event.ctrlKey || event.metaKey || event.altKey || event.target?.closest?.('input, textarea, select, [contenteditable="true"]')) return;
		const action = { '+': zoomIn, '=': zoomIn, '-': zoomOut, '0': fitView }[event.key];
		if (!action) return;
		event.preventDefault();
		action();
	});
	const controls = { zoomIn, zoomOut, fit: fitView, focus, fullscreen,
		destroy() { stopAnimation(); listeners.forEach(remove => remove()); observer?.disconnect(); } };
	for (const button of svgOrEl.parentElement?.querySelectorAll?.('[data-panzoom-action]') ?? []) {
		const action = button.getAttribute('data-panzoom-action');
		if (typeof controls[action] === 'function') listen(button, 'click', controls[action]);
	}
	const observer = globalThis.ResizeObserver ? new ResizeObserver(() => {
		if (targetBounds && frame === null) focus(targetBounds, 0);
	}) : null;
	observer?.observe(svgOrEl);
	return controls;
}
