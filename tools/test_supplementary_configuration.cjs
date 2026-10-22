// Run with Node 24 and jsdom 26 (set NODE_PATH to a local test dependency folder).
// Exercises the actual teacher template functions; all accounts/stories/POSTs are synthetic.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {test} = require('node:test');
const root = path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/templates/pabasa_app/courses.html'), 'utf8');
const python = process.env.PABASA_TEST_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const catalogs = spawnSync(python, ['-c', `
import os,sys,json
sys.path.insert(0,'pabasa_site');os.environ['DJANGO_SETTINGS_MODULE']='pabasa_site.settings'
import django;django.setup()
from pabasa_app.views import _picture_word_catalog
from pabasa_app.sound_detective import catalog
from pabasa_app.syllable_blending import activity_catalog
from pabasa_app.clap_count_word_bank import word_bank_catalog
print(json.dumps({'picture-word-catalog':_picture_word_catalog(),'sound-detective-catalog':catalog(),'syllable-blending-catalog':activity_catalog(),'clap-count-word-bank':word_bank_catalog()}))
`], {cwd: root, encoding: 'utf8', env: {...process.env, DB_ENGINE: 'sqlite', SQLITE_PATH: ':memory:', PYTHONIOENCODING: 'utf-8'}});
assert.equal(catalogs.status, 0, catalogs.stderr);
const catalogData = JSON.parse(catalogs.stdout);
const sourceFunctions = [...template.matchAll(/^        (?:async )?function (\w+)\([^]*?^        }/gm)];
const functions = sourceFunctions.filter(m => (m.index >= template.indexOf('        function setNodeVisibility(')
    && m.index <= template.indexOf('        function saveTemplateActivity(')) || m[1] === 'syncMaterialLanguageSelection').map(m => m[0]).join('\n');
const constants = template.slice(template.indexOf('        const TEMPLATE_DEFINITIONS ='), template.indexOf('        let activeTemplateActivity ='));
const bindings = template.slice(template.indexOf('        const addMaterialModal ='), template.indexOf('        const TEMPLATE_DEFINITIONS ='))
    .match(/^        const [^\n]+;/gm).join('\n');
