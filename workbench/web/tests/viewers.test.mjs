import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { withDOM, descendants, click, settle } from './dom-helper.mjs';

const fixtureJson = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));
const fixtureText = async name => await readFile(new URL(`../mock/${name}`, import.meta.url), 'utf8');

const sampleSvgWithMeta = `
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
	<g data-node-id="c1">
		<title data-node-label="迴圈觀念">迴圈觀念</title>
		<desc data-node-explanation="讓程式依特定條件重複執行指定區塊。">讓程式依特定條件重複執行指定區塊。</desc>
		<desc data-node-quote="教材第三章第 2 節原文：迴圈為程式控制核心。">教材第三章第 2 節原文：迴圈為程式控制核心。</desc>
		<rect x="20" y="20" width="160" height="60" rx="8" />
		<text x="100" y="55">迴圈觀念</text>
	</g>
	<g data-node-id="c2">
		<title data-node-label="終止條件">終止條件</title>
		<desc data-node-explanation="確保迴圈在滿足條件時正確跳出，避免無窮迴圈。">確保迴圈在滿足條件時正確跳出，避免無窮迴圈。</desc>
		<rect x="20" y="120" width="160" height="60" rx="8" />
		<text x="100" y="155">終止條件</text>
	</g>
</svg>
`;

test('SVG viewer: 初始維持總覽，點選節點顯示解釋與折疊來源，提供下載與離頁清理', async () => {
	await withDOM(async doc => {
		const { mount, extractNodeMetadata } = await import('../js/viewers/svg.mjs');
		globalThis.fetch = async () => ({ ok: true, text: async () => sampleSvgWithMeta });

		const host = doc.createElement('div');
		const viewer = await mount(host, {
			unit: 'test-unit',
			item: { label: '心智圖測試' },
			files: { svg: 'mindmap/mindmap.svg' }
		});

		try {
			// 1. 下載按鈕檢查
			const download = descendants(host).find(node => node.tagName === 'a' && node.textContent.includes('下載 SVG'));
			assert.ok(download, '應包含下載 SVG 按鈕');
			assert.match(download.href, /mindmap\.svg/);

			// 2. 初始視圖保持總覽提示
			const inspector = descendants(host).find(node => node.classList?.contains?.('svg-inspector') || node.className.includes('svg-inspector'));
			assert.ok(inspector, '應包含概念詳情面板');
			assert.match(inspector.textContent, /點選或以鍵盤選取心智圖節點/);

			// 3. 節點有無障礙屬性
			const nodes = descendants(host).filter(node => node.getAttribute?.('data-node-id'));
			assert.equal(nodes.length, 2);
			const node1 = nodes[0];
			const node2 = nodes[1];
			assert.equal(node1.getAttribute('tabindex'), '0');
			assert.equal(node1.getAttribute('role'), 'button');
			assert.equal(node1.getAttribute('aria-pressed'), 'false');
			assert.equal(node1.getAttribute('aria-label'), '概念：迴圈觀念');

			// 4. 點選節點 c1
			click(node1);
			await settle();
			assert.equal(node1.getAttribute('data-selected'), 'true');
			assert.equal(node1.getAttribute('aria-pressed'), 'true');
			assert.match(inspector.textContent, /迴圈觀念/);
			assert.match(inspector.textContent, /讓程式依特定條件重複執行/);
			assert.match(inspector.textContent, /教材原文引用/);
			assert.match(inspector.textContent, /迴圈為程式控制核心/);

			// 5. 鍵盤 Enter 選取節點 c2
			const enterKey = new Event('keydown', { bubbles: true, cancelable: true });
			Object.defineProperty(enterKey, 'key', { value: 'Enter' });
			node2.dispatchEvent(enterKey);
			await settle();
			assert.equal(node1.getAttribute('data-selected'), null);
			assert.equal(node1.getAttribute('aria-pressed'), 'false');
			assert.equal(node2.getAttribute('data-selected'), 'true');
			assert.equal(node2.getAttribute('aria-pressed'), 'true');
			assert.match(inspector.textContent, /終止條件/);
			assert.match(inspector.textContent, /確保迴圈在滿足條件時正確跳出/);
			// c2 沒有 quote，不應包含引用區塊
			assert.doesNotMatch(inspector.textContent, /教材原文引用/);

			// 6. 鍵盤 Space 選取節點 c1
			const spaceKey = new Event('keydown', { bubbles: true, cancelable: true });
			Object.defineProperty(spaceKey, 'key', { value: ' ' });
			node1.dispatchEvent(spaceKey);
			await settle();
			assert.equal(node1.getAttribute('data-selected'), 'true');
			assert.match(inspector.textContent, /迴圈觀念/);

			// 7. 測試 extractNodeMetadata 提取函式
			const meta1 = extractNodeMetadata(node1);
			assert.equal(meta1.label, '迴圈觀念');
			assert.equal(meta1.explanation, '讓程式依特定條件重複執行指定區塊。');
			assert.equal(meta1.quote, '教材第三章第 2 節原文：迴圈為程式控制核心。');
		} finally {
			viewer.dispose();
		}

		// 離頁清理後觸發事件不應引發例外
		const key = new Event('keydown', { bubbles: true, cancelable: true });
		Object.defineProperty(key, 'key', { value: 'Enter' });
		host.dispatchEvent(key);
	});
});

