import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { api } from '../js/api.mjs';
import { withDOM, descendants, click, settle } from './dom-helper.mjs';

const fixture = async name => JSON.parse(await readFile(new URL(`../mock/${name}.json`, import.meta.url), 'utf8'));
const find = (host, label) => descendants(host).find(node => node.tagName === 'button' && node.textContent === label);

test('生成頁只勾未完成項目，總額隨勾選改變並送出選取的 items', async () => {
	await withDOM(async () => {
		const { renderMakeGenerate } = await import('../js/pages/make-generate.mjs');
		const unit = await fixture('unit-done');
		const original = { get: api.get, post: api.post };
		const calls = [];
		api.get = async path => path === '/formats' ? fixture('formats') : path === '/queue' ? fixture('queue-idle') : unit;
		api.post = async (path, body) => { calls.push({ path, body }); return { job_ids: [] }; };
		let page;
		try {
			page = await renderMakeGenerate(unit);
			const inputs = descendants(page).filter(node => node.tagName === 'input');
			assert.equal(inputs.length, 8);
			assert.equal(inputs.filter(node => node.checked).length, 2);
			assert.match(page.textContent, /US\$0\.115/);
			inputs.at(4).checked = false;
			inputs.at(4).dispatchEvent(new Event('change'));
			assert.match(page.textContent, /預估總計.*US\$0\.056/);
			click(find(page, '開始生成'));
			await settle();
			assert.deepEqual(calls, [{ path: `/units/${unit.unit_id}/generate`, body: { items: ['q4'] } }]);
		} finally { page?.dispose(); Object.assign(api, original); }
	});
});

test('live 圖跟隨工作、失敗才提供允許的重試；每 2 秒輪詢且隱藏或離頁即停止', async () => {
	await withDOM(async doc => {
		const { renderMakeGenerate } = await import('../js/pages/make-generate.mjs');
		const unit = await fixture('unit-analyzed');
		const registry = await fixture('formats');
		let job = await fixture('job-running');
		const original = { get: api.get, post: api.post, setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout };
		const timers = new Map();
		const calls = [];
		api.get = async path => { calls.push(path); return path === '/formats' ? registry : path === '/queue' ? { running: job.state === 'running' ? job : null, queued: [] } : path.startsWith('/jobs/') ? job : unit; };
		api.post = async path => { calls.push(path); job = { ...job, job_id: 'retried', state: 'running', error: null }; return { job_id: 'retried' }; };
		globalThis.setTimeout = (fn, ms) => { assert.equal(ms, 2000); timers.set(1, fn); return 1; };
		globalThis.clearTimeout = id => timers.delete(id);
		let page;
		try {
			page = await renderMakeGenerate(unit);
			page.mount();
			await settle();
			assert.ok(calls.includes(`/jobs/${job.job_id}`));
			assert.equal(descendants(page).find(node => node.getAttribute('data-node-id') === 'repair').getAttribute('data-state'), 'running');
			assert.equal(timers.size, 1);
			doc.hidden = true;
			doc.dispatchEvent(new Event('visibilitychange'));
			assert.equal(timers.size, 0);
			const count = calls.length;
			await settle();
			assert.equal(calls.length, count);
			job = { ...await fixture('job-failed'), job_id: job.job_id };
			doc.hidden = false;
			doc.dispatchEvent(new Event('visibilitychange'));
			await settle();
			assert.match(page.textContent, new RegExp(job.error.reason));
			assert.ok(page.textContent.includes(job.error.advice));
			assert.equal(descendants(page).find(node => node.getAttribute('data-node-id') === 'repair').getAttribute('data-state'), 'failed');
			const failedId = job.job_id;
			click(find(page, '重試'));
			await settle();
			assert.ok(calls.includes(`/jobs/${failedId}/retry`));
			const failed = await fixture('job-failed');
			job = { ...failed, job_id: 'retried', error: { ...failed.error, retry: false } };
			const tick = timers.get(1);
			timers.clear();
			await tick();
			await settle();
			assert.equal(find(page, '重試'), undefined);
			page.dispose();
			assert.equal(timers.size, 0);
		} finally { page?.dispose(); Object.assign(api, { get: original.get, post: original.post }); globalThis.setTimeout = original.setTimeout; globalThis.clearTimeout = original.clearTimeout; }
	});
});

