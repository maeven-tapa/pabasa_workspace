// Run the actual reader navigation/state functions with controlled save failures.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'),'utf8');
function section(start,end){const at=source.indexOf(start);assert.ok(at>=0,start);const to=source.indexOf(end,at+start.length);assert.ok(to>at,end);return source.slice(at,to);}
const copy=value=>JSON.parse(JSON.stringify(value));
function environment(extra={}){
 const events=[],messages=[];let state={stage:'words',task1_score:3};
 const values={Promise,Date,JSON,console:{debug(){},info(){},warn(){}},Math,URL,Set,
  window:{PABASA_USER_ID:1},localStorage:{setItem(){},getItem(){return null;}},
  isAdminPreview:false,liveStudentEndState:null,studentEndStateVersion:1,liveSessionId:'synthetic-live',
  officialAssessmentId:'fixture',materialId:'fixture',
  isCrla:true,isAssistMode:false,currentStoryState:'',currentSelectedStory:null,currentAssessmentUiMode:'standard',
  currentIndex:0,currentPageIndex:0,currentStorySegmentIndex:0,items:['one','two'],
  isAdvancingItem:false,crlaNavigationInFlight:false,isFinalizingReading:false,
  crlaLiveSpeech:null,mediaRecorder:null,stoppingSpeechRecognition:false,isRecording:false,
  liveSessionPaused:false,liveSessionEnded:false,liveSessionEndRedirecting:false,
  liveSaveFlushInFlight:false,liveSessionRedirectingToWaitingRoom:false,liveActiveIntervalStartedAt:1,
  itemLocked:[false,false],itemScores:[null,null],itemResultVersion:0,pendingAudioChunk:null,
  nextBtn:{disabled:false},autoAdvanceTimer:null,
  getCurrentPageCount:()=>1,clearSentenceItemTimer(){},isCurrentLiveAssessment:()=>true,
  readStudentEndState:()=>state,
  updateStudentEndState:async patch=>({success:true,student_end_assessment_state:{...state,...patch}}),
  transitionToItem(index){values.currentIndex=index;events.push('advanced');},
  stopSpeechRecognition(){events.push('mic-stopped');},showCompletion:async()=>events.push('completed'),
  setSpeechStatus(...args){messages.push(args);},syncStoryReadingTimerProcessing(){},
  updateAssessmentNavigationButtons(){values.nextBtn.disabled=values.isAdvancingItem||values.crlaNavigationInFlight;},
  updateSpeechProcessingControls(){},traceEndSession(){},traceLiveCrlaRedirect(){},
  pauseLiveElapsedTimer(){},showLiveSessionPaused(){},hasActiveReadingAttempt:()=>false,
  showLiveSessionEnded(transition){values.liveSessionEndRedirecting=true;events.push(transition?.kind||'ended');},
  ...extra,
 };
 const context=vm.createContext(values);
 const helper=source.includes('async function saveCrlaNavigationState(')?section('async function saveCrlaNavigationState(','async function skipCrlaReadingItem('):'';
 vm.runInContext(helper+section('async function skipCrlaReadingItem(','function goToNextPageOrItem(')+section('async function handleLiveSessionState(','let liveSessionPolling = false;'),context);
 return {context,events,messages,state:()=>state};
}
test('unconfirmed student skip stays on the same item and releases navigation',async()=>{
 const {context,events,messages}=environment({updateStudentEndState:async()=>null});
 await context.skipCrlaReadingItem();
 assert.equal(context.currentIndex,0);assert.deepEqual(events,[]);
 assert.equal(context.isAdvancingItem,false);assert.equal(context.nextBtn.disabled,false);
 assert.ok(messages.some(args=>/save/i.test(args.join(' '))));
 assert.deepEqual(copy(context.itemScores),[null,null]);
});
test('a rejected skip save is handled and remains retryable',async()=>{
 const {context}=environment({updateStudentEndState:async()=>{throw Error('connection lost');}});
 await assert.doesNotReject(()=>context.skipCrlaReadingItem());
 assert.equal(context.currentIndex,0);assert.equal(context.isAdvancingItem,false);
 assert.equal(context.nextBtn.disabled,false);
});
test('retry after a failed save moves once, preserving earlier scores',async()=>{
 let calls=0;const {context,events}=environment({updateStudentEndState:async patch=>++calls===1?null:{success:true,student_end_assessment_state:{stage:'words',task1_score:3,...patch}}});
 await context.skipCrlaReadingItem();assert.equal(context.currentIndex,0);
 await context.skipCrlaReadingItem();assert.equal(context.currentIndex,1);
 assert.deepEqual(events,['advanced']);assert.equal(context.liveStudentEndState.task1_score,3);
});
test('duplicate skip clicks wait for the same item save without advancing twice',async()=>{
 let release,calls=0;const {context,events}=environment({updateStudentEndState:patch=>{calls++;return new Promise(resolve=>{release=()=>resolve({success:true,student_end_assessment_state:{stage:'words',...patch}});});}});
 const pending=context.skipCrlaReadingItem();await context.skipCrlaReadingItem();
 assert.equal(calls,1);assert.equal(context.currentIndex,0);release();await pending;
 assert.deepEqual(events,['advanced']);assert.equal(context.isAdvancingItem,false);
});
for(const status of ['skipped','missed'])test(`teacher ${status} stops the reader even while the class is still active`,async()=>{
 const {context,events}=environment();
 await context.handleLiveSessionState({status:'started',student_states:{'1':{status}}});
 assert.equal(context.liveSessionEnded,true);assert.deepEqual(events,['skipped']);
});
test('another student being skipped does not stop this reader',async()=>{
 const {context,events}=environment();
 await context.handleLiveSessionState({status:'started',student_states:{'1':{status:'reading'},'2':{status:'skipped'}}});
 assert.equal(context.liveSessionEnded,false);assert.deepEqual(events,[]);
});
test('teacher skip returned by an in-flight save prevents later cursor advancement',async()=>{
 const {context,events}=environment({updateStudentEndState:async patch=>({success:true,temporary_live_state:true,student_end_assessment_state:{stage:'words',...patch},live_session:{status:'started',student_states:{'1':{status:'skipped'}}}})});
 await context.skipCrlaReadingItem();assert.equal(context.currentIndex,0);
 assert.deepEqual(events,['skipped']);
});
test('teacher skip during a speech flush prevents saving or advancing the old item',async()=>{
 let release,saves=0;const {context,events}=environment({crlaLiveSpeech:{flushing:false},
  currentSpeechContext:()=>({index:0}),sameCrlaStreamItem:()=>true,
  flushCurrentSpeechChunk:()=>new Promise(resolve=>{release=resolve;}),
  updateStudentEndState:async()=>{saves++;return {success:true};}});
 const pending=context.skipCrlaReadingItem();
 await context.handleLiveSessionState({status:'started',student_states:{'1':{status:'skipped'}}});
 release();await pending;assert.equal(saves,0);assert.equal(context.currentIndex,0);
 assert.deepEqual(events,['skipped']);
});
test('comprehension skip does not move to the next question when its save fails',async()=>{
 const {context}=environment({crlaQuestionNarrating:false,crlaQuestionTransitioning:false,crlaSpokenAttemptProcessing:false,
  crlaQuestionPulseReady:true,currentStoryQuestions:[{},{}],currentStoryQuestionIndex:0,
  currentStoryResults:[null,null],currentStoryAnswers:['',''],crlaSpeechAttemptActive:false,crlaSpeechRecognition:null,
  syncCRLAQuestionButtons(){},renderCRLAQuestion(){},persistCRLAComprehensionState:async()=>null,
  finishCRLAComprehension:async()=>{},crlaAnswerFeedback:{classList:{remove(){}}}});
 let click;context.crlaQuestionNextBtn={addEventListener(_,handler){click=handler;}};
 vm.runInContext(section('crlaQuestionNextBtn?.addEventListener("click", async () => {','window.addEventListener("pagehide",'),context);
 await click();assert.equal(context.currentStoryQuestionIndex,0);
 assert.deepEqual(copy(context.currentStoryResults),[null,null]);
 assert.equal(context.crlaQuestionTransitioning,false);
});
test('the actual state write queue keeps a failed Skip out of local recovery storage',async()=>{
 let accepted=false;const writes=[];const initial={stage:'words',task1_score:3};
 const {context}=environment({getStudentEndStateKey:()=> 'synthetic-key',
  localStorage:{setItem(key,value){writes.push(JSON.parse(value));},getItem(){return null;}},
  writeStudentEndState:async value=>accepted?{success:true,student_end_assessment_state:value}:null});
 context.readStudentEndState=()=>context.liveStudentEndState||initial;
 vm.runInContext(section('let studentEndStateWriteQueue = Promise.resolve();','// CRLA Official Assessment: Persist item score'),context);
 await context.skipCrlaReadingItem();assert.equal(context.currentIndex,0);
 assert.equal(context.liveStudentEndState,null);assert.equal(writes.length,0);
 accepted=true;await context.skipCrlaReadingItem();
 assert.equal(context.currentIndex,1);assert.equal(context.liveStudentEndState.crla_question_index,1);
 assert.equal(writes.at(-1).task1_score,3);assert.equal(writes.at(-1).crla_question_index,1);
});
const storyFunctions=()=>section('function normalizeWords(','function lcsLength(')
 +section('function syncItemCorrectWordCount(','function renderPersistedEndState(')
 +section('function calculateFinalizedStoryMetrics(','function punctuationHelperForProgress(')
 +section('function resetStoryMiscueTracking(','function storyNormalizedSingleWord(')
 +section('function recordStoryAlignmentMiscues(','function storyAlignmentHasInsertionMiscue(');
