// Use only through the disposable Django test. Actual page/progress APIs;
// microphone, speech provider and audio playback are simulated.
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
(async()=>{
  assert(process.env.PABASA_L15G2_SERVER && process.env.PABASA_L15G2_STUDENT_COOKIE,
    'Run through the disposable Django browser test.');
  const browser = await chromium.launch({channel:'chrome',headless:true});
  try {
    const base=process.env.PABASA_L15G2_SERVER, page=await browser.newPage(), errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.context().addCookies([{name:'sessionid',value:process.env.PABASA_L15G2_STUDENT_COOKIE,url:base}]);
    await page.addInitScript(()=>{
      window.testFeedback=[];
      HTMLMediaElement.prototype.play=function(){
        window.testFeedback.push(this.src);
        setTimeout(()=>this.dispatchEvent(new Event('ended')),this.src.includes('ano_ang_nasa_larawan')?40:1);
        return Promise.resolve();
      };
      HTMLMediaElement.prototype.pause=function(){};
      const timer=window.setTimeout.bind(window);
      window.setTimeout=(fn,ms,...args)=>timer(fn,ms===4000?1:ms,...args);
      const track=new EventTarget();
      track.readyState='live';track.enabled=true;
      track.stop=()=>{track.readyState='ended';track.dispatchEvent(new Event('ended'));};
      navigator.mediaDevices.getUserMedia=async()=>({getTracks:()=>[track],getAudioTracks:()=>[track]});
      window.MediaRecorder=class {
        constructor(){this.mimeType='audio/webm';}
        start(){}
        stop(){this.ondataavailable?.({data:new Blob(['disposable-recording'],{type:this.mimeType})});this.onstop?.();}
      };
    });
    const ready=()=>page.waitForFunction(()=>document.querySelector('#read')&&!document.querySelector('#read').disabled);
    const current=()=>page.locator('.progress .active').textContent();
    await page.goto(base+process.env.PABASA_L15G2_URL);
    const data=await page.locator('#lesson15-gawain2-data').textContent();
    const parsed=JSON.parse(data);
    assert.deepEqual(parsed.part1_items.map(item=>item.word),['yo-yo','masaya','yungib','oyayi','yelo']);
    await page.locator('#begin').click();await ready();
    for(const [number, nextItem, rejected] of [[1,'1',true],[2,'2',false],[3,'2',true],
         [4,'2',true],[5,'3',false],[6,'4',false],[7,'4',false],[8,'5',false],[9,null,false]]){
      const reply=page.waitForResponse(response=>response.url().endsWith('/api/reading/transcribe/'));
      await page.locator('#read').click();
      const response=await reply;
      assert.equal(response.status(),200);
      const result=await response.json();
      assert.equal(result.language_code,'fil-PH');
      if(rejected){
        assert.equal(result.recognition_rejected_reason,'non_filipino_language');
        assert.equal(result.complete,false);
      }
      if(number===7)assert.equal(result.complete,false);
      if(nextItem){
        await page.waitForFunction(item=>document.querySelector('.progress .active')?.textContent===item&&!document.querySelector('#read')?.disabled,nextItem);
        assert.equal(await current(),nextItem);
      } else {
        await page.waitForFunction(()=>document.querySelector('.board')&&!document.querySelector('[data-a]')?.disabled);
      }
      if(number===1){
        assert(await page.evaluate(()=>window.testFeedback.some(url=>/kaya_mo_yan_ulitin_natin|isa_pa_subukan_mong_muli/.test(url))));
        await page.reload();await page.locator('#begin').click();await ready();
        assert.equal(await current(),'1');
      }
    }
    // Completing reading alone must not complete the syllable matching phase.
    assert.equal(await page.locator('.completion').count(),0);
    assert.equal(await page.locator('#finish').isDisabled(),true);
    await page.reload();await page.locator('#begin').click();
    await page.waitForFunction(()=>document.querySelector('.board')&&!document.querySelector('[data-a]')?.disabled);
    for(const item of parsed.items){
      const save=page.waitForResponse(response=>response.url()===base+parsed.progress_url&&response.request().method()==='POST');
      await page.locator(`[data-a="${item.id}"]`).click();
      await page.locator(`.column [data-b="${item.expected_b_id}"]`).click();
      const response=await save;
      assert.equal(response.status(),200);
      assert.equal((await response.json()).success,true);
    }
    assert.equal(await page.locator('.svg-overlay line').count(),5);
    assert.equal(await page.locator('#finish').isEnabled(),true);
    const complete=page.waitForResponse(response=>response.url()===base+parsed.completion_url);
    await page.locator('#finish').click();
    assert.equal((await complete).status(),200);
    await page.locator('.completion').waitFor();
    await page.reload();await page.locator('.completion').waitFor();
    assert.deepEqual(errors,[]);
    console.log('PASS L15 G2 browser: mixed Hangul/Korean metadata blocked, retry and refresh preserved, five words/segmentation/hielo allowance, reading-to-matching transition, connections and completion persisted. Capture, provider and audio simulated.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