const languageEvents = template.slice(template.indexOf("            Array.from(document.querySelectorAll('input[name=\"templateLanguage\"]')).forEach(input => {\n                input.addEventListener('change'"), template.indexOf("            templateActivityForm?.addEventListener('submit'"));
assert.ok(languageEvents.includes("input.addEventListener('change'"));
const stories = [1, 2].map(id => ({id, title: `Fixture story ${id}`, language: 'Filipino', text: `Fixture passage ${id}.`, story_text: `Fixture passage ${id}.`, text_preview: `Fixture passage ${id}.`}));
const script = `
let editingCard=null,currentItemsList=[],currentItemsAreParagraph=false;
let materialSelectedStudentIds=new Set(),materialEligibleStudents=[];
let selectedTemplateLanguage='',activeTemplateActivity=null,activeTemplateItemEditIndex=null;
let templateActivityInitialSnapshot=null,personalMaterialInitialSnapshot=null,personalWorkspaceActive=false,createdTemplateActivities=[];
const currentSectionId=1,classReadings={1:{story_reading:${JSON.stringify(stories)}}};
const escapeHtml=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
${bindings}
${constants}
${functions}
// Modal, roster, and network shells only. Configuration/render/validation/save logic above is unmodified.
function setAddMaterialMode(){}
function renderMaterialStudents(){}
function ensureCsrfToken(){return Promise.resolve('synthetic-csrf');}
function materialPublicationSettings(){return {publication_scope:'whole_class'};}
function resolveMaterialClassContext(){return {classId:1,targetId:null};}
function getTeacherSectionId(){return 1;}
function getCurrentOpenCourseLanguageValue(){return 'English';}
function getCurrentClassLanguageValue(){return 'English';}
window.SoundDetective={mount:node=>{node.textContent='Selected sound activity preview';}};
window.posts=[];window.fixtureErrors=[];
window.fetch=async(url,options={})=>{
 if(options.method==='POST'){
  const body=JSON.parse(options.body);window.posts.push({url,body});
  return {ok:true,status:200,json:async()=>({success:true,material:{...body,id:body.material_id||1001,raw_id:body.material_id||1001,content_json:JSON.parse(body.content)}})};
 }
 if(window.deferStories)await new Promise(resolve=>(window.pendingStories||=[]).push(resolve));
 return {ok:true,json:async()=>({success:true,stories:${JSON.stringify(stories)}})};
};
window.bootstrap={Modal:{getOrCreateInstance:()=>({hide(){}})}};
${languageEvents}
templateActivityTitle.addEventListener('input',()=>{renderTemplatePreview();updateFirst15CreateStepLock();});
templateActivityTitleSelect.addEventListener('change',updateFirst15CreateStepLock);
templateWeeksGrid.addEventListener('change',()=>{renderTemplatePreview();updateFirst15CreateStepLock();});
templateDynamicFields.addEventListener('input',renderTemplatePreview);
templateSaveBtn.addEventListener('click',saveTemplateActivity);
window.fixture={
 titles:TEMPLATE_META.map(row=>row[1]),
 open:async title=>{if(title==='Reading Practice'){activeTemplateActivity=null;beginPersonalMaterialWorkspace();}else await showTemplateBuilder(title);},
 state:()=>activeTemplateActivity,dynamic:()=>renderTemplateDynamicFields(activeTemplateActivity.templateTitle),
 values:getTemplateFormValues,validate:validateTemplateActivityForm,update:updateFirst15CreateStepLock,preview:renderTemplatePreview,
 restore:material=>{activeTemplateActivity=restoreTemplateActivityState(material);window.__templateEditStateRestored=true;applyTemplateLanguageSelection(activeTemplateActivity.language,activeTemplateActivity.templateTitle);templateActivityTitle.value=activeTemplateActivity.title;renderTemplateDynamicFields(activeTemplateActivity.templateTitle,activeTemplateActivity.content);renderTemplateWeeks(activeTemplateActivity.weeks);renderTemplatePreview();},
 items:items=>{currentItemsList=items;updateReadingPracticeProgression();},
 readingProgress:updateReadingPracticeProgression,
 syncLanguage:syncMaterialLanguageSelection
};
document.querySelectorAll('[data-fixture-template]').forEach(button=>button.onclick=()=>window.fixture.open(button.dataset.fixtureTemplate).catch(error=>{window.fixtureErrors.push(error.message);}));
`;
function djangoTags(s) {
    return s.replace(/{% static ['"]([^'"]+)['"] %}/g, '/static/$1').replace(/{% url ['"]([^'"]+)['"] %}/g, '/fixture/$1');
}
function html({styles = false} = {}) {
    const form = template.match(/<form id="templateActivityForm"[^]*?<\/form>/)[0];
    const personal = template.slice(template.indexOf('                    <div id="personalWorkspaceBack"'), template.indexOf('                </form>', template.indexOf('                    <div id="personalWorkspaceBack"')));
    const titleNames = [...template.matchAll(/\['\d{2}', (?:'([^']+)'|"([^"]+)"),/g)].map(m => m[1] || m[2]);
    return djangoTags(`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">${styles ? [...template.matchAll(/<style[^>]*>[^]*?<\/style>/g)].map(m=>m[0]).join('') : ''}</head><body><h1>Supplementary configuration verification</h1><nav>${titleNames.map(title=>`<button data-fixture-template="${title.replaceAll('"','&quot;')}">${title}</button>`).join('')}</nav><div id="addMaterialModal"><div id="templateLandingPanel"></div><div id="templateActivityGrid"></div><div id="templateBuilderPanel"><h2 id="templateBuilderTitle"></h2><p id="templateBuilderSubtitle"></p><div id="templateBuilderLessonPill"></div>${form}</div>${personal}<div class="modal-footer"></div></div>${Object.entries(catalogData).map(([id,data])=>`<script type="application/json" id="${id}">${JSON.stringify(data).replaceAll('<','\\u003c')}</script>`).join('')}<script>${fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static/pabasa_app/js/letter_sound_matching_display.js'),'utf8')}\n${script}</script></body></html>`);
}
const settle = () => new Promise(resolve => setTimeout(resolve, 0));
function create() {
    const {JSDOM, VirtualConsole} = require('jsdom');
    const errors = [];
    const vc = new VirtualConsole();vc.on('jsdomError', e => errors.push(e.message));
    const dom = new JSDOM(html(), {url:'http://localhost/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(window){window.HTMLElement.prototype.scrollIntoView=function(){};}});
    assert.ok(dom.window.fixture, errors.join('\n'));
    return {dom,w:dom.window,d:dom.window.document,errors};
}
function change(f, selector, value) {
    const element=f.d.querySelector(selector);assert.ok(element,selector);
    if(element.type==='radio'||element.type==='checkbox')element.checked=value;
    else element.value=value;
    element.dispatchEvent(new f.w.Event('change',{bubbles:true}));
}
function title(f) {
    const element=f.d.getElementById('templateActivityTitle');element.value='Fixture activity';
    element.dispatchEvent(new f.w.Event('input',{bubbles:true}));
}
const schedule = f => f.d.querySelector('[aria-labelledby="templateScheduleHeading"]').inert;
const selectors = {
    'Letter & Sound Matching':'#letterSoundReadingSet','Sound Detective':'#soundDetectiveSet',
    'Match the Letter to Its Sound':'#letterSoundCorrespondenceReadingSet','Clap & Count Syllables':'#clapWordSet',
    'Decode the Word':'#wordDecodingReadingSet','Word Meaning Match':'#aralReadingSet','Fluency Reading':'#aralReadingSet',
    'Story Response':'#storyResponseStory','Retell the Story':'#templateActivityTitleSelect',"5W's Story Questions":'#fiveWStory'
};
async function prepare(f,name,language='Filipino') {
    await f.w.fixture.open(name);await settle();
    if(name==='Reading Practice')return;
    if(name!=='Retell the Story'&&name!=="5W's Story Questions")title(f);
    if(name!=='Retell the Story'&&name!=="5W's Story Questions")change(f,`input[name="templateLanguage"][value="${language}"]`,true);
    await settle();
}
async function selectContent(f,name,index=0,language='Filipino') {
    if(selectors[name]){
        const select=f.d.querySelector(selectors[name]);const options=[...select.options].filter(o=>o.value);
        assert.ok(options.length,`${name}: no choices`);change(f,selectors[name],options[index % options.length].value);
    }else{
        const buttons=f.d.querySelectorAll({'Syllable Blending':'.syllable-select-btn','Picture-Word Matching':'[data-picture-word-set-select]','Phrase Reading Practice':'[data-phrase-set-select]','Sentence Reading Practice':'[data-sentence-set-select]','Story Reading':'[data-story-select]'}[name]);
        if(name==='Syllable Blending'){change(f,'#syllableActivityFormat','syllable_combination');f.d.querySelectorAll('.syllable-select-btn')[index].click();}
        else buttons[index % buttons.length].click();
    }
    await settle();
    if(name==='Clap & Count Syllables')change(f,'#clapSelectAll',true);
    if(name==='Story Response')f.d.querySelector('[data-story-response-prompt]').click();
    if(name==="5W's Story Questions"){
        change(f,`input[name="templateLanguage"][value="${language}"]`,true);
        for(let i=0;i<5;i++){
            const q=f.d.querySelector(`.five-w-question[data-five-w-index="${i}"]`);q.value=`Question ${i+1}?`;q.dispatchEvent(new f.w.Event('input',{bubbles:true}));
            f.d.querySelector(`.five-w-answer[data-five-w-index="${i}"]`).value='Fixture answer';
            f.d.querySelector(`.five-w-answer-add[data-five-w-index="${i}"]`).click();
        }
    }
    await settle();
}

if(process.argv.includes('--serve')) {
    const http=require('node:http');
    http.createServer((req,res)=>{
        const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
        if(pathname.startsWith('/static/')){
            const base=path.join(root,'pabasa_site/pabasa_app/static');const file=path.resolve(base,pathname.slice(8));
            if(file.startsWith(base+path.sep)&&fs.existsSync(file)){res.end(fs.readFileSync(file));return;}
            res.writeHead(404);res.end();return;
        }
        res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html({styles:true}));
    }).listen(8767,'127.0.0.1',()=>console.log('Synthetic configuration UI: http://127.0.0.1:8767'));
} else {
    test('all 16 cards: initial state, first selection, validation, save payload and edit restoration',async t=>{
        const names=create();const titles=[...names.w.fixture.titles];names.dom.window.close();assert.equal(titles.length,16);
        for(const name of titles)for(const language of (name==='Reading Practice'||name==='Retell the Story'?['Filipino']:['Filipino','English']))await t.test(`${name} (${language})`,async()=>{
            const f=create();try{
                await prepare(f,name,language);
                if(name==='Reading Practice'){
                    assert.equal(f.d.querySelector('#materialLanguage').value,'');assert.equal(f.d.querySelector('#assignedWeek').value,'');
                    f.w.fixture.syncLanguage();assert.equal(f.d.querySelector('#materialLanguage').value,'');
                    f.d.querySelector('#materialTitle').value='Fixture reading';f.w.fixture.items(['Fixture item']);
                    change(f,'#materialLanguage','Filipino');f.w.fixture.readingProgress();
                    assert.equal(f.d.querySelector('#assignedWeek').disabled,false);
                    f.d.querySelector('#materialTitle').value='';f.w.fixture.readingProgress();assert.equal(f.d.querySelector('#materialLanguage').disabled,true);
                    return;
                }
                assert.equal(schedule(f),true,'schedule must start locked');
                if(selectors[name])assert.equal(f.d.querySelector(selectors[name]).value,'','placeholder must be selected');
                assert.equal(f.d.querySelectorAll('[aria-pressed="true"]').length,0,'no set cards preselected');
                assert.match(f.d.querySelector('#templatePreviewPanel').textContent,/Select activity content/);
                f.d.querySelector('#templateSaveBtn').click();await settle();assert.equal(f.w.posts.length,0,'placeholder must fail save validation');
                await selectContent(f,name,0,language);
                assert.equal(schedule(f),false,'first real option must unlock the schedule');
                await selectContent(f,name,1,language);
                assert.equal(schedule(f),false,'another option must also work');
                change(f,'#templateWeeksGrid input',true);
                assert.equal(f.d.querySelector('#materialPublicationSettings').inert,false);
                const values=JSON.parse(JSON.stringify(f.w.fixture.values()));
                assert.equal(f.w.fixture.validate(values),'','save validation must agree with progression');
                f.d.querySelector('#templateSaveBtn').click();await settle();await settle();
                assert.equal(f.w.posts.length,1,`save blocked: ${f.d.querySelector('#templateValidationError').textContent}`);
                const saved=f.w.posts[0].body;assert.equal(f.w.posts[0].url,'/dashboard/teacher/add-material/');
                f.w.fixture.restore({id:1001,raw_id:1001,source_type:'template',title:saved.title,language:saved.language,assigned_weeks:saved.assigned_weeks,content_json:JSON.parse(saved.content)});await settle();
                assert.equal(schedule(f),false,'saved valid activity must stay unlocked');
                const restored=f.w.fixture.values();assert.equal(f.w.fixture.validate(restored),'');
                assert.equal(restored.content.reading_set_id,values.content.reading_set_id);
                assert.equal(restored.content.source_story_reading_material_id,values.content.source_story_reading_material_id);
                for(const key of ['activity_format','activity_id','word_set','sound_set','storyTitle','storyText','response_prompt','sourceMaterialId']){
                    assert.deepEqual(restored.content[key],values.content[key],`${name}: preserve saved ${key}`);
                }
                f.d.querySelector('#templateSaveBtn').click();await settle();await settle();
                assert.equal(f.w.posts.length,2,'edit must save successfully');
                assert.equal(f.w.posts[1].url,'/dashboard/teacher/update-material/');
                assert.equal(f.w.posts[1].body.material_id,1001);
                f.w.fixture.restore({id:1001,raw_id:1001,source_type:'template',title:saved.title,language:saved.language,assigned_weeks:saved.assigned_weeks,content_json:JSON.parse(saved.content)});await settle();
                if(selectors[name]){
                    change(f,selectors[name],'');await settle();assert.equal(schedule(f),true,'clearing configuration must relock schedule');
                    assert.equal(f.d.querySelector('#materialPublicationSettings').inert,true,'clearing configuration must relock assignment');
                }else{
                    const state=f.w.fixture.state();
                    const field={'Syllable Blending':'selectedActivityId','Picture-Word Matching':'pictureWordMatching','Phrase Reading Practice':'phraseReading','Sentence Reading Practice':'sentenceReading','Story Reading':'storyReading'}[name];
                    if(field==='selectedActivityId')state[field]=null;
                    else if(field==='storyReading')state[field].storyKey='';
                    else state[field].setKey='';
                    f.w.fixture.dynamic();f.w.fixture.preview();await settle();
                    assert.equal(schedule(f),true,'programmatic clearing must relock schedule');
                    assert.equal(f.d.querySelector('#materialPublicationSettings').inert,true);
                }
                assert.deepEqual(f.errors,[]);
            }finally{f.dom.window.close();}
        });
    });
    test('Letter & Sound Matching: programmatic first-set selection works without a change event or interaction flag',async()=>{
        const f=create();try{
            await prepare(f,'Letter & Sound Matching');
            const state=f.w.fixture.state();state.__teacherSelectedConfiguration=false;
            state.letterSoundMatching.readingSetId='filipino_set_1';
            f.w.fixture.dynamic();f.w.fixture.preview();await settle();
            assert.equal(schedule(f),false);
            assert.deepEqual([...f.d.querySelectorAll('.letter-sound-item-letter')].map(e=>e.textContent),['a','e','i','o','u']);
            assert.equal(state.items.length,5);
        }finally{f.dom.window.close();}
    });
    test('custom Picture-Word Matching requires five items and keeps the item limit intact',async()=>{
        const f=create();try{
            await prepare(f,'Picture-Word Matching');change(f,'input[name="pictureWordMode"][value="custom"]',true);
            for(let i=0;i<4;i++){f.d.querySelector('[data-picture-word-custom-toggle]:not(.is-selected)').click();await settle();}
            assert.equal(schedule(f),true);
            f.d.querySelector('[data-picture-word-custom-toggle]:not(.is-selected)').click();await settle();
            assert.equal(schedule(f),false);
            assert.equal(f.d.querySelector('[data-picture-word-custom-toggle]:not(.is-selected)').disabled,true);
            f.d.querySelector('[data-picture-word-custom-remove]').click();await settle();assert.equal(schedule(f),true);
        }finally{f.dom.window.close();}
    });
    test('Clap & Count count shown after Select All matches validation and the saved value',async()=>{
        const f=create();try{
            await prepare(f,'Clap & Count Syllables');await selectContent(f,'Clap & Count Syllables');
            assert.equal(Number(f.d.querySelector('#clapNumber').value),f.w.fixture.state().clapCount.numberOfWords);
            assert.equal(f.w.fixture.state().clapCount.numberOfWords,Math.min(10,f.w.fixture.state().clapCount.selectedWordIds.length));
        }finally{f.dom.window.close();}
    });
    test('Story Response restores custom prompts and optional narration/recording settings',async()=>{
        const f=create();try{
            await prepare(f,'Story Response');await selectContent(f,'Story Response');
            const prompt=f.d.querySelector('#storyResponseCustomPrompt');prompt.value='A saved custom prompt';prompt.dispatchEvent(new f.w.Event('input',{bubbles:true}));
            change(f,'#storyResponseReadAloud',false);change(f,'#storyResponseVoiceRecording',false);
            const values=f.w.fixture.values();
            f.w.fixture.restore({id:1001,title:'Saved response',language:'Filipino',assigned_weeks:['Week 1'],content_json:{...values.content,template_title:'Story Response'}});await settle();
            const restored=f.w.fixture.values();assert.equal(restored.content.response_prompt,'A saved custom prompt');
            assert.equal(restored.content.prompt_source,'custom');assert.equal(restored.content.read_aloud_enabled,false);assert.equal(restored.content.voice_recording_enabled,false);
            assert.equal(f.d.querySelector('#storyResponseStory').value,'1');assert.equal(schedule(f),false);
        }finally{f.dom.window.close();}
    });
    test('late story responses cannot overwrite another activity panel',async()=>{
        for(const name of ['Story Response','Retell the Story']){
            const f=create();try{
                f.w.deferStories=true;await prepare(f,name);assert.ok(f.w.pendingStories.length);
                await prepare(f,'Letter & Sound Matching');f.w.pendingStories.forEach(resolve=>resolve());await settle();
                assert.equal(f.w.fixture.state().templateTitle,'Letter & Sound Matching');
                assert.equal(f.d.querySelector('#letterSoundReadingSet').value,'');assert.equal(schedule(f),true);assert.deepEqual(f.errors,[]);
            }finally{f.dom.window.close();}
        }
    });
    test('an existing valid 5W activity with fewer questions keeps its saved edit configuration',async()=>{
        const f=create();try{
            f.w.fixture.restore({id:1001,title:'Legacy questions',language:'Filipino',assigned_weeks:['Week 1'],content_json:{template_title:"5W's Story Questions",sourceMaterialId:1,storyTitle:'Fixture story 1',storyText:'Fixture passage 1.',items:[{question:'Who?',answer:'Ana',answers:['Ana']}]}});await settle();
            assert.equal(f.d.querySelector('#fiveWStory').value,'1');assert.equal(f.w.fixture.state().items.length,1);
            assert.equal(schedule(f),false);assert.equal(f.w.fixture.validate(f.w.fixture.values()),'');
        }finally{f.dom.window.close();}
    });
}
