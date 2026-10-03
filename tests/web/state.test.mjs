import {test} from 'node:test';
import assert from 'node:assert/strict';
import {initialState, reduce, canPlan, canExecute, VIDEO_ID, MINDMAP_ID, STAGES} from '../../web/js/state.mjs';
const source = {kind:'upload', ref:'material:a', revision:'sha256:'+'a'.repeat(64)};
const plan = {status:'ready', source, steps:[{capability_id:VIDEO_ID}]};
const catalog = [{id:VIDEO_ID, availability:'available'}];
test('paper test mode survives reset and selects its own capability', () => {
  const state = initialState(true);
  assert.equal(state.testMode, true);
  assert.equal(state.capabilityId, 'video.paper_preview.v1');
  assert.equal(reduce(state, {type:'reset'}).capabilityId, 'video.paper_preview.v1');
  assert.equal(initialState().capabilityId, VIDEO_ID);
});
const ready = () => {
  let s = reduce(initialState(), {type:'catalog', catalog});
  s = reduce(s, {type:'source', source});
  s = reduce(s, {type:'instruction', value:'做成影片'});
  return reduce(s, {type:'plan', record:{plan_id:'p', plan}});
};
test('plan requires a source and instruction', () => {
  assert.equal(canPlan(initialState()), false);
  assert.equal(canPlan(reduce(initialState(), {type:'source', source})), false);
});
test('execute requires matching ready plan and available capability', () => {
  assert.equal(canExecute(ready()), true);
  assert.equal(canExecute(reduce(ready(), {type:'source', source:{...source, revision:'changed'}})), false);
  assert.equal(canExecute(reduce(ready(), {type:'instruction', value:'新指令'})), false);
  assert.equal(canExecute(reduce(ready(), {type:'capability', value:'slides.lesson_deck.v1'})), false);
  assert.equal(canExecute({...ready(), catalog:[{id:VIDEO_ID, availability:'planned'}]}), false);
});
test('ready mind map plan selects its capability after an example prompt', () => {
  let s = reduce(initialState(), {type:'catalog', catalog:[...catalog, {id:MINDMAP_ID, availability:'available'}]});
  s = reduce(s, {type:'source', source});
  s = reduce(s, {type:'instruction', value:'把這份教材做成心智圖，幫我理解概念關係'});
  s = reduce(s, {type:'plan', record:{plan_id:'map-plan', plan:{status:'ready', source, steps:[{capability_id:MINDMAP_ID}]}}});
  assert.equal(s.capabilityId, MINDMAP_ID);
  assert.equal(canExecute(s), true);
});
test('new job resets events and artifacts; terminal result can start over', () => {
  let s = {...ready(), lastSeq:9, artifacts:[{artifact_id:'old'}]};
  s = reduce(s, {type:'job', jobId:'new'});
  assert.equal(s.lastSeq, 0);
  assert.deepEqual(s.artifacts, []);
  s = reduce(s, {type:'snapshot', snapshot:{job_id:'new', status:'failed', artifacts:[]}});
  assert.equal(s.uiPhase, 'failed');
  assert.equal(reduce(s, {type:'reset'}).uiPhase, 'compose');
});
test('artifact review updates artifact only', () => {
  const s = {...ready(), job:{status:'done'}, artifacts:[{artifact_id:'a',status:'needs_review'}]};
  const updated = reduce(s, {type:'artifact', artifact:{artifact_id:'a',status:'rejected'}});
  assert.equal(updated.job.status, 'done');
  assert.equal(updated.artifacts[0].status, 'rejected');
  assert.throws(() => reduce(s, {type:'missing'}));
});

