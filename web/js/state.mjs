export const VIDEO_ID = 'video.micro_lesson.v1';
export const PAPER_ID = 'video.paper_preview.v1';
export const DECK_ID = 'slides.lesson_deck.v1';
export const MINDMAP_ID = 'mindmap.concept_overview.v1';
export const STAGES = Object.freeze([
  {id:'lesson', label:'教材結構化'},
  {id:'slides', label:'投影片繪製'},
  {id:'actions', label:'動作編排'},
  {id:'validate', label:'編排驗證'},
  {id:'storyboard', label:'審稿分鏡'},
  {id:'synth', label:'語音合成'},
  {id:'timeline', label:'時間軸編譯'},
  {id:'video', label:'影片渲染'},
]);
export const DECK_STAGES = Object.freeze([
  {id:'draft', label:'簡報內容生成'},
  {id:'validate', label:'內容與來源驗證'},
  {id:'publish', label:'建立線上預覽'},
]);
export const MINDMAP_STAGES = Object.freeze([
  {id:'draft', label:'概念與關係生成'},
  {id:'validate', label:'來源引用驗證'},
  {id:'publish', label:'建立心智圖預覽'},
]);
export const stagesFor = capabilityId => capabilityId === DECK_ID ? DECK_STAGES : capabilityId === MINDMAP_ID ? MINDMAP_STAGES : STAGES;
const blankStages = capabilityId => Object.fromEntries(stagesFor(capabilityId).map(stage => [stage.id, 'pending']));
function stagesFromSnapshot(current, snapshot, lastSeq) {
  const stages = stagesFor(snapshot.capability_id);
  if (snapshot.status === 'done') return Object.fromEntries(stages.map(stage => [stage.id, 'complete']));
  const index = stages.findIndex(stage => stage.id === snapshot.stage);
  if (snapshot.status === 'awaiting_review') {
    return Object.fromEntries(stages.map((stage, i) => [stage.id,
      i <= stages.findIndex(item => item.id === 'storyboard') ? 'complete' : current[stage.id]]));
  }
  if (snapshot.status === 'failed' && index >= 0) {
    return Object.fromEntries(stages.map((stage, i) => [stage.id,
      i < index ? 'complete' : i === index ? 'failed' : current[stage.id]]));
  }
  if (snapshot.status === 'running' && index >= 0 && lastSeq === 0) {
    return Object.fromEntries(stages.map((stage, i) => [stage.id,
      i < index ? 'complete' : i === index ? 'active' : current[stage.id]]));
  }
  return current;
}
export const initialState = (testMode = false) => ({
  uiPhase: 'compose', source: null, instruction: '', capabilityId: testMode ? PAPER_ID : VIDEO_ID, testMode,
  durationRange: testMode ? {min_seconds:180,max_seconds:300} : null,
  catalog: [], planRecord: null, job: null, review: null, artifacts: [],
  lastSeq: 0, stageStatus: blankStages(VIDEO_ID), normalizationPhase: 'idle', normalizationReviewed: false, deck: null, deckPage: 0, mindmap: null, mindmapSource: null, error: '', busy: false,
});
export const validDurationRange = range => Boolean(range && Number.isSafeInteger(range.min_seconds) && Number.isSafeInteger(range.max_seconds) && range.min_seconds >= 30 && range.min_seconds <= range.max_seconds && range.max_seconds <= 600);
export const canPlan = state => Boolean(state.source && state.source.normalization_status !== 'pending' && state.instruction.trim() && !state.busy && (!state.testMode || validDurationRange(state.durationRange)) && (!state.source.normalization_attention || state.normalizationReviewed));
export const canExecute = state => {
  const plan = state.planRecord?.plan;
  const step = plan?.steps?.[0];
  const capability = state.catalog.find(item => item.id === state.capabilityId);
  return state.uiPhase === 'plan_ready' && !state.busy && (!state.source?.normalization_attention || state.normalizationReviewed) && plan?.status === 'ready' &&
    plan.steps.length === 1 && capability?.availability === 'available' &&
    step?.capability_id === state.capabilityId &&
    ['kind', 'ref', 'revision'].every(key => state.source?.[key] === plan.source?.[key]);
};
export function reduce(state, action) {
  switch (action.type) {
    case 'catalog': return {...state, catalog: action.catalog};
    case 'source': return {...state, source: action.source, normalizationPhase: 'idle', normalizationReviewed: false, planRecord: null, uiPhase: 'compose', error: ''};
    case 'normalizationReview': return {...state, normalizationReviewed: Boolean(action.value), planRecord: null, uiPhase: 'compose'};
    case 'normalizationStart': return {...state, normalizationPhase: 'working', error: ''};
    case 'normalizationFailed': return {...state,
      source: action.source?.ref === state.source?.ref && action.source?.revision === state.source?.revision ? action.source : state.source,
      normalizationPhase: 'failed', error: action.message, busy: false};
    case 'instruction': return {...state, instruction: action.value, planRecord: null, uiPhase: 'compose'};
    case 'durationRange': return {...state, durationRange:{...action.value}, planRecord:null, uiPhase:'compose'};
    case 'capability': return {...state, capabilityId: action.value, planRecord: null, uiPhase: 'compose'};
    case 'plan': {
      const plan = action.record.plan;
      const plannedId = plan.status === 'ready' && plan.steps?.length === 1 ? plan.steps[0].capability_id : null;
      const available = state.catalog.some(item => item.id === plannedId && item.availability === 'available');
      return {...state, capabilityId: available ? plannedId : state.capabilityId, planRecord: action.record,
        uiPhase: plan.status === 'ready' ? 'plan_ready' : 'clarify', error: ''};
    }
    case 'job': {
      const capabilityId = action.capabilityId || state.capabilityId;
      return {...state, job: {job_id: action.jobId, status: 'queued', capability_id: capabilityId},
        uiPhase: 'working', review: null, artifacts: [], deck: null, deckPage: 0, mindmap: null, mindmapSource: null,
        lastSeq: 0, stageStatus: blankStages(capabilityId), error: ''};
    }
    case 'snapshot': return {...state, job: action.snapshot,
      stageStatus: stagesFromSnapshot(
        Object.keys(state.stageStatus).join() === stagesFor(action.snapshot.capability_id).map(stage => stage.id).join()
          ? state.stageStatus : blankStages(action.snapshot.capability_id), action.snapshot, state.lastSeq),
      artifacts: action.snapshot.artifacts || state.artifacts,
      uiPhase: action.snapshot.status === 'done' ? 'result' :
        action.snapshot.status === 'failed' ? 'failed' :
        action.snapshot.status === 'awaiting_review' ? 'review' : 'working'};
    case 'review': return {...state, review: action.review};
    case 'event': {
      if (!Number.isSafeInteger(action.seq) || action.seq <= state.lastSeq) return state;
      const stage = action.event?.payload?.stage;
      const eventName = action.event?.event;
      const status = ({stage_start:'active', stage_end:'complete', stage_fail:'failed'})[eventName];
      return {...state, lastSeq: action.seq,
        stageStatus: stagesFor(state.job?.capability_id).some(item => item.id === stage) && status ? {...state.stageStatus, [stage]:status} : state.stageStatus};
    }
    case 'deck': return {...state, deck: action.deck, deckPage: 0};
    case 'mindmap': return {...state, mindmap: action.mindmap, mindmapSource: action.source};
    case 'deckPage': return {...state, deckPage: Math.max(0, Math.min(
      (state.deck?.slides?.length || 1) - 1, Number.isInteger(action.page) ? action.page : 0))};
    case 'artifact': return {...state, artifacts: state.artifacts.map(item =>
      item.artifact_id === action.artifact.artifact_id ? action.artifact : item)};
    case 'busy': return {...state, busy: action.value};
    case 'error': return {...state, error: action.message, busy: false};
    case 'reset': return initialState(state.testMode);
    default: throw new Error(`Unknown action: ${action.type}`);
  }
}
