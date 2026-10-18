// Actual Django markup and complete reader in Chrome; isolated synthetic APIs.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const {chromium}=require(process.env.CRLA_PLAYWRIGHT_PATH||'playwright-core');
const root=path.resolve(__dirname,'..');
const rendered=spawnSync(path.join(root,'.venv/Scripts/python.exe'),['-c',`
import os,sys,json
sys.path.insert(0,'pabasa_site');os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
import django;django.setup()
from django.template.loader import render_to_string
print(json.dumps(render_to_string('pabasa_app/reading_para_page.html',{'crla_official_assessment_id':1,'crla_official_assessment_data':{'assessment_kind':'crla'}})))
`],{cwd:root,encoding:'utf8',env:{...process.env,DB_ENGINE:'sqlite',SQLITE_PATH:':memory:',PYTHONIOENCODING:'utf-8'}});
assert.equal(rendered.status,0,rendered.stderr);
const html=JSON.parse(rendered.stdout).replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'').replace(/<link\b[^>]*>/g,'');
let source=fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static/pabasa_app/js/assessment_reader.js'),'utf8');
source=source.replace('        loadItems();',`        window.__skipTest={
 get(){return {index:currentIndex,page:currentPageIndex,question:currentStoryQuestionIndex,scores:itemScores,locked:itemLocked,
  busy:crlaNavigationInFlight,ended:liveSessionEnded,state:readStudentEndState(),micStops:window.__micStops||0};},
 poll:async()=>handleLiveSessionState(await fetchLiveSessionState()),
 capture(){isRecording=true;recognitionActive=true;mediaStream={getTracks:()=>[{stop(){window.__micStops=(window.__micStops||0)+1;}}]};},
 clip(){crlaStreamingUnavailable=true;isRecording=true;window.__clipFlushed=false;
  mediaRecorder={state:'recording',requestData(){},stop(){this.state='inactive';mediaRecorder=null;isSendingChunk=true;
   window.setTimeout(()=>{isSendingChunk=false;window.__clipFlushed=true;},200);}};},
 stopPolling(){stopLiveSessionPolling();stopLiveSessionHeartbeat();}
};
        loadItems();`);
const origin='http://localhost:9878',staticRoot=path.join(root,'pabasa_site/pabasa_app/static/pabasa_app');
const official={id:1,assessment_kind:'crla',language:'Filipino',words:Array(10).fill('Pito'),
 sentences:Array(5).fill('May pito si Ana.'),rhyme_pairs:Array(10).fill({word_a:'pito',word_b:'dito'}),
 passages:[{title:'Ang Pito',content:'May pito si Ana.\n\nNarinig ni Ben ang pito.'}],
 story_qas:[{story_title:'Ang Pito',questions:[{question:'Sino ang may pito?'},{question:'Ano ang narinig ni Ben?'}]}]};
