import {canPlan, canExecute, stagesFor, DECK_ID, MINDMAP_ID, PAPER_ID} from './state.mjs';
import {jobPath} from './api.mjs';
export const setText = (node, value) => {node.textContent = String(value ?? '');};
const el = id => document.getElementById(id);
const show = (id, yes) => {el(id).hidden = !yes;};
const clear = node => node.replaceChildren();
export function renderCatalog(state, dispatch) {
  const parent = el('catalog-cards'); clear(parent);
  for (const capability of state.catalog) {
    if (state.testMode ? capability.id !== PAPER_ID : capability.experimental) continue;
    const card = document.createElement('button'); card.type = 'button';
    card.className = 'capability'+(capability.availability === 'available' ? ' available' : '');
    card.disabled = capability.availability !== 'available';
    card.setAttribute('aria-pressed', String(state.capabilityId === capability.id));
    const body = document.createElement('span');
    const title = document.createElement('span'); title.className = 'capability-title'; setText(title, capability.label);
    const desc = document.createElement('small'); setText(desc, capability.description);
    body.append(title, desc);
    const badge = document.createElement('span'); badge.className = 'badge'+(capability.availability === 'available' ? ' ready' : '');
    setText(badge, capability.availability === 'available' ? '可製作' : '規劃中');
    card.append(body, badge);
    card.addEventListener('click', () => dispatch({type:'capability', value:capability.id}));
    parent.append(card);
  }
}
export function renderReview(review, jobId) {
  const parent = el('review-segments'); clear(parent);
  if (!review) return;
  const slides = new Map((review.slides || []).map(slide => [slide.slide_id, slide]));
  let currentSlide = null, group = null;
  for (const segment of review.segments || []) {
    if (segment.slide_id !== currentSlide) {
      currentSlide = segment.slide_id;
      group = document.createElement('div'); group.className = 'review-item';
      const heading = document.createElement('strong'); setText(heading, `投影片 ${currentSlide}`); group.append(heading);
      if (slides.has(currentSlide)) {
        const image = document.createElement('img');
        image.src = `${jobPath(jobId)}/slides/${encodeURIComponent(currentSlide)}`;
        image.alt = `投影片 ${currentSlide} 預覽`;
        image.addEventListener('error', () => image.remove()); group.append(image);
      }
      parent.append(group);
    }
    const label = document.createElement('label'); const id = `segment-${segment.slide_id}-${segment.idx}`;
    label.htmlFor = id; setText(label, `旁白段落 ${segment.idx + 1}`);
    const area = document.createElement('textarea'); area.id = id; area.value = segment.text;
    area.dataset.slideId = segment.slide_id; area.dataset.idx = segment.idx;
    group.append(label, area);
  }
}
export function editedSegments(review) {
  if (!review) return [];
  const areas = [...document.querySelectorAll('#review-segments textarea')];
  const current = areas.map(area => ({slide_id:area.dataset.slideId, idx:Number(area.dataset.idx), text:area.value}));
  return current.some((item, index) => item.text !== review.segments[index]?.text) ? current : [];
}
export function renderDeck(deck, page) {
  const slides = Array.isArray(deck?.slides) ? deck.slides : [];
  const slide = slides[page];
  const content = el('deck-slide-content'); clear(content);
  if (!slide) { setText(el('deck-slide-title'), '正在載入簡報…'); return; }
  const role = ['hook', 'concept', 'example', 'pitfall', 'summary'].includes(slide.role) ? slide.role : 'concept';
  content.className = `deck-slide-content deck-role-${role}`;
  setText(el('deck-counter'), deck.title);
  setText(el('deck-slide-title'), slide.title);
  setText(el('deck-page-label'), `${page + 1} / ${slides.length}`);
  setText(el('deck-speaker-notes'), slide.speaker_notes);
  setText(el('deck-source-quote'), slide.source_quote);
  el('deck-prev').disabled = page <= 0;
  el('deck-next').disabled = page >= slides.length - 1;
  const block = slide.blocks[0];
  if (block.type === 'code') {
    const pre = document.createElement('pre'); setText(pre, block.lines.join('\n')); content.append(pre);
  } else if (block.type === 'compare') {
    const columns = document.createElement('div'); columns.className = 'deck-compare';
    for (const side of [block.left, block.right]) {
      const column = document.createElement('div');
      const title = document.createElement('h4'); setText(title, side.title); column.append(title);
      const list = document.createElement('ul');
      for (const item of side.items) { const li = document.createElement('li'); setText(li, item); list.append(li); }
      column.append(list); columns.append(column);
    }
    content.append(columns);
  } else if (block.type === 'concept') {
    const diagram = document.createElement('div'); diagram.className = 'deck-concept';
    const center = document.createElement('strong'); center.className = 'deck-concept-center';
    setText(center, block.center); diagram.append(center);
    const branches = document.createElement('ul'); branches.className = 'deck-concept-branches';
    for (const item of block.items) {
      const branch = document.createElement('li');
      const title = document.createElement('h4'); setText(title, item.title);
      const text = document.createElement('p'); setText(text, item.text);
      branch.append(title, text); branches.append(branch);
    }
    diagram.append(branches); content.append(diagram);
  } else {
    const list = document.createElement(block.type === 'steps' ? 'ol' : 'ul');
    list.className = block.type === 'steps' ? 'deck-step-grid' : 'deck-point-grid';
    for (const item of block.items) { const li = document.createElement('li'); setText(li, item); list.append(li); }
    content.append(list);
    if (block.type === 'steps') {
      const direction = document.createElement('p'); direction.className = 'deck-flow-direction';
      setText(direction, '流程方向：依序 01 → 02 → …'); content.append(direction);
    }
  }
  if (slide.takeaway) {
    const takeaway = document.createElement('p'); takeaway.className = 'deck-takeaway';
    setText(takeaway, slide.takeaway); content.append(takeaway);
  }
}
export function renderMindmapSource(source, quote = '') {
  const panel = el('mindmap-source-text'); clear(panel);
  if (!source?.text) { setText(panel, '正在載入教材原文…'); return false; }
  const target = String(quote).replace(/\s+/g, ' ').trim();
  const index = target ? source.text.indexOf(target) : -1;
  if (index < 0) { setText(panel, source.text); return false; }
  const before = document.createElement('span'); setText(before, source.text.slice(0, index));
  const highlight = document.createElement('mark'); highlight.id = 'mindmap-source-highlight'; setText(highlight, source.text.slice(index, index + target.length));
  const after = document.createElement('span'); setText(after, source.text.slice(index + target.length));
  panel.append(before, highlight, after);
  return highlight;
}
export function renderMindmap(mindmap, source) {
  const evidence = el('mindmap-evidence'); clear(evidence);
  renderMindmapSource(source);
  if (!mindmap) { setText(el('mindmap-title'), '正在載入心智圖…'); return; }
  setText(el('mindmap-title'), mindmap.title);
  const jump = quote => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'mindmap-evidence-jump';
    setText(button, '在教材原文中查看'); button.disabled = !source?.text;
    button.addEventListener('click', () => {
      const matched = renderMindmapSource(source, quote);
      el('mindmap-source-details').open = true;
      matched?.scrollIntoView?.({block:'center', behavior:'smooth'});
    });
    return button;
  };
  for (const node of mindmap.nodes || []) {
    const item = document.createElement('li');
    const title = document.createElement('strong'); setText(title, node.label);
    const explanation = document.createElement('span'); setText(explanation, ` — ${node.explanation}`);
    const quote = document.createElement('blockquote'); setText(quote, node.source_quote);
    item.append(title, explanation, quote, jump(node.source_quote)); evidence.append(item);
  }
  const labels = new Map((mindmap.nodes || []).map(node => [node.id, node.label]));
  for (const edge of mindmap.edges || []) {
    const item = document.createElement('li');
    const relation = document.createElement('strong'); setText(relation, `${labels.get(edge.from) || edge.from} → ${labels.get(edge.to) || edge.to}：${edge.label}`);
    const quote = document.createElement('blockquote'); setText(quote, edge.source_quote);
    item.append(relation, quote, jump(edge.source_quote)); evidence.append(item);
  }
}
export function renderUsage(container, generation, normalization) {
  clear(container);
  const number = value => Number.isSafeInteger(value) && value >= 0 ? value.toLocaleString('en-US') : '未取得';
  for (const [title, usage] of [['本次生成', generation], ['教材整理（共用素材）', normalization]]) {
    const card = document.createElement('section'); card.className = 'usage-card';
    const heading = document.createElement('h3'); setText(heading, title);
    const total = document.createElement('p'); total.className = 'usage-total';
    const count = usage?.total_tokens;
    setText(total, count == null ? '未取得用量' : `${usage.complete ? '' : '至少 '}${number(count)} tokens`);
    const detail = document.createElement('p'); detail.className = 'usage-detail';
    setText(detail, usage ? `輸入 ${number(usage.input_tokens)} · 輸出 ${number(usage.output_tokens)} · 思考 ${number(usage.thinking_tokens)} · 呼叫 ${number(usage.call_count)} 次` : '此工作沒有可讀的用量紀錄');
    const cost = document.createElement('p'); cost.className = 'usage-detail';
    setText(cost, usage?.estimated_cost_usd == null ? '費用估算：未取得完整用量或適用單價' : `費用估算：US$${usage.estimated_cost_usd.toFixed(4)}`);
    card.append(heading, total, detail, cost);
    if (usage && !usage.complete) {
      const warning = document.createElement('p'); warning.className = 'usage-detail';
      setText(warning, '部分呼叫未回報用量，以上僅列已知消耗'); card.append(warning);
    }
    if (usage?.calls?.length) {
      const details = document.createElement('details');
      const summary = document.createElement('summary'); setText(summary, '查看各次模型用量');
      const list = document.createElement('ol');
      for (const call of usage.calls) {
        const item = document.createElement('li');
        setText(item, `${call.stage || '生成'} · ${call.model}：${number(call.total_tokens)} tokens`);
        list.append(item);
      }
      details.append(summary,list); card.append(details);
    }
    container.append(card);
  }
}
export function render(state, dispatch) {
  document.body.classList.toggle('has-result', state.uiPhase === 'result' && state.artifacts.length > 0);
  const normalizationUsage = (state.job?.source || state.source)?.normalization_usage;
  show('usage-panel', Boolean(state.job || normalizationUsage));
  if (state.job || normalizationUsage) renderUsage(el('usage-content'), state.job?.usage, normalizationUsage);
  if (state.job?.production_metrics) {
    const metrics = state.job.production_metrics;
    const card = document.createElement('section'); card.className = 'usage-card';
    const heading = document.createElement('h3'); setText(heading,'影片製作時間');
    const elapsed = document.createElement('p'); elapsed.className = 'usage-detail';
    setText(elapsed,`處理耗時：${Math.round(metrics.processing_seconds)} 秒（不含審稿等待）`);
    const duration = document.createElement('p'); duration.className = 'usage-detail';
    setText(duration,metrics.actual_duration_seconds == null ? '實際片長：語音生成後量測' : `實際片長：${(metrics.actual_duration_seconds / 60).toFixed(2)} 分鐘${metrics.within_requested_range === false ? ' · 超出期望範圍' : ''}`);
    card.append(heading,elapsed,duration); el('usage-content').append(card);
  }
  show('source-detail', Boolean(state.source));
  if (state.source) {
    setText(el('source-name'), state.source.original_name);
    const normalized = state.source.normalization_status === 'complete';
    setText(el('source-preview-label'), normalized ? 'AI 整理後預覽' : '原始抽取預覽（尚未完成 AI 整理）');
    setText(el('source-excerpt'), state.source.preview_excerpt);
    setText(el('source-raw-excerpt'), state.source.extracted_excerpt || state.source.preview_excerpt);
    el('source-raw-details').hidden = !normalized;
    setText(el('source-status'), normalized ? (state.source.normalization_attention
      ? `已用 ${state.source.normalization_model || 'AI'} 整理；${state.source.normalization_attention}請展開原始抽取內容，對照預覽後勾選確認。`
      : `已用 ${state.source.normalization_model || 'AI'} 整理，可對照原始抽取摘要`) :
      state.normalizationPhase === 'working' ? 'AI 正在整理文字與圖片資訊…' :
      state.normalizationPhase === 'failed' ? `整理未完成：${state.error}。教材仍是原始抽取稿，可重試。` :
      '原始抽取完成；請確認 AI 整理後再製作');
    el('normalization-review-label').hidden = !normalized || !state.source.normalization_attention;
    el('normalization-review').checked = state.normalizationReviewed;
    el('normalize-button').hidden = state.source.normalization_status === 'complete';
    el('normalize-button').disabled = state.busy;
  }
  el('plan-button').disabled = !canPlan(state);
  if (state.testMode) {
    const range = state.durationRange;
    const valid = Number.isSafeInteger(range?.min_seconds) && Number.isSafeInteger(range?.max_seconds) && range.min_seconds >= 30 && range.min_seconds <= range.max_seconds && range.max_seconds <= 600;
    setText(el('duration-error'), valid ? '' : '請填入 0.5–10 分鐘，最短不可大於最長。');
    el('duration-error').hidden = valid;
    for (const id of ['duration-min','duration-max']) el(id).setAttribute('aria-invalid', String(!valid));
  }
  el('execute-button').disabled = !canExecute(state);
  show('plan-panel', Boolean(state.planRecord));
  if (state.planRecord) {
    const plan = state.planRecord.plan;
    setText(el('plan-summary'), plan.summary);
    const step = plan.steps?.[0];
    const bounds = step?.options?.duration_range;
    const durationLabel = bounds ? `期望 ${bounds.min_seconds / 60}–${bounds.max_seconds / 60} 分鐘 · 講清楚重點優先` : `目標 ${step?.options?.duration_seconds} 秒`;
    setText(el('plan-detail'), step ? (step.capability_id === PAPER_ID ? `紙上連續動畫（A＋C）測試 · ${durationLabel} · 實際片長依語音` : step.capability_id === DECK_ID ? '線上簡報 · 逐頁預覽與審核' : step.capability_id === MINDMAP_ID ? '概念心智圖 · 圖像與來源引用審核' : `微課程影片 · ${step.options.duration_seconds} 秒 · 版型 ${step.options.layout}`) : '需要補充製作需求');
    const questions = el('plan-questions'); clear(questions);
    for (const question of plan.questions || []) { const p = document.createElement('p'); setText(p, question.message); questions.append(p); }
  }
  show('job-panel', Boolean(state.job));
  if (state.job) {
    setText(el('job-status'), ({queued:'排隊中',running:'製作中',awaiting_review:'等待講稿審核',done:'已完成',failed:'執行失敗'})[state.job.status] || state.job.status);
    setText(el('job-pct'), `${state.job.pct || 0}%`);
    el('job-progress').value = Math.max(0, Math.min(100, state.job.pct || 0));
    const stages = stagesFor(state.job.capability_id);
    const current = stages.find(stage => stage.id === state.job.stage);
    setText(el('job-stage'), state.job.status === 'awaiting_review' ? '講稿審核中，確認後繼續語音合成' :
      state.job.status === 'done' ? `${stages.length} 個階段全部完成` :
      current ? `目前階段：${current.label}` : '正在準備');
    const flow = el('stage-flow'); clear(flow);
    for (const stage of stages) {
      const item = document.createElement('li'); item.dataset.stage = stage.id;
      const label = document.createElement('span'); label.className = 'stage-label'; setText(label, stage.label);
      const statusLabel = document.createElement('span'); statusLabel.className = 'stage-status';
      const status = state.stageStatus[stage.id] || 'pending';
      item.className = `stage-${status}`;
      if (status === 'active') item.setAttribute('aria-current', 'step');
      setText(statusLabel, ({pending:'未開始', active:'進行中', complete:'已完成', failed:'失敗'})[status]);
      item.append(label, statusLabel); flow.append(item);
    }
  }
  show('review-panel', state.uiPhase === 'review');
  show('artifact-panel', state.uiPhase === 'result' && state.artifacts.length > 0);
  if (state.uiPhase === 'result' && state.artifacts.length) {
    const artifact = state.artifacts[0];
    const isDeck = artifact.kind === 'deck';
    const isMindmap = artifact.kind === 'mindmap';
    const isVideo = !isDeck && !isMindmap;
    show('deck-preview', isDeck);
    show('mindmap-preview', isMindmap);
    show('video-preview', isVideo);
    show('video-open', isVideo);
    show('video-download', isVideo);
    show('video-hint', isVideo);
    show('video-message', isVideo && !el('video-message').hidden);
    setText(el('result-title'), isDeck ? '線上簡報' : isMindmap ? '概念心智圖' : state.testMode ? '紙上連續動畫測試成果' : '微課程影片');
    if (!isMindmap) show('mindmap-download', false);
    if (isDeck) {
      renderDeck(state.deck, state.deckPage);
      const download = el('deck-download');
      download.hidden = artifact.status !== 'approved' || !artifact.download?.url;
      if (!download.hidden) { download.href = artifact.download.url; download.download = artifact.download.file_name; }
    } else if (isMindmap) {
      show('deck-download', false);
      const image = el('mindmap-image');
      const url = `${artifact.preview.url}?view=svg`;
      if (image.getAttribute('src') !== url) image.src = url;
      setText(el('mindmap-dialog-title'), state.mindmap?.title || '概念心智圖');
      renderMindmap(state.mindmap, state.mindmapSource);
      const download = el('mindmap-download');
      download.hidden = artifact.status !== 'approved' || !artifact.download?.url;
      if (!download.hidden) { download.href = artifact.download.url; download.download = artifact.download.file_name; }
    } else {
      show('deck-download', false);
      const preview = el('video-preview');
      if (preview.getAttribute('src') !== artifact.preview.url) { preview.src = artifact.preview.url; preview.load(); }
      el('video-open').href = artifact.preview.url;
      el('video-download').href = artifact.download.url;
      el('video-download').download = artifact.download.file_name;
    }
    setText(el('artifact-status'), ({needs_review:'待核可',approved:'已核可',rejected:'已退回'})[artifact.status] || artifact.status);
    el('artifact-approve').disabled = artifact.status !== 'needs_review';
    el('artifact-reject').disabled = artifact.status !== 'needs_review';
  }
  show('reset-button', state.uiPhase === 'failed');
  show('error', Boolean(state.error || state.job?.error));
  setText(el('error'), state.error || state.job?.error?.safe_message || '');
}