test('SVG viewer: 舊版 SVG 無 metadata 仍能正常載入與點選，不拋出錯誤', async () => {
	await withDOM(async doc => {
		const { mount } = await import('../js/viewers/svg.mjs');
		const oldSvg = (await fixtureText('mindmap.svg')).replace(/ data-root-id="[^"]*"/, '').replace(/<(title|desc)\b[^>]*data-node-[^>]*>[\s\S]*?<\/\1>/g, '');
		globalThis.fetch = async () => ({ ok: true, text: async () => oldSvg });

		const host = doc.createElement('div');
		const viewer = await mount(host, {
			unit: 'test-unit',
			item: 'mindmap',
			files: { svg: 'mindmap/mindmap.svg' }
		});

		try {
			const nodes = descendants(host).filter(node => node.getAttribute?.('data-node-id'));
			assert.ok(nodes.length >= 5, '舊 SVG 應有至少 5 個節點');
			const loopNode = nodes.find(n => n.getAttribute('data-node-id') === 'loop');
			assert.ok(loopNode);

			click(loopNode);
			await settle();
			assert.equal(loopNode.getAttribute('data-selected'), 'true');
			const inspector = descendants(host).find(node => node.className.includes('svg-inspector'));
			assert.ok(inspector);
			assert.match(inspector.textContent, /迴圈/);
			assert.match(inspector.textContent, /未提供延伸說明/);
			assert.doesNotMatch(inspector.textContent, /教材原文引用/);
		} finally {
			viewer.dispose();
		}
	});
});

