import {test} from 'node:test';
import assert from 'node:assert/strict';
import {segment, jobPath, planPayload, safeError, acceptEvent, StudioApi} from '../../web/js/api.mjs';
test('opaque IDs are encoded and payload includes source identity', () => {
  assert.equal(segment('a/b?c'), 'a%2Fb%3Fc');
  assert.equal(jobPath('a/b'), '/api/studio/jobs/a%2Fb');
  assert.deepEqual(planPayload('影片', {kind:'upload',ref:'material:a',revision:'sha256:x',private_path:'/secret'}),
    {contract_version:'1.0',instruction:'影片',source:{kind:'upload',ref:'material:a',revision:'sha256:x'}});
});
test('safe errors and SSE cursor reject repeats', () => {
  assert.equal(safeError({error:'忙碌'},409).message, '忙碌');
  assert.equal(safeError({error:{secret:'/home/x'}},500).message, '請求失敗（500）');
  assert.equal(acceptEvent(2,{seq:2}),false);
  assert.equal(acceptEvent(2,{seq:3}),true);
});
test('normalization errors carry the source usage to the UI', () => {
  const source = {ref:'material:a', revision:'sha256:x', normalization_usage:{total_tokens:42}};
  assert.deepEqual(safeError({error:'整理失敗', source},422).source,source);
});
test('mutations include CSRF token', async () => {
  const calls=[];
  const api=new StudioApi(async (url, options) => {calls.push({url,options});return {ok:true,json:async()=>({csrf_token:'t'})};});
  await api.session();
  await api.createJob('p');
  assert.equal(calls[1].options.headers['X-Studio-CSRF'],'t');
});
test('paper test catalog and plan use explicit isolated modes', async () => {
  const urls=[];
  const api=new StudioApi(async url => {urls.push(url);return {ok:true,json:async()=>({})};});
  await api.catalog(true);
  await api.plan('水循環',{kind:'upload',ref:'a',revision:'b'},true);
  assert.deepEqual(urls,['/api/studio/catalog?experiments=paper','/api/studio/plans?mode=paper-test']);
});

test('stale CSRF token is refreshed and the rejected mutation retries once', async () => {
  let serverToken = 'old';
  const calls = [];
  const api = new StudioApi(async (path, options) => {
    calls.push({path, token:options.headers['X-Studio-CSRF']});
    if (path === '/api/studio/session') return {ok:true,status:200,json:async()=>({csrf_token:serverToken})};
    if (options.headers['X-Studio-CSRF'] !== serverToken)
      return {ok:false,status:403,json:async()=>({code:'csrf_failed',error:'請求驗證失敗'})};
    return {ok:true,status:201,json:async()=>({source:{ref:'material:new'}})};
  });
  await api.session();
  serverToken = 'new';
  const result = await api.request('/api/studio/sources', {method:'POST', body:'upload'});
  assert.equal(result.source.ref, 'material:new');
  assert.deepEqual(calls.map(call=>call.path), [
    '/api/studio/session','/api/studio/sources','/api/studio/session','/api/studio/sources']);
  assert.deepEqual(calls.filter(call=>call.path.endsWith('/sources')).map(call=>call.token), ['old','new']);
});
test('persistent CSRF rejection stops after one retry', async () => {
  let mutations = 0;
  const api = new StudioApi(async (path) => path === '/api/studio/session'
    ? {ok:true,status:200,json:async()=>({csrf_token:'current'})}
    : (mutations++,{ok:false,status:403,json:async()=>({code:'csrf_failed',error:'請求驗證失敗'})}));
  await api.session();
  await assert.rejects(api.request('/api/studio/sources', {method:'POST', body:'upload'}), /請求驗證失敗/);
  assert.equal(mutations, 2);
});

test('paper duration range travels as structured seconds', async () => {
  let payload;
  const api=new StudioApi(async (url,options)=>{payload=JSON.parse(options.body);return {ok:true,json:async()=>({})};});
  await api.plan('重點清楚',{kind:'upload',ref:'a',revision:'b'},true,{min_seconds:180,max_seconds:300});
  assert.deepEqual(payload.duration_range,{min_seconds:180,max_seconds:300});
});