test('成品只保留一個播放器，直接點選顯示 warning 並送句號重配後回③', async () => {
	await withDOM(async () => {
		const { renderMakeProducts } = await import('../js/pages/make-products.mjs');
		const unit = await fixture('unit-done');
		const originalPost = api.post;
		const calls = [];
		api.post = async (path, body) => { calls.push({ path, body }); return { job_id: 'redo-q2' }; };
		const page = renderMakeProducts(unit);
		try {
			page.mount();
			await settle();
			assert.equal(descendants(page).filter(node => node.tagName === 'video').length, 1);
			assert.match(page.textContent, /US\$0\.053/);
			const oldVideo = descendants(page).find(node => node.tagName === 'video');
			click(descendants(page).find(node => node.getAttribute('data-product-id') === 'q2'));
			await settle();
			assert.equal(oldVideo.paused, true);
			assert.equal(descendants(page).filter(node => node.tagName === 'video').length, 1);
			assert.ok(page.textContent.includes('第 3 句可能漏唸（檢查也可能誤判，請聽一下）'));
			assert.match(page.textContent, /US\$0\.058/);
			click(find(page, '重配這句'));
			await settle();
			assert.deepEqual(calls, [{ path: `/units/${unit.unit_id}/items/q2/renarrate`, body: { beats: [3] } }]);
			assert.match(globalThis.location.hash, /^#\/make\/3\?unit=ff9e559208c9&job=redo-q2$/);
		} finally { page.dispose(); api.post = originalPost; }
	});
});

test('簡報依 block 呈現版型，方向鍵只在 viewer 活著時翻頁且提供 PPTX', async () => {
	await withDOM(async doc => {
		const { mount, renderSlide } = await import('../js/viewers/deck.mjs');
		const deck = await fixture('deck');
		globalThis.fetch = async () => ({ ok: true, json: async () => deck });
		for (const slide of deck.slides) {
			const rendered = renderSlide(slide);
			assert.ok(rendered.textContent.includes(slide.title));
			assert.ok(rendered.textContent.includes(slide.takeaway));
		}
		const concept = renderSlide({ title: '概念', role: 'concept', blocks: [{ type: 'concept', center: '中心', items: [{ title: '分支', text: '說明' }] }] });
		assert.match(concept.textContent, /中心.*分支.*說明/);
		const host = doc.createElement('div');
		const viewer = await mount(host, { unit: 'u', item: 'slides', files: { deck: 'slides/deck.json', pptx: 'slides/deck.pptx' } });
		const key = () => { const event = new Event('keydown', { cancelable: true }); Object.defineProperty(event, 'key', { value: 'ArrowRight' }); doc.dispatchEvent(event); };
		assert.match(host.textContent, /1 \/ 7/);
		key();
		assert.match(host.textContent, /2 \/ 7/);
		const download = descendants(host).find(node => node.textContent === '下載 PPTX');
		assert.equal(download.href, '/media/u/slides/deck.pptx');
		viewer.dispose();
		key();
		assert.match(host.textContent, /2 \/ 7/);
	});
});

test('點選簡報頁籤後焦點進入 viewer，方向鍵可以直接翻頁', async () => {
	await withDOM(async doc => {
		const { renderMakeProducts } = await import('../js/pages/make-products.mjs');
		const deck = await fixture('deck');
		globalThis.fetch = async () => ({ ok: true, json: async () => deck });
		const page = renderMakeProducts(await fixture('unit-done'));
		try {
			page.mount();
			click(find(page, '簡報'));
			await settle();
			assert.equal(doc.activeElement?.getAttribute('aria-label'), '簡報，左右鍵翻頁、滾輪縮放、拖曳移動');
			const key = new Event('keydown', { cancelable: true });
			Object.defineProperty(key, 'key', { value: 'ArrowRight' });
			doc.dispatchEvent(key);
			assert.match(page.textContent, /2 \/ 7/);
		} finally { page.dispose(); }
	});
});

test('embed 資源是絕對 /web 路徑，路由從 pathname 解析並依 manifest 選 viewer', async () => {
	const html = await readFile(new URL('../embed.html', import.meta.url), 'utf8');
	assert.match(html, /href="\/web\/styles\.css"/);
	assert.match(html, /src="\/web\/js\/embed\.mjs"/);
	const { parseEmbedPath } = await import('../js/embed.mjs');
	assert.deepEqual(parseEmbedPath('/embed/a%26b/q2'), { unit: 'a&b', item: 'q2' });
	assert.equal(parseEmbedPath('/web/index.html'), null);
	assert.equal(parseEmbedPath('/embed/u/q2/extra'), null);
	const { mountEmbed } = await import('../js/embed.mjs');
	await withDOM(async doc => {
		const originalGet = api.get;
		let request;
		api.get = async path => { request = path; return fixture('manifest'); };
		let viewer;
		try {
			const host = doc.createElement('main');
			viewer = await mountEmbed(host, '/embed/ff9e559208c9/highlight');
			assert.equal(request, '/units/ff9e559208c9/manifest');
			assert.match(host.textContent, /重點片.*US\$0\.060/);
			assert.equal(descendants(host).filter(node => node.tagName === 'video').length, 1);
			assert.equal(descendants(host).find(node => node.tagName === 'video').src, '/media/ff9e559208c9/highlight/video.mp4');
			await assert.rejects(mountEmbed(host, '/embed/ff9e559208c9/missing'), /成品還沒準備好/);
		} finally { viewer?.dispose(); api.get = originalGet; }
	});
});

test('離頁後的舊佇列請求不再讀取工作或建立計時器', async () => {
	await withDOM(async () => {
		const { renderMakeGenerate } = await import('../js/pages/make-generate.mjs');
		const originalGet = api.get;
		const calls = [];
		let release;
		api.get = async path => {
			calls.push(path);
			if (path === '/formats') return fixture('formats');
			if (path === '/queue') return new Promise(resolve => { release = resolve; });
			throw new Error('不應繼續讀取舊頁');
		};
		const page = await renderMakeGenerate(await fixture('unit-analyzed'));
		try {
			page.mount();
			page.dispose();
			release(await fixture('queue-busy'));
			await settle();
			assert.deepEqual(calls, ['/formats', '/queue']);
		} finally { page.dispose(); api.get = originalGet; }
	});
});

test('重新生成同一項目後清掉歷史失敗與重試，不把舊紅色步驟當成目前結果', async () => {
	await withDOM(async () => {
		const { renderMakeGenerate } = await import('../js/pages/make-generate.mjs');
		const unit = await fixture('unit-done');
		const registry = await fixture('formats');
		const oldJob = await fixture('job-failed');
		const original = { get: api.get, post: api.post };
		let fresh = structuredClone(unit);
		const newJob = { ...oldJob, job_id: 'new-q4', state: 'done', error: null, steps: oldJob.steps.map(step => ({ ...step, state: 'done' })) };
		api.get = async path => path === '/formats' ? registry : path === '/queue' ? { running: null, queued: [] }
			: path.includes('/jobs/') ? path.endsWith('new-q4') ? newJob : oldJob : fresh;
		api.post = async () => {
			fresh.items.find(item => item.item === 'q4').job_id = 'new-q4';
			fresh.items.find(item => item.item === 'q4').status = 'done';
			return { job_ids: ['new-q4'] };
		};
		const page = await renderMakeGenerate(unit);
		try {
			page.mount();
			await settle();
			assert.ok(find(page, '重試'));
			click(find(page, '開始生成'));
			await settle();
			assert.equal(Boolean(find(page, '重試')), false);
			assert.equal(descendants(page).some(node => node.getAttribute('data-state') === 'failed'), false);
		} finally { page.dispose(); Object.assign(api, original); }
	});
});

test('相同的輪詢結果保留勾選框與鍵盤焦點', async () => {
	await withDOM(async doc => {
		const { renderMakeGenerate } = await import('../js/pages/make-generate.mjs');
		const unit = await fixture('unit-analyzed');
		const registry = await fixture('formats');
		const original = { get: api.get, setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout };
		let tick;
		api.get = async path => path === '/formats' ? registry : path === '/queue' ? { running: null, queued: [] } : structuredClone(unit);
		globalThis.setTimeout = fn => { tick = fn; return 1; };
		globalThis.clearTimeout = () => {};
		const page = await renderMakeGenerate(unit);
		try {
			page.mount();
			await settle();
			const input = descendants(page).find(node => node.tagName === 'input');
			input.focus();
			await tick();
			assert.equal(doc.activeElement, input);
			assert.equal(descendants(page).includes(input), true);
		} finally { page.dispose(); api.get = original.get; globalThis.setTimeout = original.setTimeout; globalThis.clearTimeout = original.clearTimeout; }
	});
});

test('生成成功加入工作才收合選擇，可展開且保留勾選；失敗仍留在選擇區', async () => {
 await withDOM(async () => {
  const { renderMakeGenerate } = await import('../js/pages/make-generate.mjs');
  const unit = await fixture('unit-analyzed');
  const original = { get: api.get, post: api.post };
  api.get = async path => path === '/formats' ? fixture('formats') : structuredClone(unit);
  let fail = true;
  api.post = async () => { if (fail) throw new Error('無法加入工作'); return { job_ids: ['new-job'] }; };
  const page = await renderMakeGenerate(unit);
  try {
   const input = descendants(page).find(node => node.tagName === 'input');
   input.checked=false; input.dispatchEvent(new Event('change'));
   click(find(page,'開始生成')); await settle();
   assert.equal(page.getAttribute('data-selection'),'expanded');
   fail=false; click(find(page,'開始生成')); await settle();
   assert.equal(page.getAttribute('data-selection'),'collapsed');
   click(find(page,'展開選擇'));
   assert.equal(page.getAttribute('data-selection'),'expanded');
   assert.equal(descendants(page).find(node=>node.tagName==='input').checked,false);
  } finally { page.dispose(); Object.assign(api,original); }
 });
});

test('成品可直接跳到第三點，停止舊影片；未製作項目只有製作入口', async () => {
 await withDOM(async doc => {
  const { renderMakeProducts } = await import('../js/pages/make-products.mjs');
  const page=renderMakeProducts(await fixture('unit-done'));
  try {
   page.mount(); await settle();
   const old=descendants(page).find(node=>node.tagName==='video');
   const choice=id=>descendants(page).find(node=>node.getAttribute('data-product-id')===id);
   assert.ok(choice('q3'));
   click(choice('q3')); await settle();
   assert.equal(old.paused,true);
   assert.match(descendants(page).find(node=>node.tagName==='video').src,/q3\/video.mp4$/);
   assert.equal(choice('q3').getAttribute('aria-pressed'),'true');
   assert.equal(doc.activeElement?.getAttribute('data-product-id'),'q3');
   click(choice('q5')); await settle();
   assert.equal(descendants(page).filter(node=>node.tagName==='video').length,0);
   assert.ok(find(page,'去選要生成的 →'));
   assert.equal(find(page,'下一點'),undefined);
  } finally { page.dispose(); }
 });
});

test('簡報能直接選第七頁，更新頁碼及講者筆記', async () => {
 await withDOM(async doc => {
  const { mount } = await import('../js/viewers/deck.mjs');
  const data=await fixture('deck');
  globalThis.fetch=async()=>({ok:true,json:async()=>data});
  const host=doc.createElement('div');
  const viewer=await mount(host,{unit:'u',files:{deck:'slides/deck.json'}});
  try {
   const select=descendants(host).find(node=>node.getAttribute('aria-label')==='選擇投影片');
   assert.ok(select); select.value='6'; select.dispatchEvent(new Event('change'));
   assert.match(host.textContent,/7 \/ 7/);
   assert.ok(host.textContent.includes(data.slides[6].speaker_notes));
  } finally { viewer.dispose(); }
 });
});

test('再點目前成品不重載影片，播放進度保持', async () => {
 await withDOM(async () => {
  const { renderMakeProducts } = await import('../js/pages/make-products.mjs');
  const page=renderMakeProducts(await fixture('unit-done'));
  try {
   page.mount();await settle();
   const current=descendants(page).find(node=>node.tagName==='video');current.currentTime=12;
   click(descendants(page).find(node=>node.getAttribute('data-product-id')==='q1'));await settle();
   assert.equal(descendants(page).find(node=>node.tagName==='video'),current);
   assert.equal(current.currentTime,12);
  } finally {page.dispose();}
 });
});

test('送出成功但進度讀取失敗，明示已送出並鎖住同批項目', async () => {
 await withDOM(async () => {
  const { renderMakeGenerate }=await import('../js/pages/make-generate.mjs');
  const unit=await fixture('unit-analyzed');const original={get:api.get,post:api.post};
  api.get=async path=>{if(path==='/formats')return fixture('formats');throw new Error('斷線');};
  api.post=async()=>({job_ids:['accepted']});
  const page=await renderMakeGenerate(unit);
  try {
   click(find(page,'開始生成'));await settle();
   assert.match(page.textContent,/工作已送出/);
   assert.equal(find(page,'開始生成').disabled,true);
   assert.equal(page.getAttribute('data-selection'),'collapsed');
  } finally {page.dispose();Object.assign(api,original);}
 });
});

test('過期工作不阻礙目前進度；相同佇列輪詢保留按鈕與焦點', async () => {
 await withDOM(async doc => {
  const { renderMakeGenerate }=await import('../js/pages/make-generate.mjs');
  const unit=await fixture('unit-analyzed');const job=await fixture('job-running');
  const original={get:api.get,setTimeout:globalThis.setTimeout,clearTimeout:globalThis.clearTimeout};let tick;
  api.get=async path=>{
   if(path==='/formats')return fixture('formats');
   if(path==='/queue')return {running:job,queued:[]};
   if(path==='/jobs/expired')throw Object.assign(new Error('expired'),{status:404});
   if(path.startsWith('/jobs/'))return job;
   return structuredClone(unit);
  };
  globalThis.setTimeout=fn=>{tick=fn;return 1;};globalThis.clearTimeout=()=>{};
  const page=await renderMakeGenerate(unit,{query:{job:'expired'}});
  try {
   page.mount();await settle();
   const row=descendants(page).find(node=>node.getAttribute('data-job-id')===job.job_id);
   assert.ok(row);row.focus();await tick();await settle();
   assert.ok(descendants(page).includes(row));assert.equal(doc.activeElement,row);
   assert.ok(descendants(page).find(node=>node.getAttribute('data-node-id')==='repair'));
  } finally {page.dispose();api.get=original.get;globalThis.setTimeout=original.setTimeout;globalThis.clearTimeout=original.clearTimeout;}
 });
});

test('手動先收合選擇後，右側仍能開始生成', async () => {
 await withDOM(async () => {
  const { renderMakeGenerate }=await import('../js/pages/make-generate.mjs');
  const unit=await fixture('unit-analyzed');const original={get:api.get,post:api.post};let sent=false;
  api.get=async path=>path==='/formats'?fixture('formats'):structuredClone(unit);
  api.post=async()=>{sent=true;return {job_ids:['accepted']};};
  const page=await renderMakeGenerate(unit);
  try {
   click(find(page,'收合選擇'));
   const start=find(page,'開始生成');
   assert.equal(start.hidden,false);
   assert.equal(start.parentElement.className,'generate-actions');
   click(start);await settle();assert.equal(sent,true);
  } finally {page.dispose();Object.assign(api,original);}
 });
});
