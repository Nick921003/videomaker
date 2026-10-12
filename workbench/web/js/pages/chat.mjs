import { api } from '../api.mjs';
import { el } from '../ui.mjs';
import { COMPONENT_SAMPLES, PRIMARY_SAMPLE, classifyChatAction } from './chat-data.mjs';

function control(tag, className, text) {
	const node = el(tag, className, text);
	if (tag === 'button') node.type = 'button';
	return node;
}

function stopVideo(video, clear = false) {
	if (!video) return;
	video.pause?.();
	if (clear) {
		video.removeAttribute('src');
		video.src = '';
		video.load?.();
	}
}

export async function renderChat() {
	const units = await api.get('/units');
	let active = true;
	let requestVersion = 0;
	let pending = false;
	let selectedUnit = units[0]?.unit_id ?? '';
	let currentSample = PRIMARY_SAMPLE;
	const endedFor = new Set();
	let lastQuestion = '';

	const page = el('section', 'teaching-chat');
	const header = el('header', 'teaching-chat__header');
	const headerCopy = el('div', 'teaching-chat__heading');
	headerCopy.append(
		el('p', 'eyebrow', '現有教學影片'),
		el('h1', '', '看影片，直接問這一段'),
		el('p', 'teaching-chat__lede', '先看已完成的 48 秒樣片，再請工作台定位、重播或記下補強需求。'),
	);
	const unitField = el('label', 'teaching-chat__unit');
	unitField.append(el('span', '', '提問使用的教材'));
	const unitSelect = el('select');
	unitSelect.setAttribute('aria-label', '提問使用的教材');
	for (const unit of units) {
		const option = el('option', '', unit.title);
		option.value = unit.unit_id;
		unitSelect.append(option);
	}
	unitSelect.value = selectedUnit;
	unitSelect.disabled = !units.length;
	unitField.append(unitSelect);
	header.append(headerCopy, unitField);

	const workspace = el('div', 'teaching-chat__workspace');
	const videoColumn = el('section', 'teaching-chat__video-column');
	videoColumn.setAttribute('aria-label', '教學影片');
	const videoMeta = el('div', 'teaching-chat__video-meta');
	const sampleTitle = el('h2', '', PRIMARY_SAMPLE.title);
	const sampleNote = el('p', '', `${PRIMARY_SAMPLE.duration} 秒 · 現有樣片 · ${PRIMARY_SAMPLE.lesson}`);
	videoMeta.append(sampleTitle, sampleNote);
	const videoFrame = el('div', 'teaching-chat__video-frame');
	const video = el('video');
	video.src = PRIMARY_SAMPLE.src;
	video.controls = true;
	video.playsInline = true;
	video.preload = 'metadata';
	video.setAttribute('aria-label', PRIMARY_SAMPLE.title);
	videoFrame.append(video);
	const emptyVideo = el('p', 'teaching-chat__video-empty', '這份教材尚未選擇對應樣片。你仍可提問教材內容。');
	emptyVideo.hidden = true;

	const chapterControls = el('div', 'teaching-chat__chapters');
	chapterControls.setAttribute('aria-label', '影片定位');
	function playAt(time) {
		if (!video.src) return;
		video.currentTime = time;
		video.play?.();
	}
	for (const chapter of PRIMARY_SAMPLE.chapters) {
		const jump = control('button', 'teaching-chat__chapter', chapter.label);
		jump.addEventListener('click', () => playAt(chapter.time));
		chapterControls.append(jump);
	}
	const replay = control('button', 'teaching-chat__chapter teaching-chat__chapter--quiet', '重播');
	replay.addEventListener('click', () => playAt(0));
	chapterControls.append(replay);

	const demos = el('details', 'teaching-chat__demos');
	const demoSummary = el('summary', '', '查看其他課題的 15 秒元件樣片');
	const demoNote = el('p', 'teaching-chat__demo-note', '以下樣片來自不同課題，用來檢查各種呈現方式，不代表目前教材已生成同風格版本。');
	const demoGrid = el('div', 'teaching-chat__demo-grid');
	for (const sample of COMPONENT_SAMPLES) {
		const openSample = control('button', 'teaching-chat__demo');
		openSample.setAttribute('aria-label', `播放 ${sample.title}`);
		openSample.append(el('strong', '', sample.style), el('span', '', sample.title), el('small', '', `${sample.lesson} · 15 秒`));
		openSample.addEventListener('click', () => {
			stopVideo(video);
			currentSample = sample;
			video.src = sample.src;
			video.hidden = false;
			emptyVideo.hidden = true;
			sampleTitle.textContent = sample.title;
			sampleNote.textContent = `${sample.duration} 秒 · 現有元件樣片 · 其他課題：${sample.lesson}`;
			video.setAttribute('aria-label', sample.title);
			video.load?.();
		});
		demoGrid.append(openSample);
	}
	const review = el('a', 'teaching-chat__review', '開啟全部元件檢視頁');
	review.href = '/trials/index.html';
	demos.append(demoSummary, demoNote, demoGrid, review);
	videoColumn.append(videoMeta, videoFrame, emptyVideo, chapterControls, demos);

	const chatColumn = el('section', 'teaching-chat__conversation');
	chatColumn.setAttribute('aria-label', '影片提問');
	chatColumn.append(el('h2', '', '對話'));
	const messages = el('div', 'teaching-chat__messages');
	messages.setAttribute('role', 'log');
	messages.setAttribute('aria-live', 'polite');

	function appendMessage(role, text, actions = []) {
		const message = el('article', `teaching-chat__message teaching-chat__message--${role}`);
		message.append(el('p', 'teaching-chat__speaker', role === 'user' ? '你' : '工作台'), el('p', '', text));
		if (actions.length) {
			const actionRow = el('div', 'teaching-chat__message-actions');
			for (const action of actions) actionRow.append(action);
			message.append(actionRow);
		}
		messages.append(message);
		return message;
	}
	appendMessage('assistant', '你可以問教材內容，也可以說「回到條件」或「重播」。');

	const form = el('form', 'teaching-chat__form');
	const inputLabel = el('label', 'sr-only', '輸入問題');
	inputLabel.setAttribute('for', 'teaching-chat-question');
	const input = el('textarea');
	input.id = 'teaching-chat-question';
	input.rows = 3;
	input.placeholder = units.length ? '例如：為什麼條件會多判斷一次？' : '先到素材庫加入教材';
	input.disabled = !units.length;
	const send = control('button', 'button button-primary', '送出');
	send.type = 'submit';
	send.disabled = !units.length;
	const formHint = el('p', 'teaching-chat__hint', 'Enter 送出，Shift+Enter 換行。風格需求只會先記錄，不會假裝已生成。');
	form.append(inputLabel, input, send, formHint);
	chatColumn.append(messages, form);

	function setPending(value) {
		pending = value;
		input.disabled = value || !selectedUnit;
		send.disabled = value || !selectedUnit;
		send.textContent = value ? '查找中…' : '送出';
	}

	function showAnswer(result) {
		if (result.kind === 'story' || result.kind === 'highlight') {
			appendMessage('assistant', result.video
				? '找到教材中的對應段落，播放器已切換到這份成品。'
				: '找到教材中的對應段落，但這段目前還沒有影片成品。');
			if (result.video) {
				stopVideo(video);
				currentSample = { id: `unit-${selectedUnit}-${result.story}`, title: '教材對應段落', lesson: '選定教材', duration: null, src: result.video };
				video.src = result.video;
				video.hidden = false;
				emptyVideo.hidden = true;
				sampleTitle.textContent = '教材對應段落';
				sampleNote.textContent = '素材庫中的現有影片成品';
				video.load?.();
			}
		} else if (result.kind === 'out_of_scope') {
			appendMessage('assistant', '這份教材沒有教這個。請換一份教材，或改問目前單元的內容。');
		} else {
			appendMessage('assistant', '我還不能確定你指哪一段。你想找的是觀念、流程，還是操作次數？');
		}
	}

	async function ask(question, echo = true) {
		if (!active || pending || !selectedUnit || !question.trim()) return;
		const clean = question.trim();
		lastQuestion = clean;
		if (echo) appendMessage('user', clean);
		const action = classifyChatAction(clean);
		if (action.kind === 'seek' || action.kind === 'replay') {
			playAt(action.time);
			appendMessage('assistant', action.kind === 'replay' ? '已從頭重播目前影片。' : '已回到條件再次檢查的位置。');
			input.value = '';
			return;
		}
		if (action.kind === 'reinforce') {
			appendMessage('assistant', '已記錄補強需求。這只是需求紀錄，尚未開始生成同主題的新版本。');
			input.value = '';
			return;
		}
		const version = ++requestVersion;
		setPending(true);
		input.value = '';
		try {
			const result = await api.post('/ask', { unit_id: selectedUnit, question: clean });
			if (!active || version !== requestVersion) return;
			showAnswer(result);
		} catch (error) {
			if (!active || version !== requestVersion) return;
			const retry = control('button', 'button button-secondary', '再試一次');
			retry.addEventListener('click', () => {
				retry.disabled = true;
				ask(lastQuestion, false);
			});
			appendMessage('assistant', `${error.reason ?? '暫時連不上'}${error.advice ? `。${error.advice}` : ''}`, [retry]);
		} finally {
			if (active && version === requestVersion) setPending(false);
		}
	}

	form.addEventListener('submit', event => {
		event.preventDefault();
		ask(input.value);
	});
	input.addEventListener('keydown', event => {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			form.dispatchEvent(new Event('submit', { cancelable: true }));
		}
	});
	video.addEventListener('ended', () => {
		if (!active || endedFor.has(currentSample.id)) return;
		endedFor.add(currentSample.id);
		appendMessage('assistant', '看完了。你可以問我這一段的觀念，或請我回到某個位置。');
	});
	unitSelect.addEventListener('change', () => {
		selectedUnit = unitSelect.value;
		requestVersion += 1;
		setPending(false);
		stopVideo(video, true);
		currentSample = { id: `empty-${selectedUnit}`, title: '', src: '' };
		video.hidden = true;
		emptyVideo.hidden = false;
		sampleTitle.textContent = '已切換提問教材';
		sampleNote.textContent = '舊影片已清除，避免把不同教材混在一起。';
		messages.replaceChildren();
		appendMessage('assistant', '教材已切換。請直接問這份教材的內容。');
	});

	workspace.append(videoColumn, chatColumn);
	page.append(header, workspace);
	page.dispose = () => {
		if (!active) return;
		active = false;
		requestVersion += 1;
		stopVideo(video, true);
	};
	return page;
}
