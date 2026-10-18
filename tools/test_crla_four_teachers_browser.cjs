// Twenty isolated Chrome student contexts in four five-student classes.
// Full actual reader/Django markup; APIs and captured speech are controlled
// fixtures. Pair this with benchmark_crla_four_teachers.py for real live I/O.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawnSync}=require('node:child_process');
const {chromium}=require(process.env.CRLA_PLAYWRIGHT_PATH||'playwright-core');
const root=path.resolve(__dirname,'..'),staticRoot=path.join(root,'pabasa_site/pabasa_app/static/pabasa_app');
const rendered=spawnSync(path.join(root,'.venv/Scripts/python.exe'),['-c',`
import os,sys,json
sys.path.insert(0,'pabasa_site');os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
import django;django.setup()
from django.conf import settings
if os.environ.get('CRLA_TEMPLATE_ROOT'):
 settings.TEMPLATES[0]['DIRS']=[os.environ['CRLA_TEMPLATE_ROOT']]
 settings.TEMPLATES[0]['APP_DIRS']=False
from django.template.loader import render_to_string
from pabasa_app.reading_stt import analyze_reading,align_story_transcript
responses={}
for name,text in [('word','Pito'),('sentence','May pito si Ana.'),('story','May pito si Ana. Narinig ni Ben ang pito.')]:
 d=dict(analyze_reading(text,0,text,'fil-PH',crla_story_reading=name=='story'),success=True)
 if name=='story':
  a=align_story_transcript(text,text,'fil-PH',crla_story_reading=True)
  d.update(word_results=a['word_results'],word_alignment=a)
 responses[name]=d
print(json.dumps({'html':render_to_string('pabasa_app/reading_para_page.html',{'crla_official_assessment_id':1,'crla_official_assessment_data':{'assessment_kind':'crla'}}),'responses':responses}))
`],{cwd:root,encoding:'utf8',env:{...process.env,DB_ENGINE:'sqlite',SQLITE_PATH:':memory:',PYTHONIOENCODING:'utf-8'}});
assert.equal(rendered.status,0,rendered.stderr);
const fixture=JSON.parse(rendered.stdout),html=fixture.html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/g,'').replace(/<link\b[^>]*>/g,'');
const source=fs.readFileSync(process.env.CRLA_READER_SOURCE_PATH||path.join(staticRoot,'js/assessment_reader.js'),'utf8').replace('        loadItems();',`
        window.__fourTeacherTest={handleSpeechResult,
         capture(){isRecording=true;speechRecognitionUsed=true;startTime=Date.now()-2000;},
         state(){return {index:currentIndex,question:currentStoryQuestionIndex,stage:currentStoryState,saved:readStudentEndState()};},
         beginStory(){const original=startSpeechRecognition;startSpeechRecognition=()=>{};
          try{startReading({fromStoryReadingCountdown:true});}finally{startSpeechRecognition=original;}}
        };
        loadItems();`);
const origin='http://localhost:9879';
const official={id:1,assessment_kind:'crla',language:'Filipino',words:Array(10).fill('Pito'),sentences:Array(5).fill('May pito si Ana.'),
 passages:[{title:'Ang Pito',content:'May pito si Ana. Narinig ni Ben ang pito.'}],
 story_qas:[{story_title:'Ang Pito',questions:[{question:'Sino ang may pito?'},{question:'Ano ang narinig ni Ben?'}]}]};
