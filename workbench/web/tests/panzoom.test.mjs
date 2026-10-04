import test from 'node:test';
import assert from 'node:assert/strict';
import { zoomAt, fit, clampScale, attach } from '../js/panzoom.mjs';

const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} ≠ ${expected}`);

test('zoomAt 讓游標下的圖面座標保持固定，包括倍率上限', () => {
	const view = { x: -80, y: 30, scale: 0.7 };
	const point = { x: 271, y: 195 };
	for (const factor of [0.01, 0.8, 1.5, 100]) {
		const next = zoomAt(view, factor, point);
		close((point.x - next.x) / next.scale, (point.x - view.x) / view.scale);
		close((point.y - next.y) / next.scale, (point.y - view.y) / view.scale);
		assert.ok(next.scale >= 0.2 && next.scale <= 4);
	}
	assert.deepEqual(view, { x: -80, y: 30, scale: 0.7 });
});

test('fit 置中帶位移的範圍，留白且倍率受限', () => {
	const bounds = { x: -125, y: 40, w: 500, h: 300 };
	const viewport = { w: 900, h: 600 };
	const view = fit(bounds, viewport);
	close(view.x + (bounds.x + bounds.w / 2) * view.scale, viewport.w / 2);
	close(view.y + (bounds.y + bounds.h / 2) * view.scale, viewport.h / 2);
	assert.ok(bounds.w * view.scale <= viewport.w - 48);
	assert.ok(bounds.h * view.scale <= viewport.h - 48);
	assert.equal(fit({ x: 0, y: 0, w: 1, h: 1 }, viewport).scale, 4);
	assert.equal(fit({ x: 0, y: 0, w: 10000, h: 10000 }, { w: 100, h: 100 }).scale, 0.2);
	for (const value of Object.values(fit({ x: 0, y: 0, w: 0, h: 0 }, { w: 0, h: 0 }))) assert.ok(Number.isFinite(value));
	assert.equal(clampScale(0.1), 0.2);
	assert.equal(clampScale(10), 4);
	assert.equal(clampScale(0.5, 1, 2), 1);
});

class Surface extends EventTarget {
	constructor() { super(); this.attributes = new Map(); this.clientWidth = 800; this.clientHeight = 500; }
	getBoundingClientRect() { return { left: 20, top: 30, width: 800, height: 500 }; }
	setAttribute(key, value) { this.attributes.set(key, String(value)); }
	getAttribute(key) { return this.attributes.get(key) ?? null; }
	setPointerCapture() {}
	releasePointerCapture() {}
}
const dispatch = (el, type, properties) => {
	const event = Object.assign(new Event(type, { cancelable: true }), properties);
	el.dispatchEvent(event);
	return event;
};

test('attach 綁定滾輪、拖曳、快捷鍵與按鈕；卸載後不再更新', () => {
	const surface = new Surface();
	surface.setAttribute('data-bounds', JSON.stringify({ x: 0, y: 0, w: 600, h: 400 }));
	let view;
	const controls = attach(surface, { onChange: next => { view = next; } });
	controls.fit();
	const initial = { ...view };
	const wheel = dispatch(surface, 'wheel', { clientX: 250, clientY: 200, deltaY: -100 });
	assert.ok(wheel.defaultPrevented);
	assert.ok(view.scale > initial.scale);
	close((230 - view.x) / view.scale, (230 - initial.x) / initial.scale);
	dispatch(surface, 'pointerdown', { pointerId: 1, button: 0, clientX: 50, clientY: 80 });
	const before = { ...view };
	dispatch(surface, 'pointermove', { pointerId: 1, clientX: 90, clientY: 130 });
	close(view.x, before.x + 40);
	close(view.y, before.y + 50);
	dispatch(surface, 'pointerup', { pointerId: 1 });
	dispatch(surface, 'keydown', { key: '0' });
	assert.deepEqual(view, initial);
	controls.zoomIn();
	const enlarged = view.scale;
	dispatch(surface, 'keydown', { key: '-' });
	assert.ok(view.scale < enlarged);
	dispatch(surface, 'keydown', { key: '+' });
	close(view.scale, enlarged);
	const unhandled = dispatch(surface, 'keydown', { key: '+', ctrlKey: true });
	assert.equal(unhandled.defaultPrevented, false);
	controls.zoomOut();
	controls.destroy();
	const final = { ...view };
	dispatch(surface, 'wheel', { deltaY: -100, clientX: 10, clientY: 10 });
	assert.deepEqual(view, final);
});

test('focus 使用指定範圍，fullscreen 可進出', async () => {
	const surface = new Surface();
	const doc = Object.assign(new EventTarget(), { fullscreenElement: null, exitFullscreen: async () => { doc.fullscreenElement = null; } });
	surface.ownerDocument = doc;
	surface.requestFullscreen = async () => { doc.fullscreenElement = surface; };
	let view;
	const controls = attach(surface, { onChange: next => { view = next; } });
	const bounds = { x: 200, y: 80, w: 250, h: 180 };
	await controls.focus(bounds, 0);
	assert.deepEqual(view, fit(bounds, { w: 800, h: 500 }));
	await controls.fullscreen();
	assert.equal(doc.fullscreenElement, surface);
	await controls.fullscreen();
	assert.equal(doc.fullscreenElement, null);
	controls.destroy();
});

test('focus 平滑插值，ResizeObserver 不打斷動畫，拖曳後不誤觸節點', async () => {
	const previous = { requestAnimationFrame: globalThis.requestAnimationFrame, cancelAnimationFrame: globalThis.cancelAnimationFrame,
		ResizeObserver: globalThis.ResizeObserver };
	const frames = new Map();
	let serial = 0;
	let resize;
	globalThis.requestAnimationFrame = callback => { frames.set(++serial, callback); return serial; };
	globalThis.cancelAnimationFrame = id => frames.delete(id);
	globalThis.ResizeObserver = class { constructor(callback) { resize = callback; } observe() {} disconnect() {} };
	const tick = time => {
		const callbacks = [...frames.values()];
		frames.clear();
		callbacks.forEach(callback => callback(time));
	};
	try {
		const surface = new Surface();
		let view;
		const controls = attach(surface, { onChange: next => { view = next; } });
		const bounds = { x: 100, y: 40, w: 200, h: 150 };
		const animation = controls.focus(bounds, 350);
		tick(0);
		assert.equal(view.scale, 1);
		resize();
		assert.equal(view.scale, 1);
		tick(175);
		assert.ok(view.scale > 1 && view.scale < fit(bounds, { w: 800, h: 500 }).scale);
		tick(350);
		await animation;
		assert.deepEqual(view, fit(bounds, { w: 800, h: 500 }));
		dispatch(surface, 'pointerdown', { pointerId: 1, button: 0, clientX: 50, clientY: 80 });
		dispatch(surface, 'pointermove', { pointerId: 1, clientX: 90, clientY: 130 });
		dispatch(surface, 'pointerup', { pointerId: 1 });
		assert.equal(dispatch(surface, 'click', { detail: 1 }).defaultPrevented, true);
		controls.destroy();
		assert.equal(frames.size, 0);
	} finally {
		for (const [key, value] of Object.entries(previous)) {
			if (value === undefined) delete globalThis[key];
			else globalThis[key] = value;
		}
	}
});

test('在圖面邊緣按下、移到外面放開後，不留下拖曳狀態', () => {
	const surface = new Surface();
	const doc = new EventTarget();
	surface.ownerDocument = doc;
	let view;
	const controls = attach(surface, { onChange: next => { view = next; } });
	controls.focus({ x: 0, y: 0, w: 600, h: 400 }, 0);
	const initial = { ...view };
	dispatch(surface, 'pointerdown', { pointerId: 1, button: 0, clientX: 21, clientY: 100 });
	dispatch(doc, 'pointerup', { pointerId: 1 });
	dispatch(surface, 'pointermove', { pointerId: 1, buttons: 0, clientX: 100, clientY: 150 });
	assert.deepEqual(view, initial);
	dispatch(surface, 'pointerdown', { pointerId: 2, button: 0, clientX: 50, clientY: 80 });
	dispatch(surface, 'pointermove', { pointerId: 2, buttons: 1, clientX: 80, clientY: 100 });
	assert.equal(view.x, initial.x + 30);
	assert.equal(view.y, initial.y + 20);
	controls.destroy();
});