(async()=>{
 const browsers=await Promise.all(Array.from({length:3},()=>chromium.launch({channel:'chrome',headless:true})));
 const contexts=[];
 try{
  const clients=await Promise.all(Array.from({length:30},async(_,index)=>{
   const context=await browsers[Math.floor(index/10)].newContext();contexts.push(context);
   const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   const state={cursor:0,reject:true,status:'reading',posts:0,officialWrites:0,checkClip:false,earlyClipWrites:0};
   await context.addInitScript(({official,id})=>{
    window.__PABASA_OFFICIAL_ASSESSMENT__=official;window.PABASA_USER_ID=String(id);window.PABASA_USER_ROLE='student';
    window.__PABASA_STUDENT_END_STATE__={stage:'words',branch:'words',material_id:'1',task1_score:0,crla_question_index:0};
   },{official,id:index+1});
   const response=()=>({success:true,session:{id:'synthetic',status:'started',student_ids:[index+1],student_states:{[index+1]:{
    status:state.status,recovery_state:{stage:'words',crla_question_index:state.cursor}}}}});
   await context.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url());if(url.origin!==origin)return route.abort();
    if(url.pathname.startsWith('/dashboard/assessment/reading_ui/'))return route.fulfill({contentType:'text/html',body:html});
    if(url.pathname==='/dashboard/assessment/')return route.fulfill({contentType:'text/html',body:'Synthetic assessment dashboard'});
    if(url.pathname.startsWith('/static/pabasa_app/')){
     let file=path.resolve(staticRoot,url.pathname.slice('/static/pabasa_app/'.length));
     if(!fs.existsSync(file))file=file.replace(/\.(png|jpe?g)$/i,'.webp');
     if(file.startsWith(staticRoot+path.sep)&&fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({body:fs.readFileSync(file)});
    }
    if(url.pathname==='/api/assessment/end-state/')state.officialWrites++;
    if(url.pathname.endsWith('/student-update/')){
     state.posts++;const payload=request.postDataJSON();const cursor=payload.recovery_state?.crla_question_index;
     if(state.checkClip&&!await page.evaluate(()=>window.__clipFlushed))state.earlyClipWrites++;
     if(state.reject&&cursor>state.cursor)return route.fulfill({status:503,json:{success:false}});
     if(state.status==='reading'&&Number.isInteger(cursor))state.cursor=cursor;
     return route.fulfill({json:response()});
    }
    if(url.pathname==='/api/live-assessment/session/synthetic/')return route.fulfill({json:response()});
    return route.fulfill({json:{}});
   });
   await page.goto(origin+'/dashboard/assessment/reading_ui/word/?official_assessment_id=1&crla_stage=words&live=1&live_session_id=synthetic&live_recovery=1&countdown=0');
   await page.addScriptTag({content:source});
   await page.waitForFunction(()=>window.__skipTest&&document.getElementById('readingWord').textContent.includes('Pito'));
   await page.evaluate(()=>window.__skipTest.stopPolling());
   return {context,page,state,errors};
  }));
  await Promise.all(clients.map(async({page,state})=>{
   const before=state.posts;await page.locator('#nextBtn').click();
   await page.waitForFunction(()=>!window.__skipTest.get().busy);
   assert.ok(state.posts>before);assert.equal(state.cursor,0);
   assert.equal((await page.evaluate(()=>window.__skipTest.get())).index,0);
   assert.equal(await page.locator('#nextBtn').isEnabled(),true);
   state.reject=false;await page.locator('#nextBtn').click();
   await page.waitForFunction(()=>window.__skipTest.get().index===1&&!window.__skipTest.get().busy);
   assert.equal(state.cursor,1);assert.equal(state.officialWrites,0);
   const value=await page.evaluate(()=>window.__skipTest.get());
   assert.ok(value.scores.every(score=>score===null));assert.ok(value.locked.every(locked=>!locked));
  }));
  console.log('PASS: 30 complete Chrome readers retain the item on HTTP 503 and advance once after an explicit retry, without scoring a skip');
  await Promise.all(clients.map(async({page,state})=>{
   await page.evaluate(()=>window.__skipTest.clip());state.checkClip=true;
   await page.locator('#nextBtn').click();
   await page.waitForFunction(()=>window.__skipTest.get().index===2&&!window.__skipTest.get().busy);
   assert.equal(state.earlyClipWrites,0);assert.equal(state.cursor,2);state.checkClip=false;
  }));
  console.log('PASS: all 30 Chrome readers drain their fallback clip before publishing the next item');
  await Promise.all(clients.map(async({page,state,errors})=>{
   await page.evaluate(()=>window.__skipTest.capture());state.status='skipped';
   await page.evaluate(()=>window.__skipTest.poll());
   assert.equal((await page.evaluate(()=>window.__skipTest.get())).ended,true);
   assert.equal((await page.evaluate(()=>window.__skipTest.get())).micStops,1);
   assert.match(await page.locator('#liveSessionEndedTitle').textContent(),/follow up/);
   await page.waitForURL(origin+'/dashboard/assessment/',{timeout:12000});
   assert.equal(state.officialWrites,0);assert.deepEqual(errors,[]);
  }));
  console.log('PASS: teacher skip stops capture and returns all 30 Chrome readers to the assessment dashboard without a fake completion');
 }finally{await Promise.all(contexts.map(c=>c.close()));await Promise.all(browsers.map(b=>b.close()));}
})().catch(error=>{console.error(error);process.exitCode=1;});