(async()=>{
 const browsers=await Promise.all(Array.from({length:4},()=>chromium.launch({channel:'chrome',headless:true})));
 const contexts=[],groups=Array.from({length:4},()=>({status:'started',states:{},officialWrites:0,posts:0}));
 const clients=[];
 try{
  await Promise.all(Array.from({length:20},async(_,index)=>{
   const groupIndex=Math.floor(index/5),group=groups[groupIndex],id=index+1;
   const context=await browsers[groupIndex].newContext();contexts.push(context);const page=await context.newPage();page.setDefaultTimeout(25000);
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   group.states[id]={status:'reading',recovery_state:{stage:'words',branch:'words',material_id:'1',task1_score:0,crla_question_index:0}};
   await context.addInitScript(({official,id})=>{window.__PABASA_OFFICIAL_ASSESSMENT__=official;window.PABASA_USER_ID=String(id);window.PABASA_USER_ROLE='student';},{official,id});
   const session=()=>({success:true,session:{id:'class-'+groupIndex,status:group.status,student_ids:Object.keys(group.states).map(Number),student_states:group.states}});
   await context.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url());if(url.origin!==origin)return route.abort();
    if(url.pathname.startsWith('/dashboard/assessment/reading_ui/'))return route.fulfill({contentType:'text/html',body:html});
    if(url.pathname.endsWith('/waiting/'))return route.fulfill({contentType:'text/html',body:'Synthetic live waiting room'});
    if(url.pathname.startsWith('/static/pabasa_app/')){
     let file=path.resolve(staticRoot,url.pathname.slice('/static/pabasa_app/'.length));
     if(!fs.existsSync(file))file=file.replace(/\.(png|jpe?g)$/i,'.webp');
     if(file.startsWith(staticRoot+path.sep)&&fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({body:fs.readFileSync(file)});
    }
    if(url.pathname==='/api/assessment/end-state/'||url.pathname==='/api/assessment/complete/'){
     group.officialWrites++;return route.fulfill({status:500,json:{success:false,error:'Unexpected official completion'}});
    }
    if(url.pathname.endsWith('/student-update/')){
     assert.equal(url.pathname,`/api/live-assessment/session/class-${groupIndex}/student-update/`,'Student may only publish to own class');
     const patch=request.postDataJSON();group.posts++;
     const current=group.states[id];if(current.status!=='completed')group.states[id]={...current,...patch,recovery_state:{...current.recovery_state,...patch.recovery_state}};
     return route.fulfill({json:session()});
    }
    if(url.pathname===`/api/live-assessment/session/class-${groupIndex}/`)return route.fulfill({json:session()});
    return route.fulfill({json:{success:true}});
   });
   page.on('domcontentloaded',async()=>{
    if(!new URL(page.url()).pathname.startsWith('/dashboard/assessment/reading_ui/'))return;
    try{
     await page.evaluate(state=>{window.__PABASA_STUDENT_END_STATE__=state;},group.states[id].recovery_state);
     await page.addScriptTag({content:source});
    }catch(e){errors.push(e.message);}
   });
   await page.goto(`${origin}/dashboard/assessment/reading_ui/word/?official_assessment_id=1&crla_stage=words&live=1&live_session_id=class-${groupIndex}&live_recovery=1&countdown=0`);
   await page.waitForFunction(()=>window.__fourTeacherTest&&document.getElementById('readingWord').textContent.includes('Pito'));
   clients.push({page,id,group,errors});
  }));
  console.log('PASS: 20 isolated students loaded, five per class');
  await Promise.all(clients.map(async({page,id,group})=>{
   for(const branch of ['words','sentences']){
    const count=branch==='words'?10:5;
    for(let item=0;item<count;item++){
     await page.evaluate(data=>{window.__fourTeacherTest.capture();window.__fourTeacherTest.handleSpeechResult(data);},fixture.responses[branch==='words'?'word':'sentence']);
     if(item<count-1)await page.waitForFunction(next=>window.__fourTeacherTest.state().index===next,item+1);
    }
    await page.waitForFunction(()=>document.querySelector('.reader-shell').classList.contains('is-section-complete'));
    await page.reload();
    await page.waitForFunction(()=>window.__fourTeacherTest&&document.querySelector('.reader-shell').classList.contains('is-section-complete'));
    await page.locator('#finishBtn').click();
    await page.waitForURL(url=>url.searchParams.get('crla_stage')===(branch==='words'?'sentences':'story_selection'));
    await page.waitForFunction(()=>window.__fourTeacherTest&&!document.querySelector('.reader-shell').classList.contains('is-section-complete'));
   }
   await page.waitForFunction(()=>!document.getElementById('storySelectionPanel').classList.contains('d-none'));
   await page.locator('.story-selection-cta').first().click();
   await page.waitForFunction(()=>document.querySelector('.reader-shell').classList.contains('is-story-ready-state'));
   await page.evaluate(()=>window.__fourTeacherTest.beginStory());
   await page.evaluate(data=>{window.__fourTeacherTest.capture();window.__fourTeacherTest.handleSpeechResult(data);},fixture.responses.story);
   await page.waitForFunction(()=>!document.getElementById('crlaQuestionPanel').classList.contains('d-none'));
   for(let question=0;question<2;question++){
    await page.locator('#crlaQuestionNextBtn').click();
    if(question===0)await page.waitForFunction(()=>window.__fourTeacherTest.state().question===1);
   }
   await page.waitForFunction(()=>!document.getElementById('learnerExperiencePage').classList.contains('d-none'));
   await page.locator('.rating-option[data-rating="4"]').click();await page.locator('#learnerExperienceContinue').click();
   await page.waitForURL(url=>url.pathname.endsWith('/waiting/'));
   assert.equal(group.states[id].status,'completed');assert.equal(group.states[id].recovery_state.temporary_completed,true);
   assert.equal(group.states[id].recovery_state.task1_score,10);assert.equal(group.states[id].recovery_state.task2_sentences_score,10);
   assert.deepEqual(group.states[id].recovery_state.crla_results,[null,null]);
  }));
  assert.deepEqual(groups.map(g=>Object.values(g.states).filter(s=>s.status==='completed').length),[5,5,5,5]);
  assert.equal(groups.reduce((sum,g)=>sum+g.officialWrites,0),0);
  assert.deepEqual(clients.flatMap(c=>c.errors),[]);
  console.log('PASS: all 20 finished 10 words, 5 sentences, story, 2 unanswered comprehension questions, rating and waiting-room navigation; reload preserved both section completions');
  console.log('PASS: each class retained its own five completed students; no premature official result writes or browser exceptions');
 }finally{await Promise.all(contexts.map(c=>c.close()));await Promise.all(browsers.map(b=>b.close()));}
})().catch(e=>{console.error(e);process.exitCode=1;});
