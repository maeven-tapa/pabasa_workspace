// Actual practice reader + save queue in Chrome; all API faults are local fixtures.
const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');const {spawnSync}=require('node:child_process');
const {chromium}=require(process.env.CRLA_PLAYWRIGHT_PATH||'playwright-core');
const root=path.resolve(__dirname,'..');const staticRoot=path.join(root,'pabasa_site/pabasa_app/static/pabasa_app');
const render=spawnSync(path.join(root,'.venv/Scripts/python.exe'),['-c',`
import os,sys,json
from types import SimpleNamespace
sys.path.insert(0,'pabasa_site');os.environ['DJANGO_SETTINGS_MODULE']='pabasa_site.settings'
import django;django.setup()
from django.template.loader import render_to_string
from django.http import QueryDict
out={}
for mode in ('free','color','hunt'):
 request=SimpleNamespace(GET=QueryDict('game='+mode+'&difficulty=easy&level=level_1'),session={'user_id':'__STUDENT__','user_role':'student'},path='/dashboard/practice/word/')
 material={'id':'practice-42','raw_id':42,'title':'Synthetic Practice','game_mode':mode,'difficulty':'easy','level':'level_1','type':'word','language':'English','items':['cat','dog','sun','moon','star'],'content':'cat\\ndog\\nsun\\nmoon\\nstar','status':'published'}
 out[mode]=render_to_string('pabasa_app/practice_word_page.html',{'request':request,'practice_materials':[material],'selected_practice_language':'English','csrf_token':'fixture'})
print(json.dumps(out))
`],{cwd:root,encoding:'utf8',env:{...process.env,DB_ENGINE:'sqlite',SQLITE_PATH:':memory:',PYTHONIOENCODING:'utf-8'}});
assert.equal(render.status,0,render.stderr);const templates=JSON.parse(render.stdout);
const queueSource=fs.readFileSync(path.join(staticRoot,'js/practice_completion_queue.js'),'utf8');
const readerSource=fs.readFileSync(path.join(staticRoot,'js/practice_reader.js'),'utf8').replace('    updatePracticeLanguageLabels();\n    loadItems();',`
    window.__practiceTest={
      state:()=>({index:currentIndex,correct:correctResponses,total:items.length,pending:practiceCompletionQueue?.pending(),listening:huntListeningDesired}),
      speech:()=>{huntListeningDesired=true;return submitPracticeSpeech(new Blob(['fixture'],{type:'audio/webm'}),currentSpeechTarget(),recordBtn);},
      deniedMic:()=>{huntListeningDesired=true;return startPracticeSpeechRecording(recordBtn);},
      finish:()=>{correctResponses=items.length;itemOutcomes=items.map(()=>'read');
        if(isHuntMode)items.forEach((word,index)=>finalizeHuntSpeechResult(index,word,word,.95));
        return showCompletion();}
    };
    updatePracticeLanguageLabels();
    loadItems();`);
assert.ok(readerSource.includes('window.__practiceTest='));
const origin='http://localhost:9882';
(async()=>{
 const browsers=await Promise.all(Array.from({length:3},()=>chromium.launch({channel:'chrome',headless:true})));
 const contexts=[];const clients=[];
 try {
  await Promise.all(Array.from({length:30},async(_,i)=>{
   const mode=['free','color','hunt'][Math.floor(i/10)];const context=await browsers[Math.floor(i/10)].newContext();contexts.push(context);
   await context.addInitScript(id=>{window.PABASA_USER_ID=String(id);window.PABASA_USER_ROLE='student';},i+1);
   await context.addInitScript(()=>{navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Synthetic permission denied','NotAllowedError');};});
   const transport={offline:false,speechFail:true};const deposits=new Map();let completions=0;let available=0;const errors=[];
   const html=templates[mode].replaceAll('__STUDENT__',String(i+1)).replace(/<script\b([^>]*)>[\s\S]*?<\/script>/g,(tag,attributes)=>attributes.includes('application/json')?tag:'').replace(/<link\b[^>]*>/g,'');
   const url=origin+'/dashboard/practice/word/?id=42&game='+mode+'&difficulty=easy&level=level_1';
   await context.route('**/*',async route=>{
    const req=route.request(),u=new URL(req.url());if(u.origin!==origin)return route.abort();
    if(u.pathname.startsWith('/dashboard/practice/word/'))return route.fulfill({contentType:'text/html',body:html});
    if(transport.offline&&(u.pathname.startsWith('/api/')||u.pathname==='/record-assessment-completion/'))return route.abort('internetdisconnected');
    if(u.pathname==='/api/reading/transcribe/')return route.fulfill({status:503,json:{success:false,error:'Synthetic provider unavailable'}});
    if(u.pathname==='/api/practice/hunt/award-stars/'){
     const payload=req.postDataJSON(),key=payload.attempt_id+':'+payload.award_type+':'+payload.word_index;
     const stars=payload.award_type==='word'?2:3;const duplicate=deposits.has(key);if(!duplicate){deposits.set(key,stars);available+=stars;}
     return route.fulfill({json:{success:true,award_type:payload.award_type,earned_stars:stars,star_delta:duplicate?0:stars,duplicate,available_stars:available,total_stars_earned:available,attempt_stars:available}});
    }
    if(u.pathname==='/record-assessment-completion/'){completions++;return route.fulfill({json:{success:true,material_id:'practice-42',status:'Done'}});}
    return route.fulfill({json:{success:true}});
   });
   async function page(){const p=await context.newPage();p.setDefaultTimeout(60000);p.on('pageerror',e=>errors.push(e.message));
    p.on('domcontentloaded',async()=>{try{await p.addScriptTag({content:queueSource});await p.addScriptTag({content:readerSource});}catch(e){errors.push(e.message);}});
    await p.goto(url);await p.waitForFunction(()=>window.__practiceTest?.state().total===5);return p;}
   const p=await page();clients.push({p,page,transport,mode,errors,deposits,get completions(){return completions;},get available(){return available;}});
  }));
  await Promise.all(clients.map(async c=>{
   const before=await c.p.evaluate(()=>__practiceTest.state());await c.p.evaluate(()=>__practiceTest.speech());
   const after=await c.p.evaluate(()=>__practiceTest.state());assert.equal(after.index,before.index);assert.equal(after.correct,before.correct);
   assert.equal(after.listening,false);
   await c.p.evaluate(()=>__practiceTest.deniedMic());assert.equal((await c.p.evaluate(()=>__practiceTest.state())).listening,false);
   c.transport.offline=true;assert.equal(await c.p.evaluate(()=>__practiceTest.finish()),false);
   assert.equal((await c.p.evaluate(()=>__practiceTest.state())).pending,1);
   assert.equal(await c.p.getByRole('button',{name:'Retry Save'}).isVisible(),true);
  }));
  console.log('PASS: 30 provider errors and 30 microphone denials stop automatic retries without advancing; 30 offline completions remain pending with Retry Save');
  await Promise.all(clients.map(async(c,i)=>{
   await c.p.close();c.transport.offline=false;c.p=await c.page();
   await c.p.waitForFunction(()=>__practiceTest.state().pending===0);
   if(c.mode==='hunt'){assert.equal(c.available,13);assert.equal(c.deposits.size,6);}
   assert.equal(c.completions,1);assert.deepEqual(c.errors,[]);
  }));
  console.log('PASS: all 30 closed pages recover pending results; each Hunt wallet has exactly 13 stars without duplicate deposits');
 }finally{await Promise.all(contexts.map(c=>c.close()));await Promise.all(browsers.map(b=>b.close()));}
})().catch(e=>{console.error(e);process.exitCode=1;});