test('a failed story skip and retry retain captured words and count omissions once',async()=>{
 let accepted=false;const pages=['one two three four five','six seven','eight nine'];
 const initial={stage:'story_reading',words_read:3,miscues:2,story_skipped_segments:[]};
 const {context}=environment({isOfficialAssessmentLaunch:true,currentStoryState:'story_reading',currentSelectedStory:{title:'Synthetic story'},
  itemPages:[pages],items:[pages.join(' ')],pageCorrectWordCounts:[[3]],correctWordCounts:[3],paragraphWordResults:{},
  storyMiscueCount:2,storyWordResults:{},storyInsertionMiscues:0,storyHasReadingEvidence:true,
  storyMiscueResponseKeys:new Set(),pendingStorySelfCorrection:null,
  getCurrentPageCount:()=>3,getCurrentDisplayText:()=>pages[context.currentPageIndex],
  readStudentEndState:()=>context.liveStudentEndState||initial,
  updateStudentEndState:async patch=>accepted?{success:true,student_end_assessment_state:{...initial,...patch}}:null,
  resetStorySegmentState(){},updateUI(){},renderStoryReadingState(){},logStorySegmentInitialization(){},animateCurrentItem(){}});
 vm.runInContext(storyFunctions(),context);
 await context.skipCrlaReadingItem();assert.equal(context.currentPageIndex,0);assert.equal(context.isAdvancingItem,false);
 accepted=true;await context.skipCrlaReadingItem();assert.equal(context.currentPageIndex,1);
 assert.equal(context.liveStudentEndState.story_segment_index,1);
 assert.deepEqual(copy(context.liveStudentEndState.story_skipped_segments),[0]);
 assert.equal(context.liveStudentEndState.words_read,3);assert.equal(context.storyMiscueCount,2);
 assert.deepEqual(copy(context.liveStudentEndState.story_word_results[0]),{0:'correct',1:'correct',2:'correct',3:'omission',4:'omission'});
});
test('a failed story skip cannot enter comprehension on the last segment',async()=>{
 const {context,events}=environment({currentStoryState:'story_reading',currentSelectedStory:{title:'Synthetic'},
  updateStudentEndState:async()=>null,finalizeStorySegment(){},strictStoryEvidence:()=>({words_read:0,miscues:5}),
  stopReading:async()=>events.push('comprehension')});
 await context.skipCrlaReadingItem();assert.deepEqual(events,[]);assert.equal(context.isAdvancingItem,false);
 assert.equal(context.currentPageIndex,0);
});
test('Skip drains a fallback clip recording before advancing or discarding its result',async()=>{
 let release,flushed=0;const {context,events}=environment({mediaRecorder:{state:'recording'},
  currentSpeechContext:()=>({index:0}),sameCrlaStreamItem:()=>true,
  flushCurrentSpeechChunk:async()=>{flushed++;},waitForPendingSpeech:()=>new Promise(resolve=>{release=resolve;})});
 const pending=context.skipCrlaReadingItem();
 await new Promise(resolve=>setImmediate(resolve));assert.equal(flushed,1);assert.equal(context.currentIndex,0);
 release(true);await pending;assert.equal(context.currentIndex,1);assert.deepEqual(events,['advanced']);
});
test('an unresolved fallback clip prevents a skip and leaves captured scores intact',async()=>{
 let saves=0;const score={correct_words:2};const {context,messages}=environment({mediaRecorder:{state:'recording'},itemScores:[score,null],
  currentSpeechContext:()=>({index:0}),sameCrlaStreamItem:()=>true,flushCurrentSpeechChunk:async()=>{},waitForPendingSpeech:async()=>false,
  updateStudentEndState:async()=>{saves++;return {success:true};}});
 await context.skipCrlaReadingItem();assert.equal(saves,0);assert.equal(context.currentIndex,0);
 assert.deepEqual(copy(context.itemScores),[score,null]);assert.equal(context.crlaNavigationInFlight,false);
 assert.ok(messages.some(args=>args[0].includes('unresolved')));
});
test('a clip that completes the item while Skip waits is not overwritten with an unanswered result',async()=>{
 const {context,events}=environment({mediaRecorder:{state:'recording'},currentSpeechContext:()=>({index:0}),sameCrlaStreamItem:()=>true,
  flushCurrentSpeechChunk:async()=>{},waitForPendingSpeech:async()=>{
   context.itemLocked[0]=true;context.itemScores[0]={correct_words:1,completed:true};return true;
  }});
 await context.skipCrlaReadingItem();assert.equal(context.currentIndex,0);assert.deepEqual(events,[]);
 assert.deepEqual(copy(context.itemScores[0]),{correct_words:1,completed:true});
});
test('teacher-assisted reader uses the same save acknowledgement before skipping',async()=>{
 let accepted=false;const {context,events}=environment({isAssistMode:true,isCurrentLiveAssessment:()=>false,
  updateStudentEndState:async patch=>accepted?{success:true,student_end_assessment_state:{stage:'words',...patch}}:null});
 await context.skipCrlaReadingItem();assert.equal(context.currentIndex,0);
 accepted=true;await context.skipCrlaReadingItem();assert.equal(context.currentIndex,1);
 assert.deepEqual(events,['advanced']);assert.deepEqual(copy(context.itemScores),[null,null]);
});
test('a teacher skip while the fallback clip drains cannot display a microphone retry error',async()=>{
 let release;const {context,messages}=environment({mediaRecorder:{state:'recording'},currentSpeechContext:()=>({index:0}),sameCrlaStreamItem:()=>true,
  flushCurrentSpeechChunk:async()=>{},waitForPendingSpeech:()=>new Promise(resolve=>{release=resolve;})});
 const pending=context.skipCrlaReadingItem();await new Promise(resolve=>setImmediate(resolve));
 await context.handleLiveSessionState({status:'started',student_states:{'1':{status:'skipped'}}});
 release(false);await pending;assert.deepEqual(messages,[]);assert.equal(context.currentIndex,0);
});
test('comprehension monitor retains the saved next-question cursor before the UI advances',async()=>{
 const published=[];const {context}=environment({currentSelectedStory:{title:'Synthetic',content:'Synthetic story'},
  currentStoryQuestionIndex:0,currentStoryQuestions:[{question:'One'},{question:'Two'}],currentStoryAnswers:['',''],currentStoryResults:[null,null],
  getAssessmentElapsedSeconds:()=>1,publishLiveSessionState:async value=>{published.push(value);return {};},
  updateStudentEndState:async value=>({success:true,student_end_assessment_state:value})});
 vm.runInContext(section('async function persistCRLAComprehensionState(','let crlaQuestionNarrating = false;'),context);
 await context.persistCRLAComprehensionState({crla_question_index:1},{navigation:true});
 assert.equal(published[0].recovery_state?.crla_question_index,1);
 assert.equal(published[0].items_completed,0);
});
test('live comprehension snapshots use the question cursor instead of the story item index',()=>{
 const context=vm.createContext({persistedRecoveryState:{stage:'story_comprehension',crla_question_index:2},
  isPendingBranchTransition:false,currentAssessmentBranch:'story',recoveryStage:'story_comprehension',currentStoryState:'story_comprehension',
  currentStoryQuestionIndex:2,currentIndex:0,itemScores:[],itemLocked:[],correctWordCounts:[],pageCorrectWordCounts:[],
  isStrictStoryReading:()=>false,updateValues:{}});
 vm.runInContext(section('const recoveryState = {','const elapsedSeconds = Number.isFinite')+'globalThis.snapshot=recoveryState;',context);
 assert.equal(context.snapshot.crla_question_index,2);
});