test('簡報 viewer: 新 1.1 簡報不可 fitSlide 無限縮字，超量時提供可讀標記與提示；舊 1.0 維持相容', async () => {
	await withDOM(async doc => {
		const { fitSlide } = await import('../js/viewers/deck.mjs');

		// 測試 1: 新 1.1 遇到超量內容，縮字次數受限（不無限縮到微型字），並標記 overflow
		const cardV11 = doc.createElement('article');
		cardV11.className = 'deck-slide';
		const contentV11 = doc.createElement('div');
		contentV11.className = 'deck-slide-content';
		cardV11.append(contentV11);

		// 模擬卡片高度 540，內容超量高度 1200
		cardV11.clientHeight = 540;
		cardV11.clientWidth = 960;
		contentV11.clientHeight = 400;
		contentV11.clientWidth = 880;
		cardV11.scrollHeight = 1200;
		cardV11.scrollWidth = 960;
		contentV11.scrollHeight = 1000;
		contentV11.scrollWidth = 880;

		fitSlide(cardV11, '1.1');
		const scale11 = parseFloat(cardV11.style.getPropertyValue('--deck-scale') || '1');
		assert.ok(scale11 >= 0.81, `新 1.1 縮小倍率 (${scale11}) 不應低於可讀下限 0.81`);
		assert.equal(cardV11.getAttribute('data-overflow'), 'true');
		const notice11 = cardV11.querySelector('.deck-overflow-notice');
		assert.ok(notice11, '新 1.1 超量內容應顯示可讀捲動提示');
		assert.match(notice11.textContent, /內容較多 · 可向下捲動/);

		// 測試 2: 舊 1.0 維持最多 40 次縮字，無 overflow notice
		const cardV10 = doc.createElement('article');
		cardV10.className = 'deck-slide';
		const contentV10 = doc.createElement('div');
		contentV10.className = 'deck-slide-content';
		cardV10.append(contentV10);

		cardV10.clientHeight = 540;
		cardV10.clientWidth = 960;
		contentV10.clientHeight = 400;
		contentV10.clientWidth = 880;
		cardV10.scrollHeight = 1200;
		cardV10.scrollWidth = 960;
		contentV10.scrollHeight = 1000;
		contentV10.scrollWidth = 880;

		fitSlide(cardV10, '1.0');
		const scale10 = parseFloat(cardV10.style.getPropertyValue('--deck-scale') || '1');
		assert.ok(scale10 < 0.1, `舊 1.0 應重複縮字至容納為止，scale=${scale10}`);
		assert.equal(cardV10.getAttribute('data-overflow'), null);
		assert.equal(cardV10.querySelector('.deck-overflow-notice'), null);

		// 測試 3: 正常尺寸投影片不觸發縮字與超量提示
		const normalCard = doc.createElement('article');
		normalCard.className = 'deck-slide';
		const normalContent = doc.createElement('div');
		normalContent.className = 'deck-slide-content';
		normalCard.append(normalContent);

		normalCard.clientHeight = 540;
		normalCard.clientWidth = 960;
		normalContent.clientHeight = 400;
		normalContent.clientWidth = 880;
		normalCard.scrollHeight = 500;
		normalCard.scrollWidth = 900;
		normalContent.scrollHeight = 350;
		normalContent.scrollWidth = 800;

		fitSlide(normalCard, '1.1');
		assert.equal(normalCard.style.getPropertyValue('--deck-scale'), '');
		assert.equal(normalCard.getAttribute('data-overflow'), null);
		assert.equal(normalCard.querySelector('.deck-overflow-notice'), null);
	});
});

test('簡報 viewer: 頁跳轉、講者筆記與原文完整維持', async () => {
	await withDOM(async doc => {
		const { mount } = await import('../js/viewers/deck.mjs');
		const deck = await fixtureJson('deck');
		globalThis.fetch = async () => ({ ok: true, json: async () => deck });

		const host = doc.createElement('div');
		const viewer = await mount(host, { unit: 'test-unit', files: { deck: 'slides/deck.json', pptx: 'slides/deck.pptx' } });

		try {
			// 頁碼初始為 1 / 7
			assert.match(host.textContent, /1 \/ 7/);
			assert.ok(host.textContent.includes(deck.slides[0].speaker_notes));

			// 下一頁按鈕
			const nextBtn = descendants(host).find(node => node.tagName === 'button' && node.textContent === '下一頁');
			assert.ok(nextBtn);
			click(nextBtn);
			await settle();
			assert.match(host.textContent, /2 \/ 7/);
			assert.ok(host.textContent.includes(deck.slides[1].speaker_notes));

			// 上一頁按鈕
			const prevBtn = descendants(host).find(node => node.tagName === 'button' && node.textContent === '上一頁');
			assert.ok(prevBtn);
			click(prevBtn);
			await settle();
			assert.match(host.textContent, /1 \/ 7/);

			// 下拉跳頁
			const jumpSelect = descendants(host).find(node => node.getAttribute('aria-label') === '選擇投影片');
			assert.ok(jumpSelect);
			jumpSelect.value = '3';
			jumpSelect.dispatchEvent(new Event('change'));
			await settle();
			assert.match(host.textContent, /4 \/ 7/);
			assert.ok(host.textContent.includes(deck.slides[3].speaker_notes));
		} finally {
			viewer.dispose();
		}
	});
});
