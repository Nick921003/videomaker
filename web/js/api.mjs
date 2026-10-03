export const segment = value => encodeURIComponent(String(value));
export const jobPath = id => `/api/studio/jobs/${segment(id)}`;
export const artifactPath = id => `/api/studio/artifacts/${segment(id)}`;
export const sourcePayload = source => ({kind:source.kind, ref:source.ref, revision:source.revision});
export const planPayload = (instruction, source, durationRange = null) => ({contract_version:'1.0', instruction, source:sourcePayload(source),
  ...(durationRange ? {duration_range:{...durationRange}} : {})});
export const safeError = (payload, status) => {
  const message = payload?.error;
  const error = new Error(typeof message === 'string' && message.length < 300 ? message : `請求失敗（${status}）`);
  if (payload?.source && typeof payload.source === 'object') error.source = payload.source;
  return error;
};
export const acceptEvent = (lastSeq, event) => Number.isSafeInteger(event?.seq) && event.seq > lastSeq;

export class StudioApi {
  constructor(fetcher = (...args) => fetch(...args)) { this.fetcher = fetcher; this.token = ''; }
  async request(path, options = {}, mayRefresh = true) {
    const method = (options.method || 'GET').toUpperCase();
    const headers = {...options.headers};
    if (method !== 'GET') headers['X-Studio-CSRF'] = this.token;
    const response = await this.fetcher(path, {...options, headers});
    let payload = null;
    try { payload = await response.json(); } catch { /* empty response */ }
    // The server checks CSRF before reading or applying a mutation. A rejected
    // request can therefore be retried once after its process-local token rotates.
    if (mayRefresh && method !== 'GET' && response.status === 403 && payload?.code === 'csrf_failed') {
      await this.session();
      return this.request(path, options, false);
    }
    if (!response.ok) throw safeError(payload, response.status);
    return payload;
  }
  async session() { const data = await this.request('/api/studio/session'); this.token = data.csrf_token; return data; }
  catalog(testMode = false) { return this.request('/api/studio/catalog'+(testMode ? '?experiments=paper' : '')); }
  upload(file) { const form = new FormData(); form.append('file', file); return this.request('/api/studio/sources', {method:'POST', body:form}); }
  normalizeSource(source) { return this.request(`/api/studio/sources/${segment(source.ref)}/normalize`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({revision:source.revision})}); }
  plan(instruction, source, testMode = false, durationRange = null) { return this.request('/api/studio/plans?mode='+(testMode ? 'paper-test' : 'rule'), {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(planPayload(instruction, source, testMode ? durationRange : null))}); }
  createJob(planId) { return this.request('/api/studio/jobs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({plan_id:planId})}); }
  snapshot(id) { return this.request(jobPath(id)); }
  deckPreview(url) { return this.request(url); }
  mindmapSource(id) { return this.request(jobPath(id)+'/source'); }
  review(id) { return this.request(jobPath(id)+'/review'); }
  submitReview(id, segments) { return this.request(jobPath(id)+'/review', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({segments})}); }
  reviewArtifact(id, decision) { return this.request(artifactPath(id)+'/review', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({decision})}); }
  removeSource(ref) { return this.request(`/api/studio/sources/${segment(ref)}`, {method:'DELETE'}); }
}

export function connectEvents(jobId, after, {onEvent, onSnapshot, onError}, makeSource = url => new EventSource(url)) {
  let source = null, timer = null, closed = false, lastSeq = after, retries = 0;
  const stop = () => { closed = true; if (source) source.close(); if (timer) clearTimeout(timer); };
  const open = () => {
    if (closed) return;
    source = makeSource(`${jobPath(jobId)}/events?after=${lastSeq}`);
    source.onmessage = message => {
      try {
        const event = JSON.parse(message.data);
        if (acceptEvent(lastSeq, event)) { lastSeq = event.seq; retries = 0; onEvent(event); }
      } catch { onError?.(new Error('事件資料無法讀取')); }
    };
    source.addEventListener('snapshot', message => {
      try { const snapshot = JSON.parse(message.data); onSnapshot(snapshot); if (['done','failed'].includes(snapshot.status)) stop(); }
      catch { onError?.(new Error('工作狀態無法讀取')); }
    });
    source.onerror = () => {
      source.close();
      if (closed) return;
      const delay = Math.min(8000, 500 * 2 ** Math.min(retries++, 4));
      timer = setTimeout(open, delay);
    };
  };
  open();
  return {stop, get lastSeq() {return lastSeq;}};
}
