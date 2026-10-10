// Exercise the actual course progress renderer and delegated review handlers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
const root = path.resolve(__dirname, '..');
const app = path.join(root, 'pabasa_site/pabasa_app');
const template = fs.readFileSync(path.join(app, 'templates/pabasa_app/courses.html'), 'utf8');
const between = (start, end) => {
    const first = template.indexOf(start), last = template.indexOf(end, first);
    assert(first >= 0 && last > first, start);
    return template.slice(first, last);
};
const urls = text => text.replace(/{% url ["']([^"']+)["'] %}/g, '/test/$1');
const progress = between('        function progressStudentMatches(', "        if (e.target.closest('.view-student-progress'))");
const audio = between('    const studentProgressRetellGrades = new Map();', '    // Existing course student-progress actions');
const grades = between("    document.addEventListener('click', function(event) {\n        const fluencyButton", "    document.addEventListener('input', function(event) {");
const fluency = between("    document.addEventListener('change', function(event) {\n        const select = event.target.closest('.session5-fluency-select')", "    document.addEventListener('click', function(event) {\n        const courseTrigger");
const adapter = between('    function installCourseInlineModalAdapter() {', '    installCourseInlineModalAdapter();');
const modalHtml = between('<div class="modal fade" id="studentProgressModal"', '<script>\ndocument.addEventListener');
const courseCss = [...template.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(match => match[1]).join('\n');
const dashboard = fs.readFileSync(path.join(app, 'templates/pabasa_app/base_dashboard.html'), 'utf8');
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
    session4_total_items:index===2?12:4, session4_correct_items:0,
    session4_recordings:Array.from({length:index===2?8:4}, (_, item) => ({
        submission_id:200+item, item_label:letters[item%4], teacher_score:null,
        recording_available:item===0, audio_url:item===0?'/recording.wav':null,
    })),
    session5_recordings:Array.from({length:22}, (_, item) => ({
        item_index:item, expected_text:'Reading '+(item+1), submission_id:item===1?301:null,
        classification:item===0?'RED':'', classification_source:item===0?'skipped':'',
        review_status:item===0?'skipped':'pending', recording_url:item===1?'/recording.wav':null,
    })),
}]}]));
const setup = `
const course={title:'Reading course',materials:[],sections:[]};
const findCourseById=()=>course, activeRecords=rows=>rows, classReadings={};
const rawRecordId=value=>value, fetchAssessmentProgressDetails=async()=>(${JSON.stringify(attempts)});
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const latestAttemptValue=(attempt,...keys)=>keys.map(key=>attempt[key]).find(value=>value!==undefined);
const reviewToasts=[];
const formatDateTime=String,formatCourseReportDuration=String,ensureCsrfToken=async()=>'test',showToast=(message,type)=>reviewToasts.push({message,type});
class Modal{constructor(element){this._element=element;Modal.instances.set(element,this)}show(){this._element.classList.add('show')}hide(){this._element.classList.remove('show');this._element.dispatchEvent(new Event('hidden.bs.modal'))}static getOrCreateInstance(element){return Modal.getInstance(element)||new Modal(element)}static getInstance(element){return Modal.instances.get(element)}}
Modal.instances=new WeakMap();window.bootstrap={Modal};
${audio}
${urls(progress)}
${urls(grades)}
${urls(fluency)}
${adapter}
installCourseInlineModalAdapter();
window.openProgress=()=>openStudentProgressModal(48,'Test student','1');
`;

