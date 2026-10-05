import { el } from '../ui.mjs';
import { fileURL } from './common.mjs';

export function mount(host, { unit, item, files }) {
	const root = el('section', 'viewer viewer-video');
	root.setAttribute('aria-label', typeof item === 'string' ? item : item.label);
	const video = el('video', 'product-video');
	video.controls = true;
	video.playsInline = true;
	video.preload = 'metadata';
	video.src = fileURL(unit, files.video, 'video');
	const notice = el('p', 'section-note video-notice');
	notice.hidden = true;
	video.addEventListener('error', () => {
		notice.hidden = false;
		notice.textContent = '影片暫時讀不到，請稍後再試。';
	});
	root.append(video, notice);
	host.replaceChildren(root);
	return { dispose() { video.pause?.(); video.removeAttribute('src'); video.load?.(); } };
}
