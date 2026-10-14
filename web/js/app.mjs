import {StudioApi, connectEvents} from './api.mjs';
import {initialState, reduce, canPlan, canExecute, DECK_ID, MINDMAP_ID, PAPER_ID} from './state.mjs';
import {render, renderCatalog, renderReview, editedSegments, setText} from './render.mjs';
const api = new StudioApi();
let state = initialState(document.body.dataset.paperTest === 'true'), connection = null, poller = null, countdown = null, reviewLoaded = false, videoTimer = null, deckLoading = null, mindmapLoading = null;
const jobStorageKey = state.testMode ? 'studio.paperTestJobId' : 'studio.jobId';
const el = id => document.getElementById(id);
const VIDEO_PROMPT = '把這份教材做成 90 秒的微課程影片';
const PAPER_PROMPT = '用紙上連續動畫講清楚教材重點，幫我理解過程與狀態變化';
const DECK_PROMPT = '把這份教材做成線上簡報';
const MINDMAP_PROMPT = '把這份教材做成心智圖，幫我理解概念關係';
const suggestedPrompt = id => id === PAPER_ID ? PAPER_PROMPT : id === DECK_ID ? DECK_PROMPT : id === MINDMAP_ID ? MINDMAP_PROMPT : VIDEO_PROMPT;
function dispatch(action) {
  const wasResult = state.uiPhase === 'result';
  state = reduce(state, action);
  if (action.type === 'capability' && [VIDEO_PROMPT, DECK_PROMPT, MINDMAP_PROMPT].includes(state.instruction)) {
    const prompt = suggestedPrompt(state.capabilityId);
    state = reduce(state, {type:'instruction', value:prompt});
    el('instruction').value = prompt;
  }
  render(state, dispatch);
  if (!wasResult && state.uiPhase === 'result' && state.artifacts.length) {
    requestAnimationFrame(() => el('artifact-panel').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'}));
  }
  if (action.type === 'catalog' || action.type === 'capability' || action.type === 'plan') renderCatalog(state, dispatch);
}
const error = err => dispatch({type:'error', message:err?.message || '操作失敗，請再試一次'});
const busy = value => dispatch({type:'busy', value});
function stopJob() {
  connection?.stop(); connection = null;
  if (poller) clearInterval(poller); poller = null;
  if (countdown) clearInterval(countdown); countdown = null;
}
async function loadDeck(snapshot) {
  const artifact = snapshot.artifacts?.find(item => item.kind === 'deck');
  if (snapshot.status !== 'done' || !artifact || state.deck) return;
  if (!deckLoading) deckLoading = api.deckPreview(artifact.preview.url).then(deck => {
    if (state.job?.job_id === snapshot.job_id) dispatch({type:'deck', deck});
  }).finally(() => {deckLoading = null;});
  return deckLoading;
}
async function loadMindmap(snapshot) {
  const artifact = snapshot.artifacts?.find(item => item.kind === 'mindmap');
  if (snapshot.status !== 'done' || !artifact || state.mindmap) return;
  if (!mindmapLoading) mindmapLoading = Promise.all([
    api.deckPreview(artifact.preview.url), api.mindmapSource(snapshot.job_id),
  ]).then(([mindmap, source]) => {
    if (source.revision !== snapshot.source?.revision) throw new Error('教材版本不一致，請重新整理');
    if (state.job?.job_id === snapshot.job_id) dispatch({type:'mindmap', mindmap, source});
  }).finally(() => {mindmapLoading = null;});
  return mindmapLoading;
}
async function refreshJob(id) {
  const snapshot = await api.snapshot(id);
  dispatch({type:'snapshot', snapshot});
  await loadDeck(snapshot);
  await loadMindmap(snapshot);
  if (snapshot.status === 'awaiting_review' && !reviewLoaded) {
    reviewLoaded = true;
    try { const review = await api.review(id); dispatch({type:'review', review}); renderReview(review, id); startCountdown(review.deadline); }
    catch (err) { reviewLoaded = false; error(err); }
  }
  if (snapshot.status !== 'awaiting_review') reviewLoaded = false;
  if (['done','failed'].includes(snapshot.status)) stopJob();
  return snapshot;
}
function startCountdown(deadline) {
  if (countdown) clearInterval(countdown);
  const tick = () => setText(el('review-countdown'), `剩餘 ${Math.max(0,Math.ceil(deadline-Date.now()/1000))} 秒`);
  tick(); countdown = setInterval(tick, 500);
}
function watchJob(id) {
  stopJob(); reviewLoaded = false;
  connection = connectEvents(id, state.lastSeq, {
    onEvent: event => {dispatch({type:'event', seq:event.seq, event}); refreshJob(id).catch(error);},
    onSnapshot: snapshot => {dispatch({type:'snapshot', snapshot}); loadDeck(snapshot).catch(error); loadMindmap(snapshot).catch(error); if (['done','failed'].includes(snapshot.status)) stopJob();},
    onError: error,
  });
  poller = setInterval(() => refreshJob(id).catch(error), 1200);
  refreshJob(id).catch(error);
}
async function onFile(file) {
  if (!file) return;
  setText(el('file-name'), file.name);
  busy(true);
  try {
    const result = await api.upload(file);
    dispatch({type:'source', source:result.source});
    if (!state.instruction) { el('instruction').value = suggestedPrompt(state.capabilityId); dispatch({type:'instruction', value:el('instruction').value}); }
  } catch (err) { error(err); }
  finally { busy(false); }
}
async function onNormalize() {
  if (!state.source || state.source.normalization_status === 'complete') return;
  dispatch({type:'normalizationStart'});
  busy(true);
  try { const name = state.source.original_name; const result = await api.normalizeSource(state.source); dispatch({type:'source', source:{...result.source, original_name:name}}); }
  catch (err) { dispatch({type:'normalizationFailed', source:err?.source, message:err?.message || 'AI 整理失敗，請再試一次'}); }
  finally { busy(false); }
}
async function onPlan() {
  if (!canPlan(state)) return;
  const requestKey = () => JSON.stringify([state.instruction,state.source?.ref,state.source?.revision,state.durationRange,state.capabilityId]);
  const key = requestKey();
  busy(true);
  try {
    const record = await api.plan(state.instruction, state.source, state.testMode, state.durationRange);
    if (key === requestKey()) dispatch({type:'plan', record});
  }
  catch (err) { error(err); }
  finally { busy(false); }
}
async function onExecute() {
  if (!canExecute(state)) return;
  busy(true);
  try {
    const result = await api.createJob(state.planRecord.plan_id);
    sessionStorage.setItem(jobStorageKey, result.job_id);
    dispatch({type:'job', jobId:result.job_id, capabilityId:state.capabilityId}); watchJob(result.job_id);
  } catch (err) { error(err); }
  finally { busy(false); }
}
async function submitReview(segments) {
  busy(true);
  try {
    const result = await api.submitReview(state.job.job_id, segments);
    if (!result.ok) { error(new Error(result.errors?.[0]?.safe_message || '講稿尚未通過驗證')); reviewLoaded = false; await refreshJob(state.job.job_id); }
    else { reviewLoaded = false; await refreshJob(state.job.job_id); }
  } catch (err) { error(err); }
  finally { busy(false); }
}
async function decide(decision) {
  const artifact = state.artifacts[0];
  if (artifact?.status !== 'needs_review') return;
  busy(true);
  try { const result = await api.reviewArtifact(artifact.artifact_id, decision); dispatch({type:'artifact', artifact:result.artifact}); }
  catch (err) { error(err); }
  finally { busy(false); }
}
async function reset() {
  stopJob(); sessionStorage.removeItem(jobStorageKey);
  if (videoTimer) clearTimeout(videoTimer); videoTimer = null;
  el('video-preview').removeAttribute('src'); el('video-preview').load();
  el('video-message').hidden = true;
  const oldSource = state.source;
  dispatch({type:'reset'}); el('source-file').value = ''; el('instruction').value = ''; setText(el('file-name'),'尚未選擇檔案');
  if (state.testMode) { el('duration-min').value = '3'; el('duration-max').value = '5'; }
  renderCatalog(state, dispatch);
  if (oldSource) try {await api.removeSource(oldSource.ref);} catch { /* temporary source cleanup is best effort */ }
}
async function init() {
  el('source-file').addEventListener('change', event => onFile(event.target.files?.[0]));
  el('instruction').addEventListener('input', event => dispatch({type:'instruction', value:event.target.value}));
  if (state.testMode) {
    const durationChanged = () => {
      const seconds = id => el(id).checkValidity() ? Math.round(el(id).valueAsNumber * 60) : NaN;
      dispatch({type:'durationRange',value:{min_seconds:seconds('duration-min'),max_seconds:seconds('duration-max')}});
    };
    el('duration-min').addEventListener('input', durationChanged);
    el('duration-max').addEventListener('input', durationChanged);
  }
  for (const button of document.querySelectorAll('[data-example]')) button.addEventListener('click', () => {
    el('instruction').value = button.dataset.example; dispatch({type:'instruction', value:button.dataset.example});
  });
  el('normalize-button').addEventListener('click', onNormalize);
  el('normalization-review').addEventListener('change', event => dispatch({type:'normalizationReview', value:event.target.checked}));
  el('plan-button').addEventListener('click', onPlan);
  el('execute-button').addEventListener('click', onExecute);
  el('review-original').addEventListener('click', () => submitReview([]));
  el('review-submit').addEventListener('click', () => submitReview(editedSegments(state.review)));
  el('artifact-approve').addEventListener('click', () => decide('approve'));
  el('artifact-reject').addEventListener('click', () => decide('reject'));
  const mindmapDialog = el('mindmap-dialog');
  const mindmapPan = el('mindmap-pan');
  const largeMindmap = el('mindmap-large-image');
  let mindmapZoom = 1, panStart = null;
  function setMindmapZoom(value, resetPosition = false) {
    if (!largeMindmap.naturalWidth || !largeMindmap.naturalHeight) return;
    const centerX = (mindmapPan.scrollLeft + mindmapPan.clientWidth / 2) / Math.max(1, mindmapPan.scrollWidth);
    const centerY = (mindmapPan.scrollTop + mindmapPan.clientHeight / 2) / Math.max(1, mindmapPan.scrollHeight);
    mindmapZoom = Math.max(0.1, Math.min(4, value));
    largeMindmap.style.width = `${Math.round(largeMindmap.naturalWidth * mindmapZoom)}px`;
    largeMindmap.style.height = `${Math.round(largeMindmap.naturalHeight * mindmapZoom)}px`;
    setText(el('mindmap-zoom-level'), `${Math.round(mindmapZoom * 100)}%`);
    requestAnimationFrame(() => {
      mindmapPan.classList.toggle('pannable', mindmapPan.scrollWidth > mindmapPan.clientWidth || mindmapPan.scrollHeight > mindmapPan.clientHeight);
      mindmapPan.scrollLeft = resetPosition ? 0 : centerX * mindmapPan.scrollWidth - mindmapPan.clientWidth / 2;
      mindmapPan.scrollTop = resetPosition ? Math.max(0, (mindmapPan.scrollHeight - mindmapPan.clientHeight) / 2) : centerY * mindmapPan.scrollHeight - mindmapPan.clientHeight / 2;
    });
  }
  el('mindmap-open').addEventListener('click', () => {
    const preview = el('mindmap-image');
    if (!preview.getAttribute('src') || mindmapDialog.open) return;
    largeMindmap.onload = () => setMindmapZoom(1, true);
    largeMindmap.src = preview.src;
    mindmapDialog.showModal();
    if (largeMindmap.complete && largeMindmap.naturalWidth) setMindmapZoom(1, true);
  });
  el('mindmap-zoom-out').addEventListener('click', () => setMindmapZoom(mindmapZoom / 1.25));
  el('mindmap-zoom-in').addEventListener('click', () => setMindmapZoom(mindmapZoom * 1.25));
  el('mindmap-fit').addEventListener('click', () => setMindmapZoom(Math.min(
    (mindmapPan.clientWidth - 32) / largeMindmap.naturalWidth,
    (mindmapPan.clientHeight - 32) / largeMindmap.naturalHeight)));
  el('mindmap-close').addEventListener('click', () => mindmapDialog.close());
  mindmapPan.addEventListener('pointerdown', event => {
    if (event.button !== 0 || !mindmapPan.classList.contains('pannable')) return;
    panStart = {id:event.pointerId, x:event.clientX, y:event.clientY,
      left:mindmapPan.scrollLeft, top:mindmapPan.scrollTop};
    mindmapPan.setPointerCapture(event.pointerId);
    mindmapPan.classList.add('dragging');
    event.preventDefault();
  });
  mindmapPan.addEventListener('pointermove', event => {
    if (!panStart || event.pointerId !== panStart.id) return;
    mindmapPan.scrollLeft = panStart.left - (event.clientX - panStart.x);
    mindmapPan.scrollTop = panStart.top - (event.clientY - panStart.y);
  });
  const stopMindmapPan = event => {
    if (!panStart || event.pointerId !== panStart.id) return;
    if (mindmapPan.hasPointerCapture(event.pointerId)) mindmapPan.releasePointerCapture(event.pointerId);
    panStart = null;
    mindmapPan.classList.remove('dragging');
  };
  mindmapPan.addEventListener('pointerup', stopMindmapPan);
  mindmapPan.addEventListener('pointercancel', stopMindmapPan);
  el('deck-prev').addEventListener('click', () => dispatch({type:'deckPage', page:state.deckPage - 1}));
  el('deck-next').addEventListener('click', () => dispatch({type:'deckPage', page:state.deckPage + 1}));
  el('reset-button').addEventListener('click', reset);
  el('result-reset').addEventListener('click', reset);
  const video = el('video-preview');
  const message = el('video-message');
  video.addEventListener('loadstart', () => {
    message.textContent = '正在載入影片…'; message.hidden = false;
    if (videoTimer) clearTimeout(videoTimer);
    videoTimer = setTimeout(() => { if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) message.textContent = '載入時間較長，可以試著在新分頁播放。'; }, 8000);
  });
  const videoReady = () => { if (videoTimer) clearTimeout(videoTimer); videoTimer = null; message.hidden = true; };
  video.addEventListener('loadeddata', videoReady);
  video.addEventListener('canplay', videoReady);
  video.addEventListener('playing', videoReady);
  video.addEventListener('error', () => { if (videoTimer) clearTimeout(videoTimer); videoTimer = null; message.textContent = '此視窗無法播放影片，請在新分頁開啟或下載 MP4。'; message.hidden = false; });
  render(state, dispatch);
  try {
    await api.session();
    const catalog = await api.catalog(state.testMode); dispatch({type:'catalog', catalog:catalog.capabilities});
    const linkedId = new URLSearchParams(location.search).get('job');
    const oldId = /^[a-f0-9]{32}$/.test(linkedId || '') ? linkedId : sessionStorage.getItem(jobStorageKey);
    if (oldId) {
      try { const snapshot = await api.snapshot(oldId); dispatch({type:'job', jobId:oldId, capabilityId:snapshot.capability_id}); dispatch({type:'snapshot', snapshot});
        await loadDeck(snapshot); await loadMindmap(snapshot); if (!['done','failed'].includes(snapshot.status)) watchJob(oldId); }
      catch {sessionStorage.removeItem(jobStorageKey); error(new Error('本機服務重啟，工作狀態已清除'));}
    }
  } catch (err) {error(err);}
}
init();
