/**
 * 對話式教材製作工作台原型 (Chat-driven Material Studio)
 * 左側：AI 對話流（支援教材分析、五大重點勾選、素材庫自動檢索命中、製作狀態顯示）
 * 右側：即時多功能畫布與預覽工作區（點擊直接切換影片、PPT、心智圖與多風格展示，不跳頁）
 */
import { el } from '../ui.mjs';

export async function renderChat() {
	const container = el('div', 'chat-studio-layout');

	// ---------------- 左側：對話互動串流 ----------------
	const chatPanel = el('section', 'chat-panel');
	const chatHeader = el('header', 'chat-header');
	chatHeader.innerHTML = `
		<div class="chat-header-info">
			<span class="chat-ai-avatar">🤖</span>
			<div>
				<h2 class="chat-title">AI 教材製作助理</h2>
				<p class="chat-subtitle">貼上教材或提問，即時分析、挑選元件並一鍵生成</p>
			</div>
		</div>
		<span class="badge badge-live">對話原型模式</span>
	`;

	const chatMessages = el('div', 'chat-messages-container scroll-box');
	const chatFooter = el('footer', 'chat-input-bar');

	// ---------------- 右側：即時畫布與預覽區 ----------------
	const previewPanel = el('section', 'preview-workspace-panel');
	const previewHeader = el('header', 'preview-workspace-header');
	previewHeader.innerHTML = `
		<div class="preview-tabs" id="preview-tabs">
			<button class="preview-tab active" data-type="video">🎬 影片播放器</button>
			<button class="preview-tab" data-type="deck">📑 簡報 PPT 檢視</button>
			<button class="preview-tab" data-type="mindmap">🧠 概念心智圖</button>
			<button class="preview-tab" data-type="showcase">🎨 風格元件全集</button>
		</div>
		<div class="preview-actions">
			<span id="preview-status-badge" class="badge">就緒</span>
		</div>
	`;

	const previewContent = el('div', 'preview-workspace-content');
	previewContent.id = 'preview-workspace-content';

	// 預設右側畫面：顯示當前手帳樣片播放器
	function updatePreviewToVideo(title, src, meta = '') {
		previewContent.innerHTML = `
			<div class="preview-video-container">
				<div class="preview-video-meta">
					<h3 class="preview-title">${title}</h3>
					<span class="preview-tag">${meta || '1080p 24fps · Gemini 配音 · 手帳方格紙手寫'}</span>
				</div>
				<div class="video-frame-box">
					<video id="studio-video-player" src="${src}" controls autoplay playsinline></video>
				</div>
				<div class="preview-video-controls">
					<div class="preview-info-card">
						<h4>✨ 視覺風格特點</h4>
						<p>採用方格紙便簽、即時鋼筆跟隨與墨水書寫、相機俯瞰運鏡，適合循序漸進的課堂筆記感。</p>
					</div>
					<div class="preview-btn-group">
						<a class="btn btn-primary" href="${src}" download>⬇️ 下載 MP4 影片</a>
						<button class="btn btn-secondary" onclick="alert('已複製分享連結')">🔗 分享教材連結</button>
					</div>
				</div>
			</div>
		`;
		const badge = previewHeader.querySelector('#preview-status-badge');
		if (badge) {
			badge.textContent = '現有成品';
			badge.className = 'badge badge-ok';
		}
	}

	function updatePreviewToShowcase(activeKey = 'all') {
		previewContent.innerHTML = `
			<div class="showcase-container scroll-box">
				<div class="showcase-banner">
					<h3>🎨 課綱多元視覺風格工具箱（4 大擴充 Demo）</h3>
					<p>點擊下方任一風格，即時檢視該元件在不同教材主題中的表現：</p>
				</div>
				<div class="showcase-grid">
					<div class="showcase-card ${activeKey === 'notebook' ? 'selected' : ''}" onclick="window.__switchShowcase('notebook')">
						<div class="showcase-badge">手帳風格</div>
						<h4>v3-notebook · 方格筆記本</h4>
						<p>適用：演算走讀、變數狀態追蹤、手寫推導</p>
						<span class="showcase-tag">已製作完成 (C 迴圈)</span>
					</div>
					<div class="showcase-card ${activeKey === 'kinetic' ? 'selected' : ''}" onclick="window.__switchShowcase('kinetic')">
						<div class="showcase-badge">動態文字</div>
						<h4>y5_kinetic_type · 柔和動態文字</h4>
						<p>適用：章節破題提問、重點警告、提神金句</p>
						<span class="showcase-tag">已調平色階 (C 迴圈)</span>
					</div>
					<div class="showcase-card ${activeKey === 'keynote' ? 'selected' : ''}" onclick="window.__switchShowcase('keynote')">
						<div class="showcase-badge">現代卡片</div>
						<h4>t2_keynote_ui · Keynote UI</h4>
						<p>適用：Web API 架構、系統模組流向、物件封裝</p>
						<span class="showcase-tag">高質感毛玻璃</span>
					</div>
					<div class="showcase-card ${activeKey === 'chart' ? 'selected' : ''}" onclick="window.__switchShowcase('chart')">
						<div class="showcase-badge">數據圖表</div>
						<h4>t3_finance_chart · 演算法效能圖</h4>
						<p>適用：時間複雜度 O(n) vs O(log n) 數據對決</p>
						<span class="showcase-tag">長條/折線動態生長</span>
					</div>
					<div class="showcase-card ${activeKey === 'chalk' ? 'selected' : ''}" onclick="window.__switchShowcase('chalk')">
						<div class="showcase-badge">黑板粉筆</div>
						<h4>v8-chalkboard · 課堂粉筆黑板</h4>
						<p>適用：指標記憶體位址 (&x, *p) 推導、數學公式</p>
						<span class="showcase-tag">粉筆磨砂筆跡</span>
					</div>
					<div class="showcase-card ${activeKey === 'drafting' ? 'selected' : ''}" onclick="window.__switchShowcase('drafting')">
						<div class="showcase-badge">工程藍圖</div>
						<h4>v7-drafting · 系統記憶體圖紙</h4>
						<p>適用：Stack vs Heap 記憶體空間、指標引用</p>
						<span class="showcase-tag">CAD 坐標引導線</span>
					</div>
				</div>
				<div id="showcase-detail-view" class="showcase-detail-box">
					<p class="text-muted">點選上方任一卡片檢視動態詳情與設定。</p>
				</div>
			</div>
		`;
		window.__switchShowcase(activeKey);
	}

	// 元件模板動態狀態與客製化資料庫
	const COMPONENT_DATA = {
		keynote: {
			title: 'Web API 微服務架構與請求分流',
			step1: 'Client 請求端',
			step2: 'API Gateway (驗證/分流)',
			step3: 'Database 資料庫',
			theme: '深色高質感毛玻璃'
		},
		chart: {
			title: '演算法效能評測：二元搜尋 vs 線性搜尋',
			label1: '線性搜尋 O(n)',
			val1: 1000000,
			label2: '二元搜尋 O(log n)',
			val2: 20
		},
		chalk: {
			title: 'C 語言指標記憶體位址 (&x, *p) 板書推導',
			line1: 'int a = 42;       /* 變數 a 位於 0x7ffee4 */',
			line2: 'int *p = &a;      /* 指標 p 存入位址 0x7ffee4 */',
			line3: '*p = 99;          /* 解引用修改：a 的值變為 99 */',
			circle: '0x7ffee4'
		},
		drafting: {
			title: '系統記憶體 Stack vs Heap 空間劃分藍圖',
			stackText: '高位址 0xFFFFFFFF · Stack 局部變數 (向下生長 ↓)',
			freeText: '未分配空閒記憶體區間 (Free Memory Chunk)',
			heapText: '低位址 0x00000000 · Heap 動態 malloc (向上生長 ↑)'
		},
		kinetic: {
			hero: '迴圈邊界條件寫 i < 5 還是 i <= 5？',
			sub: '少算一次或多跑一輪？這就是差一錯誤！'
		}
	};

	let animTimer = null;

	window.__switchShowcase = function(key) {
		const detail = document.getElementById('showcase-detail-view');
		if (!detail) return;
		if (animTimer) clearInterval(animTimer);

		if (key === 'notebook') {
			detail.innerHTML = `
				<div class="detail-header">
					<h4>📘 嵐叔手帳筆記（v3-notebook）· 當前成品</h4>
					<button class="btn btn-sm btn-primary" onclick="window.__viewVideo('out/C-lanshu_notebook.mp4', 'C 迴圈手帳筆記')">在播放器打開</button>
				</div>
				<p>模擬老師手寫手帳筆記，方格紙帶活頁孔與便簽紙陰影，鋼筆筆桿動態跟隨、筆尖墨水書寫。</p>
				<div class="live-stage-card">
					<div class="stage-viewport" style="background:#26211e;">
						<video src="/out/C-lanshu_notebook.mp4" controls autoplay loop style="width:100%;height:100%;object-fit:contain;"></video>
					</div>
				</div>
			`;
			return;
		}

		if (key === 'keynote') {
			const d = COMPONENT_DATA.keynote;
			detail.innerHTML = `
				<div class="detail-header">
					<h4>💻 現代 Keynote UI（t2_keynote_ui）· 實際動態效果與客製化</h4>
					<span class="badge badge-ok">模板已就緒</span>
				</div>
				<p>深色星雲背景、毛玻璃卡片由模糊中立體浮現、API 箭頭脈衝流向穿梭。您可直接在下方客製化文字與節點。</p>
				<div class="live-stage-card">
					<div class="stage-viewport">
						<div class="keynote-stage" id="keynote-stage-dom">
							<div class="keynote-container">
								<div class="keynote-card" id="kn-c1">${d.step1}</div>
								<div class="keynote-arrow" id="kn-a1">➔</div>
								<div class="keynote-card highlight" id="kn-c2">${d.step2}</div>
								<div class="keynote-arrow" id="kn-a2">➔</div>
								<div class="keynote-card" id="kn-c3">${d.step3}</div>
							</div>
						</div>
					</div>
					<div class="stage-controls-bar">
						<button class="stage-btn" onclick="window.__playKeynoteAnim()">🔄 重播動態動畫</button>
						<span style="font-size:12px;color:#94a3b8;">真實動態渲染：立體 3D 浮現 + 光子流向</span>
					</div>
				</div>

				<div class="customizer-panel">
					<div class="customizer-header">
						<h4>🛠️ 元件屬性客製化檢查器 (Inspector)</h4>
						<span class="badge">修改後即時渲染</span>
					</div>
					<div class="customizer-grid">
						<div class="customizer-field">
							<label class="customizer-label">節點一文字 (Client)</label>
							<input class="customizer-input" id="inp-kn-s1" value="${d.step1}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">節點二核心 (Gateway)</label>
							<input class="customizer-input" id="inp-kn-s2" value="${d.step2}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">節點三後端 (DB/Service)</label>
							<input class="customizer-input" id="inp-kn-s3" value="${d.step3}">
						</div>
					</div>
					<div class="customizer-actions">
						<button class="btn btn-primary" onclick="window.__applyKeynoteCustom()">✨ 套用修改並重播</button>
						<button class="btn btn-secondary" onclick="alert('已儲存為您的客製化 Keynote 元件模板！未來教材可自動引用。')">💾 儲存為我的元件</button>
					</div>
				</div>
			`;
			setTimeout(window.__playKeynoteAnim, 100);
		} else if (key === 'chart') {
			const d = COMPONENT_DATA.chart;
			detail.innerHTML = `
				<div class="detail-header">
					<h4>📊 演算法數據圖表（t3_finance_chart）· 實際動態效果與客製化</h4>
					<span class="badge badge-ok">模板已就緒</span>
				</div>
				<p>長條柱動態生長衝刺、數值從零累計跳動、高低對決印章。可修改兩組演算法名稱與比對數值。</p>
				<div class="live-stage-card">
					<div class="stage-viewport">
						<div class="chart-stage">
							<div class="chart-title-tag" id="chart-title-dom">${d.title}</div>
							<div class="chart-bar-row">
								<div>
									<div style="font-size:13px;color:#cbd5e1;margin-bottom:4px;" id="c-lbl1">${d.label1}</div>
									<div class="chart-bar-track">
										<div class="chart-bar-grow red" id="c-bar1" style="width:0%"><span id="c-txt1">0</span> 次運算</div>
									</div>
								</div>
								<div>
									<div style="font-size:13px;color:#cbd5e1;margin-bottom:4px;" id="c-lbl2">${d.label2}</div>
									<div class="chart-bar-track">
										<div class="chart-bar-grow green" id="c-bar2" style="width:0%"><span id="c-txt2">0</span> 次運算</div>
									</div>
								</div>
							</div>
						</div>
					</div>
					<div class="stage-controls-bar">
						<button class="stage-btn" onclick="window.__playChartAnim()">🔄 重播生長動畫</button>
						<span style="font-size:12px;color:#94a3b8;">真實動態渲染：柱狀圖彈性延伸 + 數字即時翻滾</span>
					</div>
				</div>

				<div class="customizer-panel">
					<div class="customizer-header">
						<h4>🛠️ 元件屬性客製化檢查器 (Inspector)</h4>
						<span class="badge">修改後即時渲染</span>
					</div>
					<div class="customizer-grid">
						<div class="customizer-field">
							<label class="customizer-label">長條一標籤</label>
							<input class="customizer-input" id="inp-ch-l1" value="${d.label1}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">長條一數值 (大)</label>
							<input class="customizer-input" type="number" id="inp-ch-v1" value="${d.val1}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">長條二標籤</label>
							<input class="customizer-input" id="inp-ch-l2" value="${d.label2}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">長條二數值 (小)</label>
							<input class="customizer-input" type="number" id="inp-ch-v2" value="${d.val2}">
						</div>
					</div>
					<div class="customizer-actions">
						<button class="btn btn-primary" onclick="window.__applyChartCustom()">✨ 套用修改並重播</button>
						<button class="btn btn-secondary" onclick="alert('已儲存為您的圖表元件模板！')">💾 儲存為我的元件</button>
					</div>
				</div>
			`;
			setTimeout(window.__playChartAnim, 100);
		} else if (key === 'chalk') {
			const d = COMPONENT_DATA.chalk;
			detail.innerHTML = `
				<div class="detail-header">
					<h4>🖍️ 課堂黑板粉筆（v8-chalkboard）· 實際動態效果與客製化</h4>
					<span class="badge badge-ok">模板已就緒</span>
				</div>
				<p>黑板磨砂紋理、彩色粉筆逐筆書寫、手繪粉筆圈重點。可修改板書程式碼與圈選位址。</p>
				<div class="live-stage-card">
					<div class="stage-viewport">
						<div class="chalk-stage">
							<div class="chalk-line" id="chk-l1">${d.line1}</div>
							<div class="chalk-line" id="chk-l2" style="color:#ffd166;">${d.line2}</div>
							<div class="chalk-line" id="chk-l3" style="color:#a7c957;">${d.line3}</div>
							<div class="chalk-circle" id="chk-cir" style="left:380px;top:140px;">圈選重點</div>
						</div>
					</div>
					<div class="stage-controls-bar">
						<button class="stage-btn" onclick="window.__playChalkAnim()">🔄 重播粉筆板書</button>
						<span style="font-size:12px;color:#94a3b8;">真實動態渲染：粉筆粉塵顆粒感 + 順序筆跡書寫</span>
					</div>
				</div>

				<div class="customizer-panel">
					<div class="customizer-header">
						<h4>🛠️ 元件屬性客製化檢查器 (Inspector)</h4>
						<span class="badge">修改後即時渲染</span>
					</div>
					<div class="customizer-grid">
						<div class="customizer-field">
							<label class="customizer-label">粉筆第一行程式碼</label>
							<input class="customizer-input" id="inp-ck-l1" value="${d.line1}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">粉筆第二行 (黃色粉筆)</label>
							<input class="customizer-input" id="inp-ck-l2" value="${d.line2}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">粉筆第三行 (綠色粉筆)</label>
							<input class="customizer-input" id="inp-ck-l3" value="${d.line3}">
						</div>
					</div>
					<div class="customizer-actions">
						<button class="btn btn-primary" onclick="window.__applyChalkCustom()">✨ 套用修改並重播</button>
						<button class="btn btn-secondary" onclick="alert('已儲存為您的黑板粉筆元件模板！')">💾 儲存為我的元件</button>
					</div>
				</div>
			`;
			setTimeout(window.__playChalkAnim, 100);
		} else if (key === 'drafting') {
			const d = COMPONENT_DATA.drafting;
			detail.innerHTML = `
				<div class="detail-header">
					<h4>📐 工程藍圖圖紙（v7-drafting）· 實際動態效果與客製化</h4>
					<span class="badge badge-ok">模板已就緒</span>
				</div>
				<p>CAD 毫米網格底、記憶體 Stack 與 Heap 空間對向生長、等角標註線。可客製化記憶體段落說明。</p>
				<div class="live-stage-card">
					<div class="stage-viewport">
						<div class="blueprint-stage">
							<div class="blueprint-box" id="bp-b1">${d.stackText}</div>
							<div class="blueprint-box" id="bp-b2" style="border-color:#38bdf888;color:#7dd3fc;">${d.freeText}</div>
							<div class="blueprint-box" id="bp-b3">${d.heapText}</div>
						</div>
					</div>
					<div class="stage-controls-bar">
						<button class="stage-btn" onclick="window.__playDraftAnim()">🔄 重播藍圖展開</button>
						<span style="font-size:12px;color:#94a3b8;">真實動態渲染：CAD 十字導引線 + 對向生長記憶體堆疊</span>
					</div>
				</div>

				<div class="customizer-panel">
					<div class="customizer-header">
						<h4>🛠️ 元件屬性客製化檢查器 (Inspector)</h4>
						<span class="badge">修改後即時渲染</span>
					</div>
					<div class="customizer-grid">
						<div class="customizer-field">
							<label class="customizer-label">高位址 Stack 描述</label>
							<input class="customizer-input" id="inp-bp-s" value="${d.stackText}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">中位址 Free 空間描述</label>
							<input class="customizer-input" id="inp-bp-f" value="${d.freeText}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">低位址 Heap 描述</label>
							<input class="customizer-input" id="inp-bp-h" value="${d.heapText}">
						</div>
					</div>
					<div class="customizer-actions">
						<button class="btn btn-primary" onclick="window.__applyDraftCustom()">✨ 套用修改並重播</button>
						<button class="btn btn-secondary" onclick="alert('已儲存為您的工程藍圖元件模板！')">💾 儲存為我的元件</button>
					</div>
				</div>
			`;
			setTimeout(window.__playDraftAnim, 100);
		} else if (key === 'kinetic') {
			const d = COMPONENT_DATA.kinetic;
			detail.innerHTML = `
				<div class="detail-header">
					<h4>⚡ 柔和動態文字（y5_kinetic_type）· 實際動態效果與客製化</h4>
					<span class="badge badge-ok">模板已就緒</span>
				</div>
				<p>字體砸入過衝回彈、暖沙底色消除暴閃。可客製化破題金句與警示內容。</p>
				<div class="live-stage-card">
					<div class="stage-viewport">
						<div class="kinetic-stage">
							<div class="kinetic-hero-text" id="kn-hero">${d.hero}</div>
							<div class="kinetic-sub-text" id="kn-sub">${d.sub}</div>
						</div>
					</div>
					<div class="stage-controls-bar">
						<button class="stage-btn" onclick="window.__playKineticAnim()">🔄 重播文字砸入動效</button>
						<span style="font-size:12px;color:#94a3b8;">真實動態渲染：重力過衝回彈 + 重點刷筆高亮</span>
					</div>
				</div>

				<div class="customizer-panel">
					<div class="customizer-header">
						<h4>🛠️ 元件屬性客製化檢查器 (Inspector)</h4>
						<span class="badge">修改後即時渲染</span>
					</div>
					<div class="customizer-grid">
						<div class="customizer-field">
							<label class="customizer-label">主金句文字</label>
							<input class="customizer-input" id="inp-kt-h" value="${d.hero}">
						</div>
						<div class="customizer-field">
							<label class="customizer-label">次重點警示文字</label>
							<input class="customizer-input" id="inp-kt-s" value="${d.sub}">
						</div>
					</div>
					<div class="customizer-actions">
						<button class="btn btn-primary" onclick="window.__applyKineticCustom()">✨ 套用修改並重播</button>
						<button class="btn btn-secondary" onclick="alert('已儲存為您的動態文字元件模板！')">💾 儲存為我的元件</button>
					</div>
				</div>
			`;
			setTimeout(window.__playKineticAnim, 100);
		}
	};

	// ---------------- 動畫播放與客製化套用控制器 ----------------
	window.__playKeynoteAnim = function() {
		const c1 = document.getElementById('kn-c1');
		const a1 = document.getElementById('kn-a1');
		const c2 = document.getElementById('kn-c2');
		const a2 = document.getElementById('kn-a2');
		const c3 = document.getElementById('kn-c3');
		if (!c1) return;
		[c1, a1, c2, a2, c3].forEach(el => el && el.classList.remove('active'));
		setTimeout(() => c1 && c1.classList.add('active'), 100);
		setTimeout(() => a1 && a1.classList.add('active'), 400);
		setTimeout(() => c2 && c2.classList.add('active'), 700);
		setTimeout(() => a2 && a2.classList.add('active'), 1000);
		setTimeout(() => c3 && c3.classList.add('active'), 1300);
	};

	window.__applyKeynoteCustom = function() {
		const s1 = document.getElementById('inp-kn-s1')?.value;
		const s2 = document.getElementById('inp-kn-s2')?.value;
		const s3 = document.getElementById('inp-kn-s3')?.value;
		if (s1) { COMPONENT_DATA.keynote.step1 = s1; document.getElementById('kn-c1').textContent = s1; }
		if (s2) { COMPONENT_DATA.keynote.step2 = s2; document.getElementById('kn-c2').textContent = s2; }
		if (s3) { COMPONENT_DATA.keynote.step3 = s3; document.getElementById('kn-c3').textContent = s3; }
		window.__playKeynoteAnim();
	};

	window.__playChartAnim = function() {
		const b1 = document.getElementById('c-bar1');
		const b2 = document.getElementById('c-bar2');
		const t1 = document.getElementById('c-txt1');
		const t2 = document.getElementById('c-txt2');
		if (!b1 || !b2) return;
		b1.style.width = '0%';
		b2.style.width = '0%';
		t1.textContent = '0';
		t2.textContent = '0';
		const target1 = COMPONENT_DATA.chart.val1;
		const target2 = COMPONENT_DATA.chart.val2;

		setTimeout(() => {
			b1.style.width = '88%';
			b2.style.width = '12%';
			let step = 0;
			const timer = setInterval(() => {
				step += 1;
				t1.textContent = Math.round(target1 * (step / 20)).toLocaleString();
				t2.textContent = Math.round(target2 * (step / 20)).toLocaleString();
				if (step >= 20) clearInterval(timer);
			}, 50);
		}, 150);
	};

	window.__applyChartCustom = function() {
		const l1 = document.getElementById('inp-ch-l1')?.value;
		const v1 = parseInt(document.getElementById('inp-ch-v1')?.value) || 100;
		const l2 = document.getElementById('inp-ch-l2')?.value;
		const v2 = parseInt(document.getElementById('inp-ch-v2')?.value) || 10;
		if (l1) { COMPONENT_DATA.chart.label1 = l1; document.getElementById('c-lbl1').textContent = l1; }
		if (l2) { COMPONENT_DATA.chart.label2 = l2; document.getElementById('c-lbl2').textContent = l2; }
		COMPONENT_DATA.chart.val1 = v1;
		COMPONENT_DATA.chart.val2 = v2;
		window.__playChartAnim();
	};

	window.__playChalkAnim = function() {
		const l1 = document.getElementById('chk-l1');
		const l2 = document.getElementById('chk-l2');
		const l3 = document.getElementById('chk-l3');
		const cir = document.getElementById('chk-cir');
		if (!l1) return;
		[l1, l2, l3, cir].forEach(el => el && el.classList.remove('active'));
		setTimeout(() => l1 && l1.classList.add('active'), 150);
		setTimeout(() => l2 && l2.classList.add('active'), 600);
		setTimeout(() => l3 && l3.classList.add('active'), 1100);
		setTimeout(() => cir && cir.classList.add('active'), 1600);
	};

	window.__applyChalkCustom = function() {
		const l1 = document.getElementById('inp-ck-l1')?.value;
		const l2 = document.getElementById('inp-ck-l2')?.value;
		const l3 = document.getElementById('inp-ck-l3')?.value;
		if (l1) { COMPONENT_DATA.chalk.line1 = l1; document.getElementById('chk-l1').textContent = l1; }
		if (l2) { COMPONENT_DATA.chalk.line2 = l2; document.getElementById('chk-l2').textContent = l2; }
		if (l3) { COMPONENT_DATA.chalk.line3 = l3; document.getElementById('chk-l3').textContent = l3; }
		window.__playChalkAnim();
	};

	window.__playDraftAnim = function() {
		const b1 = document.getElementById('bp-b1');
		const b2 = document.getElementById('bp-b2');
		const b3 = document.getElementById('bp-b3');
		if (!b1) return;
		[b1, b2, b3].forEach(el => el && el.classList.remove('active'));
		setTimeout(() => b1 && b1.classList.add('active'), 150);
		setTimeout(() => b2 && b2.classList.add('active'), 600);
		setTimeout(() => b3 && b3.classList.add('active'), 1050);
	};

	window.__applyDraftCustom = function() {
		const s = document.getElementById('inp-bp-s')?.value;
		const f = document.getElementById('inp-bp-f')?.value;
		const h = document.getElementById('inp-bp-h')?.value;
		if (s) { COMPONENT_DATA.drafting.stackText = s; document.getElementById('bp-b1').textContent = s; }
		if (f) { COMPONENT_DATA.drafting.freeText = f; document.getElementById('bp-b2').textContent = f; }
		if (h) { COMPONENT_DATA.drafting.heapText = h; document.getElementById('bp-b3').textContent = h; }
		window.__playDraftAnim();
	};

	window.__playKineticAnim = function() {
		const h = document.getElementById('kn-hero');
		const s = document.getElementById('kn-sub');
		if (!h) return;
		[h, s].forEach(el => el && el.classList.remove('active'));
		setTimeout(() => h && h.classList.add('active'), 150);
		setTimeout(() => s && s.classList.add('active'), 600);
	};

	window.__applyKineticCustom = function() {
		const h = document.getElementById('inp-kt-h')?.value;
		const s = document.getElementById('inp-kt-s')?.value;
		if (h) { COMPONENT_DATA.kinetic.hero = h; document.getElementById('kn-hero').textContent = h; }
		if (s) { COMPONENT_DATA.kinetic.sub = s; document.getElementById('kn-sub').textContent = s; }
		window.__playKineticAnim();
	};

	window.__viewVideo = function(src, title) {
		updatePreviewToVideo(title, src);
		// 切換 tab
		document.querySelectorAll('.preview-tab').forEach(b => b.classList.toggle('active', b.dataset.type === 'video'));
	};

	// 初始預設右側畫面
	updatePreviewToVideo('C 迴圈邊界：手帳手寫筆記本樣片', '/out/C-lanshu_notebook.mp4', '1080p · 嵐叔 v3-notebook · 實測對齊');

	// ---------------- 對話邏輯與互動 ----------------
	function appendMessage(role, contentHtml) {
		const msg = el('div', `chat-message-bubble ${role}`);
		const avatar = el('div', 'chat-avatar', role === 'ai' ? '🤖' : '👤');
		const body = el('div', 'chat-body');
		body.innerHTML = contentHtml;
		msg.append(avatar, body);
		chatMessages.append(msg);
		chatMessages.scrollTop = chatMessages.scrollHeight;
	}

	// 初始歡迎訊息
	appendMessage('ai', `
		<p><b>你好！我是你的教材製作 AI 助手。</b></p>
		<p>你可以直接貼上教材文字，或問我「<i>我不懂某某知識點，能用影片解釋嗎？</i>」</p>
		<div class="chat-prompt-chips">
			<button class="chip-btn" data-act="ask_boundary">💡 我不懂迴圈邊界條件（< 或 <=），能用影片解釋嗎？</button>
			<button class="chip-btn" data-act="analyze_pointers">📑 這是一份 C 語言指標教材，請幫我分析重點並規劃製作</button>
			<button class="chip-btn" data-act="search_chart">📊 我想比較線性搜尋與二元搜尋的效能數據</button>
			<button class="chip-btn" data-act="show_styles">🎨 看看目前有哪些可用的視覺風格元件？</button>
		</div>
	`);

	// 點擊快捷推薦
	chatMessages.addEventListener('click', e => {
		const btn = e.target.closest('.chip-btn');
		if (!btn) return;
		const act = btn.dataset.act;

		if (act === 'ask_boundary') {
			appendMessage('user', '我不懂迴圈邊界條件（< 或 <=），能用影片解釋嗎？');
			setTimeout(() => {
				appendMessage('ai', `
					<p>🔍 正在搜尋素材庫...</p>
					<div class="chat-card hit-card">
						<div class="hit-icon">🎯</div>
						<div class="hit-content">
							<h4>素材庫已命中現成教材！</h4>
							<p>找到<b>《C 迴圈邊界：手帳手寫推導與動態文字》</b>（時長 13.4s，已完成配音與動態渲染）。</p>
							<p class="text-success">✨ <b>無需重新付費生成</b>，已即時在右側為您展開播放器！</p>
							<div class="hit-actions">
								<button class="btn btn-sm btn-primary" onclick="window.__viewVideo('/out/C-lanshu_notebook.mp4', 'C 迴圈手帳手寫筆記')">▶️ 播放手帳手寫版</button>
								<button class="btn btn-sm btn-secondary" onclick="window.__viewVideo('/out/C-y5_kinetic_type.mp4', 'C 迴圈柔和動態文字')">⚡ 播放動態文字版</button>
							</div>
						</div>
					</div>
				`);
				window.__viewVideo('/out/C-lanshu_notebook.mp4', 'C 迴圈邊界（素材庫直接調出）');
			}, 600);
		} else if (act === 'analyze_pointers') {
			appendMessage('user', '這是一份 C 語言指標教材，請幫我分析重點並規劃製作：<br><i>「指標是 C 語言的核心，存放變數的記憶體位址。透過 & 取得位址，透過 * 進行解引用修改值。常見錯誤包括野指標與記憶體洩漏...」</i>');
			setTimeout(() => {
				appendMessage('ai', `
					<p>已為您完成教材深度解析！拆解出 <b>5 個核心教學重點</b>：</p>
					<p class="text-muted">您可以直接勾選想要製作的重點，我會自動為每個重點配對最適風格：</p>
					<div class="chat-card checklist-card" id="pointer-topics-card">
						<label class="topic-item"><input type="checkbox" checked value="1"> <span><b>重點 1：指標與變數的記憶體位址</b> <span class="tag-badge">推薦：黑板粉筆推導</span></span></label>
						<label class="topic-item"><input type="checkbox" checked value="2"> <span><b>重點 2：解引用操作 *p 的讀寫機制</b> <span class="tag-badge">推薦：手帳鋼筆筆記</span></span></label>
						<label class="topic-item"><input type="checkbox" checked value="3"> <span><b>重點 3：Stack 與 Heap 記憶體空間劃分</b> <span class="tag-badge">推薦：工程藍圖圖紙</span></span></label>
						<label class="topic-item"><input type="checkbox" value="4"> <span><b>重點 4：野指標與記憶體洩漏陷阱</b> <span class="tag-badge">推薦：柔和動態文字</span></span></label>
						<label class="topic-item"><input type="checkbox" value="5"> <span><b>重點 5：函式傳址呼叫架構</b> <span class="tag-badge">推薦：Keynote UI 卡片</span></span></label>
						<div class="checklist-actions">
							<button class="btn btn-primary" id="btn-start-generate">🚀 確認重點，開始生成影片與簡報</button>
							<button class="btn btn-secondary" id="btn-select-all">全選</button>
						</div>
					</div>
				`);
			}, 700);
		} else if (act === 'search_chart') {
			appendMessage('user', '我想比較線性搜尋與二元搜尋的效能數據，有適合的元件嗎？');
			setTimeout(() => {
				appendMessage('ai', `
					<p>這非常適合使用我們的<b>數據圖表元件（<code>t3_finance_chart</code>）</b>！</p>
					<p>在百萬筆數據下，$O(n)$ 與 $O(\\log n)$ 的 50,000 倍差距，透過動態長條圖生長最直觀。已為您在右側畫布展開演算法對比效果：</p>
				`);
				updatePreviewToShowcase('chart');
				document.querySelectorAll('.preview-tab').forEach(b => b.classList.toggle('active', b.dataset.type === 'showcase'));
			}, 500);
		} else if (act === 'show_styles') {
			appendMessage('user', '看看目前有哪些可用的視覺風格元件？');
			setTimeout(() => {
				appendMessage('ai', `
					<p>已為您在右側展開<b>「課綱多元視覺風格工具箱」</b>！包含手帳方格紙、動態文字、Keynote 卡片、數據圖表、黑板粉筆與工程藍圖。您可以直接點選查看！</p>
				`);
				updatePreviewToShowcase('all');
				document.querySelectorAll('.preview-tab').forEach(b => b.classList.toggle('active', b.dataset.type === 'showcase'));
			}, 400);
		}
	});

	// 監聽「確認重點，開始生成」按鈕
	chatMessages.addEventListener('click', e => {
		if (e.target.id === 'btn-start-generate') {
			const checked = chatMessages.querySelectorAll('#pointer-topics-card input:checked').length;
			appendMessage('user', `我選好了這 ${checked} 個重點，開始製作吧！`);
			appendMessage('ai', `
				<div class="chat-card progress-card" id="gen-progress-card">
					<h4>⚙️ AI 教材流水線製作中...</h4>
					<p class="progress-step-text" id="prog-text">正在規劃教學腳本 (teaching_plan.json)...</p>
					<div class="progress-bar-bg"><div class="progress-bar-inner" id="prog-bar" style="width: 25%"></div></div>
				</div>
			`);
			// 模擬無縫進度推進
			const progText = document.getElementById('prog-text');
			const progBar = document.getElementById('prog-bar');
			setTimeout(() => {
				if (progText) progText.textContent = '🎙️ 正在呼叫 Gemini TTS 配音並檢查音素...';
				if (progBar) progBar.style.width = '60%';
			}, 800);
			setTimeout(() => {
				if (progText) progText.textContent = '🎨 正在合成黑板粉筆與手帳動畫影格...';
				if (progBar) progBar.style.width = '88%';
			}, 1600);
			setTimeout(() => {
				const card = document.getElementById('gen-progress-card');
				if (card) {
					card.className = 'chat-card success-card';
					card.innerHTML = `
						<h4>🎉 製作完成！已自動在右側展開成品</h4>
						<p>已依據您的選擇生成指標教學樣片，並已同步更新 PPT 簡報結構。</p>
						<div class="hit-actions">
							<button class="btn btn-sm btn-primary" onclick="window.__switchShowcase('chalk')">📺 查看黑板推導</button>
							<button class="btn btn-sm btn-secondary" onclick="window.__switchShowcase('drafting')">📐 查看藍圖記憶體</button>
						</div>
					`;
				}
				updatePreviewToShowcase('chalk');
				document.querySelectorAll('.preview-tab').forEach(b => b.classList.toggle('active', b.dataset.type === 'showcase'));
			}, 2400);
		} else if (e.target.id === 'btn-select-all') {
			chatMessages.querySelectorAll('#pointer-topics-card input').forEach(i => i.checked = true);
		}
	});

	// 現代化 AI 輸入卡片（ChatGPT / Claude 風格）
	chatFooter.innerHTML = `
		<div class="chat-input-card">
			<textarea id="chat-text-input" placeholder="貼上教材內容，或告訴我想學什麼知識點..." rows="1"></textarea>
			<div class="chat-input-bottom-row">
				<span class="chat-input-hint">↵ 發送 · Shift+↵ 換行</span>
				<button class="chat-send-icon-btn" id="chat-send-btn" title="發送訊息" aria-label="發送訊息">
					<svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
				</button>
			</div>
		</div>
	`;

	const inputEl = chatFooter.querySelector('#chat-text-input');
	inputEl.addEventListener('input', () => {
		inputEl.style.height = 'auto';
		inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
	});

	const sendMsg = () => {
		const val = inputEl.value.trim();
		if (!val) return;
		inputEl.value = '';
		inputEl.style.height = 'auto';
		appendMessage('user', val);
		setTimeout(() => {
			appendMessage('ai', `
				<p>收到您的教材需求：「<b>${val.slice(0, 30)}${val.length > 30 ? '...' : ''}</b>」</p>
				<p>正在分析該知識點的教學結構... 為您推薦右側的<b>視覺風格元件庫</b>！您可以點選右側上方任一元件進行文字客製化、位置調整，並即時檢視動態渲染效果！</p>
			`);
		}, 500);
	};

	chatFooter.querySelector('#chat-send-btn').onclick = sendMsg;
	inputEl.onkeydown = e => {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMsg();
		}
	};

	// 預覽 Tabs 切換
	previewHeader.querySelector('#preview-tabs').addEventListener('click', e => {
		const btn = e.target.closest('.preview-tab');
		if (!btn) return;
		document.querySelectorAll('.preview-tab').forEach(b => b.classList.toggle('active', b === btn));
		const type = btn.dataset.type;
		if (type === 'video') {
			updatePreviewToVideo('C 迴圈邊界：手帳手寫筆記本樣片', '/out/C-lanshu_notebook.mp4');
		} else if (type === 'deck') {
			previewContent.innerHTML = `
				<div class="preview-deck-container">
					<div class="preview-video-meta">
						<h3 class="preview-title">📑 教學簡報 Deck 預覽（原生可編輯卡片）</h3>
						<span class="preview-tag">依教學規劃自動排版 · 支援 PPTX 匯出</span>
					</div>
					<div class="mock-deck-slide">
						<h2>單元一：迴圈邊界條件與差一錯誤</h2>
						<div class="mock-slide-cards">
							<div class="slide-card">
								<h4>起點決定幾次？</h4>
								<p>從 <code>i = 0</code> 還是 <code>i = 1</code> 開始，決定了初始狀態。</p>
							</div>
							<div class="slide-card accent">
								<h4>最後一格要算嗎？</h4>
								<p><code>i < 5</code> (0~4 共 5 輪) vs <code>i <= 5</code> (0~5 共 6 輪)</p>
							</div>
						</div>
					</div>
					<div class="preview-btn-group">
						<button class="btn btn-primary" onclick="alert('正在匯出原生 PPTX...')">⬇️ 匯出可編輯 PPTX</button>
					</div>
				</div>
			`;
			const badge = previewHeader.querySelector('#preview-status-badge');
			if (badge) { badge.textContent = '簡報模式'; badge.className = 'badge'; }
		} else if (type === 'mindmap') {
			previewContent.innerHTML = `
				<div class="preview-mindmap-container">
					<div class="preview-video-meta">
						<h3 class="preview-title">🧠 概念心智圖（結構關係樹）</h3>
						<span class="preview-tag">依教學重點展開 · 點擊向外生長</span>
					</div>
					<div class="mock-mindmap-tree">
						<div class="mm-node root">迴圈邊界控制</div>
						<div class="mm-branches">
							<div class="mm-node">起點確認 (i=0)</div>
							<div class="mm-node highlight">終止判斷 (&lt; vs &lt;=)</div>
							<div class="mm-node">每輪更新 (i++)</div>
						</div>
					</div>
					<div class="preview-btn-group">
						<button class="btn btn-primary" onclick="alert('已匯出高清 SVG')">⬇️ 匯出 SVG 心智圖</button>
					</div>
				</div>
			`;
			const badge = previewHeader.querySelector('#preview-status-badge');
			if (badge) { badge.textContent = '心智圖模式'; badge.className = 'badge'; }
		} else if (type === 'showcase') {
			updatePreviewToShowcase('all');
		}
	});

	chatPanel.append(chatHeader, chatMessages, chatFooter);
	previewPanel.append(previewHeader, previewContent);
	container.append(chatPanel, previewPanel);

	return container;
}
