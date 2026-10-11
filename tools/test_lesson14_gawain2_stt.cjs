// Real isolated Django page/API; capture and feedback playback are simulated.
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PABASA_PLAYWRIGHT_PATH || 'playwright-core');
(async()=>{
    assert(process.env.PABASA_L14_SERVER && process.env.PABASA_L14_STUDENT_COOKIE,
        'Run only through the disposable Django browser test.');
    const browser = await chromium.launch({channel:'chrome',headless:true});
    try {
        const base = process.env.PABASA_L14_SERVER;
        const page = await browser.newPage();
        const errors=[], responses=[];
        page.on('pageerror', error=>errors.push(error.message));
        await page.context().addCookies([{name:'sessionid',value:process.env.PABASA_L14_STUDENT_COOKIE,url:base}]);
        await page.addInitScript(()=>{
            window.testFeedback=[];
            HTMLMediaElement.prototype.play=function(){
                window.testFeedback.push(this.src);
                // Model the activity's main instruction lasting longer than
                // its separate intro cue; both existing listeners are retained.
                setTimeout(()=>this.dispatchEvent(new Event('ended')),
                    this.src.includes('ano_ang_nasa_larawan') ? 40 : 1);
                return Promise.resolve();
            };
            HTMLMediaElement.prototype.pause=function(){};
        });
        const installCapture=()=>page.evaluate(()=>{
            const stream={getTracks:()=>[{stop(){}}]};
            window.Basahin={...window.Basahin,openMicrophone:async()=>stream,
                capture:async options=>{
                    window.testCaptureFields=options.fields;
                    if(options.fields.language!=='fil-PH')throw Error('Capture language changed');
                    if(!['mata','buto','tala','nipa','tubo','nota'].includes(options.fields.target_text))throw Error('Capture context missing');
                    return new Blob(['disposable-recording'],{type:'audio/webm'});
                }};
        });
        await page.goto(base+process.env.PABASA_L14_URL);
        await installCapture();
        const begin=()=>page.locator('#begin').click();
        const activeItem=()=>page.locator('.progress .active').textContent();
        await begin();
        await page.waitForFunction(()=>!document.querySelector('#read')?.disabled);
        for(const [number, expectedItem, expectedMatch] of [[1,'1',false],[2,'2',true],[3,'2',false],[4,'3',true]]){
            const reply=page.waitForResponse(response=>response.url().endsWith('/api/reading/transcribe/'),{timeout:10000});
            reply.catch(()=>{});
            await page.locator('#read').click();
            const response=await reply.catch(async error=>{throw Error(`${error.message}; phase ${number}; diagnostics ${JSON.stringify(await page.evaluate(()=>({capture:window.testCaptureFields,label:document.querySelector('#read')?.textContent,disabled:document.querySelector('#read')?.disabled})))}`);});
            assert.equal(response.status(),200);
            const result=await response.json();responses.push(result);
            assert.equal(result.complete,expectedMatch);
            assert.equal(result.language_code,'fil-PH');
            await page.waitForFunction(item=>document.querySelector('.progress .active')?.textContent===item&& !document.querySelector('#read')?.disabled,expectedItem);
            assert.equal(await activeItem(),expectedItem);
            if(number===1){
                assert.equal(result.recognition_rejected_reason,'non_filipino_language');
                assert(await page.evaluate(()=>window.testFeedback.some(url=>/kaya_mo_yan_ulitin_natin|isa_pa_subukan_mong_muli/.test(url))));
                // Reload after a rejected attempt: same item, retryable, no
                // reset or artificial successful reading from normalization.
                await page.reload();
                await installCapture();
                await begin();
                await page.waitForFunction(()=>!document.querySelector('#read')?.disabled);
                assert.equal(await activeItem(),'1');
            }
        }
        await page.reload();
        await installCapture();
        await begin();
        await page.waitForFunction(()=>!document.querySelector('#read')?.disabled);
        assert.equal(await activeItem(),'3');
        assert.equal(responses[0].raw_transcript,'mata 한국');
        assert.equal(responses[2].raw_transcript,'오 야 이');
        assert.deepEqual(errors,[]);
        console.log('PASS browser: actual L14 G2 page/API, Korean and mixed-script no-match feedback, retry on same item, Filipino/segmented success, capture context, failed-attempt refresh and saved advancement. Microphone, speech provider and audio playback simulated.');
    } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