test('real stage events drive the eight-step workflow and reject replayed events', () => {
  let s = reduce(ready(), {type:'job', jobId:'job1'});
  assert.equal(STAGES.length, 8);
  assert.equal(s.stageStatus.lesson, 'pending');
  s = reduce(s, {type:'event', seq:1, event:{event:'stage_start', payload:{stage:'lesson'}}});
  assert.equal(s.stageStatus.lesson, 'active');
  s = reduce(s, {type:'event', seq:2, event:{event:'stage_end', payload:{stage:'lesson'}}});
  assert.equal(s.stageStatus.lesson, 'complete');
  s = reduce(s, {type:'event', seq:3, event:{event:'stage_start', payload:{stage:'slides'}}});
  assert.equal(s.stageStatus.slides, 'active');
  s = reduce(s, {type:'event', seq:2, event:{event:'stage_fail', payload:{stage:'slides'}}});
  assert.equal(s.stageStatus.slides, 'active');
  s = reduce(s, {type:'event', seq:4, event:{event:'stage_fail', payload:{stage:'slides'}}});
  assert.equal(s.stageStatus.slides, 'failed');
  assert.equal(s.lastSeq, 4);
});
test('terminal snapshots reconstruct workflow after page reload', () => {
  let s = reduce(initialState(), {type:'job', jobId:'job1'});
  s = reduce(s, {type:'snapshot', snapshot:{status:'done', pct:100, artifacts:[]}});
  assert.ok(STAGES.every(stage => s.stageStatus[stage.id] === 'complete'));
  s = reduce(initialState(), {type:'job', jobId:'job2'});
  s = reduce(s, {type:'snapshot', snapshot:{status:'failed', stage:'synth', pct:46, artifacts:[]}});
  assert.equal(s.stageStatus.lesson, 'complete');
  assert.equal(s.stageStatus.synth, 'failed');
  assert.equal(s.stageStatus.video, 'pending');
});
test('deck snapshots use three deck stages and preserve page navigation', () => {
  let s = reduce(initialState(), {type:'job', jobId:'deckjob', capabilityId:'slides.lesson_deck.v1'});
  s = reduce(s, {type:'snapshot', snapshot:{job_id:'deckjob', capability_id:'slides.lesson_deck.v1', status:'running', stage:'validate', pct:75, artifacts:[]}});
  assert.deepEqual(Object.keys(s.stageStatus), ['draft','validate','publish']);
  assert.equal(s.stageStatus.draft, 'complete');
  assert.equal(s.stageStatus.validate, 'active');
  s = reduce(s, {type:'deck', deck:{slides:[{slide_id:'s1'},{slide_id:'s2'}]}});
  s = reduce(s, {type:'deckPage', page:1});
  assert.equal(s.deckPage, 1);
  assert.equal(reduce(s, {type:'deckPage', page:7}).deckPage, 1);
});
test('mind map job uses its own stages and stores preview data', () => {
  let s = reduce(initialState(), {type:'job', jobId:'map', capabilityId:'mindmap.concept_overview.v1'});
  assert.deepEqual(Object.keys(s.stageStatus), ['draft','validate','publish']);
  s = reduce(s, {type:'snapshot', snapshot:{job_id:'map', capability_id:'mindmap.concept_overview.v1', status:'done', pct:100, artifacts:[]}});
  assert.equal(s.stageStatus.publish, 'complete');
  s = reduce(s, {type:'mindmap', mindmap:{root_id:'root'}});
  assert.equal(s.mindmap.root_id, 'root');
  assert.equal(reduce(s, {type:'job', jobId:'next'}).mindmap, null);
});

test('new uploads require confirmed AI normalization before planning', () => {
  let s = reduce(initialState(), {type:'source', source:{...source, normalization_status:'pending'}});
  s = reduce(s, {type:'instruction', value:'做成心智圖'});
  assert.equal(canPlan(s), false);
  s = reduce(s, {type:'source', source:{...source, normalization_status:'complete'}});
  assert.equal(canPlan(s), true);
});
test('normalization progress and failure remain visible beside the uploaded source', () => {
  let s = reduce(initialState(), {type:'source', source:{...source, normalization_status:'pending'}});
  s = reduce(s, {type:'normalizationStart'});
  assert.equal(s.normalizationPhase, 'working');
  s = reduce(s, {type:'normalizationFailed', message:'引文無法對回原文'});
  assert.equal(s.normalizationPhase, 'failed');
  assert.equal(s.error, '引文無法對回原文');
  s = reduce(s, {type:'source', source:{...source, normalization_status:'complete'}});
  assert.equal(s.normalizationPhase, 'idle');
});
test('normalization failure keeps reported usage for the matching source', () => {
  const s = reduce(initialState(), {type:'source',source});
  const failed = reduce(s, {type:'normalizationFailed',message:'失敗',source:{...source,normalization_usage:{total_tokens:42}}});
  assert.equal(failed.source.normalization_usage.total_tokens,42);
  const stale = reduce(s, {type:'normalizationFailed',message:'失敗',source:{...source,ref:'material:other'}});
  assert.deepEqual(stale.source,source);
});

test('unmatched AI citation requires source review before planning', () => {
  let s = reduce(initialState(), {type:'source', source:{...source, normalization_status:'complete', normalization_attention:'請核對'}});
  s = reduce(s, {type:'instruction', value:'做成心智圖'});
  assert.equal(canPlan(s), false);
  s = reduce(s, {type:'normalizationReview', value:true});
  assert.equal(canPlan(s), true);
  s = reduce(s, {type:'source', source:{...source, normalization_status:'complete', normalization_attention:'請核對'}});
  assert.equal(canPlan(s), false);
});

test('duration edits invalidate the old plan and reject invalid ranges', () => {
  let s={...initialState(true),source,instruction:'重點清楚',planRecord:{plan},uiPhase:'plan_ready'};
  assert.deepEqual(s.durationRange,{min_seconds:180,max_seconds:300});
  s=reduce(s,{type:'durationRange',value:{min_seconds:180,max_seconds:240}});
  assert.equal(s.planRecord,null);
  assert.equal(canPlan(s),true);
  for (const bounds of [{min_seconds:300,max_seconds:180},{min_seconds:NaN,max_seconds:300},{min_seconds:0,max_seconds:300}]) {
    assert.equal(canPlan(reduce(s,{type:'durationRange',value:bounds})),false);
  }
});
