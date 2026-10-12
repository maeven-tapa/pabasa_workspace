// Exercise the actual course progress renderer and delegated review handlers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '..');
const app = path.join(root, 'pabasa_site/pabasa_app');
const template = fs.readFileSync(path.join(app, 'templates/pabasa_app/courses.html'), 'utf8').replace(/\r\n/g, '\n');
const between = (start, end) => {
    const first = template.indexOf(start), last = template.indexOf(end, first);
    assert(first >= 0 && last > first, start);
    return template.slice(first, last);
};
const live = Boolean(process.env.PABASA_REVIEW_SERVER);
const lesson1Only = process.env.PABASA_REVIEW_LESSON1_ONLY === '1';
const liveUrls = JSON.parse(process.env.PABASA_REVIEW_URLS || '{}');
const urls = text => text.replace(/{% url ["']([^"']+)["'] %}/g, (_, name) => liveUrls[name] || '/test/'+name);
const progress = between('        function progressStudentMatches(', "        if (e.target.closest('.view-student-progress'))");
const audio = between('    const studentProgressRetellGrades = new Map();', '    // Existing course student-progress actions');
const grades = between("    document.addEventListener('click', function(event) {\n        const fluencyButton", "    document.addEventListener('input', function(event) {");
const fluency = between("    document.addEventListener('change', function(event) {\n        const select = event.target.closest('.session5-fluency-select')", "    document.addEventListener('click', function(event) {\n        const courseTrigger");
const adapter = between('    function installCourseInlineModalAdapter() {', '    installCourseInlineModalAdapter();');
const modalHtml = between('<div class="modal fade" id="studentProgressModal"', '<script>\ndocument.addEventListener');
const courseCss = [...template.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(match => match[1]).join('\n').replace(/{% static ["']([^"']+)["'] %}/g, '/static/$1');
const dashboard = fs.readFileSync(path.join(app, 'templates/pabasa_app/base_dashboard.html'), 'utf8').replace(/\r\n/g, '\n');
const dashboardCss = [...dashboard.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(match => match[1]).join('\n');
const displayScale = dashboard.slice(dashboard.indexOf('        (() => {\n            const applyDashboardDisplayScale'), dashboard.indexOf('    </script>', dashboard.indexOf('const applyDashboardDisplayScale')));
async function assertReviewFits(dialog) {
    const bounds = await dialog.evaluate(node => {
        const rect = element => {const r = element.getBoundingClientRect(); return {top:r.top,bottom:r.bottom,left:r.left,right:r.right};};
        return {dialog:rect(node),header:rect(node.querySelector('.student-progress-review-header')),
            close:rect(node.querySelector('.student-progress-review-close')),height:innerHeight,width:innerWidth};
    });
    for (const [name, rect] of Object.entries(bounds).filter(([name])=>['dialog','header','close'].includes(name))) {
        assert(rect.top >= 0 && rect.bottom <= bounds.height && rect.left >= 0 && rect.right <= bounds.width,
            `${name} must fit the viewport: ${JSON.stringify(bounds)}`);
    }
    assert(await dialog.evaluate(node=>node.scrollHeight<=node.clientHeight+2), 'Only the recording list should scroll');
    if(await dialog.evaluate(node=>node.classList.contains('student-progress-review-dialog--compact-reading'))){
        assert(bounds.dialog.right-bounds.dialog.left<=1100,'Compact dialog width must account for dashboard zoom');
    }
}
const keys = ['lesson-1-gawain-1','session-4-gawain-1','session-4-gawain-2','lesson-13-gawain-1','session-5-lesson-14-gawain-4','lesson-29-gawain-3'];
const letters = ['B','b','U','u'];
const wav = Buffer.alloc(44 + 32000);
wav.write('RIFF',0);wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);
wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(1,22);
wav.writeUInt32LE(16000,24);wav.writeUInt32LE(32000,28);wav.writeUInt16LE(2,32);
wav.writeUInt16LE(16,34);wav.write('data',36);wav.writeUInt32LE(32000,40);
const attempts = Object.fromEntries(keys.map((key, index) => ['prescribed-'+key, {attempts:[{
    student_id:48, status:'in_progress', submission_id:100+index,
    recording_available:true, recording_url:'/recording.wav', can_retry:true, can_check:true,
    session4_total_items:index===2?12:index===5?11:4, session4_correct_items:0,
    session4_recordings:Array.from({length:index===2?8:index===5?11:4}, (_, item) => ({
        submission_id:200+index*20+item, item_label:letters[item%4], teacher_score:null,
        recording_available:item===0, audio_url:item===0?'/recording.wav':null,
    })),
    session5_recordings:Array.from({length:22}, (_, item) => ({
        item_index:item, expected_text:'Reading '+(item+1), submission_id:item===1?501:null,
        classification:item===0?'RED':'', classification_source:item===0?'skipped':'',
        review_status:item===0?'skipped':'pending', recording_url:item===1?'/recording.wav':null,
    })),
}]}]));
attempts['prescribed-lesson-15-gawain-3'] = {attempts:[{
    student_id:48, status:'in_progress', activity_type:'session_5_fluency', lesson15_review:true,
    session5_recordings:Array.from({length:22}, (_, item) => ({
        item_index:item, expected_text:'Reading '+(item+1), submission_id:item===1?601:null,
        attempt_id:'test-attempt', review_version:0,
        classification:item===0?'RED':'', classification_source:item===0?'skipped':'',
        review_status:item===0?'skipped':item===1?'pending':'missing',
        recording_url:item===1?'/recording.wav':null,
    })),
}]};
Object.assign(attempts, JSON.parse(process.env.PABASA_REVIEW_ATTEMPTS || '{}'));
const studentId = Number(process.env.PABASA_REVIEW_STUDENT_ID || 48);
Object.values(attempts).forEach(entry=>entry.attempts.forEach(attempt=>attempt.student_id=studentId));
const setup = `
const course={title:'Reading course',materials:[],sections:[]};
const findCourseById=()=>course, activeRecords=rows=>rows, classReadings={};
const progressFixtures=${JSON.stringify(attempts)};
const rawRecordId=value=>value, fetchAssessmentProgressDetails=async()=>progressFixtures;
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const latestAttemptValue=(attempt,...keys)=>keys.map(key=>attempt[key]).find(value=>value!==undefined);
const reviewToasts=[];
const formatDateTime=String,formatCourseReportDuration=String,ensureCsrfToken=async()=>'a'.repeat(32),showToast=(message,type)=>reviewToasts.push({message,type});
class Modal{constructor(element){this._element=element;Modal.instances.set(element,this)}show(){this._element.classList.add('show')}hide(){this._element.classList.remove('show');this._element.dispatchEvent(new Event('hidden.bs.modal'))}static getOrCreateInstance(element){return Modal.getInstance(element)||new Modal(element)}static getInstance(element){return Modal.instances.get(element)}}
Modal.instances=new WeakMap();window.bootstrap={Modal};
${audio}
${urls(lesson1Only ? progress.replace('const tasks = courseProgressTasks(course, studentId);',
    "const tasks = courseProgressTasks(course, studentId).filter(task=>task.assessmentId==='prescribed-lesson-1-gawain-1');") : progress)}
${urls(grades)}
${urls(fluency)}
${adapter}
installCourseInlineModalAdapter();
window.openProgress=()=>openStudentProgressModal(${studentId},'Test student','1');
`;

new (require('node:vm').Script)(setup);
(async()=>{
    const browser = await chromium.launch({channel:'chrome',headless:true});
    try {
        for (const [width,height,ratio] of (live ? [[1918,997,1]] : [[1918,997,1],[1366,900,1.25],[1366,768,1.5],[1024,500,1],[390,844,1],[844,390,1]])) {
            const page = await browser.newPage({viewport:{width,height},deviceScaleFactor:ratio,
                userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'});
            const errors=[],posts=[];
            const base=process.env.PABASA_REVIEW_SERVER || 'http://localhost:9876';
            if(live)await page.context().addCookies([{name:'sessionid',value:process.env.PABASA_REVIEW_TEACHER_COOKIE,url:base},{name:'csrftoken',value:'a'.repeat(32),url:base}]);
            page.on('pageerror',error=>errors.push(error.message));
            let failNext=false;
            let failAvailability=false, holdAvailability=false, releaseAvailability;
            const availabilityRequests=[];
            const completion = Object.fromEntries(Object.keys(attempts).map(key => [key, true]));
            await page.route('**/*', async route=>{
                const request=route.request(),url=new URL(request.url());
                if(url.pathname==='/activity')return route.fulfill({contentType:'text/html',body:'<!doctype html><html></html>'});
                if(live && url.pathname.startsWith('/api/')){
                    if(url.pathname===liveUrls.teacher_prescribed_review_availability){
                        availabilityRequests.push(url.searchParams.get('activity_id'));
                        if(failAvailability){failAvailability=false;return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({success:false})});}
                        if(holdAvailability)await new Promise(resolve=>releaseAvailability=resolve);
                    }
                    if(request.method()==='POST'){
                        posts.push({url:url.pathname,data:request.postDataJSON()});
                        if(failNext){failNext=false;return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({success:false,error:'Test save failure'})});}
                    }
                    return route.continue();
                }
                if(url.pathname==='/static/pabasa_app/font/Righteous-Regular.ttf')return route.fulfill({contentType:'font/ttf',body:fs.readFileSync(path.join(app,'static/pabasa_app/font/Righteous-Regular.ttf'))});
                if(url.pathname==='/fonts/bootstrap-icons.woff2')return route.fulfill({contentType:'font/woff2',body:fs.readFileSync(path.join(app,'static/pabasa_app/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2'))});
                if(url.pathname.startsWith('/test/')) {
                    if(url.pathname==='/test/teacher_prescribed_review_availability') {
                        const key=url.searchParams.get('activity_id');
                        return route.fulfill({contentType:'application/json',body:JSON.stringify({success:true,
                            completed:key?{[key]:completion[key]===true}:completion})});
                    }
                    const data=request.postDataJSON();posts.push({url:url.pathname,data});
                    const fail=failNext;failNext=false;
                    const items=attempts['prescribed-lesson-15-gawain-3'].attempts[0].session5_recordings.map(item=>item.item_index===data.item_index?{...item,classification:data.classification,classification_source:'teacher',review_status:'reviewed'}:item);
                    return route.fulfill({status:fail?500:200,contentType:'application/json',body:JSON.stringify(fail?{success:false,error:'Test save failure'}:{success:true,items,all_reviewed:true,correct_items:1,total_items:url.pathname.includes('lesson29')?11:4,status:data.action==='retry'?'retry':'checked'})});
                }
                if(url.pathname==='/recording.wav')return route.fulfill({contentType:'audio/wav',body:wav});
                return route.fulfill({status:404,body:''});
            });
            await page.goto(base+'/activity');
            await page.setContent(`<style>body{font-family:Arial;margin:0}.d-none{display:none!important}.modal:not(.course-detail-page){display:none}.student-progress-list{display:grid;gap:12px}.student-progress-card{border:1px solid #dce8ed;border-radius:12px;padding:16px}.student-progress-card-header,.student-progress-stats{display:flex;justify-content:space-between}.student-progress-title{margin:8px 0}.student-progress-type{font-size:12px;color:#176078}.student-progress-stats{margin-top:12px}.student-progress-stat-label{display:block;font-size:11px}.form-select{padding:10px;width:100%}${courseCss}${fs.readFileSync(path.join(app,'static/pabasa_app/css/student_activity_review.css'),'utf8')}</style><main id="courseDetailModal" class="course-detail-page"><button class="course-modal-close-btn" data-bs-dismiss="modal">Close course</button><div id="courseMainContent"></div><aside id="courseSidebar"></aside><div id="courseInlineDialogHost"></div></main>${modalHtml}`);
            await page.addStyleTag({content:dashboardCss});
            await page.addStyleTag({path:path.join(app,'static/pabasa_app/vendor/bootstrap-icons/bootstrap-icons.css')});
            await page.evaluate(()=>document.getElementById('courseDetailModal').classList.add('dashboard-app-shell'));
            await page.addScriptTag({content:displayScale});
            await page.addScriptTag({path:path.join(app,'static/pabasa_app/js/student_activity_review.js')});
            await page.addScriptTag({path:path.join(app,'static/pabasa_app/js/lesson15_reading_review.js')});
            await page.addScriptTag({content:setup});
            assert.deepEqual(errors,[]);
            await page.evaluate(()=>window.openProgress());
            const cards=page.locator('#studentProgressList > .student-progress-card');
            assert.equal(await cards.count(),lesson1Only?1:7);
            assert.deepEqual(await cards.locator('.student-progress-type').allTextContents(),lesson1Only?['Session 1']:['Session 1','Session 4','Session 4','Session 5','Session 5','Session 5','Session 13']);
            assert.equal(await page.locator('dialog[open]').count(),0);
            assert.equal(await page.locator('.session4-letter-recording:visible').count(),0);
            assert.equal(await page.locator('.session5-fluency-row:visible').count(),0);
            if(process.env.PABASA_REVIEW_GATE_ONLY==='1'){
                const trigger=index=>cards.nth(index).locator('.student-progress-review-trigger');
                for(let index=0;index<7;index++)assert.equal(await trigger(index).isDisabled(),index!==3);
                assert.match(await trigger(3).textContent(),/Open to listen and review/);
                for(const width of [390,1918]){
                    await page.setViewportSize({width,height:width===390?844:997});
                    assert(await trigger(0).evaluate(node=>node.scrollWidth<=node.clientWidth));
                    assert.equal(await trigger(0).evaluate(node=>getComputedStyle(node).transitionDuration),'0s');
                    for(const dark of [true,false]){
                        await page.evaluate(dark=>document.body.classList.toggle('dark-theme',dark),dark);
                        await trigger(0).hover();
                        assert.equal(await trigger(0).evaluate(node=>getComputedStyle(node).cursor),'not-allowed');
                        assert.equal(await trigger(0).evaluate(node=>getComputedStyle(node).color),
                            await trigger(0).locator('span[aria-hidden]').evaluate(node=>getComputedStyle(node).color));
                        assert.equal(await trigger(0).evaluate(node=>getComputedStyle(node).transform),'none');
                    }
                }
                for(const index of [0,5]){
                    assert.equal(await trigger(index).locator('small').textContent(),'Available after activity completion');
                    assert.equal(await trigger(index).evaluate(node=>getComputedStyle(node).cursor),'not-allowed');
                    const colors=await trigger(index).evaluate(node=>{
                        const style=getComputedStyle(node);return [style.backgroundColor,style.borderColor,style.color,style.transform];
                    });
                    await trigger(index).hover();
                    assert.deepEqual(await trigger(index).evaluate(node=>{
                        const style=getComputedStyle(node);return [style.backgroundColor,style.borderColor,style.color,style.transform];
                    }),colors,'Disabled hover must not change the button');
                    await trigger(index).evaluate(node=>node.focus());
                    assert.equal(await trigger(index).evaluate(node=>node===document.activeElement),false);
                    const before=availabilityRequests.length;
                    await trigger(index).evaluate(node=>{
                        node.disabled=false;
                        node.closest('article').dataset.reviewPrescribed='false';
                        node.dispatchEvent(new MouseEvent('click',{bubbles:true}));
                    });
                    assert.equal(await trigger(index).isDisabled(),true,'Direct events cannot bypass captured completion');
                    assert.equal(availabilityRequests.length,before);
                    assert.equal(await page.locator('dialog[open]').count(),0);
                }
                // Actual keyboard activation opens a completed activity with
                // pending grades, but must perform a fresh server GET first.
                await trigger(3).focus();
                await page.keyboard.press('Enter');
                await page.waitForFunction(()=>Boolean(document.querySelector('dialog[open]')));
                assert.equal(availabilityRequests.at(-1),'prescribed-lesson-13-gawain-1');
                await cards.nth(3).locator('.student-progress-review-close').click();
                failAvailability=true;
                await trigger(3).click();
                await page.waitForFunction(()=>reviewToasts.length>0);
                assert.equal(await page.locator('dialog[open]').count(),0);
                assert.equal(await trigger(3).isEnabled(),true,'A failed status request must allow retry');
                // Double invocation during a pending completion check sends
                // only one GET and cannot open early.
                holdAvailability=true;
                const before=availabilityRequests.length;
                await trigger(3).evaluate(node=>{
                    node.dispatchEvent(new MouseEvent('click',{bubbles:true}));
                    node.dispatchEvent(new MouseEvent('click',{bubbles:true}));
                });
                while(!releaseAvailability)await page.waitForTimeout(10);
                assert.equal(availabilityRequests.length,before+1);
                assert.equal(await page.locator('dialog[open]').count(),0);
                holdAvailability=false;releaseAvailability();
                await page.waitForFunction(()=>Boolean(document.querySelector('dialog[open]')));
                await cards.nth(3).locator('.student-progress-review-close').click();
                const student=await browser.newContext({extraHTTPHeaders:{Cookie:
                    `sessionid=${process.env.PABASA_REVIEW_STUDENT_COOKIE}; csrftoken=${'a'.repeat(32)}`,
                    'X-CSRFToken':'a'.repeat(32)}});
                const finished=await student.request.post(base+liveUrls.lesson15_reading_skip,{data:{
                    activity_key:'lesson-15-gawain-3',item_index:21,
                    state_version:Number(process.env.PABASA_REVIEW_STATE_VERSION),request_id:require('node:crypto').randomUUID()}});
                assert.equal(finished.status(),200,await finished.text());
                assert.equal((await finished.json()).progress.activity_completed,true);
                await page.evaluate(()=>window.openProgress());
                assert.equal(await trigger(5).isEnabled(),true,'Refreshing must observe persisted completion');
                for(const index of [0,1,2,4,6])assert.equal(await trigger(index).isDisabled(),true,'Completing L15 must not enable another activity');
                await trigger(5).click();
                await page.waitForFunction(()=>Boolean(document.querySelector('dialog[open]')));
                await cards.nth(5).locator('.student-progress-review-close').click();
                // A real disposable restart invalidates the cached enabled
                // state; fresh server validation must prevent the old button
                // from opening even before the teacher refreshes the cards.
                const reset=await student.request.post(base+liveUrls.lesson15_progress,{data:{reset:true}});
                assert.equal(reset.status(),200,await reset.text());
                assert.equal((await reset.json()).progress.activity_completed,false);
                await trigger(5).click();
                await page.waitForFunction(()=>document.querySelectorAll('.student-progress-review-trigger')[5].getAttribute('aria-busy')===null);
                assert.equal(await trigger(5).isDisabled(),true);
                assert.equal(await page.locator('dialog[open]').count(),0);
                await student.close();
                // Source switching, search, and supplementary review behavior
                // remain independent of the prescribed completion gate.
                await page.evaluate(()=>{
                    course.materials.push({id:900,title:'Supplementary recording',source_type:'personal',content_json:{activity_type:'retell_story'}});
                    progressFixtures['material-900']={attempts:[{student_id:window.__studentProgressStudentId,status:'in_progress'}]};
                });
                await page.locator('[data-student-progress-source="supplementary"]').click();
                await page.waitForFunction(()=>document.querySelectorAll('#studentProgressList>.student-progress-card').length===1);
                assert.equal(await trigger(0).isEnabled(),true);
                const previousRequests=availabilityRequests.length;
                await trigger(0).click();
                assert.equal(await page.locator('dialog[open]').count(),1);
                assert.equal(availabilityRequests.length,previousRequests,'Supplementary review must not use this gate');
                await cards.nth(0).locator('.student-progress-review-close').click();
                await page.locator('[data-student-progress-source="prescribed"]').click();
                await page.waitForFunction(()=>document.querySelectorAll('#studentProgressList>.student-progress-card').length===7);
                await page.locator('#studentProgressSearch').fill('Lesson 15');
                assert.equal(await cards.count(),1);
                assert.equal(await trigger(0).isDisabled(),true);
                await page.locator('#studentProgressSearch').fill('');
                await page.locator('#studentProgressSort').selectOption('latest');
                assert.equal(await cards.count(),7);
                assert.equal(await trigger(3).isEnabled(),true);
                assert.deepEqual(errors,[]);
                await page.close();
                console.log('PASS: real current-term completion gate, not-started/in-progress disabled despite recordings/grades, completed pending reviews enabled, keyboard/direct-event bypass blocked, status failure/retry, double-click protection, persisted completion refresh and activity isolation, stale enabled button rejected after disposable restart, source tabs/search/sort preserved.');
                continue;
            }
            const openReview=async index=>{
                await cards.nth(index).locator('.student-progress-review-trigger').click();
                await cards.nth(index).locator('dialog[open]').waitFor({state:'visible'});
            };
            for(const [index,count] of (lesson1Only?[]:[[1,4],[2,8],[3,4],[6,11]])){
                await openReview(index);
                const dialog=cards.nth(index).locator('dialog');
                await assertReviewFits(dialog);
                assert.equal(await dialog.locator('.student-progress-review-footer').count(),0);
                assert.equal(await dialog.getByRole('button',{name:'Back to activities'}).count(),0);
                assert.equal(await dialog.locator('.session4-letter-recording:visible').count(),count);
                assert.equal(await dialog.locator('audio').count(),1);
                assert.equal(await dialog.locator('.session4-no-recording').count(),count-1);
                {
                    const identities={1:['SESSION 4','Lessons 10, 11, at 12 · Gawain 1'],2:['SESSION 4','Lessons 10, 11, at 12 · Gawain 2'],3:['SESSION 5','Lesson 13 · Gawain 1'],6:['SESSION 13','Lesson 29 Activity 3 · Trace & Say']};
                    assert.equal(await dialog.locator('.student-progress-review-header small').textContent(),identities[index][0]);
                    assert.equal(await dialog.locator('.student-progress-review-header h2').textContent(),identities[index][1]);
                    assert.equal(await dialog.getByText('Teacher Review',{exact:true}).count(),0);
                    assert.equal(await dialog.locator('.session5-evaluation-summary strong').textContent(),`Reading Evaluation — 0 / ${count} Reviewed`);
                    assert.equal(await dialog.locator('.session5-evaluation-summary span').textContent(),'Pending: 1 · Skipped: 0');
                    assert.equal(await dialog.locator('.reading-review-neutral').count(),count-1);
                    assert.equal(await dialog.locator('.session4-score-button').count(),2);
                    await dialog.locator('.student-progress-review-header h2').evaluate(node=>document.fonts.load(getComputedStyle(node).font));
                    assert.equal(await dialog.locator('.student-progress-review-header h2').evaluate(node=>getComputedStyle(node).fontFamily.includes('Righteous')),true);
                    for(const size of [{width:390,height:844},{width,height}]){
                        await page.setViewportSize(size);
                        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
                        await assertReviewFits(dialog);
                        assert(await dialog.evaluate(node=>node.scrollWidth<=node.clientWidth+2));
                        assert(await dialog.locator('.student-progress-review-body').evaluate(node=>node.scrollHeight<=node.clientHeight+2));
                        assert(await dialog.locator('.reading-review-list').evaluate(node=>node.scrollWidth<=node.clientWidth+2));
                        if(size.width===390){
                            assert.equal(await dialog.locator('.session4-letter-recording').first().evaluate(node=>getComputedStyle(node).gridTemplateColumns.trim().split(/\s+/).length),1,'Letter-score rows must stack without implicit grid tracks');
                            assert(await dialog.locator('audio').evaluate(node=>node.getBoundingClientRect().width>=180),'Mobile audio controls must remain visible and usable');
                            if(count>=8){
                                const top=await dialog.locator('.session5-evaluation-summary').evaluate(node=>node.getBoundingClientRect().top);
                                assert(await dialog.locator('.reading-review-list').evaluate(node=>node.scrollHeight>node.clientHeight));
                                await dialog.locator('.reading-review-list').evaluate(node=>node.scrollTop=node.scrollHeight);
                                assert.equal(await dialog.locator('.session5-evaluation-summary').evaluate(node=>node.getBoundingClientRect().top),top,'Review summary must stay fixed while recordings scroll');
                                await dialog.locator('.reading-review-list').evaluate(node=>node.scrollTop=0);
                            }
                        }
                        if(process.env.PABASA_REVIEW_SCREENSHOTS)await page.screenshot({path:path.join(process.env.PABASA_REVIEW_SCREENSHOTS,`teacher-recording-review-${index}-${size.width}.png`)});
                    }
                }
                await dialog.locator('.session4-score-button[data-score="1"]').click();
                await dialog.locator('.session4-score-feedback').filter({hasText:'Saved'}).waitFor();
                assert.equal(posts.at(-1).data.score,1);
                const scoreName=index===6?'teacher_lesson29_trace_say_score':['teacher_session_4_gawain_1_score','teacher_session_4_gawain_2_score','teacher_lesson_13_gawain_1_score'][index-1];
                assert.equal(posts.at(-1).url,liveUrls[scoreName] || '/test/'+scoreName);
                assert.equal(await dialog.locator('.session5-evaluation-summary strong').textContent(),`Reading Evaluation — 1 / ${count} Reviewed`);
                assert.equal(await cards.nth(index).locator('.student-progress-score').textContent(),live?'Awaiting teacher':index===6?'1/11':'1/4');
                failNext=true;
                await dialog.locator('.session4-score-button[data-score="0"]').click();
                await dialog.locator('.session4-score-feedback').filter({hasText:'Test save failure'}).waitFor();
                assert.equal(await dialog.locator('.session4-score-button.selected').getAttribute('data-score'),'1');
                await dialog.locator('audio').evaluate(audio=>audio.play());
                assert.equal(await dialog.locator('audio').evaluate(audio=>audio.paused),false);
                await page.keyboard.press('Escape');
                assert.equal(await dialog.evaluate(node=>node.open),true,'Escape must not close the review');
                await page.mouse.click(1,1);
                assert.equal(await dialog.evaluate(node=>node.open),true,'Outside clicks must not close the review');
                // Exercise the fallback used by browsers without closedby support.
                assert.equal(await dialog.evaluate(node=>node.dispatchEvent(new Event('cancel',{cancelable:true}))),false);
                assert.equal(await dialog.evaluate(node=>node.open),true);
                await dialog.locator('.student-progress-review-close').click();
                await page.waitForFunction(()=>!document.querySelector('dialog[open]'));
                await page.waitForFunction(id=>document.getElementById(id).querySelector('audio').paused,await dialog.getAttribute('id'));
                assert.equal(await dialog.locator('audio').evaluate(audio=>audio.paused),true);
                assert.equal(await page.locator('#courseInlineDialogHost').getAttribute('data-inline-modal-id'),'studentProgressModal');
                assert.equal(await cards.nth(index).locator('.student-progress-review-trigger').evaluate(node=>node===document.activeElement),true);
                await openReview(index);
                assert.equal(await dialog.locator('.session4-score-button.selected').getAttribute('data-score'),'1');
                await dialog.locator('.student-progress-review-close').click();
            }
            for(const index of (lesson1Only?[]:[4,5])){
            await openReview(index);
            const fluencyDialog=cards.nth(index).locator('dialog');
            await assertReviewFits(fluencyDialog);
            assert.equal(await fluencyDialog.locator('.session5-fluency-row').count(),22);
            assert.equal(await fluencyDialog.locator('.student-progress-review-header h2').textContent(),index===4?'Lesson 14 · Gawain 4':'Lesson 15 · Gawain 3');
            assert.equal(await fluencyDialog.getByText('Teacher Review',{exact:true}).count(),0);
            assert.equal(await fluencyDialog.locator('.session5-evaluation-summary strong').textContent(),'Reading Evaluation — 0 / 22 Reviewed');
            assert.equal(await fluencyDialog.locator('.session5-evaluation-summary span').textContent(),'Pending: 1 · Skipped: 1');
            const readingRows=fluencyDialog.locator('.session5-fluency-row');
            assert.equal(await readingRows.nth(0).locator('select').count(),0);
            assert.equal(await readingRows.nth(0).locator('.session5-review-state').textContent(),'Nilaktawan · Awtomatiko');
            assert.equal(await readingRows.nth(2).locator('select').count(),0);
            assert.equal(await readingRows.nth(2).locator('.reading-review-neutral').textContent(),'Wala pang pagbasa');
            for(const grade of ['GREEN','YELLOW','RED']){
            await readingRows.nth(1).locator('select').selectOption(grade);
            await readingRows.nth(1).locator('.session5-review-state').filter({hasText:'reviewed'}).waitFor();
            await page.waitForFunction(()=>!document.querySelector('dialog[open] select').disabled);
            assert.equal(await fluencyDialog.locator('.session5-evaluation-summary strong').textContent(),'Reading Evaluation — 1 / 22 Reviewed');
            assert.equal(await fluencyDialog.locator('.session5-evaluation-summary span').textContent(),'Pending: 0 · Skipped: 1');
            }
            assert.equal(posts.at(-1).data.classification,'RED');
            const classifyName=index===4?'teacher_session_5_lesson_14_gawain_4_classify':'lesson15_reading_classify';
            assert.equal(posts.at(-1).url,liveUrls[classifyName] || '/test/'+classifyName);
            failNext=true;
            await readingRows.nth(1).locator('select').selectOption('GREEN');
            await page.waitForFunction(()=>!document.querySelector('dialog[open] select').disabled);
            assert.equal(await readingRows.nth(1).locator('select').inputValue(),'RED');
            assert.equal(await fluencyDialog.locator('.session5-evaluation-summary strong').textContent(),'Reading Evaluation — 1 / 22 Reviewed');
            await fluencyDialog.locator('audio').evaluate(audio=>audio.play());
            assert.equal(await fluencyDialog.locator('audio').evaluate(audio=>audio.paused),false);
            assert(await fluencyDialog.evaluate(dialog=>dialog.scrollWidth<=dialog.clientWidth+2));
            assert(await fluencyDialog.locator('.reading-review-list').evaluate(body=>body.scrollHeight>body.clientHeight));
            assert(await fluencyDialog.locator('.student-progress-review-body').evaluate(body=>body.scrollHeight<=body.clientHeight+2));
            await fluencyDialog.locator('.reading-review-list').evaluate(body=>body.scrollTo(0,body.scrollHeight));
            await assertReviewFits(fluencyDialog);
            assert(await fluencyDialog.locator('.session5-evaluation-summary').evaluate(node=>{const r=node.getBoundingClientRect(),d=node.closest('dialog').getBoundingClientRect();return r.top>=d.top&&r.bottom<=d.bottom;}));
            if(width===1918){
                for(const size of [{width:390,height:844},{width,height}]){
                    await page.setViewportSize(size);
                    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
                    await assertReviewFits(fluencyDialog);
                    assert(await fluencyDialog.locator('.reading-review-list').evaluate(node=>node.scrollWidth<=node.clientWidth+2));
                    if(size.width===390)assert.equal(await fluencyDialog.locator('.session5-fluency-row').first().evaluate(node=>getComputedStyle(node).gridTemplateColumns.trim().split(/\s+/).length),1,'Mobile rows must stack in one column without implicit grid tracks');
                    if(process.env.PABASA_REVIEW_SCREENSHOTS)await page.screenshot({path:path.join(process.env.PABASA_REVIEW_SCREENSHOTS,`teacher-recording-review-${index}-${size.width}.png`)});
                }
            }
            await fluencyDialog.locator('.reading-review-list').evaluate(body=>body.scrollTo(0,0));
            if(process.env.PABASA_REVIEW_SCREENSHOTS)await page.screenshot({path:path.join(process.env.PABASA_REVIEW_SCREENSHOTS,`teacher-recording-review-${index}-${width}.png`)});
            await fluencyDialog.locator('.student-progress-review-close').click();
            if(live){
                const name=index===4?'teacher_session_5_lesson_14_gawain_4_recordings':'lesson15_reading_reviews';
                const key=index===4?'prescribed-session-5-lesson-14-gawain-4':'prescribed-lesson-15-gawain-3';
                await page.evaluate(async({url,key,id})=>{
                    const response=await fetch(url+'?student_id='+id);const data=await response.json();
                    progressFixtures[key].attempts[0].session5_recordings=data.items;
                },{url:liveUrls[name],key,id:studentId});
            }
            await page.evaluate(()=>window.openProgress());
            await openReview(index);
            const reopened=cards.nth(index).locator('dialog');
            assert.equal(await reopened.locator('.session5-evaluation-summary strong').textContent(),'Reading Evaluation — 1 / 22 Reviewed');
            assert.equal(await reopened.locator('.session5-evaluation-summary span').textContent(),'Pending: 0 · Skipped: 1');
            assert.equal(await reopened.locator('select').inputValue(),'RED');
            await reopened.locator('.student-progress-review-close').click();
            }
            await openReview(0);
            const singleDialog=cards.nth(0).locator('dialog');
            assert.equal(await singleDialog.locator('.student-progress-lesson1-action[data-action="checked"]').textContent(),'Mark as Complete');
            assert.equal(await cards.nth(0).locator('.badge').textContent(),'Pending review');
            await page.evaluate(()=>document.fonts.load('16px bootstrap-icons'));
            assert.equal(await singleDialog.locator('.student-progress-retell-play i').evaluate(node=>getComputedStyle(node,'::before').content==='none'),false);
            assert.equal(await singleDialog.locator('.student-progress-review-header small').textContent(),'SESSION 1');
            assert.equal(await singleDialog.locator('.student-progress-review-header h2').textContent(),'Lesson 1 · Gawain 1');
            assert.equal(await singleDialog.locator('.single-recording-review-row').count(),1);
            assert.equal(await singleDialog.locator('.session5-evaluation-summary strong').textContent(),'Reading Evaluation — 0 / 1 Reviewed');
            assert.equal(await singleDialog.locator('.session5-evaluation-summary span').textContent(),'Pending: 1 · Skipped: 0');
            assert.equal(await singleDialog.locator('select,.session4-score-button').count(),0,'Lesson 1 retains review actions, not letter/fluency grades');
            for(const size of [{width:390,height:844},{width,height}]){
                await page.setViewportSize(size);
                await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
                await assertReviewFits(singleDialog);
                assert(await singleDialog.locator('.student-progress-review-body').evaluate(node=>node.scrollHeight<=node.clientHeight+2));
                assert(await singleDialog.locator('.reading-review-list').evaluate(node=>node.scrollWidth<=node.clientWidth+2));
                if(process.env.PABASA_REVIEW_SCREENSHOTS)await page.screenshot({path:path.join(process.env.PABASA_REVIEW_SCREENSHOTS,`teacher-recording-review-0-${size.width}.png`)});
            }
            await cards.nth(0).locator('.student-progress-retell-play').click();
            await page.waitForFunction(()=>activeStudentProgressAudio && !activeStudentProgressAudio.paused);
            failNext=true;
            await singleDialog.locator('.student-progress-lesson1-action[data-action="checked"]').click();
            await page.waitForFunction(()=>reviewToasts.at(-1)?.message==='Test save failure'&&!document.querySelector('.student-progress-lesson1-action[data-action="checked"]').disabled);
            assert.equal(await singleDialog.locator('.student-progress-lesson1-action[data-action="checked"]').isEnabled(),true);
            assert.equal(await singleDialog.locator('.session5-evaluation-summary strong').textContent(),'Reading Evaluation — 0 / 1 Reviewed');
            await cards.nth(0).locator('.student-progress-lesson1-action[data-action="checked"]').click();
            await page.waitForFunction(()=>!document.querySelector('.lesson1-review-actions'));
            assert.equal(posts.at(-1).url,liveUrls.teacher_lesson_1_gawain_1_review_action || '/test/teacher_lesson_1_gawain_1_review_action');
            assert.equal(await cards.nth(0).locator('.student-progress-score').textContent(),'1/1');
            assert.equal(await singleDialog.locator('.session5-evaluation-summary strong').textContent(),'Reading Evaluation — 1 / 1 Reviewed');
            assert.equal(await singleDialog.locator('.single-recording-review-status').textContent(),'Reviewed');
            await cards.nth(0).locator('.student-progress-review-close').click();
            await page.waitForFunction(()=>activeStudentProgressAudio===null);
            // Search rerenders the current rows. Approval and full credit must
            // persist there without bringing back the two review actions.
            await page.locator('#studentProgressSearch').fill('Lesson 1 Gawain 1');
            assert.equal(await cards.first().locator('.student-progress-score').textContent(),'1/1');
            assert.equal(await cards.first().locator('.badge').textContent(),'Completed');
            assert.equal(await cards.first().locator('.student-progress-lesson1-action').count(),0);
            await page.locator('#studentProgressSearch').fill('');
            if(lesson1Only){
                await page.evaluate(()=>bootstrap.Modal.getInstance(document.getElementById('studentProgressModal')).hide());
                assert.deepEqual(errors,[]);
                await page.close();
                console.log('PASS: pending Lesson 1 opens before approval, real recording plays, Mark as Complete saves 1/1, failure restores controls, search retains approval, desktop/mobile review fits. Authorized real endpoints in disposable DB.');
                continue;
            }
            if(!live){
                // A fresh disposable pending submission can still be sent for
                // retry; this does not bypass the real checked-record policy.
                await page.evaluate(()=>Object.assign(progressFixtures['prescribed-lesson-1-gawain-1'].attempts[0],
                    {status:'submitted',can_retry:true,can_check:true}));
                await page.evaluate(()=>window.openProgress());
                await openReview(0);
                await cards.nth(0).locator('.student-progress-lesson1-action[data-action="retry"]').click();
                await cards.nth(0).locator('.single-recording-review-status').filter({hasText:'Retry requested'}).waitFor();
                assert.equal(posts.at(-1).data.action,'retry');
                assert.equal(await cards.nth(0).locator('.session5-evaluation-summary strong').textContent(),'Reading Evaluation — 0 / 1 Reviewed');
                await cards.nth(0).locator('.student-progress-review-close').click();
            }
            if(!live){
            await openReview(6);
            failNext=true;
            await cards.nth(6).locator('.student-progress-lesson29-action[data-action="checked"]').click();
            await page.waitForFunction(()=>reviewToasts.at(-1)?.message==='Test save failure');
            assert.equal(await cards.nth(6).locator('dialog[open]').count(),1,'Failed review actions must keep the review open');
            assert.equal(await cards.nth(6).locator('.session4-letter-recording').count(),11);
            assert.equal(await cards.nth(6).locator('.student-progress-review-trigger').count(),1);
            await cards.nth(6).locator('.student-progress-review-close').click();
            for(const action of ['retry','checked']){
                await page.evaluate(()=>window.openProgress());
                const traceCard=cards.nth(6);
                await openReview(6);
                const playing=await traceCard.locator('audio').elementHandle();
                await playing.evaluate(audio=>audio.play());
                await traceCard.locator(`.student-progress-lesson29-action[data-action="${action}"]`).click();
                await page.waitForFunction(()=>!document.querySelector('.student-progress-card:last-child .student-progress-review-trigger'));
                assert.deepEqual(posts.at(-1),{url:'/test/teacher_lesson29_trace_say_review_action',data:{student_id:String(studentId),action}});
                assert.equal(await traceCard.locator('.student-progress-recording, dialog, .student-progress-review-trigger').count(),0);
                assert.equal(await playing.evaluate(audio=>audio.paused),true,'Successful review actions must stop playback');
                assert.equal(await traceCard.evaluate(card=>card===document.activeElement),true);
                assert.equal(await page.locator('#courseInlineDialogHost').getAttribute('data-inline-modal-id'),'studentProgressModal');
                assert.equal(await cards.nth(4).locator('.student-progress-review-trigger').count(),1,'Other activity reviews must remain available');
                await playing.dispose();
            }
            }else{
                await openReview(6);
                assert.equal(await cards.nth(6).locator('.student-progress-lesson29-action[data-action="checked"]').isDisabled(),true,'Partial reviews cannot finalize Trace & Say');
                assert.equal(await cards.nth(6).locator('.student-progress-lesson29-action[data-action="retry"]').isEnabled(),true);
                await cards.nth(6).locator('.student-progress-review-close').click();
            }
            await page.locator('#studentProgressSearch').fill('Trace');
            assert.equal(await cards.count(),1);
            assert.equal(await cards.locator('.student-progress-type').textContent(),'Session 13');
            await page.locator('#studentProgressSearch').fill('');
            await page.locator('#studentProgressSort').selectOption('latest');
            assert.deepEqual(await cards.locator('.student-progress-type').allTextContents(),['Session 1','Session 4','Session 4','Session 5','Session 5','Session 5','Session 13']);
            await openReview(4);
            await page.evaluate(()=>bootstrap.Modal.getInstance(document.getElementById('studentProgressModal')).hide());
            await page.waitForFunction(()=>!document.querySelector('dialog[open]'));
            assert.equal(await page.locator('#courseInlineDialogHost').evaluate(node=>node.classList.contains('d-none')),true);
            assert.deepEqual(errors,[]);
            await page.close();
        }
        if(!process.env.PABASA_REVIEW_GATE_ONLY&&!lesson1Only)console.log('PASS: all seven compact review headers/counts, three columns, neutral unattempted/read-only skipped rows, playback, original fluency/binary scores and Lesson 1 review actions, failure recovery, fixed summary/list-only scrolling, desktop/mobile resizing. '+(live?'Authorized real endpoints in disposable DB.':'Isolated mocked API fixtures at six display configurations, including Trace & Say retry/finalization actions.'));
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