new (require('node:vm').Script)(setup);
(async()=>{
    const browser = await chromium.launch({channel:'chrome',headless:true});
    try {
        for (const [width,height,ratio] of [[1918,997,1],[1366,900,1.25],[1366,768,1.5],[1024,500,1],[390,844,1],[844,390,1]]) {
            const page = await browser.newPage({viewport:{width,height},deviceScaleFactor:ratio,
                userAgent:'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36'});
            const errors=[],posts=[];
            page.on('pageerror',error=>errors.push(error.message));
            let failNext=false;
            await page.route('**/*', async route=>{
                const request=route.request(),url=new URL(request.url());
                if(url.pathname==='/activity')return route.fulfill({contentType:'text/html',body:'<!doctype html><html></html>'});
                if(url.pathname.startsWith('/test/')) {
                    const data=request.postDataJSON();posts.push({url:url.pathname,data});
                    const fail=failNext;failNext=false;
                    return route.fulfill({status:fail?500:200,contentType:'application/json',body:JSON.stringify(fail?{success:false,error:'Test save failure'}:{success:true,all_reviewed:true,correct_items:1,total_items:4,status:'checked'})});
                }
                if(url.pathname==='/recording.wav')return route.fulfill({contentType:'audio/wav',body:wav});
                return route.fulfill({status:404,body:''});
            });
            await page.goto('http://localhost:9876/activity');
            await page.setContent(`<style>body{font-family:Arial;margin:0}.d-none{display:none!important}.modal:not(.course-detail-page){display:none}.student-progress-list{display:grid;gap:12px}.student-progress-card{border:1px solid #dce8ed;border-radius:12px;padding:16px}.student-progress-card-header,.student-progress-stats{display:flex;justify-content:space-between}.student-progress-title{margin:8px 0}.student-progress-type{font-size:12px;color:#176078}.student-progress-stats{margin-top:12px}.student-progress-stat-label{display:block;font-size:11px}.form-select{padding:10px;width:100%}${courseCss}${fs.readFileSync(path.join(app,'static/pabasa_app/css/student_activity_review.css'),'utf8')}</style><main id="courseDetailModal" class="course-detail-page"><button class="course-modal-close-btn" data-bs-dismiss="modal">Close course</button><div id="courseMainContent"></div><aside id="courseSidebar"></aside><div id="courseInlineDialogHost"></div></main>${modalHtml}`);
            await page.addStyleTag({content:dashboardCss});
            await page.evaluate(()=>document.getElementById('courseDetailModal').classList.add('dashboard-app-shell'));
            await page.addScriptTag({content:displayScale});
            await page.addScriptTag({path:path.join(app,'static/pabasa_app/js/student_activity_review.js')});
            await page.addScriptTag({content:setup});
            assert.deepEqual(errors,[]);
            await page.evaluate(()=>window.openProgress());
            const cards=page.locator('#studentProgressList > .student-progress-card');
            assert.equal(await cards.count(),6);
            assert.deepEqual(await cards.locator('.student-progress-type').allTextContents(),['Session 1','Session 4','Session 4','Session 5','Session 5','Session 13']);
            assert.equal(await page.locator('dialog[open]').count(),0);
            assert.equal(await page.locator('.session4-letter-recording:visible').count(),0);
            assert.equal(await page.locator('.session5-fluency-row:visible').count(),0);
            for(const [index,count] of [[1,4],[2,8],[3,4],[5,4]]){
                await cards.nth(index).locator('.student-progress-review-trigger').click();
                const dialog=cards.nth(index).locator('dialog');
                await assertReviewFits(dialog);
                assert.equal(await dialog.locator('.student-progress-review-footer').count(),0);
                assert.equal(await dialog.getByRole('button',{name:'Back to activities'}).count(),0);
                assert.equal(await dialog.locator('.session4-letter-recording:visible').count(),count);
                assert.equal(await dialog.locator('audio').count(),1);
                assert.equal(await dialog.locator('.session4-no-recording').count(),count-1);
                await dialog.locator('.session4-score-button[data-score="1"]').click();
                await dialog.locator('.session4-score-feedback').filter({hasText:'Saved'}).waitFor();
                assert.equal(posts.at(-1).data.score,1);
                assert(posts.at(-1).url.endsWith(['teacher_session_4_gawain_1_score','teacher_session_4_gawain_2_score','teacher_lesson_13_gawain_1_score',null,'teacher_lesson29_trace_say_score'][index-1]));
                assert.equal(await cards.nth(index).locator('.student-progress-score').textContent(),'1/4');
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
                assert.equal(await dialog.locator('audio').evaluate(audio=>audio.paused),true);
                assert.equal(await page.locator('#courseInlineDialogHost').getAttribute('data-inline-modal-id'),'studentProgressModal');
                assert.equal(await cards.nth(index).locator('.student-progress-review-trigger').evaluate(node=>node===document.activeElement),true);
                await cards.nth(index).locator('.student-progress-review-trigger').click();
                assert.equal(await dialog.locator('.session4-score-button.selected').getAttribute('data-score'),'1');
                await dialog.locator('.student-progress-review-close').click();
            }
            await cards.nth(4).locator('.student-progress-review-trigger').click();
            const fluencyDialog=cards.nth(4).locator('dialog');
            await assertReviewFits(fluencyDialog);
            assert.equal(await fluencyDialog.locator('.session5-fluency-row').count(),22);
            assert.equal(await fluencyDialog.locator('.session5-fluency-select').nth(0).isDisabled(),true);
            await fluencyDialog.locator('.session5-fluency-select').nth(1).selectOption('GREEN');
            await fluencyDialog.locator('.session5-review-state').nth(1).filter({hasText:'reviewed'}).waitFor();
            assert.equal(posts.at(-1).data.classification,'GREEN');
            assert.equal(posts.at(-1).url,'/test/teacher_session_5_lesson_14_gawain_4_classify');
            assert(await fluencyDialog.evaluate(dialog=>dialog.scrollWidth<=dialog.clientWidth+2));
            assert(await fluencyDialog.locator('.student-progress-review-body').evaluate(body=>body.scrollHeight>body.clientHeight));
            await fluencyDialog.locator('.student-progress-review-body').evaluate(body=>body.scrollTo(0,body.scrollHeight));
            await assertReviewFits(fluencyDialog);
            if(width===1918){
                for(const size of [{width:390,height:844},{width,height}]){
                    await page.setViewportSize(size);
                    await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
                    await assertReviewFits(fluencyDialog);
                }
            }
            await fluencyDialog.locator('.student-progress-review-body').evaluate(body=>body.scrollTo(0,0));
            if(process.env.PABASA_REVIEW_SCREENSHOTS)await page.screenshot({path:path.join(process.env.PABASA_REVIEW_SCREENSHOTS,`teacher-recording-review-${width}.png`)});
            await fluencyDialog.locator('.student-progress-review-close').click();
            await cards.nth(0).locator('.student-progress-review-trigger').click();
            await cards.nth(0).locator('.student-progress-retell-play').click();
            await page.waitForFunction(()=>activeStudentProgressAudio && !activeStudentProgressAudio.paused);
            await cards.nth(0).locator('.student-progress-lesson1-action[data-action="checked"]').click();
            await page.waitForFunction(()=>!document.querySelector('.lesson1-review-actions'));
            assert.equal(posts.at(-1).url,'/test/teacher_lesson_1_gawain_1_review_action');
            assert.equal(await cards.nth(0).locator('.student-progress-score').textContent(),'1');
            await cards.nth(0).locator('.student-progress-review-close').click();
            await page.waitForFunction(()=>activeStudentProgressAudio===null);
            await cards.nth(5).locator('.student-progress-review-trigger').click();
            failNext=true;
            await cards.nth(5).locator('.student-progress-lesson29-action[data-action="checked"]').click();
            await page.waitForFunction(()=>reviewToasts.at(-1)?.message==='Test save failure');
            assert.equal(await cards.nth(5).locator('dialog[open]').count(),1,'Failed review actions must keep the review open');
            assert.equal(await cards.nth(5).locator('.session4-letter-recording').count(),4);
            assert.equal(await cards.nth(5).locator('.student-progress-review-trigger').count(),1);
            await cards.nth(5).locator('.student-progress-review-close').click();
            for(const action of ['retry','checked']){
                await page.evaluate(()=>window.openProgress());
                const traceCard=cards.nth(5);
                await traceCard.locator('.student-progress-review-trigger').click();
                const playing=await traceCard.locator('audio').elementHandle();
                await playing.evaluate(audio=>audio.play());
                await traceCard.locator(`.student-progress-lesson29-action[data-action="${action}"]`).click();
                await page.waitForFunction(()=>!document.querySelector('.student-progress-card:last-child .student-progress-review-trigger'));
                assert.deepEqual(posts.at(-1),{url:'/test/teacher_lesson29_trace_say_review_action',data:{student_id:'48',action}});
                assert.equal(await traceCard.locator('.student-progress-recording, dialog, .student-progress-review-trigger').count(),0);
                assert.equal(await playing.evaluate(audio=>audio.paused),true,'Successful review actions must stop playback');
                assert.equal(await traceCard.evaluate(card=>card===document.activeElement),true);
                assert.equal(await page.locator('#courseInlineDialogHost').getAttribute('data-inline-modal-id'),'studentProgressModal');
                assert.equal(await cards.nth(4).locator('.student-progress-review-trigger').count(),1,'Other activity reviews must remain available');
                await playing.dispose();
            }
            await page.locator('#studentProgressSearch').fill('Trace');
            assert.equal(await cards.count(),1);
            assert.equal(await cards.locator('.student-progress-type').textContent(),'Session 13');
            await page.locator('#studentProgressSearch').fill('');
            await page.locator('#studentProgressSort').selectOption('latest');
            assert.deepEqual(await cards.locator('.student-progress-type').allTextContents(),['Session 1','Session 4','Session 4','Session 5','Session 5','Session 13']);
            await cards.nth(4).locator('.student-progress-review-trigger').click();
            await page.evaluate(()=>bootstrap.Modal.getInstance(document.getElementById('studentProgressModal')).hide());
            await page.waitForFunction(()=>!document.querySelector('dialog[open]'));
            assert.equal(await page.locator('#courseInlineDialogHost').evaluate(node=>node.classList.contains('d-none')),true);
            assert.deepEqual(errors,[]);
            await page.close();
        }
        console.log('PASS: Lesson 29 retry/completion cleanup and failure preservation; X-only dismissal, viewport bounds at six display configurations, resizing, scrolling, ordering, playback, grading, reopening, focus, course parent and search/sort.');
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
