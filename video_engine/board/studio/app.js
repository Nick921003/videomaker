/**
 * 教材影片工作室 — 前端核心應用 (app.js)
 * 遵循無框架、無 CDN、無建置步驟規範；支援即時 API 與 ?mock=1 模擬模式。
 */
(function () {
	"use strict";

	// 網址參數判斷是否啟用 mock 模式
	const urlParams = new URLSearchParams(window.location.search);
	const isMock = urlParams.get("mock") === "1" || window.location.protocol === "file:";

	// 應用程式全域狀態
	const state = {
		isMock: isMock,
		units: [],
		activeUnitId: null,
		activeUnit: null,
		selectedStoryIds: new Set(),
		activeJobId: null,
		pollTimer: null,
		pipelinesData: null,
		activeTab: "video",
		mockData: {
			units: [],
			unitDetails: {},
			jobs: {},
			pipelines: null,
			askAnswers: null
		}
	};

	// DOM 元素引用快取
	const dom = {
		mockBadge: document.getElementById("mock-badge"),
		unitList: document.getElementById("unit-list"),
		btnToggleAdd: document.getElementById("btn-toggle-add"),
		addUnitPanel: document.getElementById("add-unit-panel"),
		inputUnitTitle: document.getElementById("input-unit-title"),
		fileUnitMd: document.getElementById("file-unit-md"),
		inputUnitMd: document.getElementById("input-unit-md"),
		btnSubmitUnit: document.getElementById("btn-submit-unit"),
		btnCancelAdd: document.getElementById("btn-cancel-add"),
		mainContent: document.getElementById("main-content"),
		unitHeader: document.getElementById("unit-header"),
		askForm: document.getElementById("ask-form"),
		askInput: document.getElementById("ask-input"),
		quickPrompts: document.querySelector(".quick-prompts"),
		btnAskSubmit: document.getElementById("btn-ask-submit"),
		askResultArea: document.getElementById("ask-result-area"),
		scopeSection: document.getElementById("scope-section"),
		highlightSection: document.getElementById("highlight-section"),
		storiesList: document.getElementById("stories-list"),
		checkSelectAll: document.getElementById("check-select-all"),
		bottomBar: document.getElementById("bottom-action-bar"),
		bottomSummary: document.getElementById("bottom-summary"),
		btnGenerateSelected: document.getElementById("btn-generate-selected"),
		jobPanel: document.getElementById("job-panel"),
		jobStageText: document.getElementById("job-stage-text"),
		jobSpentText: document.getElementById("job-spent-text"),
		jobStatusBadge: document.getElementById("job-status-badge"),
		jobLogView: document.getElementById("job-log-view"),
		helpModal: document.getElementById("help-modal"),
		btnOpenHelp: document.getElementById("btn-open-help"),
		btnCloseHelp: document.getElementById("btn-close-help"),
		stepsTbody: document.getElementById("steps-tbody"),
		tabTotalBar: document.getElementById("tab-total-bar")
	};

	// ==================== API / MOCK 調用層 ====================

	/**
	 * 通用 API 請求函式，?mock=1 時自動改由本地 mock/*.json 與記憶體狀態服務
	 */
	async function apiRequest(endpoint, options = {}) {
		if (state.isMock) {
			return handleMockRequest(endpoint, options);
		}
		const res = await fetch(endpoint, {
			headers: { "Content-Type": "application/json", ...(options.headers || {}) },
			...options
		});
		if (!res.ok) {
			const err = await res.json().catch(() => ({ error: `伺服器回應錯誤 (${res.status})` }));
			throw new Error(err.error || `HTTP ${res.status}`);
		}
		return await res.json();
	}

	/**
	 * 模擬模式 (Mock) 的虛擬後端邏輯
	 */
	async function handleMockRequest(endpoint, options) {
		const method = (options.method || "GET").toUpperCase();

		// 1. GET /api/units
		if (endpoint === "/api/units" && method === "GET") {
			if (!state.mockData.units.length) {
				const res = await fetch("mock/units.json");
				state.mockData.units = await res.json();
			}
			return JSON.parse(JSON.stringify(state.mockData.units));
		}

		// 2. POST /api/units (建立新教材)
		if (endpoint === "/api/units" && method === "POST") {
			const body = JSON.parse(options.body || "{}");
			const newId = "u_sha256_" + Math.random().toString(36).substring(2, 8);
			const title = body.title || (body.markdown ? body.markdown.split("\n")[0].replace(/^#*\s*/, "") : "未命名教材");
			const newUnit = {
				unit_id: newId,
				title: title,
				created_at: new Date().toISOString().replace("T", " ").substring(0, 19),
				planned: false,
				videos: 0,
				spent_usd: 0.00
			};
			state.mockData.units.unshift(newUnit);
			state.mockData.unitDetails[newId] = {
				unit_id: newId,
				title: title,
				planned: false,
				spent_usd: 0.00,
				plan: null,
				jobs: []
			};
			return { unit_id: newId, created: true };
		}

		// 3. GET /api/units/<id>
		const unitMatch = endpoint.match(/^\/api\/units\/([a-zA-Z0-9_-]+)$/);
		if (unitMatch && method === "GET") {
			const unitId = unitMatch[1];
			if (!state.mockData.unitDetails[unitId]) {
				const filename = unitId === "u_sha256_02" ? "mock/unit_u_sha256_02.json" : "mock/unit_u_sha256_01.json";
				const res = await fetch(filename);
				const data = await res.json();
				data.unit_id = unitId;
				state.mockData.unitDetails[unitId] = data;
			}
			return JSON.parse(JSON.stringify(state.mockData.unitDetails[unitId]));
		}

		// 4. POST /api/units/<id>/plan
		const planMatch = endpoint.match(/^\/api\/units\/([a-zA-Z0-9_-]+)\/plan$/);
		if (planMatch && method === "POST") {
			const unitId = planMatch[1];
			const jobId = "job_plan_" + Date.now();
			createMockJob(jobId, unitId, "plan");
			return { job_id: jobId };
		}

		// 5. POST /api/units/<id>/videos
		const videoMatch = endpoint.match(/^\/api\/units\/([a-zA-Z0-9_-]+)\/videos$/);
		if (videoMatch && method === "POST") {
			const unitId = videoMatch[1];
			const body = JSON.parse(options.body || "{}");
			const jobId = "job_vid_" + Date.now();
			createMockJob(jobId, unitId, body.highlight ? "highlight" : "stories", body);
			return { job_id: jobId };
		}

		// 6. GET /api/jobs/<job_id>
		const jobMatch = endpoint.match(/^\/api\/jobs\/([a-zA-Z0-9_-]+)$/);
		if (jobMatch && method === "GET") {
			const jobId = jobMatch[1];
			const job = state.mockData.jobs[jobId];
			if (!job) throw new Error("找不到工作 " + jobId);
			return advanceMockJob(job);
		}

		// 7. POST /api/ask
		if (endpoint === "/api/ask" && method === "POST") {
			const body = JSON.parse(options.body || "{}");
			const q = (body.question || "").trim();
			if (!state.mockData.askAnswers) {
				const res = await fetch("mock/ask_answers.json");
				state.mockData.askAnswers = await res.json();
			}
			// 關鍵字比對預設回答
			for (const preset of state.mockData.askAnswers.presets) {
				if (preset.keywords.some(k => q.includes(k))) {
					const clone = JSON.parse(JSON.stringify(preset.response));
					// 根據當前單元影片狀態微調
					if (clone.story && state.activeUnit && state.activeUnit.plan) {
						const story = state.activeUnit.plan.stories.find(s => s.id === clone.story);
						if (story) {
							clone.video = story.video;
						}
					}
					return clone;
				}
			}
			return state.mockData.askAnswers.fallback_no_match;
		}

		// 8. GET /api/pipelines
		if (endpoint === "/api/pipelines" && method === "GET") {
			if (!state.mockData.pipelines) {
				const res = await fetch("mock/pipelines.json");
				state.mockData.pipelines = await res.json();
			}
			return state.mockData.pipelines;
		}

		throw new Error("Mock 尚未支援的端點: " + endpoint);
	}

	/**
	 * 建立模擬工作階段
	 */
	function createMockJob(jobId, unitId, kind, payload = {}) {
		state.mockData.jobs[jobId] = {
			job_id: jobId,
			unit_id: unitId,
			kind: kind,
			payload: payload,
			state: "running",
			stepIndex: 0,
			spent_usd: 0.015,
			error: null,
			stages: kind === "plan" ? [
				{ stage: "教材整理 (Gemini 3.8 Flash)", log: ["[INFO] 讀取 Markdown...", "[INFO] 呼叫 Gemini 3.8 Flash 整理觀念故事"], cost: 0.015 },
				{ stage: "本機自我檢查 (selftest)", log: ["[PASS] 14項元件量測閘測試通過", "[INFO] 建立分鏡結構與重點片組合"], cost: 0.015 },
				{ stage: "完成", log: ["[DONE] 教材規劃已寫入 plan.json"], cost: 0.015 }
			] : [
				{ stage: "分鏡製作 (Gemini 3.8 Flash)", log: ["[INFO] 產生 scene.json", "[INFO] 驗證閘檢查通過"], cost: 0.03 },
				{ stage: "配音合成 (GPT-SoVITS)", log: ["[INFO] TTS 音檔生成完畢", "[INFO] faster-whisper 漏字檢查無誤"], cost: 0.03 },
				{ stage: "出片渲染 (Playwright+ffmpeg)", log: ["[INFO] Canvas 畫面截圖錄製", "[DONE] 影音合成 1080p MP4 完成"], cost: 0.035 }
			]
		};
	}

	/**
	 * 每次輪詢前進一個階段
	 */
	function advanceMockJob(job) {
		const stageInfo = job.stages[job.stepIndex];
		const logs = [];
		for (let i = 0; i <= job.stepIndex; i++) {
			logs.push(...job.stages[i].log);
		}
		const isDone = job.stepIndex >= job.stages.length - 1;
		const response = {
			job_id: job.job_id,
			unit_id: job.unit_id,
			kind: job.kind,
			state: isDone ? "done" : "running",
			stage: stageInfo.stage,
			log: logs,
			spent_usd: stageInfo.cost,
			error: null
		};

		if (isDone) {
			// 更新該單元之 mock 資料狀態
			applyMockJobCompletion(job);
		} else {
			job.stepIndex++;
		}
		return response;
	}

	/**
	 * 當模擬工作完成時，更新單元物件以供後續查詢呈現最新結果
	 */
	function applyMockJobCompletion(job) {
		const unit = state.mockData.unitDetails[job.unit_id];
		if (!unit) return;

		if (job.kind === "plan") {
			unit.planned = true;
			unit.spent_usd += 0.015;
			unit.plan = {
				unit_title: unit.title,
				scope: {
					covers: ["基本觀念與操作", "核心邏輯與流程推導", "常見易錯點分析與防護"],
					not_covers: ["進階自訂樹狀資料結構", "外部非標準庫語法實作"]
				},
				stories: [
					{
						id: "q1",
						question: "這個觀念的核心前提是什麼？",
						also_asks: ["為什麼不能直接執行？"],
						title: "觀念前提與背景",
						sec: 60,
						screens: ["流程圖", "結構展開"],
						show: "圖解展示前提的重要性",
						status: "none",
						video: null,
						estimate_usd: 0.035
					},
					{
						id: "q2",
						question: "遇到邊界狀態時該如何處理？",
						also_asks: ["邊界交錯時會發生什麼？"],
						title: "邊界條件解析",
						sec: 65,
						screens: ["刻度尺", "動態指標"],
						show: "模擬指標移動至邊界臨界點",
						status: "none",
						video: null,
						estimate_usd: 0.035
					}
				],
				highlight: {
					stories: ["q1", "q2"],
					total_sec: 125,
					why: "整合核心前提與邊界防護兩大關鍵",
					status: "none",
					video: null,
					estimate_usd: 0.07
				}
			};
			// 同步更新清單項目
			const item = state.mockData.units.find(u => u.unit_id === job.unit_id);
			if (item) {
				item.planned = true;
				item.spent_usd = unit.spent_usd;
			}
		} else if (job.kind === "stories") {
			const storyIds = (job.payload && job.payload.stories) || [];
			if (unit.plan && unit.plan.stories) {
				unit.plan.stories.forEach(s => {
					if (storyIds.includes(s.id)) {
						s.status = "done";
						s.video = `/media/${job.unit_id}/${s.id}/video.mp4`;
						s.duration = s.sec || 60;
						s.cost_usd = 0.03;
						unit.spent_usd += 0.03;
					}
				});
				const doneCount = unit.plan.stories.filter(s => s.status === "done").length;
				const item = state.mockData.units.find(u => u.unit_id === job.unit_id);
				if (item) {
					item.videos = doneCount;
					item.spent_usd = unit.spent_usd;
				}
			}
		} else if (job.kind === "highlight") {
			if (unit.plan && unit.plan.highlight) {
				unit.plan.highlight.status = "done";
				unit.plan.highlight.video = `/media/${job.unit_id}/highlight/video.mp4`;
				unit.plan.highlight.duration = unit.plan.highlight.total_sec || 180;
				unit.spent_usd += 0.07;
			}
		}
	}

	// ==================== 頁面渲染邏輯 ====================

	/**
	 * 渲染左欄素材庫清單
	 */
	function renderUnitsList() {
		dom.unitList.innerHTML = "";
		if (!state.units.length) {
			dom.unitList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; padding: 12px;">尚無教材，請點擊上方按鈕新增</div>';
			return;
		}

		state.units.forEach(u => {
			const item = document.createElement("div");
			item.className = "unit-item" + (u.unit_id === state.activeUnitId ? " active" : "");
			item.setAttribute("role", "button");
			item.setAttribute("tabindex", "0");
			item.dataset.unitId = u.unit_id;

			const titleDiv = document.createElement("div");
			titleDiv.className = "unit-item-title";
			titleDiv.textContent = u.title;

			const metaDiv = document.createElement("div");
			metaDiv.className = "unit-item-meta";
			metaDiv.innerHTML = `
				<span>${u.planned ? "✓ 已規劃" : "待規劃"} · ${u.videos || 0} 部影片</span>
				<span>US$${(u.spent_usd || 0).toFixed(2)}</span>
			`;

			item.appendChild(titleDiv);
			item.appendChild(metaDiv);

			item.addEventListener("click", () => selectUnit(u.unit_id));
			item.addEventListener("keydown", (e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					selectUnit(u.unit_id);
				}
			});

			dom.unitList.appendChild(item);
		});
	}

	/**
	 * 選取特定教材並載入詳細資訊
	 */
	async function selectUnit(unitId) {
		state.activeUnitId = unitId;
		state.selectedStoryIds.clear();
		renderUnitsList();
		try {
			const data = await apiRequest(`/api/units/${unitId}`);
			state.activeUnit = data;
			renderActiveUnit();
		} catch (err) {
			alert("載入單元失敗: " + err.message);
		}
	}

	/**
	 * 渲染右欄目前選中教材內容
	 */
	function renderActiveUnit() {
		const unit = state.activeUnit;
		renderAskPrompts();
		if (!unit) return;

		// 1. 教材標題與摘要卡片
		dom.unitHeader.innerHTML = `
			<div>
				<h1 class="unit-headline">${escapeHtml(unit.title)}</h1>
				<div style="font-size: 0.775rem; color: var(--text-muted); margin-top: 4px;">
					單元 ID: <code>${escapeHtml(unit.unit_id)}</code>
				</div>
			</div>
			<div class="unit-meta-stats">
				<div class="stat-item">累計花費：<span class="stat-val">US$${(unit.spent_usd || 0).toFixed(3)}</span></div>
				${!unit.planned ? `
					<button id="btn-start-plan" class="btn btn-accent btn-sm" type="button">
						開始教材規劃 (AI)
					</button>
				` : ""}
			</div>
		`;

		const btnStartPlan = document.getElementById("btn-start-plan");
		if (btnStartPlan) {
			btnStartPlan.addEventListener("click", () => triggerUnitPlan(unit.unit_id));
		}

		// 若尚未規劃，隱藏故事與重點片區塊
		if (!unit.planned || !unit.plan) {
			dom.scopeSection.innerHTML = `
				<div style="text-align: center; padding: 24px; color: var(--text-muted);">
					<p style="font-size: 1rem; font-weight: 700; margin-bottom: 8px;">此教材尚未進行觀念規劃與分段</p>
					<p style="font-size: 0.85rem; margin-bottom: 14px;">點擊上方「開始教材規劃 (AI)」即可提取問題故事與估價</p>
				</div>
			`;
			dom.highlightSection.style.display = "none";
			dom.storiesList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.875rem; padding: 12px;">尚未產生故事</div>';
			updateBottomBar();
			return;
		}

		dom.highlightSection.style.display = "flex";

		// 2. 涵蓋範圍卡片 (Covers / Not covers)
		renderScope(unit.plan.scope);

		// 3. 重點片卡片
		renderHighlight(unit.plan.highlight);

		// 4. 問題故事清單
		renderStories(unit.plan.stories);

		// 5. 更新底部操作列
		updateBottomBar();
	}

	function renderAskPrompts() {
		const plan = state.activeUnit && state.activeUnit.plan;
		dom.quickPrompts.querySelectorAll(".quick-chip").forEach(chip => chip.remove());
		dom.quickPrompts.style.display = plan ? "" : "none";
		dom.askInput.placeholder = "先選一份教材";
		if (!plan) return;

		const stories = plan.stories || [];
		const firstQuestion = (stories[0] && stories[0].question) || "這個單元的重點是什麼？";
		dom.askInput.placeholder = `輸入學生的問題（例如：${firstQuestion}）`;
		const prompts = stories.map(story => {
			const title = Array.from(story.title || "");
			return {
				label: title.length > 12 ? title.slice(0, 11).join("") + "…" : title.join(""),
				question: story.question
			};
		});
		prompts.push({
			label: "單元重點",
			question: (plan.highlight && plan.highlight.question) || "這個單元的重點是什麼？"
		});
		const notCovers = plan.scope && plan.scope.not_covers;
		if (notCovers && notCovers.length) {
			prompts.push({ label: "超出範圍", question: `請問 ${notCovers[0]} 怎麼做？` });
		}
		prompts.forEach(prompt => {
			const chip = document.createElement("button");
			chip.type = "button";
			chip.className = "quick-chip";
			chip.textContent = prompt.label;
			chip.dataset.prompt = prompt.question;
			dom.quickPrompts.appendChild(chip);
		});
	}

	/**
	 * 渲染涵蓋範圍
	 */
	function renderScope(scope) {
		const covers = (scope && scope.covers) || [];
		const notCovers = (scope && scope.not_covers) || [];

		dom.scopeSection.innerHTML = `
			<div class="scope-grid">
				<div class="scope-col">
					<div class="scope-title scope-covers">
						<span aria-hidden="true">✓</span> 涵蓋範圍 (本單元深入解析)
					</div>
					<ul class="scope-list">
						${covers.map(c => `<li>${escapeHtml(c)}</li>`).join("")}
					</ul>
				</div>
				<div class="scope-col">
					<div class="scope-title scope-not-covers">
						<span aria-hidden="true">✗</span> 不涵蓋範圍 (避免混淆／多元教材鎖定)
					</div>
					<ul class="scope-list">
						${notCovers.map(nc => `<li>${escapeHtml(nc)}</li>`).join("")}
					</ul>
				</div>
			</div>
		`;
	}

	/**
	 * 渲染重點片 Card
	 */
	function renderHighlight(hl) {
		if (!hl) {
			dom.highlightSection.style.display = "none";
			return;
		}
		const isDone = hl.status === "done" && hl.video;
		dom.highlightSection.innerHTML = `
			<div class="card-topbar">
				<div>
					<h3 class="section-title">
						<span aria-hidden="true">🌟</span> 重點片 (單元精華總結)
					</h3>
					<div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 2px;">
						串聯段落：${(hl.stories || []).join(", ")} ｜ 總秒數：${hl.total_sec || 0} 秒
					</div>
				</div>
				<span class="badge ${isDone ? "badge-done" : "badge-none"}">
					${isDone ? "✓ 已出片" : "尚未生成"}
				</span>
			</div>
			<p style="font-size: 0.875rem; color: var(--text-main);">${escapeHtml(hl.why || "")}</p>
			${isDone ? `
				<div class="video-container">
					<video controls src="${escapeHtml(hl.video)}" poster=""></video>
				</div>
			` : `
				<div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
					<span style="font-size: 0.85rem; color: var(--text-muted);">
						預估花費：<strong style="color: var(--accent);">US$${(hl.estimate_usd || 0.1).toFixed(3)}</strong>
					</span>
					<button id="btn-generate-highlight" class="btn btn-accent btn-sm" type="button">
						生成重點片
					</button>
				</div>
			`}
		`;

		const btnHl = document.getElementById("btn-generate-highlight");
		if (btnHl) {
			btnHl.addEventListener("click", () => triggerHighlightVideo(state.activeUnitId));
		}
	}

	/**
	 * 渲染故事清單 Cards
	 */
	function renderStories(stories) {
		dom.storiesList.innerHTML = "";
		if (!stories || !stories.length) {
			dom.storiesList.innerHTML = '<div style="color: var(--text-muted); font-size: 0.875rem; padding: 12px;">無問題故事</div>';
			return;
		}

		stories.forEach(story => {
			const card = document.createElement("div");
			card.className = "story-card";
			card.id = `story-card-${story.id}`;

			const isDone = story.status === "done";
			const isRunning = story.status === "running" || story.status === "queued";
			const isChecked = state.selectedStoryIds.has(story.id);

			card.innerHTML = `
				<div class="story-header">
					<input type="checkbox" class="story-check" data-story-id="${story.id}"
						${isChecked ? "checked" : ""}
						${isDone || isRunning ? "disabled" : ""}>
					<div class="story-main">
						<h4 class="story-question">${escapeHtml(story.question)}</h4>
						<div class="story-subtitle">
							<strong>${escapeHtml(story.title || "")}</strong> · 建議時間：${story.sec || 60} 秒
						</div>
						<div class="story-screens">
							${(story.screens || []).map(s => `<span class="screen-chip">${escapeHtml(s)}</span>`).join("")}
						</div>
						${story.show ? `<div style="font-size: 0.775rem; color: var(--text-muted); margin-top: 4px;">必演重點：${escapeHtml(story.show)}</div>` : ""}
					</div>
					<span class="badge ${isDone ? "badge-done" : (isRunning ? "badge-running" : "badge-none")}">
						${isDone ? "✓ 已出片" : (isRunning ? "生成中" : "待生成")}
					</span>
				</div>
				${isDone && story.video ? `
					<div class="video-container">
						<video controls src="${escapeHtml(story.video)}"></video>
					</div>
				` : ""}
				<div class="story-footer">
					<span>${isDone ? `實際花費：US$${(story.cost_usd || 0.03).toFixed(3)} (${story.duration || story.sec}s)` : `預估花費：US$${(story.estimate_usd || 0.035).toFixed(3)}`}</span>
					${!isDone && !isRunning ? `
						<button class="btn btn-sm btn-single-gen" data-story-id="${story.id}" type="button">
							單獨生成這段
						</button>
					` : ""}
				</div>
			`;

			// 勾選框監聽
			const chk = card.querySelector(".story-check");
			chk.addEventListener("change", (e) => {
				if (e.target.checked) {
					state.selectedStoryIds.add(story.id);
				} else {
					state.selectedStoryIds.delete(story.id);
				}
				updateBottomBar();
			});

			// 單獨生成按鈕
			const btnSingle = card.querySelector(".btn-single-gen");
			if (btnSingle) {
				btnSingle.addEventListener("click", () => triggerStoriesVideo(state.activeUnitId, [story.id]));
			}

			dom.storiesList.appendChild(card);
		});
	}

	/**
	 * 更新底部統計欄與按鈕狀態
	 */
	function updateBottomBar() {
		const count = state.selectedStoryIds.size;
		const totalEst = count * 0.035;
		dom.bottomSummary.textContent = `已勾選 ${count} 段 ｜ 預估花費 US$${totalEst.toFixed(3)}`;
		dom.btnGenerateSelected.disabled = count === 0;
		dom.btnGenerateSelected.textContent = count > 0 ? `生成勾選的段落 (${count} 段)` : "生成勾選的段落";

		// 同步全選狀態
		if (state.activeUnit && state.activeUnit.plan && state.activeUnit.plan.stories) {
			const ungenerated = state.activeUnit.plan.stories.filter(s => s.status !== "done" && s.status !== "running");
			dom.checkSelectAll.checked = ungenerated.length > 0 && ungenerated.every(s => state.selectedStoryIds.has(s.id));
		}
	}

	// ==================== 學生提問入口處理 ====================

	/**
	 * 送出學生問題查詢 /api/ask
	 */
	async function submitStudentAsk() {
		const question = dom.askInput.value.trim();
		if (!question) return;
		if (!state.activeUnitId) {
			alert("請先從左側選擇一個教材單元！");
			return;
		}

		dom.btnAskSubmit.disabled = true;
		dom.btnAskSubmit.textContent = "比對中...";
		dom.askResultArea.style.display = "block";
		dom.askResultArea.innerHTML = '<div style="font-size: 0.85rem; color: var(--text-muted);">正在分析教材庫與觀念比對...</div>';

		try {
			const res = await apiRequest("/api/ask", {
				method: "POST",
				body: JSON.stringify({ unit_id: state.activeUnitId, question: question })
			});
			renderAskResult(res);
		} catch (err) {
			dom.askResultArea.innerHTML = `<div style="color: var(--accent); font-size: 0.85rem;">查詢失敗: ${err.message}</div>`;
		} finally {
			dom.btnAskSubmit.disabled = false;
			dom.btnAskSubmit.textContent = "查詢 / 提問";
		}
	}

	/**
	 * 渲染學生提問比對結果
	 */
	function renderAskResult(result) {
		const { kind, story: storyId, reason, video, closest } = result;

		let html = `<div class="ask-result">`;

		if (kind === "story") {
			const story = state.activeUnit && state.activeUnit.plan && state.activeUnit.plan.stories ? state.activeUnit.plan.stories.find(s => s.id === storyId) : null;
			html += `
				<div class="ask-result-header">
					<span>🎯 命中教材問題故事：${escapeHtml((story && story.question) || storyId)}</span>
					<span class="badge ${video ? "badge-done" : "badge-none"}">${video ? "在庫影片" : "未出片"}</span>
				</div>
				<p style="font-size: 0.825rem; color: var(--text-main);">${escapeHtml(reason || "")}</p>
			`;
			if (video) {
				html += `
					<div class="video-container" style="margin-top: 6px;">
						<video controls autoplay src="${escapeHtml(video)}"></video>
					</div>
				`;
			} else {
				html += `
					<div style="margin-top: 8px;">
						<button id="btn-ask-gen-story" class="btn btn-accent btn-sm" type="button">
							立即生成這段影片 (預估 US$0.035)
						</button>
					</div>
				`;
			}
		} else if (kind === "highlight") {
			html += `
				<div class="ask-result-header">
					<span>🌟 命中重點片（單元核心精華）</span>
				</div>
				<p style="font-size: 0.825rem; color: var(--text-main);">${escapeHtml(reason || "")}</p>
			`;
			if (video) {
				html += `
					<div class="video-container" style="margin-top: 6px;">
						<video controls autoplay src="${escapeHtml(video)}"></video>
					</div>
				`;
			} else {
				html += `
					<div style="margin-top: 8px;">
						<button id="btn-ask-gen-hl" class="btn btn-accent btn-sm" type="button">
							生成重點片
						</button>
					</div>
				`;
			}
		} else if (kind === "out_of_scope") {
			html += `
				<div class="ask-out-of-scope">
					<span aria-hidden="true" style="font-size: 1.25rem;">🔒</span>
					<span>這份教材沒有教這個，多元教材已鎖住</span>
				</div>
				<p style="font-size: 0.825rem; color: var(--text-muted); margin-top: 4px;">
					${escapeHtml(reason || "本問題涉及非本單元涵蓋之觀念或外部技術，為維持學習專注度不予生成。")}
				</p>
			`;
		} else {
			// no_match
			html += `
				<div style="font-weight: 700; font-size: 0.9rem; color: var(--text-muted);">
					🔍 未找到高度相符的故事段落
				</div>
				<p style="font-size: 0.825rem; color: var(--text-main); margin-top: 4px;">
					${escapeHtml(reason || "建議參考以下最相近的單元內容：")}
				</p>
			`;
			if (closest && closest.length) {
				html += `<div style="display: flex; gap: 8px; margin-top: 6px;">`;
				closest.forEach(id => {
					html += `<button class="btn btn-sm btn-jump-story" data-story-id="${id}" type="button">檢視 ${id}</button>`;
				});
				html += `</div>`;
			}
		}

		html += `</div>`;
		dom.askResultArea.innerHTML = html;

		// 綁定動態生成按鈕
		const btnGenStory = document.getElementById("btn-ask-gen-story");
		if (btnGenStory) {
			btnGenStory.addEventListener("click", () => triggerStoriesVideo(state.activeUnitId, [storyId]));
		}
		const btnGenHl = document.getElementById("btn-ask-gen-hl");
		if (btnGenHl) {
			btnGenHl.addEventListener("click", () => triggerHighlightVideo(state.activeUnitId));
		}
		dom.askResultArea.querySelectorAll(".btn-jump-story").forEach(btn => {
			btn.addEventListener("click", () => {
				const sid = btn.dataset.storyId;
				const target = document.getElementById(`story-card-${sid}`);
				if (target) target.scrollIntoView({ behavior: "smooth", block: "center" });
			});
		});
	}

	// ==================== 工作觸發與輪詢 (Job Polling) ====================

	/**
	 * 啟動教材規劃工作
	 */
	async function triggerUnitPlan(unitId) {
		try {
			const res = await apiRequest(`/api/units/${unitId}/plan`, { method: "POST" });
			if (res.job_id) {
				startJobPolling(res.job_id);
			} else {
				// 已有規劃
				selectUnit(unitId);
			}
		} catch (err) {
			alert("啟動教材規劃失敗: " + err.message);
		}
	}

	/**
	 * 啟動問題故事影片生成工作
	 */
	async function triggerStoriesVideo(unitId, storyIds) {
		if (!storyIds || !storyIds.length) return;
		try {
			const res = await apiRequest(`/api/units/${unitId}/videos`, {
				method: "POST",
				body: JSON.stringify({ stories: storyIds })
			});
			if (res.job_id) {
				startJobPolling(res.job_id);
			}
		} catch (err) {
			alert("啟動出片工作失敗: " + err.message);
		}
	}

	/**
	 * 啟動重點片生成工作
	 */
	async function triggerHighlightVideo(unitId) {
		try {
			const res = await apiRequest(`/api/units/${unitId}/videos`, {
				method: "POST",
				body: JSON.stringify({ highlight: true })
			});
			if (res.job_id) {
				startJobPolling(res.job_id);
			}
		} catch (err) {
			alert("啟動重點片工作失敗: " + err.message);
		}
	}

	/**
	 * 每 2 秒輪詢 /api/jobs/<job_id>
	 */
	function startJobPolling(jobId) {
		if (state.pollTimer) clearInterval(state.pollTimer);
		state.activeJobId = jobId;
		dom.jobPanel.style.display = "flex";
		dom.jobStatusBadge.className = "badge badge-running";
		dom.jobStatusBadge.textContent = "執行中";

		const poll = async () => {
			try {
				const job = await apiRequest(`/api/jobs/${jobId}`);
				dom.jobStageText.textContent = `階段：${job.stage || "處理中..."}`;
				dom.jobSpentText.textContent = `花費：US$${(job.spent_usd || 0).toFixed(3)}`;
				dom.jobLogView.textContent = (job.log || []).slice(-40).join("\n");
				dom.jobLogView.scrollTop = dom.jobLogView.scrollHeight;

				if (job.state === "done") {
					clearInterval(state.pollTimer);
					state.pollTimer = null;
					dom.jobStatusBadge.className = "badge badge-done";
					dom.jobStatusBadge.textContent = "完成";
					// 刷新單元與清單
					if (state.activeUnitId) {
						selectUnit(state.activeUnitId);
					}
					loadUnitsList();
				} else if (job.state === "failed") {
					clearInterval(state.pollTimer);
					state.pollTimer = null;
					dom.jobStatusBadge.className = "badge badge-none";
					dom.jobStatusBadge.textContent = "失敗: " + (job.error || "未知錯誤");
				}
			} catch (e) {
				console.error("輪詢工作失敗:", e);
			}
		};

		poll();
		state.pollTimer = setInterval(poll, 2000);
	}

	// ==================== 說明彈窗與分頁 (Help Modal) ====================

	/**
	 * 打開說明彈窗並載入 /api/pipelines 資料
	 */
	async function openHelpModal() {
		dom.helpModal.classList.add("open");
		if (!state.pipelinesData) {
			try {
				state.pipelinesData = await apiRequest("/api/pipelines");
				renderHelpTab(state.activeTab);
			} catch (e) {
				dom.tabTotalBar.textContent = "無法載入流程說明資料: " + e.message;
			}
		} else {
			renderHelpTab(state.activeTab);
		}
	}

	function closeHelpModal() {
		dom.helpModal.classList.remove("open");
	}

	function renderHelpTab(tabKey) {
		state.activeTab = tabKey;
		const tabs = dom.helpModal.querySelectorAll(".tab-btn");
		tabs.forEach(btn => {
			const active = btn.dataset.tab === tabKey;
			btn.classList.toggle("active", active);
			btn.setAttribute("aria-selected", active ? "true" : "false");
		});

		const pdata = state.pipelinesData && state.pipelinesData[tabKey];
		if (!pdata) return;

		dom.stepsTbody.innerHTML = (pdata.steps || []).map(s => `
			<tr>
				<td><strong>${escapeHtml(s.step)}</strong></td>
				<td><code>${escapeHtml(s.model)}</code></td>
				<td style="color: var(--accent); font-weight: 700;">${escapeHtml(s.cost)}</td>
				<td>${escapeHtml(s.desc)}</td>
			</tr>
		`).join("");

		dom.tabTotalBar.textContent = `合計：${pdata.total || ""}`;
	}

	// ==================== 事件綁定與初始化 ====================

	/**
	 * 載入素材庫清單
	 */
	async function loadUnitsList() {
		try {
			state.units = await apiRequest("/api/units");
			renderUnitsList();
			if (!state.activeUnitId && state.units.length > 0) {
				selectUnit(state.units[0].unit_id);
			}
		} catch (err) {
			console.error("載入素材庫失敗:", err);
		}
	}

	function initEventHandlers() {
		// Mock 提示標籤
		if (state.isMock) {
			dom.mockBadge.style.display = "inline-block";
		}

		// 新增教材切換
		dom.btnToggleAdd.addEventListener("click", () => {
			dom.addUnitPanel.classList.toggle("open");
		});
		dom.btnCancelAdd.addEventListener("click", () => {
			dom.addUnitPanel.classList.remove("open");
		});

		// 檔案選取自動帶入
		dom.fileUnitMd.addEventListener("change", (e) => {
			const file = e.target.files[0];
			if (file) {
				const reader = new FileReader();
				reader.onload = (evt) => {
					dom.inputUnitMd.value = evt.target.result;
					if (!dom.inputUnitTitle.value.trim()) {
						dom.inputUnitTitle.value = file.name.replace(/\.[^/.]+$/, "");
					}
				};
				reader.readAsText(file);
			}
		});

		// 建立教材送出
		dom.btnSubmitUnit.addEventListener("click", async () => {
			const title = dom.inputUnitTitle.value.trim();
			const markdown = dom.inputUnitMd.value.trim();
			if (!markdown) {
				alert("請貼上或選取 Markdown 教材內容！");
				return;
			}
			dom.btnSubmitUnit.disabled = true;
			dom.btnSubmitUnit.textContent = "建立中...";
			try {
				const res = await apiRequest("/api/units", {
					method: "POST",
					body: JSON.stringify({ title: title || undefined, markdown: markdown })
				});
				dom.addUnitPanel.classList.remove("open");
				dom.inputUnitTitle.value = "";
				dom.inputUnitMd.value = "";
				dom.fileUnitMd.value = "";
				await loadUnitsList();
				if (res.unit_id) {
					await selectUnit(res.unit_id);
					// 自動啟動規劃
					await triggerUnitPlan(res.unit_id);
				}
			} catch (err) {
				alert("建立教材失敗: " + err.message);
			} finally {
				dom.btnSubmitUnit.disabled = false;
				dom.btnSubmitUnit.textContent = "建立並開始規劃";
			}
		});

		// 全選未生成段落
		dom.checkSelectAll.addEventListener("change", (e) => {
			const checked = e.target.checked;
			if (state.activeUnit && state.activeUnit.plan && state.activeUnit.plan.stories) {
				state.activeUnit.plan.stories.forEach(s => {
					if (s.status !== "done" && s.status !== "running") {
						if (checked) {
							state.selectedStoryIds.add(s.id);
						} else {
							state.selectedStoryIds.delete(s.id);
						}
					}
				});
			}
			renderStories((state.activeUnit && state.activeUnit.plan && state.activeUnit.plan.stories) || []);
			updateBottomBar();
		});

		// 底部生成按鈕
		dom.btnGenerateSelected.addEventListener("click", () => {
			if (state.selectedStoryIds.size > 0 && state.activeUnitId) {
				triggerStoriesVideo(state.activeUnitId, Array.from(state.selectedStoryIds));
			}
		});

		// 提問表單
		dom.askForm.addEventListener("submit", (e) => {
			e.preventDefault();
			submitStudentAsk();
		});

		// 快速提問標籤點擊
		dom.quickPrompts.addEventListener("click", (e) => {
			const chip = e.target.closest(".quick-chip");
			if (!chip) return;
			dom.askInput.value = chip.dataset.prompt;
			submitStudentAsk();
		});

		// 說明彈窗
		dom.btnOpenHelp.addEventListener("click", openHelpModal);
		dom.btnCloseHelp.addEventListener("click", closeHelpModal);
		dom.helpModal.addEventListener("click", (e) => {
			if (e.target === dom.helpModal) closeHelpModal();
		});
		document.addEventListener("keydown", (e) => {
			if (e.key === "Escape" && dom.helpModal.classList.contains("open")) {
				closeHelpModal();
			}
		});

		// 說明分頁按鈕
		dom.helpModal.querySelectorAll(".tab-btn").forEach(btn => {
			btn.addEventListener("click", () => renderHelpTab(btn.dataset.tab));
		});
	}

	function escapeHtml(str) {
		if (typeof str !== "string") return "";
		return str.replace(/[&<>"']/g, m => ({
			"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
		}[m]));
	}

	// 啟動應用
	renderAskPrompts();
	initEventHandlers();
	loadUnitsList();
})();
